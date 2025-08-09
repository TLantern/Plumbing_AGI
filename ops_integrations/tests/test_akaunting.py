#!/usr/bin/env python3
"""
Test script for Akaunting API connection
"""

import os
import requests
import sys

def test_akaunting_connection():
    """Test Akaunting API connection"""
    
    # Get environment variables
    base_url = os.getenv('AKAUNTING_BASE_URL')
    api_token = os.getenv('AKAUNTING_API_TOKEN')
    company_id = os.getenv('AKAUNTING_COMPANY_ID')
    
    if not all([base_url, api_token, company_id]):
        print("❌ Missing required environment variables:")
        print(f"   AKAUNTING_BASE_URL: {base_url}")
        print(f"   AKAUNTING_API_TOKEN: {api_token}")
        print(f"   AKAUNTING_COMPANY_ID: {company_id}")
        return False
    
    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {api_token}"
    }
    
    print(f"🔍 Testing Akaunting connection to: {base_url}")
    print(f"🔑 Using API token: {api_token[:8]}...")
    print(f"🏢 Company ID: {company_id}")
    print()
    
    # Test the companies endpoint
    url = f"{base_url}/api/companies"
    print(f"📡 Testing: {url}")
    try:
        response = requests.get(url, headers=headers, timeout=10)
        print(f"   ✅ Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"   📊 Response: {len(str(data))} characters")
            if 'data' in data:
                print(f"   📋 Data items: {len(data['data'])}")
        else:
            print(f"   ❌ Error: {response.text[:100]}...")
    except requests.exceptions.ConnectionError as e:
        print(f"   ❌ Connection Error: {e}")
        print(f"   💡 This means the subdomain doesn't exist yet")
    except requests.exceptions.Timeout as e:
        print(f"   ⏰ Timeout Error: {e}")
    except Exception as e:
        print(f"   ❌ Error: {e}")
    
    return True

def check_akaunting_setup():
    """Check if Akaunting instance exists and provide setup instructions"""
    print("🔍 Checking Akaunting setup...")
    print()
    
    # Test common Akaunting domains
    test_domains = [
        "https://akaunting.com",
        "https://safeharbour.akaunting.com",
        "https://safeharbour.akaunting.cloud"
    ]
    
    for domain in test_domains:
        print(f"📡 Testing: {domain}")
        try:
            response = requests.get(domain, timeout=5)
            print(f"   ✅ Status: {response.status_code}")
        except requests.exceptions.ConnectionError:
            print(f"   ❌ Connection Error")
        except Exception as e:
            print(f"   ❌ Error: {e}")
    
    print()
    print("🚀 To set up your Akaunting instance:")
    print("   1. Go to https://akaunting.com")
    print("   2. Click 'Get Started' or 'Sign Up'")
    print("   3. Choose Akaunting Cloud")
    print("   4. Use 'safeharbour' as your company name")
    print("   5. Follow the setup wizard")
    print("   6. Get your instance URL from the dashboard")
    print("   7. Generate API token in Admin > Settings > API")
    print()

if __name__ == "__main__":
    print("🚀 Akaunting API Connection Test")
    print("=" * 40)
    
    # First check if Akaunting is set up
    check_akaunting_setup()
    
    test_akaunting_connection()
    
    print()
    print("✅ Test completed!") 