import os
import logging
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from dotenv import load_dotenv
import openai
from flows import intents
from prompts.prompt_layer import (
    INTENT_CLASSIFICATION_PROMPT,
    FOLLOW_UP_PROMPTS,
    SCHEDULER_PROMPT,
)

# Load environment variables
load_dotenv()

# Try to import ClickSend, but don't fail if it's not available
try:
    import clicksend_client  # type: ignore
    from clicksend_client import SmsMessage, SmsMessageCollection  # type: ignore
    from clicksend_client.rest import ApiException as ClickSendApiException  # type: ignore
    CLICKSEND_AVAILABLE = True
except ImportError:
    CLICKSEND_AVAILABLE = False
    logging.warning("ClickSend not installed. Run: pip install clicksend-client")

class SMSAdapter:
    def __init__(self):
        # ClickSend configuration
        self.cs_username = os.getenv('CLICKSEND_USERNAME')
        self.cs_api_key = os.getenv('CLICKSEND_API_KEY')
        self.from_number = os.getenv('CLICKSEND_FROM_NUMBER')
        self.cs_source = os.getenv('CLICKSEND_SOURCE', 'plumbing-agi')
        # Ensure proper format for E.164 number if provided
        if self.from_number and not self.from_number.startswith('+'):
            self.from_number = '+1' + self.from_number
        
        # OpenAI configuration
        openai.api_key = os.getenv('OPENAI_API_KEY')
        
        # Enable only if ClickSend is available and credentials are present
        if not CLICKSEND_AVAILABLE or not self.cs_username or not self.cs_api_key:
            logging.warning("ClickSend SMS not configured - missing environment variables or library")
            self.enabled = False
            self.cs_api = None
        else:
            self.enabled = True
            configuration = clicksend_client.Configuration()  # type: ignore
            configuration.username = self.cs_username  # type: ignore[attr-defined]
            configuration.password = self.cs_api_key  # type: ignore[attr-defined]
            self.cs_api = clicksend_client.SMSApi(clicksend_client.ApiClient(configuration))  # type: ignore

    def send_sms(self, to_number: str, message: str) -> Dict[str, Any]:
        """Send SMS message using ClickSend."""
        if not self.enabled or self.cs_api is None:
            return {"success": False, "error": "SMS not configured"}
        
        try:
            sms_message = SmsMessage(  # type: ignore
                source=self.cs_source,
                body=message,
                to=to_number,
            )
            # Some accounts may be configured with a default sender ID; we skip setting 'from' explicitly
            payload = SmsMessageCollection(messages=[sms_message])  # type: ignore
            api_response = self.cs_api.sms_send_post(payload)  # type: ignore
            response_str = str(api_response)
            logging.info(f"✅ SMS sent request to {to_number} via ClickSend")
            return {
                "success": True,
                "raw_response": response_str,
                "to": to_number,
            }
            
        except ClickSendApiException as e:  # type: ignore
            logging.error(f"❌ ClickSend API error: {e}")
            return {"success": False, "error": str(e)}
        except Exception as e:
            logging.error(f"❌ SMS send failed: {e}")
            return {"success": False, "error": str(e)}

    def classify_intent(self, message_body: str) -> str:
        """Classify the intent of an incoming message."""
        try:
            response = openai.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": INTENT_CLASSIFICATION_PROMPT},
                    {"role": "user", "content": message_body}
                ],
                max_tokens=20,
                temperature=0.1  # Low temperature for deterministic results
            )
            
            intent = response.choices[0].message.content.strip().upper()
            
            # Validate that the intent is one we recognize
            valid_intents = intents.get_intent_tags()
            if intent in valid_intents:
                return intent
            else:
                logging.warning(f"Unknown intent returned: {intent}, falling back to GENERAL_INQUIRY")
                return "GENERAL_INQUIRY"
                
        except Exception as e:
            logging.error(f"❌ Error classifying intent: {e}")
            return "GENERAL_INQUIRY"

    def generate_follow_up_response(self, message_body: str, intent_tag: str) -> str:
        """Generate a follow-up response based on the classified intent."""
        try:
            # Get the follow-up prompt for this intent
            follow_up_prompt = FOLLOW_UP_PROMPTS.get(intent_tag, FOLLOW_UP_PROMPTS["GENERAL_INQUIRY"])
            
            response = openai.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": follow_up_prompt},
                    {"role": "user", "content": f"Customer message: {message_body}"}
                ],
                max_tokens=160,
                temperature=0.7
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            logging.error(f"❌ Error generating follow-up response: {e}")
            return "Hey! How can I help with your plumbing needs for today?"

    def handle_incoming_message(self, from_number: str, message_body: str) -> Dict[str, Any]:
        """Handle incoming SMS messages with intent classification and follow-up."""
        try:
            logging.info(f"📨 Incoming SMS from {from_number}: {message_body}")
            
            # Step 1: Classify the intent
            intent_tag = self.classify_intent(message_body)
            logging.info(f"🎯 Classified intent: {intent_tag}")
            
            # Step 2: Generate appropriate follow-up response
            response_text = self.generate_follow_up_response(message_body, intent_tag)
            logging.info(f"💬 Generated response: {response_text}")
            
            # Step 3: Send the response
            result = self.send_sms(from_number, response_text)
            
            # Add intent information to the result
            result["intent_tag"] = intent_tag
            result["original_message"] = message_body
            
            return result
            
        except Exception as e:
            logging.error(f"❌ Error handling incoming message: {e}")
            # Fallback response
            fallback = "Hey! How can I help with your plumbing needs for today?"
            return self.send_sms(from_number, fallback)

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

def handle_incoming_sms(from_number: str, message_body: str) -> Dict[str, Any]:
    """Quick function to handle incoming SMS messages."""
    sms = SMSAdapter()
    return sms.handle_incoming_message(from_number, message_body) 