import numpy as np
import pandas as pd

raw = pd.read_csv("universes/sp500_raw.csv")
ADDED = pd.to_datetime(raw["Date added"], errors="coerce")
ADDED.index = raw["Symbol"].str.replace(".", "-", regex=False)

PX = pd.read_csv("data/real_prices.csv", usecols=["ts", "symbol", "close"], parse_dates=["ts"])
PX = PX[PX["symbol"] != "SPY"].drop_duplicates(["ts", "symbol"], keep="last")
C = PX.pivot(index="ts", columns="symbol", values="close").sort_index()
ADD_C = ADDED.reindex(C.columns)
WINDOWS = {"2017-19": "2018-07-01", "2019-21": "2020-07-01", "2021-23": "2022-07-01", "2023-25": "2024-07-01"}

_P = {}
def picks(as_of, use_filter):
    k = (as_of, use_filter)
    if k in _P:
        return _P[k]
    t = pd.Timestamp(as_of)
    c = C.loc[:t]
    if len(c) < 62:
        _P[k] = ([], [])
        return _P[k]
    if use_filter:
        c = c.loc[:, (ADD_C.isna() | (ADD_C <= t)).values]
    m = (c.iloc[-1] / c.iloc[-61] - 1).dropna().nlargest(4).index
    v = (c.iloc[-1] / c.iloc[-6] - 1).dropna().nsmallest(4).index
    _P[k] = (list(m), list(v))
    return _P[k]

def weights(as_of, use_filter, kind):
    m, v = picks(as_of, use_filter)
    d = {}
    if kind in ("base", "mom"):
        for s in m:
            d[s] = d.get(s, 0.0) + (0.125 if kind == "base" else 0.25)
    if kind in ("base", "rev"):
        for s in v:
            d[s] = d.get(s, 0.0) + (0.125 if kind == "base" else 0.25)
    return pd.Series(d, dtype=float)

def simulate(kind, use_filter):
    res = {}
    for lab, split in WINDOWS.items():
        df = pd.read_csv(f"sweep_exports/1_1__{lab}.csv")
        prev, nets = pd.Series(dtype=float), []
        for r in df.itertuples():
            a, d0, d1 = str(r.as_of)[:10], str(r.priced_from)[:10], str(r.priced_to)[:10]
            w = weights(a, use_filter, kind)
            p0, p1 = C.loc[pd.Timestamp(d0), w.index], C.loc[pd.Timestamp(d1), w.index]
            ok = p0.notna() & p1.notna() & (p0 > 0)
            g = float((w[ok] * (p1[ok] / p0[ok] - 1)).sum())
            keys = w.index.union(prev.index)
            turn = float((w.reindex(keys).fillna(0) - prev.reindex(keys).fillna(0)).abs().sum())
            if a >= split:
                nets.append(g - turn * 15 / 1e4)
            prev = w
        res[lab] = nets
    return res
