import json
import numpy as np
C = json.load(open("solo_cache.json"))
SP = ["2016-07-01", "2018-07-01", "2020-07-01", "2022-07-01", "2024-07-01"]
name = "momentum"
r = []
for i in (1, 2, 3, 4):
    p = sorted((q["as_of"][:10], q["net"]) for q in C[f"{name}_{i}"]["periods"])
    o = [n for d, n in p if d >= SP[i]]
    print(f"창{i} 기간수 {len(o)} 평균net {np.mean(o):.4%} 누적 {np.prod(1 + np.array(o)) - 1:.1%}")
    r += o
lg = np.log1p(np.array(r)); eq = np.exp(np.cumsum(lg))
print(f"전체 {len(r)}기간, 누적 {eq[-1]:.2f}배, 로그성장 {lg.sum():.3f}")
blk = [lg[i:i + 27].sum() for i in range(0, len(lg), 27)]
for k, b in enumerate(blk):
    print(f"블록 {k + 1:>2}  로그성장 {b:+.3f}")
top2 = sum(sorted(blk, reverse=True)[:2])
print(f"상위 2블록 비중 {top2 / lg.sum():.0%}  (블렌드는 46%)")
