"""
Database initialization and migration script for salon phone service
"""

import asyncio
import logging
import sys
from datetime import datetime
import json
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from .database import initialize_database, get_db_session
from .models import Location, Agent, Service, BookingStatus, BookingSource, CallStatus

logger = logging.getLogger(__name__)

async def create_default_location() -> int:
    """Create default location for single-location deployments"""
    async with get_db_session() as session:
        # Check if default location exists
        result = await session.execute(select(Location).where(Location.id == 1))
        existing_location = result.scalar_one_or_none()
        
        if existing_location:
            logger.info(f"Default location already exists: {existing_location.name}")
            return existing_location.id
        
        # Create default location
        location = Location(
            id=1,
            name="Bold Wings Salon",
            phone="+1234567890",  # Update with actual phone
            timezone="America/New_York",
            owner_name="Owner Name",
            owner_email="owner@boldwingssalon.com"
        )
        
        session.add(location)
        await session.commit()
        await session.refresh(location)
        
        logger.info(f"Created default location: {location.name}")
        return location.id

async def create_default_agent(location_id: int) -> int:
    """Create default AI agent for a location"""
    async with get_db_session() as session:
        # Check if agent exists
        result = await session.execute(
            select(Agent).where(Agent.location_id == location_id)
        )
        existing_agent = result.scalar_one_or_none()
        
        if existing_agent:
            logger.info(f"Agent already exists for location {location_id}")
            return existing_agent.id
        
        # Default business hours
        business_hours = {
            "monday": "9:00 AM - 6:00 PM",
            "tuesday": "9:00 AM - 6:00 PM", 
            "wednesday": "9:00 AM - 6:00 PM",
            "thursday": "9:00 AM - 8:00 PM",
            "friday": "9:00 AM - 8:00 PM",
            "saturday": "8:00 AM - 5:00 PM",
            "sunday": "Closed"
        }
        
        # Default system prompt
        system_prompt = '''You are a friendly salon assistant for Bold Wings Salon. Your role is to:

1. Greet customers warmly and professionally
2. Answer questions about services, pricing, and availability
3. Help schedule appointments
4. Provide information about our stylists and their specialties
5. Handle frequently asked questions
6. Transfer to human staff when needed

Key guidelines:
- Be conversational and friendly, not robotic
- Keep responses under 50 words when possible
- Always ask follow-up questions to help customers
- Use specific service names and prices when available
- Mention stylist specialties when relevant
- Confirm booking details clearly before scheduling
- If you can't help, offer to connect them with a human'''
        
        agent = Agent(
            location_id=location_id,
            twilio_number="+1234567890",  # Update with actual Twilio number
            voice_id="kdmDKE6EkgrWrrykO9Qt",  # Default ElevenLabs voice
            system_prompt=system_prompt,
            business_hours_json=json.dumps(business_hours)
        )
        
        session.add(agent)
        await session.commit()
        await session.refresh(agent)
        
        logger.info(f"Created default agent for location {location_id}")
        return agent.id

async def create_default_services(location_id: int) -> None:
    """Create default salon services"""
    async with get_db_session() as session:
        # Check if services exist
        result = await session.execute(
            select(Service).where(Service.location_id == location_id)
        )
        existing_services = result.scalars().all()
        
        if existing_services:
            logger.info(f"Services already exist for location {location_id}: {len(existing_services)} services")
            return
        
        # Default salon services
        default_services = [
            {
                "name": "Haircut & Style",
                "duration_min": 60,
                "price_cents": 6500,  # $65.00
                "notes": "Professional haircut with wash, cut, and style"
            },
            {
                "name": "Color & Highlights",
                "duration_min": 120,
                "price_cents": 12000,  # $120.00
                "notes": "Full color service with highlights and toning"
            },
            {
                "name": "Blowout",
                "duration_min": 45,
                "price_cents": 4500,  # $45.00
                "notes": "Professional blow dry and styling"
            },
            {
                "name": "Deep Conditioning Treatment",
                "duration_min": 30,
                "price_cents": 3500,  # $35.00
                "notes": "Nourishing hair treatment for health and shine"
            },
            {
                "name": "Consultation",
                "duration_min": 15,
                "price_cents": 0,  # Free
                "notes": "Complimentary consultation for new services"
            },
            {
                "name": "Wedding/Event Styling",
                "duration_min": 90,
                "price_cents": 15000,  # $150.00
                "notes": "Special occasion hair styling for weddings and events"
            }
        ]
        
        for service_data in default_services:
            service = Service(
                location_id=location_id,
                name=service_data["name"],
                duration_min=service_data["duration_min"],
                price_cents=service_data["price_cents"],
                active_bool=True,
                notes=service_data["notes"]
            )
            session.add(service)
        
        await session.commit()
        logger.info(f"Created {len(default_services)} default services for location {location_id}")

async def initialize_salon_database():
    """Initialize the complete salon database with default data"""
    try:
        # Initialize database connection
        db_manager = initialize_database()
        logger.info("Database connection initialized")
        
        # Create tables
        await db_manager.create_tables()
        logger.info("Database tables created/verified")
        
        # Create default location
        location_id = await create_default_location()
        
        # Create default agent
        agent_id = await create_default_agent(location_id)
        
        # Create default services
        await create_default_services(location_id)
        
        logger.info("✅ Salon database initialization completed successfully")
        logger.info(f"Default location ID: {location_id}")
        logger.info(f"Default agent ID: {agent_id}")
        
        return {
            "status": "success",
            "location_id": location_id,
            "agent_id": agent_id,
            "message": "Database initialized with default salon data"
        }
        
    except Exception as e:
        logger.error(f"❌ Database initialization failed: {e}")
        raise

async def migrate_existing_data():
    """Migrate data from existing SQLite databases if they exist"""
    import os
    
    # Check for existing salon databases
    existing_dbs = [
        "salon_crm.db",
        "hairstyling_analytics.db",
        "../../salon_crm.db"  # Check project root
    ]
    
    for db_path in existing_dbs:
        if os.path.exists(db_path):
            logger.info(f"Found existing database: {db_path}")
            # TODO: Implement migration logic if needed
            # For now, we'll start fresh with the new schema
    
    logger.info("Migration check completed")

if __name__ == "__main__":
    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    async def main():
        try:
            await migrate_existing_data()
            result = await initialize_salon_database()
            print(f"✅ Success: {result['message']}")
            print(f"Location ID: {result['location_id']}")
            print(f"Agent ID: {result['agent_id']}")
        except Exception as e:
            print(f"❌ Error: {e}")
            sys.exit(1)
    
    # Run the initialization
    asyncio.run(main())
