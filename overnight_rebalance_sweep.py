"""overnight_high을 rebalance 2d/3d/4d/5d로 스윕 (1d는 overnight_gono_go.py에서 이미 처리).
끝나면 1d 결과(overnight_high_cache.json)까지 합쳐서 최종 비교표를 출력한다."""

import subprocess, json, random

PERIODS = [
    {"from": "2015-01-01", "to": "2017-12-31", "split": "2016-07-01"},
    {"from": "2017-01-01", "to": "2019-12-31", "split": "2018-07-01"},
    {"from": "2019-01-01", "to": "2021-12-31", "split": "2020-07-01"},
    {"from": "2021-01-01", "to": "2023-12-31", "split": "2022-07-01"},
    {"from": "2023-01-01", "to": "2025-12-31", "split": "2024-07-01"},
]

ALPHA_ID = "alpha_overnight_high"
REBALANCES = ["2d", "3d", "4d", "5d"]
N_PERMUTATIONS, P_THRESHOLD, MIN_FOLDS_POSITIVE, MIN_PERIODS = 2000, 0.05, 4, 20
CACHE_FILE = "overnight_rebalance_sweep_cache.json"
CACHE_1D_FILE = "overnight_high_cache.json"  # 이미 완료된 1d 결과


def load_json(path):
    try:
        return json.load(open(path))
    except FileNotFoundError:
        return {}


def save_cache(cache):
    json.dump(cache, open(CACHE_FILE, "w"))


def run_solo(rebalance, period):
    print(f"  running {ALPHA_ID} (rebalance={rebalance}): {period['from']}~{period['to']}", flush=True)
    cmd = ["qanat", "backtest", "--from", period["from"], "--to", period["to"],
           "--alpha", ALPHA_ID, "--rebalance", rebalance,
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


def evaluate(periods_data, split_lookup):
    results = []
    for i, split in enumerate(split_lookup):
        comps = [{"gross": p["gross"], "fees": p["fees"], "slippage": p["slippage"]}
                 for p in periods_data[i]["periods"] if p["as_of"] >= split]
        n = len(comps)
        if n < MIN_PERIODS:
            results.append({"net": 0, "p": 1.0, "passed": False, "n": n})
            continue
        net, p = perm_test(comps)
        passed = net > 0 and p < P_THRESHOLD
        results.append({"net": net, "p": p, "passed": passed, "n": n})
    return results


def main():
    cache = load_json(CACHE_FILE)

    for rebalance in REBALANCES:
        print(f"\n### rebalance={rebalance} ###", flush=True)
        for i, period in enumerate(PERIODS):
            key = f"{ALPHA_ID}_{rebalance}_{i}"
            if key in cache:
                print(f"  구간 {i+1}/5: 캐시 사용", flush=True)
                continue
            cache[key] = run_solo(rebalance, period)
            save_cache(cache)

    print("\n\n" + "=" * 70, flush=True)
    print("최종 비교표 (overnight_high, rebalance 1d~5d)", flush=True)
    print("=" * 70, flush=True)

    splits = [p["split"] for p in PERIODS]
    summary = []

    cache_1d = load_json(CACHE_1D_FILE)
    if all(f"{ALPHA_ID}_{i}" in cache_1d for i in range(5)):
        periods_data = [cache_1d[f"{ALPHA_ID}_{i}"] for i in range(5)]
        results = evaluate(periods_data, splits)
        n_pos = sum(1 for r in results if r["net"] > 0)
        n_sig = sum(1 for r in results if r["p"] < P_THRESHOLD)
        n_pass = sum(1 for r in results if r["passed"])
        avg_net = sum(r["net"] for r in results) / len(results)
        verdict = "GO" if n_pass >= MIN_FOLDS_POSITIVE else "NO-GO"
        summary.append(("1d", n_pos, n_sig, n_pass, avg_net, verdict))
    else:
        print("  (1d 결과 캐시가 아직 없음 -> overnight_gono_go.py 먼저 완료 필요)", flush=True)

    for rebalance in REBALANCES:
        periods_data = [cache[f"{ALPHA_ID}_{rebalance}_{i}"] for i in range(5)]
        results = evaluate(periods_data, splits)
        n_pos = sum(1 for r in results if r["net"] > 0)
        n_sig = sum(1 for r in results if r["p"] < P_THRESHOLD)
        n_pass = sum(1 for r in results if r["passed"])
        avg_net = sum(r["net"] for r in results) / len(results)
        verdict = "GO" if n_pass >= MIN_FOLDS_POSITIVE else "NO-GO"
        summary.append((rebalance, n_pos, n_sig, n_pass, avg_net, verdict))

    print(f"{'rebalance':<10} {'positive':<10} {'p<0.05':<8} {'pass':<6} {'avg net':<10} verdict", flush=True)
    for label, n_pos, n_sig, n_pass, avg_net, verdict in summary:
        print(f"{label:<10} {n_pos}/5{'':<6} {n_sig}/5{'':<4} {n_pass}/5{'':<2} {avg_net:+.4f}   {verdict}", flush=True)


if __name__ == "__main__":
    main()
