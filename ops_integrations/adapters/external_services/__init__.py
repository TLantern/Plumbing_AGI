"""
External service adapters for third-party integrations.

This module contains adapters for:
- Twilio webhook handling
- Google Calendar integration
- Google Sheets integration
- SMS messaging services
"""

from . import twilio_webhook
from . import google_calendar
from . import sheets
from . import sms

__all__ = [
    'twilio_webhook',
    'google_calendar',
    'sheets',
    'sms'
] 