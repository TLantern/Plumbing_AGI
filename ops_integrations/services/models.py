"""
Database models for the salon phone service with multi-location support
"""

from datetime import datetime
from enum import Enum
from typing import Optional
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey, Enum as SQLEnum, DECIMAL
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

Base = declarative_base()

class BookingStatus(str, Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed" 
    CANCELED = "canceled"
    NO_SHOW = "no_show"
    COMPLETED = "completed"

class BookingSource(str, Enum):
    AI_CALL = "ai_call"
    WEB = "web"
    MANUAL = "manual"
    CALENDLY = "calendly"

class CallStatus(str, Enum):
    ANSWERED = "answered"
    MISSED = "missed"
    VOICEMAIL = "voicemail"
    CONVERTED = "converted"

class Location(Base):
    __tablename__ = "locations"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    phone = Column(String(20), nullable=False)
    timezone = Column(String(50), nullable=False, default="America/New_York")
    owner_name = Column(String(255), nullable=False)
    owner_email = Column(String(255), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    agents = relationship("Agent", back_populates="location")
    services = relationship("Service", back_populates="location")
    bookings = relationship("Booking", back_populates="location")
    calls = relationship("Call", back_populates="location")

class Agent(Base):
    __tablename__ = "agents"
    
    id = Column(Integer, primary_key=True, index=True)
    location_id = Column(Integer, ForeignKey("locations.id"), nullable=False)
    twilio_number = Column(String(20), nullable=False)
    voice_id = Column(String(50), nullable=False, default="kdmDKE6EkgrWrrykO9Qt")
    system_prompt = Column(Text, nullable=False)
    business_hours_json = Column(Text, nullable=False)  # JSON string with business hours
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    location = relationship("Location", back_populates="agents")

class Service(Base):
    __tablename__ = "services"
    
    id = Column(Integer, primary_key=True, index=True)
    location_id = Column(Integer, ForeignKey("locations.id"), nullable=False)
    name = Column(String(255), nullable=False)
    duration_min = Column(Integer, nullable=False)
    price_cents = Column(Integer, nullable=False)
    active_bool = Column(Boolean, nullable=False, default=True)
    notes = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    location = relationship("Location", back_populates="services")
    bookings = relationship("Booking", back_populates="service")

class Booking(Base):
    __tablename__ = "bookings"
    
    id = Column(Integer, primary_key=True, index=True)
    location_id = Column(Integer, ForeignKey("locations.id"), nullable=False)
    service_id = Column(Integer, ForeignKey("services.id"), nullable=False)
    start_at = Column(DateTime(timezone=True), nullable=False)
    end_at = Column(DateTime(timezone=True), nullable=False)
    status = Column(SQLEnum(BookingStatus), nullable=False, default=BookingStatus.PENDING)
    customer_name = Column(String(255), nullable=False)
    customer_phone = Column(String(20), nullable=False)
    source = Column(SQLEnum(BookingSource), nullable=False, default=BookingSource.AI_CALL)
    call_id = Column(Integer, ForeignKey("calls.id"), nullable=True)
    price_cents_snapshot = Column(Integer, nullable=False)
    notes = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    location = relationship("Location", back_populates="bookings")
    service = relationship("Service", back_populates="bookings")
    call = relationship("Call", back_populates="booking")

class Call(Base):
    __tablename__ = "calls"
    
    id = Column(Integer, primary_key=True, index=True)
    location_id = Column(Integer, ForeignKey("locations.id"), nullable=False)
    call_sid = Column(String(255), unique=True, nullable=False)
    started_at = Column(DateTime(timezone=True), nullable=False)
    ended_at = Column(DateTime(timezone=True), nullable=True)
    duration_sec = Column(Integer, nullable=True)
    status = Column(SQLEnum(CallStatus), nullable=False, default=CallStatus.ANSWERED)
    transcript_url = Column(String(500), nullable=True)
    recording_url = Column(String(500), nullable=True)
    booking_id = Column(Integer, ForeignKey("bookings.id"), nullable=True)
    customer_phone = Column(String(20), nullable=False)
    customer_name = Column(String(255), nullable=True)
    intent_extracted = Column(Text, nullable=True)
    conversation_summary = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    location = relationship("Location", back_populates="calls")
    booking = relationship("Booking", back_populates="call", uselist=False)
