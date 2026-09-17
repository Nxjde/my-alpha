"""Short-term reversal: buy what just fell

Momentum's mirror over a few days rather than a few months. It trades far more
often, which is exactly why it is worth running against fees.

Wired by `qanat alphas add reversal`. It is an ordinary step -- edit it, or throw it
away and write your own. That is the point of having it.
"""

import pandas as pd


def run(ctx):
    o = ctx.options
    sym, date, px = o.get("symbol_column", "symbol"), o.get("date_column", "date"), \
        o.get("price_column", "close")
    lookback, top_n = int(o.get("lookback", 5)), int(o.get("top_n", 4))

    bars = ctx.read(o["reads"]).sort_values(date)
    allowed = set(ctx.universe()["symbol"])
    bars = bars[bars[sym].isin(allowed)]

    rows = []
    for name, g in bars.groupby(sym):
        if len(g) <= lookback:
            continue
        past, now = g[px].iloc[-lookback - 1], g[px].iloc[-1]
        if past and past > 0:
            rows.append({"symbol": name, "score": now / past - 1.0, "as_of": g[date].iloc[-1]})
    if len(rows) < top_n:
        return pd.DataFrame(columns=["symbol", "weight", "score", "as_of"])

    # buy what just fell: the short-horizon mirror of momentum
    picked = pd.DataFrame(rows).nsmallest(top_n, "score")
    picked["weight"] = 1.0 / len(picked)
    return picked[["symbol", "weight", "score", "as_of"]].reset_index(drop=True)
