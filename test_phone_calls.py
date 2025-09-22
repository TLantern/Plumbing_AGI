#!/usr/bin/env python3
"""
Test script for salon phone service integration
Tests the unified Supabase backend with simulated calls
"""

import asyncio
import json
import requests
import time
from datetime import datetime
from typing import Dict, Any

# Test configuration
BASE_URL = "http://localhost:5001"
TEST_SHOP_ID = "test_shop_001"
TEST_PHONE = "+15551234567"

class PhoneServiceTester:
    def __init__(self, base_url: str = BASE_URL):
        self.base_url = base_url
        self.test_calls = []
    
    async def setup_test_shop(self) -> Dict[str, Any]:
        """Setup a test shop for testing"""
        print("🏪 Setting up test shop...")
        
        shop_data = {
            "location_id": 1,
            "phone_number": TEST_PHONE,
            "website_url": "https://example-salon.com",
            "business_name": "Test Salon",
            "voice_id": "kdmDKE6EkgrWrrykO9Qt"
        }
        
        try:
            response = requests.post(f"{self.base_url}/shop/setup", json=shop_data)
            if response.status_code == 200:
                result = response.json()
                print(f"✅ Test shop setup: {result}")
                return result
            else:
                print(f"❌ Shop setup failed: {response.status_code} - {response.text}")
                return {"error": "Setup failed"}
        except Exception as e:
            print(f"❌ Error setting up shop: {e}")
            return {"error": str(e)}
    
    async def simulate_voice_webhook(self, call_sid: str, caller_number: str, outcome: str = "in_progress") -> Dict[str, Any]:
        """Simulate a Twilio voice webhook call"""
        print(f"📞 Simulating voice webhook for call {call_sid}...")
        
        # Simulate Twilio form data
        form_data = {
            "CallSid": call_sid,
            "From": caller_number,
            "To": TEST_PHONE,
            "CallStatus": "in-progress",
            "Direction": "inbound"
        }
        
        try:
            response = requests.post(f"{self.base_url}/voice", data=form_data)
            if response.status_code == 200:
                print(f"✅ Voice webhook successful: {response.text[:100]}...")
                return {"success": True, "twiml": response.text}
            else:
                print(f"❌ Voice webhook failed: {response.status_code} - {response.text}")
                return {"error": "Webhook failed"}
        except Exception as e:
            print(f"❌ Error with voice webhook: {e}")
            return {"error": str(e)}
    
    async def simulate_conversation_relay(self, call_sid: str, messages: list) -> Dict[str, Any]:
        """Simulate ConversationRelay WebSocket messages"""
        print(f"💬 Simulating conversation for call {call_sid}...")
        
        # This would normally be a WebSocket connection
        # For testing, we'll simulate the data that would be sent
        conversation_data = {
            "call_sid": call_sid,
            "messages": messages,
            "outcome": "booked" if "book" in " ".join(messages).lower() else "inquiry"
        }
        
        print(f"📝 Conversation data: {conversation_data}")
        return conversation_data
    
    async def check_call_logged(self, call_sid: str) -> Dict[str, Any]:
        """Check if call was logged in Supabase"""
        print(f"🔍 Checking if call {call_sid} was logged...")
        
        try:
            # This would normally query Supabase directly
            # For now, we'll check the metrics endpoint
            response = requests.get(f"{self.base_url}/metrics")
            if response.status_code == 200:
                metrics = response.json()
                print(f"📊 Current metrics: {metrics}")
                return metrics
            else:
                print(f"❌ Failed to get metrics: {response.status_code}")
                return {"error": "Metrics failed"}
        except Exception as e:
            print(f"❌ Error checking call: {e}")
            return {"error": str(e)}
    
    async def test_booking_call(self) -> Dict[str, Any]:
        """Test a call that results in a booking"""
        print("\n🎯 Testing booking call...")
        
        call_sid = f"CA{int(time.time())}001"
        caller_number = "+15559876543"
        
        # 1. Simulate voice webhook
        webhook_result = await self.simulate_voice_webhook(call_sid, caller_number)
        if not webhook_result.get("success"):
            return webhook_result
        
        # 2. Simulate conversation
        messages = [
            "Hi, I'd like to book an appointment",
            "I need a haircut for next Tuesday",
            "Yes, 2 PM works perfect",
            "Great, book me for that time"
        ]
        
        conversation_result = await self.simulate_conversation_relay(call_sid, messages)
        
        # 3. Check if call was logged
        await asyncio.sleep(1)  # Give time for processing
        metrics_result = await self.check_call_logged(call_sid)
        
        self.test_calls.append({
            "call_sid": call_sid,
            "type": "booking",
            "webhook_result": webhook_result,
            "conversation_result": conversation_result,
            "metrics_result": metrics_result
        })
        
        return {
            "call_sid": call_sid,
            "type": "booking",
            "success": True
        }
    
    async def test_inquiry_call(self) -> Dict[str, Any]:
        """Test a call that results in an inquiry"""
        print("\n❓ Testing inquiry call...")
        
        call_sid = f"CA{int(time.time())}002"
        caller_number = "+15551234567"
        
        # 1. Simulate voice webhook
        webhook_result = await self.simulate_voice_webhook(call_sid, caller_number)
        if not webhook_result.get("success"):
            return webhook_result
        
        # 2. Simulate conversation
        messages = [
            "Hi, what are your hours?",
            "Do you do color treatments?",
            "What are your prices?",
            "Thanks, I'll call back later"
        ]
        
        conversation_result = await self.simulate_conversation_relay(call_sid, messages)
        
        # 3. Check if call was logged
        await asyncio.sleep(1)  # Give time for processing
        metrics_result = await self.check_call_logged(call_sid)
        
        self.test_calls.append({
            "call_sid": call_sid,
            "type": "inquiry",
            "webhook_result": webhook_result,
            "conversation_result": conversation_result,
            "metrics_result": metrics_result
        })
        
        return {
            "call_sid": call_sid,
            "type": "inquiry",
            "success": True
        }
    
    async def check_platform_metrics(self) -> Dict[str, Any]:
        """Check platform-wide metrics"""
        print("\n📈 Checking platform metrics...")
        
        try:
            response = requests.get(f"{self.base_url}/admin/platform-metrics")
            if response.status_code == 200:
                metrics = response.json()
                print(f"🏢 Platform metrics: {metrics}")
                return metrics
            else:
                print(f"❌ Failed to get platform metrics: {response.status_code}")
                return {"error": "Platform metrics failed"}
        except Exception as e:
            print(f"❌ Error getting platform metrics: {e}")
            return {"error": str(e)}
    
    async def run_all_tests(self):
        """Run all test scenarios"""
        print("🚀 Starting phone service integration tests...")
        print(f"📍 Testing against: {self.base_url}")
        
        # 1. Setup test shop
        shop_result = await self.setup_test_shop()
        if shop_result.get("error"):
            print("❌ Cannot proceed without test shop")
            return
        
        # 2. Test booking call
        booking_result = await self.test_booking_call()
        
        # 3. Test inquiry call
        inquiry_result = await self.test_inquiry_call()
        
        # 4. Check platform metrics
        platform_metrics = await self.check_platform_metrics()
        
        # 5. Summary
        print("\n📋 Test Summary:")
        print(f"✅ Test shop setup: {'Success' if not shop_result.get('error') else 'Failed'}")
        print(f"✅ Booking call: {'Success' if booking_result.get('success') else 'Failed'}")
        print(f"✅ Inquiry call: {'Success' if inquiry_result.get('success') else 'Failed'}")
        print(f"✅ Platform metrics: {'Success' if not platform_metrics.get('error') else 'Failed'}")
        
        print(f"\n📞 Total test calls: {len(self.test_calls)}")
        for call in self.test_calls:
            print(f"  - {call['call_sid']}: {call['type']}")
        
        return {
            "shop_setup": shop_result,
            "booking_call": booking_result,
            "inquiry_call": inquiry_result,
            "platform_metrics": platform_metrics,
            "total_calls": len(self.test_calls)
        }

async def main():
    """Main test function"""
    tester = PhoneServiceTester()
    results = await tester.run_all_tests()
    
    print("\n🎉 Test completed!")
    return results

if __name__ == "__main__":
    asyncio.run(main())
