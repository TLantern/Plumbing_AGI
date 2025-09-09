#!/usr/bin/env python3
"""
Test batch upsert with variations
"""
import os
import sys

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from square.client import SquareClient
from square.config import SquareConfig

def test_batch_with_variations():
    """Test batch upsert with variations"""
    print("🧪 Testing batch upsert with variations...")
    
    # Load configuration
    try:
        config = SquareConfig.from_env()
        client = SquareClient(config)
    except Exception as e:
        print(f"❌ Failed to initialize Square client: {e}")
        return
    
    # Create item with variation using batch upsert
    print("\n📝 Creating item with variation...")
    batch_data = {
        "idempotency_key": "test_batch_variations_123",
        "batches": [
            {
                "objects": [
                    {
                        "type": "ITEM",
                        "id": "#test_item_with_var",
                        "item_data": {
                            "name": "Test Haircut with Variation",
                            "description": "A test service with variation",
                            "variations": [
                                {
                                    "type": "ITEM_VARIATION",
                                    "id": "#test_var_456",
                                    "item_variation_data": {
                                        "name": "Standard",
                                        "pricing_type": "FIXED_PRICING",
                                        "price_money": {
                                            "amount": 5000,  # $50.00 in cents
                                            "currency": "CAD"
                                        }
                                    }
                                }
                            ]
                        }
                    }
                ]
            }
        ]
    }
    
    try:
        batch_response = client.post("/v2/catalog/batch-upsert", data=batch_data)
        print(f"✅ Batch upsert response: {batch_response}")
        
        if batch_response.get("objects"):
            print(f"🎉 Successfully created {len(batch_response['objects'])} objects!")
            for obj in batch_response["objects"]:
                print(f"  - {obj.get('type')}: {obj.get('id')}")
        else:
            print("⚠️  No objects returned in response")
            
    except Exception as e:
        print(f"❌ Batch upsert failed: {e}")
        print(f"🔍 Error details: {str(e)}")

if __name__ == "__main__":
    test_batch_with_variations() 