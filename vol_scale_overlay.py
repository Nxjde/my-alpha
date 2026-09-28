"""
vol_scale_overlay.py

목적:
momentum+reversal(1:1) 조합 위에 "포트폴리오 레벨 변동성 스케일링" 오버레이를 얹어서,
2017-2019처럼 최악인 레짐에서 익스포저를 줄이는 게 실제로 도움이 되는지 검증한다.

설계 원칙 (STATE.md 핵심 발견 2번과 충돌하지 않도록):
- 종목 선택/필터링 로직은 절대 건드리지 않는다 (이미 실패로 결론난 영역).
- 오직 "포트폴리오 전체 비중을 얼마나 태울지"만 최근 실현 변동성 percentile로 조절한다.
- 판단(discretion)이 들어가지 않는 완전 규칙 기반: threshold를 넘으면 자동으로 scale down.

USAGE (EC2, ~/my-alpha 에서):
    python3.11 vol_scale_overlay.py

실행 전 꼭 확인/수정해야 하는 것 (아래 CONFIG 섹션):
1. DUCKDB_PATH, PRICES_PATH 경로가 실제 프로젝트 구조와 맞는지
2. duckdb의 weights 테이블 실제 컬럼명 (as_of/date, symbol, weight 등 이름이 다를 수 있음)
   -> 스크립트 맨 아래 `if __name__` 블록에서 duckdb.sql("DESCRIBE main.weights__momentum")
      먼저 찍어보고 컬럼명 맞춰서 load_weights() 함수 수정
3. real_prices.csv 컬럼명 (ts/symbol/close 등)도 동일하게 먼저 head로 확인
4. SPLITS의 실제 in/out 경계가 qanat.yaml에 설정된 값과 일치하는지
   (STATE.md에는 out-of-sample 결과만 있고 정확한 split 날짜는 기록 안 돼 있어서
    momentum_reversal_sweep.py / split_sweep_long.py 안의 실제 split 날짜를 확인해서 맞출 것)
"""

import duckdb
import numpy as np
import pandas as pd

# ---------------- CONFIG (실행 전 검증 필요) ----------------
DUCKDB_PATH = "data/qanat.duckdb"
PRICES_PATH = "data/real_prices.csv"

# 5개 구간 (STATE.md 기준, out-of-sample 구간 경계값 — 실제 in/out split 지점은
# 프로젝트의 다른 sweep 스크립트에서 확인해서 맞출 것)
PERIODS = [
    ("2015-01-01", "2017-01-01"),
    ("2017-01-01", "2019-01-01"),
    ("2019-01-01", "2021-01-01"),
    ("2021-01-01", "2023-01-01"),
    ("2023-01-01", "2025-01-01"),
]

# 변동성 스케일링 파라미터
VOL_LOOKBACK_DAYS = 20          # 실현 변동성 계산 윈도우
VOL_PCTL_LOOKBACK_DAYS = 252    # percentile 산출용 lookback (rolling, 1년)
VOL_PCTL_THRESHOLD = 0.80       # 이 percentile 넘으면 스케일 다운
SCALE_DOWN_FACTOR = 0.5         # 초과 시 익스포저를 이 배수로 축소 (1.0 = 스케일링 없음)

FEE_BPS = 5
SLIPPAGE_BPS = 10
N_PERMUTATIONS = 2000
P_THRESHOLD = 0.05


def load_weights(duckdb_path: str) -> pd.DataFrame:
    """
    main.weights__momentum, main.weights__reversal를 0.5/0.5로 합쳐서
    (date, symbol, weight) 형태의 결합 포트폴리오 비중 시계열을 반환.
    -- 컬럼명은 실제 스키마 확인 후 맞출 것 (아래는 가정) --
    """
    con = duckdb.connect(duckdb_path, read_only=True)
    mom = con.sql("SELECT * FROM main.weights__momentum").df()
    rev = con.sql("SELECT * FROM main.weights__reversal").df()
    con.close()

    # TODO: 실제 컬럼명에 맞춰 rename (as_of->date, symbol, weight 가정)
    mom = mom.rename(columns={"as_of": "date"})
    rev = rev.rename(columns={"as_of": "date"})

    combined = pd.concat([
        mom.assign(weight=mom["weight"] * 0.5),
        rev.assign(weight=rev["weight"] * 0.5),
    ])
    combined = combined.groupby(["date", "symbol"], as_index=False)["weight"].sum()
    return combined


