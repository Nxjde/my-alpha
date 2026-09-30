import numpy as np
import pandas as pd

PX = pd.read_csv("data/real_prices.csv", usecols=["ts", "symbol", "open", "high", "low", "close", "volume"], parse_dates=["ts"])
PX = PX[PX["symbol"] != "SPY"].drop_duplicates(["ts", "symbol"], keep="last")
P = {c: PX.pivot(index="ts", columns="symbol", values=c).sort_index() for c in ["high", "low", "close", "volume"]}
CLOSE, HIGH, LOW, VOL = P["close"], P["high"], P["low"], P["volume"]

WINDOWS = {"2017-19": "2018-07-01", "2019-21": "2020-07-01", "2021-23": "2022-07-01", "2023-25": "2024-07-01"}
_CACHE = {}
def load_window(lab):
    if lab not in _CACHE:
        df = pd.read_csv(f"sweep_exports/1_1__{lab}.csv")
        _CACHE[lab] = [dict(as_of=str(r.as_of)[:10], d0=str(r.priced_from)[:10], d1=str(r.priced_to)[:10],
                            gross=float(r.gross), cost=float(r.fees) + float(r.slippage)) for r in df.itertuples()]
    return _CACHE[lab]

def sig_base(as_of):
    c = CLOSE.loc[:pd.Timestamp(as_of)]
    if len(c) < 62:
        return None
    m = (c.iloc[-1] / c.iloc[-61] - 1).dropna().nlargest(4).index
    v = (c.iloc[-1] / c.iloc[-6] - 1).dropna().nsmallest(4).index
    w = pd.Series(0.0, index=CLOSE.columns)
    w[m] += 0.125
    w[v] += 0.125
    return w[w > 0]

def sig_volspike(as_of):
    t = pd.Timestamp(as_of)
    c, v = CLOSE.loc[:t], VOL.loc[:t]
    if len(c) < 22:
        return None
    ratio = v.iloc[-1] / v.iloc[-21:-1].mean()
    ret1 = c.iloc[-1] / c.iloc[-2] - 1
    pick = ret1[(ratio >= 2) & (ret1 < 0)].dropna().nsmallest(4).index
    return pd.Series(0.25, index=pick)

def clv5(as_of):
    t = pd.Timestamp(as_of)
    h, l, c = HIGH.loc[:t].iloc[-5:], LOW.loc[:t].iloc[-5:], CLOSE.loc[:t].iloc[-5:]
    if len(c) < 5:
        return None
    rng = (h - l).where((h - l) > 0)
    s = ((2 * c - h - l) / rng).mean()
    return s[rng.notna().sum() >= 4].dropna()

def sig_clv_low(as_of):
    s = clv5(as_of)
    return None if s is None else pd.Series(0.25, index=s.nsmallest(4).index)

def sig_clv_high(as_of):
    s = clv5(as_of)
    return None if s is None else pd.Series(0.25, index=s.nlargest(4).index)

def simulate(sig):
    out = {}
    for lab, split in WINDOWS.items():
        prev, nets = pd.Series(dtype=float), []
        for r in load_window(lab):
            w = sig(r["as_of"])
            w = pd.Series(dtype=float) if (w is None or w.empty) else w
            p0, p1 = CLOSE.loc[pd.Timestamp(r["d0"]), w.index], CLOSE.loc[pd.Timestamp(r["d1"]), w.index]
            ok = p0.notna() & p1.notna() & (p0 > 0)
            gross = float((w[ok] * (p1[ok] / p0[ok] - 1)).sum())
            keys = w.index.union(prev.index)
            turn = float((w.reindex(keys).fillna(0) - prev.reindex(keys).fillna(0)).abs().sum())
            if r["as_of"] >= split:
                nets.append(gross - turn * 15 / 1e4)
            prev = w
        out[lab] = nets
    return out

BASE = {lab: [r["gross"] - r["cost"] for r in load_window(lab) if r["as_of"] >= sp] for lab, sp in WINDOWS.items()}
b_all = np.array([x for lab in WINDOWS for x in BASE[lab]])
chk = simulate(sig_base)
d = np.abs(np.array([x for lab in WINDOWS for x in chk[lab]]) - b_all)
print(f"[검증] baseline 재구성 net vs 엔진: 평균|차이|={d.mean():.6f} 최대={d.max():.6f}  (기준 1e-4)")

CANDS = {"거래량급증반전": sig_volspike, "CLV낮음(반등)": sig_clv_low, "CLV높음(지속)": sig_clv_high}
for name, sig in CANDS.items():
    res = simulate(sig)
    x = np.array([v for lab in WINDOWS for v in res[lab]])
    corr, sr = np.corrcoef(x, b_all)[0, 1], x.mean() / x.std()
    wins = [np.prod(1 + np.array(res[lab])) - 1 for lab in WINDOWS]
    ok = corr < 0.3 and sr >= 0.06 and all(w > 0 for w in wins)
    print(f"{name:<12} n={len(x)} Sharpe={sr:.4f} 상관={corr:.2f} 창별=" + "/".join(f"{w:+.0%}" for w in wins) + ("  통과" if ok else "  탈락"))

ADV = (CLOSE * VOL).rolling(20).mean()
held = []
for lab in WINDOWS:
    for r in load_window(lab):
        w = sig_base(r["as_of"])
        held += ADV.loc[:pd.Timestamp(r["as_of"])].iloc[-1].reindex(w.index).dropna().tolist()
adv = pd.Series(held)
print("\n[유동성] baseline 보유 종목의 20일 평균 거래대금(USD) 분포")
print(adv.describe(percentiles=[.01, .05, .5]).round(0).to_string())
for acct in (1e5, 1e6):
    pos = acct * 0.125
    print(f"계좌 {acct:,.0f}: 포지션 {pos:,.0f} = 거래대금의 최소 대비 {pos / adv.min():.2%}, 1% 분위 대비 {pos / adv.quantile(.01):.2%}")
