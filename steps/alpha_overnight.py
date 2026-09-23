"""Overnight gap: score built from yesterday's close to today's open.

This is information close-to-close momentum/reversal never sees -- it isolates
the pre-market/opening print (news, retail order flow) from the trading-session
return. The literature is mixed on sign (overnight gaps sometimes persist a few
days, sometimes revert), so direction is left as an option and decided empirically.

Wired the same way as alpha_momentum / alpha_reversal_short: an ordinary step.
"""

import pandas as pd


def run(ctx):
    o = ctx.options
    sym, date = o.get("symbol_column", "symbol"), o.get("date_column", "date")
    open_col, close_col = o.get("open_column", "open"), o.get("close_column", "close")
    top_n = int(o.get("top_n", 4))
    direction = o.get("direction", "high")  # "high": buy biggest gap-up, "low": buy biggest gap-down

    bars = ctx.read(o["reads"]).sort_values(date)
    allowed = set(ctx.universe()["symbol"])
    bars = bars[bars[sym].isin(allowed)]

    rows = []
    for name, g in bars.groupby(sym):
        if len(g) < 2:
            continue
        prev_close, today_open = g[close_col].iloc[-2], g[open_col].iloc[-1]
        if prev_close and prev_close > 0:
            rows.append({"symbol": name, "score": today_open / prev_close - 1.0,
                         "as_of": g[date].iloc[-1]})
    if len(rows) < top_n:
        return pd.DataFrame(columns=["symbol", "weight", "score", "as_of"])

    df = pd.DataFrame(rows)
    picked = df.nlargest(top_n, "score") if direction == "high" else df.nsmallest(top_n, "score")
    picked["weight"] = 1.0 / len(picked)
    return picked[["symbol", "weight", "score", "as_of"]].reset_index(drop=True)
