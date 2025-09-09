#!/usr/bin/env python3
"""
Add appointment segments to existing services to make them bookable
"""
import os
import sys
from typing import Dict, Any, List

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from square.client import SquareClient
from square.config import SquareConfig

def get_services_without_appointment_segments(client: SquareClient) -> List[Dict[str, Any]]:
    """Get all services that don't have appointment segments"""
    try:
        response = client.get('/v2/catalog/list')
        objects = response.get('objects', [])
        
        services_needing_segments = []
        for obj in objects:
            if obj.get('type') == 'ITEM':
                item_data = obj.get('item_data', {})
                if 'appointment_segments' not in item_data:
                    services_needing_segments.append(obj)
        
        return services_needing_segments
        
    except Exception as e:
        print(f"❌ Error getting services: {e}")
        return []

def add_appointment_segments_to_service(client: SquareClient, service: Dict[str, Any], duration_minutes: int = 60) -> bool:
    """
    Add appointment segments to a service by creating a new version
    
    Args:
        client: Square API client
        service: Service object from catalog
        duration_minutes: Duration of the appointment in minutes
        
    Returns:
        True if successful, False otherwise
    """
    try:
        service_id = service.get('id')
        item_data = service.get('item_data', {})
        variations = item_data.get('variations', [])
        
        if not variations:
            print(f"  ⚠️  Service {service_id} has no variations, skipping")
            return False
        
        # Create new item ID
        new_item_id = f"#new_{service_id}_{hash(service_id) % 1000000}"
        
        # Create new variation IDs to avoid conflicts
        new_variations = []
        for i, variation in enumerate(variations):
            variation_data = variation.get('item_variation_data', {}).copy()
            # Update the item_id reference to the new item ID
            variation_data['item_id'] = new_item_id
            
            new_variation = {
                "type": "ITEM_VARIATION",
                "id": f"#new_var_{hash(variation.get('id', '')) % 1000000}",
                "item_variation_data": variation_data
            }
            new_variations.append(new_variation)
        
        # Get the first new variation ID for appointment segments
        new_variation_id = new_variations[0].get('id')
        
        # Create appointment segment data
        appointment_segment = {
            "duration_minutes": duration_minutes,
            "service_variation_id": new_variation_id
        }
        
        # Create a new version of the service with appointment segments
        new_service_data = {
            "type": "ITEM",
            "id": new_item_id,
            "item_data": {
                "name": item_data.get('name'),
                "description": item_data.get('description'),
                "category_id": item_data.get('category_id'),
                "variations": new_variations,
                "appointment_segments": [appointment_segment]
            }
        }
        
        # Use batch upsert to create the new service
        batch_data = {
            "idempotency_key": f"new_appointment_segments_{service_id}_{hash(service_id) % 1000000}",
            "batches": [
                {
                    "objects": [new_service_data]
                }
            ]
        }
        
        response = client.post("/v2/catalog/batch-upsert", data=batch_data)
        
        if response and response.get('objects'):
            print(f"  ✅ Created new version with appointment segments for {item_data.get('name', 'Unknown')}")
            return True
        else:
            print(f"  ❌ Failed to create new version for {item_data.get('name', 'Unknown')}")
            return False
            
    except Exception as e:
        print(f"  ❌ Error adding appointment segments: {e}")
        return False

def add_appointment_segments_to_all_services():
    """Add appointment segments to all services that need them"""
    print("🚀 Adding appointment segments to make services bookable...")
    
    # Load configuration
    try:
        config = SquareConfig.from_env()
        client = SquareClient(config)
    except Exception as e:
        print(f"❌ Failed to initialize Square client: {e}")
        return
    
    # Get services that need appointment segments
    services_needing_segments = get_services_without_appointment_segments(client)
    
    if not services_needing_segments:
        print("✅ All services already have appointment segments!")
        return
    
    print(f"📋 Found {len(services_needing_segments)} services needing appointment segments")
    
    # Add appointment segments to each service
    successful_updates = 0
    failed_updates = 0
    
    for service in services_needing_segments:
        service_name = service.get('item_data', {}).get('name', 'Unknown')
        print(f"\n📝 Processing: {service_name}")
        
        # Determine duration based on service type (you can customize this)
        duration = determine_service_duration(service_name)
        
        if add_appointment_segments_to_service(client, service, duration):
            successful_updates += 1
        else:
            failed_updates += 1
    
    # Summary
    print(f"\n{'='*50}")
    print("📊 APPOINTMENT SEGMENTS SUMMARY")
    print(f"{'='*50}")
    print(f"✅ Successfully updated: {successful_updates} services")
    print(f"❌ Failed to update: {failed_updates} services")
    
    if successful_updates > 0:
        print(f"\n🎉 {successful_updates} services are now bookable!")
        print("💡 Next steps:")
        print("  1. Check your Square Dashboard to see bookable services")
        print("  2. Test the booking functionality")
        print("  3. Verify services appear in the Square Bookings interface")

def determine_service_duration(service_name: str) -> int:
    """
    Determine the duration for a service based on its name
    You can customize this logic based on your business needs
    """
    service_name_lower = service_name.lower()
    
    # Quick services (30 minutes)
    if any(word in service_name_lower for word in ['beading', 'take down', 'wash']):
        return 30
    
    # Standard services (60 minutes)
    if any(word in service_name_lower for word in ['weave', 'braid', 'twist', 'crochet', 'boho']):
        return 60
    
    # Complex services (90 minutes)
    if any(word in service_name_lower for word in ['loc', 'micro', 'sister']):
        return 90
    
    # Very complex services (120 minutes)
    if any(word in service_name_lower for word in ['starter', 'full']):
        return 120
    
    # Default duration
    return 60

if __name__ == "__main__":
    add_appointment_segments_to_all_services() 