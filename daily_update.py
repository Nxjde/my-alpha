"""
daily_update.py — real_prices.csv에 최근 종가를 안전하게 append.

기존 fetch_prices.py처럼 전체를 다시 받아 덮어쓰지 않고, 최근 N일치만 받아서
날짜가 이미 있는 행은 건너뛰고 없는 행만 추가한다. 컬럼 순서/이름을 항상
정확히 7개(ts,symbol,open,high,low,close,volume)로 강제해서, 예전에 SPY만
따로 받다가 스키마가 깨졌던 것과 같은 사고를 방지한다.
"""
import yfinance as yf
import pandas as pd
from pathlib import Path

CSV_PATH = Path("data/real_prices.csv")
UNIVERSE_PATH = Path("universes/sp500.csv")
LOOKBACK_DAYS = "10d"  # 매일 도니까 며칠 여유 있게 겹쳐 받아서 휴장일/누락 방지
EXPECTED_COLUMNS = ["ts", "symbol", "open", "high", "low", "close", "volume"]


def load_existing():
    if not CSV_PATH.exists():
        return pd.DataFrame(columns=EXPECTED_COLUMNS)
    df = pd.read_csv(CSV_PATH)
    # 스키마 강제: 예전 손상 행(컬럼 수 다른 것) 있으면 여기서 걸러냄
    df = df[EXPECTED_COLUMNS] if set(EXPECTED_COLUMNS).issubset(df.columns) else df.iloc[:, :7]
    df.columns = EXPECTED_COLUMNS
    df = df.dropna(subset=["ts", "symbol"])
    df = df[(df["ts"] != "") & (df["symbol"] != "")]
    return df


def fetch_recent(symbols):
    data = yf.download(symbols, period=LOOKBACK_DAYS, interval="1d",
                        group_by="ticker", progress=False, threads=True)
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
            sub = df[EXPECTED_COLUMNS].dropna()
            if len(sub):
                rows.append(sub)
            else:
                skipped.append(sym)
        except Exception:
            skipped.append(sym)
    if not rows:
        raise RuntimeError("아무 종목도 못 받아왔습니다 — yfinance 응답 확인 필요")
    fresh = pd.concat(rows, ignore_index=True)
    fresh["ts"] = pd.to_datetime(fresh["ts"]).dt.strftime("%Y-%m-%d")
    return fresh, skipped


def main():
    universe = pd.read_csv(UNIVERSE_PATH)
    symbols = universe["symbol"].tolist()

    existing = load_existing()
    print(f"기존 데이터: {len(existing)}행, {existing['symbol'].nunique()}개 종목, "
          f"마지막 날짜 {existing['ts'].max() if len(existing) else '(없음)'}")

    fresh, skipped = fetch_recent(symbols)
    print(f"새로 받은 데이터: {len(fresh)}행 ({fresh['ts'].min()}~{fresh['ts'].max()}), "
          f"건너뜀 {len(skipped)}개")

    combined = pd.concat([existing, fresh], ignore_index=True)
    before = len(combined)
    combined = combined.drop_duplicates(subset=["ts", "symbol"], keep="last")
    combined = combined.sort_values(["symbol", "ts"])
    print(f"중복 제거: {before}행 -> {len(combined)}행")

    combined.to_csv(CSV_PATH, index=False, columns=EXPECTED_COLUMNS)
    print(f"저장 완료: {CSV_PATH}, 최종 마지막 날짜 {combined['ts'].max()}")


if __name__ == "__main__":
    main()
