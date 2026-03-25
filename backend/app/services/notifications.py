"""
Pushover notification service for alert notifications.
"""

import logging
from typing import Optional

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

# Pushover API endpoint
PUSHOVER_API_URL = "https://api.pushover.net/1/messages.json"

# Priority mapping: alert priority -> Pushover priority
# Pushover: -2 (lowest) to 2 (emergency)
PRIORITY_MAP = {
    "low": -1,
    "normal": 0,
    "high": 1,
    "urgent": 2,
}


class PushoverClient:
    """Client for sending Pushover notifications."""

    def __init__(
        self,
        user_key: Optional[str] = None,
        api_token: Optional[str] = None,
    ):
        self.user_key = user_key or settings.pushover_user_key
        self.api_token = api_token or settings.pushover_api_token
        self._client: Optional[httpx.AsyncClient] = None

    @property
    def is_configured(self) -> bool:
        """Check if Pushover credentials are configured."""
        return bool(self.user_key and self.api_token)

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=30.0)
        return self._client

    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None

    async def send(
        self,
        title: str,
        message: str,
        priority: str = "normal",
        url: Optional[str] = None,
        url_title: Optional[str] = None,
        sound: Optional[str] = None,
    ) -> bool:
        """
        Send a Pushover notification.

        Args:
            title: Notification title
            message: Notification body
            priority: low, normal, high, or urgent
            url: Optional URL to include
            url_title: Optional title for the URL
            sound: Optional sound name (see Pushover docs)

        Returns:
            True if notification was sent successfully
        """
        if not self.is_configured:
            logger.warning("Pushover not configured, skipping notification")
            return False

        pushover_priority = PRIORITY_MAP.get(priority, 0)

        payload = {
            "token": self.api_token,
            "user": self.user_key,
            "title": title,
            "message": message,
            "priority": pushover_priority,
        }

        if url:
            payload["url"] = url
        if url_title:
            payload["url_title"] = url_title
        if sound:
            payload["sound"] = sound

        # For urgent priority (2), Pushover requires retry and expire params
        if pushover_priority == 2:
            payload["retry"] = 60  # Retry every 60 seconds
            payload["expire"] = 3600  # Expire after 1 hour

        try:
            client = await self._get_client()
            response = await client.post(PUSHOVER_API_URL, data=payload)

            if response.status_code == 200:
                logger.info(f"Pushover notification sent: {title}")
                return True
            else:
                logger.error(
                    f"Pushover API error: {response.status_code} - {response.text}"
                )
                return False

        except Exception as e:
            logger.error(f"Failed to send Pushover notification: {e}")
            return False


async def send_alert_notification(
    ticker: str,
    alert_name: str,
    condition_description: str,
    actual_value: float,
    action_note: Optional[str] = None,
    priority: str = "normal",
) -> bool:
    """
    Send an alert triggered notification.

    Args:
        ticker: Stock ticker symbol
        alert_name: Name of the alert
        condition_description: Human-readable condition (e.g., "price > $150")
        actual_value: The actual value that triggered the alert
        action_note: Optional action to take
        priority: Alert priority level

    Returns:
        True if notification was sent
    """
    client = PushoverClient()

    title = f"{ticker}: {alert_name}"

    message_parts = [
        f"Condition: {condition_description}",
        f"Actual: {actual_value:.2f}",
    ]

    if action_note:
        message_parts.append(f"\nAction: {action_note}")

    message = "\n".join(message_parts)

    try:
        result = await client.send(
            title=title,
            message=message,
            priority=priority,
        )
        return result
    finally:
        await client.close()


def format_condition(condition: dict) -> str:
    """
    Format a condition dict as a human-readable string.

    Args:
        condition: {"metric": "price", "operator": ">", "value": 150}

    Returns:
        "price > 150"
    """
    metric = condition.get("metric", "?")
    operator = condition.get("operator", "?")
    value = condition.get("value", "?")

    # Format value nicely
    if isinstance(value, float):
        if metric == "price":
            value_str = f"${value:.2f}"
        elif metric in ("rsi", "hv_rank", "range_position"):
            value_str = f"{value:.1f}"
        else:
            value_str = f"{value:.2f}"
    else:
        value_str = str(value)

    return f"{metric} {operator} {value_str}"
