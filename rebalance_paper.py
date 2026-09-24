"""
qanat의 momentum + reversal(1:1) 최신 weights를 읽어서, KIS 모의투자 계좌를
그 목표 비중에 맞게 리밸런싱한다.

사용법:
    python3.11 rebalance_paper.py --dry-run     # 주문 미리보기만, 실제 주문 안 넣음
    python3.11 rebalance_paper.py --live        # 실제로 모의투자 계좌에 주문 넣음

기본은 항상 dry-run이다. --live를 명시해야 실제 주문이 나간다.

전제:
- qanat.yaml의 store 경로(기본 data/qanat.duckdb)에 weights__momentum, weights__reversal
  테이블이 있다고 가정 (project: equity, allocation momentum=1,reversal=1과 동일한 조합 로직 사용)
- 정수 주(whole share) 단위로만 매매 (소수점 주문 미지원 가정)
- 지정가 주문만 사용 (모의투자는 시장가가 막혀있는 경우가 많음)
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import duckdb
import pandas as pd

import kis_client

STORE_PATH = Path(__file__).parent / "data" / "qanat.duckdb"
LOG_PATH = Path(__file__).parent / "logs" / "paper_rebalance.jsonl"
ALLOCATION = {"momentum": 0.5, "reversal": 0.5}  # --allocation momentum=1,reversal=1 과 동일
MIN_TRADE_USD = 5.0  # 이 금액보다 작은 리밸런싱은 수수료 대비 의미 없어서 건너뜀


def latest_weights(table: str) -> pd.Series:
    """weights__<table>에서 가장 최근 as_of 날짜의 symbol -> weight를 읽어온다."""
    con = duckdb.connect(str(STORE_PATH), read_only=True)
    try:
        df = con.execute(
            f"""
            SELECT symbol, weight FROM weights__{table}
            WHERE as_of = (SELECT max(as_of) FROM weights__{table})
            """
        ).fetchdf()
    finally:
        con.close()
    if df.empty:
        print(f"경고: weights__{table}에 데이터가 없음", file=sys.stderr)
        return pd.Series(dtype=float)
    return df.set_index("symbol")["weight"]


def combine(books: dict[str, pd.Series], share: dict[str, float]) -> pd.Series:
    """qanat.backtest.combine()과 동일한 로직: 비중대로 섞고 절대값 합이 1이 되게 재정규화."""
    total = pd.Series(dtype=float)
    for name, w in books.items():
        if w.empty:
            continue
        total = total.add(w * share.get(name, 0.0), fill_value=0.0)
    total = total[total != 0]
    scale = total.abs().sum()
    return total / scale if scale > 0 else total


def build_orders(target_weights: pd.Series, equity: float, holdings: dict) -> list[dict]:
    """목표 비중과 현재 잔고를 비교해서 (symbol, side, qty, exchange, price) 주문 리스트 생성."""
    orders = []

    all_symbols = set(target_weights.index) | set(holdings.keys())
    for symbol in sorted(all_symbols):
        target_w = float(target_weights.get(symbol, 0.0))
        current_qty = float(holdings.get(symbol, 0.0))

        try:
            quote_exch, price, order_exch = kis_client.resolve_exchange(symbol)
        except RuntimeError as e:
            print(f"건너뜀: {e}", file=sys.stderr)
            continue

        target_qty = int((target_w * equity) // price)  # 정수 주 단위, 내림
        diff_qty = target_qty - int(current_qty)
        diff_usd = abs(diff_qty) * price

        if diff_qty == 0 or diff_usd < MIN_TRADE_USD:
            continue

        side = "buy" if diff_qty > 0 else "sell"
        # 체결 확률 높이려고 지정가를 현재가에서 살짝 유리하게(매수는 위로, 매도는 아래로)
        limit_price = price * 1.005 if side == "buy" else price * 0.995

        orders.append(
            {
                "symbol": symbol,
                "side": side,
                "qty": abs(diff_qty),
                "exchange": order_exch,
                "price": round(limit_price, 2),
                "target_weight": round(target_w, 4),
                "target_qty": target_qty,
                "current_qty": int(current_qty),
            }
        )
    return orders


def main():
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--dry-run", action="store_true", help="주문 미리보기만")
    group.add_argument("--live", action="store_true", help="실제로 모의투자에 주문 제출")
    args = parser.parse_args()

    momentum_w = latest_weights("momentum")
    reversal_w = latest_weights("reversal")
    target = combine({"momentum": momentum_w, "reversal": reversal_w}, ALLOCATION)

    if target.empty:
        print("목표 비중이 비어있음 - 중단", file=sys.stderr)
        sys.exit(1)

    print(f"목표 포트폴리오 ({len(target)}개 종목):")
    for symbol, w in target.sort_values(ascending=False).items():
        print(f"  {symbol:6s} {w:+.4f}")

    holdings = kis_client.get_overseas_holdings()
    cash_usd = kis_client.get_cash_usd()

    holdings_value = 0.0
    for symbol, qty in holdings.items():
        try:
            _, price, _ = kis_client.resolve_exchange(symbol)
            holdings_value += qty * price
        except RuntimeError as e:
            print(f"경고: 보유종목 {symbol} 시가평가 실패, 총자산 계산에서 제외: {e}", file=sys.stderr)

    equity = cash_usd + holdings_value
    print(f"\n현재 예수금(USD): {cash_usd:,.2f}")
    print(f"현재 보유종목 평가액(USD): {holdings_value:,.2f}")
    print(f"총자산(USD): {equity:,.2f}")
    print(f"현재 보유: {holdings}")

    orders = build_orders(target, equity, holdings)

    if not orders:
        print("\n리밸런싱 불필요 (변동 없음 또는 전부 최소거래금액 미만)")
        return

    print(f"\n주문 {len(orders)}건:")
    for o in orders:
        print(
            f"  {o['side']:4s} {o['symbol']:6s} {o['qty']:4d}주 @ {o['price']:.2f} "
            f"(목표 {o['target_qty']}주, 현재 {o['current_qty']}주)"
        )

    if args.live:
        print("\n--live 모드: 실제 주문 제출 중...")
        for o in orders:
            try:
                kis_client.place_overseas_order(
                    o["symbol"], o["qty"], o["side"], o["price"], o["exchange"]
                )
                status = "ok"
                print(f"  {o['symbol']} {o['side']} 주문 완료")
            except Exception as e:  # 개별 주문 실패가 나머지 주문까지 막지 않도록
                status = f"error: {e}"
                print(f"  {o['symbol']} {o['side']} 주문 실패: {e}", file=sys.stderr)
            _append_log({**o, "status": status}, mode="live", equity=equity)
    else:
        print("\n--dry-run 모드: 실제 주문은 넣지 않았습니다. 실제 실행하려면 --live로 재실행하세요.")
        for o in orders:
            _append_log({**o, "status": "dry-run"}, mode="dry-run", equity=equity)


def _append_log(order_entry: dict, mode: str, equity: float) -> None:
    LOG_PATH.parent.mkdir(exist_ok=True)
    with open(LOG_PATH, "a") as f:
        f.write(
            json.dumps(
                {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "mode": mode,
                    "equity_usd": equity,
                    "order": order_entry,
                }
            )
            + "\n"
        )


if __name__ == "__main__":
    main()
