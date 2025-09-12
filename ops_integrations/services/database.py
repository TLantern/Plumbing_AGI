"""
Database configuration and connection management for salon phone service
"""

import os
import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import sessionmaker, Session
from .models import Base

logger = logging.getLogger(__name__)

class DatabaseManager:
    def __init__(self, database_url: str):
        self.database_url = database_url
        self.async_engine = None
        self.sync_engine = None
        self.async_session_factory = None
        self.sync_session_factory = None
        
    def initialize(self):
        """Initialize database engines and session factories"""
        try:
            # For PostgreSQL async operations
            if self.database_url.startswith("postgresql://"):
                async_url = self.database_url.replace("postgresql://", "postgresql+asyncpg://")
            else:
                async_url = self.database_url
                
            self.async_engine = create_async_engine(
                async_url,
                echo=False,
                pool_pre_ping=True,
                pool_recycle=300
            )
            
            # For sync operations (migrations, etc.)
            self.sync_engine = create_engine(
                self.database_url,
                echo=False,
                pool_pre_ping=True,
                pool_recycle=300
            )
            
            self.async_session_factory = async_sessionmaker(
                self.async_engine,
                class_=AsyncSession,
                expire_on_commit=False
            )
            
            self.sync_session_factory = sessionmaker(
                self.sync_engine,
                expire_on_commit=False
            )
            
            logger.info("Database connections initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            raise
    
    async def create_tables(self):
        """Create all tables"""
        try:
            async with self.async_engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            logger.info("Database tables created successfully")
        except Exception as e:
            logger.error(f"Failed to create tables: {e}")
            raise
    
    def create_tables_sync(self):
        """Create all tables synchronously"""
        try:
            Base.metadata.create_all(self.sync_engine)
            logger.info("Database tables created successfully (sync)")
        except Exception as e:
            logger.error(f"Failed to create tables (sync): {e}")
            raise
    
    @asynccontextmanager
    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """Get async database session"""
        async with self.async_session_factory() as session:
            try:
                yield session
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()
    
    @asynccontextmanager
    def get_sync_session(self) -> Session:
        """Get sync database session"""
        with self.sync_session_factory() as session:
            try:
                yield session
            except Exception:
                session.rollback()
                raise
            finally:
                session.close()

# Global database manager instance
db_manager: Optional[DatabaseManager] = None

def get_database_url() -> str:
    """Get database URL from environment variables"""
    # Heroku provides DATABASE_URL automatically
    database_url = os.getenv("DATABASE_URL")
    
    if not database_url:
        # Fallback to SQLite for local development
        database_url = "sqlite:///./salon_phone.db"
        logger.warning("No DATABASE_URL found, using SQLite for local development")
    
    # Handle Heroku's postgres:// URL format
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)
    
    return database_url

def initialize_database() -> DatabaseManager:
    """Initialize and return database manager"""
    global db_manager
    
    database_url = get_database_url()
    db_manager = DatabaseManager(database_url)
    db_manager.initialize()
    
    return db_manager

async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependency to get database session"""
    if not db_manager:
        raise RuntimeError("Database not initialized. Call initialize_database() first.")
    
    async with db_manager.get_session() as session:
        yield session
