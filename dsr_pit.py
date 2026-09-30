import json, math, random, statistics
from statistics import NormalDist
N = NormalDist()
S = json.load(open("pit_series.json"))

def dsr(r, M, sd_sr):
    n, mu, sd = len(r), statistics.mean(r), statistics.stdev(r)
    sr = mu / sd
    sk = sum((x - mu) ** 3 for x in r) / n / sd ** 3
    ku = sum((x - mu) ** 4 for x in r) / n / sd ** 4
    g = 0.5772156649
    sr0 = 0.0 if M == 1 else sd_sr * ((1 - g) * N.inv_cdf(1 - 1 / M) + g * N.inv_cdf(1 - 1 / (M * math.e)))
    sig = math.sqrt(max((1 - sk * sr + (ku - 1) / 4 * sr ** 2) / (n - 1), 1e-12))
    return N.cdf((sr - sr0) / sig)

for name in ("base_nofilter", "base_pit", "mom_pit", "rev_pit"):
    r = S[name]
    print(f"\n[{name}] 확률(SR>0, 시도 보정 없음) = {dsr(r, 1, 0):.3f}")
    print("sd_SR \\ M   " + "".join(f"{m:>8}" for m in (21, 60, 115)))
    for s in (0.02, 0.043, 0.06):
        print(f"{s:<12}" + "".join(f"{dsr(r, m, s):>8.3f}" for m in (21, 60, 115)))

def sr_of(x):
    return statistics.mean(x) / statistics.pstdev(x)

def boot(a, b, block=10, B=2000, seed=0):
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

print()
for label, a, b in [("필터 없음 - 필터 baseline (편향 효과)", "base_nofilter", "base_pit"),
                    ("블렌드 - momentum (필터)", "base_pit", "mom_pit"),
                    ("블렌드 - reversal (필터)", "base_pit", "rev_pit")]:
    lo, mid, hi, p = boot(S[a], S[b])
    print(f"{label:<28} dSharpe 95%CI [{lo:+.4f}, {hi:+.4f}] 중앙 {mid:+.4f} P(d<=0)={p:.2f}")
