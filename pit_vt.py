import json, random
import numpy as np

F = json.load(open("pit_full.json"))
LB = 12

def vt_oos(nets, n_is, mult, rp_annual, cost=0.0):
    x = np.array(nets)
    pool = [x[j - LB:j].std() for j in range(LB, n_is + 1)]
    target = mult * np.mean([v for v in pool if v > 0])
    rp = rp_annual * 5 / 365
    def sc(k):
        v = x[k - LB:k].std()
        return 1.0 if v == 0 else max(0.5, min(1.0, target / v))
    prev, out = sc(n_is - 1), []
    for k in range(n_is, len(x)):
        s = sc(k)
        out.append(x[k] * s + (1 - s) * rp - abs(s - prev) * cost)
        prev = s
    return out

def compound(x):
    return float(np.prod(1 + np.array(x)) - 1)

def mdd(x):
    e = np.cumprod(1 + np.array(x))
    pk = np.maximum.accumulate(np.r_[1.0, e])[1:]
    return float((e / pk - 1).min())

def summarize(by_win):
    pool = np.array([r for o in by_win for r in o])
    return (float(np.mean([compound(o) for o in by_win])), float(pool.mean() / pool.std()),
            min(mdd(o) for o in by_win), pool)

def base_oos(key):
    return [F[key][lab][0][F[key][lab][1]:] for lab in F[key]]

def run_vt(key, mult, rp, cost=0.0):
    return summarize([vt_oos(F[key][lab][0], F[key][lab][1], mult, rp, cost) for lab in F[key]])

def boot(a, b, block=10, B=2000, seed=0):
    rnd, n, d = random.Random(seed), len(a), []
    sr = lambda x: x.mean() / x.std()
    for _ in range(B):
        idx = []
        while len(idx) < n:
            s = rnd.randrange(n - block + 1)
            idx += range(s, s + block)
        idx = idx[:n]
        d.append(sr(a[idx]) - sr(b[idx]))
    d.sort()
    return d[int(0.025 * B)], d[B // 2], d[int(0.975 * B)], sum(x <= 0 for x in d) / B

MULTS = [0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
for key, label in (("nofilter", "필터 없음"), ("pit", "편입일 필터")):
    b = summarize(base_oos(key))
    print(f"\n=== {label} | baseline avg_net={b[0]:.1%} Sharpe={b[1]:.4f} mdd={b[2]:.1%} ===")
    print("mult   Sharpe(RP0) Sharpe(RP3.35)  net@RP0  net@3.35  mdd@3.35")
    for m in MULTS:
        r0, r1 = run_vt(key, m, 0.0), run_vt(key, m, 0.0335)
        print(f"{m:<6} {r0[1]:>10.4f} {r1[1]:>13.4f} {r0[0]:>8.1%} {r1[0]:>9.1%} {r1[2]:>9.1%}")
    c = run_vt(key, 0.7, 0.0335, 0.0015)
    print(f"비용15bps(0.7, RP3.35%): net={c[0]:.1%} Sharpe={c[1]:.4f} mdd={c[2]:.1%}")
    for rp in (0.0, 0.0335):
        lo, mid, hi, p = boot(run_vt(key, 0.7, rp)[3], b[3])
        print(f"  0.7/RP{rp:.2%} - baseline: dSharpe CI[{lo:+.4f},{hi:+.4f}] 중앙 {mid:+.4f} P(d<=0)={p:.2f}")
