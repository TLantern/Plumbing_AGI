#!/usr/bin/env python3
"""
Direct Supabase integration test
Tests the unified backend without requiring the full phone service to be running
"""

import asyncio
import json
import os
from datetime import datetime, timezone
from typing import Dict, Any

# Set up environment
os.environ["SUPABASE_URL"] = "https://yzoalegdsogecfiqzfbp.supabase.co"
os.environ["SUPABASE_ANON_KEY"] = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Inl6b2FsZWdkc29nZWNmaXF6ZmJwIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTc2NTMyNzIsImV4cCI6MjA3MzIyOTI3Mn0.rZe11f29kVYP9_oI3ER6NAHPrYs5r6U4ksasV272HGw"

from ops_integrations.services.unified_supabase_service import get_unified_supabase_service, CallData, AppointmentData

class SupabaseIntegrationTester:
    def __init__(self):
        self.supabase_service = get_unified_supabase_service()
        self.test_results = []
    
    async def test_shop_creation(self) -> Dict[str, Any]:
        """Test creating a shop in Supabase"""
        print("🏪 Testing shop creation...")
        
        shop_data = {
            'salon_id': 'test_shop_001',
            'salon_name': 'Test Salon Integration',
            'business_name': 'Test Salon Integration',
            'website_url': 'https://test-salon.com',
            'phone': '+15551234567',
            'timezone': 'America/New_York'
        }
        
        try:
            result = await self.supabase_service.create_or_update_shop(shop_data)
            print(f"✅ Shop creation result: {result}")
            return result
        except Exception as e:
            print(f"❌ Shop creation failed: {e}")
            return {"error": str(e)}
    
    async def test_call_logging(self) -> Dict[str, Any]:
        """Test logging a call to Supabase"""
        print("📞 Testing call logging...")
        
        call_data = CallData(
            call_sid="CA_TEST_001",
            salon_id="test_shop_001",
            caller_phone="+15559876543",
            caller_name="Test Customer",
            call_type="answered",
            outcome="in_progress",
            intent="appointment_booking",
            sentiment="positive",
            duration_seconds=0,
            timestamp=datetime.now(timezone.utc).isoformat()
        )
        
        try:
            result = await self.supabase_service.log_call(call_data)
            print(f"✅ Call logging result: {result}")
            return result
        except Exception as e:
            print(f"❌ Call logging failed: {e}")
            return {"error": str(e)}
    
    async def test_call_outcome_update(self) -> Dict[str, Any]:
        """Test updating call outcome"""
        print("🔄 Testing call outcome update...")
        
        try:
            result = await self.supabase_service.update_call_outcome(
                "CA_TEST_001",
                outcome="booked",
                intent="haircut_appointment",
                sentiment="positive"
            )
            print(f"✅ Call outcome update result: {result}")
            return result
        except Exception as e:
            print(f"❌ Call outcome update failed: {e}")
            return {"error": str(e)}
    
    async def test_appointment_creation(self) -> Dict[str, Any]:
        """Test creating an appointment"""
        print("📅 Testing appointment creation...")
        
        appointment_data = AppointmentData(
            salon_id="test_shop_001",
            call_id="CA_TEST_001",
            service_id="svc_haircut",
            appointment_date="2024-01-15T14:00:00Z",
            status="scheduled",
            estimated_revenue_cents=8000
        )
        
        try:
            result = await self.supabase_service.create_appointment(appointment_data)
            print(f"✅ Appointment creation result: {result}")
            return result
        except Exception as e:
            print(f"❌ Appointment creation failed: {e}")
            return {"error": str(e)}
    
    async def test_services_storage(self) -> Dict[str, Any]:
        """Test storing services for a shop"""
        print("🛍️ Testing services storage...")
        
        services = [
            {
                "name": "Haircut & Style",
                "description": "Professional haircut and styling",
                "price": "$80",
                "price_cents": 8000,
                "duration": "60 minutes",
                "category": "Hair Services"
            },
            {
                "name": "Color Treatment",
                "description": "Full color service",
                "price": "$120",
                "price_cents": 12000,
                "duration": "90 minutes",
                "category": "Color Services"
            }
        ]
        
        try:
            result = await self.supabase_service.store_services("test_shop_001", services)
            print(f"✅ Services storage result: {result}")
            return result
        except Exception as e:
            print(f"❌ Services storage failed: {e}")
            return {"error": str(e)}
    
    async def test_shop_metrics(self) -> Dict[str, Any]:
        """Test getting shop metrics"""
        print("📊 Testing shop metrics...")
        
        try:
            result = await self.supabase_service.get_shop_metrics("test_shop_001", 30)
            print(f"✅ Shop metrics result: {result}")
            return result
        except Exception as e:
            print(f"❌ Shop metrics failed: {e}")
            return {"error": str(e)}
    
    async def test_platform_metrics(self) -> Dict[str, Any]:
        """Test getting platform metrics"""
        print("🏢 Testing platform metrics...")
        
        try:
            result = await self.supabase_service.get_platform_metrics()
            print(f"✅ Platform metrics result: {result}")
            return result
        except Exception as e:
            print(f"❌ Platform metrics failed: {e}")
            return {"error": str(e)}
    
    async def test_shop_listing(self) -> Dict[str, Any]:
        """Test listing all shops"""
        print("📋 Testing shop listing...")
        
        try:
            result = await self.supabase_service.list_all_shops()
            print(f"✅ Shop listing result: {len(result)} shops found")
            for shop in result:
                print(f"  - {shop.get('salon_name', 'Unknown')} (ID: {shop.get('id', 'Unknown')})")
            return {"shops": result, "count": len(result)}
        except Exception as e:
            print(f"❌ Shop listing failed: {e}")
            return {"error": str(e)}
    
    async def run_all_tests(self):
        """Run all integration tests"""
        print("🚀 Starting Supabase integration tests...")
        print("=" * 50)
        
        tests = [
            ("Shop Creation", self.test_shop_creation),
            ("Services Storage", self.test_services_storage),
            ("Call Logging", self.test_call_logging),
            ("Call Outcome Update", self.test_call_outcome_update),
            ("Appointment Creation", self.test_appointment_creation),
            ("Shop Metrics", self.test_shop_metrics),
            ("Platform Metrics", self.test_platform_metrics),
            ("Shop Listing", self.test_shop_listing)
        ]
        
        results = {}
        
        for test_name, test_func in tests:
            print(f"\n🧪 Running: {test_name}")
            print("-" * 30)
            try:
                result = await test_func()
                results[test_name] = result
                self.test_results.append({
                    "test": test_name,
                    "success": not result.get("error"),
                    "result": result
                })
            except Exception as e:
                print(f"❌ Test {test_name} failed with exception: {e}")
                results[test_name] = {"error": str(e)}
                self.test_results.append({
                    "test": test_name,
                    "success": False,
                    "result": {"error": str(e)}
                })
        
        # Summary
        print("\n" + "=" * 50)
        print("📋 Test Summary:")
        print("=" * 50)
        
        passed = sum(1 for result in self.test_results if result["success"])
        total = len(self.test_results)
        
        for result in self.test_results:
            status = "✅ PASS" if result["success"] else "❌ FAIL"
            print(f"{status} {result['test']}")
        
        print(f"\n🎯 Results: {passed}/{total} tests passed")
        
        if passed == total:
            print("🎉 All tests passed! Supabase integration is working correctly.")
        else:
            print("⚠️ Some tests failed. Check the errors above.")
        
        return {
            "total_tests": total,
            "passed_tests": passed,
            "failed_tests": total - passed,
            "results": results
        }

async def main():
    """Main test function"""
    tester = SupabaseIntegrationTester()
    results = await tester.run_all_tests()
    return results

if __name__ == "__main__":
    asyncio.run(main())
