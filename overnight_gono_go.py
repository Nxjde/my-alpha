"""overnight_high (갭업 매수) 단독 5구간 Go/No-Go 검증.
overnight_low는 파일럿에서 gross부터 마이너스라 이미 탈락 -- 여기선 안 돌림."""

import subprocess, json, random

PERIODS = [
    {"from": "2015-01-01", "to": "2017-12-31", "split": "2016-07-01"},
    {"from": "2017-01-01", "to": "2019-12-31", "split": "2018-07-01"},
    {"from": "2019-01-01", "to": "2021-12-31", "split": "2020-07-01"},
    {"from": "2021-01-01", "to": "2023-12-31", "split": "2022-07-01"},
    {"from": "2023-01-01", "to": "2025-12-31", "split": "2024-07-01"},
]

ALPHA_ID, REBALANCE = "alpha_overnight_high", "1d"
N_PERMUTATIONS, P_THRESHOLD, MIN_FOLDS_POSITIVE, MIN_PERIODS = 2000, 0.05, 4, 20
CACHE_FILE = "overnight_high_cache.json"


def load_cache():
    try:
        return json.load(open(CACHE_FILE))
    except FileNotFoundError:
        return {}


def save_cache(cache):
    json.dump(cache, open(CACHE_FILE, "w"))


def run_solo(period):
    print(f"  running {ALPHA_ID}: {period['from']}~{period['to']}", flush=True)
    cmd = ["qanat", "backtest", "--from", period["from"], "--to", period["to"],
           "--alpha", ALPHA_ID, "--rebalance", REBALANCE,
           "--split", period["split"], "--json", "--quiet", "--force"]
    out = subprocess.run(cmd, capture_output=True, text=True)
    start = out.stdout.find("{")
    if start == -1:
        raise RuntimeError(f"JSON 못 찾음 -> {out.stdout[:300]} {out.stderr[:300]}")
    return json.loads(out.stdout[start:])


def compound(nets):
    eq = 1.0
    for n in nets:
        eq *= 1.0 + n
    return eq - 1.0


def perm_test(components, n_perm=N_PERMUTATIONS, seed=0):
    rng = random.Random(seed)
    actual = compound([c["gross"] - c["fees"] - c["slippage"] for c in components])
    hits = sum(1 for _ in range(n_perm) if compound(
        [(c["gross"] if rng.random() < 0.5 else -c["gross"]) - c["fees"] - c["slippage"]
         for c in components]) >= actual)
    return actual, hits / n_perm


def main():
    cache = load_cache()
    for i, period in enumerate(PERIODS):
        key = f"{ALPHA_ID}_{i}"
        if key in cache:
            print(f"  구간 {i+1}/5: 캐시 사용", flush=True)
            continue
        cache[key] = run_solo(period)
        save_cache(cache)

    print("\n" + "=" * 70, flush=True)
    print("overnight_high Go/No-Go 결과", flush=True)
    print("=" * 70, flush=True)

    results = []
    for i, period in enumerate(PERIODS):
        key = f"{ALPHA_ID}_{i}"
        split = period["split"]
        comps = [{"gross": p["gross"], "fees": p["fees"], "slippage": p["slippage"]}
                 for p in cache[key]["periods"] if p["as_of"] >= split]
        n = len(comps)
        if n < MIN_PERIODS:
            print(f"  {period['from']}~{period['to']}: n={n} 표본 부족 SKIP", flush=True)
            results.append({"net": 0, "p": 1.0, "passed": False})
            continue
        net, p = perm_test(comps)
        passed = net > 0 and p < P_THRESHOLD
        results.append({"net": net, "p": p, "passed": passed})
        flag = "PASS" if passed else ("유의성 부족" if net > 0 else "FAIL")
        print(f"  {period['from']}~{period['to']}: n={n}, net={net:+.4f}, p={p:.4f} -> {flag}", flush=True)

    n_pos = sum(1 for r in results if r["net"] > 0)
    n_sig = sum(1 for r in results if r["p"] < P_THRESHOLD)
    n_pass = sum(1 for r in results if r["passed"])
    verdict = "GO" if n_pass >= MIN_FOLDS_POSITIVE else "NO-GO"
    avg_net = sum(r["net"] for r in results) / len(results)
    print(f"\n요약: {n_pos}/5 positive, {n_sig}/5 p<0.05, {n_pass}/5 full-pass, "
          f"평균 net={avg_net:+.4f} -> 판정: {verdict}", flush=True)


if __name__ == "__main__":
    main()
