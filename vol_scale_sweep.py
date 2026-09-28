"""
vol_scale_sweep.py

solo_cache.json에서 momentum/reversal 5구간 solo 결과를 로드해서,
1:1 합산 시계열에 포트폴리오 레벨 변동성 스케일링을 얹고,
SCALE_DOWN_FACTOR(축소 정도)와 VOL_PCTL_THRESHOLD(축소 발동 기준)를 스윕한다.
numpy 없이 순수 표준 라이브러리만 사용.
"""

import json
import statistics
import random

PERIODS = [
    {"from": "2015-01-01", "to": "2017-12-31", "split": "2016-07-01"},
    {"from": "2017-01-01", "to": "2019-12-31", "split": "2018-07-01"},
    {"from": "2019-01-01", "to": "2021-12-31", "split": "2020-07-01"},
    {"from": "2021-01-01", "to": "2023-12-31", "split": "2022-07-01"},
    {"from": "2023-01-01", "to": "2025-12-31", "split": "2024-07-01"},
]

VOL_LOOKBACK_PERIODS = 12
VOL_PCTL_LOOKBACK = 26
N_PERMUTATIONS = 2000

SCALE_DOWN_FACTORS = [0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]
VOL_PCTL_THRESHOLDS = [0.70, 0.80, 0.90]

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
        return 0.0
    return statistics.pstdev(window)


def apply_vol_scaling(series, threshold, scale_down):
    dates = [d for d, _ in series]
    nets = [n for _, n in series]
    scaled = []
    for i in range(len(nets)):
        if i < VOL_LOOKBACK_PERIODS + 1:
            scale = 1.0
        else:
            window = nets[max(0, i - VOL_LOOKBACK_PERIODS - VOL_PCTL_LOOKBACK):i]
            vol_series = []
            for j in range(VOL_LOOKBACK_PERIODS, len(window) + 1):
                vol_series.append(realized_vol(window[max(0, j - VOL_LOOKBACK_PERIODS):j]))
            if len(vol_series) < 2:
                scale = 1.0
            else:
                current_vol = vol_series[-1]
                pctl = sum(1 for v in vol_series if v < current_vol) / len(vol_series)
                scale = scale_down if pctl > threshold else 1.0
        scaled.append((dates[i], nets[i] * scale))
    return scaled


def split_in_out(series, split_date):
    in_sample = [n for d, n in series if d < split_date]
    out_sample = [n for d, n in series if d >= split_date]
    return in_sample, out_sample


def sharpe(returns):
    if len(returns) < 2:
        return 0.0
    mean = statistics.mean(returns)
    std = statistics.pstdev(returns)
    return mean / std if std > 0 else 0.0


def permutation_p_value(out_sample_net, n_perm=N_PERMUTATIONS):
    if len(out_sample_net) < 5:
        return float("nan")
    actual = compound(out_sample_net)
    rng = random.Random(42)
    count_ge = 0
    for _ in range(n_perm):
        flipped = [n * rng.choice([-1, 1]) for n in out_sample_net]
        if compound(flipped) >= actual:
            count_ge += 1
    return (count_ge + 1) / (n_perm + 1)


base_series_by_period = []
for i, period in enumerate(PERIODS):
    m_json = CACHE[f"momentum_{i}"]
    r_json = CACHE[f"reversal_{i}"]
    base_series_by_period.append(build_blended_series(m_json, r_json))

print("=== Baseline (스케일링 없음, 1:1) ===")
base_all_oos = []
for i, period in enumerate(PERIODS):
    _, out = split_in_out(base_series_by_period[i], period["split"])
    base_all_oos.extend(out)
    label = f"{period['from'][:4]}~{period['to'][:4]}"
    print(f"  {label}: net {compound(out):>8.1%}  n={len(out)}")
print(f"  전체 OOS Sharpe: {sharpe(base_all_oos):.4f}  (n={len(base_all_oos)})\n")

print(f"{'threshold':>10} {'scale_down':>11} {'worst_period_net':>17} {'avg_oos_net':>13} {'oos_sharpe':>11} {'p_value':>9}")
results = []
for threshold in VOL_PCTL_THRESHOLDS:
    for scale_down in SCALE_DOWN_FACTORS:
        all_oos = []
        period_nets = []
        for i, period in enumerate(PERIODS):
            scaled = apply_vol_scaling(base_series_by_period[i], threshold, scale_down)
            _, out = split_in_out(scaled, period["split"])
            all_oos.extend(out)
            period_nets.append(compound(out))
        worst = min(period_nets)
        avg_net = statistics.mean(period_nets)
        sr = sharpe(all_oos)
        p = permutation_p_value(all_oos, n_perm=500)
        results.append((threshold, scale_down, worst, avg_net, sr, p))
        print(f"{threshold:>10.2f} {scale_down:>11.2f} {worst:>17.1%} {avg_net:>13.1%} {sr:>11.4f} {p:>9.3f}")

print("\n=== Baseline 대비 개선 여부 ===")
base_worst = min(compound(split_in_out(base_series_by_period[i], PERIODS[i]["split"])[1]) for i in range(len(PERIODS)))
base_sr = sharpe(base_all_oos)
print(f"Baseline: worst_period={base_worst:.1%}, sharpe={base_sr:.4f}")

best_worst = max(results, key=lambda r: r[2])
best_sharpe = max(results, key=lambda r: r[4])
print(f"Worst-period 최선: threshold={best_worst[0]}, scale_down={best_worst[1]} -> worst={best_worst[2]:.1%}, sharpe={best_worst[4]:.4f}")
print(f"Sharpe 최선: threshold={best_sharpe[0]}, scale_down={best_sharpe[1]} -> worst={best_sharpe[2]:.1%}, sharpe={best_sharpe[4]:.4f}")
