"""
Service layer modules for external integrations and core services.

This module contains service implementations for:
- Phone call processing and voice services
- Webhook handling and server management
- Whisper transcription services
- Plumbing service management
- Local whisper processing
"""

from . import phone_service
from . import webhook_server
from . import whisper_service
from . import plumbing_services
from . import local_whisper

__all__ = [
    'phone_service',
    'webhook_server',
    'whisper_service',
    'plumbing_services',
    'local_whisper'
] 