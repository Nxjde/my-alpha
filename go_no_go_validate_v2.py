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

CANDIDATES = [
    ("1:1", 1.0, 1),
    ("3:1", 3.0, 1),
    ("3.5:1", 3.5, 1),
    ("defensive 2.5:1", 2.5, 1),
    ("aggressive 4:1", 4.0, 1),
]

N_PERMUTATIONS = 2000
MIN_FOLDS_POSITIVE = 4
P_THRESHOLD = 0.05
MIN_PERIODS_PER_FOLD = 20

CACHE_FILE = "solo_cache.json"


def run_solo(alpha_name, period):
    cmd = [
        "qanat", "backtest",
        "--from", period["from"], "--to", period["to"],
        "--alpha", alpha_name,
        "--split", period["split"],
        "--json", "--quiet", "--force",
    ]
    out = subprocess.run(cmd, capture_output=True, text=True)
    start = out.stdout.find("{")
    if start == -1:
        raise RuntimeError(f"{alpha_name} {period}: JSON 못 찾음 -> {out.stdout[:300]} {out.stderr[:300]}")
    return json.loads(out.stdout[start:])


def load_or_run_solo():
    try:
        with open(CACHE_FILE) as f:
            print(f"{CACHE_FILE} 캐시 사용 (재실행 안 함)")
            return json.load(f)
    except FileNotFoundError:
        pass
    cache = {}
    for name in ("momentum", "reversal"):
        for i, period in enumerate(PERIODS):
            print(f"running {name} solo: {period['from']}~{period['to']} ...")
            cache[f"{name}_{i}"] = run_solo(name, period)
    with open(CACHE_FILE, "w") as f:
        json.dump(cache, f)
    return cache


def blended_out_sample_components(cache, period_idx, period, w_m, w_r):
    """out-of-sample 구간에서 날짜별 (gross, fees, slippage)를 비율대로 재조정하며 반환.
    net을 직접 섞지 않고 성분별로 섞어야, gross만 뒤집는 올바른 permutation이 가능하다."""
    m = {p["as_of"]: p for p in cache[f"momentum_{period_idx}"]["periods"]}
    r = {p["as_of"]: p for p in cache[f"reversal_{period_idx}"]["periods"]}
    dates = sorted(set(m) & set(r))
    split = period["split"]
    total_w = w_m + w_r
    wm, wr = w_m / total_w, w_r / total_w

    out = []
    for d in dates:
        if d < split:
            continue
        gross = wm * m[d]["gross"] + wr * r[d]["gross"]
        fees = wm * m[d]["fees"] + wr * r[d]["fees"]
        slip = wm * m[d]["slippage"] + wr * r[d]["slippage"]
        out.append({"gross": gross, "fees": fees, "slippage": slip})
    return out


def compound(net_list):
    equity = 1.0
    for n in net_list:
        equity *= 1.0 + n
    return equity - 1.0


def actual_net_series(components):
    return [c["gross"] - c["fees"] - c["slippage"] for c in components]


def permutation_test(components, n_perm=N_PERMUTATIONS, seed=0):
    """귀무가설: 방향 예측(gross의 부호)이 랜덤이었다면. fees/slippage는 방향과 무관하게
    항상 나가는 고정 비용이므로 뒤집지 않는다."""
    rng = random.Random(seed)
    actual = compound(actual_net_series(components))
    hits = 0
    for _ in range(n_perm):
        shuffled_net = [
            (c["gross"] if rng.random() < 0.5 else -c["gross"]) - c["fees"] - c["slippage"]
            for c in components
        ]
        if compound(shuffled_net) >= actual:
            hits += 1
    return actual, hits / n_perm


def main():
    cache = load_or_run_solo()

    print("\n\n" + "=" * 70)
    print("Go/No-Go 검증 결과 (gross-only permutation, fees/slippage 고정)")
    print("=" * 70)

    for label, w_m, w_r in CANDIDATES:
        print(f"\n\n########## {label} (momentum={w_m}, reversal={w_r}) ##########")
        fold_results = []
        for i, period in enumerate(PERIODS):
            components = blended_out_sample_components(cache, i, period, w_m, w_r)
            n = len(components)
            actual, p = permutation_test(components)
            positive = actual > 0
            passed = positive and p < P_THRESHOLD and n >= MIN_PERIODS_PER_FOLD
            fold_results.append({"net": actual, "p_value": p, "passed": passed})
            flag = "PASS" if passed else ("유의성 부족" if positive else "FAIL")
            print(f"  {period['from']}~{period['to']}: n={n}, net={actual:+.4f}, "
                  f"p={p:.4f}  -> {flag}")

        n_positive = sum(1 for f in fold_results if f["net"] > 0)
        n_significant = sum(1 for f in fold_results if f["p_value"] < P_THRESHOLD)
        n_passed = sum(1 for f in fold_results if f["passed"])
        print(f"\n  요약: {n_positive}/5 positive, {n_significant}/5 p<0.05, "
              f"{n_passed}/5 full-pass")
        verdict = "GO" if n_passed >= MIN_FOLDS_POSITIVE else "NO-GO"
        print(f"  기준: {MIN_FOLDS_POSITIVE}/5 이상 full-pass 필요 -> 판정: {verdict}")


if __name__ == "__main__":
    main()
