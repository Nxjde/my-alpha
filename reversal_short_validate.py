"""
reversal_short_validate.py

alpha_reversal_short (lookback=1) 단독으로 5구간 Go/No-Go 검증.
- 기존 solo_cache.json과 별개로 reversal_short_cache.json에 결과 저장
- 검증 기준: 5구간 중 4구간 이상 (positive AND p<0.05 AND n>=20)
- permutation: gross 부호만 뒤집기, fees/slippage 고정
"""
import subprocess
import json
import random

PERIODS = [
    {"from": "2015-01-01", "to": "2017-12-31", "split": "2016-07-01"},
    {"from": "2017-01-01", "to": "2019-12-31", "split": "2018-07-01"},
    {"from": "2019-01-01", "to": "2021-12-31", "split": "2020-07-01"},
    {"from": "2021-01-01", "to": "2023-12-31", "split": "2022-07-01"},
    {"from": "2023-01-01", "to": "2025-12-31", "split": "2024-07-01"},
]

N_PERMUTATIONS = 2000
P_THRESHOLD = 0.05
MIN_FOLDS_POSITIVE = 4
MIN_PERIODS = 20
CACHE_FILE = "reversal_short_cache.json"


def run_solo(period):
    cmd = [
        "qanat", "backtest",
        "--from", period["from"], "--to", period["to"],
        "--alpha", "alpha_reversal_short",
        "--split", period["split"],
        "--json", "--quiet", "--force",
    ]
    out = subprocess.run(cmd, capture_output=True, text=True)
    start = out.stdout.find("{")
    if start == -1:
        raise RuntimeError(f"JSON 못 찾음: {out.stdout[:300]} {out.stderr[:300]}")
    return json.loads(out.stdout[start:])


def load_or_run():
    try:
        with open(CACHE_FILE) as f:
            print(f"{CACHE_FILE} 캐시 사용")
            return json.load(f)
    except FileNotFoundError:
        pass
    cache = {}
    for i, period in enumerate(PERIODS):
        print(f"running reversal_short solo: {period['from']}~{period['to']} ...")
        cache[str(i)] = run_solo(period)
    with open(CACHE_FILE, "w") as f:
        json.dump(cache, f)
    return cache


def out_sample_components(result, period):
    periods_data = result["periods"]
    split = period["split"]
    out = []
    for p in periods_data:
        if p["as_of"] < split:
            continue
        out.append({
            "gross": p["gross"],
            "fees": p["fees"],
            "slippage": p["slippage"],
        })
    return out


def compound(net_list):
    eq = 1.0
    for n in net_list:
        eq *= 1.0 + n
    return eq - 1.0


def permutation_test(components, n_perm=N_PERMUTATIONS, seed=0):
    rng = random.Random(seed)
    actual = compound([c["gross"] - c["fees"] - c["slippage"] for c in components])
    hits = 0
    for _ in range(n_perm):
        shuffled = [
            (c["gross"] if rng.random() < 0.5 else -c["gross"]) - c["fees"] - c["slippage"]
            for c in components
        ]
        if compound(shuffled) >= actual:
            hits += 1
    return actual, hits / n_perm


def main():
    cache = load_or_run()

    print("\n" + "=" * 70)
    print("alpha_reversal_short (lookback=1) — Go/No-Go 검증")
    print("=" * 70)

    # 비교용: 기존 reversal(lookback=5) 결과도 solo_cache.json에서 같이 보여줌
    try:
        with open("solo_cache.json") as f:
            old_cache = json.load(f)
        print("\n[참고] 기존 reversal(lookback=5) out-of-sample:")
        for i, period in enumerate(PERIODS):
            seg = old_cache[f"reversal_{i}"]["segments"]
            print(f"  {period['from']}~{period['to']}: {seg['out_of_sample']['net']:+.4f}")
    except Exception:
        pass

    print("\n[신규] reversal_short(lookback=1) Go/No-Go:")
    fold_results = []
    for i, period in enumerate(PERIODS):
        components = out_sample_components(cache[str(i)], period)
        n = len(components)
        if n < MIN_PERIODS:
            print(f"  {period['from']}~{period['to']}: n={n} (표본 부족, SKIP)")
            fold_results.append({"net": 0, "p_value": 1.0, "passed": False})
            continue
        actual, p = permutation_test(components)
        positive = actual > 0
        passed = positive and p < P_THRESHOLD
        fold_results.append({"net": actual, "p_value": p, "passed": passed})
        flag = "PASS" if passed else ("유의성 부족" if positive else "FAIL")
        print(f"  {period['from']}~{period['to']}: n={n}, net={actual:+.4f}, p={p:.4f}  -> {flag}")

    n_positive = sum(1 for f in fold_results if f["net"] > 0)
    n_sig = sum(1 for f in fold_results if f["p_value"] < P_THRESHOLD)
    n_passed = sum(1 for f in fold_results if f["passed"])
    print(f"\n  요약: {n_positive}/5 positive, {n_sig}/5 p<0.05, {n_passed}/5 full-pass")
    verdict = "GO ✓" if n_passed >= MIN_FOLDS_POSITIVE else "NO-GO ✗"
    print(f"  기준: {MIN_FOLDS_POSITIVE}/5 이상 full-pass 필요 -> 판정: {verdict}")

    print("\n[비교] 단기화의 실제 효과:")
    print("  구간별 net 비교는 위 참고 수치와 대조해서 보세요.")
    print("  비용이 5배 늘어나는 대신 신호가 더 날카로워졌는지가 핵심입니다.")


if __name__ == "__main__":
    main()
