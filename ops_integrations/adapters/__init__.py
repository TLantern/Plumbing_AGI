"""
Adapter modules for system integrations and external services.

This module contains adapters for:
- Audio processing and speech recognition
- Intent extraction and conversation management
- Text-to-speech services
- External service integrations (Twilio, Google, etc.)
- CRM and business system integrations
"""

# Core adapters
from . import audio_processor
from . import speech_recognizer
from . import intent_extractor
from . import conversation_manager
from . import tts_manager

# External services
from .external_services import twilio_webhook, google_calendar, sheets, sms

# Integrations
from .integrations import crm, akaunting, inventory, calender

__all__ = [
    # Core adapters
    'audio_processor',
    'speech_recognizer',
    'intent_extractor',
    'conversation_manager',
    'tts_manager',
    
    # External services
    'twilio_webhook',
    'google_calendar',
    'sheets',
    'sms',
    
    # Integrations
    'crm',
    'akaunting',
    'inventory',
    'calender'
] 