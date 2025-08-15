import os
import requests
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from enum import Enum
from dotenv import load_dotenv
# Replace direct relative imports with dual-mode imports (package + script fallback)
try:
    from ops_integrations.core.models import Customer
except Exception:
    import sys as _sys
    import os as _os
    _CURRENT_DIR = _os.path.dirname(__file__)
    _OPS_ROOT = _os.path.abspath(_os.path.join(_CURRENT_DIR, '..', '..'))
    if _OPS_ROOT not in _sys.path:
        _sys.path.insert(0, _OPS_ROOT)
    from ops_integrations.core.models import Customer

# Load environment variables
load_dotenv()

class CustomerStatus(Enum):
    """Customer status enum for tracking customer lifecycle."""
    NEW = "New"
    CONTACTED = "Contacted"
    QUOTED = "Quoted"
    SCHEDULED = "Scheduled"
    IN_PROGRESS = "In Progress"
    COMPLETED = "Completed"
    FOLLOW_UP = "Follow Up Required"
    INACTIVE = "Inactive"
    PRIORITY = "Priority Customer"

class InteractionType(Enum):
    """Interaction type enum for tracking different communication methods."""
    PHONE_INBOUND = "Phone (Inbound)"
    PHONE_OUTBOUND = "Phone (Outbound)"
    SMS_INBOUND = "SMS (Inbound)"
    SMS_OUTBOUND = "SMS (Outbound)"
    EMAIL_INBOUND = "Email (Inbound)"
    EMAIL_OUTBOUND = "Email (Outbound)"
    WEBSITE_FORM = "Website Form"
    REFERRAL = "Referral"
    APPOINTMENT = "Appointment"
    SERVICE_COMPLETION = "Service Completion"

