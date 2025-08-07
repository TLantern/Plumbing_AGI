#!/usr/bin/env python3
"""
Test script for webhook server
"""
import requests
import json
import time

def test_webhook_server():
    """Test the webhook server endpoints."""
    base_url = "http://localhost:5001"
    
    print("🧪 Testing Webhook Server...")
    
    # Test health endpoint
    try:
        response = requests.get(f"{base_url}/health", timeout=5)
        print(f"✅ Health check: {response.status_code}")
        print(f"📊 Response: {response.json()}")
    except requests.exceptions.RequestException as e:
        print(f"❌ Health check failed: {e}")
        return False
    
    # Test webhook endpoint with mock data
    try:
        mock_data = {
            'From': '+19404656984',
            'To': '+18084826296',
            'Body': 'my pipe just burst and there is water everywhere!'
        }
        
        response = requests.post(f"{base_url}/webhook/sms", data=mock_data, timeout=10)
        print(f"✅ Webhook test: {response.status_code}")
        print(f"📊 Response: {response.json()}")
        
    except requests.exceptions.RequestException as e:
        print(f"❌ Webhook test failed: {e}")
        return False
    
    return True

if __name__ == "__main__":
    print("🚀 Starting webhook server test...")
    time.sleep(2)  # Give server time to start
    
    if test_webhook_server():
        print("✅ Webhook server test completed successfully!")
    else:
        print("❌ Webhook server test failed!") 