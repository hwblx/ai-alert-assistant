import hashlib
import json
import logging

from sqlmodel.ext.asyncio.session import AsyncSession

from app.schemas import AlertPayload, AlertStatus, Fingerprint, IngestionResult
from app.database.models import Alert
from app.database.crud import get_alert_by_lookback, create_alert

logger = logging.getLogger(__name__)


def compute_fingerprint(payload: AlertPayload) -> Fingerprint:
    identity = {
        "name": payload.name,
        "severity": payload.severity,
    }

    canonical = json.dumps(
        identity,
        sort_keys=True,
        separators=(",", ":"),
    )

    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


async def ingest_alert(
    session: AsyncSession,
    payload: AlertPayload,
    lookback_minutes: int = 15
) -> IngestionResult:
    fingerprint: Fingerprint = compute_fingerprint(payload)

    prev_alert = await get_alert_by_lookback(
        session,
        fingerprint=fingerprint,
        lookback=lookback_minutes
    )

    if prev_alert:
        logger.info(f"Alert deduplicated against recent incident; skipping processing (alert_id={prev_alert.id}, fingerprint={fingerprint})")

        return IngestionResult(
            status=prev_alert.status,
            alert_id=prev_alert.id,
            fingerprint=prev_alert.fingerprint,
            message= "deduplicated"
        )

    new_alert = Alert(
        fingerprint=fingerprint,
        name=payload.name, 
        source="alertmanager", 
        status=AlertStatus.PENDING,
        raw_payload=payload.model_dump()
    )

    alert = await create_alert(session, new_alert=new_alert) 
    
    logger.info(f"Ingested new alert (alert_id={alert.id}, fingerprint={fingerprint}, name={payload.name})")
    return IngestionResult(
        status=alert.status,
        alert_id=alert.id,
        fingerprint=alert.fingerprint,
        message= "created"
    )

    

