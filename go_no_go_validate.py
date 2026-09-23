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

# 검증할 후보 비율 (STATE.md 후보안 기준)
CANDIDATES = [
    ("defensive 2.5:1", 2.5, 1),
    ("aggressive 4:1", 4.0, 1),
]

N_PERMUTATIONS = 2000
MIN_FOLDS_POSITIVE = 4   # 5개 중 최소 4개 (BTC 프로젝트의 3-of-4 기준을 5-fold로 스케일)
P_THRESHOLD = 0.05
MIN_PERIODS_PER_FOLD = 20  # 최소 표본 수 체크 (BTC 프로젝트 min 100 trades에 대응하는 완화 버전)

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


def blended_out_sample_returns(cache, period_idx, period, w_m, w_r):
    """해당 period의 out-of-sample 구간에서, 지정 비율로 매 period마다 재조정한다고
    가정한 날짜별 blended net 리스트를 반환."""
    m = cache[f"momentum_{period_idx}"]["periods"]
    r = cache[f"reversal_{period_idx}"]["periods"]
    by_date_m = {p["as_of"]: p["net"] for p in m}
    by_date_r = {p["as_of"]: p["net"] for p in r}
    dates = sorted(set(by_date_m) & set(by_date_r))
    split = period["split"]
    total_w = w_m + w_r
    wm, wr = w_m / total_w, w_r / total_w
    return [wm * by_date_m[d] + wr * by_date_r[d] for d in dates if d >= split]


def compound(net_list):
    equity = 1.0
    for n in net_list:
        equity *= 1.0 + n
    return equity - 1.0


def permutation_test(returns, n_perm=N_PERMUTATIONS, seed=0):
    """귀무가설: 각 period 수익률의 부호는 랜덤(진짜 알파가 없다면 +/- 가 반반이어야 함).
    실제 수익률의 절댓값은 그대로 두고 부호만 랜덤하게 뒤집어서 n_perm번 복리 계산 후,
    실제 총수익 이상이 나온 비율을 p-value로 반환."""
    rng = random.Random(seed)
    actual = compound(returns)
    abs_vals = [abs(x) for x in returns]
    hits = 0
    for _ in range(n_perm):
        shuffled = [v if rng.random() < 0.5 else -v for v in abs_vals]
        if compound(shuffled) >= actual:
            hits += 1
    p_value = hits / n_perm
    return actual, p_value


def main():
    cache = load_or_run_solo()

    print("\n\n" + "=" * 70)
    print("Go/No-Go 검증 결과")
    print("=" * 70)

    for label, w_m, w_r in CANDIDATES:
        print(f"\n\n########## {label} (momentum={w_m}, reversal={w_r}) ##########")
        fold_results = []
        for i, period in enumerate(PERIODS):
            returns = blended_out_sample_returns(cache, i, period, w_m, w_r)
            n = len(returns)
            actual, p = permutation_test(returns)
            positive = actual > 0
            passed = positive and p < P_THRESHOLD and n >= MIN_PERIODS_PER_FOLD
            fold_results.append({
                "period": f"{period['from']}~{period['to']}",
                "n_periods": n, "net": actual, "p_value": p, "passed": passed,
            })
            flag = "PASS" if passed else ("정답이지만 유의성 부족" if positive else "FAIL")
            print(f"  {period['from']}~{period['to']}: n={n}, net={actual:+.4f}, "
                  f"p={p:.4f}  -> {flag}")

        n_positive = sum(1 for f in fold_results if f["net"] > 0)
        n_significant = sum(1 for f in fold_results if f["p_value"] < P_THRESHOLD)
        n_passed = sum(1 for f in fold_results if f["passed"])

        print(f"\n  요약: {n_positive}/5 folds positive, {n_significant}/5 folds p<0.05, "
              f"{n_passed}/5 folds full-pass (positive AND p<0.05 AND n>={MIN_PERIODS_PER_FOLD})")

        verdict = "GO" if n_passed >= MIN_FOLDS_POSITIVE else "NO-GO"
        print(f"  기준: {MIN_FOLDS_POSITIVE}/5 이상 full-pass 필요 -> 판정: {verdict}")


if __name__ == "__main__":
    main()
