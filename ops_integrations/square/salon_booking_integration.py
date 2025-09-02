"""
Salon Booking Integration Example

Complete integration example showing how to use Square API
for salon phone booking system.
"""

import os
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List

from .client import SquareClient
from .config import SquareConfig
from .services import LocationsService, CatalogService, CustomersService, BookingsService
from .exceptions import SquareAPIError, SquareBookingError


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SalonBookingManager:
    """
    Main class for managing salon bookings through Square API
    Designed to integrate with phone call handling system
    """
    
    def __init__(self, config: Optional[SquareConfig] = None):
        """
        Initialize the salon booking manager
        
        Args:
            config: Square API configuration. If None, loads from environment
        """
        if config is None:
            config = SquareConfig.from_env()
        
        self.client = SquareClient(config)
        self.config = config
        
        # Initialize services
        self.locations = LocationsService(self.client)
        self.catalog = CatalogService(self.client)
        self.customers = CustomersService(self.client)
        self.bookings = BookingsService(self.client)
        
        # Cache commonly used IDs
        self._location_id = None
        self._services_cache = {}
    
    def get_location_id(self) -> str:
        """Get the main location ID, cached for performance"""
        if self._location_id is None:
            self._location_id = self.locations.get_main_location_id()
        return self._location_id
    
    def get_available_services(self) -> List[Dict[str, Any]]:
        """Get list of all bookable services"""
        try:
            location_id = self.get_location_id()
            services = self.catalog.get_bookable_services(location_id)
            
            # Format for easy use
            formatted_services = []
            for service in services:
                service_data = service.get("item_data", {})
                formatted_services.append({
                    "id": service.get("id"),
                    "name": service_data.get("name"),
                    "description": service_data.get("description", ""),
                    "category": service_data.get("category_id"),
                })
            
            return formatted_services
            
        except Exception as e:
            logger.error(f"Failed to get available services: {e}")
            return []
    
    def find_service_variation_id(self, service_name: str) -> Optional[str]:
        """
        Find service variation ID by service name
        
        Args:
            service_name: Name of the service to find
            
        Returns:
            Service variation ID if found, None otherwise
        """
        try:
            # Check cache first
            if service_name in self._services_cache:
                return self._services_cache[service_name]
            
            # Find service by name
            service = self.catalog.find_service_by_name(service_name)
            if not service:
                logger.warning(f"Service '{service_name}' not found")
                return None
            
            # Get variation ID
            service_id = service.get("id")
            variation_id = self.catalog.get_service_variation_id(service_id)
            
            # Cache for future use
            if variation_id:
                self._services_cache[service_name] = variation_id
            
            return variation_id
            
        except Exception as e:
            logger.error(f"Failed to find service variation ID: {e}")
            return None
    
    def create_booking_from_call(self, customer_info: Dict[str, str], 
                               service_name: str, preferred_time: datetime,
                               notes: Optional[str] = None) -> Dict[str, Any]:
        """
        Create booking from phone call information
        
        Args:
            customer_info: Dict with customer details (first_name, last_name, phone_number, email)
            service_name: Name of requested service
            preferred_time: Preferred appointment time
            notes: Optional booking notes
            
        Returns:
            Booking result with success status and details
        """
        try:
            logger.info(f"Processing booking request for {customer_info.get('first_name')} {customer_info.get('last_name')}")
            
            # 1. Get location ID
            location_id = self.get_location_id()
            
            # 2. Find service variation ID
            variation_id = self.find_service_variation_id(service_name)
            if not variation_id:
                return {
                    "success": False,
                    "error": f"Service '{service_name}' not available",
                    "message": f"Sorry, we don't offer '{service_name}' service."
                }
            
            # 3. Get or create customer
            customer_id = self.customers.get_customer_id(
                first_name=customer_info.get("first_name", ""),
                last_name=customer_info.get("last_name", ""),
                phone_number=customer_info.get("phone_number"),
                email=customer_info.get("email")
            )
            
            # 4. Check availability for requested time
            is_available = self.bookings.check_availability_for_time(
                location_id=location_id,
                service_variation_id=variation_id,
                desired_time=preferred_time
            )
            
            if not is_available:
                # Try to find alternative times
                alternatives = self.find_alternative_times(
                    location_id, variation_id, preferred_time
                )
                
                return {
                    "success": False,
                    "error": "Time slot not available",
                    "message": f"The requested time {preferred_time.strftime('%Y-%m-%d %H:%M')} is not available.",
                    "alternatives": alternatives
                }
            
            # 5. Create the booking
            booking = self.bookings.create_booking(
                location_id=location_id,
                customer_id=customer_id,
                service_variation_id=variation_id,
                start_at=preferred_time,
                note=notes
            )
            
            return {
                "success": True,
                "booking_id": booking.get("id"),
                "booking": booking,
                "message": f"Booking confirmed for {preferred_time.strftime('%A, %B %d at %I:%M %p')}"
            }
            
        except SquareBookingError as e:
            logger.error(f"Booking error: {e}")
            return {
                "success": False,
                "error": "booking_failed",
                "message": "Unable to create booking. Please try again later."
            }
        except Exception as e:
            logger.error(f"Unexpected error creating booking: {e}")
            return {
                "success": False,
                "error": "system_error",
                "message": "System error occurred. Please call back later."
            }
    
    def find_alternative_times(self, location_id: str, service_variation_id: str,
                             preferred_time: datetime, days_to_search: int = 7) -> List[Dict[str, Any]]:
        """
        Find alternative appointment times near the preferred time
        
        Args:
            location_id: Square location ID
            service_variation_id: Service variation ID
            preferred_time: Originally requested time
            days_to_search: Number of days to search for alternatives
            
        Returns:
            List of alternative time slots
        """
        try:
            # Search for availability in the next week
            start_search = preferred_time
            end_search = preferred_time + timedelta(days=days_to_search)
            
            # Ensure we meet Square's 24-hour minimum window
            if (end_search - start_search).total_seconds() < 24 * 3600:
                end_search = start_search + timedelta(hours=25)
            
            availabilities = self.bookings.search_availability(
                location_id=location_id,
                service_variation_id=service_variation_id,
                start_at=start_search,
                end_at=end_search
            )
            
            # Format alternatives for easy use
            alternatives = []
            for availability in availabilities[:5]:  # Limit to 5 alternatives
                start_at_str = availability.get("start_at", "")
                if start_at_str:
                    start_time = datetime.fromisoformat(start_at_str.replace("Z", "+00:00"))
                    alternatives.append({
                        "datetime": start_time,
                        "formatted": start_time.strftime('%A, %B %d at %I:%M %p'),
                        "availability": availability
                    })
            
            return alternatives
            
        except Exception as e:
            logger.error(f"Failed to find alternative times: {e}")
            return []
    
    def get_booking_details(self, booking_id: str) -> Optional[Dict[str, Any]]:
        """
        Get booking details by ID
        
        Args:
            booking_id: Square booking ID
            
        Returns:
            Booking details if found, None otherwise
        """
        try:
            booking = self.bookings.get_booking(booking_id)
            
            # Format for easy use
            start_at_str = booking.get("start_at", "")
            start_time = None
            if start_at_str:
                start_time = datetime.fromisoformat(start_at_str.replace("Z", "+00:00"))
            
            return {
                "id": booking.get("id"),
                "status": booking.get("status"),
                "customer_id": booking.get("customer_id"),
                "start_time": start_time,
                "start_time_formatted": start_time.strftime('%A, %B %d at %I:%M %p') if start_time else "",
                "location_id": booking.get("location_id"),
                "appointment_segments": booking.get("appointment_segments", []),
                "customer_note": booking.get("customer_note", ""),
                "raw_booking": booking
            }
            
        except Exception as e:
            logger.error(f"Failed to get booking details: {e}")
            return None
    
    def cancel_booking_by_phone(self, booking_id: str, reason: str = "Customer request") -> Dict[str, Any]:
        """
        Cancel booking with phone-friendly response
        
        Args:
            booking_id: Square booking ID
            reason: Cancellation reason
            
        Returns:
            Cancellation result
        """
        try:
            cancelled_booking = self.bookings.cancel_booking(booking_id, reason)
            
            return {
                "success": True,
                "booking_id": booking_id,
                "message": "Your appointment has been cancelled successfully."
            }
            
        except Exception as e:
            logger.error(f"Failed to cancel booking: {e}")
            return {
                "success": False,
                "error": str(e),
                "message": "Unable to cancel appointment. Please call back."
            }
    
    def get_upcoming_appointments(self, days_ahead: int = 30) -> List[Dict[str, Any]]:
        """
        Get upcoming appointments for the salon
        
        Args:
            days_ahead: Number of days ahead to look
            
        Returns:
            List of upcoming appointments
        """
        try:
            location_id = self.get_location_id()
            bookings = self.bookings.get_upcoming_bookings(location_id, days_ahead)
            
            # Format for easy use
            formatted_bookings = []
            for booking in bookings:
                details = self.get_booking_details(booking.get("id"))
                if details:
                    formatted_bookings.append(details)
            
            return formatted_bookings
            
        except Exception as e:
            logger.error(f"Failed to get upcoming appointments: {e}")
            return []
    
    def health_check(self) -> bool:
        """
        Perform health check to ensure Square API is accessible
        
        Returns:
            True if healthy, False otherwise
        """
        try:
            return self.client.health_check()
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False


