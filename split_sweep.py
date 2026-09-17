import subprocess
import json

splits = ["2024-12-01", "2025-03-01", "2025-06-01", "2025-09-11", "2025-12-01"]

results = []
for split in splits:
    print(f"=== split: {split} ===")
    cmd = [
        "qanat", "backtest",
        "--from", "2024-09-12",
        "--to", "2026-09-11",
        "--alpha", "alpha_momentum",
        "--split", split,
        "--json", "--quiet", "--force"
    ]
    out = subprocess.run(cmd, capture_output=True, text=True)

    # JSON은 첫 '{' 부터 시작하니 그 부분만 추출
    stdout = out.stdout
    json_start = stdout.find("{")
    if json_start == -1:
        print("  JSON을 못 찾음")
        print(stdout[:500])
        print(out.stderr[:500])
        continue

    try:
        data = json.loads(stdout[json_start:])
        seg = data.get("segments", {})
        in_s = seg.get("in_sample", {}).get("net")
        out_s = seg.get("out_of_sample", {}).get("net")
        results.append({"split": split, "in_sample_net": in_s, "out_sample_net": out_s})
        print(f"  in-sample: {in_s}, out-of-sample: {out_s}")
    except Exception as e:
        print(f"  파싱 실패: {e}")
        print(stdout[json_start:json_start+300])

print("\n=== 요약 ===")
for r in results:
    print(r)
