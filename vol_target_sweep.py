"""
vol_target_sweep.py

이진(threshold) 방식 대신 연속적인 vol targeting 방식으로 스케일링.
scale = target_vol / current_realized_vol, [min_cap, max_cap]으로 제한.
평온한 구간엔 레버리지업(scale>1), 위기 구간엔 축소(scale<1) — 대칭적 조정.
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


def apply_vol_targeting(series, target_vol, min_cap, max_cap):
    """look-ahead 방지: t 시점 스케일은 t 이전 VOL_LOOKBACK_PERIODS만으로 계산."""
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
                scale = max(min_cap, min(max_cap, scale))
        scaled.append((dates[i], nets[i] * scale))
    return scaled


def split_in_out(series, split_date):
    in_sample = [(d, n) for d, n in series if d < split_date]
    out_sample = [(d, n) for d, n in series if d >= split_date]
    return in_sample, out_sample


def max_drawdown(series_with_dates):
    equity, peak, max_dd = 1.0, 1.0, 0.0
    for d, n in series_with_dates:
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
print(f"참고: 전체 기간 평균 실현 변동성(12기간 lookback) = {avg_hist_vol:.5f}\n")

# baseline
base_all_oos = []
base_worst_mdd = 0.0
base_period_nets = []
for i, period in enumerate(PERIODS):
    _, out = split_in_out(base_series_by_period[i], period["split"])
    base_all_oos.extend([n for _, n in out])
    base_period_nets.append(compound([n for _, n in out]))
    base_worst_mdd = min(base_worst_mdd, max_drawdown(out))

print("=== Baseline ===")
print(f"전체 OOS net(평균): {statistics.mean(base_period_nets):.1%}, Sharpe: {sharpe(base_all_oos):.4f}, worst MDD: {base_worst_mdd:.1%}\n")

# target_vol을 평균 실현변동성의 배수로 스윕, cap 범위도 스윕
TARGET_MULTIPLIERS = [0.7, 0.8, 0.9, 1.0, 1.1, 1.2, 1.3]
CAP_RANGES = [(0.5, 1.5), (0.5, 2.0), (0.3, 2.0)]

print(f"{'target_mult':>11} {'cap':>12} {'avg_oos_net':>13} {'oos_sharpe':>11} {'worst_mdd':>10}")
results = []
for mult in TARGET_MULTIPLIERS:
    target_vol = avg_hist_vol * mult
    for min_cap, max_cap in CAP_RANGES:
        all_oos = []
        period_nets = []
        worst_mdd = 0.0
        for i, period in enumerate(PERIODS):
            scaled = apply_vol_targeting(base_series_by_period[i], target_vol, min_cap, max_cap)
            _, out = split_in_out(scaled, period["split"])
            all_oos.extend([n for _, n in out])
            period_nets.append(compound([n for _, n in out]))
            worst_mdd = min(worst_mdd, max_drawdown(out))
        avg_net = statistics.mean(period_nets)
        sr = sharpe(all_oos)
        cap_label = f"[{min_cap},{max_cap}]"
        results.append((mult, cap_label, avg_net, sr, worst_mdd))
        print(f"{mult:>11.2f} {cap_label:>12} {avg_net:>13.1%} {sr:>11.4f} {worst_mdd:>10.1%}")

print("\n=== Baseline 대비 개선된 조합 (수익 AND Sharpe 둘 다 baseline보다 좋은 경우) ===")
base_avg_net = statistics.mean(base_period_nets)
base_sr = sharpe(base_all_oos)
improved = [r for r in results if r[2] > base_avg_net and r[3] > base_sr]
if improved:
    for r in sorted(improved, key=lambda x: -x[3]):
        print(f"  target_mult={r[0]}, cap={r[1]} -> avg_net={r[2]:.1%}, sharpe={r[3]:.4f}, worst_mdd={r[4]:.1%}")
else:
    print("  없음 (수익과 Sharpe를 동시에 개선하는 조합 없음)")
