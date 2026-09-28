"""
vol_target_leverage_sweep.py

vol targeting(target_mult=0.7, cap=[0.5,2.0])으로 낮춘 MDD 위에,
고정 레버리지를 얹어서 baseline과 같은 MDD 수준에서 수익이 얼마나 개선되는지 확인.
동시에 순간 최대 총 배율(청산 리스크 지표)도 같이 추적.
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
MIN_CAP, MAX_CAP = 0.5, 2.0

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


def apply_vol_targeting_with_leverage(series, target_vol, min_cap, max_cap, fixed_leverage):
    """vol targeting scale에 고정 레버리지를 곱한 총 배율을 적용.
    반환: [(date, net, total_scale), ...] -- total_scale은 순간 배율 추적용"""
    dates = [d for d, _ in series]
    nets = [n for _, n in series]
    scaled = []
    for i in range(len(nets)):
        if i < VOL_LOOKBACK_PERIODS:
            vt_scale = 1.0
        else:
            window = nets[i - VOL_LOOKBACK_PERIODS:i]
            vol = realized_vol(window)
            if vol is None or vol == 0:
                vt_scale = 1.0
            else:
                vt_scale = target_vol / vol
                vt_scale = max(min_cap, min(max_cap, vt_scale))
        total_scale = vt_scale * fixed_leverage
        scaled.append((dates[i], nets[i] * total_scale, total_scale))
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

# baseline
base_all_oos = []
base_period_nets = []
base_worst_mdd = 0.0
for i, period in enumerate(PERIODS):
    _, out = split_in_out([(d, n) for d, n in base_series_by_period[i]], period["split"])
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
print(f"=== Baseline === avg_net={base_avg_net:.1%}  sharpe={base_sr:.4f}  worst_mdd={base_worst_mdd:.1%}\n")

# 고정 레버리지 스윕
FIXED_LEVERAGES = [1.0, 1.2, 1.4, 1.5, 1.6, 1.8, 2.0]

print(f"{'fixed_lev':>9} {'avg_net':>9} {'sharpe':>8} {'worst_mdd':>10} {'max_instant_scale':>18}")
for lev in FIXED_LEVERAGES:
    all_oos = []
    period_nets = []
    worst_mdd = 0.0
    max_instant_scale = 0.0
    for i, period in enumerate(PERIODS):
        scaled = apply_vol_targeting_with_leverage(base_series_by_period[i], target_vol, MIN_CAP, MAX_CAP, lev)
        _, out = split_in_out(scaled, period["split"])
        all_oos.extend([n for _, n, _ in out])
        period_nets.append(compound([n for _, n, _ in out]))
        max_instant_scale = max(max_instant_scale, max((s for _, _, s in out), default=0.0))
        worst_mdd = min(worst_mdd, max_drawdown(out))
    avg_net = statistics.mean(period_nets)
    sr = sharpe(all_oos)
    flag = ""
    if avg_net > base_avg_net and sr > base_sr and worst_mdd > base_worst_mdd:
        flag = "  <- 3개 지표 전부 개선!"
    elif avg_net > base_avg_net and sr > base_sr:
        flag = "  <- 수익+Sharpe 개선"
    print(f"{lev:>9.1f} {avg_net:>9.1%} {sr:>8.4f} {worst_mdd:>10.1%} {max_instant_scale:>18.2f}{flag}")

print(f"\n(target_vol={target_vol:.5f} = 평균실현변동성 x {TARGET_MULT}, vol-targeting cap=[{MIN_CAP},{MAX_CAP}])")
print("max_instant_scale: 어느 한 리밸런싱 시점에서든 실제로 걸렸던 최대 총 배율(vol-target scale x 고정레버리지)")
