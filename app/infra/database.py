"""Engine e session factory do SQLAlchemy 2.0 async."""

import ssl
from collections.abc import AsyncGenerator

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from infra.config import settings

connect_args: dict = {}
if "supabase" in settings.database_url or "sslmode" in settings.database_url:
    ssl_ctx = ssl.create_default_context()
    ssl_ctx.check_hostname = False
    ssl_ctx.verify_mode = ssl.CERT_NONE
    connect_args["ssl"] = ssl_ctx

engine = create_async_engine(
    settings.async_database_url,
    pool_size=5,
    max_overflow=5,
    pool_pre_ping=True,
    connect_args=connect_args,
)

if settings.db_schema:

    @event.listens_for(engine.sync_engine, "connect")
    def _set_search_path(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute(f"SET search_path TO {settings.db_schema}, public")
        cursor.close()

async_session = async_sessionmaker(engine, expire_on_commit=False)


async def get_session() -> AsyncGenerator[AsyncSession]:
    """Gera sessão async para injeção de dependência."""
    async with async_session() as session:
        yield session
