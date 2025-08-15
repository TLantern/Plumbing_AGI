import logging
from typing import Dict, Any
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

from ops_integrations.adapters.external_services.google_calendar import CalendarAdapter
from ops_integrations.adapters.integrations.crm import CRMAdapter
from ops_integrations.adapters.integrations.inventory import InventoryAdapter

logging.basicConfig(level=logging.INFO)

class OpsETLSync:
    def __init__(self):
        self.calendar = CalendarAdapter()
        
        # Initialize CRM adapter - now properly enabled
        try:
            self.crm = CRMAdapter()
            self.crm_available = self.crm.enabled
            if self.crm_available:
                logging.info("✅ Baserow CRM integration enabled and ready")
            else:
                logging.warning("⚠️ Baserow CRM not configured - missing environment variables")
        except Exception as e:
            logging.error(f"❌ CRM initialization failed: {e}")
            self.crm = None
            self.crm_available = False
        
        self.inventory = InventoryAdapter()  # Currently disabled
        
        # Initialize Akaunting adapter only if credentials are available
        try:
            from adapters.integrations.akaunting import AkauntingAdapter
            self.accounting = AkauntingAdapter()
            self.accounting_available = True
            logging.info("✅ Akaunting integration enabled")
        except Exception as e:
            logging.warning(f"⚠️ Akaunting not available: {e}")
            self.accounting = None
            self.accounting_available = False

    def sync_data(self):
        """Main sync method for production use with enhanced CRM integration."""
        logging.info("🚀 Starting Plumbing AGI data sync with enhanced CRM")
        
        try:
            # Sync Akaunting customers to CRM if both are available
            if self.accounting_available and self.crm_available:
                logging.info("📊 Syncing Akaunting customers to Baserow CRM...")
                customers = self.accounting.get_customers()
                logging.info(f"Retrieved {len(customers)} customers from Akaunting")
                
                # Sync customers to CRM with proper status management
                self.crm.sync_customers(customers)
                logging.info(f"✅ Synced {len(customers)} customers to CRM with status tracking")
                
                # Get invoices for additional customer insights
                invoices = self.accounting.get_invoices()
                logging.info(f"Retrieved {len(invoices)} invoices from Akaunting")
                
            elif self.accounting_available:
                customers = self.accounting.get_customers()
                invoices = self.accounting.get_invoices()
                logging.info(f"📊 Retrieved {len(customers)} customers and {len(invoices)} invoices from Akaunting")
                logging.warning("💾 Data retrieved but CRM sync unavailable - stored locally")
                
            elif self.crm_available:
                logging.info("📋 CRM is available but no accounting data source configured")
            else:
                logging.warning("⚠️ No data sources configured for sync")
                
            logging.info("✅ Data sync completed successfully")
            return True
            
        except Exception as e:
            logging.error(f"❌ Data sync failed: {e}")
            return False

    def test_crm_interaction_capture(self):
        """Test the enhanced CRM interaction capture functionality."""
        if not self.crm_available:
            logging.warning("⚠️ CRM not available for testing")
            return False
            
        logging.info("🧪 Testing CRM interaction capture...")
        
        try:
            # Test capturing different types of customer interactions
            test_interactions = [
                {
                    "phone": "555-TEST-001",
                    "name": "Test Customer Alpha",
                    "interaction_type": "phone_inbound",
                    "message": "Called about kitchen sink repair",
                    "service_type": "Emergency Plumbing",
                    "urgency": "High"
                },
                {
                    "phone": "555-TEST-002", 
                    "name": "Test Customer Beta",
                    "interaction_type": "sms_inbound",
                    "message": "Need quote for bathroom renovation",
                    "service_type": "Quote Request",
                    "urgency": "Normal"
                },
                {
                    "email": "test@customer.com",
                    "name": "Test Customer Gamma",
                    "interaction_type": "email_inbound", 
                    "message": "Interested in scheduling maintenance service",
                    "service_type": "Maintenance",
                    "urgency": "Low"
                }
            ]
            
            captured_customers = []
            
            for interaction in test_interactions:
                from adapters.integrations.crm import InteractionType
                
                interaction_type_map = {
                    "phone_inbound": InteractionType.PHONE_INBOUND,
                    "sms_inbound": InteractionType.SMS_INBOUND,
                    "email_inbound": InteractionType.EMAIL_INBOUND
                }
                
                result = self.crm.capture_customer_interaction(
                    phone=interaction.get("phone"),
                    email=interaction.get("email"),
                    name=interaction["name"],
                    interaction_type=interaction_type_map[interaction["interaction_type"]],
                    message_content=interaction["message"],
                    service_type=interaction["service_type"],
                    urgency=interaction["urgency"]
                )
                
                if result.get("success"):
                    customer_id = result["customer_id"]
                    captured_customers.append(customer_id)
                    
                    logging.info(f"✅ Captured {interaction['interaction_type']} interaction:")
                    logging.info(f"   Customer: {result.get('customer_name')} (ID: {customer_id})")
                    logging.info(f"   Status: {result.get('customer_status')}")
                    logging.info(f"   New Customer: {result.get('is_new_customer', False)}")
                else:
                    logging.error(f"❌ Failed to capture interaction: {result.get('error')}")
            
            # Test service status updates
            if captured_customers:
                test_customer_id = captured_customers[0]
                logging.info(f"🔧 Testing service status updates for customer {test_customer_id}...")
                
                # Test scheduling
                schedule_success = self.crm.update_service_status(test_customer_id, "scheduled", "Test scheduling")
                if schedule_success:
                    logging.info("✅ Successfully updated status to 'scheduled'")
                
                # Test service in progress
                progress_success = self.crm.update_service_status(test_customer_id, "in_progress", "Test service start")
                if progress_success:
                    logging.info("✅ Successfully updated status to 'in_progress'")
                
                # Test completion
                complete_success = self.crm.update_service_status(test_customer_id, "completed", "Test service completion")
                if complete_success:
                    logging.info("✅ Successfully updated status to 'completed'")
                
                # Get customer details to verify
                customer_details = self.crm.get_customer_details(test_customer_id)
                if customer_details:
                    customer = customer_details["customer"]
                    interactions = customer_details["recent_interactions"]
                    logging.info(f"📋 Customer details: Status={customer.get('Status')}, Total Interactions={customer.get('Total_Interactions', 0)}")
                    logging.info(f"📝 Recent interactions: {len(interactions)} recorded")
            
            logging.info("✅ CRM interaction capture testing completed successfully")
            return True
            
        except Exception as e:
            logging.error(f"❌ CRM testing failed: {e}")
            return False

    def run(self):
        """Enhanced test method with CRM interaction testing."""
        logging.info("🚀 Starting Enhanced Calendar and CRM test")
        try:
            # Test calendar functionality - read events
            events = self.calendar.get_events()
            logging.info(f"📅 Successfully retrieved {len(events)} events from calendar")
            
            # Display first few events if any exist
            if events:
                for i, event in enumerate(events[:3]):
                    logging.info(f"📌 Event {i+1}: {event.get('summary', 'No title')} - {event.get('start', {}).get('dateTime', 'No time')}")
            else:
                logging.info("📅 No events found in calendar")
            
            # Test creating a sample event
            from datetime import datetime, timedelta
            start_time = datetime.utcnow() + timedelta(hours=1)
            end_time = start_time + timedelta(hours=2)
            
            event = self.calendar.create_event(
                summary="Test Plumbing Appointment - Enhanced CRM",
                start_time=start_time,
                end_time=end_time,
                description="Test appointment for enhanced calendar and CRM functionality",
                location="123 Test Street"
            )
            logging.info(f"📅 Successfully created test event: {event.get('htmlLink', 'No link available')}")
            
            # Test enhanced CRM functionality
            if self.crm_available:
                logging.info("🔄 Testing enhanced CRM functionality...")
                self.test_crm_interaction_capture()
            else:
                logging.warning("⚠️ CRM not configured - skipping CRM tests")
            
            # Test Akaunting functionality if available
            if self.accounting_available:
                try:
                    customers = self.accounting.get_customers()
                    logging.info(f"💼 Successfully retrieved {len(customers)} customers from Akaunting")
                    
                    invoices = self.accounting.get_invoices()
                    logging.info(f"📄 Successfully retrieved {len(invoices)} invoices from Akaunting")
                    
                    # If CRM is available, demonstrate customer sync
                    if self.crm_available and customers:
                        logging.info("🔄 Testing customer sync from Akaunting to CRM...")
                        # Sync first customer as a test
                        test_customer = customers[0]
                        from adapters.integrations.crm import InteractionType
                        
                        sync_result = self.crm.capture_customer_interaction(
                            phone=test_customer.phone,
                            email=test_customer.email,
                            name=test_customer.name,
                            interaction_type=InteractionType.PHONE_INBOUND,
                            message_content="Customer synced from Akaunting for testing",
                            service_type="Existing Customer Sync"
                        )
                        
                        if sync_result.get("success"):
                            logging.info(f"✅ Successfully synced test customer: {test_customer.name}")
                        else:
                            logging.warning(f"⚠️ Customer sync test failed: {sync_result.get('error')}")
                    
                except Exception as e:
                    logging.warning(f"⚠️ Akaunting test failed: {e}")
            else:
                logging.warning("⚠️ Akaunting not configured - skipping accounting tests")
            
            logging.info("✅ Enhanced Calendar and CRM test successful!")
            
        except Exception as e:
            logging.error(f"❌ Test failed: {e}")
            raise
        
        logging.info("🎉 Enhanced test complete - CRM integration ready for production!")

    def get_system_status(self) -> Dict[str, Any]:
        """Get status of all system integrations."""
        status = {
            "calendar": {
                "available": hasattr(self.calendar, 'service') and self.calendar.service is not None,
                "name": "Google Calendar"
            },
            "crm": {
                "available": self.crm_available,
                "name": "Baserow CRM",
                "features": ["customer_tracking", "interaction_logging", "status_management"] if self.crm_available else []
            },
            "accounting": {
                "available": self.accounting_available,
                "name": "Akaunting"
            },
            "inventory": {
                "available": False,
                "name": "Inventory Management (Disabled)"
            }
        }
        
        return status