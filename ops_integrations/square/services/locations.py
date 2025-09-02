"""
Square Locations Service

Handles location-related operations for Square API.
"""

import logging
from typing import List, Dict, Any, Optional

from ..client import SquareClient
from ..exceptions import SquareLocationError


logger = logging.getLogger(__name__)


class LocationsService:
    """Service for managing Square locations"""
    
    def __init__(self, client: SquareClient):
        """
        Initialize LocationsService
        
        Args:
            client: Square API client instance
        """
        self.client = client
    
    def list_locations(self) -> List[Dict[str, Any]]:
        """
        List all locations for the merchant
        
        Returns:
            List of location objects
            
        Raises:
            SquareLocationError: If listing locations fails
        """
        try:
            logger.info("Fetching all locations")
            response = self.client.get("/v2/locations")
            
            locations = response.get("locations", [])
            logger.info(f"Found {len(locations)} locations")
            
            return locations
            
        except Exception as e:
            logger.error(f"Failed to list locations: {e}")
            raise SquareLocationError(f"Failed to list locations: {e}")
    
    def get_location(self, location_id: str) -> Dict[str, Any]:
        """
        Get a specific location by ID
        
        Args:
            location_id: Square location ID
            
        Returns:
            Location object
            
        Raises:
            SquareLocationError: If location retrieval fails
        """
        try:
            logger.info(f"Fetching location: {location_id}")
            response = self.client.get(f"/v2/locations/{location_id}")
            
            location = response.get("location")
            if not location:
                raise SquareLocationError(f"Location {location_id} not found")
            
            return location
            
        except Exception as e:
            logger.error(f"Failed to get location {location_id}: {e}")
            raise SquareLocationError(f"Failed to get location {location_id}: {e}")
    
    def get_main_location_id(self) -> str:
        """
        Get the main location ID (first active location)
        
        Returns:
            Main location ID
            
        Raises:
            SquareLocationError: If no active locations found
        """
        try:
            locations = self.list_locations()
            
            # Filter for active locations
            active_locations = [
                loc for loc in locations 
                if loc.get("status") == "ACTIVE"
            ]
            
            if not active_locations:
                raise SquareLocationError("No active locations found")
            
            # Return the first active location's ID
            main_location = active_locations[0]
            location_id = main_location.get("id")
            
            logger.info(f"Main location ID: {location_id}")
            return location_id
            
        except Exception as e:
            logger.error(f"Failed to get main location ID: {e}")
            raise SquareLocationError(f"Failed to get main location ID: {e}")
    
    def find_location_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """
        Find a location by name
        
        Args:
            name: Location name to search for
            
        Returns:
            Location object if found, None otherwise
        """
        try:
            locations = self.list_locations()
            
            for location in locations:
                if location.get("name", "").lower() == name.lower():
                    logger.info(f"Found location by name '{name}': {location.get('id')}")
                    return location
            
            logger.warning(f"No location found with name '{name}'")
            return None
            
        except Exception as e:
            logger.error(f"Failed to find location by name '{name}': {e}")
            return None
    
    def get_location_capabilities(self, location_id: str) -> List[str]:
        """
        Get the capabilities of a specific location
        
        Args:
            location_id: Square location ID
            
        Returns:
            List of location capabilities
        """
        try:
            location = self.get_location(location_id)
            capabilities = location.get("capabilities", [])
            
            logger.info(f"Location {location_id} capabilities: {capabilities}")
            return capabilities
            
        except Exception as e:
            logger.error(f"Failed to get location capabilities: {e}")
            return []
    
    def is_bookings_enabled(self, location_id: str) -> bool:
        """
        Check if bookings are enabled for a location
        
        Args:
            location_id: Square location ID
            
        Returns:
            True if bookings are enabled, False otherwise
        """
        try:
            capabilities = self.get_location_capabilities(location_id)
            bookings_enabled = "BOOKINGS" in capabilities
            
            logger.info(f"Bookings enabled for location {location_id}: {bookings_enabled}")
            return bookings_enabled
            
        except Exception as e:
            logger.error(f"Failed to check bookings capability: {e}")
            return False
