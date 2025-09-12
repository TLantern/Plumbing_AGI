"""
Knowledge service to provide AI with comprehensive location information
"""

import json
import logging
import os
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class LocationKnowledge:
    """Complete knowledge base for a location"""
    location_id: int
    business_name: str
    phone: str
    address: str
    hours: Dict[str, str]
    services: List[Dict[str, Any]]
    professionals: List[Dict[str, Any]]
    faq_items: List[Dict[str, str]]
    last_updated: datetime
    
    def get_service_by_name(self, service_name: str) -> Optional[Dict[str, Any]]:
        """Find service by name (case-insensitive partial match)"""
        service_name_lower = service_name.lower()
        for service in self.services:
            if service_name_lower in service['name'].lower():
                return service
        return None
    
    def get_services_by_category(self, category: str) -> List[Dict[str, Any]]:
        """Get all services in a category"""
        return [s for s in self.services if s.get('category') == category]
    
    def get_professional_by_name(self, professional_name: str) -> Optional[Dict[str, Any]]:
        """Find professional by name"""
        professional_name_lower = professional_name.lower()
        for professional in self.professionals:
            if professional_name_lower in professional['name'].lower():
                return professional
        return None
    
    def search_faq(self, query: str) -> List[Dict[str, str]]:
        """Search FAQ items by query"""
        query_lower = query.lower()
        matching_faq = []
        
        for faq in self.faq_items:
            if (query_lower in faq['question'].lower() or 
                query_lower in faq['answer'].lower()):
                matching_faq.append(faq)
        
        return matching_faq
    
    def get_price_range(self) -> Dict[str, int]:
        """Get service price range"""
        prices = [s['price_cents'] for s in self.services if s.get('price_cents')]
        if not prices:
            return {'min': 0, 'max': 0}
        
        return {
            'min': min(prices),
            'max': max(prices)
        }
    
    def get_available_categories(self) -> List[str]:
        """Get all available service categories"""
        categories = set()
        for service in self.services:
            if service.get('category'):
                categories.add(service['category'])
        return sorted(list(categories))

