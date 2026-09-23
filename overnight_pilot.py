"""오버나잇 갭 전략 파일럿: 딱 1개 구간(2023~2025)만 high/low 두 방향으로 돌려서
gross/net이 애초에 말이 되는 수준인지 싸게 확인한다.
여기서 그럴듯하면 -> 5구간 풀 Go/No-Go로 진행.
여기서부터 이미 답이 없으면 -> 오버나잇도 접고 다른 후보로."""

import subprocess, json

PERIOD = {"from": "2023-01-01", "to": "2025-12-31", "split": "2024-07-01"}
CANDIDATES = [
    ("overnight_high (갭업 매수)", "alpha_overnight_high"),
    ("overnight_low (갭다운 매수)", "alpha_overnight_low"),
]


def run_solo(alpha_id):
    cmd = ["qanat", "backtest", "--from", PERIOD["from"], "--to", PERIOD["to"],
           "--alpha", alpha_id, "--rebalance", "1d",
           "--split", PERIOD["split"], "--json", "--quiet", "--force"]
    print(f"  실행 중: {alpha_id} ...")
    out = subprocess.run(cmd, capture_output=True, text=True)
    start = out.stdout.find("{")
    if start == -1:
        raise RuntimeError(f"{alpha_id}: JSON 못 찾음 -> {out.stdout[:300]} {out.stderr[:300]}")
    return json.loads(out.stdout[start:])


def compound(nets):
    eq = 1.0
    for n in nets:
        eq *= 1.0 + n
    return eq - 1.0


def main():
    for label, alpha_id in CANDIDATES:
        print(f"\n### {label} ###")
        result = run_solo(alpha_id)
        split = PERIOD["split"]
        oos = [p for p in result["periods"] if p["as_of"] >= split]
        n = len(oos)
        gross = compound([p["gross"] for p in oos])
        net = compound([p["gross"] - p["fees"] - p["slippage"] for p in oos])
        avg_fee_drag = sum(p["fees"] + p["slippage"] for p in oos) / n if n else 0
        print(f"  out-of-sample n={n}")
        print(f"  gross(비용 전) 누적수익 = {gross:+.4f}")
        print(f"  net(비용 후)  누적수익 = {net:+.4f}")
        print(f"  구간당 평균 비용        = {avg_fee_drag:.5f}")


if __name__ == "__main__":
    main()
