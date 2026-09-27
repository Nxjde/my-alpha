import csv, math, glob, re
from datetime import datetime

# 구간별 split 날짜 (out-of-sample 시작점)
SPLITS = {
    "2017-19": datetime(2018, 7, 1),
    "2019-21": datetime(2020, 7, 1),
    "2021-23": datetime(2022, 7, 1),
    "2023-25": datetime(2024, 7, 1),
}
RATIOS = ["1_1", "2_1", "2.5_1", "3_1", "3.5_1", "4_1"]

def load_oos_returns(ratio_tag):
    """해당 비율의 4개 구간 CSV에서 out-of-sample net 수익률만 이어붙여 반환"""
    returns = []
    for label, split_dt in SPLITS.items():
        path = f"sweep_exports/{ratio_tag}__{label}.csv"
        with open(path, newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                as_of = datetime.strptime(row["as_of"], "%Y-%m-%d %H:%M:%S")
                if as_of >= split_dt:
                    returns.append(float(row["net"]))
    return returns

def moments(returns):
    n = len(returns)
    mean = sum(returns) / n
    var = sum((r - mean) ** 2 for r in returns) / (n - 1)
    std = math.sqrt(var)
    if std == 0:
        return mean, std, 0.0, 3.0, n
    skew = (sum((r - mean) ** 3 for r in returns) / n) / (std ** 3)
    kurt = (sum((r - mean) ** 4 for r in returns) / n) / (std ** 4)  # non-excess (정규분포=3)
    return mean, std, skew, kurt, n

def norm_cdf(x):
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))

def norm_ppf(p):
    # Acklam's algorithm (표준정규분포 역함수 근사)
    if p <= 0 or p >= 1:
        raise ValueError("p must be in (0,1)")
    a = [-3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02,
         1.383577518672690e+02, -3.066479806614716e+01, 2.506628277459239e+00]
    b = [-5.447609879822406e+01, 1.615858368580409e+02, -1.556989798598866e+02,
         6.680131188771972e+01, -1.328068155288572e+01]
    c = [-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e+00,
         -2.549732539343734e+00, 4.374664141464968e+00, 2.938163982698783e+00]
    d = [7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e+00,
         3.754408661907416e+00]
    p_low = 0.02425
    p_high = 1 - p_low
    if p < p_low:
        q = math.sqrt(-2 * math.log(p))
        return (((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / \
               ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)
    elif p <= p_high:
        q = p - 0.5
        r = q * q
        return (((((a[0]*r+a[1])*r+a[2])*r+a[3])*r+a[4])*r+a[5])*q / \
               (((((b[0]*r+b[1])*r+b[2])*r+b[3])*r+b[4])*r+1)
    else:
        q = math.sqrt(-2 * math.log(1 - p))
        return -(((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / \
               ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)

# 1) 각 비율의 out-of-sample Sharpe 및 통계량 계산
stats = {}
for tag in RATIOS:
    rets = load_oos_returns(tag)
    mean, std, skew, kurt, n = moments(rets)
    sharpe = mean / std if std > 0 else 0.0
    stats[tag] = {"mean": mean, "std": std, "skew": skew, "kurt": kurt, "n": n, "sharpe": sharpe}

# 2) 6개 trial의 Sharpe 분산 (선택편향 보정을 위한 V[SR])
sharpes = [stats[t]["sharpe"] for t in RATIOS]
M = len(sharpes)
mean_sr = sum(sharpes) / M
var_sr = sum((s - mean_sr) ** 2 for s in sharpes) / (M - 1)

gamma = 0.5772156649  # Euler-Mascheroni constant
e = math.e
SR0 = math.sqrt(var_sr) * (
    (1 - gamma) * norm_ppf(1 - 1.0 / M) + gamma * norm_ppf(1 - 1.0 / (M * e))
)

# 3) 각 비율의 DSR (Deflated Sharpe Ratio) 계산
print(f"{'ratio':<8} {'N':>5} {'Sharpe':>9} {'skew':>8} {'kurt':>8} {'sigma_SR':>10} {'DSR':>8}")
for tag in RATIOS:
    s = stats[tag]
    sr, n, skew, kurt = s["sharpe"], s["n"], s["skew"], s["kurt"]
    sigma_sr = math.sqrt(max((1 - skew*sr + (kurt-1)/4 * sr**2) / (n - 1), 1e-12))
    dsr = norm_cdf((sr - SR0) / sigma_sr)
    print(f"{tag:<8} {n:>5} {sr:>9.4f} {skew:>8.3f} {kurt:>8.3f} {sigma_sr:>10.4f} {dsr:>8.4f}")

print(f"\n예상 최대 Sharpe (선택편향, {M}개 trial 기준): {SR0:.4f}")
print("DSR은 '선택편향을 감안했을 때, 진짜 Sharpe > 0일 확률'입니다. 관례적으로 0.95 이상이면 유의합니다.")
