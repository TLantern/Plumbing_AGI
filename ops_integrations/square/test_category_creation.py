#!/usr/bin/env python3
"""
Test creating a category first, then an item
"""
import os
import sys

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from square.client import SquareClient
from square.config import SquareConfig

def test_category_and_item():
    """Test creating a category first, then an item"""
    print("🧪 Testing category and item creation...")
    
    # Load configuration
    try:
        config = SquareConfig.from_env()
        client = SquareClient(config)
    except Exception as e:
        print(f"❌ Failed to initialize Square client: {e}")
        return
    
    # Step 1: Create a category
    print("\n📁 Step 1: Creating category...")
    category_data = {
        "type": "CATEGORY",
        "id": "#test_category_123",
        "category_data": {
            "name": "Test Hair Services"
        }
    }
    
    try:
        category_response = client.post("/v2/catalog/object", data=category_data)
        print(f"✅ Category created: {category_response}")
        category_id = category_response.get("object", {}).get("id")
    except Exception as e:
        print(f"❌ Category creation failed: {e}")
        return
    
    # Step 2: Create an item with the category
    print(f"\n📝 Step 2: Creating item with category {category_id}...")
    item_data = {
        "type": "ITEM",
        "id": "#test_item_123",
        "item_data": {
            "name": "Test Haircut",
            "description": "A test service",
            "category_id": category_id
        }
    }
    
    try:
        item_response = client.post("/v2/catalog/object", data=item_data)
        print(f"✅ Item created: {item_response}")
    except Exception as e:
        print(f"❌ Item creation failed: {e}")
        print(f"🔍 Error details: {str(e)}")

if __name__ == "__main__":
    test_category_and_item() 