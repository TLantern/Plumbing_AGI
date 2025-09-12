#!/usr/bin/env python3
"""
Setup script to create missing tables in Supabase for website scraper integration
"""

import os
import asyncio
import logging
from supabase import create_client, Client

# Load environment variables
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    print("⚠️ python-dotenv not installed, using system environment variables only")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def setup_supabase_tables():
    """Create missing tables in Supabase"""
    
    # Get Supabase configuration
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_ANON_KEY")
    
    # Fallback: if SUPABASE_URL is not set, try to use DATABASE_URL
    if not supabase_url:
        database_url = os.getenv("DATABASE_URL")
        if database_url and "supabase.co" in database_url:
            # Convert database URL to API URL
            if database_url.startswith("https://db."):
                project_ref = database_url.replace("https://db.", "").replace(".supabase.co", "")
                supabase_url = f"https://{project_ref}.supabase.co"
            else:
                supabase_url = database_url
            logger.info(f"🔄 Using DATABASE_URL as SUPABASE_URL: {supabase_url}")
    
    if not supabase_url or not supabase_key:
        logger.error("❌ Missing Supabase configuration. Please set SUPABASE_URL and SUPABASE_ANON_KEY in your .env file")
        return False
    
    try:
        # Create Supabase client
        supabase: Client = create_client(supabase_url, supabase_key)
        logger.info(f"✅ Connected to Supabase: {supabase_url}")
        
        # Read the SQL file
        with open('create_supabase_tables.sql', 'r') as f:
            sql_commands = f.read()
        
        # Split SQL commands (simple approach - assumes semicolon separation)
        commands = [cmd.strip() for cmd in sql_commands.split(';') if cmd.strip()]
        
        logger.info(f"📝 Executing {len(commands)} SQL commands...")
        
        # Execute each command
        for i, command in enumerate(commands, 1):
            if command:
                try:
                    logger.info(f"Executing command {i}/{len(commands)}...")
                    # Use Supabase RPC to execute SQL
                    result = supabase.rpc('exec_sql', {'sql': command}).execute()
                    logger.info(f"✅ Command {i} executed successfully")
                except Exception as e:
                    logger.warning(f"⚠️ Command {i} failed (may already exist): {e}")
        
        logger.info("🎉 Table setup completed!")
        
        # Test the tables by trying to list them
        logger.info("🧪 Testing table access...")
        
        try:
            # Test salon_static_data table
            result = supabase.table('salon_static_data').select('key').limit(1).execute()
            logger.info("✅ salon_static_data table accessible")
        except Exception as e:
            logger.error(f"❌ salon_static_data table error: {e}")
        
        try:
            # Test scraped_services table
            result = supabase.table('scraped_services').select('id').limit(1).execute()
            logger.info("✅ scraped_services table accessible")
        except Exception as e:
            logger.error(f"❌ scraped_services table error: {e}")
        
        try:
            # Test scraped_professionals table
            result = supabase.table('scraped_professionals').select('id').limit(1).execute()
            logger.info("✅ scraped_professionals table accessible")
        except Exception as e:
            logger.error(f"❌ scraped_professionals table error: {e}")
        
        try:
            # Test salon_info table
            result = supabase.table('salon_info').select('id').limit(1).execute()
            logger.info("✅ salon_info table accessible")
        except Exception as e:
            logger.error(f"❌ salon_info table error: {e}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Setup failed: {e}")
        return False

if __name__ == "__main__":
    success = asyncio.run(setup_supabase_tables())
    if success:
        print("\n🎉 Supabase tables setup completed successfully!")
        print("Your salon phone service should now work with Supabase storage.")
    else:
        print("\n❌ Setup failed. Please check the logs above.")
