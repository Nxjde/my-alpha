"""qanat.yaml의 backtest: 항목 바로 앞에 alpha_overnight_high/low step 2개를 삽입한다."""

NEW_STEPS = """- id: alpha_overnight_high
  from:
  - normalized.prices
  to:
  - weights.overnight_high
  script: steps/alpha_overnight.py
  universe: sp500
  options:
    top_n: 4
    reads: normalized.prices
    direction: high
- id: alpha_overnight_low
  from:
  - normalized.prices
  to:
  - weights.overnight_low
  script: steps/alpha_overnight.py
  universe: sp500
  options:
    top_n: 4
    reads: normalized.prices
    direction: low
"""

path = "qanat.yaml"
with open(path) as f:
    content = f.read()

if "alpha_overnight_high" in content:
    print("이미 추가되어 있음 — 아무것도 안 함")
else:
    marker = "backtest:"
    idx = content.index(marker)
    with open(path + ".bak4", "w") as f:
        f.write(content)
    new_content = content[:idx] + NEW_STEPS + content[idx:]
    with open(path, "w") as f:
        f.write(new_content)
    print("추가 완료. 백업: qanat.yaml.bak4")
