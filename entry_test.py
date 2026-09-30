import glob, math, random, statistics
import pandas as pd

PX = pd.read_csv("data/real_prices.csv", usecols=["ts", "symbol", "open", "close"], parse_dates=["ts"])
PX = PX[PX["symbol"] != "SPY"].drop_duplicates(["ts", "symbol"], keep="last")
CLOSE = PX.pivot(index="ts", columns="symbol", values="close").sort_index()
OPEN = PX.pivot(index="ts", columns="symbol", values="open").sort_index()

def weights_at(as_of):
    c = CLOSE.loc[:pd.Timestamp(as_of)]
    if len(c) < 62:
        return None
    mom = (c.iloc[-1] / c.iloc[-61] - 1.0).dropna()
    rev = (c.iloc[-1] / c.iloc[-6] - 1.0).dropna()
    w = pd.Series(0.0, index=CLOSE.columns)
    w[mom.nlargest(4).index] += 0.125
    w[rev.nsmallest(4).index] += 0.125
    return w[w > 0]

SPLITS = {"2017-19": "2018-07-01", "2019-21": "2020-07-01", "2021-23": "2022-07-01", "2023-25": "2024-07-01"}
ROWS = []
for label, split in SPLITS.items():
    df = pd.read_csv(f"sweep_exports/1_1__{label}.csv")
    for _, r in df.iterrows():
        as_of = str(r["as_of"])[:10]
        if as_of >= split:
            ROWS.append({"as_of": as_of, "d0": str(r["priced_from"])[:10], "d1": str(r["priced_to"])[:10],
                         "gross": float(r["gross"]), "turn": float(r["turnover"]),
                         "cost": float(r["fees"]) + float(r["slippage"])})
print("기준 행 수:", len(ROWS))

def gross_of(w, d0, d1, table):
    p0, p1 = table.loc[pd.Timestamp(d0), w.index], table.loc[pd.Timestamp(d1), w.index]
    ok = p0.notna() & p1.notna() & (p0 > 0)
    return float((w[ok] * (p1[ok] / p0[ok] - 1.0)).sum())

for r in ROWS:
    w = weights_at(r["as_of"])
    r["rc"] = gross_of(w, r["d0"], r["d1"], CLOSE)
    r["ro"] = gross_of(w, r["d0"], r["d1"], OPEN)

diff = [abs(r["rc"] - r["gross"]) for r in ROWS]
print(f"검증: 평균|차이|={statistics.mean(diff):.6f}  최대={max(diff):.6f}  "
      f"|차이|<1e-4 비율={sum(d < 1e-4 for d in diff) / len(diff):.1%}")

def sr(x):
    return statistics.mean(x) / statistics.pstdev(x)

def boot(a, b, block=10, B=2000, seed=0):
    rnd, n, d = random.Random(seed), len(a), []
    for _ in range(B):
        idx = []
        while len(idx) < n:
            s = rnd.randrange(n - block + 1)
            idx += range(s, s + block)
        idx = idx[:n]
        d.append(sr([a[i] for i in idx]) - sr([b[i] for i in idx]))
    d.sort()
    return d[int(0.025 * B)], d[B // 2], d[int(0.975 * B)], sum(x <= 0 for x in d) / B

close_net = [r["gross"] - r["cost"] for r in ROWS]
print(f"\n종가->종가(엔진) n={len(ROWS)} 평균={statistics.mean(close_net):.5f} Sharpe={sr(close_net):.4f}")
for extra in (0, 5, 10):
    open_net = [r["ro"] - r["cost"] - r["turn"] * extra / 1e4 for r in ROWS]
    lo, mid, hi, p = boot(open_net, close_net)
    print(f"시가->시가 +{extra:>2}bps  평균={statistics.mean(open_net):.5f} Sharpe={sr(open_net):.4f}  "
          f"dSharpe CI[{lo:+.4f},{hi:+.4f}] 중앙 {mid:+.4f} P(d<=0)={p:.2f}")
