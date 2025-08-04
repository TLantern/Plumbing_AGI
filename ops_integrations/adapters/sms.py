import os
import logging
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Try to import Twilio, but don't fail if it's not available
try:
    from twilio.rest import Client
    from twilio.base.exceptions import TwilioException
    TWILIO_AVAILABLE = True
except ImportError:
    TWILIO_AVAILABLE = False
    logging.warning("Twilio not installed. Run: pip install twilio")

class SMSAdapter:
    def __init__(self):
        self.account_sid = os.getenv('TWILIO_ACCOUNT_SID')
        self.auth_token = os.getenv('TWILIO_AUTH_TOKEN')
        self.from_number = os.getenv('TWILIO_FROM_NUMBER')
        
        if not all([self.account_sid, self.auth_token, self.from_number]):
            logging.warning("Twilio not configured - missing environment variables")
            self.enabled = False
        else:
            self.enabled = True
            if TWILIO_AVAILABLE:
                self.client = Client(self.account_sid, self.auth_token)
            else:
                self.enabled = False
                logging.error("Twilio library not available")

    def send_sms(self, to_number: str, message: str) -> Dict[str, Any]:
        """Send SMS message using Twilio."""
        if not self.enabled:
            return {"success": False, "error": "SMS not configured"}
        
        try:
            message = self.client.messages.create(
                body=message,
                from_=self.from_number,
                to=to_number
            )
            
            logging.info(f"✅ SMS sent successfully to {to_number}: {message.sid}")
            return {
                "success": True,
                "message_sid": message.sid,
                "status": message.status,
                "to": to_number
            }
            
        except TwilioException as e:
            logging.error(f"❌ SMS send failed: {e}")
            return {"success": False, "error": str(e)}

    def send_booking_confirmation(self, customer_phone: str, customer_name: str, 
                                service_type: str, appointment_time: datetime, 
                                address: str = "") -> Dict[str, Any]:
        """Send booking confirmation SMS."""
        formatted_time = appointment_time.strftime("%A, %B %d at %I:%M %p")
        
        message = f"""Hi {customer_name}! 

Your {service_type} appointment is confirmed for {formatted_time}.

{f'Address: {address}' if address else ''}

We'll send a reminder 1 hour before. Call us if you need to reschedule.

Thank you for choosing our plumbing services!"""

        return self.send_sms(customer_phone, message)

    def send_reminder(self, customer_phone: str, customer_name: str, 
                     service_type: str, appointment_time: datetime) -> Dict[str, Any]:
        """Send appointment reminder SMS."""
        formatted_time = appointment_time.strftime("%I:%M %p")
        
        message = f"""Hi {customer_name}!

Reminder: Your {service_type} appointment is today at {formatted_time}.

Please ensure someone is available to let us in. We'll call when we're on our way.

Thank you!"""

        return self.send_sms(customer_phone, message)

    def send_eta_update(self, customer_phone: str, customer_name: str, 
                       eta_minutes: int) -> Dict[str, Any]:
        """Send ETA update SMS."""
        message = f"""Hi {customer_name}!

We're on our way and will arrive in approximately {eta_minutes} minutes.

Please ensure someone is available to let us in.

Thank you for your patience!"""

        return self.send_sms(customer_phone, message)

    def send_job_completion(self, customer_phone: str, customer_name: str, 
                          service_type: str, invoice_amount: float = None) -> Dict[str, Any]:
        """Send job completion SMS."""
        message = f"""Hi {customer_name}!

Your {service_type} has been completed successfully.

{f'Invoice amount: ${invoice_amount:.2f}' if invoice_amount else ''}

Thank you for choosing our services! We appreciate your business."""

        return self.send_sms(customer_phone, message)

# Quick functions for easy SMS sending
def send_booking_sms(phone: str, name: str, service: str, appointment_time: datetime, address: str = "") -> Dict[str, Any]:
    """Quick function to send booking confirmation."""
    sms = SMSAdapter()
    return sms.send_booking_confirmation(phone, name, service, appointment_time, address)

def send_reminder_sms(phone: str, name: str, service: str, appointment_time: datetime) -> Dict[str, Any]:
    """Quick function to send appointment reminder."""
    sms = SMSAdapter()
    return sms.send_reminder(phone, name, service, appointment_time)

def send_eta_sms(phone: str, name: str, eta_minutes: int) -> Dict[str, Any]:
    """Quick function to send ETA update."""
    sms = SMSAdapter()
    return sms.send_eta_update(phone, name, eta_minutes)

def send_completion_sms(phone: str, name: str, service: str, amount: float = None) -> Dict[str, Any]:
    """Quick function to send job completion notification."""
    sms = SMSAdapter()
    return sms.send_job_completion(phone, name, service, amount) 