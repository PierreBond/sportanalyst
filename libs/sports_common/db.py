from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

from sports_common.config import settings
from sports_common.logging import get_logger

logger = get_logger(__name__)


class DatabaseClient:
    def __init__(
        self,
        database_url: str | None = None,
        echo: bool = False,
    ) -> None:
        self._database_url = database_url or settings.database_url
        self._engine: AsyncEngine | None = None
        self._session_factory: sessionmaker[AsyncSession] | None = None
        self._echo = echo

    @property
    def engine(self) -> AsyncEngine:
        if self._engine is None:
            self._engine = create_async_engine(
                self._database_url,
                echo=self._echo,
                poolclass=NullPool,
            )
        return self._engine

    @property
    def session_factory(self) -> sessionmaker[AsyncSession]:
        if self._session_factory is None:
            self._session_factory = sessionmaker(
                bind=self.engine,
                class_=AsyncSession,
                expire_on_commit=False,
            )
        return self._session_factory

    @asynccontextmanager
    async def session(self) -> AsyncGenerator[AsyncSession, None]:
        async with self.session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    async def init_db(self) -> None:
        async with self.engine.begin() as conn:
            logger.info("database_connection_established")

    async def close(self) -> None:
        if self._engine:
            await self.engine.dispose()


db_client = DatabaseClient()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with db_client.session() as session:
        yield session


get_async_session = get_db