# Example usage functions for phone integration
def handle_phone_booking_request(caller_name: str, caller_phone: str, 
                               service_name: str, preferred_date_str: str,
                               preferred_time_str: str) -> Dict[str, Any]:
    """
    Handle booking request from phone call
    
    Args:
        caller_name: Full name of caller (e.g., "John Doe")
        caller_phone: Phone number
        service_name: Requested service
        preferred_date_str: Preferred date (e.g., "2024-01-15")
        preferred_time_str: Preferred time (e.g., "14:30")
        
    Returns:
        Booking result
    """
    try:
        # Parse caller name
        name_parts = caller_name.split(" ", 1)
        first_name = name_parts[0] if name_parts else ""
        last_name = name_parts[1] if len(name_parts) > 1 else ""
        
        # Parse preferred datetime
        preferred_datetime = datetime.strptime(
            f"{preferred_date_str} {preferred_time_str}",
            "%Y-%m-%d %H:%M"
        )
        
        # Create customer info
        customer_info = {
            "first_name": first_name,
            "last_name": last_name,
            "phone_number": caller_phone
        }
        
        # Create booking
        salon_manager = SalonBookingManager()
        result = salon_manager.create_booking_from_call(
            customer_info=customer_info,
            service_name=service_name,
            preferred_time=preferred_datetime,
            notes=f"Booked via phone call from {caller_phone}"
        )
        
        return result
        
    except ValueError as e:
        return {
            "success": False,
            "error": "invalid_datetime",
            "message": "Invalid date or time format provided."
        }
    except Exception as e:
        logger.error(f"Phone booking request failed: {e}")
        return {
            "success": False,
            "error": "system_error",
            "message": "System error occurred. Please try again."
        }


