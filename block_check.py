import pandas as pd
PX = pd.read_csv("data/real_prices.csv", usecols=["ts", "symbol", "close"], parse_dates=["ts"])
PX = PX[PX.symbol != "SPY"].drop_duplicates(["ts", "symbol"], keep="last")
C = PX.pivot(index="ts", columns="symbol", values="close").sort_index()
S = {"2017-19": "2018-07-01", "2019-21": "2020-07-01", "2021-23": "2022-07-01", "2023-25": "2024-07-01"}
ROWS = []
for lab, sp in S.items():
    df = pd.read_csv(f"sweep_exports/1_1__{lab}.csv")
    for _, r in df.iterrows():
        if str(r["as_of"])[:10] >= sp:
            ROWS.append((str(r["as_of"])[:10], str(r["priced_from"])[:10], str(r["priced_to"])[:10]))

def w_at(as_of):
    c = C.loc[:pd.Timestamp(as_of)]
    m = (c.iloc[-1] / c.iloc[-61] - 1).dropna().nlargest(4).index
    v = (c.iloc[-1] / c.iloc[-6] - 1).dropna().nsmallest(4).index
    w = pd.Series(0.0, index=C.columns)
    w[m] += 0.125
    w[v] += 0.125
    return w[w > 0]

for name, a, b in [("블록11", 270, 296), ("블록16", 405, 431)]:
    tot = pd.Series(0.0, index=C.columns)
    for as_of, d0, d1 in ROWS[a:b + 1]:
        w = w_at(as_of)
        p0, p1 = C.loc[pd.Timestamp(d0), w.index], C.loc[pd.Timestamp(d1), w.index]
        ok = p0.notna() & p1.notna() & (p0 > 0)
        tot[w.index[ok]] += (w[ok] * (p1[ok] / p0[ok] - 1)).values
    t = tot[tot != 0].sort_values(ascending=False)
    print(f"\n{name} 기여 합계 {t.sum():+.3f} (단순 합)")
    print(" 상위:", ", ".join(f"{k} {v:+.3f}" for k, v in t.head(6).items()))
    print(f" 상위 3종목 비중 {t.head(3).sum() / t.sum():.0%}")
