"""
Ops Integrations Package

A comprehensive system for managing plumbing service operations including:
- Voice call processing and transcription
- Intent extraction and classification
- Conversation management
- External service integrations
- CRM and booking systems
"""

__version__ = "1.0.0"
__author__ = "Plumbing AGI Team"

# Core modules
from .core import job_booking, contact_capture, inquiry_handler, models

# Services
from .services import phone_service, webhook_server, whisper_service, plumbing_services, local_whisper

# Adapters
from .adapters import (
    audio_processor,
    speech_recognizer,
    intent_extractor,
    conversation_manager,
    tts_manager
)

# External service adapters
from .adapters.external_services import (
    twilio_webhook,
    google_calendar,
    sheets,
    sms
)

# Integration adapters
from .adapters.integrations import (
    crm,
    akaunting
)

# ETL and utilities
from .etl import ops_etl
from .utils import *

__all__ = [
    # Core
    'job_booking',
    'contact_capture', 
    'inquiry_handler',
    'models',
    
    # Services
    'phone_service',
    'webhook_server',
    'whisper_service',
    'plumbing_services',
    'local_whisper',
    
    # Adapters
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
    
    # ETL
    'ops_etl'
] 