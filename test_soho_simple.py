#!/usr/bin/env python3
"""
Simple test script to scrape SoHo Salon Denton website without database
"""

import asyncio
import logging
import sys
import os

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ops_integrations.services.website_scraper import SalonWebsiteScraper

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

async def test_soho_salon_simple():
    """Test scraping the SoHo Salon Denton website without database"""
    
    website_url = "https://sohosalondenton.glossgenius.com"
    
    print("🔍 Testing SoHo Salon Denton Website Scraping (Simple)")
    print("=" * 60)
    print(f"Website: {website_url}")
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
            else:
                print("❌ No services found - this might indicate the website structure is different")
                print("   The website might be using JavaScript to load content dynamically")
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
            else:
                print("❌ No professionals found")
                print()
            
            # Show sample FAQ
            if scraped_info.faq_items:
                print("❓ Sample FAQ:")
                for i, faq in enumerate(scraped_info.faq_items[:3]):
                    print(f"   {i+1}. Q: {faq['question']}")
                    print(f"      A: {faq['answer'][:100]}...")
                print()
            else:
                print("❌ No FAQ items found")
                print()
        
        # Test the booking flow page specifically
        print("🎯 Testing Booking Flow Page")
        print("=" * 30)
        booking_url = "https://sohosalondenton.glossgenius.com/booking-flow"
        print(f"URL: {booking_url}")
        
        async with SalonWebsiteScraper() as scraper:
            booking_info = await scraper.scrape_salon_website(booking_url)
            
            print(f"✅ Booking page scraping completed!")
            print(f"   Business Name: {booking_info.business_name}")
            print(f"   Services Found: {len(booking_info.services)}")
            print(f"   Professionals Found: {len(booking_info.professionals)}")
            print(f"   FAQ Items Found: {len(booking_info.faq_items)}")
            
            if booking_info.services:
                print("\n📋 Services from Booking Page:")
                for i, service in enumerate(booking_info.services):
                    price_text = f"${service.price_cents/100:.2f}" if service.price_cents else "Price varies"
                    duration_text = f"{service.duration_min}min" if service.duration_min else "Duration varies"
                    print(f"   {i+1}. {service.name} - {price_text}, {duration_text}")
                    print(f"      Category: {service.category}")
                    if service.description:
                        print(f"      Description: {service.description[:150]}...")
                    print()
        
    except Exception as e:
        print(f"❌ Error during testing: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    print("🚀 SoHo Salon Denton Simple Scraping Test")
    print("=" * 45)
    
    # Run the test
    asyncio.run(test_soho_salon_simple())
    
    print("\n✅ Testing completed!")
    print("\n📝 Notes:")
    print("   - If no services were found, the website might use JavaScript")
    print("   - GlossGenius websites often load content dynamically")
    print("   - Consider using a headless browser for JavaScript-heavy sites")
