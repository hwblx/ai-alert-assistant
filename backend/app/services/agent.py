from typing import Any
import logging

from app.services.prompt_strategy import analyze_sequentially, analyze_single_pass
from app.schemas import AlertAssessment
from app.settings import settings
from app.errors import AgentAnalysisError

SEQUENTIAL_PROMPTING = settings.SEQUENTIAL_PROMPTING

logger = logging.getLogger(__name__)
logger.setLevel(level=logging.WARNING)


async def analyze_alert(raw_payload: dict[str, Any]) -> AlertAssessment:
    logger.warning("Start analyzing alert ...")

    try:
        if SEQUENTIAL_PROMPTING:
            return await analyze_sequentially(raw_payload)

        else:
            return await analyze_single_pass(raw_payload)

    except Exception as e:
        raise AgentAnalysisError(
            f"Failed to analyze alert: {e}"
        ) from e


