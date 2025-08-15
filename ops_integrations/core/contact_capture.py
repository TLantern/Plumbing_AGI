#!/usr/bin/env python3
"""
Immediate Contact Capture for Plumbing AGI
Captures and saves customer information the moment they contact us through any channel
"""

import os
import sys
import logging
from datetime import datetime
from typing import Dict, Any, Optional
from dotenv import load_dotenv

# Add the project root to the Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

# Load environment variables
load_dotenv()

from ops_integrations.adapters.crm import CRMAdapter, InteractionType

logging.basicConfig(level=logging.INFO)

class ContactCapture:
    def __init__(self):
        self.crm = CRMAdapter()
    
    def capture_phone_contact(self, phone_number: str, name: str = None, notes: str = "", 
                            service_type: str = "Phone Inquiry", urgency: str = "Normal") -> Dict[str, Any]:
        """
        Immediately capture phone contact information with automatic CRM status management.
        
        Args:
            phone_number: The phone number that contacted us
            name: Customer name if available (can be None initially)
            notes: Any initial notes from the call
            service_type: Type of service being requested
            urgency: Urgency level (Normal, High, Emergency)
        
        Returns:
            Dictionary with detailed result information
        """
        logging.info(f"📞 Capturing phone contact from {phone_number}")
        
        return self.crm.capture_customer_interaction(
            phone=phone_number,
            name=name,
            interaction_type=InteractionType.PHONE_INBOUND,
            message_content=f"Customer called from {phone_number}. {notes}".strip(),
            service_type=service_type,
            urgency=urgency
        )
    
    def capture_sms_contact(self, phone_number: str, message_content: str = "", name: str = None,
                          service_type: str = "SMS Inquiry", urgency: str = "Normal") -> Dict[str, Any]:
        """
        Immediately capture SMS contact information with automatic CRM status management.
        
        Args:
            phone_number: The phone number that sent SMS
            message_content: The SMS message content
            name: Customer name if available
            service_type: Type of service being requested
            urgency: Urgency level
        
        Returns:
            Dictionary with detailed result information
        """
        logging.info(f"💬 Capturing SMS contact from {phone_number}")
        
        return self.crm.capture_customer_interaction(
            phone=phone_number,
            name=name,
            interaction_type=InteractionType.SMS_INBOUND,
            message_content=message_content,
            service_type=service_type,
            urgency=urgency
        )
    
    def capture_email_contact(self, email: str, subject: str = "", name: str = None, 
                            message_content: str = "", service_type: str = "Email Inquiry",
                            urgency: str = "Normal") -> Dict[str, Any]:
        """
        Immediately capture email contact information with automatic CRM status management.
        
        Args:
            email: The email address that contacted us
            subject: Email subject line
            name: Customer name if available
            message_content: Email content
            service_type: Type of service being requested
            urgency: Urgency level
        
        Returns:
            Dictionary with detailed result information
        """
        logging.info(f"📧 Capturing email contact from {email}")
        
        full_message = f"Subject: {subject}\n{message_content}" if subject else message_content
        
        return self.crm.capture_customer_interaction(
            email=email,
            name=name,
            interaction_type=InteractionType.EMAIL_INBOUND,
            message_content=full_message,
            service_type=service_type,
            urgency=urgency
        )
    
    def capture_website_contact(self, name: str, email: str = "", phone: str = "", 
                              message: str = "", service_type: str = "Website Inquiry",
                              urgency: str = "Normal") -> Dict[str, Any]:
        """
        Immediately capture website form contact information with automatic CRM status management.
        
        Args:
            name: Customer name from form
            email: Email from form
            phone: Phone from form
            message: Message from form
            service_type: Type of service being requested
            urgency: Urgency level
        
        Returns:
            Dictionary with detailed result information
        """
        logging.info(f"🌐 Capturing website contact from {name}")
        
        return self.crm.capture_customer_interaction(
            phone=phone if phone else None,
            email=email if email else None,
            name=name,
            interaction_type=InteractionType.WEBSITE_FORM,
            message_content=message,
            service_type=service_type,
            urgency=urgency
        )
    
    def capture_referral_contact(self, name: str, phone: str = "", email: str = "", 
                               referred_by: str = "", notes: str = "",
                               service_type: str = "Referral Inquiry", urgency: str = "Normal") -> Dict[str, Any]:
        """
        Immediately capture referral contact information with automatic CRM status management.
        
        Args:
            name: Customer name
            phone: Phone number
            email: Email address
            referred_by: Who referred them
            notes: Additional notes
            service_type: Type of service being requested
            urgency: Urgency level
        
        Returns:
            Dictionary with detailed result information
        """
        logging.info(f"👥 Capturing referral contact: {name}")
        
        message_content = f"Referred by: {referred_by}. {notes}".strip()
        
        return self.crm.capture_customer_interaction(
            phone=phone if phone else None,
            email=email if email else None,
            name=name,
            interaction_type=InteractionType.REFERRAL,
            message_content=message_content,
            service_type=service_type,
            urgency=urgency
        )
    
    def update_service_status(self, customer_id: int, service_status: str, notes: str = "") -> Dict[str, Any]:
        """
        Update customer service status (scheduled, in progress, completed).
        
        Args:
            customer_id: The ID of the customer
            service_status: New service status (scheduled, in_progress, completed, follow_up)
            notes: Additional notes about the status change
        
        Returns:
            Dictionary with result information
        """
        try:
            success = self.crm.update_service_status(customer_id, service_status, notes)
            
            if success:
                return {
                    "success": True,
                    "message": f"Service status updated to: {service_status}",
                    "customer_id": customer_id,
                    "new_status": service_status
                }
            else:
                return {
                    "success": False,
                    "error": "Failed to update service status",
                    "customer_id": customer_id
                }
                
        except Exception as e:
            logging.error(f"Failed to update service status for customer {customer_id}: {e}")
            return {"success": False, "error": str(e), "customer_id": customer_id}
    
    def get_customer_info(self, customer_id: int) -> Optional[Dict[str, Any]]:
        """
        Get complete customer information including interaction history.
        
        Args:
            customer_id: The ID of the customer
            
        Returns:
            Dictionary with customer details or None if not found
        """
        return self.crm.get_customer_details(customer_id)
    
    def log_interaction_result(self, result: Dict[str, Any]) -> None:
        """Log the result of a customer interaction capture."""
        if result.get('success'):
            customer_name = result.get('customer_name', 'Unknown')
            customer_status = result.get('customer_status', 'Unknown')
            is_new = result.get('is_new_customer', False)
            interactions = result.get('previous_interactions', 0)
            
            status_emoji = {
                'New': '🆕',
                'Contacted': '📞',
                'Quoted': '💰',
                'Scheduled': '📅',
                'In Progress': '🔧',
                'Completed': '✅',
                'Follow Up Required': '🔄',
                'Priority Customer': '⭐'
            }.get(customer_status, '📋')
            
            new_indicator = " (NEW CUSTOMER)" if is_new else f" ({interactions} previous interactions)"
            
            logging.info(f"✅ {status_emoji} Customer captured: {customer_name} - Status: {customer_status}{new_indicator}")
            
        else:
            error = result.get('error', 'Unknown error')
            logging.error(f"❌ Failed to capture customer: {error}")

