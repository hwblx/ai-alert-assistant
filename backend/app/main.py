import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
import httpx

from app.settings import settings
from app.database.session import create_db_and_tables, engine
from app.api import webhooks
from app.services.agent import get_agent

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    force=True
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.http_client = None

    try:
        await create_db_and_tables()

        app.state.ai_agent = get_agent()

        app.state.http_client = httpx.AsyncClient(
            timeout=settings.HTTP_TIMEOUT,
            follow_redirects=True,
            )

        yield

    except Exception:
        logger.exception("Application lifespan error")
        raise

    finally:
        try:
            if app.state.http_client is not None:
                await app.state.http_client.aclose()
        finally:
            await engine.dispose()


app = FastAPI(
    lifespan=lifespan,
    title="AI Alert Assistant",
    version="0.1",
)
app.include_router(webhooks.router)





