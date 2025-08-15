#!/usr/bin/env python3
"""
Job Booking System for Plumbing AGI
Integrates SMS notifications with CRM and calendar management
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Prefer package-relative imports; on failure, fall back to script-friendly absolute imports
try:
    from ops_integrations.adapters.integrations.crm import CRMAdapter, InteractionType
    from ops_integrations.adapters.external_services.google_calendar import CalendarAdapter
    from ops_integrations.adapters.external_services.sms import SMSAdapter
except Exception:
    import sys as _sys
    import os as _os
    _CURRENT_DIR = _os.path.dirname(__file__)
    _OPS_ROOT = _os.path.abspath(_os.path.join(_CURRENT_DIR, '..'))
    if _OPS_ROOT not in _sys.path:
        _sys.path.insert(0, _OPS_ROOT)
    from ops_integrations.adapters.integrations.crm import CRMAdapter, InteractionType
    from ops_integrations.adapters.external_services.google_calendar import CalendarAdapter
    from ops_integrations.adapters.external_services.sms import SMSAdapter

logging.basicConfig(level=logging.INFO)

class JobBookingSystem:
    def __init__(self):
        self.crm = CRMAdapter()
        self.calendar = CalendarAdapter()
        self.sms = SMSAdapter()
        
        # Check system availability
        self.crm_available = self.crm.enabled if self.crm else False
        self.calendar_available = hasattr(self.calendar, 'service') and self.calendar.service is not None
        self.sms_available = self.sms.enabled if self.sms else False
        
        logging.info(f"Job Booking System initialized:")
        logging.info(f"  CRM: {'✅ Available' if self.crm_available else '❌ Not available'}")
        logging.info(f"  Calendar: {'✅ Available' if self.calendar_available else '❌ Not available'}")
        logging.info(f"  SMS: {'✅ Available' if self.sms_available else '❌ Not available'}")

    def book_job(self, customer_phone: str, customer_name: str, service_type: str, 
                appointment_time: datetime, address: str = "", notes: str = "") -> Dict[str, Any]:
        """
        Book a job with full integration (CRM + Calendar + SMS).
        
        Args:
            customer_phone: Customer's phone number
            customer_name: Customer's name
            service_type: Type of service (Emergency Plumbing, Drain Cleaning, etc.)
            appointment_time: When the appointment is scheduled
            address: Service address
            notes: Additional notes about the job
            
        Returns:
            Dictionary with booking results
        """
        logging.info(f"📅 Booking job for {customer_name} - {service_type} at {appointment_time}")
        
        results = {
            "customer_captured": False,
            "calendar_event_created": False,
            "sms_sent": False,
            "customer_id": None,
            "event_id": None,
            "sms_result": None
        }
        
        try:
            # Step 1: Capture customer in CRM
            if self.crm_available:
                crm_result = self.crm.capture_customer_interaction(
                    phone=customer_phone,
                    name=customer_name,
                    interaction_type=InteractionType.PHONE_INBOUND,
                    message_content=f"Job booking: {service_type}. {notes}",
                    service_type=service_type,
                    urgency="Normal"
                )
                
                if crm_result.get("success"):
                    results["customer_captured"] = True
                    results["customer_id"] = crm_result.get("customer_id")
                    logging.info(f"✅ Customer captured in CRM: {customer_name}")
                    
                    # Update customer status to scheduled
                    if results["customer_id"]:
                        self.crm.update_service_status(results["customer_id"], "scheduled", 
                                                     f"Appointment scheduled for {appointment_time}")
                else:
                    logging.warning(f"⚠️ Failed to capture customer in CRM: {crm_result.get('error')}")
            
            # Step 2: Create calendar event
            if self.calendar_available:
                try:
                    end_time = appointment_time + timedelta(hours=2)  # Default 2-hour slot
                    
                    event = self.calendar.create_event(
                        summary=f"{service_type} - {customer_name}",
                        start_time=appointment_time,
                        end_time=end_time,
                        description=f"Service: {service_type}\nCustomer: {customer_name}\nPhone: {customer_phone}\nAddress: {address}\nNotes: {notes}",
                        location=address
                    )
                    
                    if event and event.get('id'):
                        results["calendar_event_created"] = True
                        results["event_id"] = event.get('id')
                        logging.info(f"✅ Calendar event created: {event.get('htmlLink', 'No link')}")
                    else:
                        logging.warning("⚠️ Failed to create calendar event")
                        
                except Exception as e:
                    logging.error(f"❌ Calendar event creation failed: {e}")
            
            # Step 3: Send booking confirmation SMS
            if self.sms_available:
                sms_result = self.sms.send_booking_confirmation(
                    customer_phone, customer_name, service_type, appointment_time, address
                )
                
                results["sms_sent"] = sms_result.get("success", False)
                results["sms_result"] = sms_result
                
                if results["sms_sent"]:
                    logging.info(f"✅ Booking confirmation SMS sent to {customer_phone}")
                else:
                    logging.warning(f"⚠️ SMS send failed: {sms_result.get('error')}")
            
            # Step 4: Schedule reminder SMS (1 hour before)
            if self.sms_available and results["sms_sent"]:
                reminder_time = appointment_time - timedelta(hours=1)
                if reminder_time > datetime.now():
                    # In a real system, you'd use a task scheduler here
                    logging.info(f"📱 Reminder SMS scheduled for {reminder_time}")
            
            logging.info(f"✅ Job booking completed for {customer_name}")
            return results
            
        except Exception as e:
            logging.error(f"❌ Job booking failed: {e}")
            return results

    def update_job_status(self, customer_id: int, status: str, notes: str = "") -> Dict[str, Any]:
        """
        Update job status and send appropriate notifications.
        
        Args:
            customer_id: Customer ID from CRM
            status: New status (scheduled, in_progress, completed, cancelled)
            notes: Additional notes
            
        Returns:
            Dictionary with update results
        """
        logging.info(f"🔄 Updating job status for customer {customer_id} to {status}")
        
        results = {
            "status_updated": False,
            "sms_sent": False,
            "customer_details": None
        }
        
        try:
            # Get customer details
            if self.crm_available:
                customer_details = self.crm.get_customer_details(customer_id)
                if customer_details:
                    results["customer_details"] = customer_details
                    customer = customer_details["customer"]
                    customer_name = customer.get("Name", "Customer")
                    customer_phone = customer.get("Phone", "")
                    service_type = customer.get("Last_Service_Type", "Plumbing Service")
                    
                    # Update status in CRM
                    status_updated = self.crm.update_service_status(customer_id, status, notes)
                    results["status_updated"] = status_updated
                    
                    if status_updated and self.sms_available and customer_phone:
                        # Send appropriate SMS based on status
                        if status == "in_progress":
                            sms_result = self.sms.send_eta_update(customer_phone, customer_name, 15)
                            results["sms_sent"] = sms_result.get("success", False)
                            
                        elif status == "completed":
                            sms_result = self.sms.send_job_completion(customer_phone, customer_name, service_type)
                            results["sms_sent"] = sms_result.get("success", False)
                        
                        if results["sms_sent"]:
                            logging.info(f"✅ Status update SMS sent to {customer_phone}")
                        else:
                            logging.warning(f"⚠️ Status update SMS failed")
                    
                    logging.info(f"✅ Job status updated to {status}")
                else:
                    logging.warning(f"⚠️ Customer {customer_id} not found")
            
            return results
            
        except Exception as e:
            logging.error(f"❌ Job status update failed: {e}")
            return results

    def send_reminder(self, customer_id: int) -> Dict[str, Any]:
        """
        Send appointment reminder SMS.
        
        Args:
            customer_id: Customer ID from CRM
            
        Returns:
            Dictionary with reminder results
        """
        logging.info(f"📱 Sending reminder for customer {customer_id}")
        
        results = {
            "reminder_sent": False,
            "customer_details": None
        }
        
        try:
            if self.crm_available and self.sms_available:
                customer_details = self.crm.get_customer_details(customer_id)
                if customer_details:
                    results["customer_details"] = customer_details
                    customer = customer_details["customer"]
                    customer_name = customer.get("Name", "Customer")
                    customer_phone = customer.get("Phone", "")
                    service_type = customer.get("Last_Service_Type", "Plumbing Service")
                    
                    # For demo purposes, use current time as appointment time
                    # In real system, you'd get this from calendar
                    appointment_time = datetime.now() + timedelta(hours=1)
                    
                    if customer_phone:
                        sms_result = self.sms.send_reminder(customer_phone, customer_name, service_type, appointment_time)
                        results["reminder_sent"] = sms_result.get("success", False)
                        
                        if results["reminder_sent"]:
                            logging.info(f"✅ Reminder sent to {customer_phone}")
                        else:
                            logging.warning(f"⚠️ Reminder failed: {sms_result.get('error')}")
                    else:
                        logging.warning(f"⚠️ No phone number for customer {customer_id}")
                else:
                    logging.warning(f"⚠️ Customer {customer_id} not found")
            
            return results
            
        except Exception as e:
            logging.error(f"❌ Reminder send failed: {e}")
            return results

# Quick functions for easy job booking
def book_emergency_job(phone: str, name: str, service: str, address: str = "", notes: str = "") -> Dict[str, Any]:
    """Quick function to book emergency job respecting scheduling rules."""
    from adapters.phone import find_next_compliant_slot  # lazy import to avoid cycles in adapters
    booking_system = JobBookingSystem()
    earliest = datetime.now() + timedelta(minutes=30)
    appointment_time = find_next_compliant_slot(earliest, emergency=True)
    return booking_system.book_job(phone, name, service, appointment_time, address, notes)

def book_scheduled_job(phone: str, name: str, service: str, appointment_time: datetime, address: str = "", notes: str = "") -> Dict[str, Any]:
    """Quick function to book scheduled job."""
    booking_system = JobBookingSystem()
    return booking_system.book_job(phone, name, service, appointment_time, address, notes)

def update_job_status(customer_id: int, status: str, notes: str = "") -> Dict[str, Any]:
    """Quick function to update job status."""
    booking_system = JobBookingSystem()
    return booking_system.update_job_status(customer_id, status, notes)

def send_appointment_reminder(customer_id: int) -> Dict[str, Any]:
    """Quick function to send appointment reminder."""
    booking_system = JobBookingSystem()
    return booking_system.send_reminder(customer_id)

if __name__ == "__main__":
    # Test the job booking system
    print("🧪 Testing Job Booking System...")
    
    booking_system = JobBookingSystem()
    
    # Test booking a job
    print("\n📅 Testing job booking...")
    result = book_scheduled_job(
        "555-123-4567",
        "John Smith",
        "Emergency Plumbing",
        datetime.now() + timedelta(hours=2),
        "123 Main Street",
        "Kitchen sink is leaking"
    )
    
    print(f"Booking result: {result}")
    
    print("\n✅ Job booking system test completed!") 