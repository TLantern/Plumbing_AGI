"""
Unified Supabase storage backend
Replaces both DatabaseStorageBackend and SupabaseSalonService with a single, consistent interface
"""

import os
import json
import logging
from typing import Dict, List, Any, Optional
from supabase import create_client, Client
from datetime import datetime
from .cloud_storage import CloudStorageBackend, get_global_storage_backend

logger = logging.getLogger(__name__)

class SupabaseStorageBackend(CloudStorageBackend):
    """Unified Supabase storage backend for all salon data"""
    
    def __init__(self):
        # Get Supabase URL and key from environment
        self.supabase_url = os.getenv("SUPABASE_URL")
        self.supabase_key = os.getenv("SUPABASE_ANON_KEY")
        
        # Fallback: if SUPABASE_URL is not set, try to use DATABASE_URL
        if not self.supabase_url:
            database_url = os.getenv("DATABASE_URL")
            if database_url and "supabase.co" in database_url:
                # Convert database URL to API URL
                # db.yzoalegdsogecfiqzfbp.supabase.co -> yzoalegdsogecfiqzfbp.supabase.co
                if database_url.startswith("https://db."):
                    project_ref = database_url.replace("https://db.", "").replace(".supabase.co", "")
                    self.supabase_url = f"https://{project_ref}.supabase.co"
                else:
                    self.supabase_url = database_url
                logger.info(f"🔄 Using DATABASE_URL as SUPABASE_URL: {self.supabase_url}")
        
        if not self.supabase_url:
            raise ValueError("SUPABASE_URL environment variable is required")
        if not self.supabase_key:
            raise ValueError("SUPABASE_ANON_KEY environment variable is required")
        
        self.supabase: Client = create_client(self.supabase_url, self.supabase_key)
        logger.info(f"✅ Supabase storage initialized: {self.supabase_url}")
    
    async def _ensure_tables_exist(self):
        """Ensure all required tables exist"""
        try:
            # Create salon_static_data table for knowledge storage
            await self.supabase.rpc('create_salon_static_data_table').execute()
        except Exception as e:
            logger.warning(f"Table creation RPC not available, tables may already exist: {e}")
    
    # ===== CLOUD STORAGE INTERFACE METHODS =====
    
    async def store_data(self, key: str, data: Dict[str, Any]) -> bool:
        """Store data (CloudStorageBackend interface)"""
        return await self.store_knowledge(key, data)
    
    async def retrieve_data(self, key: str) -> Optional[Dict[str, Any]]:
        """Retrieve data (CloudStorageBackend interface)"""
        return await self.retrieve_knowledge(key)
    
    async def list_keys(self) -> List[str]:
        """List all keys (CloudStorageBackend interface)"""
        return await self.list_knowledge_keys()
    
    async def delete_data(self, key: str) -> bool:
        """Delete data (CloudStorageBackend interface)"""
        return await self.delete_knowledge(key)
    
    async def exists(self, key: str) -> bool:
        """Check if key exists (CloudStorageBackend interface)"""
        return await self.knowledge_exists(key)
    
    # ===== KNOWLEDGE STORAGE METHODS =====
    
    async def store_knowledge(self, key: str, data: Dict[str, Any]) -> bool:
        """Store knowledge data (replaces DatabaseStorageBackend.store_data)"""
        try:
            await self._ensure_tables_exist()
            
            result = await self.supabase.table('salon_static_data').upsert({
                'key': key,
                'data': data,
                'updated_at': datetime.utcnow().isoformat()
            }).execute()
            
            logger.info(f"✅ Stored knowledge {key} to Supabase")
            return True
            
        except Exception as e:
            logger.warning(f"⚠️ salon_static_data table not found, using fallback: {e}")
            # Fallback: try to store to existing services table
            try:
                if key.startswith('location_') and 'services' in data:
                    # Extract salon ID from key
                    salon_id = key.replace('location_', '')
                    services = data.get('services', [])
                    
                    # Store services to the existing services table
                    for service in services:
                        service_data = {
                            'salon_id': salon_id,
                            'name': service.get('name', ''),
                            'average_price_cents': service.get('price_cents', 0),
                            'is_active': True
                        }
                        self.supabase.table('services').upsert(service_data).execute()
                    
                    logger.info(f"✅ Stored {len(services)} services to fallback services table")
                    return True
                return False
            except Exception as e2:
                logger.error(f"❌ Error storing knowledge to fallback: {e2}")
                return False
    
    async def retrieve_knowledge(self, key: str) -> Optional[Dict[str, Any]]:
        """Retrieve knowledge data (replaces DatabaseStorageBackend.retrieve_data)"""
        try:
            result = await self.supabase.table('salon_static_data').select('data').eq('key', key).execute()
            
            if result.data and len(result.data) > 0:
                return result.data[0]['data']
            return None
            
        except Exception as e:
            logger.warning(f"⚠️ salon_static_data table not found, using fallback: {e}")
            # Fallback: try to get data from existing services table
            try:
                if key.startswith('location_'):
                    # Extract salon ID from key
                    salon_id = key.replace('location_', '')
                    result = self.supabase.table('services').select('*').eq('salon_id', salon_id).execute()
                    if result.data:
                        # Convert services to knowledge format
                        services = result.data
                        return {
                            'services': services,
                            'location_id': salon_id,
                            'source': 'fallback_services_table'
                        }
                return None
            except Exception as e2:
                logger.error(f"❌ Error retrieving knowledge from fallback: {e2}")
                return None
    
    async def list_knowledge_keys(self) -> List[str]:
        """List all knowledge keys (replaces DatabaseStorageBackend.list_keys)"""
        try:
            result = await self.supabase.table('salon_static_data').select('key').execute()
            return [row['key'] for row in result.data] if result.data else []
            
        except Exception as e:
            logger.warning(f"⚠️ salon_static_data table not found, using fallback: {e}")
            # Fallback: try to get keys from existing services table
            try:
                result = self.supabase.table('services').select('id').execute()
                if result.data:
                    # Create location keys from service IDs
                    return [f"location_{row['id']}" for row in result.data]
                return []
            except Exception as e2:
                logger.error(f"❌ Error listing keys from fallback: {e2}")
                return []
    
    async def delete_knowledge(self, key: str) -> bool:
        """Delete knowledge data"""
        try:
            await self.supabase.table('salon_static_data').delete().eq('key', key).execute()
            logger.info(f"✅ Deleted knowledge {key}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error deleting knowledge {key}: {e}")
            return False
    
    async def knowledge_exists(self, key: str) -> bool:
        """Check if knowledge exists"""
        try:
            result = await self.supabase.table('salon_static_data').select('key').eq('key', key).execute()
            return len(result.data) > 0 if result.data else False
            
        except Exception as e:
            logger.error(f"❌ Error checking knowledge existence {key}: {e}")
            return False
    
    # ===== SALON DATA METHODS =====
    
    async def insert_scraped_services(self, services_data: List[Dict[str, Any]], salon_id: str) -> Dict[str, Any]:
        """Insert scraped services data (from SupabaseSalonService)"""
        try:
            # Prepare data for insertion
            insert_data = []
            for service in services_data:
                service_data = {
                    'salon_id': salon_id,
                    'service_name': service.get('name', ''),
                    'description': service.get('description', ''),
                    'price': service.get('price', ''),
                    'duration': service.get('duration', ''),
                    'category': service.get('category', ''),
                    'raw_data': service,
                    'created_at': datetime.utcnow().isoformat()
                }
                insert_data.append(service_data)
            
            result = await self.supabase.table('scraped_services').upsert(insert_data).execute()
            
            logger.info(f"✅ Inserted {len(insert_data)} services for salon {salon_id}")
            return {
                'success': True,
                'inserted_count': len(insert_data),
                'salon_id': salon_id
            }
            
        except Exception as e:
            logger.error(f"❌ Error inserting scraped services: {e}")
            return {
                'success': False,
                'error': str(e),
                'salon_id': salon_id
            }
    
    async def get_salon_services(self, salon_id: str) -> List[Dict[str, Any]]:
        """Get all services for a salon"""
        try:
            result = await self.supabase.table('scraped_services').select('*').eq('salon_id', salon_id).execute()
            return result.data if result.data else []
            
        except Exception as e:
            logger.error(f"❌ Error getting salon services: {e}")
            return []
    
    async def insert_salon_info(self, salon_data: Dict[str, Any]) -> Dict[str, Any]:
        """Insert salon information"""
        try:
            salon_data['created_at'] = datetime.utcnow().isoformat()
            result = await self.supabase.table('salon_info').upsert(salon_data).execute()
            
            logger.info(f"✅ Inserted salon info: {salon_data.get('name', 'Unknown')}")
            return {
                'success': True,
                'salon_data': salon_data
            }
            
        except Exception as e:
            logger.error(f"❌ Error inserting salon info: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def get_salon_info(self, salon_id: str) -> Optional[Dict[str, Any]]:
        """Get salon information"""
        try:
            result = await self.supabase.table('salon_info').select('*').eq('id', salon_id).execute()
            return result.data[0] if result.data and len(result.data) > 0 else None
            
        except Exception as e:
            logger.error(f"❌ Error getting salon info: {e}")
            return None

# Global instance - lazy initialization
supabase_storage = None

def get_supabase_storage():
    """Get the global Supabase storage instance"""
    global supabase_storage
    if supabase_storage is None:
        supabase_storage = SupabaseStorageBackend()
    return supabase_storage
