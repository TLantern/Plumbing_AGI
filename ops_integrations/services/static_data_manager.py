"""
Static data management for salon location information
Handles one-time scraping and persistent cloud storage of location data
"""

import json
import logging
import os
from datetime import datetime
from typing import Dict, Any, List, Optional
from .website_scraper import SalonWebsiteScraper, ScrapedLocationInfo
from .knowledge_service import knowledge_service
from .cloud_storage import storage_backend

logger = logging.getLogger(__name__)

class StaticDataManager:
    """Manages static location data with cloud storage for instant access during calls"""
    
    def __init__(self):
        self.storage = storage_backend
        
    def _get_location_key(self, location_id: int) -> str:
        """Get storage key for a location"""
        return f"location_{location_id}"
    
    async def data_exists(self, location_id: int) -> bool:
        """Check if data exists for a location"""
        key = self._get_location_key(location_id)
        return await self.storage.exists(key)
    
    async def get_data_age(self, location_id: int) -> Optional[int]:
        """Get age of data in days"""
        key = self._get_location_key(location_id)
        
        try:
            data = await self.storage.retrieve_data(key)
            if not data:
                return None
            
            scraped_at = datetime.fromisoformat(data['scraped_at'])
            age_days = (datetime.now() - scraped_at).days
            return age_days
        except Exception as e:
            logger.error(f"Error getting data age for location {location_id}: {e}")
            return None
    
    async def scrape_and_store_location_data(
        self, 
        location_id: int, 
        website_url: str,
        force_update: bool = False
    ) -> Dict[str, Any]:
        """Scrape website data and store it in cloud storage"""
        
        key = self._get_location_key(location_id)
        
        # Check if we should skip scraping
        if not force_update and await self.data_exists(location_id):
            age_days = await self.get_data_age(location_id)
            if age_days is not None and age_days < 7:  # Data less than 7 days old
                logger.info(f"Location {location_id} data is {age_days} days old, skipping scrape")
                return {
                    'status': 'skipped',
                    'reason': f'Data is only {age_days} days old',
                    'storage_key': key
                }
        
        logger.info(f"🔍 Scraping website data for location {location_id}: {website_url}")
        
        try:
            async with SalonWebsiteScraper() as scraper:
                scraped_info = await scraper.scrape_salon_website(website_url)
                
                # Create comprehensive data structure
                static_data = {
                    'location_id': location_id,
                    'scraped_at': scraped_info.scraped_at.isoformat(),
                    'source_url': website_url,
                    'business_info': {
                        'name': scraped_info.business_name,
                        'url': scraped_info.location_url,
                        'phone': scraped_info.phone,
                        'address': scraped_info.address,
                        'hours': scraped_info.hours
                    },
                    'services': [
                        {
                            'name': service.name,
                            'description': service.description,
                            'price_text': service.price_text,
                            'price_cents': service.price_cents,
                            'duration_text': service.duration_text,
                            'duration_min': service.duration_min,
                            'category': service.category,
                            'professional_name': service.professional_name,
                            'professional_bio': service.professional_bio,
                            'specialties': service.specialties,
                            'image_url': service.image_url
                        }
                        for service in scraped_info.services
                    ],
                    'professionals': [
                        {
                            'name': prof.name,
                            'title': prof.title,
                            'bio': prof.bio,
                            'specialties': prof.specialties,
                            'experience_years': prof.experience_years,
                            'certifications': prof.certifications,
                            'image_url': prof.image_url
                        }
                        for prof in scraped_info.professionals
                    ],
                    'faq': scraped_info.faq_items,
                    'stats': {
                        'services_count': len(scraped_info.services),
                        'professionals_count': len(scraped_info.professionals),
                        'faq_count': len(scraped_info.faq_items),
                        'categories': list(set(s.category for s in scraped_info.services if s.category))
                    }
                }
                
                # Store to cloud storage
                success = await self.storage.store_data(key, static_data)
                
                if success:
                    # Update in-memory cache immediately
                    knowledge_service.refresh_location_knowledge(location_id)
                    
                    logger.info(f"✅ Scraped and stored data for location {location_id}")
                    logger.info(f"   🔗 Storage key: {key}")
                    logger.info(f"   📊 Services: {static_data['stats']['services_count']}")
                    logger.info(f"   👥 Professionals: {static_data['stats']['professionals_count']}")
                    logger.info(f"   ❓ FAQ items: {static_data['stats']['faq_count']}")
                    
                    return {
                        'status': 'success',
                        'storage_key': key,
                        'stats': static_data['stats'],
                        'business_name': scraped_info.business_name
                    }
                else:
                    return {
                        'status': 'error',
                        'error': 'Failed to store data to cloud storage',
                        'storage_key': key
                    }
                
        except Exception as e:
            logger.error(f"❌ Failed to scrape location {location_id}: {e}")
            return {
                'status': 'error',
                'error': str(e),
                'storage_key': key
            }
    
    async def list_all_locations(self) -> List[Dict[str, Any]]:
        """List all locations with stored data"""
        locations = []
        
        try:
            # Get all storage keys
            keys = await self.storage.list_keys()
            
            for key in keys:
                if key.startswith("location_"):
                    try:
                        location_id = int(key.replace("location_", ""))
                        data = await self.storage.retrieve_data(key)
                        
                        if data:
                            age_days = await self.get_data_age(location_id)
                            
                            locations.append({
                                'location_id': location_id,
                                'business_name': data['business_info']['name'],
                                'scraped_at': data['scraped_at'],
                                'source_url': data['source_url'],
                                'stats': data['stats'],
                                'storage_key': key,
                                'age_days': age_days
                            })
                    except Exception as e:
                        logger.warning(f"Error reading location data for key {key}: {e}")
            
            return sorted(locations, key=lambda x: x['location_id'])
            
        except Exception as e:
            logger.error(f"Error listing locations: {e}")
            return []
    
    async def get_location_summary(self, location_id: int) -> Optional[Dict[str, Any]]:
        """Get summary information for a location"""
        key = self._get_location_key(location_id)
        
        try:
            data = await self.storage.retrieve_data(key)
            if not data:
                return None
            
            age_days = await self.get_data_age(location_id)
            
            return {
                'location_id': location_id,
                'business_name': data['business_info']['name'],
                'scraped_at': data['scraped_at'],
                'age_days': age_days,
                'stats': data['stats'],
                'has_services': data['stats']['services_count'] > 0,
                'has_professionals': data['stats']['professionals_count'] > 0,
                'has_faq': data['stats']['faq_count'] > 0
            }
            
        except Exception as e:
            logger.error(f"Error reading location {location_id} summary: {e}")
            return None
    
    async def create_ai_context_data(self, location_id: int) -> Optional[str]:
        """Create condensed AI context and store it in cloud storage"""
        key = self._get_location_key(location_id)
        
        try:
            # Check if data exists
            if not await self.storage.exists(key):
                return None
            
            # Generate AI context
            context = knowledge_service.get_ai_context_for_location(location_id)
            
            if context:
                # Store AI context as separate key
                context_key = f"ai_context_{location_id}"
                context_data = {
                    'location_id': location_id,
                    'context': context,
                    'created_at': datetime.now().isoformat()
                }
                
                success = await self.storage.store_data(context_key, context_data)
                
                if success:
                    logger.info(f"Created AI context data for location {location_id}")
                    return context_key
                
        except Exception as e:
            logger.error(f"Error creating AI context for location {location_id}: {e}")
        
        return None

# Global static data manager
static_data_manager = StaticDataManager()

async def setup_location_data(location_id: int, website_url: str) -> Dict[str, Any]:
    """One-time setup for location data"""
    result = await static_data_manager.scrape_and_store_location_data(
        location_id, 
        website_url, 
        force_update=True
    )
    
    if result['status'] == 'success':
        # Create AI context data for even faster access
        context_key = await static_data_manager.create_ai_context_data(location_id)
        if context_key:
            result['ai_context_key'] = context_key
    
    return result

async def get_location_status(location_id: int) -> Dict[str, Any]:
    """Get current status of location data"""
    summary = await static_data_manager.get_location_summary(location_id)
    
    if not summary:
        return {
            'status': 'no_data',
            'message': f'No data found for location {location_id}',
            'needs_scraping': True
        }
    
    age_days = summary['age_days'] or 0
    needs_update = age_days > 30  # Suggest update after 30 days
    
    return {
        'status': 'ready',
        'summary': summary,
        'needs_scraping': False,
        'needs_update': needs_update,
        'message': f"Data is {age_days} days old" + (", consider updating" if needs_update else ", current")
    }
