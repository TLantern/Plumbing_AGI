#!/usr/bin/env python3
"""
Insert SoHo Salon scraped data into Supabase
"""

import asyncio
import json
import logging
import sys
import os

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ops_integrations.services.supabase_integration import SupabaseSalonService

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

async def insert_soho_data_to_supabase():
    """Insert SoHo Salon data into Supabase"""
    
    print("🏢 Inserting SoHo Salon Data into Supabase")
    print("=" * 50)
    
    # Load the scraped data
    try:
        with open('soho_salon_data.json', 'r') as f:
            data = json.load(f)
        print("✅ Loaded scraped data from JSON file")
    except FileNotFoundError:
        print("❌ soho_salon_data.json not found. Please run the scraper first.")
        return
    except json.JSONDecodeError as e:
        print(f"❌ Error parsing JSON: {e}")
        return
    
    # Initialize Supabase service
    try:
        supabase_service = SupabaseSalonService()
        print("✅ Connected to Supabase")
    except Exception as e:
        print(f"❌ Error connecting to Supabase: {e}")
        print("Make sure DATABASE_URL and SUPABASE_ANON_KEY environment variables are set")
        return
    
    # Use a sample salon ID (you'll need to replace this with actual salon ID)
    salon_id = "soho-salon-denton"  # Replace with actual salon ID from your Supabase
    
    print(f"📊 Processing data for salon ID: {salon_id}")
    print(f"   Services: {len(data['services'])}")
    print(f"   Professionals: {len(data['professionals'])}")
    print()
    
    # Clear existing data
    print("🧹 Clearing existing data...")
    clear_result = await supabase_service.clear_existing_data(salon_id)
    if clear_result['status'] == 'success':
        print(f"✅ Cleared {clear_result.get('services_deleted', 0)} services and {clear_result.get('professionals_deleted', 0)} professionals")
    else:
        print(f"⚠️  Warning clearing data: {clear_result.get('message', 'Unknown error')}")
    
    # Insert services
    print("💇 Inserting services...")
    services_result = await supabase_service.insert_scraped_services(data['services'], salon_id)
    
    if services_result['status'] == 'success':
        print(f"✅ Inserted {services_result['services_inserted']} services")
        
        # Show sample services
        print("📋 Sample services inserted:")
        for i, service in enumerate(data['services'][:5]):
            price_dollars = service['price_cents'] / 100
            print(f"   {i+1}. {service['name']} - ${price_dollars:.2f} - {service['duration_minutes']}min")
    else:
        print(f"❌ Error inserting services: {services_result.get('message', 'Unknown error')}")
    
    # Insert professionals
    print("\n👥 Inserting professionals...")
    professionals_result = await supabase_service.insert_scraped_professionals(data['professionals'], salon_id)
    
    if professionals_result['status'] == 'success':
        print(f"✅ Inserted {professionals_result['professionals_inserted']} professionals")
        
        # Show sample professionals
        print("👥 Sample professionals inserted:")
        for i, prof in enumerate(data['professionals']):
            specialties = ', '.join(prof.get('specialties', []))
            print(f"   {i+1}. {prof['name']} - {prof.get('title', 'Stylist')}")
            if specialties:
                print(f"      Specialties: {specialties}")
    else:
        print(f"❌ Error inserting professionals: {professionals_result.get('message', 'Unknown error')}")
    
    # Update salon info
    print("\n🏢 Updating salon information...")
    salon_info_result = await supabase_service.update_salon_info(data['location_info'], salon_id)
    
    if salon_info_result['status'] == 'success':
        print("✅ Updated salon information")
        print(f"   Name: {data['location_info']['name']}")
        print(f"   Address: {data['location_info']['address']}")
        print(f"   Phone: {data['location_info']['phone']}")
    else:
        print(f"❌ Error updating salon info: {salon_info_result.get('message', 'Unknown error')}")
    
    # Summary
    print("\n📊 Supabase Insertion Summary:")
    print(f"   Salon ID: {salon_id}")
    print(f"   Services: {services_result.get('services_inserted', 0)} inserted")
    print(f"   Professionals: {professionals_result.get('professionals_inserted', 0)} inserted")
    print(f"   Salon Info: {'Updated' if salon_info_result['status'] == 'success' else 'Failed'}")
    
    if all(result['status'] in ['success', 'warning'] for result in [services_result, professionals_result, salon_info_result]):
        print("\n✅ All data successfully inserted into Supabase!")
        print("   The AI can now access this data for customer calls.")
    else:
        print("\n⚠️  Some data insertion failed. Check the errors above.")

if __name__ == "__main__":
    print("🚀 SoHo Salon Supabase Integration")
    print("=" * 40)
    
    # Run the insertion
    asyncio.run(insert_soho_data_to_supabase())
    
    print("\n✅ Integration completed!")
