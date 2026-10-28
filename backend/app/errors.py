from fastapi import HTTPException, status


ALERT_NOT_FOUND = HTTPException(
    status_code = status.HTTP_404_NOT_FOUND, detail="Alert not found"
)

HOOKDECK_MISSING_SECRET = HTTPException(
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR, 
    detail="Webhook signing secret not configured"
)

PAYLOAD_VALIDATION_ERROR = HTTPException(
    status_code = status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Invalid payload"
)

HOOKDECK_INVALID_SIGNATURE = HTTPException(
    status_code = status.HTTP_401_UNAUTHORIZED, detail="Invalid signature"
)

HOOKDECK_MISSING_SIGNATURE = HTTPException(
    status_code = status.HTTP_401_UNAUTHORIZED, detail="Missing signature"
)


class AgentAnalysisError(Exception):
    """Raised when agent analysis fails."""


class AlertProcessError(Exception):
    """Raised when alert processing fails."""


class ModelInitializationError(Exception):
    """Raised when model intialization fails."""


class NotificationError(Exception):
    """Raised when notification fails."""



