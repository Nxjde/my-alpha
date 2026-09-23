"""qanat.yaml의 backtest: 항목 바로 앞에 alpha_reversal_lb2/lb3/lb4 step 3개를 삽입한다.
실행 전 자동으로 qanat.yaml.bak3 백업을 만든다."""

NEW_STEPS = """- id: alpha_reversal_lb2
  from:
  - normalized.prices
  to:
  - weights.reversal_lb2
  script: steps/alpha_reversal_lb2.py
  universe: sp500
  options:
    lookback: 2
    top_n: 4
    reads: normalized.prices
- id: alpha_reversal_lb3
  from:
  - normalized.prices
  to:
  - weights.reversal_lb3
  script: steps/alpha_reversal_lb3.py
  universe: sp500
  options:
    lookback: 3
    top_n: 4
    reads: normalized.prices
- id: alpha_reversal_lb4
  from:
  - normalized.prices
  to:
  - weights.reversal_lb4
  script: steps/alpha_reversal_lb4.py
  universe: sp500
  options:
    lookback: 4
    top_n: 4
    reads: normalized.prices
"""

path = "qanat.yaml"
with open(path) as f:
    content = f.read()

if "alpha_reversal_lb2" in content:
    print("이미 추가되어 있음 — 아무것도 안 함")
else:
    marker = "backtest:"
    idx = content.index(marker)
    with open(path + ".bak3", "w") as f:
        f.write(content)
    new_content = content[:idx] + NEW_STEPS + content[idx:]
    with open(path, "w") as f:
        f.write(new_content)
    print("추가 완료. 백업: qanat.yaml.bak3")
