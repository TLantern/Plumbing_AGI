#!/usr/bin/env python3
"""
Customer Inquiry Handler for Plumbing AGI
Processes customer inquiries and saves them to Baserow CRM
"""

import os
import logging
from datetime import datetime
from typing import Dict, Any, Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from ..adapters.integrations.crm import CRMAdapter

logging.basicConfig(level=logging.INFO)

class InquiryHandler:
    def __init__(self):
        self.crm = CRMAdapter()
    
    def process_inquiry(self, inquiry_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a customer inquiry and save it to the CRM.
        
        Args:
            inquiry_data: Dictionary containing:
                - name: Customer name
                - email: Customer email
                - phone: Customer phone
                - address: Customer address (optional)
                - service_type: Type of service needed
                - description: Description of the inquiry
                - urgency: Urgency level (Low/Normal/High/Emergency)
                - source: Where the inquiry came from (Phone/Email/Website/etc)
                - contact_method: Preferred contact method
        
        Returns:
            Dictionary with result information
        """
        logging.info(f"Processing inquiry from {inquiry_data.get('name', 'Unknown')}")
        
        # Validate required fields
        required_fields = ['name', 'service_type']
        missing_fields = [field for field in required_fields if not inquiry_data.get(field)]
        
        if missing_fields:
            error_msg = f"Missing required fields: {', '.join(missing_fields)}"
            logging.error(error_msg)
            return {"success": False, "error": error_msg}
        
        # Add timestamp and processing info
        inquiry_data['received_at'] = datetime.now().isoformat()
        inquiry_data['processed_by'] = 'Plumbing AGI System'
        
        # Save to CRM
        try:
            result = self.crm.save_customer_inquiry(inquiry_data)
            
            if result and not result.get('error'):
                logging.info(f"Successfully processed inquiry: {result.get('id', 'Unknown ID')}")
                return {
                    "success": True,
                    "inquiry_id": result.get('id'),
                    "message": "Inquiry processed and saved to CRM",
                    "customer_saved": True
                }
            else:
                logging.error(f"Failed to save inquiry: {result.get('error', 'Unknown error')}")
                return {
                    "success": False,
                    "error": result.get('error', 'Failed to save inquiry'),
                    "saved_locally": True
                }
                
        except Exception as e:
            logging.error(f"Error processing inquiry: {e}")
            return {
                "success": False,
                "error": str(e),
                "saved_locally": True
            }
    
    def create_sample_inquiry(self) -> Dict[str, Any]:
        """Create a sample inquiry for testing."""
        sample_inquiry = {
            "name": "John Smith",
            "email": "john.smith@email.com",
            "phone": "555-123-4567",
            "address": "123 Main Street, Anytown, USA",
            "service_type": "Emergency Plumbing",
            "description": "Kitchen sink is leaking heavily, water everywhere!",
            "urgency": "High",
            "source": "Phone Call",
            "contact_method": "Phone"
        }
        
        return self.process_inquiry(sample_inquiry)

def handle_phone_inquiry(name: str, phone: str, service_type: str, description: str = "", urgency: str = "Normal") -> Dict[str, Any]:
    """
    Quick function to handle phone inquiries.
    
    Args:
        name: Customer name
        phone: Customer phone number
        service_type: Type of service (Emergency Plumbing, Drain Cleaning, Installation, etc.)
        description: Description of the problem
        urgency: Urgency level (Low/Normal/High/Emergency)
    
    Returns:
        Result dictionary
    """
    handler = InquiryHandler()
    
    inquiry_data = {
        "name": name,
        "phone": phone,
        "service_type": service_type,
        "description": description,
        "urgency": urgency,
        "source": "Phone Call",
        "contact_method": "Phone"
    }
    
    return handler.process_inquiry(inquiry_data)

def handle_email_inquiry(name: str, email: str, service_type: str, description: str = "", urgency: str = "Normal") -> Dict[str, Any]:
    """
    Quick function to handle email inquiries.
    
    Args:
        name: Customer name
        email: Customer email
        service_type: Type of service
        description: Description of the problem
        urgency: Urgency level
    
    Returns:
        Result dictionary
    """
    handler = InquiryHandler()
    
    inquiry_data = {
        "name": name,
        "email": email,
        "service_type": service_type,
        "description": description,
        "urgency": urgency,
        "source": "Email",
        "contact_method": "Email"
    }
    
    return handler.process_inquiry(inquiry_data)

def handle_website_inquiry(name: str, email: str, phone: str, service_type: str, description: str = "", urgency: str = "Normal") -> Dict[str, Any]:
    """
    Quick function to handle website form inquiries.
    
    Args:
        name: Customer name
        email: Customer email
        phone: Customer phone
        service_type: Type of service
        description: Description of the problem
        urgency: Urgency level
    
    Returns:
        Result dictionary
    """
    handler = InquiryHandler()
    
    inquiry_data = {
        "name": name,
        "email": email,
        "phone": phone,
        "service_type": service_type,
        "description": description,
        "urgency": urgency,
        "source": "Website",
        "contact_method": "Email"
    }
    
    return handler.process_inquiry(inquiry_data)

if __name__ == "__main__":
    # Test the inquiry handler
    handler = InquiryHandler()
    
    print("🧪 Testing Inquiry Handler...")
    result = handler.create_sample_inquiry()
    
    if result["success"]:
        print(f"✅ Sample inquiry processed successfully: {result.get('inquiry_id')}")
    else:
        print(f"❌ Failed to process inquiry: {result.get('error')}")
        if result.get('saved_locally'):
            print("💾 Inquiry saved to local backup") 