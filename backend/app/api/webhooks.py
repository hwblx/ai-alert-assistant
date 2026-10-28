import hashlib
import hmac
import base64
import logging

from fastapi import APIRouter, Depends, Request, Response, BackgroundTasks, status
from pydantic import ValidationError

from app.schemas import AlertPayload, IngestionResult
from app.database.session import SessionDep
from app.services.ingestion import ingest_alert
from app.services.orchestrator import process_alert
from app.settings import settings
from app.errors import (
    HOOKDECK_MISSING_SECRET,
    HOOKDECK_MISSING_SIGNATURE, HOOKDECK_INVALID_SIGNATURE,
    PAYLOAD_VALIDATION_ERROR
)

logging.basicConfig(level=logging.CRITICAL)
logger = logging.getLogger(__name__)
router = APIRouter()


async def verify_webhook(request: Request):
    HOOKDECK_SIGNING_SECRET = settings.HOOKDECK_SIGNING_SECRET

    if not HOOKDECK_SIGNING_SECRET:
        raise HOOKDECK_MISSING_SECRET

    signatures = [
        request.headers.get("x-hookdeck-signature"),
        request.headers.get("x-hookdeck-signature-2"),
    ]

    signatures = [sig for sig in signatures if sig]

    if not signatures:
        raise HOOKDECK_MISSING_SIGNATURE

    body = await request.body()

    expected_signature = base64.b64encode(
        hmac.new(
            HOOKDECK_SIGNING_SECRET.encode("utf-8"),
            body,
            hashlib.sha256,
        ).digest()
    ).decode("ascii")

    if not any(
        hmac.compare_digest(expected_signature, signature)
        for signature in signatures
    ):
        raise HOOKDECK_INVALID_SIGNATURE


@router.post("/webhooks", response_model=IngestionResult, dependencies=[Depends(verify_webhook)])
async def receive_webhook(
    request: Request,
    session: SessionDep,
    background_tasks: BackgroundTasks,
    response: Response,
):
    body = await request.body()

    try:
        payload = AlertPayload.model_validate_json(body)
    except ValidationError:
        raise PAYLOAD_VALIDATION_ERROR

    result: IngestionResult = await ingest_alert(
        session,
        payload,
        lookback_minutes=settings.ALERT_DEDUPLICATION_WINDOW_MINUTES
    )

    if result.alert_id and result.message == "created":
        background_tasks.add_task(
            process_alert,
            alert_id=result.alert_id,
            client=request.app.state.http_client
        )

        response.status_code = status.HTTP_201_CREATED
    else:
        response.status_code = status.HTTP_200_OK

    return result


