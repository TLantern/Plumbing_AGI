#!/usr/bin/env python3
"""
Test script to scrape SoHo Salon Denton website
"""

import asyncio
import logging
import sys
import os

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ops_integrations.services.website_scraper import SalonWebsiteScraper
from ops_integrations.services.static_data_manager import setup_location_data

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

async def test_soho_salon_scraping():
    """Test scraping the SoHo Salon Denton website"""
    
    website_url = "https://sohosalondenton.glossgenius.com"
    location_id = 1
    
    print("🔍 Testing SoHo Salon Denton Website Scraping")
    print("=" * 50)
    print(f"Website: {website_url}")
    print(f"Location ID: {location_id}")
    print()
    
    try:
        # Test the scraper directly
        print("📡 Testing website scraper...")
        async with SalonWebsiteScraper() as scraper:
            scraped_info = await scraper.scrape_salon_website(website_url)
            
            print(f"✅ Scraping completed!")
            print(f"   Business Name: {scraped_info.business_name}")
            print(f"   Services Found: {len(scraped_info.services)}")
            print(f"   Professionals Found: {len(scraped_info.professionals)}")
            print(f"   FAQ Items Found: {len(scraped_info.faq_items)}")
            print()
            
            # Show sample services
            if scraped_info.services:
                print("📋 Sample Services:")
                for i, service in enumerate(scraped_info.services[:5]):
                    price_text = f"${service.price_cents/100:.2f}" if service.price_cents else "Price varies"
                    duration_text = f"{service.duration_min}min" if service.duration_min else "Duration varies"
                    print(f"   {i+1}. {service.name} - {price_text}, {duration_text}")
                    if service.description:
                        print(f"      {service.description[:100]}...")
                print()
            
            # Show sample professionals
            if scraped_info.professionals:
                print("👥 Sample Professionals:")
                for i, prof in enumerate(scraped_info.professionals[:3]):
                    print(f"   {i+1}. {prof.name} - {prof.title}")
                    if prof.specialties:
                        print(f"      Specialties: {', '.join(prof.specialties)}")
                    if prof.bio:
                        print(f"      Bio: {prof.bio[:100]}...")
                print()
            
            # Show sample FAQ
            if scraped_info.faq_items:
                print("❓ Sample FAQ:")
                for i, faq in enumerate(scraped_info.faq_items[:3]):
                    print(f"   {i+1}. Q: {faq['question']}")
                    print(f"      A: {faq['answer'][:100]}...")
                print()
        
        # Test the full setup process
        print("💾 Testing data storage setup...")
        result = await setup_location_data(location_id, website_url)
        
        if result['status'] == 'success':
            print(f"✅ Data storage successful!")
            print(f"   Business: {result['business_name']}")
            print(f"   Services: {result['stats']['services_count']}")
            print(f"   Professionals: {result['stats']['professionals_count']}")
            print(f"   FAQ Items: {result['stats']['faq_count']}")
            print(f"   Storage Key: {result['storage_key']}")
        else:
            print(f"❌ Data storage failed: {result.get('error', 'Unknown error')}")
        
    except Exception as e:
        print(f"❌ Error during testing: {e}")
        import traceback
        traceback.print_exc()

async def test_booking_flow_page():
    """Test scraping the specific booking flow page"""
    
    booking_url = "https://sohosalondenton.glossgenius.com/booking-flow"
    
    print("\n🎯 Testing Booking Flow Page")
    print("=" * 30)
    print(f"URL: {booking_url}")
    print()
    
    try:
        async with SalonWebsiteScraper() as scraper:
            scraped_info = await scraper.scrape_salon_website(booking_url)
            
            print(f"✅ Booking page scraping completed!")
            print(f"   Business Name: {scraped_info.business_name}")
            print(f"   Services Found: {len(scraped_info.services)}")
            print(f"   Professionals Found: {len(scraped_info.professionals)}")
            print(f"   FAQ Items Found: {len(scraped_info.faq_items)}")
            
            # Show all services from booking page
            if scraped_info.services:
                print("\n📋 All Services from Booking Page:")
                for i, service in enumerate(scraped_info.services):
                    price_text = f"${service.price_cents/100:.2f}" if service.price_cents else "Price varies"
                    duration_text = f"{service.duration_min}min" if service.duration_min else "Duration varies"
                    print(f"   {i+1}. {service.name} - {price_text}, {duration_text}")
                    print(f"      Category: {service.category}")
                    if service.description:
                        print(f"      Description: {service.description[:150]}...")
                    print()
            
    except Exception as e:
        print(f"❌ Error scraping booking page: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    print("🚀 SoHo Salon Denton Scraping Test")
    print("=" * 40)
    
    # Run the tests
    asyncio.run(test_soho_salon_scraping())
    asyncio.run(test_booking_flow_page())
    
    print("\n✅ Testing completed!")
