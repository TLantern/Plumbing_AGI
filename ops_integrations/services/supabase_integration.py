"""
Supabase integration for salon data
"""

import os
import json
import logging
from typing import Dict, List, Any, Optional
from supabase import create_client, Client  # type: ignore

logger = logging.getLogger(__name__)

class SupabaseSalonService:
    def __init__(self):
        database_url = os.getenv("DATABASE_URL")
        
        if not database_url:
            raise ValueError("DATABASE_URL environment variable is required")
        
        # Extract Supabase URL and key from DATABASE_URL
        # DATABASE_URL format: postgresql://postgres:[password]@[host]:[port]/postgres
        # We need to convert this to Supabase format
        if database_url.startswith("postgresql://"):
            # Extract components from postgres URL
            import re
            # More flexible regex to handle special characters in password
            match = re.match(r'postgresql://postgres:([^@]+)@([^:]+):(\d+)/(.+)', database_url)
            if match:
                password, host, port, database = match.groups()
                # Convert database hostname to Supabase API URL
                # db.[project-ref].supabase.co -> [project-ref].supabase.co
                if host.startswith('db.'):
                    project_ref = host.replace('db.', '').replace('.supabase.co', '')
                    self.supabase_url = f"https://{project_ref}.supabase.co"
                else:
                    self.supabase_url = f"https://{host}"
                # For Supabase, we typically use the anon key from environment
                self.supabase_key = os.getenv("SUPABASE_ANON_KEY")
                
                if not self.supabase_key:
                    raise ValueError("SUPABASE_ANON_KEY environment variable is required")
            else:
                # Try alternative parsing for URLs with special characters
                try:
                    # Handle URLs with special characters in password
                    import urllib.parse
                    # Find the last @ symbol to split properly
                    last_at_index = database_url.rfind('@')
                    if last_at_index > 0:
                        user_pass_part = database_url[:last_at_index]
                        host_part = database_url[last_at_index + 1:]
                        
                        # Extract password from user:pass part
                        if 'postgresql://postgres:' in user_pass_part:
                            password = user_pass_part.replace('postgresql://postgres:', '')
                            # URL encode the password
                            encoded_password = urllib.parse.quote(password, safe='')
                            encoded_url = f"postgresql://postgres:{encoded_password}@{host_part}"
                            
                            from urllib.parse import urlparse
                            parsed = urlparse(encoded_url)
                            if parsed.hostname:
                                # Convert database hostname to Supabase API URL
                                # db.[project-ref].supabase.co -> [project-ref].supabase.co
                                if parsed.hostname.startswith('db.'):
                                    project_ref = parsed.hostname.replace('db.', '').replace('.supabase.co', '')
                                    self.supabase_url = f"https://{project_ref}.supabase.co"
                                else:
                                    self.supabase_url = f"https://{parsed.hostname}"
                                self.supabase_key = os.getenv("SUPABASE_ANON_KEY")
                                
                                if not self.supabase_key:
                                    raise ValueError("SUPABASE_ANON_KEY environment variable is required")
                            else:
                                raise ValueError("Could not parse DATABASE_URL")
                        else:
                            raise ValueError("Invalid DATABASE_URL format")
                    else:
                        raise ValueError("Invalid DATABASE_URL format")
                except Exception as e:
                    raise ValueError(f"Invalid DATABASE_URL format: {e}")
        else:
            # Assume it's already a Supabase URL
            self.supabase_url = database_url
            self.supabase_key = os.getenv("SUPABASE_ANON_KEY")
            
            if not self.supabase_key:
                raise ValueError("SUPABASE_ANON_KEY environment variable is required")
        
        self.supabase: Client = create_client(self.supabase_url, self.supabase_key)
        logger.info(f"Supabase client initialized with URL: {self.supabase_url}")
    
    async def insert_scraped_services(self, services_data: List[Dict[str, Any]], salon_id: str) -> Dict[str, Any]:
        """Insert scraped services into Supabase"""
        try:
            # Prepare services for insertion
            services_to_insert = []
            
            for service in services_data:
                # Skip services with no price (consultations, etc.)
                if not service.get('price_cents') or service['price_cents'] == 0:
                    continue
                
                service_record = {
                    'salon_id': salon_id,
                    'name': service['name'],
                    'average_price_cents': service['price_cents'],
                    'duration_minutes': service.get('duration_minutes', 60),
                    'category': service.get('category', 'other'),
                    'description': service.get('description', ''),
                    'professional_name': service.get('professional', ''),
                    'created_at': 'now()',
                    'updated_at': 'now()'
                }
                services_to_insert.append(service_record)
            
            if not services_to_insert:
                logger.warning("No services with pricing found to insert")
                return {"status": "warning", "message": "No services with pricing found"}
            
            # Insert services into Supabase
            result = self.supabase.table('services').insert(services_to_insert).execute()
            
            logger.info(f"Successfully inserted {len(services_to_insert)} services into Supabase")
            
            return {
                "status": "success",
                "services_inserted": len(services_to_insert),
                "data": result.data
            }
            
        except Exception as e:
            logger.error(f"Error inserting services into Supabase: {e}")
            return {"status": "error", "message": str(e)}
    
    async def insert_scraped_professionals(self, professionals_data: List[Dict[str, Any]], salon_id: str) -> Dict[str, Any]:
        """Insert scraped professionals into Supabase"""
        try:
            # Prepare professionals for insertion
            professionals_to_insert = []
            
            for prof in professionals_data:
                professional_record = {
                    'salon_id': salon_id,
                    'name': prof['name'],
                    'title': prof.get('title', 'Stylist'),
                    'bio': prof.get('bio', ''),
                    'specialties': json.dumps(prof.get('specialties', [])),
                    'created_at': 'now()',
                    'updated_at': 'now()'
                }
                professionals_to_insert.append(professional_record)
            
            if not professionals_to_insert:
                logger.warning("No professionals found to insert")
                return {"status": "warning", "message": "No professionals found"}
            
            # Insert professionals into Supabase
            result = self.supabase.table('professionals').insert(professionals_to_insert).execute()
            
            logger.info(f"Successfully inserted {len(professionals_to_insert)} professionals into Supabase")
            
            return {
                "status": "success",
                "professionals_inserted": len(professionals_to_insert),
                "data": result.data
            }
            
        except Exception as e:
            logger.error(f"Error inserting professionals into Supabase: {e}")
            return {"status": "error", "message": str(e)}
    
    async def update_salon_info(self, salon_data: Dict[str, Any], salon_id: str) -> Dict[str, Any]:
        """Update salon information in Supabase"""
        try:
            salon_info = {
                'name': salon_data.get('name', ''),
                'address': salon_data.get('address', ''),
                'phone': salon_data.get('phone', ''),
                'website': salon_data.get('website', ''),
                'updated_at': 'now()'
            }
            
            # Update salon information
            result = self.supabase.table('salons').update(salon_info).eq('id', salon_id).execute()
            
            logger.info(f"Successfully updated salon info for {salon_id}")
            
            return {
                "status": "success",
                "data": result.data
            }
            
        except Exception as e:
            logger.error(f"Error updating salon info: {e}")
            return {"status": "error", "message": str(e)}
    
    async def clear_existing_data(self, salon_id: str) -> Dict[str, Any]:
        """Clear existing services and professionals for a salon"""
        try:
            # Delete existing services
            services_result = self.supabase.table('services').delete().eq('salon_id', salon_id).execute()
            
            # Delete existing professionals
            professionals_result = self.supabase.table('professionals').delete().eq('salon_id', salon_id).execute()
            
            logger.info(f"Cleared existing data for salon {salon_id}")
            
            return {
                "status": "success",
                "services_deleted": len(services_result.data) if services_result.data else 0,
                "professionals_deleted": len(professionals_result.data) if professionals_result.data else 0
            }
            
        except Exception as e:
            logger.error(f"Error clearing existing data: {e}")
            return {"status": "error", "message": str(e)}
