import json, math, random, statistics
from statistics import NormalDist

SPLITS = ["2016-07-01", "2018-07-01", "2020-07-01", "2022-07-01", "2024-07-01"]
LB, MIN_CAP = 12, 0.5
CACHE = json.load(open("solo_cache.json"))

def blend(i):
    m = {p["as_of"]: p["net"] for p in CACHE[f"momentum_{i}"]["periods"]}
    r = {p["as_of"]: p["net"] for p in CACHE[f"reversal_{i}"]["periods"]}
    return [(d, 0.5 * m[d] + 0.5 * r[d]) for d in sorted(set(m) & set(r))]

SER = [blend(i) for i in range(5)]
NETS = [[n for _, n in s] for s in SER]
N_IS = [sum(1 for d, _ in SER[i] if d < SPLITS[i]) for i in range(5)]

def vol_pool(i, upto=None):
    x = NETS[i]
    end = len(x) if upto is None else upto
    return [v for v in (statistics.pstdev(x[j - LB:j]) for j in range(LB, end)) if v]

GLOBAL_BASE = statistics.mean([v for i in range(5) for v in vol_pool(i)])

def compound(x):
    e = 1.0
    for n in x:
        e *= 1 + n
    return e - 1

def mdd(x):
    e = pk = 1.0
    dd = 0.0
    for n in x:
        e *= 1 + n
        pk = max(pk, e)
        dd = min(dd, e / pk - 1)
    return dd

def scaled_oos(i, mult, rp_annual, mode, cost=0.0):
    x = NETS[i]
    base = GLOBAL_BASE if mode == "global" else statistics.mean(vol_pool(i, N_IS[i] + 1))
    target, rp = mult * base, rp_annual * 5 / 365
    def scale(k):
        v = statistics.pstdev(x[k - LB:k])
        return 1.0 if v == 0 else max(MIN_CAP, min(1.0, target / v))
    prev, out = scale(N_IS[i] - 1), []
    for k in range(N_IS[i], len(x)):
        s = scale(k)
        out.append(x[k] * s + (1 - s) * rp - abs(s - prev) * cost)
        prev = s
    return out

def summarize(oos_by_period):
    pool = [r for o in oos_by_period for r in o]
    return (statistics.mean(compound(o) for o in oos_by_period),
            statistics.mean(pool) / statistics.pstdev(pool),
            min(mdd(o) for o in oos_by_period), pool)

def baseline():
    return summarize([NETS[i][N_IS[i]:] for i in range(5)])

def evaluate(mult, rp, mode, cost=0.0):
    return summarize([scaled_oos(i, mult, rp, mode, cost) for i in range(5)])

MULTS = [0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
RPS = [0.0, 0.02, 0.0335, 0.04, 0.05]

if __name__ == "__main__":
    b = baseline()
    print(f"baseline  avg_net={b[0]:.1%}  sharpe={b[1]:.4f}  mdd={b[2]:.1%}")
    for mode in ("global", "insample"):
        R = {(m, rp): evaluate(m, rp, mode) for m in MULTS for rp in RPS}
        print(f"\n=== target_vol={mode} | Sharpe by RP rate ===")
        print("mult  " + "".join(f"{rp:>8.2%}" for rp in RPS) + "  net@0%  net@3.35%  mdd@3.35%")
        for m in MULTS:
            row = "".join(f"{R[(m, rp)][1]:>8.4f}" for rp in RPS)
            print(f"{m:<6}{row}  {R[(m, 0.0)][0]:>6.1%}  {R[(m, 0.0335)][0]:>8.1%}  {R[(m, 0.0335)][2]:>8.1%}")
        c = evaluate(0.7, 0.0335, mode, cost=0.0015)
        print(f"switch cost 15bps/unit (0.7, RP3.35%): net={c[0]:.1%} sharpe={c[1]:.4f} mdd={c[2]:.1%}")
