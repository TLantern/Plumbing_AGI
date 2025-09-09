#!/usr/bin/env python3
"""
Test script for Google Sheets integration with enhanced metrics
Run this to test the new revenue/call, response speed, and call duration bucket tracking
"""

import asyncio
import httpx
import json
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def test_sheets_integration():
    """Test the Google Sheets integration with enhanced metrics"""
    
    # Salon service URL (adjust for your deployment)
    salon_service_url = "http://localhost:5001"  # Change to your Heroku URL for production
    
    try:
        logger.info("🧪 Starting Google Sheets integration test...")
        
        # Test the sheets integration endpoint
        async with httpx.AsyncClient() as client:
            response = await client.post(f"{salon_service_url}/test/sheets-integration")
            
            if response.status_code == 200:
                result = response.json()
                logger.info(f"✅ Test completed successfully!")
                logger.info(f"📊 Result: {json.dumps(result, indent=2)}")
                
                if result.get("status") == "success":
                    logger.info("🎉 Google Sheets integration is working correctly!")
                    logger.info("📈 Enhanced metrics being tracked:")
                    logger.info("   • Call Duration Buckets: Short (<30s), Medium (30s-2min), Long (>2min)")
                    logger.info("   • Response Speed: Time from first speech to first response")
                    logger.info("   • Revenue per Call: Based on service price and appointment scheduling")
                else:
                    logger.warning(f"⚠️ Test completed but with issues: {result.get('message')}")
            else:
                logger.error(f"❌ Test failed with status code: {response.status_code}")
                logger.error(f"Response: {response.text}")
                
    except httpx.ConnectError:
        logger.error(f"❌ Could not connect to salon service at {salon_service_url}")
        logger.error("Make sure the salon service is running locally or update the URL for your deployment")
    except Exception as e:
        logger.error(f"❌ Test failed with error: {e}")

async def test_direct_sheets_class():
    """Test the GoogleSheetsCRM class directly"""
    try:
        logger.info("🧪 Testing GoogleSheetsCRM class directly...")
        
        # Import the sheets class
        from ops_integrations.adapters.external_services.sheets import GoogleSheetsCRM
        
        # Create instance
        sheets_crm = GoogleSheetsCRM()
        
        if sheets_crm.enabled:
            logger.info("✅ GoogleSheetsCRM is enabled and configured")
            
            # Test the utility functions
            duration_bucket = sheets_crm.calculate_call_duration_bucket(45)
            response_speed = sheets_crm.calculate_response_speed(10.0, 12.5)
            revenue = sheets_crm.calculate_revenue_per_call(85.0, True)
            
            logger.info(f"📊 Test calculations:")
            logger.info(f"   • Duration bucket for 45s: {duration_bucket}")
            logger.info(f"   • Response speed (10s to 12.5s): {response_speed}s")
            logger.info(f"   • Revenue for $85 service with appointment: ${revenue}")
            
            # Test the integration
            result = sheets_crm.test_sheets_integration()
            logger.info(f"📈 Sheets integration test result: {result}")
            
        else:
            logger.warning("⚠️ GoogleSheetsCRM is not enabled")
            logger.info("To enable, set these environment variables:")
            logger.info("   • GOOGLE_SHEETS_SPREADSHEET_ID")
            logger.info("   • GOOGLE_SHEETS_CREDENTIALS_PATH or GOOGLE_SHEETS_CREDENTIALS_JSON")
            logger.info("   • SHEETS_BOOKINGS_TAB_NAME (optional, defaults to 'Bookings')")
            
    except ImportError as e:
        logger.error(f"❌ Could not import GoogleSheetsCRM: {e}")
    except Exception as e:
        logger.error(f"❌ Direct test failed: {e}")

async def main():
    """Run all tests"""
    logger.info("🚀 Starting Google Sheets Integration Tests")
    logger.info("=" * 60)
    
    # Test 1: Direct class test
    await test_direct_sheets_class()
    
    logger.info("\n" + "=" * 60)
    
    # Test 2: Service endpoint test
    await test_sheets_integration()
    
    logger.info("\n" + "=" * 60)
    logger.info("🏁 All tests completed!")

if __name__ == "__main__":
    asyncio.run(main())
