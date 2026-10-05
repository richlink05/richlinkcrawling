"""SQLAlchemy Base 및 비동기 엔진/세션 설정.

애플리케이션 전체가 공유하는 단일 엔진과 세션 팩토리를 제공한다.
"""
from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from backend.config.settings import get_settings


class Base(DeclarativeBase):
    """모든 ORM 모델이 상속하는 베이스 클래스."""


_settings = get_settings()

engine = create_async_engine(
    _settings.database_url,
    echo=_settings.database_echo,
    pool_pre_ping=True,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,
    autoflush=False,
)


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI Depends(get_db_session)로 주입할 비동기 DB 세션 제공자.

    요청/작업 단위로 세션을 열고, 블록 종료 시 자동으로 닫는다.
    """
    async with AsyncSessionLocal() as session:
        yield session
