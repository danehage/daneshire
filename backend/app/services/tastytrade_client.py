"""
Tastytrade API client — async, with session-token caching and 401-driven re-exchange.

Auth model (per #15 Agent Brief): the developer API uses a session-token
model, not OAuth. The client holds a long-lived ``remember-token``
provisioned via a one-time manual login (out of scope here) and exchanges
it for a short-lived ``session-token`` on first use. On HTTP 401 from a
data endpoint, the client transparently re-exchanges and retries once.

Surface used by :class:`MarketData`:
- :meth:`get_iv_snapshot(ticker)` — returns :class:`IVSnapshotRaw`
- :meth:`get_options_chain(ticker, expiry)` — returns raw chain rows

Expected-move math (per ADR-0003) lives here so the seam only sees an
already-computed :class:`IVSnapshotRaw`. The endpoint URL shapes mirror
the public tastytrade developer docs and are isolated as class constants
so they can be retargeted when a live remember-token is provisioned.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional

import httpx

from app.config import settings
from app.schemas.iv import IVSnapshotRaw

logger = logging.getLogger(__name__)


_REQUEST_TIMEOUT = 15.0
# How stale a chain quote may be before we refuse to mid-mark it (ADR-0003).
_MAX_CHAIN_AGE_SECONDS = 10 * 60


class TastytradeError(Exception):
    """Base for all TastytradeClient failures.

    Distinct from :class:`MarketDataError` — the seam translates these
    into the seam's own error hierarchy (`OptionsDataUnavailable` etc.).
    """


class TastytradeAuthError(TastytradeError):
    """Session-token exchange failed (bad / revoked remember-token)."""


class TastytradeUnavailable(TastytradeError):
    """No usable options data for this ticker (no chain, no quotes, stale)."""


class TastytradeClient:
    """Async tastytrade client with session-token caching and 401 retry."""

    BASE_URL = "https://api.tastytrade.com"
    SESSIONS_PATH = "/sessions"
    CHAIN_QUOTES_PATH = "/option-chains/{symbol}/quotes"
    QUOTE_PATH = "/market-data/{symbol}"

    def __init__(
        self,
        remember_token: Optional[str] = None,
        *,
        http_client: Optional[httpx.AsyncClient] = None,
    ):
        self._remember_token = remember_token or settings.tastytrade_remember_token
        if not self._remember_token:
            raise ValueError(
                "TASTYTRADE_REMEMBER_TOKEN is not set. "
                "Provision one via the manual login script and add it to .env."
            )
        # If a client is injected (tests), reuse it; otherwise own a private one.
        self._http = http_client
        self._owns_http = http_client is None
        self._session_token: Optional[str] = None
        self._session_lock = asyncio.Lock()

    # ------------------------------------------------------------------
    # Auth
    # ------------------------------------------------------------------

    async def _http_client(self) -> httpx.AsyncClient:
        if self._http is None:
            self._http = httpx.AsyncClient(base_url=self.BASE_URL, timeout=_REQUEST_TIMEOUT)
        return self._http

    async def _ensure_session(self, *, force: bool = False) -> str:
        async with self._session_lock:
            if self._session_token and not force:
                return self._session_token
            client = await self._http_client()
            try:
                resp = await client.post(
                    self.SESSIONS_PATH,
                    json={"login": "", "remember-token": self._remember_token},
                )
            except httpx.RequestError as exc:
                raise TastytradeAuthError(f"network error during session exchange: {exc}") from exc
            if resp.status_code != 201 and resp.status_code != 200:
                raise TastytradeAuthError(
                    f"session exchange returned HTTP {resp.status_code}: {resp.text[:200]}"
                )
            payload = resp.json() or {}
            data = payload.get("data") or payload
            token = data.get("session-token") or data.get("sessionToken")
            if not token:
                raise TastytradeAuthError("session exchange response missing session-token")
            self._session_token = token
            return token

    async def _authed_get(self, path: str, params: Optional[dict] = None) -> dict:
        """GET with session-token; one transparent re-exchange on 401."""
        client = await self._http_client()
        token = await self._ensure_session()
        for attempt in range(2):
            try:
                resp = await client.get(
                    path, params=params, headers={"Authorization": token}
                )
            except httpx.RequestError as exc:
                raise TastytradeUnavailable(f"network error on {path}: {exc}") from exc
            if resp.status_code == 401 and attempt == 0:
                logger.info("tastytrade 401 on %s — re-exchanging session", path)
                token = await self._ensure_session(force=True)
                continue
            if resp.status_code == 404:
                raise TastytradeUnavailable(f"no data for {path}")
            if resp.status_code != 200:
                raise TastytradeUnavailable(
                    f"HTTP {resp.status_code} on {path}: {resp.text[:200]}"
                )
            return resp.json() or {}
        # Should be unreachable — second 401 falls through above.
        raise TastytradeUnavailable(f"unauthenticated after retry on {path}")

    async def aclose(self) -> None:
        if self._http is not None and self._owns_http:
            await self._http.aclose()

    # ------------------------------------------------------------------
    # Data
    # ------------------------------------------------------------------

    async def get_options_chain(self, ticker: str, expiry: date) -> list[dict]:
        """Return raw option-chain rows for ``ticker`` at ``expiry``.

        Each row is the provider's quote dict (strike, type, bid, ask,
        last, updated-at, ...). Empty list if the chain does not exist
        for that expiry (the chain is published but holds no rows for
        the date).
        """
        path = self.CHAIN_QUOTES_PATH.format(symbol=ticker.upper())
        payload = await self._authed_get(path, params={"expiration": expiry.isoformat()})
        # Tastytrade wraps list results in {"data": {"items": [...]}}.
        data = payload.get("data") or {}
        return list(data.get("items") or [])

    async def get_iv_snapshot(self, ticker: str) -> IVSnapshotRaw:
        """Build today's snapshot for ``ticker`` from a fresh chain pull.

        Raises :class:`TastytradeUnavailable` if the chain is missing,
        the underlying quote is missing, or no usable straddle can be
        priced. Per ADR-0003, snapshots without an expected move must
        not be written, so callers should treat this as a hard skip.
        """
        symbol = ticker.upper()

        # 1. Front-week expiry: pick the earliest published weekly that
        # strictly follows today. The chain endpoint with no expiry
        # returns the full chain; tastytrade exposes a separate metadata
        # endpoint, but the chain payload also carries expirations.
        underlying_quote = await self._fetch_underlying_quote(symbol)
        front_expiry = await self._fetch_front_expiry(symbol)
        chain = await self.get_options_chain(symbol, front_expiry)
        if not chain:
            raise TastytradeUnavailable(f"chain empty for {symbol} @ {front_expiry}")

        atm = _pick_atm_strike(chain, underlying_quote.price)
        if atm is None:
            raise TastytradeUnavailable(f"no ATM strike found for {symbol} @ {front_expiry}")
        call_mid = _quote_mid_or_last(atm.call)
        put_mid = _quote_mid_or_last(atm.put)
        if call_mid is None or put_mid is None:
            raise TastytradeUnavailable(
                f"stale or zero straddle quotes for {symbol} @ {front_expiry}"
            )
        expected_move_pct = (Decimal(call_mid) + Decimal(put_mid)) / Decimal(underlying_quote.price)

        return IVSnapshotRaw(
            ticker=symbol,
            iv30=Decimal(str(underlying_quote.iv30)),
            iv_rank_provider=Decimal(str(underlying_quote.iv_rank_provider)),
            expected_move_pct=expected_move_pct,
        )

    # ------------------------------------------------------------------
    # Underlying / expiry helpers
    # ------------------------------------------------------------------

    async def _fetch_underlying_quote(self, symbol: str) -> "_UnderlyingQuote":
        payload = await self._authed_get(self.QUOTE_PATH.format(symbol=symbol))
        data = payload.get("data") or payload
        try:
            price = float(data["last"]) if data.get("last") is not None else float(data["mid"])
            iv30 = float(data["implied-volatility-30d"])
            iv_rank = float(data["implied-volatility-rank"])
        except (KeyError, TypeError, ValueError) as exc:
            raise TastytradeUnavailable(
                f"underlying quote missing required fields for {symbol}: {exc}"
            ) from exc
        return _UnderlyingQuote(price=price, iv30=iv30, iv_rank_provider=iv_rank)

    async def _fetch_front_expiry(self, symbol: str) -> date:
        payload = await self._authed_get(
            f"/option-chains/{symbol}/nested",
        )
        data = payload.get("data") or {}
        items = data.get("items") or []
        if not items:
            raise TastytradeUnavailable(f"no expirations published for {symbol}")
        # `items` is a list of {"expiration-date": "YYYY-MM-DD", ...} sorted ascending.
        today = date.today()
        for item in items:
            exp_str = item.get("expiration-date")
            if not exp_str:
                continue
            try:
                exp = date.fromisoformat(exp_str)
            except ValueError:
                continue
            if exp > today:
                return exp
        raise TastytradeUnavailable(f"no future expirations for {symbol}")


# ---------------------------------------------------------------------------
# Internal helpers — pure functions, no I/O. Tested directly.
# ---------------------------------------------------------------------------


from dataclasses import dataclass


@dataclass(frozen=True)
class _UnderlyingQuote:
    price: float
    iv30: float
    iv_rank_provider: float


@dataclass(frozen=True)
class _Straddle:
    strike: float
    call: dict
    put: dict


def _pick_atm_strike(chain: list[dict], underlying_price: float) -> Optional[_Straddle]:
    """Find the strike nearest ``underlying_price`` that has both legs.

    ADR-0003 tie-break: when two strikes are equidistant, prefer the
    lower strike.
    """
    by_strike: dict[float, dict[str, dict]] = {}
    for row in chain:
        try:
            strike = float(row.get("strike-price"))
        except (TypeError, ValueError):
            continue
        side = (row.get("option-type") or "").lower()
        if side not in ("call", "put"):
            continue
        by_strike.setdefault(strike, {})[side] = row

    candidates = [
        (strike, legs)
        for strike, legs in by_strike.items()
        if "call" in legs and "put" in legs
    ]
    if not candidates:
        return None
    # Sort by (abs distance asc, strike asc) so ties resolve toward the
    # lower strike per ADR-0003.
    candidates.sort(key=lambda c: (abs(c[0] - underlying_price), c[0]))
    strike, legs = candidates[0]
    return _Straddle(strike=strike, call=legs["call"], put=legs["put"])


def _quote_mid_or_last(row: dict) -> Optional[float]:
    """Mid `(bid+ask)/2` if both positive; else `last` if positive and
    fresh; else ``None`` (per ADR-0003).
    """
    try:
        bid = float(row.get("bid") or 0)
        ask = float(row.get("ask") or 0)
    except (TypeError, ValueError):
        bid = ask = 0.0
    if bid > 0 and ask > 0:
        return (bid + ask) / 2.0
    # Fall back to last, but only if positive and not stale.
    try:
        last = float(row.get("last") or 0)
    except (TypeError, ValueError):
        return None
    if last <= 0:
        return None
    updated_at = row.get("updated-at")
    if updated_at:
        ts = _parse_iso(updated_at)
        if ts is not None and (datetime.now(timezone.utc) - ts).total_seconds() > _MAX_CHAIN_AGE_SECONDS:
            return None
    return last


def _parse_iso(value: str) -> Optional[datetime]:
    try:
        # Tastytrade emits e.g. "2026-05-26T14:32:00.000+00:00"; Python's
        # fromisoformat handles offset-aware strings on 3.11+.
        return datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return None
