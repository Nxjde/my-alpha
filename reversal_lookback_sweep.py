"""momentum+reversal 'frequent trading' 후보 스윕:
lookback=2/3/4일을 각각 같은 rebalance 주기(2d/3d/4d)로 테스트.
기존 alpha_reversal(lookback=5, rebalance=5d)와 alpha_reversal_short(lookback=1)도
동일한 방식(lookback==rebalance)으로 재검증해서 다섯 지점을 나란히 비교한다.
"""

import subprocess, json, random

PERIODS = [
    {"from": "2015-01-01", "to": "2017-12-31", "split": "2016-07-01"},
    {"from": "2017-01-01", "to": "2019-12-31", "split": "2018-07-01"},
    {"from": "2019-01-01", "to": "2021-12-31", "split": "2020-07-01"},
    {"from": "2021-01-01", "to": "2023-12-31", "split": "2022-07-01"},
    {"from": "2023-01-01", "to": "2025-12-31", "split": "2024-07-01"},
]

# (표시용 이름, qanat 알파 id, rebalance) — lookback==rebalance로 맞춰서 진짜 매매 빈도 효과를 봄
CANDIDATES = [
    ("lookback=1 / 1d", "alpha_reversal_short", "1d"),
    ("lookback=2 / 2d", "alpha_reversal_lb2", "2d"),
    ("lookback=3 / 3d", "alpha_reversal_lb3", "3d"),
    ("lookback=4 / 4d", "alpha_reversal_lb4", "4d"),
    ("lookback=5 / 5d (기존 baseline)", "alpha_reversal", "5d"),
]

N_PERMUTATIONS, P_THRESHOLD, MIN_FOLDS_POSITIVE, MIN_PERIODS = 2000, 0.05, 4, 20
CACHE_FILE = "reversal_lookback_sweep_cache.json"


def load_cache():
    try:
        return json.load(open(CACHE_FILE))
    except FileNotFoundError:
        return {}


def save_cache(cache):
    json.dump(cache, open(CACHE_FILE, "w"))


def run_solo(alpha_id, rebalance, period, key):
    print(f"  running {alpha_id} (rebalance={rebalance}): {period['from']}~{period['to']}")
    cmd = ["qanat", "backtest", "--from", period["from"], "--to", period["to"],
           "--alpha", alpha_id, "--rebalance", rebalance,
           "--split", period["split"], "--json", "--quiet", "--force"]
    out = subprocess.run(cmd, capture_output=True, text=True)
    start = out.stdout.find("{")
    if start == -1:
        raise RuntimeError(f"{key}: JSON 못 찾음 -> {out.stdout[:300]} {out.stderr[:300]}")
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

    for label, alpha_id, rebalance in CANDIDATES:
        print(f"\n### {label} ({alpha_id}, rebalance={rebalance}) ###")
        for i, period in enumerate(PERIODS):
            key = f"{alpha_id}_{rebalance}_{i}"
            if key in cache:
                print(f"  구간 {i+1}/5: 캐시 사용")
                continue
            cache[key] = run_solo(alpha_id, rebalance, period, key)
            save_cache(cache)

    print("\n\n" + "=" * 70)
    print("Go/No-Go 결과 (lookback==rebalance 매칭, gross-only permutation)")
    print("=" * 70)

    summary = []
    for label, alpha_id, rebalance in CANDIDATES:
        print(f"\n########## {label} ##########")
        results = []
        for i, period in enumerate(PERIODS):
            key = f"{alpha_id}_{rebalance}_{i}"
            split = period["split"]
            comps = [{"gross": p["gross"], "fees": p["fees"], "slippage": p["slippage"]}
                     for p in cache[key]["periods"] if p["as_of"] >= split]
            n = len(comps)
            if n < MIN_PERIODS:
                print(f"  {period['from']}~{period['to']}: n={n} 표본 부족 SKIP")
                results.append({"net": 0, "p": 1.0, "passed": False})
                continue
            net, p = perm_test(comps)
            passed = net > 0 and p < P_THRESHOLD
            results.append({"net": net, "p": p, "passed": passed})
            flag = "PASS" if passed else ("유의성 부족" if net > 0 else "FAIL")
            print(f"  {period['from']}~{period['to']}: n={n}, net={net:+.4f}, p={p:.4f} -> {flag}")

        n_pos = sum(1 for r in results if r["net"] > 0)
        n_sig = sum(1 for r in results if r["p"] < P_THRESHOLD)
        n_pass = sum(1 for r in results if r["passed"])
        verdict = "GO" if n_pass >= MIN_FOLDS_POSITIVE else "NO-GO"
        avg_net = sum(r["net"] for r in results) / len(results)
        print(f"  요약: {n_pos}/5 positive, {n_sig}/5 p<0.05, {n_pass}/5 full-pass, "
              f"평균 net={avg_net:+.4f} -> 판정: {verdict}")
        summary.append((label, n_pos, n_sig, n_pass, avg_net, verdict))

    print("\n\n" + "=" * 70)
    print("최종 비교표")
    print("=" * 70)
    print(f"{'candidate':<28} {'positive':<10} {'p<0.05':<8} {'pass':<6} {'avg net':<10} verdict")
    for label, n_pos, n_sig, n_pass, avg_net, verdict in summary:
        print(f"{label:<28} {n_pos}/5{'':<6} {n_sig}/5{'':<4} {n_pass}/5{'':<2} {avg_net:+.4f}   {verdict}")


if __name__ == "__main__":
    main()
