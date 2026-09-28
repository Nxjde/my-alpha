"""
vol_target_with_rp.py

target_mult=0.7, cap=[0.5,2.0] vol targeting 위에, scale<1일 때 남는 유휴 현금을
KIS 외화RP(USD, 수시형 연 3.35% 세전 가정)로 운용했다고 가정해 수익을 추가.
레버리지(scale>1) 부분은 여전히 반영 안 함(계좌 규정상 100% 증거금이라 불가).
"""

import json
import statistics

PERIODS = [
    {"from": "2015-01-01", "to": "2017-12-31", "split": "2016-07-01"},
    {"from": "2017-01-01", "to": "2019-12-31", "split": "2018-07-01"},
    {"from": "2019-01-01", "to": "2021-12-31", "split": "2020-07-01"},
    {"from": "2021-01-01", "to": "2023-12-31", "split": "2022-07-01"},
    {"from": "2023-01-01", "to": "2025-12-31", "split": "2024-07-01"},
]

VOL_LOOKBACK_PERIODS = 12
TARGET_MULT = 0.70
MIN_CAP, MAX_CAP = 0.5, 2.0   # cap>1 부분은 실제로는 레버리지 불가하니 아래서 1.0으로 다시 클립
RP_ANNUAL_RATE = 0.0335       # USD RP 수시형 세전 연 3.35% (2026년 시점 고시금리)
REBALANCE_DAYS = 5

with open("solo_cache.json") as f:
    CACHE = json.load(f)


def compound(net_list):
    equity = 1.0
    for n in net_list:
        equity *= 1.0 + n
    return equity - 1.0


def build_blended_series(m_json, r_json, w_m=1.0, w_r=1.0):
    by_date_m = {p["as_of"]: p["net"] for p in m_json["periods"]}
    by_date_r = {p["as_of"]: p["net"] for p in r_json["periods"]}
    dates = sorted(set(by_date_m) & set(by_date_r))
    total_w = w_m + w_r
    wm, wr = w_m / total_w, w_r / total_w
    return [(d, wm * by_date_m[d] + wr * by_date_r[d]) for d in dates]


def realized_vol(window):
    if len(window) < 2:
        return None
    return statistics.pstdev(window)


def apply_vol_targeting_with_rp(series, target_vol, min_cap, max_cap, rp_period_rate):
    """scale은 [min_cap, 1.0]로 클립 (레버리지 불가 반영).
    (1 - scale) 만큼의 유휴 비중은 RP 이자를 받는다고 가정."""
    dates = [d for d, _ in series]
    nets = [n for _, n in series]
    scaled = []
    for i in range(len(nets)):
        if i < VOL_LOOKBACK_PERIODS:
            scale = 1.0
        else:
            window = nets[i - VOL_LOOKBACK_PERIODS:i]
            vol = realized_vol(window)
            if vol is None or vol == 0:
                scale = 1.0
            else:
                scale = target_vol / vol
                scale = max(min_cap, min(1.0, scale))  # 레버리지 불가하니 상한 1.0으로 클립
        idle = 1.0 - scale
        combined_net = nets[i] * scale + idle * rp_period_rate
        scaled.append((dates[i], combined_net, scale))
    return scaled


def split_in_out(series, split_date):
    in_sample = [t for t in series if t[0] < split_date]
    out_sample = [t for t in series if t[0] >= split_date]
    return in_sample, out_sample


def max_drawdown(series_with_dates):
    equity, peak, max_dd = 1.0, 1.0, 0.0
    for d, n, *_ in series_with_dates:
        equity *= (1.0 + n)
        peak = max(peak, equity)
        max_dd = min(max_dd, (equity - peak) / peak)
    return max_dd


def sharpe(returns):
    if len(returns) < 2:
        return 0.0
    mean = statistics.mean(returns)
    std = statistics.pstdev(returns)
    return mean / std if std > 0 else 0.0


base_series_by_period = []
all_base_vols = []
for i, period in enumerate(PERIODS):
    m_json = CACHE[f"momentum_{i}"]
    r_json = CACHE[f"reversal_{i}"]
    series = build_blended_series(m_json, r_json)
    base_series_by_period.append(series)
    nets = [n for _, n in series]
    for j in range(VOL_LOOKBACK_PERIODS, len(nets)):
        v = realized_vol(nets[j - VOL_LOOKBACK_PERIODS:j])
        if v:
            all_base_vols.append(v)

avg_hist_vol = statistics.mean(all_base_vols)
target_vol = avg_hist_vol * TARGET_MULT
rp_period_rate = RP_ANNUAL_RATE * (REBALANCE_DAYS / 365)

# baseline
base_all_oos = []
base_period_nets = []
base_worst_mdd = 0.0
for i, period in enumerate(PERIODS):
    out = [(d, n) for d, n in base_series_by_period[i] if d >= period["split"]]
    base_all_oos.extend([n for _, n in out])
    base_period_nets.append(compound([n for _, n in out]))
    equity, peak, max_dd = 1.0, 1.0, 0.0
    for d, n in out:
        equity *= (1.0 + n)
        peak = max(peak, equity)
        max_dd = min(max_dd, (equity - peak) / peak)
    base_worst_mdd = min(base_worst_mdd, max_dd)

base_avg_net = statistics.mean(base_period_nets)
base_sr = sharpe(base_all_oos)
print(f"=== Baseline (스케일링 없음) === avg_net={base_avg_net:.1%}  sharpe={base_sr:.4f}  worst_mdd={base_worst_mdd:.1%}\n")

# vol targeting + idle cash in RP (레버리지 없음, cap<=1.0)
all_oos = []
period_nets = []
worst_mdd = 0.0
min_scale_seen = 1.0
for i, period in enumerate(PERIODS):
    scaled = apply_vol_targeting_with_rp(base_series_by_period[i], target_vol, MIN_CAP, MAX_CAP, rp_period_rate)
    out = [t for t in scaled if t[0] >= period["split"]]
    all_oos.extend([n for _, n, _ in out])
    period_nets.append(compound([n for _, n, _ in out]))
    worst_mdd = min(worst_mdd, max_drawdown(out))
    min_scale_seen = min(min_scale_seen, min((s for _, _, s in out), default=1.0))

avg_net = statistics.mean(period_nets)
sr = sharpe(all_oos)
print(f"=== Vol Targeting + 유휴현금 RP운용 (target_mult={TARGET_MULT}, RP연 {RP_ANNUAL_RATE:.2%}) ===")
print(f"avg_net={avg_net:.1%}  sharpe={sr:.4f}  worst_mdd={worst_mdd:.1%}  (min_scale={min_scale_seen:.2f})\n")

print("=== 구간별 비교 ===")
print(f"{'구간':<12}{'baseline':>10}{'RP운용':>10}")
for i, period in enumerate(PERIODS):
    label = f"{period['from'][:4]}~{period['to'][:4]}"
    scaled = apply_vol_targeting_with_rp(base_series_by_period[i], target_vol, MIN_CAP, MAX_CAP, rp_period_rate)
    out = [t for t in scaled if t[0] >= period["split"]]
    rp_net = compound([n for _, n, _ in out])
    print(f"{label:<12}{base_period_nets[i]:>9.1%} {rp_net:>9.1%}")

if avg_net > base_avg_net and sr > base_sr:
    print("\n-> 수익 AND Sharpe 둘 다 baseline보다 개선됨 (레버리지 없이)")
elif sr > base_sr:
    print("\n-> Sharpe는 개선, 수익은 baseline보다 낮음")
else:
    print("\n-> 개선 없음")
