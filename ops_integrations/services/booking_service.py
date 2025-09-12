"""
Booking and job confirmation service for salon phone system
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Tuple
from sqlalchemy.ext.asyncio import AsyncSession  # type: ignore
from sqlalchemy import select, and_  # type: ignore
from .models import Location, Agent, Service, Booking, Call, BookingStatus, BookingSource
from .database import get_db_session

logger = logging.getLogger(__name__)

class BookingService:
    def __init__(self):
        self.confirmation_keywords = [
            "yes", "yeah", "yep", "sure", "okay", "ok", "confirm", "book it", 
            "schedule it", "that works", "sounds good", "perfect", "great"
        ]
        self.cancellation_keywords = [
            "no", "nah", "nope", "cancel", "nevermind", "never mind", "not now",
            "maybe later", "let me think", "not today"
        ]
    
    async def extract_booking_intent(self, text: str, call_sid: str) -> Dict[str, Any]:
        """Extract booking intent from conversation text"""
        text_lower = text.lower().strip()
        
        # Check for confirmation keywords
        is_confirmation = any(keyword in text_lower for keyword in self.confirmation_keywords)
        is_cancellation = any(keyword in text_lower for keyword in self.cancellation_keywords)
        
        # Extract service mentions
        service_keywords = {
            "haircut": ["haircut", "cut", "trim", "hair cut"],
            "color": ["color", "dye", "highlights", "lowlights", "coloring"],
            "styling": ["style", "styling", "blowout", "blow out", "updo"],
            "treatment": ["treatment", "deep condition", "keratin", "protein"],
            "perm": ["perm", "permanent", "wave", "curls"],
            "consultation": ["consultation", "consult", "advice", "look at"]
        }
        
        detected_services = []
        for service_type, keywords in service_keywords.items():
            if any(keyword in text_lower for keyword in keywords):
                detected_services.append(service_type)
        
        # Extract time preferences
        time_keywords = {
            "morning": ["morning", "am", "early"],
            "afternoon": ["afternoon", "pm", "lunch"],
            "evening": ["evening", "night", "late"],
            "today": ["today", "now", "asap"],
            "tomorrow": ["tomorrow"],
            "this_week": ["this week", "soon", "quick"]
        }
        
        time_preferences = []
        for time_period, keywords in time_keywords.items():
            if any(keyword in text_lower for keyword in keywords):
                time_preferences.append(time_period)
        
        return {
            "is_confirmation": is_confirmation,
            "is_cancellation": is_cancellation,
            "detected_services": detected_services,
            "time_preferences": time_preferences,
            "has_booking_intent": bool(detected_services) or is_confirmation,
            "call_sid": call_sid,
            "raw_text": text
        }
    
    async def should_confirm_booking(self, conversation_context: List[str], latest_text: str) -> bool:
        """Determine if the AI should ask for booking confirmation"""
        
        # Analyze conversation history for booking signals
        full_conversation = " ".join(conversation_context + [latest_text]).lower()
        
        # Check if we've already asked for confirmation recently
        recent_confirmation_asked = any(
            "would you like me to" in msg.lower() or "shall i book" in msg.lower() 
            for msg in conversation_context[-3:]  # Last 3 exchanges
        )
        
        if recent_confirmation_asked:
            return False
        
        # Look for strong booking indicators
        booking_indicators = [
            "book", "schedule", "appointment", "when can", "available", 
            "next week", "tomorrow", "today", "time slot", "open"
        ]
        
        service_mentions = [
            "haircut", "color", "highlights", "styling", "treatment", 
            "perm", "consultation", "trim"
        ]
        
        has_booking_intent = any(indicator in full_conversation for indicator in booking_indicators)
        has_service_mention = any(service in full_conversation for service in service_mentions)
        
        # Confirm if they mentioned both service and scheduling intent
        return has_booking_intent and has_service_mention
    
    async def get_available_services(self, location_id: int) -> List[Dict[str, Any]]:
        """Get available services for a location"""
        async with get_db_session() as session:
            result = await session.execute(
                select(Service).where(
                    and_(Service.location_id == location_id, Service.active_bool == True)
                )
            )
            services = result.scalars().all()
            
            return [
                {
                    "id": service.id,
                    "name": service.name,
                    "duration_min": service.duration_min,
                    "price_cents": service.price_cents,
                    "price_display": f"${service.price_cents / 100:.2f}"
                }
                for service in services
            ]
    
    async def create_pending_booking(
        self, 
        location_id: int,
        service_name: str,
        customer_name: str,
        customer_phone: str,
        call_sid: str,
        preferred_time: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Create a pending booking that requires confirmation"""
        
        async with get_db_session() as session:
            # Find the service
            result = await session.execute(
                select(Service).where(
                    and_(
                        Service.location_id == location_id,
                        Service.name.ilike(f"%{service_name}%"),
                        Service.active_bool == True
                    )
                )
            )
            service = result.scalar_one_or_none()
            
            if not service:
                logger.warning(f"Service '{service_name}' not found for location {location_id}")
                return None
            
            # Find the associated call
            call_result = await session.execute(
                select(Call).where(Call.call_sid == call_sid)
            )
            call = call_result.scalar_one_or_none()
            
            # Calculate booking time (default to next business day at 10 AM)
            start_time = datetime.now() + timedelta(days=1)
            start_time = start_time.replace(hour=10, minute=0, second=0, microsecond=0)
            end_time = start_time + timedelta(minutes=service.duration_min)
            
            # Create pending booking
            booking = Booking(
                location_id=location_id,
                service_id=service.id,
                start_at=start_time,
                end_at=end_time,
                status=BookingStatus.PENDING,
                customer_name=customer_name,
                customer_phone=customer_phone,
                source=BookingSource.AI_CALL,
                call_id=call.id if call else None,
                price_cents_snapshot=service.price_cents,
                notes=f"Auto-created from call. Preferred time: {preferred_time or 'Not specified'}"
            )
            
            session.add(booking)
            await session.commit()
            await session.refresh(booking)
            
            logger.info(f"Created pending booking {booking.id} for {customer_name}")
            
            return {
                "booking_id": booking.id,
                "service_name": service.name,
                "duration_min": service.duration_min,
                "price_display": f"${service.price_cents / 100:.2f}",
                "start_time": start_time.strftime("%A, %B %d at %I:%M %p"),
                "customer_name": customer_name
            }
    
    async def confirm_booking(self, booking_id: int) -> bool:
        """Confirm a pending booking"""
        async with get_db_session() as session:
            result = await session.execute(
                select(Booking).where(Booking.id == booking_id)
            )
            booking = result.scalar_one_or_none()
            
            if booking and booking.status == BookingStatus.PENDING:
                booking.status = BookingStatus.CONFIRMED
                await session.commit()
                logger.info(f"Confirmed booking {booking_id}")
                return True
            
            return False
    
    async def cancel_booking(self, booking_id: int) -> bool:
        """Cancel a pending booking"""
        async with get_db_session() as session:
            result = await session.execute(
                select(Booking).where(Booking.id == booking_id)
            )
            booking = result.scalar_one_or_none()
            
            if booking and booking.status == BookingStatus.PENDING:
                booking.status = BookingStatus.CANCELED
                await session.commit()
                logger.info(f"Canceled booking {booking_id}")
                return True
            
            return False

# Global booking service instance
booking_service = BookingService()