class LocationKnowledgeService:
    """Service to manage and provide location knowledge to AI"""
    
    def __init__(self):
        self.knowledge_cache: Dict[int, LocationKnowledge] = {}
        self.cache_expiry_hours = 24 * 7  # Refresh knowledge every 7 days (static data)
        # Pre-loading will be done on-demand or during startup events
        
    async def _load_all_locations_on_startup(self):
        """Load all available location data into memory at startup"""
        # Import here to avoid circular imports
        from .cloud_storage import storage_backend
        
        try:
            # Get all location keys
            keys = await storage_backend.list_keys()
            
            for key in keys:
                if key.startswith("location_"):
                    try:
                        location_id = int(key.replace("location_", ""))
                        knowledge = await self._load_scraped_data(location_id)
                        if knowledge:
                            self.knowledge_cache[location_id] = knowledge
                            logger.info(f"Pre-loaded knowledge for location {location_id}")
                    except Exception as e:
                        logger.warning(f"Failed to pre-load {key}: {e}")
            
            logger.info(f"Pre-loaded knowledge for {len(self.knowledge_cache)} locations")
            
        except Exception as e:
            logger.warning(f"Failed to pre-load locations from cloud storage: {e}")
            logger.info("Service will load locations on-demand")
    
    async def _load_scraped_data(self, location_id: int) -> Optional[LocationKnowledge]:
        """Load scraped data from cloud storage"""
        try:
            # Import here to avoid circular imports
            from .cloud_storage import storage_backend
            
            # Retrieve data from cloud storage
            key = f"location_{location_id}"
            data = await storage_backend.retrieve_data(key)
            
            if not data:
                logger.warning(f"No data found in cloud storage for location {location_id}")
                return None
            
            # Parse the scraped timestamp
            scraped_at = datetime.fromisoformat(data['scraped_at'])
            
            knowledge = LocationKnowledge(
                location_id=location_id,
                business_name=data['business_info']['name'],
                phone=data['business_info']['phone'],
                address=data['business_info']['address'],
                hours=data['business_info']['hours'],
                services=data['services'],
                professionals=data['professionals'],
                faq_items=data['faq'],
                last_updated=scraped_at
            )
            
            logger.info(f"Loaded knowledge for location {location_id}: {len(knowledge.services)} services, {len(knowledge.professionals)} professionals")
            return knowledge
            
        except Exception as e:
            logger.error(f"Error loading scraped data for location {location_id}: {e}")
            return None
    
    async def get_location_knowledge(self, location_id: int) -> Optional[LocationKnowledge]:
        """Get knowledge for a location from pre-loaded cache (no delays)"""
        
        # Return from cache immediately - no file I/O during calls
        if location_id in self.knowledge_cache:
            return self.knowledge_cache[location_id]
        
        # If not in cache, try to load once
        logger.warning(f"Location {location_id} not in cache, attempting to load")
        knowledge = await self._load_scraped_data(location_id)
        if knowledge:
            self.knowledge_cache[location_id] = knowledge
            return knowledge
        
        return None
    
    async def refresh_location_knowledge(self, location_id: int) -> bool:
        """Force refresh knowledge for a location"""
        knowledge = await self._load_scraped_data(location_id)
        if knowledge:
            self.knowledge_cache[location_id] = knowledge
            return True
        return False
    
    async def get_ai_context_for_location(self, location_id: int) -> str:
        """Generate comprehensive AI context string for a location"""
        knowledge = await self.get_location_knowledge(location_id)
        
        if not knowledge:
            return f"I don't have detailed information about location {location_id} yet. Please provide basic assistance."
        
        # Build comprehensive context
        context_parts = []
        
        # Business info
        context_parts.append(f"BUSINESS: {knowledge.business_name}")
        if knowledge.phone:
            context_parts.append(f"PHONE: {knowledge.phone}")
        if knowledge.address:
            context_parts.append(f"ADDRESS: {knowledge.address}")
        
        # Hours
        if knowledge.hours:
            hours_text = ", ".join([f"{day}: {hours}" for day, hours in knowledge.hours.items()])
            context_parts.append(f"HOURS: {hours_text}")
        
        # Services
        if knowledge.services:
            context_parts.append(f"\nSERVICES ({len(knowledge.services)} available):")
            
            # Group by category
            by_category = {}
            for service in knowledge.services:
                category = service.get('category', 'other')
                if category not in by_category:
                    by_category[category] = []
                by_category[category].append(service)
            
            for category, services in by_category.items():
                context_parts.append(f"\n{category.upper()}:")
                for service in services[:5]:  # Limit to prevent context overflow
                    price_text = f"${service['price_cents']/100:.2f}" if service.get('price_cents') else "Price varies"
                    duration_text = f"{service['duration_min']}min" if service.get('duration_min') else "Duration varies"
                    context_parts.append(f"  • {service['name']} - {price_text}, {duration_text}")
                    if service.get('description'):
                        context_parts.append(f"    {service['description'][:100]}...")
        
        # Professionals
        if knowledge.professionals:
            context_parts.append(f"\nSTAFF ({len(knowledge.professionals)} professionals):")
            for prof in knowledge.professionals[:3]:  # Limit to prevent overflow
                specialties = ", ".join(prof.get('specialties', []))
                context_parts.append(f"  • {prof['name']} - {prof.get('title', 'Stylist')}")
                if specialties:
                    context_parts.append(f"    Specializes in: {specialties}")
                if prof.get('bio'):
                    context_parts.append(f"    {prof['bio'][:100]}...")
        
        # Common FAQ
        if knowledge.faq_items:
            context_parts.append(f"\nCOMMON QUESTIONS:")
            for faq in knowledge.faq_items[:3]:  # Limit to prevent overflow
                context_parts.append(f"  Q: {faq['question']}")
                context_parts.append(f"  A: {faq['answer'][:150]}...")
        
        # Price range
        price_range = knowledge.get_price_range()
        if price_range['max'] > 0:
            context_parts.append(f"\nPRICE RANGE: ${price_range['min']/100:.2f} - ${price_range['max']/100:.2f}")
        
        context_parts.append(f"\nLAST UPDATED: {knowledge.last_updated.strftime('%Y-%m-%d')}")
        
        return "\n".join(context_parts)
    
    async def find_service_matches(self, location_id: int, query: str) -> List[Dict[str, Any]]:
        """Find services matching a query"""
        knowledge = await self.get_location_knowledge(location_id)
        if not knowledge:
            return []
        
        query_lower = query.lower()
        matches = []
        
        for service in knowledge.services:
            # Check name match
            if query_lower in service['name'].lower():
                matches.append({**service, 'match_type': 'name'})
                continue
            
            # Check description match
            if service.get('description') and query_lower in service['description'].lower():
                matches.append({**service, 'match_type': 'description'})
                continue
            
            # Check category match
            if service.get('category') and query_lower in service['category'].lower():
                matches.append({**service, 'match_type': 'category'})
        
        return matches
    
    async def get_booking_suggestions(self, location_id: int, service_query: str) -> Dict[str, Any]:
        """Get booking suggestions based on service query"""
        knowledge = await self.get_location_knowledge(location_id)
        if not knowledge:
            return {'error': 'No location knowledge available'}
        
        matches = await self.find_service_matches(location_id, service_query)
        
        if not matches:
            # Suggest similar services
            suggestions = []
            categories = knowledge.get_available_categories()
            for category in categories:
                category_services = knowledge.get_services_by_category(category)
                if category_services:
                    suggestions.append({
                        'category': category,
                        'services': category_services[:2]  # Top 2 from each category
                    })
            
            return {
                'exact_matches': [],
                'suggestions': suggestions,
                'message': f"No exact matches for '{service_query}'. Here are our available services:"
            }
        
        return {
            'exact_matches': matches,
            'suggestions': [],
            'message': f"Found {len(matches)} services matching '{service_query}'"
        }

# Global knowledge service instance
knowledge_service = LocationKnowledgeService()
