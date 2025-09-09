#!/usr/bin/env python3
"""
Test adding appointment segments to a single service
"""
import os
import sys

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from square.client import SquareClient
from square.config import SquareConfig

def test_single_appointment_segment():
    """Test adding appointment segments to one service"""
    print("🧪 Testing single appointment segment addition...")
    
    # Load configuration
    try:
        config = SquareConfig.from_env()
        client = SquareClient(config)
    except Exception as e:
        print(f"❌ Failed to initialize Square client: {e}")
        return
    
    # Get the first service
    response = client.get('/v2/catalog/list')
    items = [obj for obj in response.get('objects', []) if obj.get('type') == 'ITEM']
    
    if not items:
        print("❌ No items found")
        return
    
    test_service = items[0]
    service_name = test_service.get('item_data', {}).get('name', 'Unknown')
    service_id = test_service.get('id')
    
    print(f"📝 Testing with service: {service_name} (ID: {service_id})")
    
    # Check current structure
    item_data = test_service.get('item_data', {})
    variations = item_data.get('variations', [])
    
    print(f"  Current variations: {len(variations)}")
    print(f"  Has appointment_segments: {'appointment_segments' in item_data}")
    
    if not variations:
        print("❌ Service has no variations")
        return
    
    variation_id = variations[0].get('id')
    print(f"  First variation ID: {variation_id}")
    
    # Try to add appointment segments using a simple update
    try:
        # Method 1: Try direct update
        update_data = {
            "type": "ITEM",
            "id": service_id,
            "item_data": {
                "appointment_segments": [
                    {
                        "duration_minutes": 60,
                        "service_variation_id": variation_id
                    }
                ]
            }
        }
        
        print(f"  🔄 Attempting to add appointment segments...")
        response = client.post("/v2/catalog/object", data=update_data)
        
        if response and response.get('object'):
            print(f"  ✅ Successfully added appointment segments!")
            updated_item = response['object']
            updated_item_data = updated_item.get('item_data', {})
            print(f"  📊 Updated item data keys: {list(updated_item_data.keys())}")
            print(f"  📅 Appointment segments: {updated_item_data.get('appointment_segments', [])}")
        else:
            print(f"  ❌ Failed to add appointment segments")
            print(f"  📊 Response: {response}")
            
    except Exception as e:
        print(f"  ❌ Error: {e}")
        print(f"  🔍 Error type: {type(e)}")

if __name__ == "__main__":
    test_single_appointment_segment() 