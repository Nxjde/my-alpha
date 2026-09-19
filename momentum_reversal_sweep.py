import subprocess
import json

tests = [
    {"from": "2015-01-01", "to": "2017-12-31", "split": "2016-07-01"},
    {"from": "2017-01-01", "to": "2019-12-31", "split": "2018-07-01"},
    {"from": "2019-01-01", "to": "2021-12-31", "split": "2020-07-01"},
    {"from": "2021-01-01", "to": "2023-12-31", "split": "2022-07-01"},
    {"from": "2023-01-01", "to": "2025-12-31", "split": "2024-07-01"},
]

# STATE.md TODO: 다양한 비율로 momentum+reversal 검증
# 필요하면 이 리스트에 비율을 추가/삭제해서 원하는 조합만 돌리면 됨
allocations = [
    "momentum=1,reversal=1",   # 1:1 (50:50) - low_vol 최선 조합과 동일 비율로 우선 비교
    "momentum=2,reversal=1",   # 2:1 (67:33)
    "momentum=3,reversal=1",   # 3:1 (75:25)
    "momentum=1,reversal=2",   # 1:2 - reversal 비중을 더 준 경우
]

all_results = {}

for alloc in allocations:
    print(f"\n########## allocation: {alloc} ##########")
    results = []
    for t in tests:
        print(f"=== {t['from']} ~ {t['to']}, split {t['split']} ===")
        cmd = [
            "qanat", "backtest",
            "--from", t["from"], "--to", t["to"],
            "--alpha", "alpha_momentum,alpha_reversal",
            "--allocation", alloc,
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
    all_results[alloc] = results

print("\n\n=== 전체 요약 (allocation별) ===")
for alloc, results in all_results.items():
    print(f"\n-- {alloc} --")
    for r in results:
        print(r)

# 참고: STATE.md 기준 비교 대상
# 순수 momentum:      2017-19 -26.7% / 2019-21 +84.4% / 2021-23 +104.6% / 2023-25 +113.5%
# momentum+low_vol(1:1): 2017-19 -3.9% / 2019-21 +52.8% / 2021-23 +39.8% / 2023-25 +48.6%
# reversal(단독):      2017-19 +127.3% / 2019-21 +40.9% / 2021-23 +24.1% / 2023-25 -4.9%
