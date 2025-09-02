"""
Phone Integration Example for Square Booking System

Shows how to integrate Square bookings with the existing phone system.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

from .salon_booking_integration import SalonBookingManager


logger = logging.getLogger(__name__)


class PhoneBookingHandler:
    """
    Handles Square bookings from phone calls
    Integrates with existing phone system architecture
    """
    
    def __init__(self):
        """Initialize the phone booking handler"""
        self.salon_manager = SalonBookingManager()
        
    def process_booking_intent(self, call_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process booking intent from phone call
        
        Args:
            call_data: Dictionary containing call information:
                - caller_name: Full name of caller
                - caller_phone: Phone number
                - service_requested: Name of service requested
                - preferred_date: Preferred date (YYYY-MM-DD format)
                - preferred_time: Preferred time (HH:MM format)
                - additional_notes: Any additional notes
                
        Returns:
            Response dictionary for phone system
        """
        try:
            logger.info(f"Processing booking intent for {call_data.get('caller_name')}")
            
            # Extract and validate call data
            caller_name = call_data.get('caller_name', '')
            caller_phone = call_data.get('caller_phone', '')
            service_requested = call_data.get('service_requested', '')
            preferred_date = call_data.get('preferred_date', '')
            preferred_time = call_data.get('preferred_time', '')
            notes = call_data.get('additional_notes', '')
            
            # Validate required fields
            if not all([caller_name, caller_phone, service_requested, preferred_date, preferred_time]):
                return {
                    "status": "error",
                    "message": "Missing required booking information. Please provide your name, phone number, service, date and time.",
                    "requires_clarification": True,
                    "missing_fields": self._get_missing_fields(call_data)
                }
            
            # Parse caller name
            name_parts = caller_name.strip().split(" ", 1)
            first_name = name_parts[0] if name_parts else ""
            last_name = name_parts[1] if len(name_parts) > 1 else ""
            
            # Parse datetime
            try:
                preferred_datetime = datetime.strptime(
                    f"{preferred_date} {preferred_time}",
                    "%Y-%m-%d %H:%M"
                )
            except ValueError:
                return {
                    "status": "error", 
                    "message": "Invalid date or time format. Please provide date as YYYY-MM-DD and time as HH:MM.",
                    "requires_clarification": True
                }
            
            # Check if date is in the future
            if preferred_datetime <= datetime.now():
                return {
                    "status": "error",
                    "message": "Please choose a future date and time for your appointment.",
                    "requires_clarification": True
                }
            
            # Create customer info
            customer_info = {
                "first_name": first_name,
                "last_name": last_name,
                "phone_number": caller_phone
            }
            
            # Create booking
            booking_result = self.salon_manager.create_booking_from_call(
                customer_info=customer_info,
                service_name=service_requested,
                preferred_time=preferred_datetime,
                notes=f"Phone booking. Notes: {notes}" if notes else "Phone booking"
            )
            
            if booking_result["success"]:
                return {
                    "status": "success",
                    "message": booking_result["message"],
                    "booking_id": booking_result["booking_id"],
                    "action": "booking_confirmed"
                }
            else:
                # Handle specific error cases
                if booking_result.get("alternatives"):
                    alternatives_text = self._format_alternatives(booking_result["alternatives"])
                    return {
                        "status": "alternatives_available",
                        "message": f"{booking_result['message']} Would you like to book one of these alternative times? {alternatives_text}",
                        "alternatives": booking_result["alternatives"],
                        "requires_clarification": True
                    }
                else:
                    return {
                        "status": "error",
                        "message": booking_result["message"],
                        "requires_clarification": True
                    }
            
        except Exception as e:
            logger.error(f"Error processing booking intent: {e}")
            return {
                "status": "error",
                "message": "I'm having trouble processing your booking right now. Please try again or call back later.",
                "requires_escalation": True
            }
    
    def process_cancellation_intent(self, call_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process cancellation intent from phone call
        
        Args:
            call_data: Dictionary containing:
                - caller_phone: Phone number to identify bookings
                - booking_reference: Optional booking ID or reference
                
        Returns:
            Response dictionary for phone system
        """
        try:
            caller_phone = call_data.get('caller_phone', '')
            booking_reference = call_data.get('booking_reference', '')
            
            if not caller_phone:
                return {
                    "status": "error",
                    "message": "I need your phone number to find your booking.",
                    "requires_clarification": True
                }
            
            # If specific booking ID provided, try to cancel it
            if booking_reference:
                result = self.salon_manager.cancel_booking_by_phone(
                    booking_id=booking_reference,
                    reason="Customer phone cancellation"
                )
                return {
                    "status": "success" if result["success"] else "error",
                    "message": result["message"],
                    "action": "booking_cancelled" if result["success"] else None
                }
            
            # Otherwise, get upcoming bookings for the phone number
            # This would require implementing customer lookup by phone
            return {
                "status": "info",
                "message": "Let me find your upcoming appointments. Can you provide your booking reference number or the date of your appointment?",
                "requires_clarification": True
            }
            
        except Exception as e:
            logger.error(f"Error processing cancellation intent: {e}")
            return {
                "status": "error",
                "message": "I'm having trouble accessing your booking information. Please try again.",
                "requires_escalation": True
            }
    
    def check_availability_for_call(self, service_name: str, date_str: str) -> Dict[str, Any]:
        """
        Check availability for a specific service and date
        
        Args:
            service_name: Name of the service
            date_str: Date in YYYY-MM-DD format
            
        Returns:
            Availability information
        """
        try:
            from .salon_booking_integration import get_available_time_slots
            
            time_slots = get_available_time_slots(service_name, date_str)
            
            if time_slots:
                slots_text = ", ".join(time_slots[:5])  # Limit to 5 slots
                return {
                    "status": "available",
                    "message": f"Available times for {service_name} on {date_str}: {slots_text}",
                    "time_slots": time_slots
                }
            else:
                return {
                    "status": "unavailable",
                    "message": f"No available times for {service_name} on {date_str}. Would you like to try a different date?",
                    "requires_clarification": True
                }
                
        except Exception as e:
            logger.error(f"Error checking availability: {e}")
            return {
                "status": "error",
                "message": "I'm having trouble checking availability. Please try again.",
                "requires_escalation": True
            }
    
    def get_service_list(self) -> Dict[str, Any]:
        """Get list of available services for phone callers"""
        try:
            services = self.salon_manager.get_available_services()
            
            if services:
                service_names = [s["name"] for s in services if s["name"]]
                services_text = ", ".join(service_names)
                
                return {
                    "status": "success",
                    "message": f"We offer the following services: {services_text}",
                    "services": service_names
                }
            else:
                return {
                    "status": "error",
                    "message": "I'm having trouble retrieving our service list. Please call back later.",
                    "requires_escalation": True
                }
                
        except Exception as e:
            logger.error(f"Error getting service list: {e}")
            return {
                "status": "error", 
                "message": "I'm having trouble accessing our services. Please try again.",
                "requires_escalation": True
            }
    
    def health_check(self) -> bool:
        """Check if Square API is available"""
        return self.salon_manager.health_check()
    
    def _get_missing_fields(self, call_data: Dict[str, Any]) -> list:
        """Get list of missing required fields"""
        required_fields = {
            'caller_name': 'your name',
            'caller_phone': 'your phone number',
            'service_requested': 'the service you want',
            'preferred_date': 'your preferred date',
            'preferred_time': 'your preferred time'
        }
        
        missing = []
        for field, description in required_fields.items():
            if not call_data.get(field):
                missing.append(description)
        
        return missing
    
    def _format_alternatives(self, alternatives: list) -> str:
        """Format alternative time options for phone response"""
        if not alternatives:
            return ""
        
        formatted = []
        for alt in alternatives[:3]:  # Limit to 3 alternatives
            formatted.append(alt["formatted"])
        
        return " or ".join(formatted)


# Example integration with existing phone system
def integrate_with_phone_handler(phone_intent: str, call_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Main integration point with existing phone system
    
    Args:
        phone_intent: Intent extracted from phone call (e.g., "book_appointment", "cancel_appointment")
        call_data: Call data with extracted information
        
    Returns:
        Response for phone system to use
    """
    handler = PhoneBookingHandler()
    
    # Check if Square API is available
    if not handler.health_check():
        return {
            "status": "error",
            "message": "Our booking system is temporarily unavailable. Please call back later.",
            "requires_escalation": True
        }
    
    # Route to appropriate handler based on intent
    if phone_intent == "book_appointment":
        return handler.process_booking_intent(call_data)
    
    elif phone_intent == "cancel_appointment":
        return handler.process_cancellation_intent(call_data)
    
    elif phone_intent == "check_availability":
        service_name = call_data.get('service_requested', '')
        date_str = call_data.get('preferred_date', '')
        return handler.check_availability_for_call(service_name, date_str)
    
    elif phone_intent == "get_services":
        return handler.get_service_list()
    
    else:
        return {
            "status": "error",
            "message": "I didn't understand your request. Can you please clarify what you'd like to do?",
            "requires_clarification": True
        }


# Example usage for testing
if __name__ == "__main__":
    # Example booking call
    call_data = {
        "caller_name": "Jane Smith",
        "caller_phone": "+1234567890", 
        "service_requested": "Haircut",
        "preferred_date": "2024-01-15",
        "preferred_time": "14:30",
        "additional_notes": "First time customer"
    }
    
    result = integrate_with_phone_handler("book_appointment", call_data)
    print(f"Booking result: {result}")
    
    # Example availability check
    availability_data = {
        "service_requested": "Haircut",
        "preferred_date": "2024-01-15"
    }
    
    availability = integrate_with_phone_handler("check_availability", availability_data)
    print(f"Availability: {availability}")
