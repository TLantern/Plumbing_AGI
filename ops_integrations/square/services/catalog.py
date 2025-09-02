"""
Square Catalog Service

Handles catalog-related operations for Square API including services and items.
"""

import logging
from typing import List, Dict, Any, Optional

from ..client import SquareClient
from ..exceptions import SquareCatalogError


logger = logging.getLogger(__name__)


class CatalogService:
    """Service for managing Square catalog items and services"""
    
    def __init__(self, client: SquareClient):
        """
        Initialize CatalogService
        
        Args:
            client: Square API client instance
        """
        self.client = client
    
    def list_catalog_items(self, types: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """
        List catalog items with optional type filtering
        
        Args:
            types: List of catalog object types to filter by (e.g., ["ITEM", "ITEM_VARIATION"])
            
        Returns:
            List of catalog objects
            
        Raises:
            SquareCatalogError: If listing catalog items fails
        """
        try:
            logger.info("Fetching catalog items")
            
            params = {}
            if types:
                params["types"] = ",".join(types)
            
            response = self.client.get("/v2/catalog/list", params=params)
            
            objects = response.get("objects", [])
            logger.info(f"Found {len(objects)} catalog objects")
            
            return objects
            
        except Exception as e:
            logger.error(f"Failed to list catalog items: {e}")
            raise SquareCatalogError(f"Failed to list catalog items: {e}")
    
    def search_catalog_items(self, text_filter: Optional[str] = None, 
                           category_ids: Optional[List[str]] = None,
                           include_related: bool = True) -> List[Dict[str, Any]]:
        """
        Search catalog items with filters
        
        Args:
            text_filter: Text to search for in item names/descriptions
            category_ids: List of category IDs to filter by
            include_related: Whether to include related objects
            
        Returns:
            List of matching catalog objects
            
        Raises:
            SquareCatalogError: If search fails
        """
        try:
            logger.info(f"Searching catalog items with text: {text_filter}")
            
            search_query = {
                "object_types": ["ITEM"]
            }
            
            # Add text filter
            if text_filter:
                search_query["text_filter"] = {
                    "text": text_filter
                }
            
            # Add category filter
            if category_ids:
                search_query["category_filter"] = {
                    "any_category_ids": category_ids
                }
            
            data = {
                "object_types": ["ITEM"],
                "query": search_query,
                "include_related_objects": include_related
            }
            
            response = self.client.post("/v2/catalog/search", data=data)
            
            objects = response.get("objects", [])
            logger.info(f"Found {len(objects)} matching catalog objects")
            
            return objects
            
        except Exception as e:
            logger.error(f"Failed to search catalog items: {e}")
            raise SquareCatalogError(f"Failed to search catalog items: {e}")
    
    def get_bookable_services(self, location_id: str) -> List[Dict[str, Any]]:
        """
        Get all bookable services for a location
        
        Args:
            location_id: Square location ID
            
        Returns:
            List of bookable service items
            
        Raises:
            SquareCatalogError: If retrieval fails
        """
        try:
            logger.info(f"Fetching bookable services for location: {location_id}")
            
            # Search for items that have appointment segments (bookable services)
            search_query = {
                "object_types": ["ITEM"],
                "query": {
                    "exact_query": {
                        "attribute_name": "appointment_segments",
                        "attribute_value": "*"
                    }
                }
            }
            
            data = {
                "object_types": ["ITEM", "ITEM_VARIATION"],
                "query": search_query,
                "include_related_objects": True
            }
            
            response = self.client.post("/v2/catalog/search", data=data)
            
            objects = response.get("objects", [])
            
            # Filter for items that are actually bookable services
            bookable_services = []
            for obj in objects:
                if obj.get("type") == "ITEM":
                    item_data = obj.get("item_data", {})
                    # Check if item has appointment segments defined
                    if "appointment_segments" in item_data:
                        bookable_services.append(obj)
            
            logger.info(f"Found {len(bookable_services)} bookable services")
            return bookable_services
            
        except Exception as e:
            logger.error(f"Failed to get bookable services: {e}")
            raise SquareCatalogError(f"Failed to get bookable services: {e}")
    
    def get_service_variations(self, service_item_id: str) -> List[Dict[str, Any]]:
        """
        Get all variations for a service item
        
        Args:
            service_item_id: Square item ID for the service
            
        Returns:
            List of service variations
            
        Raises:
            SquareCatalogError: If retrieval fails
        """
        try:
            logger.info(f"Fetching variations for service: {service_item_id}")
            
            # Get the service item with related objects
            response = self.client.get(f"/v2/catalog/object/{service_item_id}?include_related_objects=true")
            
            # Extract variations from related objects
            related_objects = response.get("related_objects", [])
            variations = [
                obj for obj in related_objects 
                if obj.get("type") == "ITEM_VARIATION"
            ]
            
            logger.info(f"Found {len(variations)} variations")
            return variations
            
        except Exception as e:
            logger.error(f"Failed to get service variations: {e}")
            raise SquareCatalogError(f"Failed to get service variations: {e}")
    
    def find_service_by_name(self, service_name: str) -> Optional[Dict[str, Any]]:
        """
        Find a bookable service by name
        
        Args:
            service_name: Name of the service to find
            
        Returns:
            Service item if found, None otherwise
        """
        try:
            logger.info(f"Searching for service: {service_name}")
            
            # Search catalog items by text
            items = self.search_catalog_items(text_filter=service_name)
            
            # Look for exact or close matches
            for item in items:
                if item.get("type") == "ITEM":
                    item_data = item.get("item_data", {})
                    item_name = item_data.get("name", "").lower()
                    
                    # Check if it's a bookable service and name matches
                    if (service_name.lower() in item_name and 
                        "appointment_segments" in item_data):
                        logger.info(f"Found service: {item.get('id')}")
                        return item
            
            logger.warning(f"No bookable service found with name: {service_name}")
            return None
            
        except Exception as e:
            logger.error(f"Failed to find service by name: {e}")
            return None
    
    def get_service_variation_id(self, service_item_id: str, 
                               variation_name: Optional[str] = None) -> Optional[str]:
        """
        Get the variation ID for a service
        
        Args:
            service_item_id: Square item ID for the service
            variation_name: Optional specific variation name, defaults to first variation
            
        Returns:
            Service variation ID if found, None otherwise
        """
        try:
            variations = self.get_service_variations(service_item_id)
            
            if not variations:
                logger.warning(f"No variations found for service: {service_item_id}")
                return None
            
            # If specific variation name requested, find it
            if variation_name:
                for variation in variations:
                    variation_data = variation.get("item_variation_data", {})
                    if variation_data.get("name", "").lower() == variation_name.lower():
                        variation_id = variation.get("id")
                        logger.info(f"Found variation '{variation_name}': {variation_id}")
                        return variation_id
                
                logger.warning(f"Variation '{variation_name}' not found")
                return None
            
            # Return first variation ID
            first_variation = variations[0]
            variation_id = first_variation.get("id")
            logger.info(f"Using first variation: {variation_id}")
            return variation_id
            
        except Exception as e:
            logger.error(f"Failed to get service variation ID: {e}")
            return None
    
    def is_service_bookable(self, service_item_id: str) -> bool:
        """
        Check if a service item is bookable
        
        Args:
            service_item_id: Square item ID for the service
            
        Returns:
            True if service is bookable, False otherwise
        """
        try:
            response = self.client.get(f"/v2/catalog/object/{service_item_id}")
            
            obj = response.get("object", {})
            if obj.get("type") != "ITEM":
                return False
            
            item_data = obj.get("item_data", {})
            is_bookable = "appointment_segments" in item_data
            
            logger.info(f"Service {service_item_id} bookable: {is_bookable}")
            return is_bookable
            
        except Exception as e:
            logger.error(f"Failed to check if service is bookable: {e}")
            return False
