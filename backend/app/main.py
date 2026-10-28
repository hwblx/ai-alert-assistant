import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
import httpx

from app.settings import settings
from app.database.session import create_db_and_tables, engine
from app.api import webhooks

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.http_client = None

    try:
        await create_db_and_tables()

        app.state.http_client = httpx.AsyncClient(
            timeout=settings.HTTP_TIMEOUT,
            follow_redirects=True,
            )

        yield

    except Exception as e:
        logger.error(
            msg="Application lifespan error",
            exc_info=e
        )
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





