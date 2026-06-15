from __future__ import annotations
import pytest
import pytest_asyncio
from sqlalchemy import BigInteger
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.ext.compiler import compiles

from app.database.base import Base
from app.database import models  # noqa: F401  ensure models are registered


# SQLite's autoincrement-on-insert behavior only kicks in for columns whose
# type compiles to exactly "INTEGER" (i.e. an alias for the rowid). The
# production schema uses BigInteger primary keys (fine on Postgres), so for
# the SQLite test engine we compile BigInteger -> INTEGER.
@compiles(BigInteger, "sqlite")
def _compile_big_integer_sqlite(type_, compiler, **kw):
    return "INTEGER"


@pytest_asyncio.fixture
async def session():
    engine = create_async_engine("sqlite+aiosqlite://", future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with SessionLocal() as s:
        yield s

    await engine.dispose()


@pytest.fixture
def anyio_backend():
    return "asyncio"
