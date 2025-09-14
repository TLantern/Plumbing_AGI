"""
Supabase Configuration for Unified Backend
Ensures both the main webpage and salon phone service use the same Supabase instance
"""

import os
from typing import Dict, Any

# Supabase configuration matching the main webpage
SUPABASE_CONFIG = {
    "url": "https://yzoalegdsogecfiqzfbp.supabase.co",
    "anon_key": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Inl6b2FsZWdkc29nZWNmaXF6ZmJwIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTc2NTMyNzIsImV4cCI6MjA3MzIyOTI3Mn0.rZe11f29kVYP9_oI3ER6NAHPrYs5r6U4ksasV272HGw"
}

def get_supabase_config() -> Dict[str, str]:
    """Get Supabase configuration with environment variable overrides"""
    return {
        "url": os.getenv("SUPABASE_URL", SUPABASE_CONFIG["url"]),
        "anon_key": os.getenv("SUPABASE_ANON_KEY", SUPABASE_CONFIG["anon_key"])
    }

def setup_supabase_environment():
    """Set up environment variables for Supabase if not already set"""
    config = get_supabase_config()
    
    if not os.getenv("SUPABASE_URL"):
        os.environ["SUPABASE_URL"] = config["url"]
    
    if not os.getenv("SUPABASE_ANON_KEY"):
        os.environ["SUPABASE_ANON_KEY"] = config["anon_key"]
    
    return config

# Database schema information for reference
SCHEMA_INFO = {
    "tables": {
        "profiles": "Shop profiles and basic information",
        "salon_info": "Detailed salon information and settings",
        "calls": "Call logs and analytics",
        "appointments": "Appointment bookings",
        "services": "Service catalog",
        "scraped_services": "Detailed service information from website scraping",
        "scraped_professionals": "Staff information from website scraping",
        "salon_static_data": "Cached knowledge and static data",
        "audit_logs": "System audit trail",
        "user_roles": "User role management",
        "user_google_tokens": "Google OAuth tokens"
    },
    "functions": {
        "get_salon_kpis": "Get key performance indicators for a salon",
        "get_calls_timeseries": "Get call volume over time",
        "get_platform_metrics": "Get platform-wide metrics",
        "get_all_salons_overview": "Get overview of all salons",
        "get_recent_calls_view": "Get recent calls across all salons",
        "get_revenue_by_service_view": "Get revenue breakdown by service"
    }
}

def get_schema_info() -> Dict[str, Any]:
    """Get database schema information"""
    return SCHEMA_INFO
