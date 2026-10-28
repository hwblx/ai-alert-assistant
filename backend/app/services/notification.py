import asyncio
from typing import Any

import httpx

from app.schemas import AlertResponse
from app.settings import settings
from app.errors import NotificationError

HOOKDECK_API_URL = settings.HOOKDECK_API_URL
HOOKDECK_API_KEY = settings.HOOKDECK_API_KEY


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
                    await asyncio.sleep(2 ** attempt)
                    continue
                raise

            if response.status_code in http_codes:
                if attempt < max_attempts -1:
                    await asyncio.sleep(2 ** attempt)
                    continue

            response.raise_for_status()
            return response.json()

    except Exception as e:
        raise NotificationError(
            f"Notification failed: {e}"
        ) from e

