#!/usr/bin/env python3
"""
Startup script for Salon Analytics Service
"""

import os
import sys
import logging
import argparse
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

def setup_logging(log_level: str = "INFO"):
    """Set up logging configuration."""
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(project_root / "logs" / "salon_analytics.log")
        ]
    )

def check_dependencies():
    """Check if required dependencies are installed."""
    required_packages = [
        'fastapi',
        'uvicorn',
        'websockets',
        'httpx',
        'sqlite3'  # Built-in, but check availability
    ]
    
    missing_packages = []
    
    for package in required_packages:
        try:
            if package == 'sqlite3':
                import sqlite3
            else:
                __import__(package)
        except ImportError:
            missing_packages.append(package)
    
    if missing_packages:
        print(f"❌ Missing required packages: {', '.join(missing_packages)}")
        print("Install them with: pip install fastapi uvicorn websockets httpx")
        return False
    
    return True

def create_directories():
    """Create necessary directories."""
    directories = [
        project_root / "logs",
        project_root / "data",
        project_root / "data" / "salon"
    ]
    
    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True)
        print(f"✅ Directory created/verified: {directory}")

def start_salon_service(host: str = "0.0.0.0", port: int = 5002, reload: bool = False):
    """Start the salon analytics service."""
    try:
        import uvicorn
        from ops_integrations.services.salon_analytics_service import app
        
        print(f"🚀 Starting Salon Analytics Service on {host}:{port}")
        print(f"📊 Dashboard will be available at: http://localhost:3000/salon-dashboard")
        print(f"🔗 WebSocket endpoint: ws://{host}:{port}/salon")
        print(f"📡 API endpoint: http://{host}:{port}/salon/dashboard")
        
        uvicorn.run(
            "ops_integrations.services.salon_analytics_service:app",
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
        print(f"❌ Failed to start salon service: {e}")
        sys.exit(1)

def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Start Salon Analytics Service")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--port", type=int, default=5002, help="Port to bind to")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload for development")
    parser.add_argument("--log-level", default="INFO", help="Log level (DEBUG, INFO, WARNING, ERROR)")
    parser.add_argument("--check-only", action="store_true", help="Only check dependencies and exit")
    
    args = parser.parse_args()
    
    # Setup logging
    setup_logging(args.log_level)
    
    print("🏪 Salon Analytics Service Startup")
    print("=" * 40)
    
    # Check dependencies
    print("📋 Checking dependencies...")
    if not check_dependencies():
        sys.exit(1)
    print("✅ All dependencies available")
    
    # Create directories
    print("📁 Creating directories...")
    create_directories()
    
    if args.check_only:
        print("✅ All checks passed!")
        return
    
    # Start the service
    start_salon_service(
        host=args.host,
        port=args.port,
        reload=args.reload
    )

if __name__ == "__main__":
    main()
