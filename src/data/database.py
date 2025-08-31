"""Database connection and session management."""

from contextlib import asynccontextmanager, contextmanager
from typing import AsyncGenerator, Generator

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool, QueuePool

from ..config import settings
from ..utils.logger import get_logger
from .models import Base


logger = get_logger(__name__)


class DatabaseService:
    """Database service for managing connections and sessions."""
    
    def __init__(self):
        self.engine = None
        self.async_engine = None
        self.SessionLocal = None
        self.AsyncSessionLocal = None
        self._initialized = False
    
    def initialize(self, database_url: str = None):
        """Initialize database connections."""
        if self._initialized:
            return
        
        db_url = database_url or settings.get_database_url()
        
        # Build driver-specific URLs for sync/async
        # Normalize base PostgreSQL URL without driver suffix
        if db_url.startswith('postgresql+'):
            base_url = 'postgresql://' + db_url.split('://', 1)[1]
        else:
            base_url = db_url

        # Sync engine (psycopg3)
        sync_url = base_url.replace('postgresql://', 'postgresql+psycopg://')
        self.engine = create_engine(
            sync_url,
            pool_size=settings.database.pool_size,
            max_overflow=settings.database.max_overflow,
            pool_timeout=settings.database.pool_timeout,
            pool_pre_ping=True,
            echo=settings.database.echo
        )

        # Async engine (asyncpg)
        async_url = base_url.replace('postgresql://', 'postgresql+asyncpg://')
        self.async_engine = create_async_engine(
            async_url,
            pool_size=settings.database.pool_size,
            max_overflow=settings.database.max_overflow,
            pool_timeout=settings.database.pool_timeout,
            pool_pre_ping=True,
            echo=settings.database.echo
        )
        
        # Session factories
        self.SessionLocal = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=self.engine
        )
        
        self.AsyncSessionLocal = sessionmaker(
            self.async_engine,
            class_=AsyncSession,
            expire_on_commit=False
        )
        
        self._initialized = True
        logger.info("Database service initialized")
    
    def create_tables(self):
        """Create all database tables."""
        if not self._initialized:
            self.initialize()
        
        Base.metadata.create_all(bind=self.engine)
        logger.info("Database tables created")
    
    def drop_tables(self):
        """Drop all database tables."""
        if not self._initialized:
            self.initialize()
        
        Base.metadata.drop_all(bind=self.engine)
        logger.warning("Database tables dropped")
    
    @contextmanager
    def get_session(self) -> Generator[Session, None, None]:
        """Get a database session."""
        if not self._initialized:
            self.initialize()
        
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
    
    @asynccontextmanager
    async def get_async_session(self) -> AsyncGenerator[AsyncSession, None]:
        """Get an async database session."""
        if not self._initialized:
            self.initialize()
        
        async with self.AsyncSessionLocal() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()
    
    def close(self):
        """Close database connections."""
        if self.engine:
            self.engine.dispose()
        if self.async_engine:
            # Note: This is sync dispose, use await async_engine.dispose() in async context
            self.async_engine.sync_engine.dispose()
        self._initialized = False
        logger.info("Database connections closed")


# Global instance
db_service = DatabaseService()


# Dependency injection helpers
def get_db() -> Generator[Session, None, None]:
    """Dependency for FastAPI to get DB session."""
    with db_service.get_session() as session:
        yield session


async def get_async_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for FastAPI to get async DB session."""
    async with db_service.get_async_session() as session:
        yield session