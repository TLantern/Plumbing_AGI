"""
Database storage for static salon data
Uses PostgreSQL JSONB for persistent storage in Heroku deployment
"""

import json
import logging
import os
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

class CloudStorageBackend(ABC):
    """Abstract base class for cloud storage backends"""
    
    @abstractmethod
    async def store_data(self, key: str, data: Dict[str, Any]) -> bool:
        """Store data with given key"""
        pass
    
    @abstractmethod
    async def retrieve_data(self, key: str) -> Optional[Dict[str, Any]]:
        """Retrieve data by key"""
        pass
    
    @abstractmethod
    async def list_keys(self) -> List[str]:
        """List all available keys"""
        pass
    
    @abstractmethod
    async def delete_data(self, key: str) -> bool:
        """Delete data by key"""
        pass
    
    @abstractmethod
    async def exists(self, key: str) -> bool:
        """Check if key exists"""
        pass


class DatabaseStorageBackend(CloudStorageBackend):
    """PostgreSQL database as storage backend"""
    
    def __init__(self):
        # Import here to avoid circular imports
        from .database import db_manager
        self.db_manager = db_manager
    
    async def _ensure_table_exists(self):
        """Create storage table if it doesn't exist"""
        try:
            from sqlalchemy import text  # type: ignore
            if not self.db_manager:
                logger.error("Database manager not initialized")
                return
            async with self.db_manager.get_session() as session:
                await session.execute(text("""
                    CREATE TABLE IF NOT EXISTS salon_static_data (
                        key VARCHAR(255) PRIMARY KEY,
                        data JSONB NOT NULL,
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                        updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                    )
                """))
                await session.commit()
        except Exception as e:
            logger.error(f"❌ Error creating storage table: {e}")
    
    async def store_data(self, key: str, data: Dict[str, Any]) -> bool:
        """Store data in database"""
        await self._ensure_table_exists()
        
        try:
            from sqlalchemy import text  # type: ignore
            if not self.db_manager:
                logger.error("Database manager not initialized")
                return False
            async with self.db_manager.get_session() as session:
                await session.execute(text("""
                    INSERT INTO salon_static_data (key, data, updated_at) 
                    VALUES (:key, :data, NOW())
                    ON CONFLICT (key) 
                    DO UPDATE SET data = :data, updated_at = NOW()
                """), {"key": key, "data": json.dumps(data, default=str)})
                await session.commit()
                logger.info(f"✅ Stored {key} to database")
                return True
        except Exception as e:
            logger.error(f"❌ Error storing {key} to database: {e}")
            return False
    
    async def retrieve_data(self, key: str) -> Optional[Dict[str, Any]]:
        """Retrieve data from database"""
        await self._ensure_table_exists()
        
        try:
            from sqlalchemy import text  # type: ignore
            if not self.db_manager:
                logger.error("Database manager not initialized")
                return None
            async with self.db_manager.get_session() as session:
                result = await session.execute(text("""
                    SELECT data FROM salon_static_data WHERE key = :key
                """), {"key": key})
                row = result.fetchone()
                
                if row:
                    return json.loads(row[0])
                return None
        except Exception as e:
            logger.error(f"❌ Error retrieving {key} from database: {e}")
            return None
    
    async def list_keys(self) -> List[str]:
        """List all keys in database"""
        await self._ensure_table_exists()
        
        try:
            from sqlalchemy import text  # type: ignore
            if not self.db_manager:
                logger.error("Database manager not initialized")
                return []
            async with self.db_manager.get_session() as session:
                result = await session.execute(text("SELECT key FROM salon_static_data"))
                rows = result.fetchall()
                return [row[0] for row in rows]
        except Exception as e:
            logger.error(f"❌ Error listing database keys: {e}")
            return []
    
    async def delete_data(self, key: str) -> bool:
        """Delete data from database"""
        await self._ensure_table_exists()
        
        try:
            from sqlalchemy import text  # type: ignore
            if not self.db_manager:
                logger.error("Database manager not initialized")
                return False
            async with self.db_manager.get_session() as session:
                await session.execute(text("DELETE FROM salon_static_data WHERE key = :key"), {"key": key})
                await session.commit()
                return True
        except Exception as e:
            logger.error(f"❌ Error deleting {key} from database: {e}")
            return False
    
    async def exists(self, key: str) -> bool:
        """Check if key exists in database"""
        await self._ensure_table_exists()
        
        try:
            from sqlalchemy import text  # type: ignore
            if not self.db_manager:
                logger.error("Database manager not initialized")
                return False
            async with self.db_manager.get_session() as session:
                result = await session.execute(text("""
                    SELECT 1 FROM salon_static_data WHERE key = :key LIMIT 1
                """), {"key": key})
                return result.fetchone() is not None
        except Exception:
            return False

class LocalFileBackend(CloudStorageBackend):
    """Local filesystem backend (for development only)"""
    
    def __init__(self, data_directory: str = "./salon_data"):
        self.data_directory = data_directory
        os.makedirs(data_directory, exist_ok=True)
    
    def _get_file_path(self, key: str) -> str:
        return os.path.join(self.data_directory, f"{key}.json")
    
    async def store_data(self, key: str, data: Dict[str, Any]) -> bool:
        try:
            file_path = self._get_file_path(key)
            with open(file_path, 'w') as f:
                json.dump(data, f, indent=2, default=str)
            return True
        except Exception as e:
            logger.error(f"❌ Error storing {key} locally: {e}")
            return False
    
    async def retrieve_data(self, key: str) -> Optional[Dict[str, Any]]:
        try:
            file_path = self._get_file_path(key)
            if os.path.exists(file_path):
                with open(file_path, 'r') as f:
                    return json.load(f)
            return None
        except Exception as e:
            logger.error(f"❌ Error retrieving {key} locally: {e}")
            return None
    
    async def list_keys(self) -> List[str]:
        try:
            keys = []
            for filename in os.listdir(self.data_directory):
                if filename.endswith(".json"):
                    keys.append(filename[:-5])  # Remove .json extension
            return keys
        except Exception:
            return []
    
    async def delete_data(self, key: str) -> bool:
        try:
            file_path = self._get_file_path(key)
            if os.path.exists(file_path):
                os.remove(file_path)
            return True
        except Exception as e:
            logger.error(f"❌ Error deleting {key} locally: {e}")
            return False
    
    async def exists(self, key: str) -> bool:
        return os.path.exists(self._get_file_path(key))

def get_storage_backend() -> CloudStorageBackend:
    """Get the unified Supabase storage backend"""
    
    # Check for Supabase configuration
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_ANON_KEY")
    
    if supabase_url and supabase_key:
        logger.info("🚀 Using unified Supabase storage backend")
        from .supabase_storage import get_supabase_storage
        return get_supabase_storage()
    
    # Fallback to local storage only for development
    logger.warning("⚠️ No Supabase configuration found, using local file storage (development only)")
    return LocalFileBackend()

# Global storage backend - lazy initialization to avoid circular imports
storage_backend = None

def get_global_storage_backend():
    """Get the global storage backend with lazy initialization"""
    global storage_backend
    if storage_backend is None:
        storage_backend = get_storage_backend()
    return storage_backend