class CRMAdapter:
    def __init__(self):
        self.base_url = os.getenv('BASEROW_API_URL', 'https://api.baserow.io')
        self.api_token = os.getenv('BASEROW_API_TOKEN')
        self.database_id = os.getenv('BASEROW_DATABASE_ID')
        self.customers_table_id = os.getenv('BASEROW_CUSTOMERS_TABLE_ID')
        self.inquiries_table_id = os.getenv('BASEROW_INQUIRIES_TABLE_ID')
        self.interactions_table_id = os.getenv('BASEROW_INTERACTIONS_TABLE_ID')
        
        if not all([self.api_token, self.database_id, self.customers_table_id]):
            logging.warning("Baserow CRM not configured - missing required environment variables")
            self.enabled = False
        else:
            self.enabled = True
        
        self.headers = {
            "Authorization": f"Token {self.api_token}",
            "Content-Type": "application/json"
        }

    def capture_customer_interaction(self, phone: str = None, email: str = None, 
                                   name: str = None, interaction_type: InteractionType = InteractionType.PHONE_INBOUND,
                                   message_content: str = "", service_type: str = "General Inquiry",
                                   urgency: str = "Normal") -> Dict[str, Any]:
        """
        Capture any customer interaction (call, text, email) and automatically manage their CRM status.
        
        Args:
            phone: Customer phone number
            email: Customer email address
            name: Customer name (optional, will be auto-generated if not provided)
            interaction_type: Type of interaction (call, SMS, email, etc.)
            message_content: Content of the interaction
            service_type: Type of service being requested
            urgency: Urgency level
            
        Returns:
            Dictionary with customer info and interaction results
        """
        if not self.enabled:
            return self._fallback_capture_interaction(phone, email, name, interaction_type, message_content)
        
        try:
            # Find or create customer
            customer_record = self._find_or_create_customer(phone, email, name)
            
            if not customer_record:
                logging.error("Failed to find or create customer record")
                return self._fallback_capture_interaction(phone, email, name, interaction_type, message_content)
            
            customer_id = customer_record['id']
            
            # Record the interaction
            interaction_id = self._record_interaction(
                customer_id, interaction_type, message_content, service_type, urgency
            )
            
            # Update customer status based on interaction
            updated_status = self._update_customer_status(customer_record, interaction_type, service_type, urgency)
            
            # Create or update inquiry if needed
            inquiry_id = None
            if service_type != "General Contact":
                inquiry_id = self._create_or_update_inquiry(
                    customer_id, service_type, message_content, urgency
                )
            
            logging.info(f"Successfully captured interaction for customer {customer_id}, status: {updated_status}")
            
            return {
                "success": True,
                "customer_id": customer_id,
                "customer_name": customer_record.get('Name', name or 'Unknown'),
                "customer_status": updated_status,
                "interaction_id": interaction_id,
                "inquiry_id": inquiry_id,
                "is_new_customer": customer_record.get('_is_new', False),
                "previous_interactions": customer_record.get('Total_Interactions', 0),
                "message": f"Customer interaction captured successfully"
            }
            
        except Exception as e:
            logging.error(f"Failed to capture customer interaction: {e}")
            return self._fallback_capture_interaction(phone, email, name, interaction_type, message_content)

    def _find_or_create_customer(self, phone: str = None, email: str = None, name: str = None) -> Optional[Dict[str, Any]]:
        """Find existing customer or create new one."""
        try:
            # Try to find existing customer
            existing_customer = self._find_existing_customer(email, phone)
            
            if existing_customer:
                # Update last contact time
                self._update_customer_last_contact(existing_customer['id'])
                existing_customer['_is_new'] = False
                return existing_customer
            
            # Create new customer
            if not name:
                if email:
                    name = f"Customer ({email.split('@')[0]})"
                elif phone:
                    name = f"Customer ({phone[-4:]})"
                else:
                    name = "Unknown Customer"
            
            customer_record = {
                "Name": name,
                "Email": email or "",
                "Phone": phone or "",
                "Status": CustomerStatus.NEW.value,
                "First_Contact": datetime.now().isoformat(),
                "Last_Contact": datetime.now().isoformat(),
                "Total_Interactions": 0,
                "Priority_Level": "Normal",
                "Source": "Direct Contact"
            }
            
            url = f"{self.base_url}/api/database/rows/table/{self.customers_table_id}/"
            response = requests.post(url, headers=self.headers, json=customer_record)
            response.raise_for_status()
            
            result = response.json()
            result['_is_new'] = True
            logging.info(f"Created new customer: {result['id']} - {name}")
            return result
            
        except Exception as e:
            logging.error(f"Failed to find or create customer: {e}")
            return None

    def _record_interaction(self, customer_id: int, interaction_type: InteractionType, 
                          content: str, service_type: str, urgency: str) -> Optional[int]:
        """Record a customer interaction."""
        if not self.interactions_table_id:
            logging.warning("No interactions table configured")
            return None
            
        try:
            interaction_record = {
                "Customer": customer_id,
                "Type": interaction_type.value,
                "Content": content[:1000],  # Limit content length
                "Service_Type": service_type,
                "Urgency": urgency,
                "Timestamp": datetime.now().isoformat(),
                "Direction": "Inbound" if "Inbound" in interaction_type.value else "Outbound"
            }
            
            url = f"{self.base_url}/api/database/rows/table/{self.interactions_table_id}/"
            response = requests.post(url, headers=self.headers, json=interaction_record)
            response.raise_for_status()
            
            result = response.json()
            
            # Update customer interaction count
            self._increment_customer_interactions(customer_id)
            
            return result.get('id')
            
        except Exception as e:
            logging.error(f"Failed to record interaction: {e}")
            return None

    def _update_customer_status(self, customer_record: Dict[str, Any], 
                               interaction_type: InteractionType, service_type: str, urgency: str) -> str:
        """Update customer status based on interaction and service type."""
        try:
            current_status = customer_record.get('Status', CustomerStatus.NEW.value)
            customer_id = customer_record['id']
            
            # Determine new status based on interaction and service context
            new_status = self._determine_new_status(current_status, interaction_type, service_type, urgency)
            
            # Update customer record
            update_data = {
                "Status": new_status,
                "Last_Service_Type": service_type,
                "Last_Contact": datetime.now().isoformat()
            }
            
            # Set priority level based on urgency
            if urgency in ["High", "Emergency"]:
                update_data["Priority_Level"] = "High"
            elif urgency == "Low":
                update_data["Priority_Level"] = "Low"
            
            url = f"{self.base_url}/api/database/rows/table/{self.customers_table_id}/{customer_id}/"
            response = requests.patch(url, headers=self.headers, json=update_data)
            response.raise_for_status()
            
            logging.info(f"Updated customer {customer_id} status: {current_status} -> {new_status}")
            return new_status
            
        except Exception as e:
            logging.error(f"Failed to update customer status: {e}")
            return current_status

    def _determine_new_status(self, current_status: str, interaction_type: InteractionType, 
                            service_type: str, urgency: str) -> str:
        """Determine new customer status based on interaction context."""
        
        # Emergency situations always get priority status
        if urgency == "Emergency":
            return CustomerStatus.PRIORITY.value
        
        # If customer is new and this is their first contact
        if current_status == CustomerStatus.NEW.value:
            return CustomerStatus.CONTACTED.value
        
        # Service-specific status updates
        if "Quote" in service_type or "Estimate" in service_type:
            return CustomerStatus.QUOTED.value
        elif "Schedule" in service_type or "Appointment" in service_type:
            return CustomerStatus.SCHEDULED.value
        elif interaction_type == InteractionType.SERVICE_COMPLETION:
            return CustomerStatus.COMPLETED.value
        elif "Follow" in service_type or urgency == "High":
            return CustomerStatus.FOLLOW_UP.value
        
        # Default progression for contacted customers
        if current_status == CustomerStatus.CONTACTED.value and service_type != "General Inquiry":
            return CustomerStatus.QUOTED.value
        
        # Keep current status if no specific change is needed
        return current_status

    def _create_or_update_inquiry(self, customer_id: int, service_type: str, 
                                 description: str, urgency: str) -> Optional[int]:
        """Create or update customer inquiry."""
        if not self.inquiries_table_id:
            logging.warning("No inquiries table configured")
            return None
            
        try:
            inquiry_record = {
                "Customer": customer_id,
                "Service_Type": service_type,
                "Description": description[:500],
                "Urgency": urgency,
                "Status": "New",
                "Inquiry_Date": datetime.now().isoformat(),
                "Follow_Up_Required": urgency in ["High", "Emergency"]
            }
            
            url = f"{self.base_url}/api/database/rows/table/{self.inquiries_table_id}/"
            response = requests.post(url, headers=self.headers, json=inquiry_record)
            response.raise_for_status()
            
            result = response.json()
            return result.get('id')
            
        except Exception as e:
            logging.error(f"Failed to create inquiry: {e}")
            return None

    def update_service_status(self, customer_id: int, service_status: str, notes: str = "") -> bool:
        """Update customer service status (scheduled, in progress, completed)."""
        try:
            status_mapping = {
                "scheduled": CustomerStatus.SCHEDULED.value,
                "in_progress": CustomerStatus.IN_PROGRESS.value,
                "completed": CustomerStatus.COMPLETED.value,
                "follow_up": CustomerStatus.FOLLOW_UP.value
            }
            
            new_status = status_mapping.get(service_status.lower(), CustomerStatus.CONTACTED.value)
            
            update_data = {
                "Status": new_status,
                "Last_Contact": datetime.now().isoformat()
            }
            
            if notes:
                update_data["Notes"] = notes
            
            url = f"{self.base_url}/api/database/rows/table/{self.customers_table_id}/{customer_id}/"
            response = requests.patch(url, headers=self.headers, json=update_data)
            response.raise_for_status()
            
            # Record service status change as interaction
            if self.interactions_table_id:
                self._record_interaction(
                    customer_id, 
                    InteractionType.SERVICE_COMPLETION,
                    f"Service status updated to: {service_status}. {notes}",
                    "Status Update",
                    "Normal"
                )
            
            logging.info(f"Updated service status for customer {customer_id}: {new_status}")
            return True
            
        except Exception as e:
            logging.error(f"Failed to update service status: {e}")
            return False

    def get_customer_details(self, customer_id: int) -> Optional[Dict[str, Any]]:
        """Get complete customer details including interaction history."""
        if not self.enabled:
            return None
            
        try:
            # Get customer record
            url = f"{self.base_url}/api/database/rows/table/{self.customers_table_id}/{customer_id}/"
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            customer = response.json()
            
            # Get recent interactions
            interactions = []
            if self.interactions_table_id:
                interactions_url = f"{self.base_url}/api/database/rows/table/{self.interactions_table_id}/"
                params = {"filter__Customer__equal": customer_id, "order_by": "-Timestamp"}
                interactions_response = requests.get(interactions_url, headers=self.headers, params=params)
                if interactions_response.status_code == 200:
                    interactions = interactions_response.json().get('results', [])[:10]  # Last 10 interactions
            
            # Get open inquiries
            inquiries = []
            if self.inquiries_table_id:
                inquiries_url = f"{self.base_url}/api/database/rows/table/{self.inquiries_table_id}/"
                params = {"filter__Customer__equal": customer_id, "filter__Status__not_equal": "Completed"}
                inquiries_response = requests.get(inquiries_url, headers=self.headers, params=params)
                if inquiries_response.status_code == 200:
                    inquiries = inquiries_response.json().get('results', [])
            
            return {
                "customer": customer,
                "recent_interactions": interactions,
                "open_inquiries": inquiries
            }
            
        except Exception as e:
            logging.error(f"Failed to get customer details: {e}")
            return None

    # Helper methods
    def _update_customer_last_contact(self, customer_id: int):
        """Update customer's last contact timestamp."""
        try:
            url = f"{self.base_url}/api/database/rows/table/{self.customers_table_id}/{customer_id}/"
            update_data = {"Last_Contact": datetime.now().isoformat()}
            requests.patch(url, headers=self.headers, json=update_data)
        except Exception as e:
            logging.error(f"Failed to update last contact: {e}")

    def _increment_customer_interactions(self, customer_id: int):
        """Increment customer's total interaction count."""
        try:
            # Get current count
            url = f"{self.base_url}/api/database/rows/table/{self.customers_table_id}/{customer_id}/"
            response = requests.get(url, headers=self.headers)
            if response.status_code == 200:
                current_count = response.json().get('Total_Interactions', 0)
                update_data = {"Total_Interactions": current_count + 1}
                requests.patch(url, headers=self.headers, json=update_data)
        except Exception as e:
            logging.error(f"Failed to increment interaction count: {e}")

    def _fallback_capture_interaction(self, phone: str, email: str, name: str, 
                                    interaction_type: InteractionType, content: str) -> Dict[str, Any]:
        """Fallback method when Baserow is not available."""
        logging.warning("Using fallback interaction capture")
        
        # Handle both InteractionType enum and string values
        interaction_type_str = interaction_type.value if hasattr(interaction_type, 'value') else str(interaction_type)
        
        interaction_record = {
            "timestamp": datetime.now().isoformat(),
            "phone": phone,
            "email": email,
            "name": name,
            "type": interaction_type_str,
            "content": content,
            "saved_locally": True
        }
        
        try:
            import json
            with open('customer_interactions_backup.json', 'a') as f:
                f.write(json.dumps(interaction_record) + '\n')
        except Exception as e:
            logging.error(f"Failed to save to fallback: {e}")
        
        return {
            "success": True,
            "customer_id": f"local_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "message": "Interaction captured locally (CRM unavailable)",
            "saved_locally": True
        }

    # Legacy methods for compatibility
    def save_customer_inquiry(self, inquiry_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Legacy method - now routes to capture_customer_interaction."""
        interaction_type = InteractionType.PHONE_INBOUND
        if inquiry_data.get('contact_method') == 'Email':
            interaction_type = InteractionType.EMAIL_INBOUND
        elif inquiry_data.get('contact_method') == 'SMS':
            interaction_type = InteractionType.SMS_INBOUND
        elif inquiry_data.get('source') == 'Website':
            interaction_type = InteractionType.WEBSITE_FORM
        
        result = self.capture_customer_interaction(
            phone=inquiry_data.get('phone'),
            email=inquiry_data.get('email'),
            name=inquiry_data.get('name'),
            interaction_type=interaction_type,
            message_content=inquiry_data.get('description', ''),
            service_type=inquiry_data.get('service_type', 'General Inquiry'),
            urgency=inquiry_data.get('urgency', 'Normal')
        )
        
        if result['success']:
            return {"id": result.get('inquiry_id') or result.get('customer_id')}
        else:
            return {"error": result.get('error')}

    def _find_existing_customer(self, email: str, phone: str) -> Optional[Dict[str, Any]]:
        """Find existing customer by email or phone."""
        try:
            # Search by email if provided
            if email:
                url = f"{self.base_url}/api/database/rows/table/{self.customers_table_id}/"
                params = {"filter__Email__icontains": email}
                response = requests.get(url, headers=self.headers, params=params)
                response.raise_for_status()
                results = response.json().get('results', [])
                if results:
                    return results[0]
            
            # Search by phone if email not found and phone provided
            if phone:
                url = f"{self.base_url}/api/database/rows/table/{self.customers_table_id}/"
                params = {"filter__Phone__icontains": phone.replace('-', '').replace(' ', '')}
                response = requests.get(url, headers=self.headers, params=params)
                response.raise_for_status()
                results = response.json().get('results', [])
                if results:
                    return results[0]
            
            return None
            
        except requests.exceptions.RequestException as e:
            logging.error(f"Failed to search for existing customer: {e}")
            return None

    def sync_customers(self, customers: List[Customer]) -> None:
        """Sync customers from Akaunting to Baserow CRM."""
        if not self.enabled:
            logging.info("Baserow CRM not enabled - skipping customer sync")
            return
        
        logging.info(f"Syncing {len(customers)} customers to Baserow CRM")
        
        for customer in customers:
            try:
                # Use the new interaction capture method
                self.capture_customer_interaction(
                    phone=customer.phone,
                    email=customer.email,
                    name=customer.name,
                    interaction_type=InteractionType.PHONE_INBOUND,
                    message_content="Customer synced from Akaunting",
                    service_type="Existing Customer Sync"
                )
                
            except Exception as e:
                logging.error(f"Failed to sync customer {customer.name}: {e}")
        
        logging.info("Customer sync to Baserow CRM completed")

# Quick functions for easy interaction capture
def customer_called(phone: str, name: str = None, message: str = "") -> Dict[str, Any]:
    """Quick function when customer calls."""
    crm = CRMAdapter()
    return crm.capture_customer_interaction(
        phone=phone,
        name=name,
        interaction_type=InteractionType.PHONE_INBOUND,
        message_content=message,
        service_type="Phone Inquiry"
    )

def customer_texted(phone: str, message: str, name: str = None) -> Dict[str, Any]:
    """Quick function when customer texts."""
    crm = CRMAdapter()
    return crm.capture_customer_interaction(
        phone=phone,
        name=name,
        interaction_type=InteractionType.SMS_INBOUND,
        message_content=message,
        service_type="SMS Inquiry"
    )

def customer_emailed(email: str, subject: str = "", content: str = "", name: str = None) -> Dict[str, Any]:
    """Quick function when customer emails."""
    crm = CRMAdapter()
    return crm.capture_customer_interaction(
        email=email,
        name=name,
        interaction_type=InteractionType.EMAIL_INBOUND,
        message_content=f"Subject: {subject}\n{content}",
        service_type="Email Inquiry"
    ) 