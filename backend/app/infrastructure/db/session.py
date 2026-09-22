"""Database async session and engine setup with PostgreSQL RLS support."""

from collections.abc import AsyncGenerator

from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import settings

connect_args = {"timeout": 30.0} if "sqlite" in settings.DATABASE_URL else {}
pool_kwargs = {"poolclass": NullPool} if "sqlite" in settings.DATABASE_URL else {}

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DATABASE_ECHO,
    future=True,
    connect_args=connect_args,
    **pool_kwargs,
)

if "sqlite" in str(engine.url):
    @event.listens_for(engine.sync_engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL;")
        cursor.execute("PRAGMA busy_timeout=30000;")
        cursor.close()

async_session_factory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def set_tenant_context(session: AsyncSession, organization_id: str | None) -> None:
    """Configures PostgreSQL session variable for Row-Level Security (RLS)."""
    if organization_id and "postgresql" in str(session.bind.url if session.bind else ""):
        # Sanitize UUID to prevent SQL injection in session setting
        safe_org_id = organization_id.replace("'", "")
        await session.execute(text(f"SET LOCAL app.current_org_id = '{safe_org_id}'"))


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency for obtaining an isolated async database session."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()