# Enhanced quick functions for different contact types
def phone_rang(phone_number: str, caller_name: str = None, notes: str = "", 
              service_type: str = "Phone Inquiry", urgency: str = "Normal") -> Dict[str, Any]:
    """Enhanced function to call when phone rings with service context."""
    capturer = ContactCapture()
    result = capturer.capture_phone_contact(phone_number, caller_name, notes, service_type, urgency)
    capturer.log_interaction_result(result)
    return result

def sms_received(phone_number: str, message: str, sender_name: str = None,
                service_type: str = "SMS Inquiry", urgency: str = "Normal") -> Dict[str, Any]:
    """Enhanced function to call when SMS is received with service context."""
    capturer = ContactCapture()
    result = capturer.capture_sms_contact(phone_number, message, sender_name, service_type, urgency)
    capturer.log_interaction_result(result)
    return result

def email_received(email_address: str, subject: str = "", sender_name: str = None, 
                  content: str = "", service_type: str = "Email Inquiry", 
                  urgency: str = "Normal") -> Dict[str, Any]:
    """Enhanced function to call when email is received with service context."""
    capturer = ContactCapture()
    result = capturer.capture_email_contact(email_address, subject, sender_name, content, service_type, urgency)
    capturer.log_interaction_result(result)
    return result

