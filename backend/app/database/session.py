from typing import Annotated

from fastapi import Depends
from sqlmodel import SQLModel
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlmodel.ext.asyncio.session import AsyncSession

from app.settings import settings

database_url = settings.DATABASE_URL

engine = create_async_engine(
    database_url,
    connect_args={"check_same_thread": False},
    echo=True
)

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def create_db_and_tables():
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)


async def get_session():
    async with async_session_factory() as session:
        yield session

SessionDep = Annotated[AsyncSession, Depends(get_session)]


