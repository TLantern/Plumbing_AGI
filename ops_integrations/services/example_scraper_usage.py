"""
Example usage of the website scraper for salon information
"""

import asyncio
import logging
from website_scraper import update_location_from_website
from knowledge_service import knowledge_service

logging.basicConfig(level=logging.INFO)

async def demo_scraping():
    """Demonstrate website scraping functionality"""
    
    # Example salon websites to scrape
    example_websites = [
        "https://www.example-salon.com",  # Replace with actual salon website
        "https://www.anothersalon.com",   # Replace with actual salon website
    ]
    
    location_id = 1  # Default location
    
    for website_url in example_websites:
        print(f"\n🔍 Scraping website: {website_url}")
        
        try:
            # Scrape the website
            result = await update_location_from_website(location_id, website_url)
            
            print(f"✅ Scraping completed:")
            print(f"   Services found: {result['services_count']}")
            print(f"   Professionals found: {result['professionals_count']}")
            print(f"   FAQ items found: {result['faq_count']}")
            print(f"   Data saved to: {result['data_file']}")
            
            # Test the knowledge service
            knowledge = knowledge_service.get_location_knowledge(location_id)
            
            if knowledge:
                print(f"\n📚 Knowledge loaded for {knowledge.business_name}:")
                print(f"   Services: {len(knowledge.services)}")
                print(f"   Categories: {', '.join(knowledge.get_available_categories())}")
                
                price_range = knowledge.get_price_range()
                if price_range['max'] > 0:
                    print(f"   Price range: ${price_range['min']/100:.2f} - ${price_range['max']/100:.2f}")
                
                # Test service search
                test_queries = ["haircut", "color", "styling"]
                for query in test_queries:
                    matches = knowledge_service.find_service_matches(location_id, query)
                    if matches:
                        print(f"   '{query}' search found: {len(matches)} matches")
                
                # Test FAQ search
                faq_matches = knowledge.search_faq("price")
                if faq_matches:
                    print(f"   FAQ about 'price': {len(faq_matches)} items")
            
        except Exception as e:
            print(f"❌ Error scraping {website_url}: {e}")
        
        print("-" * 50)

async def demo_ai_context():
    """Demonstrate AI context generation"""
    location_id = 1
    
    print("\n🤖 AI Context for Location:")
    context = knowledge_service.get_ai_context_for_location(location_id)
    print(context)
    
    print("\n🔍 Booking Suggestions:")
    suggestions = knowledge_service.get_booking_suggestions(location_id, "haircut")
    print(f"Query: 'haircut'")
    print(f"Message: {suggestions.get('message', 'No message')}")
    
    if suggestions.get('exact_matches'):
        print(f"Exact matches: {len(suggestions['exact_matches'])}")
        for match in suggestions['exact_matches'][:3]:
            print(f"  - {match['name']}: ${match.get('price_cents', 0)/100:.2f}")

if __name__ == "__main__":
    print("🚀 Salon Website Scraper Demo")
    print("=" * 50)
    
    # Note: This demo requires actual salon websites to scrape
    # For testing, you can use any salon website URL
    
    print("\nTo run this demo:")
    print("1. Replace example URLs with real salon websites")
    print("2. Ensure database is initialized")
    print("3. Run: python example_scraper_usage.py")
    
    # Uncomment to run actual scraping
    # asyncio.run(demo_scraping())
    # asyncio.run(demo_ai_context())
    
    print("\n✅ Demo setup complete!")