def website_form_submitted(name: str, email: str = "", phone: str = "", message: str = "",
                          service_type: str = "Website Inquiry", urgency: str = "Normal") -> Dict[str, Any]:
    """Enhanced function to call when website form is submitted with service context."""
    capturer = ContactCapture()
    result = capturer.capture_website_contact(name, email, phone, message, service_type, urgency)
    capturer.log_interaction_result(result)
    return result

def got_referral(name: str, phone: str = "", email: str = "", referred_by: str = "",
                service_type: str = "Referral Inquiry", urgency: str = "Normal") -> Dict[str, Any]:
    """Enhanced function to call when you get a referral with service context."""
    capturer = ContactCapture()
    result = capturer.capture_referral_contact(name, phone, email, referred_by, "", service_type, urgency)
    capturer.log_interaction_result(result)
    return result

# New service management functions
def schedule_service(customer_id: int, notes: str = "") -> Dict[str, Any]:
    """Mark a customer as having service scheduled."""
    capturer = ContactCapture()
    return capturer.update_service_status(customer_id, "scheduled", notes)

def start_service(customer_id: int, notes: str = "") -> Dict[str, Any]:
    """Mark a customer's service as in progress."""
    capturer = ContactCapture()
    return capturer.update_service_status(customer_id, "in_progress", notes)

def complete_service(customer_id: int, notes: str = "") -> Dict[str, Any]:
    """Mark a customer's service as completed."""
    capturer = ContactCapture()
    return capturer.update_service_status(customer_id, "completed", notes)

def needs_follow_up(customer_id: int, notes: str = "") -> Dict[str, Any]:
    """Mark a customer as needing follow-up."""
    capturer = ContactCapture()
    return capturer.update_service_status(customer_id, "follow_up", notes)

if __name__ == "__main__":
    # Test the enhanced contact capture system
    capturer = ContactCapture()
    
    print("🧪 Testing Enhanced Contact Capture System...")
    
    # Test phone contact with service context
    print("\n📞 Testing phone contact...")
    result = phone_rang("555-123-4567", "Jane Doe", "Kitchen sink leaking badly", "Emergency Plumbing", "Emergency")
    print(f"Phone result: {result.get('message', result.get('error'))}")
    
    if result.get('success'):
        customer_id = result['customer_id']
        print(f"Customer ID: {customer_id}, Status: {result.get('customer_status')}")
        
        # Test service status updates
        print("\n🔧 Testing service status updates...")
        schedule_result = schedule_service(customer_id, "Scheduled for tomorrow morning")
        print(f"Schedule result: {schedule_result.get('message', schedule_result.get('error'))}")
        
        start_result = start_service(customer_id, "Technician arrived on site")
        print(f"Start service result: {start_result.get('message', start_result.get('error'))}")
        
        complete_result = complete_service(customer_id, "Sink repaired, new faucet installed")
        print(f"Complete service result: {complete_result.get('message', complete_result.get('error'))}")
    
    # Test SMS contact
    print("\n💬 Testing SMS contact...")
    sms_result = sms_received("555-987-6543", "Hi, need plumber for bathroom renovation quote", urgency="Normal")
    print(f"SMS result: {sms_result.get('message', sms_result.get('error'))}")
    
    # Test email contact
    print("\n📧 Testing email contact...")
    email_result = email_received("customer@email.com", "Plumbing Quote Request", "Bob Smith", 
                                "Need quote for kitchen remodel plumbing", "Quote Request")
    print(f"Email result: {email_result.get('message', email_result.get('error'))}")
    
    print("\n✅ Enhanced contact capture testing completed!") 