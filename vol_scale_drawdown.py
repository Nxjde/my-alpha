"""
vol_scale_drawdown.py

baseline(스케일링 없음) vs vol scaling 적용 시, 구간별 equity curve의
max drawdown을 비교한다. 구간 내 일시적 낙폭(PCG 파산, 크리스마스 급락 등)이
momentum+reversal 1:1 조합에서 어느 정도 남아있는지, 스케일링이 그걸 줄이는지 확인.
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
VOL_PCTL_LOOKBACK = 26

# max drawdown 비교용 대표 조합 (스윕 결과에서 중간값)
TEST_THRESHOLD = 0.80
TEST_SCALE_DOWN = 0.5

with open("solo_cache.json") as f:
    CACHE = json.load(f)


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
    in_sample = [(d, n) for d, n in series if d < split_date]
    out_sample = [(d, n) for d, n in series if d >= split_date]
    return in_sample, out_sample


def max_drawdown(series_with_dates):
    """series_with_dates: [(date, net), ...] -> (max_dd, peak_date, trough_date)"""
    equity = 1.0
    peak = 1.0
    peak_date = series_with_dates[0][0] if series_with_dates else None
    max_dd = 0.0
    max_dd_peak_date = peak_date
    max_dd_trough_date = peak_date
    for d, n in series_with_dates:
        equity *= (1.0 + n)
        if equity > peak:
            peak = equity
            peak_date = d
        dd = (equity - peak) / peak
        if dd < max_dd:
            max_dd = dd
            max_dd_peak_date = peak_date
            max_dd_trough_date = d
    return max_dd, max_dd_peak_date, max_dd_trough_date


base_series_by_period = []
for i, period in enumerate(PERIODS):
    m_json = CACHE[f"momentum_{i}"]
    r_json = CACHE[f"reversal_{i}"]
    base_series_by_period.append(build_blended_series(m_json, r_json))

print(f"=== Max Drawdown 비교 (threshold={TEST_THRESHOLD}, scale_down={TEST_SCALE_DOWN}) ===\n")
print(f"{'구간':<12}{'baseline MDD':>14}{'MDD 시점(peak→trough)':>28}{'scaled MDD':>13}{'MDD 시점':>26}")

for i, period in enumerate(PERIODS):
    label = f"{period['from'][:4]}~{period['to'][:4]}"

    _, base_out = split_in_out(base_series_by_period[i], period["split"])
    base_mdd, base_peak, base_trough = max_drawdown(base_out)

    scaled_series = apply_vol_scaling(base_series_by_period[i], TEST_THRESHOLD, TEST_SCALE_DOWN)
    _, scaled_out = split_in_out(scaled_series, period["split"])
    scaled_mdd, scaled_peak, scaled_trough = max_drawdown(scaled_out)

    base_range = f"{base_peak[:10]}→{base_trough[:10]}" if base_peak else "N/A"
    scaled_range = f"{scaled_peak[:10]}→{scaled_trough[:10]}" if scaled_peak else "N/A"

    print(f"{label:<12}{base_mdd:>13.1%} {base_range:>27}{scaled_mdd:>13.1%} {scaled_range:>26}")

print("\n(참고: 여기서의 MDD는 out-of-sample 구간 내에서의 낙폭만 계산됨)")
