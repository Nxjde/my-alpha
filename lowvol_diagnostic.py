import json, statistics

PERIODS = [
    {"from": "2015-01-01", "to": "2017-12-31", "split": "2016-07-01"},
    {"from": "2017-01-01", "to": "2019-12-31", "split": "2018-07-01"},
    {"from": "2019-01-01", "to": "2021-12-31", "split": "2020-07-01"},
    {"from": "2021-01-01", "to": "2023-12-31", "split": "2022-07-01"},
    {"from": "2023-01-01", "to": "2025-12-31", "split": "2024-07-01"},
]

with open("solo_cache.json") as f:
    CACHE = json.load(f)

def compound(nets):
    e = 1.0
    for n in nets:
        e *= (1.0 + n)
    return e - 1.0

def correlation(a, b):
    n = len(a)
    ma, mb = statistics.mean(a), statistics.mean(b)
    cov = sum((a[i]-ma)*(b[i]-mb) for i in range(n)) / n
    sa, sb = statistics.pstdev(a), statistics.pstdev(b)
    return cov / (sa*sb) if sa>0 and sb>0 else 0.0

print(f"{'구간':<12}{'low_vol OOS':>13}{'momentum+reversal OOS':>24}{'상관계수':>10}")
for i, period in enumerate(PERIODS):
    m_json = CACHE[f"momentum_{i}"]
    r_json = CACHE[f"reversal_{i}"]
    lv_json = CACHE[f"low_vol_{i}"]
    by_date_m = {p["as_of"]: p["net"] for p in m_json["periods"]}
    by_date_r = {p["as_of"]: p["net"] for p in r_json["periods"]}
    by_date_lv = {p["as_of"]: p["net"] for p in lv_json["periods"]}
    dates = sorted(set(by_date_m) & set(by_date_r) & set(by_date_lv) )
    dates_oos = [d for d in dates if d >= period["split"]]
    base_oos = [0.5*by_date_m[d]+0.5*by_date_r[d] for d in dates_oos]
    lv_oos = [by_date_lv[d] for d in dates_oos]
    label = f"{period['from'][:4]}~{period['to'][:4]}"
    print(f"{label:<12}{compound(lv_oos):>12.1%} {compound(base_oos):>23.1%} {correlation(base_oos, lv_oos):>10.3f}")
