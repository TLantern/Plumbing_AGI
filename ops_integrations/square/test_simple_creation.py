#!/usr/bin/env python3
"""
Test different Square API creation methods
"""
import os
import sys

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from square.client import SquareClient
from square.config import SquareConfig

def test_different_methods():
    """Test different Square API creation methods"""
    print("🧪 Testing different Square API creation methods...")
    
    # Load configuration
    try:
        config = SquareConfig.from_env()
        client = SquareClient(config)
    except Exception as e:
        print(f"❌ Failed to initialize Square client: {e}")
        return
    
    # Method 1: Try with upsert endpoint
    print("\n📝 Method 1: Using upsert endpoint...")
    upsert_data = {
        "idempotency_key": "test_key_123",
        "object": {
            "type": "ITEM",
            "id": "#test_item_upsert",
            "item_data": {
                "name": "Test Haircut Upsert",
                "description": "A test service using upsert"
            }
        }
    }
    
    try:
        upsert_response = client.post("/v2/catalog/upsert", data=upsert_data)
        print(f"✅ Upsert response: {upsert_response}")
    except Exception as e:
        print(f"❌ Upsert failed: {e}")
    
    # Method 2: Try with batch upsert
    print("\n📝 Method 2: Using batch upsert...")
    batch_data = {
        "idempotency_key": "test_batch_123",
        "batches": [
            {
                "objects": [
                    {
                        "type": "ITEM",
                        "id": "#test_item_batch",
                        "item_data": {
                            "name": "Test Haircut Batch",
                            "description": "A test service using batch"
                        }
                    }
                ]
            }
        ]
    }
    
    try:
        batch_response = client.post("/v2/catalog/batch-upsert", data=batch_data)
        print(f"✅ Batch upsert response: {batch_response}")
    except Exception as e:
        print(f"❌ Batch upsert failed: {e}")
    
    # Method 3: Check if we need to create a variation first
    print("\n📝 Method 3: Creating item variation first...")
    variation_data = {
        "type": "ITEM_VARIATION",
        "id": "#test_var_123",
        "item_variation_data": {
            "name": "Standard",
            "pricing_type": "FIXED_PRICING",
            "price_money": {
                "amount": 5000,  # $50.00 in cents
                "currency": "CAD"
            }
        }
    }
    
    try:
        var_response = client.post("/v2/catalog/object", data=variation_data)
        print(f"✅ Variation created: {var_response}")
    except Exception as e:
        print(f"❌ Variation creation failed: {e}")

if __name__ == "__main__":
    test_different_methods() 