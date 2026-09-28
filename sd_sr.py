import statistics
from vol_robust import CACHE, SPLITS, summarize, evaluate, MULTS, RPS

def solo(name):
    out = []
    for i in range(5):
        p = sorted((q["as_of"], q["net"]) for q in CACHE[f"{name}_{i}"]["periods"])
        out.append([n for d, n in p if d >= SPLITS[i]])
    return out

def blend_oos(wm, wr):
    out = []
    for i in range(5):
        m = {q["as_of"]: q["net"] for q in CACHE[f"momentum_{i}"]["periods"]}
        r = {q["as_of"]: q["net"] for q in CACHE[f"reversal_{i}"]["periods"]}
        ds = sorted(set(m) & set(r))
        out.append([(wm * m[d] + wr * r[d]) / (wm + wr) for d in ds if d >= SPLITS[i]])
    return out

SR = lambda oos: summarize(oos)[1]

RATIOS = [(1, 1), (2, 1), (2.5, 1), (3, 1), (3.5, 1), (4, 1)]
A = {f"blend {a}:{b}": SR(blend_oos(a, b)) for a, b in RATIOS}
B = {k: SR(solo(k)) for k in ("momentum", "reversal", "low_vol")}
C = {f"vt{m}/RP{rp:.2%}/{mode}": evaluate(m, rp, mode)[1]
     for mode in ("global", "insample") for m in MULTS for rp in RPS}

def show(title, d):
    v = list(d.values())
    print(f"\n{title}: n={len(v)}  min={min(v):.4f}  max={max(v):.4f}  sd={statistics.stdev(v):.4f}")

show("A 비율 블렌드", A)
show("B 단독 알파(momentum/reversal/low_vol)", B)
show("C vol targeting 격자", C)
show("A+B", {**A, **B})
show("A+B+C 전체", {**A, **B, **C})
print("\n[B 상세]", {k: round(v, 4) for k, v in B.items()})
