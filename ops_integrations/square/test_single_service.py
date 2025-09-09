#!/usr/bin/env python3
"""
Test creating a single catalog item to debug the API
"""
import os
import sys

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from square.client import SquareClient
from square.config import SquareConfig

def test_single_service():
    """Test creating a single service"""
    print("🧪 Testing single service creation...")
    
    # Load configuration
    try:
        config = SquareConfig.from_env()
        client = SquareClient(config)
    except Exception as e:
        print(f"❌ Failed to initialize Square client: {e}")
        return
    
    # Test with minimal data first
    test_data = {
        "type": "ITEM",
        "id": "#test_item_123",
        "item_data": {
            "name": "Test Haircut",
            "description": "A test service"
        }
    }
    
    print(f"📝 Test data: {test_data}")
    
    try:
        response = client.post("/v2/catalog/object", data=test_data)
        print(f"✅ Response: {response}")
    except Exception as e:
        print(f"❌ Error: {e}")
        print(f"🔍 Error type: {type(e)}")
        print(f"🔍 Error details: {str(e)}")

if __name__ == "__main__":
    test_single_service() 