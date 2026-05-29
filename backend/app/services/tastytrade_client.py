"""
Tastytrade API client — async, with OAuth2 access-token caching and
proactive refresh.

Auth model: the developer API uses OAuth2. The client holds a long-lived
``refresh_token`` (provisioned once via "Create Grant" in the tastytrade
OAuth Applications UI) and exchanges it together with the OAuth app's
``client_secret`` for short-lived ``access_token`` values (15-minute
TTL). Tokens are refreshed proactively before expiry; a 401 from a data
endpoint also triggers a re-exchange and one retry.

Surface used by :class:`MarketData`:
- :meth:`get_iv_snapshot(ticker)` — returns :class:`IVSnapshotRaw`
- :meth:`get_options_chain(ticker, expiry)` — returns raw chain rows

Expected-move math (per ADR-0003) lives here so the seam only sees an
already-computed :class:`IVSnapshotRaw`. The endpoint URL shapes mirror
the public tastytrade developer docs.
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
    """OAuth token exchange failed (bad / revoked refresh_token or client_secret)."""


class TastytradeUnavailable(TastytradeError):
    """No usable options data for this ticker (no chain, no quotes, stale)."""


# Refresh the access token this many seconds before its declared expiry.
# Guards against clock skew and in-flight requests racing the expiry.
_REFRESH_LEEWAY_SECONDS = 60


class TastytradeClient:
    """Async tastytrade client using OAuth2 refresh-token grant."""

    BASE_URL = "https://api.tastytrade.com"
    TOKEN_PATH = "/oauth/token"
    # Nested chain returns expirations + strikes (with OCC + streamer
    # symbols) but no per-strike quotes. Quotes for each leg are fetched
    # separately via /market-data/by-type?equity-option=SYM1,SYM2,...
    NESTED_CHAIN_PATH = "/option-chains/{symbol}/nested"
    # /market-data/by-type takes a query param naming the instrument
    # type (`equity`, `equity-option`, ...) whose value is a comma-
    # separated symbol list, and returns one item per symbol with
    # bid/ask/mid/last.
    MARKET_DATA_PATH = "/market-data/by-type"
    # /market-metrics?symbols=A,B returns IV30, IV rank (0..1), HV,
    # liquidity, dividend metadata, etc. — one item per symbol.
    MARKET_METRICS_PATH = "/market-metrics"

    def __init__(
        self,
        client_secret: Optional[str] = None,
        refresh_token: Optional[str] = None,
        *,
        http_client: Optional[httpx.AsyncClient] = None,
    ):
        self._client_secret = client_secret or settings.tastytrade_client_secret
        self._refresh_token = refresh_token or settings.tastytrade_refresh_token
        if not self._client_secret or not self._refresh_token:
            raise ValueError(
                "TASTYTRADE_CLIENT_SECRET and TASTYTRADE_REFRESH_TOKEN must both be set. "
                "Mint a refresh_token via Manage → API → OAuth Applications → Create Grant."
            )
        # If a client is injected (tests), reuse it; otherwise own a private one.
        self._http = http_client
        self._owns_http = http_client is None
        self._access_token: Optional[str] = None
        self._access_token_expires_at: Optional[datetime] = None
        self._session_lock = asyncio.Lock()

    # ------------------------------------------------------------------
    # Auth
    # ------------------------------------------------------------------

    async def _http_client(self) -> httpx.AsyncClient:
        if self._http is None:
            self._http = httpx.AsyncClient(base_url=self.BASE_URL, timeout=_REQUEST_TIMEOUT)
        return self._http

    def _access_token_is_fresh(self) -> bool:
        if not self._access_token or self._access_token_expires_at is None:
            return False
        return datetime.now(timezone.utc) < self._access_token_expires_at

    async def _ensure_access_token(self, *, force: bool = False) -> str:
        async with self._session_lock:
            if self._access_token_is_fresh() and not force:
                return self._access_token  # type: ignore[return-value]
            client = await self._http_client()
            try:
                resp = await client.post(
                    self.TOKEN_PATH,
                    json={
                        "grant_type": "refresh_token",
                        "client_secret": self._client_secret,
                        "refresh_token": self._refresh_token,
                    },
                )
            except httpx.RequestError as exc:
                raise TastytradeAuthError(f"network error during token exchange: {exc}") from exc
            if resp.status_code not in (200, 201):
                raise TastytradeAuthError(
                    f"token exchange returned HTTP {resp.status_code}: {resp.text[:200]}"
                )
            payload = resp.json() or {}
            token = payload.get("access_token")
            if not token:
                raise TastytradeAuthError("token exchange response missing access_token")
            # expires_in is the lifetime in seconds; default to 15 min if missing.
            expires_in = int(payload.get("expires_in") or 900)
            self._access_token = token
            self._access_token_expires_at = datetime.now(timezone.utc) + timedelta(
                seconds=max(expires_in - _REFRESH_LEEWAY_SECONDS, 0)
            )
            return token

    async def _authed_get(self, path: str, params: Optional[dict] = None) -> dict:
        """GET with bearer access-token; one transparent re-exchange on 401."""
        client = await self._http_client()
        token = await self._ensure_access_token()
        for attempt in range(2):
            try:
                resp = await client.get(
                    path,
                    params=params,
                    headers={"Authorization": f"Bearer {token}"},
                )
            except httpx.RequestError as exc:
                raise TastytradeUnavailable(f"network error on {path}: {exc}") from exc
            if resp.status_code == 401 and attempt == 0:
                logger.info("tastytrade 401 on %s — refreshing access token", path)
                token = await self._ensure_access_token(force=True)
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
        """Return option-chain rows for ``ticker`` at ``expiry``.

        Each row has the keys downstream helpers consume: ``strike-price``,
        ``option-type`` (``"call"`` or ``"put"``), ``bid``, ``ask``,
        ``last``, ``updated-at``. Empty list if no strikes are published
        for ``expiry`` (or none of them have a market-data response).

        Tastytrade's REST API requires two calls: the nested chain
        endpoint gives the strike→OCC-symbol mapping, then
        ``/market-data/by-type`` returns bid/ask/last per OCC symbol.
        """
        symbol = ticker.upper()
        nested = await self._authed_get(
            self.NESTED_CHAIN_PATH.format(symbol=symbol)
        )
        items = (nested.get("data") or {}).get("items") or []
        if not items:
            return []
        target_exp = None
        for exp_block in items[0].get("expirations") or []:
            if exp_block.get("expiration-date") == expiry.isoformat():
                target_exp = exp_block
                break
        if target_exp is None:
            return []
        strikes = target_exp.get("strikes") or []
        if not strikes:
            return []

        # Build OCC-symbol → (strike-price, side) map for both legs of
        # every published strike, then batch-fetch their quotes in one
        # /market-data/by-type call.
        occ_to_meta: dict[str, tuple[str, str]] = {}
        for strike in strikes:
            sp = strike.get("strike-price")
            if sp is None:
                continue
            call_sym = strike.get("call")
            put_sym = strike.get("put")
            if call_sym:
                occ_to_meta[call_sym] = (sp, "call")
            if put_sym:
                occ_to_meta[put_sym] = (sp, "put")
        if not occ_to_meta:
            return []
        quotes_payload = await self._authed_get(
            self.MARKET_DATA_PATH,
            params={"equity-option": ",".join(occ_to_meta.keys())},
        )
        md_items = (quotes_payload.get("data") or {}).get("items") or []
        rows: list[dict] = []
        for md in md_items:
            sym = md.get("symbol")
            meta = occ_to_meta.get(sym)
            if meta is None:
                continue
            strike_price, side = meta
            rows.append(
                {
                    "strike-price": strike_price,
                    "option-type": side,
                    "bid": md.get("bid"),
                    "ask": md.get("ask"),
                    "last": md.get("last"),
                    "updated-at": md.get("updated-at"),
                }
            )
        return rows

    async def get_iv_snapshot(self, ticker: str) -> IVSnapshotRaw:
        """Build today's snapshot for ``ticker`` from a fresh chain pull.

        Raises :class:`TastytradeUnavailable` if the chain is missing,
        the underlying quote is missing, or no usable straddle can be
        priced. Per ADR-0003, snapshots without an expected move must
        not be written, so callers should treat this as a hard skip.
        """
        symbol = ticker.upper()

        # Underlying quote + front-week expiry can be fetched in parallel
        # since neither depends on the other.
        underlying_quote, front_expiry = await asyncio.gather(
            self._fetch_underlying_quote(symbol),
            self._fetch_front_expiry(symbol),
        )
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
        """Combine the underlying's last-trade price (from market-data) with
        its IV index + IV rank (from market-metrics). Tastytrade splits
        these across two endpoints, so we fan out in parallel."""
        md_payload, mm_payload = await asyncio.gather(
            self._authed_get(self.MARKET_DATA_PATH, params={"equity": symbol}),
            self._authed_get(self.MARKET_METRICS_PATH, params={"symbols": symbol}),
        )
        md_items = (md_payload.get("data") or {}).get("items") or []
        mm_items = (mm_payload.get("data") or {}).get("items") or []
        if not md_items:
            raise TastytradeUnavailable(f"no market data for {symbol}")
        if not mm_items:
            raise TastytradeUnavailable(f"no market metrics for {symbol}")
        md = md_items[0]
        mm = mm_items[0]
        try:
            raw_price = md.get("last") if md.get("last") is not None else md.get("mid")
            price = float(raw_price)
            iv30 = float(mm["implied-volatility-index"])
            # Tastytrade returns IV rank as a fraction in [0, 1]; the
            # iv_snapshots.iv_rank column is constrained to [0, 100] to
            # match ADR-0004's self-computed formula, so scale here.
            iv_rank = float(mm["implied-volatility-index-rank"]) * 100.0
        except (KeyError, TypeError, ValueError) as exc:
            raise TastytradeUnavailable(
                f"underlying quote/metrics missing required fields for {symbol}: {exc}"
            ) from exc
        return _UnderlyingQuote(price=price, iv30=iv30, iv_rank_provider=iv_rank)

    async def _fetch_front_expiry(self, symbol: str) -> date:
        """Return the earliest published expiration strictly after today."""
        payload = await self._authed_get(
            self.NESTED_CHAIN_PATH.format(symbol=symbol)
        )
        items = (payload.get("data") or {}).get("items") or []
        if not items:
            raise TastytradeUnavailable(f"no chain published for {symbol}")
        # Real shape: items[0].expirations[*].expiration-date
        expirations = items[0].get("expirations") or []
        today = date.today()
        future: list[date] = []
        for exp_block in expirations:
            exp_str = exp_block.get("expiration-date")
            if not exp_str:
                continue
            try:
                d = date.fromisoformat(exp_str)
            except ValueError:
                continue
            if d > today:
                future.append(d)
        if not future:
            raise TastytradeUnavailable(f"no future expirations for {symbol}")
        return min(future)


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
