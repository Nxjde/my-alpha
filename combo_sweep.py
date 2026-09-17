import subprocess
import json

tests = [
    {"from": "2015-01-01", "to": "2017-12-31", "split": "2016-07-01"},
    {"from": "2017-01-01", "to": "2019-12-31", "split": "2018-07-01"},
    {"from": "2019-01-01", "to": "2021-12-31", "split": "2020-07-01"},
    {"from": "2021-01-01", "to": "2023-12-31", "split": "2022-07-01"},
    {"from": "2023-01-01", "to": "2025-12-31", "split": "2024-07-01"},
]

results = []
for t in tests:
    print(f"=== {t['from']} ~ {t['to']}, split {t['split']} ===")
    cmd = [
        "qanat", "backtest",
        "--from", t["from"], "--to", t["to"],
        "--alpha", "alpha_momentum,alpha_low_vol",
        "--allocation", "momentum=2,low_vol=1",
        "--split", t["split"],
        "--json", "--quiet", "--force"
    ]
    out = subprocess.run(cmd, capture_output=True, text=True)
    stdout = out.stdout
    json_start = stdout.find("{")
    if json_start == -1:
        print("  JSON 못 찾음:", stdout[:300], out.stderr[:300])
        continue
    try:
        data = json.loads(stdout[json_start:])
        seg = data.get("segments", {})
        in_s = seg.get("in_sample", {}).get("net")
        out_s = seg.get("out_of_sample", {}).get("net")
        results.append({**t, "in_sample_net": in_s, "out_sample_net": out_s})
        print(f"  in-sample: {in_s}, out-of-sample: {out_s}")
    except Exception as e:
        print(f"  파싱 실패: {e}, {stdout[json_start:json_start+200]}")

print("\n=== 요약 ===")
for r in results:
    print(r)
