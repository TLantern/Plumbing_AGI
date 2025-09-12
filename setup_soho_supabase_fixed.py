#!/usr/bin/env python3
"""
Fixed Supabase setup for SoHo Salon Denton with proper UUID handling
"""

import json
import os
import sys
import uuid
from datetime import datetime

# Add the ops_integrations directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'ops_integrations'))

try:
    from supabase import create_client, Client
    print("✅ Supabase client imported successfully")
except ImportError:
    print("❌ Supabase client not available. Install with: pip install supabase")
    sys.exit(1)

def setup_soho_salon_supabase():
    """Setup SoHo Salon Denton directly in Supabase with proper UUIDs"""
    
    # Check environment variables
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_ANON_KEY")
    
    if not supabase_url or not supabase_key:
        print("❌ Missing Supabase environment variables:")
        print(f"SUPABASE_URL: {'✅' if supabase_url else '❌'}")
        print(f"SUPABASE_ANON_KEY: {'✅' if supabase_key else '❌'}")
        return False
    
    print(f"🔗 Connecting to Supabase: {supabase_url}")
    
    try:
        # Initialize Supabase client
        supabase: Client = create_client(supabase_url, supabase_key)
        print("✅ Supabase client initialized")
        
        # Load the comprehensive salon data
        with open('soho_salon_complete_data.json', 'r') as f:
            salon_data = json.load(f)
        
        print("🏪 Setting up SoHo Salon Denton in Supabase...")
        
        # Generate a consistent UUID for SoHo Salon Denton
        # Using a deterministic UUID based on the business name
        salon_uuid = str(uuid.uuid5(uuid.NAMESPACE_DNS, "soho-salon-denton.com"))
        print(f"🏢 Salon UUID: {salon_uuid}")
        
        # 1. Store the complete knowledge data in salon_static_data table
        location_key = "location_1"
        print(f"📚 Storing knowledge data for {location_key}...")
        
        knowledge_data = {
            "business_name": salon_data["business_name"],
            "website_url": salon_data["website_url"], 
            "phone_number": salon_data["phone_number"],
            "location_id": salon_data["location_id"],
            "salon_uuid": salon_uuid,  # Add UUID for reference
            "services": salon_data["services"],
            "service_categories": salon_data["service_categories"],
            "pricing_info": salon_data["pricing_info"],
            "special_features": salon_data["special_features"],
            "booking_notes": salon_data["booking_notes"],
            "scraped_at": salon_data["scraped_at"],
            "total_services": len(salon_data["services"]),
            "professionals": [
                {
                    "name": "SoHo Salon Team",
                    "title": "Professional Stylists",
                    "specialties": [
                        "Hair Cuts & Styling",
                        "Color Services & Balayage", 
                        "Natural Hair Care",
                        "Braiding & Protective Styles",
                        "Chemical Services",
                        "Hair Treatments"
                    ],
                    "bio": "Our experienced team specializes in both traditional and natural hair care, offering everything from precision cuts to protective braiding styles."
                }
            ],
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
                },
                {
                    "question": "What's the price range for your services?",
                    "answer": "We offer services from free consultations to premium treatments up to $310+. Most cuts range from $25-$70, color services $85-$215+, and treatments $20-$310+."
                },
                {
                    "question": "How long do appointments take?",
                    "answer": "Appointment times vary: Quick services like bang trims take 15 minutes, cuts 30-75 minutes, color services 90-180 minutes, and braiding services 2-6+ hours."
                }
            ],
            "last_updated": datetime.now().isoformat()
        }
        
        # Insert into salon_static_data table
        result = supabase.table('salon_static_data').upsert({
            'key': location_key,
            'data': knowledge_data,
            'updated_at': datetime.now().isoformat()
        }).execute()
        
        print(f"✅ Knowledge data stored in Supabase: {len(result.data)} records")
        
        # 2. Store detailed service data in scraped_services table
        print("🔧 Storing detailed service data...")
        
        services_data = []
        for service in salon_data["services"]:
            service_record = {
                'salon_id': salon_uuid,  # Use UUID instead of string
                'service_name': service.get('name', ''),
                'description': service.get('description', ''),
                'price': service.get('price', ''),
                'duration': service.get('duration', ''),
                'category': service.get('category', ''),
                'raw_data': service,
                'created_at': datetime.now().isoformat()
            }
            services_data.append(service_record)
        
        services_result = supabase.table('scraped_services').upsert(services_data).execute()
        print(f"✅ Stored {len(services_result.data)} services in Supabase")
        
        # 3. Store salon info
        print("🏢 Storing salon information...")
        salon_info = {
            'salon_id': salon_uuid,  # Use UUID
            'business_name': salon_data["business_name"],
            'website_url': salon_data["website_url"],
            'phone': salon_data["phone_number"],
            'address': "Denton, TX",
            'hours': {
                "note": "Please call for current hours",
                "booking": "Online booking available 24/7"
            },
            'faq_items': knowledge_data["faq_items"],
            'created_at': datetime.now().isoformat()
        }
        
        salon_result = supabase.table('salon_info').upsert(salon_info).execute()
        print(f"✅ Salon information stored: {len(salon_result.data)} records")
        
        # 4. Store professional data
        print("👥 Storing professional data...")
        professional_data = {
            'salon_id': salon_uuid,
            'name': "SoHo Salon Team",
            'title': "Professional Stylists",
            'bio': "Our experienced team specializes in both traditional and natural hair care, offering everything from precision cuts to protective braiding styles.",
            'specialties': [
                "Hair Cuts & Styling",
                "Color Services & Balayage", 
                "Natural Hair Care",
                "Braiding & Protective Styles",
                "Chemical Services",
                "Hair Treatments"
            ],
            'raw_data': knowledge_data["professionals"][0],
            'created_at': datetime.now().isoformat()
        }
        
        professional_result = supabase.table('scraped_professionals').upsert(professional_data).execute()
        print(f"✅ Professional data stored: {len(professional_result.data)} records")
        
        print("\n🎉 SoHo Salon Denton setup complete in Supabase!")
        print(f"📍 Location ID: {salon_data['location_id']}")
        print(f"🏢 Salon UUID: {salon_uuid}")
        print(f"📞 Phone Number: {salon_data['phone_number']}")
        print(f"🌐 Website: {salon_data['website_url']}")
        print(f"🔧 Total Services: {len(salon_data['services'])}")
        print(f"📋 Service Categories: {len(salon_data['service_categories'])}")
        
        # Verify the data was stored
        print("\n🔍 Verifying data in Supabase...")
        
        # Check salon_static_data
        static_check = supabase.table('salon_static_data').select('key').eq('key', location_key).execute()
        print(f"✅ salon_static_data: {len(static_check.data)} records")
        
        # Check scraped_services
        services_check = supabase.table('scraped_services').select('id').eq('salon_id', salon_uuid).execute()
        print(f"✅ scraped_services: {len(services_check.data)} records")
        
        # Check salon_info
        info_check = supabase.table('salon_info').select('id').eq('salon_id', salon_uuid).execute()
        print(f"✅ salon_info: {len(info_check.data)} records")
        
        # Check scraped_professionals
        prof_check = supabase.table('scraped_professionals').select('id').eq('salon_id', salon_uuid).execute()
        print(f"✅ scraped_professionals: {len(prof_check.data)} records")
        
        # Save the UUID for future reference
        with open('soho_salon_uuid.txt', 'w') as f:
            f.write(salon_uuid)
        print(f"💾 Salon UUID saved to soho_salon_uuid.txt")
        
        return True
        
    except Exception as e:
        print(f"❌ Error setting up SoHo Salon in Supabase: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = setup_soho_salon_supabase()
    if success:
        print("\n✅ Supabase setup completed successfully!")
        print("\nNext steps:")
        print("1. Update PHONE_TO_LOCATION_MAP environment variable:")
        print('   export PHONE_TO_LOCATION_MAP=\'{"'+"+18084826296"+'": 1}\'')
        print("2. Start the salon phone service")
        print("3. Test with: curl http://localhost:5001/shop/1/config")
        print("4. The salon UUID is saved in soho_salon_uuid.txt for reference")
    else:
        print("\n❌ Supabase setup failed!")
        sys.exit(1)
