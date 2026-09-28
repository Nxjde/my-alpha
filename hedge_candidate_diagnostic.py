import json, statistics

PERIODS = [
    {"from": "2015-01-01", "to": "2017-12-31", "split": "2016-07-01"},
    {"from": "2017-01-01", "to": "2019-12-31", "split": "2018-07-01"},
    {"from": "2019-01-01", "to": "2021-12-31", "split": "2020-07-01"},
    {"from": "2021-01-01", "to": "2023-12-31", "split": "2022-07-01"},
    {"from": "2023-01-01", "to": "2025-12-31", "split": "2024-07-01"},
]

with open("solo_cache.json") as f:
    MAIN_CACHE = json.load(f)

CANDIDATES = {
    "low_vol": None,  # 이미 확인함, 참고용
}

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

def try_load_cache(fname):
    try:
        with open(fname) as f:
            return json.load(f)
    except FileNotFoundError:
        return None

candidate_files = {
    "overnight_high": ("overnight_high_cache.json", "alpha_overnight_high_"),
    "reversal_short": ("reversal_short_cache.json", "alpha_reversal_short_"),
}

for name, (fname, prefix) in candidate_files.items():
    cache = try_load_cache(fname)
    if cache is None:
        print(f"{name}: {fname} 없음, 스킵")
        continue
    print(f"\n=== {name} vs momentum+reversal ===")
    print(f"{'구간':<12}{name+' OOS':>14}{'m+r OOS':>10}{'상관계수':>10}")
    for i, period in enumerate(PERIODS):
        m_json = MAIN_CACHE[f"momentum_{i}"]
        r_json = MAIN_CACHE[f"reversal_{i}"]
        # 캐시 안 key 이름이 스크립트마다 다를 수 있어 몇 가지 시도
        cand_json = cache.get(f"{prefix}{i}") or cache.get(f"alpha_overnight_high_{i}") or cache.get(str(i)) or cache.get(f"{name}_{i}")
        if cand_json is None:
            print(f"{period['from'][:4]}~{period['to'][:4]}: 캐시 키 못 찾음 (키 목록: {list(cache.keys())[:5]})")
            continue
        by_date_m = {p["as_of"]: p["net"] for p in m_json["periods"]}
        by_date_r = {p["as_of"]: p["net"] for p in r_json["periods"]}
        by_date_c = {p["as_of"]: p["net"] for p in cand_json["periods"]}
        dates = sorted(set(by_date_m) & set(by_date_r) & set(by_date_c))
        dates_oos = [d for d in dates if d >= period["split"]]
        if len(dates_oos) < 5:
            continue
        base_oos = [0.5*by_date_m[d]+0.5*by_date_r[d] for d in dates_oos]
        c_oos = [by_date_c[d] for d in dates_oos]
        label = f"{period['from'][:4]}~{period['to'][:4]}"
        print(f"{label:<12}{compound(c_oos):>13.1%} {compound(base_oos):>9.1%} {correlation(base_oos, c_oos):>10.3f}")