def load_prices(prices_path: str) -> pd.DataFrame:
    """(date, symbol, close) 형태로 로드. 컬럼명은 실제 CSV 확인 후 맞출 것."""
    px = pd.read_csv(prices_path, parse_dates=["ts"])
    px = px.rename(columns={"ts": "date", "Close": "close"})
    return px[["date", "symbol", "close"]]


def build_portfolio_returns(weights: pd.DataFrame, prices: pd.DataFrame) -> pd.Series:
    """일별 결합 포트폴리오 수익률 시계열 계산 (비용 반영 전, gross)."""
    px = prices.pivot(index="date", columns="symbol", values="close").sort_index()
    daily_ret = px.pct_change()

    w = weights.pivot(index="date", columns="symbol", values="weight").sort_index()
    w = w.reindex(daily_ret.index).ffill().fillna(0.0)

    port_ret = (w.shift(1) * daily_ret).sum(axis=1)  # t-1 비중으로 t 수익 계산
    return port_ret.dropna()


def apply_vol_scaling(port_ret: pd.Series) -> pd.Series:
    """실현 변동성 percentile 기반으로 exposure를 스케일링한 수익률 시계열 반환."""
    realized_vol = port_ret.rolling(VOL_LOOKBACK_DAYS).std() * np.sqrt(252)
    vol_pctl = realized_vol.rolling(VOL_PCTL_LOOKBACK_DAYS).apply(
        lambda s: (s.iloc[-1] > s).mean(), raw=False
    )
    scale = np.where(vol_pctl > VOL_PCTL_THRESHOLD, SCALE_DOWN_FACTOR, 1.0)
    scale = pd.Series(scale, index=port_ret.index).shift(1).fillna(1.0)  # look-ahead 방지
    return port_ret * scale, scale


def apply_costs(port_ret: pd.Series, scale: pd.Series) -> pd.Series:
    """스케일 변화(turnover 증가분)에 대해서만 대략적 비용을 반영 (단순화된 근사)."""
    turnover_from_scaling = scale.diff().abs().fillna(0.0)
    cost = turnover_from_scaling * (FEE_BPS + SLIPPAGE_BPS) / 10000
    return port_ret - cost


def period_net_return(daily_ret: pd.Series, start: str, end: str) -> float:
    seg = daily_ret.loc[start:end]
    if len(seg) < 20:
        return np.nan
    return (1 + seg).prod() - 1


def permutation_test(daily_ret: pd.Series, start: str, end: str, n_perm: int = N_PERMUTATIONS) -> float:
    """구간별 gross 부호만 랜덤 뒤집는 permutation test (비용은 고정 drag로 유지)."""
    seg = daily_ret.loc[start:end].dropna()
    if len(seg) < 20:
        return np.nan
    actual = (1 + seg).prod() - 1

    rng = np.random.default_rng(42)
    sim_results = []
    for _ in range(n_perm):
        flips = rng.choice([-1, 1], size=len(seg))
        sim = seg * flips
        sim_results.append((1 + sim).prod() - 1)
    sim_results = np.array(sim_results)
    p_value = (np.sum(sim_results >= actual) + 1) / (n_perm + 1)
    return p_value


def main():
    weights = load_weights(DUCKDB_PATH)
    prices = load_prices(PRICES_PATH)

    base_ret = build_portfolio_returns(weights, prices)
    scaled_ret_raw, scale = apply_vol_scaling(base_ret)
    scaled_ret = apply_costs(scaled_ret_raw, scale)

    print(f"{'구간':<20}{'기존(1:1)':>12}{'vol-scaled':>14}{'scaled p-value':>16}")
    for start, end in PERIODS:
        base_net = period_net_return(base_ret, start, end)
        scaled_net = period_net_return(scaled_ret, start, end)
        p_val = permutation_test(scaled_ret, start, end)
        label = f"{start[:4]}~{end[:4]}"
        print(f"{label:<20}{base_net:>11.1%}{scaled_net:>13.1%}{p_val:>15.3f}")


if __name__ == "__main__":
    main()
