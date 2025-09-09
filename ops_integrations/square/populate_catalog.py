#!/usr/bin/env python3
"""
Populate Square catalog with services from boldwings.json
"""
import json
import os
import sys
from typing import Dict, Any, List

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from square.client import SquareClient
from square.config import SquareConfig

def load_boldwings_services() -> Dict[str, List[Dict[str, Any]]]:
    """Load services from boldwings.json"""
    try:
        file_path = 'config/boldwings.json'
        print(f"🔍 Trying to load: {os.path.abspath(file_path)}")
        print(f"🔍 Current working directory: {os.getcwd()}")
        
        with open(file_path, 'r') as f:
            data = json.load(f)
            return data.get('services', {})
    except FileNotFoundError:
        print(f"❌ boldwings.json not found at: {os.path.abspath(file_path)}")
        return {}
    except json.JSONDecodeError as e:
        print(f"❌ Error parsing boldwings.json: {e}")
        return {}

def create_service_batch(services: List[Dict[str, Any]], category: str, batch_size: int = 10) -> List[Dict[str, Any]]:
    """Create a batch of services for batch upsert"""
    batch_objects = []
    
    for i, service in enumerate(services):
        service_name = service['name']
        price = service['price']
        price_cents = int(price * 100)
        
        # Create item with variation
        item_object = {
            "type": "ITEM",
            "id": f"#item_{category}_{i}_{hash(service_name) % 1000000}",
            "item_data": {
                "name": service_name,
                "description": f"{service_name} - {category} service",
                "variations": [
                    {
                        "type": "ITEM_VARIATION",
                        "id": f"#var_{category}_{i}_{hash(service_name) % 1000000}",
                        "item_variation_data": {
                            "name": "Standard",
                            "pricing_type": "FIXED_PRICING",
                            "price_money": {
                                "amount": price_cents,
                                "currency": "CAD"
                            }
                        }
                    }
                ]
            }
        }
        
        batch_objects.append(item_object)
    
    return batch_objects

def populate_catalog():
    """Main function to populate the Square catalog"""
    print("🚀 Starting Square Catalog Population...")
    
    # Load configuration
    try:
        config = SquareConfig.from_env()
        client = SquareClient(config)
    except Exception as e:
        print(f"❌ Failed to initialize Square client: {e}")
        print("💡 Make sure your .env file has the correct Square credentials")
        return
    
    # Load services from boldwings.json
    services = load_boldwings_services()
    if not services:
        print("❌ No services found to populate")
        return
    
    print(f"📋 Found {len(services)} service categories to populate")
    
    # Create catalog items for each service category
    created_items = []
    failed_items = []
    
    for category, service_list in services.items():
        print(f"\n📁 Processing category: {category} ({len(service_list)} services)")
        
        try:
            # Create batch of services for this category
            batch_objects = create_service_batch(service_list, category)
            
            # Use batch upsert to create all services in this category
            batch_data = {
                "idempotency_key": f"boldwings_{category}_{hash(category) % 1000000}",
                "batches": [
                    {
                        "objects": batch_objects
                    }
                ]
            }
            
            # Execute batch upsert
            batch_response = client.post("/v2/catalog/batch-upsert", data=batch_data)
            
            if batch_response and batch_response.get("objects"):
                print(f"  ✅ Successfully created {len(batch_response['objects'])} services in {category}")
                
                # Track created services
                for obj in batch_response["objects"]:
                    if obj.get("type") == "ITEM":
                        item_data = obj.get("item_data", {})
                        created_items.append({
                            'name': item_data.get('name', 'Unknown'),
                            'category': category,
                            'id': obj.get('id', 'Unknown')
                        })
            else:
                print(f"  ❌ Failed to create services in {category}")
                failed_items.extend([{
                    'name': service['name'],
                    'category': category,
                    'error': 'Batch upsert returned no objects'
                } for service in service_list])
                
        except Exception as e:
            print(f"  ❌ Failed to create services in {category}: {e}")
            failed_items.extend([{
                'name': service['name'],
                'category': category,
                'error': str(e)
            } for service in service_list])
    
    # Summary
    print(f"\n{'='*50}")
    print("📊 POPULATION SUMMARY")
    print(f"{'='*50}")
    print(f"✅ Successfully created: {len(created_items)} services")
    print(f"❌ Failed to create: {len(failed_items)} services")
    
    if created_items:
        print(f"\n🎉 Successfully created services:")
        for item in created_items[:10]:  # Show first 10
            print(f"  - {item['name']} - {item['category']} [ID: {item['id']}]")
        if len(created_items) > 10:
            print(f"  ... and {len(created_items) - 10} more")
    
    if failed_items:
        print(f"\n⚠️  Failed to create services:")
        for item in failed_items[:5]:  # Show first 5 failures
            print(f"  - {item['name']}: {item['error']}")
        if len(failed_items) > 5:
            print(f"  ... and {len(failed_items) - 5} more failures")
    
    print(f"\n💡 Next steps:")
    print(f"  1. Check your Square Dashboard to see the created services")
    print(f"  2. Enable bookings for your location if not already done")
    print(f"  3. Test the booking functionality with: python3 -c \"from square.salon_booking_integration import SalonBookingManager; manager = SalonBookingManager(); print('Services:', len(manager.get_available_services()))\"")

if __name__ == "__main__":
    populate_catalog() 