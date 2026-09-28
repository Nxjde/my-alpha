"""
vol_target_with_lowvol.py

target_mult=0.7 vol targeting에서 scale<1일 때 남는 유휴 비중을
RP(무위험) 대신 low_vol 알파에 배분. 레버리지는 여전히 안 씀(cap<=1.0).
momentum+reversal, low_vol 모두 momentum/reversal 날짜 교집합으로 정렬.
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
MIN_CAP = 0.5

with open("solo_cache.json") as f:
    CACHE = json.load(f)


def compound(net_list):
    equity = 1.0
    for n in net_list:
        equity *= 1.0 + n
    return equity - 1.0


def build_blended_series_3way(m_json, r_json, lv_json):
    """momentum/reversal 1:1 합산 시계열 + low_vol 시계열을, 공통 날짜에 맞춰 반환."""
    by_date_m = {p["as_of"]: p["net"] for p in m_json["periods"]}
    by_date_r = {p["as_of"]: p["net"] for p in r_json["periods"]}
    by_date_lv = {p["as_of"]: p["net"] for p in lv_json["periods"]}
    dates = sorted(set(by_date_m) & set(by_date_r) & set(by_date_lv))
    base = [(d, 0.5 * by_date_m[d] + 0.5 * by_date_r[d]) for d in dates]
    lowvol = [(d, by_date_lv[d]) for d in dates]
    return base, lowvol


def realized_vol(window):
    if len(window) < 2:
        return None
    return statistics.pstdev(window)


def apply_vol_targeting_with_lowvol(base_series, lowvol_series, target_vol, min_cap):
    """scale은 [min_cap, 1.0]로 클립. (1-scale) 비중은 low_vol 그 기간 수익으로 채움."""
    dates = [d for d, _ in base_series]
    base_nets = [n for _, n in base_series]
    lv_nets = [n for _, n in lowvol_series]
    scaled = []
    for i in range(len(base_nets)):
        if i < VOL_LOOKBACK_PERIODS:
            scale = 1.0
        else:
            window = base_nets[i - VOL_LOOKBACK_PERIODS:i]
            vol = realized_vol(window)
            if vol is None or vol == 0:
                scale = 1.0
            else:
                scale = target_vol / vol
                scale = max(min_cap, min(1.0, scale))
        idle = 1.0 - scale
        combined_net = base_nets[i] * scale + idle * lv_nets[i]
        scaled.append((dates[i], combined_net, scale))
    return scaled


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
lowvol_series_by_period = []
all_base_vols = []
for i, period in enumerate(PERIODS):
    m_json = CACHE[f"momentum_{i}"]
    r_json = CACHE[f"reversal_{i}"]
    lv_json = CACHE[f"low_vol_{i}"]
    base, lowvol = build_blended_series_3way(m_json, r_json, lv_json)
    base_series_by_period.append(base)
    lowvol_series_by_period.append(lowvol)
    nets = [n for _, n in base]
    for j in range(VOL_LOOKBACK_PERIODS, len(nets)):
        v = realized_vol(nets[j - VOL_LOOKBACK_PERIODS:j])
        if v:
            all_base_vols.append(v)

avg_hist_vol = statistics.mean(all_base_vols)
target_vol = avg_hist_vol * TARGET_MULT

# baseline (momentum+reversal 1:1, 스케일링 없음) -- 날짜는 3-way 교집합 기준으로 재계산 (공정 비교)
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
print(f"=== Baseline (momentum+reversal 1:1, 스케일링 없음) ===")
print(f"avg_net={base_avg_net:.1%}  sharpe={base_sr:.4f}  worst_mdd={base_worst_mdd:.1%}\n")

# vol targeting + 유휴자금 low_vol 배분
all_oos = []
period_nets = []
worst_mdd = 0.0
for i, period in enumerate(PERIODS):
    scaled = apply_vol_targeting_with_lowvol(
        base_series_by_period[i], lowvol_series_by_period[i], target_vol, MIN_CAP
    )
    out = [t for t in scaled if t[0] >= period["split"]]
    all_oos.extend([n for _, n, _ in out])
    period_nets.append(compound([n for _, n, _ in out]))
    worst_mdd = min(worst_mdd, max_drawdown(out))

avg_net = statistics.mean(period_nets)
sr = sharpe(all_oos)
print(f"=== Vol Targeting + 유휴자금 low_vol 배분 (target_mult={TARGET_MULT}) ===")
print(f"avg_net={avg_net:.1%}  sharpe={sr:.4f}  worst_mdd={worst_mdd:.1%}\n")

print("=== 구간별 비교 ===")
print(f"{'구간':<12}{'baseline':>10}{'lowvol배분':>12}")
for i, period in enumerate(PERIODS):
    label = f"{period['from'][:4]}~{period['to'][:4]}"
    scaled = apply_vol_targeting_with_lowvol(
        base_series_by_period[i], lowvol_series_by_period[i], target_vol, MIN_CAP
    )
    out = [t for t in scaled if t[0] >= period["split"]]
    lv_net = compound([n for _, n, _ in out])
    print(f"{label:<12}{base_period_nets[i]:>9.1%} {lv_net:>11.1%}")

if avg_net > base_avg_net and sr > base_sr:
    print("\n-> 수익 AND Sharpe 둘 다 baseline보다 개선됨 (레버리지 없이)")
elif sr > base_sr:
    print("\n-> Sharpe는 개선, 수익은 baseline보다 낮음")
elif avg_net > base_avg_net:
    print("\n-> 수익은 개선, Sharpe는 baseline보다 낮음")
else:
    print("\n-> 개선 없음")
