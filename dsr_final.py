import math, statistics
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
    return N.cdf((sr - sr0) / sig)

C = {"baseline": baseline()[3],
     "vt insample": evaluate(0.7, 0.0335, "insample")[3],
     "vt global": evaluate(0.7, 0.0335, "global")[3]}

print("M=115, sd_SR=0.0185:")
for k, r in C.items():
    print(f"  {k:<12} DSR={dsr(r, 115, 0.0185):.3f}")

print("\nDSR>=0.95를 유지하는 최대 sd_SR (M=115):")
for k, r in C.items():
    lo, hi = 0.0, 0.1
    for _ in range(40):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if dsr(r, 115, mid) >= 0.95 else (lo, mid)
    print(f"  {k:<12} sd_SR <= {lo:.4f}")
