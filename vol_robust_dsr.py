import math, random, statistics
from statistics import NormalDist
from vol_robust import baseline, evaluate

N = NormalDist()

def dsr(r, M, sd_sr):
    n, mu, sd = len(r), statistics.mean(r), statistics.stdev(r)
    sr = mu / sd
    sk = sum((x - mu) ** 3 for x in r) / n / sd ** 3
    ku = sum((x - mu) ** 4 for x in r) / n / sd ** 4
    g = 0.5772156649
    sr0 = sd_sr * ((1 - g) * N.inv_cdf(1 - 1 / M) + g * N.inv_cdf(1 - 1 / (M * math.e)))
    sig = math.sqrt(max((1 - sk * sr + (ku - 1) / 4 * sr ** 2) / (n - 1), 1e-12))
    return sr, sr0, N.cdf((sr - sr0) / sig)

MS, SDS = [6, 30, 55, 80, 120], [0.0025, 0.02, 0.04, 0.06]
CANDS = {
    "baseline": baseline()[3],
    "vt0.7+RP3.35 (global)": evaluate(0.7, 0.0335, "global")[3],
    "vt0.7+RP3.35 (insample)": evaluate(0.7, 0.0335, "insample")[3],
    "vt0.7+RP0 (insample)": evaluate(0.7, 0.0, "insample")[3],
}

for name, r in CANDS.items():
    print(f"\n[{name}] n={len(r)} Sharpe={dsr(r, 6, 0.0025)[0]:.4f}")
    print("sd_SR/M   " + "".join(f"{m:>8}" for m in MS))
    for s in SDS:
        print(f"{s:<10}" + "".join(f"{dsr(r, m, s)[2]:>8.3f}" for m in MS))

def sr_of(x):
    return statistics.mean(x) / statistics.pstdev(x)

def boot_diff(a, b, block=10, B=2000, seed=0):
    rnd, n, d = random.Random(seed), len(a), []
    for _ in range(B):
        idx = []
        while len(idx) < n:
            s = rnd.randrange(n - block + 1)
            idx += range(s, s + block)
        idx = idx[:n]
        d.append(sr_of([a[i] for i in idx]) - sr_of([b[i] for i in idx]))
    d.sort()
    return d[int(0.025 * B)], d[B // 2], d[int(0.975 * B)], sum(x <= 0 for x in d) / B

base = CANDS["baseline"]
for k in ("vt0.7+RP3.35 (insample)", "vt0.7+RP0 (insample)"):
    lo, mid, hi, p = boot_diff(CANDS[k], base)
    print(f"\n{k} - baseline: dSharpe 95%CI [{lo:+.4f}, {hi:+.4f}], median {mid:+.4f}, P(d<=0)={p:.2f}")
