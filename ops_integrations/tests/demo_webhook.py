#!/usr/bin/env python3
"""
Demo script for Twilio webhook functionality.
Tests intent recognition and webhook endpoints.
"""

import requests
import json
import sys
import os

# Add the ops_integrations directory to the path
sys.path.append(os.path.join(os.path.dirname(__file__), 'ops_integrations'))

def test_intent_recognition():
    """Test intent recognition with sample texts."""
    print("🧪 TESTING INTENT RECOGNITION")
    print("=" * 50)
    
    # Import the intent recognition function
    try:
        from adapters.plumbing_services import infer_multiple_job_types_from_text
    except ImportError as e:
        print(f"❌ Error importing plumbing services: {e}")
        return
    
    test_cases = [
        "My kitchen sink is clogged and water is backing up",
        "The water heater is making strange noises and not heating properly",
        "I need a new faucet installed in my bathroom",
        "There's a leak under the kitchen sink",
        "The toilet is running constantly",
        "My dishwasher won't drain properly",
        "The garbage disposal is jammed",
        "I need a plumber to fix my shower valve"
    ]
    
    for i, text in enumerate(test_cases, 1):
        print(f"\n{i}. Testing: {text}")
        
        try:
            results = infer_multiple_job_types_from_text(text)
            primary = results.get('primary', 'None')
            secondary = results.get('secondary', [])
            description = results.get('description_suffix', '')
            
            print(f"   ✅ Primary: {primary}")
            print(f"   📋 Secondary: {secondary}")
            if description:
                print(f"   ℹ️ {description}")
                
        except Exception as e:
            print(f"   ❌ Error: {e}")

def test_flask_endpoints():
    """Test Flask endpoints if server is running."""
    print("\n🌐 TESTING FLASK ENDPOINTS")
    print("=" * 50)
    
    base_url = "http://localhost:5000"
    
    # Test health endpoint
    try:
        response = requests.get(f"{base_url}/health", timeout=5)
        if response.status_code == 200:
            print("✅ Health endpoint working")
            data = response.json()
            print(f"   Status: {data.get('status')}")
            print(f"   Twilio configured: {data.get('twilio_configured')}")
        else:
            print(f"❌ Health endpoint failed: {response.status_code}")
    except requests.exceptions.ConnectionError:
        print("❌ Flask server not running. Start it with: python3 twilio_webhook.py")
        return False
    except Exception as e:
        print(f"❌ Error testing health endpoint: {e}")
        return False
    
    # Test intent endpoint
    test_data = {
        "text": "My kitchen sink is clogged and water is backing up"
    }
    
    try:
        response = requests.post(f"{base_url}/test-intent", json=test_data, timeout=5)
        if response.status_code == 200:
            print("✅ Intent endpoint working")
            result = response.json()
            primary = result['intent_results'].get('primary', 'None')
            print(f"   Primary Intent: {primary}")
        else:
            print(f"❌ Intent endpoint failed: {response.status_code}")
    except requests.exceptions.ConnectionError:
        print("❌ Flask server not running")
        return False
    except Exception as e:
        print(f"❌ Error testing intent endpoint: {e}")
        return False
    
    return True

def test_webhook_simulation():
    """Simulate a webhook call."""
    print("\n📞 TESTING WEBHOOK SIMULATION")
    print("=" * 50)
    
    url = "http://localhost:5000/webhook"
    
    # Simulate Twilio webhook data
    webhook_data = {
        'CallSid': 'demo_call_123',
        'From': '+1234567890',
        'To': '+0987654321',
        'CallStatus': 'ringing'
    }
    
    try:
        response = requests.post(url, data=webhook_data, timeout=5)
        print(f"✅ Webhook response status: {response.status_code}")
        print(f"📝 Response content (first 200 chars): {response.text[:200]}...")
        
        # Check if it's valid TwiML
        if '<?xml' in response.text and 'Response' in response.text:
            print("✅ Valid TwiML response received")
        else:
            print("⚠️ Response may not be valid TwiML")
            
    except requests.exceptions.ConnectionError:
        print("❌ Flask server not running")
    except Exception as e:
        print(f"❌ Error: {e}")

def show_usage_instructions():
    """Show usage instructions."""
    print("\n📋 USAGE INSTRUCTIONS")
    print("=" * 50)
    print("1. Start the Flask server:")
    print("   python3 twilio_webhook.py")
    print()
    print("2. Set up ngrok for public access:")
    print("   ngrok http 5000")
    print()
    print("3. Configure Twilio webhook URL:")
    print("   - Go to Twilio Console > Phone Numbers")
    print("   - Set webhook URL to: https://your-ngrok-url.ngrok.io/webhook")
    print()
    print("4. Call your Twilio number and describe a plumbing issue")
    print("5. Receive SMS with intent analysis results")
    print()

def main():
    """Main demo function."""
    print("🚀 TWILIO WEBHOOK DEMO")
    print("=" * 60)
    
    # Test intent recognition
    test_intent_recognition()
    
    # Test Flask endpoints
    flask_running = test_flask_endpoints()
    
    # Test webhook simulation if Flask is running
    if flask_running:
        test_webhook_simulation()
    
    # Show usage instructions
    show_usage_instructions()
    
    print("✅ Demo complete!")

if __name__ == "__main__":
    main() 