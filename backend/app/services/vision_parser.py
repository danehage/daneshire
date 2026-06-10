"""
VisionParser — seam for AI-driven image parsing.

The ``VisionParser`` protocol exists for testability via injection (mirrors
AlertEngine/MarketData pattern) per ADR-0001 discipline: one real adapter,
not a multi-vendor abstraction.

Error hierarchy → HTTP status codes (mapped at the route boundary):
  VisionLowConfidence  → 422
  VisionRateLimited    → 429
  VisionUpstreamError  → 502
"""

from __future__ import annotations

import json
import logging
from typing import Protocol

from app.config import settings
from app.schemas.portfolio_parsing import ParsedPortfolioSnapshot

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Error hierarchy
# ---------------------------------------------------------------------------

CONFIDENCE_THRESHOLD = 0.6


class VisionParseError(Exception):
    """Base class for VisionParser failures."""


class VisionLowConfidence(VisionParseError):
    """Parsed result has confidence below the acceptable threshold."""


class VisionRateLimited(VisionParseError):
    """Upstream API rate limit exceeded."""


class VisionUpstreamError(VisionParseError):
    """Unexpected upstream error (network, malformed payload, etc.)."""


# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------


class VisionParser(Protocol):
    async def parse_portfolio(
        self,
        image_bytes: bytes,
        account_hint: str | None = None,
    ) -> ParsedPortfolioSnapshot: ...


# ---------------------------------------------------------------------------
# Gemini adapter
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """
You are a financial-data extraction assistant. Your job is to parse a portfolio
screenshot and return structured JSON matching the schema below exactly.

Rules:
1. Extract the account name and type (e.g. "Roth IRA", "Taxable Individual") from
   the screenshot header if visible. Include in "account_name" and "account_type".
2. Extract every position row: ticker symbol, quantity, average cost, and current
   market value. For option rows also extract strike price, expiry date, option type
   (call/put), multiplier (default 100 if visible), and the underlying ticker.
   Brokers display options as a single description string — you MUST decompose it
   into the separate fields. "ticker" is ONLY the underlying symbol, never the full
   description. Example: a row labelled "AXON Sep 18 '26 $480 Call" becomes:
     {"instrument_type": "option", "ticker": "AXON", "underlying_ticker": "AXON",
      "option_type": "call", "strike": "480", "expiry": "2026-09-18", "multiplier": 100, ...}
3. Extract cash / money-market balance as "cash_balance" if visible.
4. Extract the total portfolio value as "parsed_total_value" if shown (separate from
   the sum of positions).
5. Set "instrument_type" to "equity" for stocks/ETFs and "option" for options.
6. Short positions are valid and common (sold/written options, short stock). When a
   row shows a negative quantity, return "qty" as a negative number — never drop the
   minus sign. Keep the sign of "market_value" exactly as displayed (short positions
   often show negative market value).
7. Set "confidence" (0.0–1.0) reflecting how clearly you could read the screenshot.
   Use < 0.6 only if the image is blurry, partially cut off, or uses an unrecognised
   layout.
8. Return ONLY the JSON object. No prose, no markdown fences.

JSON schema:
{
  "account_name": string | null,
  "account_type": string | null,
  "captured_at": ISO-8601 datetime | null,
  "cash_balance": decimal string | null,
  "parsed_total_value": decimal string | null,
  "confidence": float,
  "positions": [
    {
      "instrument_type": "equity" | "option",
      "ticker": string,
      "qty": decimal string,
      "avg_cost": decimal string | null,
      "market_value": decimal string | null,
      "option_type": "call" | "put" | null,
      "strike": decimal string | null,
      "expiry": "YYYY-MM-DD" | null,
      "multiplier": integer | null,
      "underlying_ticker": string | null
    }
  ]
}
"""


def get_vision_parser_from_state(app) -> VisionParser | None:
    """Read the VisionParser singleton off ``app.state``."""
    return getattr(app.state, "vision_parser", None)


class GeminiVisionParser:
    """Gemini-backed VisionParser adapter.

    The ``google-generativeai`` import is deferred to __init__ so that this
    module can be imported in tests without the library being available. Tests
    use FakeVisionParser injected via dependency_overrides instead.

    Raises ``ValueError`` if ``GEMINI_API_KEY`` is not configured; the caller
    (lifespan) catches this and sets ``app.state.vision_parser = None``.
    Raises ``ImportError`` if ``google-generativeai`` is not installed.
    """

    def __init__(self) -> None:
        try:
            import google.generativeai as genai
            self._genai = genai
        except (ImportError, Exception) as exc:
            raise ImportError(
                "google-generativeai is required for GeminiVisionParser"
            ) from exc

        if not settings.gemini_api_key:
            raise ValueError("GEMINI_API_KEY is not configured")

        self._genai.configure(api_key=settings.gemini_api_key)
        self._model_name = "gemini-2.5-flash"

    async def parse_portfolio(
        self,
        image_bytes: bytes,
        account_hint: str | None = None,
    ) -> ParsedPortfolioSnapshot:
        try:
            model = self._genai.GenerativeModel(
                self._model_name,
                generation_config={"response_mime_type": "application/json"},
            )
            prompt_parts = [_SYSTEM_PROMPT]
            if account_hint:
                prompt_parts.append(f"Account hint from user: {account_hint}")
            prompt_parts.append(
                {"mime_type": "image/png", "data": image_bytes}
            )

            snapshot = await self._generate_and_validate(model, prompt_parts)

            if snapshot.confidence < CONFIDENCE_THRESHOLD:
                raise VisionLowConfidence(
                    f"Confidence {snapshot.confidence:.2f} below threshold "
                    f"{CONFIDENCE_THRESHOLD}"
                )
            return snapshot

        except VisionParseError:
            raise
        except Exception as exc:
            msg = str(exc).lower()
            if "quota" in msg or "rate" in msg or "429" in msg:
                raise VisionRateLimited(str(exc)) from exc
            logger.exception("Gemini parse failed")
            raise VisionUpstreamError(str(exc)) from exc

    async def _generate_and_validate(
        self, model, prompt_parts: list
    ) -> ParsedPortfolioSnapshot:
        """Call Gemini and validate the response, retrying once on schema errors.

        The retry feeds the validation error back so the model can correct
        field-mapping mistakes (e.g. a full option description left in
        ``ticker`` instead of being decomposed into the option fields).
        """
        response = await model.generate_content_async(prompt_parts)
        try:
            return ParsedPortfolioSnapshot.model_validate(json.loads(response.text))
        except Exception as exc:
            logger.warning("Gemini response failed validation, retrying: %s", exc)
            retry_parts = prompt_parts + [
                "Your previous response failed schema validation with this error:\n"
                f"{exc}\n"
                "Return the corrected JSON object. Remember: \"ticker\" is only the "
                "underlying symbol; option details belong in option_type / strike / "
                "expiry / multiplier."
            ]
            response = await model.generate_content_async(retry_parts)
            return ParsedPortfolioSnapshot.model_validate(json.loads(response.text))
