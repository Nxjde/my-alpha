import yfinance as yf
import pandas as pd

universe = pd.read_csv("universes/sp500.csv")
symbols = universe["symbol"].tolist()

print(f"{len(symbols)}개 종목, 10년치 다운로드 시작...")
data = yf.download(symbols, start="2015-01-01", end="2026-09-11",
                    interval="1d", group_by="ticker",
                    progress=True, threads=True)

rows = []
skipped = []
for sym in symbols:
    try:
        df = data[sym].reset_index()
        df["symbol"] = sym
        df = df.rename(columns={
            "Date": "ts", "Open": "open", "High": "high",
            "Low": "low", "Close": "close", "Volume": "volume"
        })
        sub = df[["ts","symbol","open","high","low","close","volume"]].dropna()
        if len(sub) > 0:
            rows.append(sub)
        else:
            skipped.append(sym)
    except Exception:
        skipped.append(sym)

result = pd.concat(rows, ignore_index=True)
result.to_csv("data/real_prices.csv", index=False)
print(f"저장 완료: {len(result)} rows, {result['symbol'].nunique()}개 종목")
print(f"건너뜀: {len(skipped)}개")
if skipped:
    print(skipped[:20])
