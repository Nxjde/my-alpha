import io, contextlib, json, math, statistics
from statistics import NormalDist
with contextlib.redirect_stdout(io.StringIO()):
    from db_sr import G, out
N = NormalDist()

KEY = ("alpha_momentum+alpha_reversal", "5d", json.dumps({"momentum": 0.5, "reversal": 0.5}, sort_keys=True))
folds = G[KEY]
BASE = [r for sp in sorted(folds) for r in folds[sp]]

def dsr(r, M, sd_sr):
    n, mu, sd = len(r), statistics.mean(r), statistics.stdev(r)
    sr = mu / sd
    sk = sum((x - mu) ** 3 for x in r) / n / sd ** 3
    ku = sum((x - mu) ** 4 for x in r) / n / sd ** 4
    g = 0.5772156649
    sr0 = sd_sr * ((1 - g) * N.inv_cdf(1 - 1 / M) + g * N.inv_cdf(1 - 1 / (M * math.e)))
    sig = math.sqrt(max((1 - sk * sr + (ku - 1) / 4 * sr ** 2) / (n - 1), 1e-12))
    return N.cdf((sr - sr0) / sig)

ALL = [o[0] for o in out]
FIVE = [o[0] for o in out if o[2] == "5d"]
NOISE = 1 / math.sqrt(len(BASE) - 1)

SUBS = {"전체 21개": ALL, "5일 주기만": FIVE}
print(f"baseline(1:1) n={len(BASE)}  Sharpe={statistics.mean(BASE)/statistics.stdev(BASE):.4f}\n")
print(f"{'sd_SR 기준':<16}{'후보수':>6}{'sd_SR':>8}{'DSR(M=후보수)':>15}{'DSR(M=115)':>12}")
for name, v in SUBS.items():
    s = statistics.stdev(v)
    print(f"{name:<16}{len(v):>6}{s:>8.4f}{dsr(BASE, len(v), s):>15.3f}{dsr(BASE, 115, s):>12.3f}")
print(f"{'귀무 노이즈 1/sqrt(n)':<16}{'-':>6}{NOISE:>8.4f}{dsr(BASE, 21, NOISE):>15.3f}{dsr(BASE, 115, NOISE):>12.3f}")
