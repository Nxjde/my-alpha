"""
한국투자증권 (KIS) Open API 클라이언트 - 모의투자(paper trading) 전용

필요한 환경변수:
    KIS_APPKEY          - 발급받은 App Key
    KIS_APPSECRET        - 발급받은 App Secret
    KIS_CANO             - 계좌번호 앞 8자리 (예: 50213721)
    KIS_ACNT_PRDT_CD     - 계좌번호 뒤 2자리 (예: 01)

토큰은 .kis_token_cache.json 파일에 캐싱되어 만료 전까지 재사용됩니다.
(KIS는 토큰 재발급 횟수에 제한이 있어서, 매 실행마다 새로 받으면 안 됩니다.)

모의투자 서버가 간헐적으로 500을 뱉는 게 관찰돼서, 모든 API 호출에 공통 재시도가
적용됩니다 (기본 3회, 1s/2s 대기).
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

import requests

BASE_URL = "https://openapivts.koreainvestment.com:29443"  # 모의투자 전용 도메인
TOKEN_CACHE_PATH = Path(__file__).parent / ".kis_token_cache.json"
MAX_RETRIES = 3

APPKEY = os.environ["KIS_APPKEY"]
APPSECRET = os.environ["KIS_APPSECRET"]
CANO = os.environ["KIS_CANO"]
ACNT_PRDT_CD = os.environ["KIS_ACNT_PRDT_CD"]


class KisApiError(RuntimeError):
    pass


def _request_with_retry(method: str, url: str, **kwargs) -> dict:
    """GET/POST 공통 재시도 래퍼. HTTP 오류든 rt_cd != '0'이든 재시도하고,
    최종 실패하면 KisApiError로 통일해서 던진다."""
    last_exc: Exception | None = None
    for attempt in range(MAX_RETRIES):
        try:
            resp = requests.request(method, url, timeout=10, **kwargs)
            resp.raise_for_status()
            data = resp.json()
            if data.get("rt_cd") not in ("0", None):
                raise KisApiError(data.get("msg1") or f"rt_cd={data.get('rt_cd')}")
            return data
        except (requests.HTTPError, requests.ConnectionError, requests.Timeout, KisApiError) as e:
            last_exc = e
            if attempt < MAX_RETRIES - 1:
                time.sleep(2**attempt)  # 1s, 2s
                continue
    raise KisApiError(f"{method} {url} 최종 실패 ({MAX_RETRIES}회 재시도): {last_exc}")


def _load_cached_token() -> str | None:
    if not TOKEN_CACHE_PATH.exists():
        return None
    try:
        data = json.loads(TOKEN_CACHE_PATH.read_text())
    except (json.JSONDecodeError, OSError):
        return None
    # 만료 10분 전에는 미리 재발급 (경계에서 401 나는 것 방지)
    if data.get("expires_at", 0) > time.time() + 600:
        return data["access_token"]
    return None


def get_token(force: bool = False) -> str:
    """캐시된 토큰이 유효하면 그대로 쓰고, 아니면 새로 발급받아 캐싱."""
    if not force:
        cached = _load_cached_token()
        if cached:
            return cached

    data = _request_with_retry(
        "POST",
        f"{BASE_URL}/oauth2/tokenP",
        headers={"content-type": "application/json"},
        json={"grant_type": "client_credentials", "appkey": APPKEY, "appsecret": APPSECRET},
    )
    expires_at = time.time() + int(data.get("expires_in", 86400))
    TOKEN_CACHE_PATH.write_text(
        json.dumps({"access_token": data["access_token"], "expires_at": expires_at})
    )
    TOKEN_CACHE_PATH.chmod(0o600)  # 토큰 파일 권한 제한
    return data["access_token"]


def _headers(tr_id: str) -> dict:
    return {
        "content-type": "application/json; charset=utf-8",
        "authorization": f"Bearer {get_token()}",
        "appkey": APPKEY,
        "appsecret": APPSECRET,
        "tr_id": tr_id,
    }


def get_overseas_holdings() -> dict:
    """해외주식 보유종목만 반환. {symbol: qty, ...}"""
    data = _request_with_retry(
        "GET",
        f"{BASE_URL}/uapi/overseas-stock/v1/trading/inquire-balance",
        headers=_headers("VTTS3012R"),
        params={
            "CANO": CANO,
            "ACNT_PRDT_CD": ACNT_PRDT_CD,
            "OVRS_EXCG_CD": "NASD",
            "TR_CRCY_CD": "USD",
            "CTX_AREA_FK200": "",
            "CTX_AREA_NK200": "",
        },
    )
    holdings = {}
    for row in data.get("output1", []):
        symbol = row.get("ovrs_pdno")
        qty = float(row.get("ovrs_cblc_qty", 0) or 0)
        if symbol and qty > 0:
            holdings[symbol] = qty
    return holdings


def get_cash_usd() -> float:
    """매수가능 USD 현금(예수금). inquire-psamount의 ord_psbl_frcr_amt 필드.
    특정 종목 기준으로 계산되는 API지만, 현금계좌라 이 필드는 종목과 무관하게
    총 예수금과 같다 (모의투자 초기 지급금 $100,000 확인됨)."""
    data = _request_with_retry(
        "GET",
        f"{BASE_URL}/uapi/overseas-stock/v1/trading/inquire-psamount",
        headers=_headers("VTTS3007R"),
        params={
            "CANO": CANO,
            "ACNT_PRDT_CD": ACNT_PRDT_CD,
            "OVRS_EXCG_CD": "NASD",
            "OVRS_ORD_UNPR": "200",
            "ITEM_CD": "AAPL",
        },
    )
    return float(data["output"]["ord_psbl_frcr_amt"])


def get_overseas_price(symbol: str, exchange: str = "NAS") -> float:
    """해외주식 현재가 조회. exchange는 시세조회용 코드(NAS/NYS/AMS)."""
    data = _request_with_retry(
        "GET",
        f"{BASE_URL}/uapi/overseas-price/v1/quotations/price",
        headers=_headers("HHDFS00000300"),
        params={"AUTH": "", "EXCD": exchange, "SYMB": symbol},
    )
    last = data.get("output", {}).get("last")
    if not last:
        raise KisApiError(f"{symbol}@{exchange} 시세 없음: {data.get('msg1')}")
    return float(last)


# 시세조회 코드(EXCD) -> 주문/잔고조회 코드(OVRS_EXCG_CD). S&P500엔 NASDAQ뿐 아니라
# NYSE/AMEX 종목도 섞여있어서, 하나씩 시도해보고 맞는 거래소를 찾는다.
_EXCHANGE_PAIRS = [("NAS", "NASD"), ("NYS", "NYSE"), ("AMS", "AMEX")]
_exchange_cache: dict[str, tuple[str, str]] = {}


def resolve_exchange(symbol: str) -> tuple[str, float, str]:
    """symbol이 어느 거래소 소속인지 찾아서 (quote_exch, price, order_exch) 반환.
    한 번 찾은 종목은 캐싱해서 매번 3번씩 조회하지 않도록 함."""
    if symbol in _exchange_cache:
        quote_exch, order_exch = _exchange_cache[symbol]
        return quote_exch, get_overseas_price(symbol, quote_exch), order_exch

    last_err = None
    for quote_exch, order_exch in _EXCHANGE_PAIRS:
        try:
            price = get_overseas_price(symbol, quote_exch)
            _exchange_cache[symbol] = (quote_exch, order_exch)
            return quote_exch, price, order_exch
        except KisApiError as e:
            last_err = e
            continue
    raise KisApiError(f"{symbol}의 거래소를 NAS/NYS/AMS 어디서도 못 찾음: {last_err}")


def place_overseas_order(
    symbol: str, qty: int, side: str, price: float, exchange: str = "NASD"
) -> dict:
    """해외주식 주문 (모의투자).

    side: "buy" 또는 "sell"
    price: 지정가. 모의투자는 시장가 주문이 안 되는 경우가 많아 지정가로 넣고,
           체결 확률을 높이려면 현재가에서 buy는 살짝 위, sell은 살짝 아래로 걸 것.
    """
    tr_id = "VTTT1002U" if side == "buy" else "VTTT1006U"  # 모의투자 매수/매도
    return _request_with_retry(
        "POST",
        f"{BASE_URL}/uapi/overseas-stock/v1/trading/order",
        headers=_headers(tr_id),
        json={
            "CANO": CANO,
            "ACNT_PRDT_CD": ACNT_PRDT_CD,
            "OVRS_EXCG_CD": exchange,
            "PDNO": symbol,
            "ORD_QTY": str(qty),
            "OVRS_ORD_UNPR": f"{price:.2f}",
            "ORD_SVR_DVSN_CD": "0",
            "ORD_DVSN": "00",  # 00: 지정가
        },
    )
