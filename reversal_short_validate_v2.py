import subprocess, json, random

PERIODS = [
    {"from": "2015-01-01", "to": "2017-12-31", "split": "2016-07-01"},
    {"from": "2017-01-01", "to": "2019-12-31", "split": "2018-07-01"},
    {"from": "2019-01-01", "to": "2021-12-31", "split": "2020-07-01"},
    {"from": "2021-01-01", "to": "2023-12-31", "split": "2022-07-01"},
    {"from": "2023-01-01", "to": "2025-12-31", "split": "2024-07-01"},
]
N_PERMUTATIONS, P_THRESHOLD, MIN_FOLDS_POSITIVE, MIN_PERIODS = 2000, 0.05, 4, 20
CACHE_FILE = "reversal_short_cache.json"

def load_cache():
    try:
        return json.load(open(CACHE_FILE))
    except FileNotFoundError:
        return {}

def save_cache(cache):
    json.dump(cache, open(CACHE_FILE, "w"))

def run_solo(period, idx):
    print(f"\n구간 {idx+1}/5: {period['from']} ~ {period['to']}")
    cmd = ["qanat","backtest","--from",period["from"],"--to",period["to"],
           "--alpha","alpha_reversal_short","--split",period["split"],"--json","--force"]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    lines = []
    for line in proc.stdout:
        lines.append(line)
        s = line.strip()
        if s and not s.startswith(("{","}", '"', "[")):
            print(f"  {s}")
    proc.wait()
    full = "".join(lines)
    start = full.find("{")
    if start == -1:
        raise RuntimeError(f"JSON 못 찾음: {full[:200]}")
    return json.loads(full[start:])

def compound(nets):
    eq = 1.0
    for n in nets: eq *= 1.0 + n
    return eq - 1.0

def perm_test(components, n_perm=N_PERMUTATIONS, seed=0):
    rng = random.Random(seed)
    actual = compound([c["gross"]-c["fees"]-c["slippage"] for c in components])
    hits = sum(1 for _ in range(n_perm) if compound(
        [(c["gross"] if rng.random()<0.5 else -c["gross"])-c["fees"]-c["slippage"]
         for c in components]) >= actual)
    return actual, hits/n_perm

def main():
    cache = load_cache()
    for i, period in enumerate(PERIODS):
        if str(i) in cache:
            print(f"구간 {i+1}/5: 캐시 사용")
            continue
        cache[str(i)] = run_solo(period, i)
        save_cache(cache)
        print(f"  -> 구간 {i+1}/5 저장 완료")

    print("\n\n== Go/No-Go 검증 결과 ==")
    try:
        old = json.load(open("solo_cache.json"))
        print("\n[참고] reversal(lookback=5) out-of-sample:")
        for i,p in enumerate(PERIODS):
            print(f"  {p['from']}~{p['to']}: {old[f'reversal_{i}']['segments']['out_of_sample']['net']:+.4f}")
    except: pass

    print("\n[신규] reversal_short(lookback=1):")
    results = []
    for i, period in enumerate(PERIODS):
        split = period["split"]
        comps = [{"gross":p["gross"],"fees":p["fees"],"slippage":p["slippage"]}
                 for p in cache[str(i)]["periods"] if p["as_of"] >= split]
        n = len(comps)
        if n < MIN_PERIODS:
            print(f"  {period['from']}~{period['to']}: n={n} 표본 부족 SKIP")
            results.append({"net":0,"p":1.0,"passed":False})
            continue
        net, p = perm_test(comps)
        passed = net > 0 and p < P_THRESHOLD
        results.append({"net":net,"p":p,"passed":passed})
        flag = "PASS ✓" if passed else ("유의성 부족" if net>0 else "FAIL ✗")
        print(f"  {period['from']}~{period['to']}: n={n}, net={net:+.4f}, p={p:.4f} -> {flag}")
        outs = [p2 for p2 in cache[str(i)]["periods"] if p2["as_of"] >= split]
        if outs:
            lat = outs[-1]
            print(f"    최근({lat['as_of']}): holdings={lat['holdings']}개, net={lat['net']:+.4f}")

    n_pass = sum(1 for r in results if r["passed"])
    print(f"\n요약: {sum(1 for r in results if r['net']>0)}/5 positive, "
          f"{sum(1 for r in results if r['p']<P_THRESHOLD)}/5 p<0.05, {n_pass}/5 passed")
    print("판정:", "GO ✓" if n_pass >= MIN_FOLDS_POSITIVE else "NO-GO ✗ — 비용을 못 이김")

if __name__ == "__main__":
    main()
