#!/usr/bin/env python3
"""
Startup script for Bold Wings Salon Phone Service
Compressed phone service with Bold Wings service integration
"""

import os
import sys
import logging
import argparse
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv(project_root / ".env")

def setup_logging(log_level: str = "INFO"):
    """Set up logging configuration."""
    logs_dir = project_root / "logs"
    logs_dir.mkdir(exist_ok=True)
    
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(logs_dir / "salon_phone.log")
        ]
    )

def check_dependencies():
    """Check if required dependencies are installed."""
    REQUIRED_PACKAGES = [
        'fastapi',
        'uvicorn',
        'websockets',
        'twilio',
        'clicksend_client',
        'openai',
        'elevenlabs',
        'httpx',
        'flask',
        'python_multipart',
        'webrtcvad',
        'whisper'
    ]
    
    missing_packages = []
    
    for package in REQUIRED_PACKAGES:
        try:
            __import__(package)
        except ImportError:
            missing_packages.append(package)
    
    if missing_packages:
        print(f"❌ Missing required packages: {', '.join(missing_packages)}")
        print("Install them with: pip install fastapi uvicorn websockets twilio openai httpx")
        return False
    
    return True

def check_environment():
    """Check environment variables"""
    required_vars = [
        'TWILIO_ACCOUNT_SID',
        'TWILIO_AUTH_TOKEN', 
        'OPENAI_API_KEY',
        'PUBLIC_BASE_URL',
        'WSS_PUBLIC_URL'
    ]
    
    missing_vars = []
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        print(f"⚠️  Missing required environment variables: {', '.join(missing_vars)}")
        print("Set them in your .env file or environment")
        print("Service will start but ConversationRelay features may not work")
    else:
        print("✅ All required environment variables are set")
    
    # Optional variables for enhanced features
    optional_vars = [
        'CI_SERVICE_SID',  # For Conversational Intelligence analytics
        'ELEVENLABS_API_KEY',  # For direct ElevenLabs TTS (Twilio handles this now)
        'ELEVENLABS_VOICE_ID'  # Voice selection for Twilio TTS
    ]
    for var in optional_vars:
        if not os.getenv(var):
            print(f"ℹ️  Optional variable {var} not set")
    
    # Check URL formats
    public_url = os.getenv('PUBLIC_BASE_URL', '')
    wss_url = os.getenv('WSS_PUBLIC_URL', '')
    
    if public_url and not public_url.startswith('https://'):
        print(f"⚠️  PUBLIC_BASE_URL should start with https:// (current: {public_url})")
    
    if wss_url and not wss_url.startswith('wss://'):
        print(f"⚠️  WSS_PUBLIC_URL should start with wss:// (current: {wss_url})")

def verify_boldwings_config():
    """Verify Bold Wings service configuration exists"""
    config_path = project_root / "ops_integrations" / "config" / "boldwings.json"
    names_path = project_root / "ops_integrations" / "config" / "boldwings_name.json"
    
    # Check services configuration
    if not config_path.exists():
        print(f"❌ Bold Wings configuration not found at {config_path}")
        return False
    
    try:
        import json
        with open(config_path, 'r') as f:
            config = json.load(f)
        
        if 'services' not in config:
            print("❌ Invalid Bold Wings configuration: missing 'services' key")
            return False
        
        service_count = sum(len(services) for services in config['services'].values())
        print(f"✅ Bold Wings services loaded: {service_count} services across {len(config['services'])} categories")
        
    except Exception as e:
        print(f"❌ Failed to load Bold Wings configuration: {e}")
        return False
    
    # Check names configuration
    if not names_path.exists():
        print(f"⚠️  Bold Wings names configuration not found at {names_path}")
        print("   Name recognition will use basic patterns only")
        return True  # Not critical, service can still work
    
    try:
        with open(names_path, 'r') as f:
            names_config = json.load(f)
        
        if 'nigerian_names' not in names_config:
            print("⚠️  Invalid Bold Wings names configuration: missing 'nigerian_names' key")
            return True
        
        name_count = len(names_config['nigerian_names'])
        print(f"✅ Bold Wings names loaded: {name_count} Nigerian names for enhanced recognition")
        
        # Don't show sample names for privacy
        print(f"   ✅ {name_count} Nigerian names loaded for enhanced recognition")
        
        return True
        
    except Exception as e:
        print(f"⚠️  Failed to load Bold Wings names: {e}")
        print("   Name recognition will use basic patterns only")
        return True  # Not critical

def start_salon_phone_service(host: str = "0.0.0.0", port: int = 5001, reload: bool = False):
    """Start the salon phone service"""
    try:
        import uvicorn
        
        print(f"🚀 Starting Bold Wings Salon Phone Service (ConversationRelay + CI) on {host}:{port}")
        print(f"📞 Twilio webhook URL: http://{host}:{port}/voice")
        print(f"🔄 ConversationRelay WebSocket: wss://{host}:{port}/cr")
        print(f"📝 CI Transcripts webhook: http://{host}:{port}/intelligence/transcripts")
        print(f"📊 Health check: http://{host}:{port}/health")
        print(f"💇‍♀️ Services endpoint: http://{host}:{port}/salon/services")
        print()
        print("🔧 Make sure to configure your Twilio phone number webhook to:")
        print(f"   https://your-domain.com:{port}/voice")
        print("🔧 And configure CI transcript webhook to:")
        print(f"   https://your-domain.com:{port}/intelligence/transcripts")
        
        uvicorn.run(
            "ops_integrations.services.salon_phone_service:app",
            host=host,
            port=port,
            reload=reload,
            log_level="info"
        )
        
    except ImportError as e:
        print(f"❌ Failed to import required modules: {e}")
        print("Make sure you're in the correct directory and dependencies are installed")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Failed to start salon phone service: {e}")
        sys.exit(1)

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Start Bold Wings Salon Phone Service")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--port", type=int, default=5001, help="Port to bind to")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload for development")
    parser.add_argument("--log-level", default="INFO", help="Log level")
    parser.add_argument("--check-only", action="store_true", help="Only check dependencies and exit")
    
    args = parser.parse_args()
    
    # Setup logging
    setup_logging(args.log_level)
    
    print("💇‍♀️ Bold Wings Salon Phone Service Startup")
    print("=" * 45)
    
    # Check dependencies
    print("📋 Checking dependencies...")
    if not check_dependencies():
        sys.exit(1)
    print("✅ All dependencies available")
    
    # Check environment
    print("🔧 Checking environment...")
    check_environment()
    
    # Verify Bold Wings configuration
    print("💄 Checking Bold Wings configuration...")
    if not verify_boldwings_config():
        sys.exit(1)
    
    if args.check_only:
        print("✅ All checks passed!")
        return
    
    # Start the service
    start_salon_phone_service(
        host=args.host,
        port=args.port,
        reload=args.reload
    )

if __name__ == "__main__":
    main()
