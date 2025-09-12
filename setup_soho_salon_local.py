#!/usr/bin/env python3
"""
Setup SoHo Salon Denton as location 1 with complete service data (Local Storage)
"""

import json
import os

def setup_soho_salon_local():
    """Setup SoHo Salon Denton with local file storage"""
    
    # Load the comprehensive salon data
    with open('soho_salon_complete_data.json', 'r') as f:
        salon_data = json.load(f)
    
    print("🏪 Setting up SoHo Salon Denton (Local Storage)...")
    
    try:
        # Create ops_integrations/data directory if it doesn't exist
        data_dir = "ops_integrations/data"
        os.makedirs(data_dir, exist_ok=True)
        
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
            "last_updated": salon_data["scraped_at"]
        }
        
        # Save to local file
        knowledge_file = os.path.join(data_dir, f"{location_key}.json")
        with open(knowledge_file, 'w') as f:
            json.dump(knowledge_data, f, indent=2)
        
        print(f"✅ Knowledge data saved to {knowledge_file}")
        
        # 2. Update the existing soho_salon_data.json with complete info
        soho_salon_file = "soho_salon_data.json"
        if os.path.exists(soho_salon_file):
            print(f"📝 Updating existing {soho_salon_file}...")
            # Merge with existing data
            with open(soho_salon_file, 'r') as f:
                existing_data = json.load(f)
            
            # Update with new comprehensive data
            existing_data.update(knowledge_data)
            
            with open(soho_salon_file, 'w') as f:
                json.dump(existing_data, f, indent=2)
                
            print(f"✅ Updated {soho_salon_file}")
        
        # 3. Create environment setup file
        env_setup = """# SoHo Salon Denton Environment Setup

export PHONE_TO_LOCATION_MAP='{""+18084826296"": 1}'
export DEFAULT_LOCATION_ID=1
export ELEVENLABS_VOICE_ID=kdmDKE6EkgrWrrykO9Qt

# Optional Supabase configuration (for production)
# export SUPABASE_URL=your_supabase_url
# export SUPABASE_ANON_KEY=your_supabase_key

echo "🏪 SoHo Salon Denton environment configured!"
echo "📞 Phone: +18084826296 → Location 1"
echo "🎵 Voice: kdmDKE6EkgrWrrykO9Qt"
"""
        
        with open("soho_salon_env.sh", 'w') as f:
            f.write(env_setup)
        
        print("✅ Environment setup file created: soho_salon_env.sh")
        
        print("\n🎉 SoHo Salon Denton setup complete!")
        print(f"📍 Location ID: {salon_data['location_id']}")
        print(f"📞 Phone Number: {salon_data['phone_number']}")
        print(f"🌐 Website: {salon_data['website_url']}")
        print(f"🔧 Total Services: {len(salon_data['services'])}")
        print(f"📋 Service Categories: {len(salon_data['service_categories'])}")
        
        # Summary of key services by category
        print("\n🌟 Service Categories & Key Services:")
        category_examples = {
            "Hair Cuts": ["Signature Cut ($70+)", "Women's Cuts ($55+)", "Men's Cut ($45+)"],
            "Color Services": ["Full Balayage ($215+)", "All Over Color ($110+)", "Color Retouch ($90+)"],
            "Natural Hair Services": ["Silk Press ($100+)", "Two Strand Twist ($75+)"],
            "Braiding Services": ["Tribal Braids ($200+)", "Knotless Braids ($150+)", "Stitch Braids ($120+)"],
            "Chemical Services": ["Keratin Treatment ($310+)", "Hair Relaxer ($140+)", "Perm ($150+)"],
            "Treatments": ["Redken Acidic Bonding ($20)", "Scalp & Neck Massage ($25)"],
            "Consultations": ["Color Consultation (Free)", "Hair Extension Consultation (Free)"]
        }
        
        for category, examples in category_examples.items():
            print(f"\n  📂 {category}:")
            for example in examples:
                print(f"    • {example}")
        
        print("\n💡 Special Features:")
        for feature in salon_data["special_features"]:
            print(f"  • {feature}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error setting up SoHo Salon: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = setup_soho_salon_local()
    if success:
        print("\n✅ Setup completed successfully!")
        print("\nNext steps:")
        print("1. Source the environment variables:")
        print("   source soho_salon_env.sh")
        print("2. Start the salon phone service:")
        print("   cd ops_integrations && python3 -m services.salon_phone_service")
        print("3. Test the system:")
        print("   curl http://localhost:5001/shop/1/config")
        print("4. Make a test call to +18084826296")
    else:
        print("\n❌ Setup failed!")
        exit(1)
