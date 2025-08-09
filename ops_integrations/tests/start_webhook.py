#!/usr/bin/env python3
"""
Simple script to start the Twilio webhook server and test it.
"""

import subprocess
import time
import requests
import sys
import os

def start_server():
    """Start the Flask server."""
    print("🚀 Starting Twilio webhook server...")
    
    try:
        # Start the server in the background
        process = subprocess.Popen([
            sys.executable, 'ops_integrations/adapters/twilio_webhook.py'
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        # Wait for server to start
        print("⏳ Waiting for server to start...")
        time.sleep(3)
        
        return process
        
    except Exception as e:
        print(f"❌ Error starting server: {e}")
        return None

def test_server():
    """Test if the server is running."""
    print("🧪 Testing server endpoints...")
    
    try:
        # Test health endpoint
        response = requests.get('http://localhost:5001/health', timeout=5)
        if response.status_code == 200:
            print("✅ Health endpoint working")
            data = response.json()
            print(f"   Status: {data.get('status')}")
            print(f"   Twilio configured: {data.get('twilio_configured')}")
        else:
            print(f"❌ Health endpoint failed: {response.status_code}")
            return False
            
        # Test intent endpoint
        test_data = {"text": "My kitchen sink is clogged"}
        response = requests.post('http://localhost:5001/test-intent', 
                               json=test_data, timeout=5)
        if response.status_code == 200:
            print("✅ Intent endpoint working")
            result = response.json()
            primary = result['intent_results'].get('primary', 'None')
            print(f"   Primary Intent: {primary}")
        else:
            print(f"❌ Intent endpoint failed: {response.status_code}")
            return False
            
        return True
        
    except requests.exceptions.ConnectionError:
        print("❌ Server not responding")
        return False
    except Exception as e:
        print(f"❌ Error testing server: {e}")
        return False

def show_next_steps():
    """Show next steps for setup."""
    print("\n📋 NEXT STEPS FOR TWILIO SETUP")
    print("=" * 50)
    print("1. Install ngrok (if not already installed):")
    print("   brew install ngrok")
    print()
    print("2. Start ngrok tunnel:")
    print("   ngrok http 5001")
    print()
    print("3. Copy the HTTPS URL (e.g., https://abc123.ngrok.io)")
    print()
    print("4. Configure Twilio webhook:")
    print("   - Go to Twilio Console > Phone Numbers")
    print("   - Click on your phone number")
    print("   - Set webhook URL to: https://your-ngrok-url.ngrok.io/webhook")
    print("   - Set HTTP Method to: POST")
    print()
    print("5. Call your Twilio number and test!")
    print()

def main():
    """Main function."""
    print("🔧 TWILIO WEBHOOK SERVER SETUP")
    print("=" * 50)
    
    # Start server
    process = start_server()
    if not process:
        return
    
    # Test server
    if test_server():
        print("\n✅ Server is running successfully!")
        show_next_steps()
        
        print("Press Ctrl+C to stop the server...")
        try:
            # Keep the server running
            process.wait()
        except KeyboardInterrupt:
            print("\n🛑 Stopping server...")
            process.terminate()
            process.wait()
            print("✅ Server stopped")
    else:
        print("\n❌ Server test failed")
        process.terminate()

if __name__ == "__main__":
    main() 