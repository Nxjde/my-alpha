import subprocess
import json

PERIODS = [
    {"from": "2015-01-01", "to": "2017-12-31", "split": "2016-07-01"},
    {"from": "2017-01-01", "to": "2019-12-31", "split": "2018-07-01"},
    {"from": "2019-01-01", "to": "2021-12-31", "split": "2020-07-01"},
    {"from": "2021-01-01", "to": "2023-12-31", "split": "2022-07-01"},
    {"from": "2023-01-01", "to": "2025-12-31", "split": "2024-07-01"},
]

# 로컬에서 시험해볼 momentum:reversal 비율들 (재실행 없이 여기만 수정하면 됨)
ALLOCATIONS = [
    (1, 1), (2, 1), (3, 1), (2.5, 1), (3.5, 1), (4, 1), (1, 2),
]


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


def compound(net_list):
    equity = 1.0
    for n in net_list:
        equity *= 1.0 + n
    return equity - 1.0


def combine(periods_m, periods_r, w_m, w_r, split_date):
    """momentum sleeve와 reversal sleeve를 as_of 날짜로 맞춰서 지정 비율로
    매 period마다 재조정(fixed-weight rebalance)한다고 가정하고 복리 계산."""
    by_date_m = {p["as_of"]: p["net"] for p in periods_m}
    by_date_r = {p["as_of"]: p["net"] for p in periods_r}
    dates = sorted(set(by_date_m) & set(by_date_r))
    missing = set(by_date_m) ^ set(by_date_r)
    if missing:
        print(f"    경고: 두 알파의 as_of 날짜가 안 맞는 부분 {len(missing)}개 (교집합만 사용)")

    total_w = w_m + w_r
    wm, wr = w_m / total_w, w_r / total_w

    in_sample_net, out_sample_net = [], []
    for d in dates:
        blended = wm * by_date_m[d] + wr * by_date_r[d]
        if d < split_date:
            in_sample_net.append(blended)
        else:
            out_sample_net.append(blended)

    return compound(in_sample_net), compound(out_sample_net)


def main():
    solo_cache = {}  # (alpha, period_idx) -> json result

    for name in ("momentum", "reversal"):
        for i, period in enumerate(PERIODS):
            print(f"running {name} solo: {period['from']}~{period['to']} ...")
            solo_cache[(name, i)] = run_solo(name, period)

    print("\n\n=== sleeve 방식 결과 (비율별 x 구간별) ===")
    for w_m, w_r in ALLOCATIONS:
        label = f"momentum={w_m}:reversal={w_r}"
        print(f"\n########## {label} ##########")
        for i, period in enumerate(PERIODS):
            m_json = solo_cache[("momentum", i)]
            r_json = solo_cache[("reversal", i)]
            in_net, out_net = combine(
                m_json["periods"], r_json["periods"], w_m, w_r, period["split"]
            )
            print(f"  {period['from']}~{period['to']} (split {period['split']}): "
                  f"in-sample={in_net:.4f}, out-of-sample={out_net:.4f}")

    print("\n\n=== 참고: momentum/reversal 단독 결과 (sleeve 검증용) ===")
    for name in ("momentum", "reversal"):
        print(f"\n-- {name} 단독 --")
        for i, period in enumerate(PERIODS):
            seg = solo_cache[(name, i)]["segments"]
            print(f"  {period['from']}~{period['to']}: "
                  f"in-sample={seg['in_sample']['net']:.4f}, "
                  f"out-of-sample={seg['out_of_sample']['net']:.4f}")


if __name__ == "__main__":
    main()
