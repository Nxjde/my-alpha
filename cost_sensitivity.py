import json
import random

PERIODS = [
    {"from": "2015-01-01", "to": "2017-12-31", "split": "2016-07-01"},
    {"from": "2017-01-01", "to": "2019-12-31", "split": "2018-07-01"},
    {"from": "2019-01-01", "to": "2021-12-31", "split": "2020-07-01"},
    {"from": "2021-01-01", "to": "2023-12-31", "split": "2022-07-01"},
    {"from": "2023-01-01", "to": "2025-12-31", "split": "2024-07-01"},
]

W_M, W_R = 1.0, 1.0  # 확정한 1:1

# 원래 백테스트 기본값이 fee_bps=5, slippage_bps=10 이었음 (STATE.md 참고).
# 여기서는 그보다 나쁜 시나리오까지 포함해서 얼마나 버티는지 확인.
COST_SCENARIOS = [
    ("기본값 (5bps/10bps)", 5.0, 10.0),
    ("1.5배 (7.5bps/15bps)", 7.5, 15.0),
    ("2배 (10bps/20bps)", 10.0, 20.0),
    ("3배 (15bps/30bps)", 15.0, 30.0),
    ("실제 리테일 최악 가정 (10bps/30bps)", 10.0, 30.0),
]

N_PERMUTATIONS = 2000
P_THRESHOLD = 0.05

CACHE_FILE = "solo_cache.json"


def compound(net_list):
    equity = 1.0
    for n in net_list:
        equity *= 1.0 + n
    return equity - 1.0


def blended_out_sample_raw(cache, period_idx, period):
    """gross, turnover를 비율대로 섞은 날짜별 raw 값 반환 (비용은 아직 적용 안 함)."""
    m = {p["as_of"]: p for p in cache[f"momentum_{period_idx}"]["periods"]}
    r = {p["as_of"]: p for p in cache[f"reversal_{period_idx}"]["periods"]}
    dates = sorted(set(m) & set(r))
    split = period["split"]
    total_w = W_M + W_R
    wm, wr = W_M / total_w, W_R / total_w

    out = []
    for d in dates:
        if d < split:
            continue
        gross = wm * m[d]["gross"] + wr * r[d]["gross"]
        turnover = wm * m[d]["turnover"] + wr * r[d]["turnover"]
        out.append({"gross": gross, "turnover": turnover})
    return out


def apply_costs(raw, fee_bps, slippage_bps):
    return [
        {
            "gross": x["gross"],
            "fees": x["turnover"] * fee_bps / 10_000.0,
            "slippage": x["turnover"] * slippage_bps / 10_000.0,
        }
        for x in raw
    ]


def net_series(components):
    return [c["gross"] - c["fees"] - c["slippage"] for c in components]


def permutation_test(components, n_perm=N_PERMUTATIONS, seed=0):
    rng = random.Random(seed)
    actual = compound(net_series(components))
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
    with open(CACHE_FILE) as f:
        cache = json.load(f)

    raw_by_period = [blended_out_sample_raw(cache, i, p) for i, p in enumerate(PERIODS)]

    print("=" * 70)
    print("momentum+reversal 1:1 — 거래비용 민감도 (재실행 없이 캐시로 계산)")
    print("=" * 70)

    for label, fee_bps, slip_bps in COST_SCENARIOS:
        print(f"\n########## {label} ##########")
        n_positive, n_significant = 0, 0
        for i, period in enumerate(PERIODS):
            components = apply_costs(raw_by_period[i], fee_bps, slip_bps)
            actual, p = permutation_test(components)
            if actual > 0:
                n_positive += 1
            if p < P_THRESHOLD:
                n_significant += 1
            print(f"  {period['from']}~{period['to']}: net={actual:+.4f}, p={p:.4f}")
        print(f"  -> {n_positive}/5 positive, {n_significant}/5 p<0.05")


if __name__ == "__main__":
    main()
