import subprocess, json

PERIODS = [
    {"from": "2015-01-01", "to": "2017-12-31", "split": "2016-07-01"},
    {"from": "2017-01-01", "to": "2019-12-31", "split": "2018-07-01"},
    {"from": "2019-01-01", "to": "2021-12-31", "split": "2020-07-01"},
    {"from": "2021-01-01", "to": "2023-12-31", "split": "2022-07-01"},
    {"from": "2023-01-01", "to": "2025-12-31", "split": "2024-07-01"},
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

with open("solo_cache.json") as f:
    cache = json.load(f)

for i, period in enumerate(PERIODS):
    key = f"low_vol_{i}"
    if key in cache:
        print(f"skip {key} (already cached)")
        continue
    print(f"running low_vol solo: {period['from']}~{period['to']} ...")
    cache[key] = run_solo("low_vol", period)
    with open("solo_cache.json", "w") as f:
        json.dump(cache, f)
    print(f"  done, saved incrementally")

print("ALL DONE")
