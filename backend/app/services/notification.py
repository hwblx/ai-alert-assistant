import asyncio
from typing import Any
import logging

import httpx

from app.schemas import AlertResponse
from app.settings import settings
from app.errors import NotificationError

HOOKDECK_API_URL = settings.HOOKDECK_API_URL
HOOKDECK_API_KEY = settings.HOOKDECK_API_KEY

logger = logging.getLogger(__name__)


async def send_notification(
    notification: AlertResponse,
    client: httpx.AsyncClient,
) -> dict[str, Any] | None:
    headers = {
        "X-API-Key": HOOKDECK_API_KEY,
    }
    payload=notification.model_dump(mode="json")

    try:
        max_attempts = 3
        http_codes = [502, 503, 504, 429]

        for attempt in range(max_attempts):
            try:
                response = await client.post(
                    url=HOOKDECK_API_URL,
                    headers=headers,
                    json=payload,
                )

            except httpx.TransportError:
                if attempt < max_attempts -1:
                    seconds = 2 ** attempt
                    logger.warning(f"Notification delivery attempt {attempt+1} encountered transport error; retrying in {seconds}")
                    await asyncio.sleep(seconds)
                    continue
                raise

            if response.status_code in http_codes:
                if attempt < max_attempts -1:
                    seconds = 2 ** attempt
                    logger.warning(f"Notification delivery attempt {attempt+1} failed; retrying in {seconds}")
                    await asyncio.sleep(seconds)
                    continue

            response.raise_for_status()
            logger.debug("Notification delivered successfully")
            return response.json()

    except Exception as e:
        logger.error(f"Notification delivery failed after {attempt+1} attempts")
        
        raise NotificationError(
            f"Notification failed: {e}"
        ) from e

    return {}

