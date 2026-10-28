from typing import Annotated
from datetime import datetime, UTC, timedelta

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.database.models import Alert
from app.database.session import async_session_factory
from app.schemas import Fingerprint, AlertUpdate


async def get_alert_by_lookback(
    session: AsyncSession,
    fingerprint: Fingerprint,
    lookback: Annotated[int, "Minutes"]
):
    now = datetime.now(UTC)
    cutoff = now - timedelta(minutes=lookback)

    statement = (
        select(Alert)
        .where(Alert.fingerprint == fingerprint)
        .where(Alert.created_at >= cutoff)
        .order_by(Alert.created_at.desc())
    )
    result = await session.exec(statement)
    return result.first()


async def create_alert(session: AsyncSession, new_alert: Alert):
    session.add(new_alert)
    await session.commit()
    await session.refresh(new_alert)

    return new_alert


async def get_alert_by_id(
    alert_id: int,
):
    async with async_session_factory() as session:
        alert = await session.get(Alert, alert_id)
        return alert


async def update_alert(
    alert_id: int,
    update: AlertUpdate
):
    async with async_session_factory() as session:
        try:
            alert = await session.get(Alert, alert_id)

            if not alert:
                return None

            alert.sqlmodel_update(update.model_dump(exclude_unset=True))
            alert.updated_at = datetime.now(UTC)

            session.add(alert)
            await session.commit()
            await session.refresh(alert)

            return alert

        except Exception:
            # await session.rollback()
            raise

