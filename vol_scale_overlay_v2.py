"""
vol_scale_overlay_v2.py

sleeve_combine.py와 동일한 방식(qanat backtest --json으로 momentum/reversal을 각각
solo로 돌려서 캐시한 뒤, 로컬에서 비율대로 합산)을 그대로 쓰되, 합산된 리밸런싱-주기별
수익률 시계열에 "포트폴리오 레벨 변동성 스케일링"을 얹는다.

종목 선택 로직은 전혀 건드리지 않음 (momentum/reversal alpha 자체는 그대로) -- 오직
"1:1로 합산한 결과를 얼마나 태울지"만 최근 실현 변동성 percentile로 조절.

USAGE:
    python3.11 vol_scale_overlay_v2.py
"""

import subprocess
import json
import numpy as np

PERIODS = [
    {"from": "2015-01-01", "to": "2017-12-31", "split": "2016-07-01"},
    {"from": "2017-01-01", "to": "2019-12-31", "split": "2018-07-01"},
    {"from": "2019-01-01", "to": "2021-12-31", "split": "2020-07-01"},
    {"from": "2021-01-01", "to": "2023-12-31", "split": "2022-07-01"},
    {"from": "2023-01-01", "to": "2025-12-31", "split": "2024-07-01"},
]

# vol 스케일링 파라미터
VOL_LOOKBACK_PERIODS = 12       # 최근 몇 개 리밸런싱 주기로 실현 변동성 계산할지
VOL_PCTL_LOOKBACK = 26          # percentile 산출용 lookback (리밸런싱 주기 수)
VOL_PCTL_THRESHOLD = 0.80       # 이 percentile 넘으면 스케일 다운
SCALE_DOWN_FACTOR = 0.5         # 초과 시 익스포저 축소 배수

N_PERMUTATIONS = 2000


def run_solo(alpha_name, period):
    cmd = [
        "qanat", "backtest",
        "--from", period["from"], "--to", period["to"],
        "--alpha", alpha_name,
        "--split", period["split"],
        "--json", "--quiet", "--force",
    ]
    out = subprocess.run(cmd, capture_output=True, text=True)
    start = out.stdout.find("{")
    if start == -1:
        raise RuntimeError(f"{alpha_name} {period}: JSON 못 찾음 -> {out.stdout[:300]} {out.stderr[:300]}")
    return json.loads(out.stdout[start:])


def compound(net_list):
    equity = 1.0
    for n in net_list:
        equity *= 1.0 + n
    return equity - 1.0


def build_blended_series(m_json, r_json, w_m=1.0, w_r=1.0):
    """momentum/reversal 1:1 합산 (period 단위) 시계열: [(as_of, blended_net), ...] 정렬됨."""
    by_date_m = {p["as_of"]: p["net"] for p in m_json["periods"]}
    by_date_r = {p["as_of"]: p["net"] for p in r_json["periods"]}
    dates = sorted(set(by_date_m) & set(by_date_r))
    total_w = w_m + w_r
    wm, wr = w_m / total_w, w_r / total_w
    return [(d, wm * by_date_m[d] + wr * by_date_r[d]) for d in dates]


def apply_vol_scaling(series):
    """series: [(date, net), ...] -> [(date, scaled_net), ...]
    look-ahead 방지를 위해 t 시점 스케일은 t-1까지의 정보로만 결정."""
    dates = [d for d, _ in series]
    nets = np.array([n for _, n in series])

    scaled = []
    for i in range(len(nets)):
        if i < VOL_LOOKBACK_PERIODS + 1:
            scale = 1.0  # 초기 구간은 데이터 부족 -> 스케일링 없음
        else:
            window = nets[max(0, i - VOL_LOOKBACK_PERIODS - VOL_PCTL_LOOKBACK):i]
            realized_vol_series = np.array([
                np.std(window[max(0, j - VOL_LOOKBACK_PERIODS):j])
                for j in range(VOL_LOOKBACK_PERIODS, len(window) + 1)
            ])
            if len(realized_vol_series) < 2:
                scale = 1.0
            else:
                current_vol = realized_vol_series[-1]
                pctl = (realized_vol_series < current_vol).mean()
                scale = SCALE_DOWN_FACTOR if pctl > VOL_PCTL_THRESHOLD else 1.0
        scaled.append((dates[i], nets[i] * scale))
    return scaled


def split_in_out(series, split_date):
    in_sample = [n for d, n in series if d < split_date]
    out_sample = [n for d, n in series if d >= split_date]
    return in_sample, out_sample


def permutation_p_value(out_sample_net, n_perm=N_PERMUTATIONS):
    """구간별 부호만 랜덤 뒤집는 단순화된 permutation test.
    (주의: STATE.md의 원래 방법론은 비용을 고정 drag로 유지하며 gross만 뒤집었음 --
    여기서는 net 자체를 뒤집는 단순화 버전이라 완전히 동일하진 않음, 참고용으로만 사용)"""
    if len(out_sample_net) < 5:
        return np.nan
    actual = compound(out_sample_net)
    arr = np.array(out_sample_net)
    rng = np.random.default_rng(42)
    sims = []
    for _ in range(n_perm):
        flips = rng.choice([-1, 1], size=len(arr))
        sims.append(compound(list(arr * flips)))
    sims = np.array(sims)
    return (np.sum(sims >= actual) + 1) / (n_perm + 1)


def main():
    solo_cache = {}
    for name in ("momentum", "reversal"):
        for i, period in enumerate(PERIODS):
            print(f"running {name} solo: {period['from']}~{period['to']} ...")
            solo_cache[(name, i)] = run_solo(name, period)

    print(f"\n{'구간':<24}{'기존(1:1) OOS':>16}{'vol-scaled OOS':>18}{'scaled p-value':>16}")
    for i, period in enumerate(PERIODS):
        m_json = solo_cache[("momentum", i)]
        r_json = solo_cache[("reversal", i)]

        base_series = build_blended_series(m_json, r_json)
        _, base_out = split_in_out(base_series, period["split"])
        base_net = compound(base_out)

        scaled_series = apply_vol_scaling(base_series)
        _, scaled_out = split_in_out(scaled_series, period["split"])
        scaled_net = compound(scaled_out)
        p_val = permutation_p_value(scaled_out)

        label = f"{period['from'][:4]}~{period['to'][:4]}"
        print(f"{label:<24}{base_net:>15.1%}{scaled_net:>17.1%}{p_val:>16.3f}")


if __name__ == "__main__":
    main()
