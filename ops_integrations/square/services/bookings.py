"""
Square Bookings Service

Handles booking-related operations for Square API including availability search,
booking creation, and management.
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta

from ..client import SquareClient
from ..exceptions import SquareBookingError, SquareValidationError


logger = logging.getLogger(__name__)


class BookingsService:
    """Service for managing Square bookings"""
    
    def __init__(self, client: SquareClient):
        """
        Initialize BookingsService
        
        Args:
            client: Square API client instance
        """
        self.client = client
    
    def search_availability(self, location_id: str, service_variation_id: str,
                          start_at: datetime, end_at: datetime,
                          team_member_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Search for available appointment slots
        
        Args:
            location_id: Square location ID
            service_variation_id: Service variation ID to book
            start_at: Start of search window
            end_at: End of search window (must be ≥24 hours and ≤32 days from start)
            team_member_id: Optional specific team member ID
            
        Returns:
            List of available time slots
            
        Raises:
            SquareBookingError: If availability search fails
            SquareValidationError: If time range is invalid
        """
        try:
            # Validate time range (Square requirement)
            time_diff = end_at - start_at
            if time_diff < timedelta(hours=24):
                raise SquareValidationError("Time range must be at least 24 hours")
            if time_diff > timedelta(days=32):
                raise SquareValidationError("Time range must be no more than 32 days")
            
            logger.info(f"Searching availability from {start_at} to {end_at}")
            
            query = {
                "filter": {
                    "location_id": location_id,
                    "segment_filters": [
                        {
                            "service_variation_id": service_variation_id
                        }
                    ],
                    "start_at_range": {
                        "start_at": start_at.isoformat() + "Z",
                        "end_at": end_at.isoformat() + "Z"
                    }
                }
            }
            
            # Add team member filter if specified
            if team_member_id:
                query["filter"]["segment_filters"][0]["team_member_id_filter"] = {
                    "any": [team_member_id]
                }
            
            data = {"query": query}
            
            response = self.client.post("/v2/bookings/availability/search", data=data)
            
            availabilities = response.get("availabilities", [])
            logger.info(f"Found {len(availabilities)} available slots")
            
            return availabilities
            
        except SquareValidationError:
            raise  # Re-raise validation errors
        except Exception as e:
            logger.error(f"Failed to search availability: {e}")
            raise SquareBookingError(f"Failed to search availability: {e}")
    
    def create_booking(self, location_id: str, customer_id: str,
                      service_variation_id: str, start_at: datetime,
                      team_member_id: Optional[str] = None,
                      duration_minutes: Optional[int] = None,
                      note: Optional[str] = None) -> Dict[str, Any]:
        """
        Create a new booking
        
        Args:
            location_id: Square location ID
            customer_id: Square customer ID
            service_variation_id: Service variation ID to book
            start_at: Appointment start time
            team_member_id: Optional specific team member ID
            duration_minutes: Optional duration override
            note: Optional booking note
            
        Returns:
            Created booking object
            
        Raises:
            SquareBookingError: If booking creation fails
        """
        try:
            logger.info(f"Creating booking for customer {customer_id} at {start_at}")
            
            # Create appointment segment
            segment = {
                "service_variation_id": service_variation_id
            }
            
            if duration_minutes:
                segment["duration_minutes"] = duration_minutes
            
            if team_member_id:
                segment["team_member_id"] = team_member_id
            
            booking_data = {
                "location_id": location_id,
                "start_at": start_at.isoformat() + "Z",
                "customer_id": customer_id,
                "appointment_segments": [segment]
            }
            
            if note:
                booking_data["customer_note"] = note
            
            data = {"booking": booking_data}
            
            response = self.client.post("/v2/bookings", data=data)
            
            booking = response.get("booking")
            if not booking:
                raise SquareBookingError("Failed to create booking - no booking data returned")
            
            booking_id = booking.get("id")
            logger.info(f"Created booking with ID: {booking_id}")
            
            return booking
            
        except Exception as e:
            logger.error(f"Failed to create booking: {e}")
            raise SquareBookingError(f"Failed to create booking: {e}")
    
    def get_booking(self, booking_id: str) -> Dict[str, Any]:
        """
        Get a specific booking by ID
        
        Args:
            booking_id: Square booking ID
            
        Returns:
            Booking object
            
        Raises:
            SquareBookingError: If booking retrieval fails
        """
        try:
            logger.info(f"Fetching booking: {booking_id}")
            response = self.client.get(f"/v2/bookings/{booking_id}")
            
            booking = response.get("booking")
            if not booking:
                raise SquareBookingError(f"Booking {booking_id} not found")
            
            return booking
            
        except Exception as e:
            logger.error(f"Failed to get booking {booking_id}: {e}")
            raise SquareBookingError(f"Failed to get booking {booking_id}: {e}")
    
    def list_bookings(self, location_id: Optional[str] = None,
                     customer_id: Optional[str] = None,
                     team_member_id: Optional[str] = None,
                     start_at_min: Optional[datetime] = None,
                     start_at_max: Optional[datetime] = None,
                     limit: int = 100) -> List[Dict[str, Any]]:
        """
        List bookings with optional filters
        
        Args:
            location_id: Filter by location ID
            customer_id: Filter by customer ID
            team_member_id: Filter by team member ID
            start_at_min: Filter by minimum start time
            start_at_max: Filter by maximum start time
            limit: Maximum number of results
            
        Returns:
            List of booking objects
            
        Raises:
            SquareBookingError: If listing bookings fails
        """
        try:
            logger.info("Listing bookings")
            
            params = {"limit": limit}
            
            if location_id:
                params["location_id"] = location_id
            if customer_id:
                params["customer_id"] = customer_id
            if team_member_id:
                params["team_member_id"] = team_member_id
            if start_at_min:
                params["start_at_min"] = start_at_min.isoformat() + "Z"
            if start_at_max:
                params["start_at_max"] = start_at_max.isoformat() + "Z"
            
            response = self.client.get("/v2/bookings", params=params)
            
            bookings = response.get("bookings", [])
            logger.info(f"Found {len(bookings)} bookings")
            
            return bookings
            
        except Exception as e:
            logger.error(f"Failed to list bookings: {e}")
            raise SquareBookingError(f"Failed to list bookings: {e}")
    
    def update_booking(self, booking_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update booking information
        
        Args:
            booking_id: Square booking ID
            updates: Dictionary of fields to update
            
        Returns:
            Updated booking object
            
        Raises:
            SquareBookingError: If update fails
        """
        try:
            logger.info(f"Updating booking: {booking_id}")
            
            data = {"booking": updates}
            
            response = self.client.patch(f"/v2/bookings/{booking_id}", data=data)
            
            booking = response.get("booking")
            if not booking:
                raise SquareBookingError("Failed to update booking - no booking data returned")
            
            logger.info(f"Updated booking: {booking_id}")
            return booking
            
        except Exception as e:
            logger.error(f"Failed to update booking {booking_id}: {e}")
            raise SquareBookingError(f"Failed to update booking {booking_id}: {e}")
    
    def cancel_booking(self, booking_id: str, cancellation_reason: Optional[str] = None) -> Dict[str, Any]:
        """
        Cancel a booking
        
        Args:
            booking_id: Square booking ID
            cancellation_reason: Optional reason for cancellation
            
        Returns:
            Updated booking object with cancelled status
            
        Raises:
            SquareBookingError: If cancellation fails
        """
        try:
            logger.info(f"Cancelling booking: {booking_id}")
            
            updates = {"status": "CANCELLED"}
            if cancellation_reason:
                updates["cancellation_reason"] = cancellation_reason
            
            return self.update_booking(booking_id, updates)
            
        except Exception as e:
            logger.error(f"Failed to cancel booking {booking_id}: {e}")
            raise SquareBookingError(f"Failed to cancel booking {booking_id}: {e}")
    
    def reschedule_booking(self, booking_id: str, new_start_at: datetime,
                         new_team_member_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Reschedule a booking to a new time
        
        Args:
            booking_id: Square booking ID
            new_start_at: New appointment start time
            new_team_member_id: Optional new team member ID
            
        Returns:
            Updated booking object
            
        Raises:
            SquareBookingError: If rescheduling fails
        """
        try:
            logger.info(f"Rescheduling booking {booking_id} to {new_start_at}")
            
            updates = {"start_at": new_start_at.isoformat() + "Z"}
            
            # If changing team member, update appointment segments
            if new_team_member_id:
                # Get current booking to modify segments
                current_booking = self.get_booking(booking_id)
                segments = current_booking.get("appointment_segments", [])
                
                # Update team member in first segment
                if segments:
                    segments[0]["team_member_id"] = new_team_member_id
                    updates["appointment_segments"] = segments
            
            return self.update_booking(booking_id, updates)
            
        except Exception as e:
            logger.error(f"Failed to reschedule booking {booking_id}: {e}")
            raise SquareBookingError(f"Failed to reschedule booking {booking_id}: {e}")
    
    def get_upcoming_bookings(self, location_id: str, days_ahead: int = 30) -> List[Dict[str, Any]]:
        """
        Get upcoming bookings for a location
        
        Args:
            location_id: Square location ID
            days_ahead: Number of days ahead to look (default 30)
            
        Returns:
            List of upcoming booking objects
        """
        try:
            now = datetime.utcnow()
            end_time = now + timedelta(days=days_ahead)
            
            return self.list_bookings(
                location_id=location_id,
                start_at_min=now,
                start_at_max=end_time
            )
            
        except Exception as e:
            logger.error(f"Failed to get upcoming bookings: {e}")
            raise SquareBookingError(f"Failed to get upcoming bookings: {e}")
    
    def check_availability_for_time(self, location_id: str, service_variation_id: str,
                                  desired_time: datetime, team_member_id: Optional[str] = None) -> bool:
        """
        Check if a specific time slot is available
        
        Args:
            location_id: Square location ID
            service_variation_id: Service variation ID
            desired_time: Desired appointment time
            team_member_id: Optional specific team member ID
            
        Returns:
            True if time slot is available, False otherwise
        """
        try:
            # Search availability in a 1-hour window around desired time
            start_search = desired_time - timedelta(minutes=30)
            end_search = desired_time + timedelta(hours=23, minutes=30)  # Ensure 24+ hour window
            
            availabilities = self.search_availability(
                location_id=location_id,
                service_variation_id=service_variation_id,
                start_at=start_search,
                end_at=end_search,
                team_member_id=team_member_id
            )
            
            # Check if any availability matches the desired time
            for availability in availabilities:
                start_at_str = availability.get("start_at", "")
                if start_at_str:
                    available_time = datetime.fromisoformat(start_at_str.replace("Z", "+00:00"))
                    # Allow 5-minute tolerance
                    time_diff = abs((available_time - desired_time).total_seconds())
                    if time_diff <= 300:  # 5 minutes
                        return True
            
            return False
            
        except Exception as e:
            logger.error(f"Failed to check availability for time: {e}")
            return False
