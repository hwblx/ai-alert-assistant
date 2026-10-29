import logging

import httpx

from app.database.crud import get_alert_by_id, update_alert
from app.errors import AlertProcessError
from app.schemas import AlertStatus, AlertUpdate, AlertResponse
from app.services.notification import send_notification
from app.services.agent import BaseAgent

logger = logging.getLogger(__name__)


async def process_alert(alert_id: int, agent: BaseAgent, client: httpx.AsyncClient):
    alert = None

    try:
        alert = await get_alert_by_id(alert_id)

        if not alert:
            logger.warning(
                "Alert not found",
                extra={"alert_id": alert_id},
             )
            return

        update = AlertUpdate(status=AlertStatus.ANALYZING)
        await update_alert(alert_id, update)

        assessment=  await agent.execute(raw_payload=alert.raw_payload)

        update = AlertUpdate(
            status=AlertStatus.NOTIFYING,
            analysis_summary=assessment.sanitized_summary
        )
        await update_alert(alert_id, update)

        notification = AlertResponse(
            **assessment.model_dump(),
            alert_metadata={
                "fingerprint": alert.fingerprint,
                "name": alert.name,
                "created_at": alert.created_at.isoformat(),
            }
        )

        await send_notification(notification, client)

        update = AlertUpdate(status=AlertStatus.COMPLETED)
        await update_alert(alert_id, update)

    except Exception as e:
        if alert:
            update = AlertUpdate(
                status=AlertStatus.FAILED,
                error_message=str(e)
            )
            await update_alert(alert_id, update)

        raise AlertProcessError(
            f"Alert processing failed: {e}"
        ) from e



