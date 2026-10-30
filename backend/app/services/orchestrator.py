import logging

import httpx

from app.database.crud import get_alert_by_id, update_alert
from app.errors import AlertProcessError
from app.schemas import AlertStatus, AlertUpdate, AlertResponse
from app.services.notification import send_notification
from app.services.agent import BaseAgent

logger = logging.getLogger(__name__)


async def process_alert(alert_id: int, agent: BaseAgent, client: httpx.AsyncClient):
    logger.info(f"Starting alert processing pipeline (alert_id={alert_id})")
    alert = None

    try:
        alert = await get_alert_by_id(alert_id)

        if not alert:
            logger.warning(f"Alert record not found for background processing (alert_id={alert_id})")
            return

        update = AlertUpdate(status=AlertStatus.ANALYZING)
        await update_alert(alert_id, update)

        assessment=  await agent.execute(raw_payload=alert.raw_payload)
        logger.info(f"Diagnostic analysis completed (alert_id={alert_id})")

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

        logger.info(f"Notification dispatched to webhook service (alert_id={alert_id})")
        await send_notification(notification, client)

        update = AlertUpdate(status=AlertStatus.COMPLETED)
        await update_alert(alert_id, update)
        
        logger.info(f"Alert processing pipeline completed successfully (alert_id={alert_id})")
 

    except Exception as e:
        logger.exception(f"Alert processing pipeline failed (alert_id={alert_id})")
        
        if alert:
            update = AlertUpdate(
                status=AlertStatus.FAILED,
                error_message=str(e)
            )
            await update_alert(alert_id, update)

        raise AlertProcessError(
            f"Alert processing failed: {e}"
        ) from e



