"""
Unified Supabase Service for Salon Phone System
Integrates with the main webpage backend schema for seamless shop management and admin oversight
"""

import os
import json
import logging
import uuid
from typing import Dict, List, Any, Optional, Union
from supabase import create_client, Client
from datetime import datetime, timezone
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class CallData:
    """Structured call data for Supabase storage"""
    call_sid: str
    salon_id: str
    caller_phone: str
    caller_name: Optional[str] = None
    call_type: str = "answered"
    outcome: str = "in_progress"
    intent: Optional[str] = None
    sentiment: Optional[str] = None
    duration_seconds: int = 0
    timestamp: Optional[str] = None

@dataclass
class AppointmentData:
    """Structured appointment data for Supabase storage"""
    salon_id: str
    call_id: Optional[str] = None
    service_id: Optional[str] = None
    appointment_date: Optional[str] = None
    status: str = "pending"
    estimated_revenue_cents: int = 0

class UnifiedSupabaseService:
    """Unified Supabase service that matches the main webpage schema"""
    
    def __init__(self):
        # Use the same Supabase credentials as the main webpage
        self.supabase_url = os.getenv("SUPABASE_URL", "https://yzoalegdsogecfiqzfbp.supabase.co")
        self.supabase_key = os.getenv("SUPABASE_ANON_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Inl6b2FsZWdkc29nZWNmaXF6ZmJwIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTc2NTMyNzIsImV4cCI6MjA3MzIyOTI3Mn0.rZe11f29kVYP9_oI3ER6NAHPrYs5r6U4ksasV272HGw")
        
        if not self.supabase_url or not self.supabase_key:
            raise ValueError("SUPABASE_URL and SUPABASE_ANON_KEY environment variables are required")
        
        self.supabase: Client = create_client(self.supabase_url, self.supabase_key)
        logger.info(f"✅ Unified Supabase service initialized: {self.supabase_url}")
    
    # ===== SHOP MANAGEMENT =====
    
    async def create_or_update_shop(self, shop_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create or update a shop profile (matches main webpage profiles table)"""
        try:
            # Ensure we have required fields
            if 'salon_name' not in shop_data:
                raise ValueError("salon_name is required")
            
            # Generate or use existing UUID
            shop_id = shop_data.get('salon_id', shop_data.get('id'))
            if shop_id and not self._is_valid_uuid(shop_id):
                # Convert string ID to UUID
                shop_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"salon_{shop_id}"))
            elif not shop_id:
                shop_id = str(uuid.uuid4())
            
            # Create profile data matching the main webpage schema
            profile_data = {
                'id': shop_id,
                'salon_name': shop_data['salon_name'],
                'phone': shop_data.get('phone'),
                'timezone': shop_data.get('timezone', 'America/New_York'),
                'created_at': datetime.now(timezone.utc).isoformat(),
                'updated_at': datetime.now(timezone.utc).isoformat()
            }
            
            # Insert/update profile
            result = self.supabase.table('profiles').upsert(profile_data).execute()
            
            # Also store detailed salon info if provided
            if any(key in shop_data for key in ['business_name', 'website_url', 'address', 'hours']):
                salon_info_data = {
                    'id': profile_data['id'],
                    'salon_id': profile_data['id'],
                    'business_name': shop_data.get('business_name', shop_data['salon_name']),
                    'website_url': shop_data.get('website_url'),
                    'phone': shop_data.get('phone'),
                    'address': shop_data.get('address'),
                    'hours': shop_data.get('hours'),
                    'faq_items': shop_data.get('faq_items'),
                    'created_at': datetime.now(timezone.utc).isoformat(),
                    'updated_at': datetime.now(timezone.utc).isoformat()
                }
                
                self.supabase.table('salon_info').upsert(salon_info_data).execute()
            
            logger.info(f"✅ Shop created/updated: {shop_data['salon_name']}")
            return {
                'success': True,
                'shop_id': profile_data['id'],
                'data': profile_data
            }
            
        except Exception as e:
            logger.error(f"❌ Error creating/updating shop: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def get_shop(self, shop_id: str) -> Optional[Dict[str, Any]]:
        """Get shop information"""
        try:
            # Get profile data
            profile_result = self.supabase.table('profiles').select('*').eq('id', shop_id).execute()
            if not profile_result.data:
                return None
            
            profile = profile_result.data[0]
            
            # Get additional salon info
            info_result = self.supabase.table('salon_info').select('*').eq('salon_id', shop_id).execute()
            salon_info = info_result.data[0] if info_result.data else {}
            
            # Combine data
            return {
                **profile,
                **salon_info
            }
            
        except Exception as e:
            logger.error(f"❌ Error getting shop {shop_id}: {e}")
            return None
    
    async def list_all_shops(self) -> List[Dict[str, Any]]:
        """List all shops with their basic info"""
        try:
            result = self.supabase.table('profiles').select('*').execute()
            return result.data if result.data else []
            
        except Exception as e:
            logger.error(f"❌ Error listing shops: {e}")
            return []
    
    # ===== CALL MANAGEMENT =====
    
    async def log_call(self, call_data: CallData) -> Dict[str, Any]:
        """Log a call to the calls table (matches main webpage schema)"""
        try:
            # Generate UUIDs for call and salon IDs
            call_id = self._generate_uuid_from_string(call_data.call_sid, "call")
            salon_id = call_data.salon_id
            if not self._is_valid_uuid(salon_id):
                salon_id = self._generate_uuid_from_string(salon_id, "salon")
            
            # Prepare call data matching the main webpage schema
            call_record = {
                'id': call_id,
                'salon_id': salon_id,
                'timestamp': call_data.timestamp or datetime.now(timezone.utc).isoformat(),
                'call_type': call_data.call_type,
                'outcome': call_data.outcome,
                'intent': call_data.intent,
                'sentiment': call_data.sentiment,
                'caller_name_masked': call_data.caller_name,
                'caller_phone_masked': self._mask_phone(call_data.caller_phone),
                'duration_seconds': call_data.duration_seconds,
                'hour_of_day': self._extract_hour(call_data.timestamp),
                'created_at': datetime.now(timezone.utc).isoformat()
            }
            
            result = self.supabase.table('calls').upsert(call_record).execute()
            
            logger.info(f"✅ Call logged: {call_data.call_sid} -> {call_data.outcome}")
            return {
                'success': True,
                'call_id': call_data.call_sid,
                'data': call_record
            }
            
        except Exception as e:
            logger.error(f"❌ Error logging call: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def update_call_outcome(self, call_sid: str, outcome: str, intent: str = None, sentiment: str = None) -> bool:
        """Update call outcome after completion"""
        try:
            # Generate UUID for call ID
            call_id = self._generate_uuid_from_string(call_sid, "call")
            
            update_data = {
                'outcome': outcome
            }
            
            if intent:
                update_data['intent'] = intent
            if sentiment:
                update_data['sentiment'] = sentiment
            
            result = self.supabase.table('calls').update(update_data).eq('id', call_id).execute()
            
            logger.info(f"✅ Call outcome updated: {call_sid} -> {outcome}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error updating call outcome: {e}")
            return False
    
    # ===== APPOINTMENT MANAGEMENT =====
    
    async def create_appointment(self, appointment_data: AppointmentData) -> Dict[str, Any]:
        """Create an appointment (matches main webpage schema)"""
        try:
            # Generate UUIDs
            appointment_id = str(uuid.uuid4())
            salon_id = appointment_data.salon_id
            if not self._is_valid_uuid(salon_id):
                salon_id = self._generate_uuid_from_string(salon_id, "salon")
            
            call_id = None
            if appointment_data.call_id:
                call_id = self._generate_uuid_from_string(appointment_data.call_id, "call")
            
            service_id = None
            if appointment_data.service_id:
                service_id = self._generate_uuid_from_string(appointment_data.service_id, "service")
            
            appointment_record = {
                'id': appointment_id,
                'salon_id': salon_id,
                'call_id': call_id,
                'service_id': service_id,
                'appointment_date': appointment_data.appointment_date,
                'status': appointment_data.status,
                'estimated_revenue_cents': appointment_data.estimated_revenue_cents,
                'created_at': datetime.now(timezone.utc).isoformat(),
                'updated_at': datetime.now(timezone.utc).isoformat()
            }
            
            result = self.supabase.table('appointments').upsert(appointment_record).execute()
            
            logger.info(f"✅ Appointment created: {appointment_record['id']}")
            return {
                'success': True,
                'appointment_id': appointment_record['id'],
                'data': appointment_record
            }
            
        except Exception as e:
            logger.error(f"❌ Error creating appointment: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    # ===== SERVICES MANAGEMENT =====
    
    async def store_services(self, salon_id: str, services: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Store services for a salon (matches main webpage schema)"""
        try:
            # Convert salon_id to UUID if needed
            salon_uuid = salon_id
            if not self._is_valid_uuid(salon_id):
                salon_uuid = self._generate_uuid_from_string(salon_id, "salon")
            
            # Store in both services and scraped_services tables for compatibility
            services_data = []
            scraped_services_data = []
            
            for service in services:
                service_name = service.get('name', '')
                service_uuid = self._generate_uuid_from_string(f"{salon_id}_{service_name}", "service")
                
                # Main services table
                service_record = {
                    'id': service_uuid,
                    'salon_id': salon_uuid,
                    'name': service_name,
                    'average_price_cents': service.get('price_cents', 0),
                    'is_active': True,
                    'created_at': datetime.now(timezone.utc).isoformat(),
                    'updated_at': datetime.now(timezone.utc).isoformat()
                }
                services_data.append(service_record)
                
                # Scraped services table (for detailed info)
                scraped_uuid = self._generate_uuid_from_string(f"scraped_{salon_id}_{service_name}", "scraped_service")
                scraped_record = {
                    'id': scraped_uuid,
                    'salon_id': salon_uuid,
                    'service_name': service_name,
                    'description': service.get('description', ''),
                    'price': service.get('price', ''),
                    'duration': service.get('duration', ''),
                    'category': service.get('category', ''),
                    'raw_data': service,
                    'created_at': datetime.now(timezone.utc).isoformat(),
                    'updated_at': datetime.now(timezone.utc).isoformat()
                }
                scraped_services_data.append(scraped_record)
            
            # Insert into both tables
            self.supabase.table('services').upsert(services_data).execute()
            self.supabase.table('scraped_services').upsert(scraped_services_data).execute()
            
            logger.info(f"✅ Stored {len(services)} services for salon {salon_id}")
            return {
                'success': True,
                'services_count': len(services),
                'salon_id': salon_id
            }
            
        except Exception as e:
            logger.error(f"❌ Error storing services: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def get_shop_services(self, salon_id: str) -> List[Dict[str, Any]]:
        """Get services for a salon"""
        try:
            result = self.supabase.table('services').select('*').eq('salon_id', salon_id).eq('is_active', True).execute()
            return result.data if result.data else []
            
        except Exception as e:
            logger.error(f"❌ Error getting shop services: {e}")
            return []
    
    # ===== ANALYTICS & REPORTING =====
    
    async def get_shop_metrics(self, salon_id: str, days: int = 30) -> Dict[str, Any]:
        """Get shop metrics using the main webpage functions"""
        try:
            # Convert salon_id to UUID if needed
            salon_uuid = salon_id
            if not self._is_valid_uuid(salon_id):
                salon_uuid = self._generate_uuid_from_string(salon_id, "salon")
            
            # Use the get_salon_kpis function from the main webpage
            result = self.supabase.rpc('get_salon_kpis', {
                'p_salon_id': salon_uuid,
                'p_days': days
            }).execute()
            
            if result.data and len(result.data) > 0:
                return result.data[0]
            else:
                return {
                    'revenue_recovered_cents': 0,
                    'calls_answered': 0,
                    'appointments_booked': 0,
                    'conversion_rate': 0.0
                }
                
        except Exception as e:
            logger.error(f"❌ Error getting shop metrics: {e}")
            return {
                'revenue_recovered_cents': 0,
                'calls_answered': 0,
                'appointments_booked': 0,
                'conversion_rate': 0.0,
                'error': str(e)
            }
    
    async def get_calls_timeseries(self, salon_id: str, days: int = 30) -> List[Dict[str, Any]]:
        """Get calls timeseries data"""
        try:
            # Convert salon_id to UUID if needed
            salon_uuid = salon_id
            if not self._is_valid_uuid(salon_id):
                salon_uuid = self._generate_uuid_from_string(salon_id, "salon")
            
            result = self.supabase.rpc('get_calls_timeseries', {
                'p_salon_id': salon_uuid,
                'p_days': days
            }).execute()
            
            return result.data if result.data else []
            
        except Exception as e:
            logger.error(f"❌ Error getting calls timeseries: {e}")
            return []
    
    async def get_platform_metrics(self) -> Dict[str, Any]:
        """Get platform-wide metrics for admin oversight"""
        try:
            result = self.supabase.rpc('get_platform_metrics').execute()
            
            if result.data and len(result.data) > 0:
                return result.data[0]
            else:
                return {
                    'total_salons': 0,
                    'active_salons': 0,
                    'total_calls': 0,
                    'total_appointments': 0,
                    'total_revenue_cents': 0
                }
                
        except Exception as e:
            logger.error(f"❌ Error getting platform metrics: {e}")
            return {
                'total_salons': 0,
                'active_salons': 0,
                'total_calls': 0,
                'total_appointments': 0,
                'total_revenue_cents': 0,
                'error': str(e)
            }
    
    # ===== UTILITY METHODS =====
    
    def _mask_phone(self, phone: str) -> str:
        """Mask phone number for privacy"""
        if not phone or len(phone) < 4:
            return phone
        
        # Keep first 3 and last 3 digits, mask the middle
        if len(phone) >= 10:
            return f"{phone[:3]}***{phone[-3:]}"
        else:
            return f"{phone[:2]}***{phone[-2:]}"
    
    def _extract_hour(self, timestamp: str) -> Optional[int]:
        """Extract hour of day from timestamp"""
        try:
            if timestamp:
                dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                return dt.hour
        except Exception:
            pass
        return None
    
    def _is_valid_uuid(self, value: str) -> bool:
        """Check if a string is a valid UUID"""
        try:
            uuid.UUID(value)
            return True
        except ValueError:
            return False
    
    def _generate_uuid_from_string(self, value: str, namespace: str = "default") -> str:
        """Generate a consistent UUID from a string"""
        return str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{namespace}_{value}"))

# Global instance
_unified_supabase_service = None

def get_unified_supabase_service() -> UnifiedSupabaseService:
    """Get the global unified Supabase service instance"""
    global _unified_supabase_service
    if _unified_supabase_service is None:
        _unified_supabase_service = UnifiedSupabaseService()
    return _unified_supabase_service