def get_available_time_slots(service_name: str, date_str: str) -> List[str]:
    """
    Get available time slots for a service on a specific date
    
    Args:
        service_name: Name of the service
        date_str: Date in format "YYYY-MM-DD"
        
    Returns:
        List of available time slots
    """
    try:
        salon_manager = SalonBookingManager()
        
        # Parse date and create search window
        search_date = datetime.strptime(date_str, "%Y-%m-%d")
        start_search = search_date.replace(hour=9, minute=0)  # 9 AM
        end_search = search_date.replace(hour=18, minute=0)   # 6 PM
        
        # Ensure minimum 24-hour window
        if (end_search - start_search).total_seconds() < 24 * 3600:
            end_search = start_search + timedelta(hours=25)
        
        # Get service variation ID
        variation_id = salon_manager.find_service_variation_id(service_name)
        if not variation_id:
            return []
        
        # Search availability
        location_id = salon_manager.get_location_id()
        availabilities = salon_manager.bookings.search_availability(
            location_id=location_id,
            service_variation_id=variation_id,
            start_at=start_search,
            end_at=end_search
        )
        
        # Format time slots
        time_slots = []
        for availability in availabilities:
            start_at_str = availability.get("start_at", "")
            if start_at_str:
                start_time = datetime.fromisoformat(start_at_str.replace("Z", "+00:00"))
                # Only include slots on the requested date
                if start_time.date() == search_date.date():
                    time_slots.append(start_time.strftime("%H:%M"))
        
        return sorted(time_slots)
        
    except Exception as e:
        logger.error(f"Failed to get available time slots: {e}")
        return []


if __name__ == "__main__":
    # Example usage
    salon_manager = SalonBookingManager()
    
    # Health check
    if salon_manager.health_check():
        print("✅ Square API connection successful")
        
        # Get available services
        services = salon_manager.get_available_services()
        print(f"📋 Available services: {[s['name'] for s in services]}")
        
        # Example booking
        customer_info = {
            "first_name": "Jane",
            "last_name": "Smith",
            "phone_number": "+1234567890"
        }
        
        appointment_time = datetime.utcnow() + timedelta(days=2)
        result = salon_manager.create_booking_from_call(
            customer_info=customer_info,
            service_name="Haircut",  # Make sure this service exists
            preferred_time=appointment_time
        )
        
        print(f"📅 Booking result: {result}")
        
    else:
        print("❌ Square API connection failed")
