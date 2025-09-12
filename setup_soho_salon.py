#!/usr/bin/env python3
"""
Setup SoHo Salon Denton as location 1 with complete service data
"""

import json
import asyncio
import sys
import os

# Add the ops_integrations directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'ops_integrations'))

from services.supabase_storage import get_supabase_storage
from services.knowledge_service import knowledge_service

async def setup_soho_salon():
    """Setup SoHo Salon Denton with complete service data"""
    
    # Load the comprehensive salon data
    with open('soho_salon_complete_data.json', 'r') as f:
        salon_data = json.load(f)
    
    print("🏪 Setting up SoHo Salon Denton...")
    
    try:
        # Get Supabase storage
        supabase_storage = get_supabase_storage()
        
        # 1. Store the complete knowledge data
        location_key = "location_1"
        print(f"📚 Storing knowledge data for {location_key}...")
        
        knowledge_data = {
            "business_name": salon_data["business_name"],
            "website_url": salon_data["website_url"], 
            "phone_number": salon_data["phone_number"],
            "location_id": salon_data["location_id"],
            "services": salon_data["services"],
            "service_categories": salon_data["service_categories"],
            "pricing_info": salon_data["pricing_info"],
            "special_features": salon_data["special_features"],
            "booking_notes": salon_data["booking_notes"],
            "scraped_at": salon_data["scraped_at"],
            "total_services": len(salon_data["services"]),
            "faq_items": [
                {
                    "question": "Do you offer free consultations?",
                    "answer": "Yes! We offer free color consultations and hair extension consultations to help plan your perfect look."
                },
                {
                    "question": "Do you require deposits?",
                    "answer": "Yes, deposits are required for most services over $50, especially color and chemical services."
                },
                {
                    "question": "Do you offer financing options?",
                    "answer": "Yes! We offer Buy Now, Pay Later options for bookings between $50-$4,000. You can get approved before your appointment."
                },
                {
                    "question": "Do you specialize in natural hair?",
                    "answer": "Absolutely! We specialize in natural hair care, protective styling, braiding services, silk press, and chemical-free treatments."
                },
                {
                    "question": "Do you offer kids services?",
                    "answer": "Yes, we offer kids cuts for children 10 & under, as well as decorative custom braids for children under 11."
                },
                {
                    "question": "What are your signature services?",
                    "answer": "Our signature services include Signature Cuts ($70+), Full Balayage ($215+), Silk Press ($100+), and comprehensive braiding services."
                }
            ]
        }
        
        success = await supabase_storage.store_knowledge(location_key, knowledge_data)
        if success:
            print("✅ Knowledge data stored successfully!")
        else:
            print("❌ Failed to store knowledge data")
            return False
        
        # 2. Store detailed service data
        print("🔧 Storing detailed service data...")
        services_result = await supabase_storage.insert_scraped_services(
            salon_data["services"], 
            str(salon_data["location_id"])
        )
        
        if services_result.get('success'):
            print(f"✅ Stored {services_result.get('inserted_count', 0)} services")
        else:
            print(f"⚠️ Service storage result: {services_result}")
        
        # 3. Store salon info
        print("🏢 Storing salon information...")
        salon_info = {
            'salon_id': str(salon_data["location_id"]),
            'business_name': salon_data["business_name"],
            'website_url': salon_data["website_url"],
            'phone': salon_data["phone_number"],
            'address': "Denton, TX",  # From business name
            'hours': {
                "note": "Please call for current hours",
                "booking": "Online booking available 24/7"
            },
            'faq_items': knowledge_data["faq_items"]
        }
        
        salon_result = await supabase_storage.insert_salon_info(salon_info)
        if salon_result.get('success'):
            print("✅ Salon information stored successfully!")
        else:
            print(f"⚠️ Salon info result: {salon_result}")
        
        # 4. Update knowledge service cache
        print("🧠 Updating knowledge service cache...")
        try:
            await knowledge_service.load_location_knowledge(salon_data["location_id"])
            print("✅ Knowledge cache updated!")
        except Exception as e:
            print(f"⚠️ Cache update error: {e}")
        
        print("\n🎉 SoHo Salon Denton setup complete!")
        print(f"📍 Location ID: {salon_data['location_id']}")
        print(f"📞 Phone Number: {salon_data['phone_number']}")
        print(f"🌐 Website: {salon_data['website_url']}")
        print(f"🔧 Total Services: {len(salon_data['services'])}")
        print(f"📋 Service Categories: {len(salon_data['service_categories'])}")
        
        # Summary of key services
        print("\n🌟 Key Services:")
        key_services = [
            "Signature Cut ($70+)",
            "Full Balayage ($215+)", 
            "Silk Press ($100+)",
            "Keratin Treatment ($310+)",
            "Knotless Braids ($150+)",
            "Free Consultations"
        ]
        for service in key_services:
            print(f"  • {service}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error setting up SoHo Salon: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(setup_soho_salon())
    if success:
        print("\n✅ Setup completed successfully!")
        print("\nNext steps:")
        print("1. Update PHONE_TO_LOCATION_MAP environment variable:")
        print('   PHONE_TO_LOCATION_MAP=\'{"'+"+18084826296"+'": 1}\'')
        print("2. Start the salon phone service")
        print("3. Test with a call to +18084826296")
    else:
        print("\n❌ Setup failed!")
        sys.exit(1)
