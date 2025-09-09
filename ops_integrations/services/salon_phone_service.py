"""
Salon Phone Service - Bold Wings Hair Salon
Compressed phone service for salon appointments with Bold Wings service patterns
"""

import asyncio
import base64
import json
import logging
import random
import re
import time
import struct
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from collections import defaultdict, deque

from fastapi import FastAPI, WebSocket, Request, BackgroundTasks, HTTPException, WebSocketDisconnect
from fastapi.responses import Response
from fastapi.middleware.cors import CORSMiddleware
from twilio.twiml.voice_response import VoiceResponse, Start
from twilio.rest import Client
from openai import OpenAI
from pydantic_settings import BaseSettings

# Import webrtcvad for Voice Activity Detection
try:
    import webrtcvad  # type: ignore
except Exception:
    class _DummyVAD:
        def __init__(self, aggressiveness: int):
            pass
        def is_speech(self, frame_bytes: bytes, sample_rate: int) -> bool:
            return False
    class _webrtcvad_module:  # minimal shim for interface
        Vad = _DummyVAD
    webrtcvad = _webrtcvad_module()  # type: ignore

# Try to import audioop for mu-law decoding and resampling; may be missing on some Python versions
try:
    import audioop as _audioop  # type: ignore
except Exception:
    _audioop = None

# Import additional audio processing modules
import io
import wave

# Import salon integration
try:
    from ops_integrations.core.salon_response_generator import salon_response_generator
except ImportError:
    salon_response_generator = None

# Import Google Sheets integration
try:
    from ops_integrations.adapters.external_services.sheets import GoogleSheetsCRM
    # Set test sheet name for development
    import os
    os.environ.setdefault("SHEETS_BOOKINGS_TAB_NAME", "test")
    sheets_crm = GoogleSheetsCRM()
    logging.info(f"📊 Google Sheets CRM initialized: enabled={sheets_crm.enabled}, spreadsheet_id={sheets_crm.spreadsheet_id}, tab_name={sheets_crm.tab_name}")
except ImportError as e:
    sheets_crm = None
    logging.error(f"Failed to import GoogleSheetsCRM: {e}")

# Set salon_phone_integration to None since it's not needed
salon_phone_integration = None

# Simple CRM replacement since hairstyling_crm was deleted
class HairstylingCRM:
    """Comprehensive CRM for Bold Wings Hair Salon"""
    
    def __init__(self):
        self.db_path = "./salon_crm.db"
        self.current_week_metrics = {
            'total_calls': 0,
            'answered_calls': 0,
            'missed_calls': 0,
            'calls_dropped': 0,
            'after_hour_calls': 0,
            'total_appointments': 0,
            'completed_appointments': 0,
            'no_shows': 0,
            'cancellations': 0,
            'total_revenue': 0.0,
            'average_revenue_per_appointment': 0.0
        }
        
        # Business hours configuration (per day)
        self.business_hours = {
            0: {'start': 7, 'end': 23},   # Monday: 7 AM – 11 PM
            1: {'start': 7, 'end': 23},   # Tuesday: 7 AM – 11 PM
            2: {'start': 7, 'end': 23},   # Wednesday: 7 AM – 11 PM
            3: {'start': 7, 'end': 23},   # Thursday: 7 AM – 11 PM
            4: {'start': 19, 'end': 23},  # Friday: 7 PM – 11 PM
            5: {'start': 19, 'end': 23},  # Saturday: 7 PM – 11 PM
            6: None                       # Sunday: Closed
        }
        
        # Customer storage
        self.customers = {}
        self.appointments = {}
        self.calls = {}
        
        # Initialize database
        self._init_database()
    
    def _init_database(self):
        """Initialize SQLite database for persistent storage"""
        import sqlite3
        import os
        
        # Create data directory if it doesn't exist (only if path has directory)
        db_dir = os.path.dirname(self.db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Create customers table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS customers (
                id INTEGER PRIMARY KEY,
                phone_number TEXT UNIQUE,
                name TEXT,
                email TEXT,
                first_contact_date TEXT,
                last_contact_date TEXT,
                total_appointments INTEGER DEFAULT 0,
                total_spent REAL DEFAULT 0.0,
                status TEXT DEFAULT 'New',
                notes TEXT
            )
        ''')
        
        # Create appointments table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS appointments (
                id INTEGER PRIMARY KEY,
                customer_id INTEGER,
                service_type TEXT,
                appointment_date TEXT,
                price REAL,
                status TEXT DEFAULT 'Scheduled',
                call_sid TEXT,
                notes TEXT,
                created_at TEXT,
                FOREIGN KEY (customer_id) REFERENCES customers (id)
            )
        ''')
        
        # Create calls table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS calls (
                id INTEGER PRIMARY KEY,
                call_sid TEXT UNIQUE,
                customer_phone TEXT,
                customer_name TEXT,
                call_date TEXT,
                duration_seconds INTEGER,
                status TEXT,
                intent_extracted TEXT,
                is_after_hours BOOLEAN,
                notes TEXT
            )
        ''')
        
        # Create weekly_metrics table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS weekly_metrics (
                id INTEGER PRIMARY KEY,
                week_start_date TEXT,
                total_calls INTEGER,
                answered_calls INTEGER,
                missed_calls INTEGER,
                calls_dropped INTEGER,
                after_hour_calls INTEGER,
                total_appointments INTEGER,
                completed_appointments INTEGER,
                no_shows INTEGER,
                cancellations INTEGER,
                total_revenue REAL,
                average_revenue_per_appointment REAL
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def _is_business_hours(self, timestamp: datetime) -> bool:
        """Check if timestamp falls within business hours"""
        weekday = timestamp.weekday()
        if self.business_hours[weekday] is None:
            return False  # Closed on this day
        
        hour = timestamp.hour
        start_hour = self.business_hours[weekday]['start']
        end_hour = self.business_hours[weekday]['end']
        
        return start_hour <= hour < end_hour
    
    def _find_or_create_customer(self, phone_number: str, name: str = None) -> int:
        """Find existing customer or create new one"""
        import sqlite3
        import hashlib
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Try to find existing customer
        cursor.execute('SELECT id FROM customers WHERE phone_number = ?', (phone_number,))
        result = cursor.fetchone()
        
        if result:
            customer_id = result[0]
            # Update last contact date
            cursor.execute('''
                UPDATE customers 
                SET last_contact_date = ?, name = COALESCE(?, name)
                WHERE id = ?
            ''', (datetime.now().isoformat(), name, customer_id))
        else:
            # Create new customer
            cursor.execute('''
                INSERT INTO customers (phone_number, name, first_contact_date, last_contact_date)
                VALUES (?, ?, ?, ?)
            ''', (phone_number, name, datetime.now().isoformat(), datetime.now().isoformat()))
            customer_id = cursor.lastrowid
        
        conn.commit()
        conn.close()
        return customer_id
    
    def track_call(self, call_data: Dict[str, Any]) -> Dict[str, Any]:
        """Track a phone call"""
        import sqlite3
        
        call_sid = call_data.get('call_sid')
        customer_phone = call_data.get('customer_phone')
        customer_name = call_data.get('customer_name')
        duration_seconds = call_data.get('duration_seconds', 0)
        status = call_data.get('status', 'completed')
        intent_extracted = call_data.get('intent_extracted')
        
        # Check if after hours
        call_time = datetime.now()
        is_after_hours = not self._is_business_hours(call_time)
        
        # Update metrics
        self.current_week_metrics['total_calls'] += 1
        if status == 'completed':
            self.current_week_metrics['answered_calls'] += 1
        elif status == 'missed':
            self.current_week_metrics['missed_calls'] += 1
        elif status == 'dropped':
            self.current_week_metrics['calls_dropped'] += 1
        
        if is_after_hours:
            self.current_week_metrics['after_hour_calls'] += 1
        
        # Save to database
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO calls 
            (call_sid, customer_phone, customer_name, call_date, duration_seconds, status, intent_extracted, is_after_hours)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (call_sid, customer_phone, customer_name, call_time.isoformat(), 
              duration_seconds, status, intent_extracted, is_after_hours))
        
        conn.commit()
        conn.close()
        
        return {
            'success': True,
            'call_id': cursor.lastrowid,
            'is_after_hours': is_after_hours,
            'metrics_updated': True
        }
    
    def schedule_appointment(self, appointment_data: Dict[str, Any]) -> Dict[str, Any]:
        """Schedule a new appointment"""
        import sqlite3
        
        customer_phone = appointment_data.get('customer_phone')
        customer_name = appointment_data.get('customer_name')
        service_type = appointment_data.get('service_type')
        appointment_date = appointment_data.get('appointment_date')
        price = appointment_data.get('price', 0.0)
        call_sid = appointment_data.get('call_sid')
        notes = appointment_data.get('notes', '')
        
        # Find or create customer
        customer_id = self._find_or_create_customer(customer_phone, customer_name)
        
        # Update metrics
        self.current_week_metrics['total_appointments'] += 1
        self.current_week_metrics['total_revenue'] += price
        
        # Calculate average revenue
        if self.current_week_metrics['total_appointments'] > 0:
            self.current_week_metrics['average_revenue_per_appointment'] = (
                self.current_week_metrics['total_revenue'] / 
                self.current_week_metrics['total_appointments']
            )
        
        # Save to database
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO appointments 
            (customer_id, service_type, appointment_date, price, call_sid, notes, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (customer_id, service_type, appointment_date, price, call_sid, notes, datetime.now().isoformat()))
        
        appointment_id = cursor.lastrowid
        
        # Update customer appointment count
        cursor.execute('''
            UPDATE customers 
            SET total_appointments = total_appointments + 1,
                total_spent = total_spent + ?
            WHERE id = ?
        ''', (price, customer_id))
        
        conn.commit()
        conn.close()
        
        return {
            'success': True,
            'appointment_id': appointment_id,
            'customer_id': customer_id,
            'metrics_updated': True
        }
    
    def update_appointment_status(self, appointment_id: int, status: str, actual_price: float = None) -> Dict[str, Any]:
        """Update appointment status (completed, no-show, cancelled)"""
        import sqlite3
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Get current appointment data
        cursor.execute('SELECT customer_id, price, status FROM appointments WHERE id = ?', (appointment_id,))
        result = cursor.fetchone()
        
        if not result:
            conn.close()
            return {'success': False, 'error': 'Appointment not found'}
        
        customer_id, original_price, current_status = result
        price = actual_price if actual_price is not None else original_price
        
        # Update appointment
        cursor.execute('''
            UPDATE appointments 
            SET status = ?, price = ?
            WHERE id = ?
        ''', (status, price, appointment_id))
        
        # Update metrics based on status change
        if current_status == 'Scheduled':
            if status == 'Completed':
                self.current_week_metrics['completed_appointments'] += 1
            elif status == 'No Show':
                self.current_week_metrics['no_shows'] += 1
            elif status == 'Cancelled':
                self.current_week_metrics['cancellations'] += 1
                self.current_week_metrics['total_appointments'] -= 1
                self.current_week_metrics['total_revenue'] -= original_price
        
        conn.commit()
        conn.close()
        
        return {'success': True, 'status_updated': True}
    
    def get_dashboard_data(self) -> Dict[str, Any]:
        """Get comprehensive dashboard data"""
        import sqlite3
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Get recent calls
        cursor.execute('''
            SELECT call_sid, customer_name, call_date, status, duration_seconds, intent_extracted
            FROM calls 
            ORDER BY call_date DESC 
            LIMIT 10
        ''')
        recent_calls = [{
            'call_sid': row[0],
            'customer_name': row[1],
            'call_date': row[2],
            'status': row[3],
            'duration_seconds': row[4],
            'intent_extracted': row[5]
        } for row in cursor.fetchall()]
        
        # Get active appointments
        cursor.execute('''
            SELECT a.id, c.name, a.service_type, a.appointment_date, a.price, a.status
            FROM appointments a
            JOIN customers c ON a.customer_id = c.id
            WHERE a.status = 'Scheduled'
            ORDER BY a.appointment_date
            LIMIT 10
        ''')
        active_appointments = [{
            'id': row[0],
            'customer_name': row[1],
            'service_type': row[2],
            'appointment_date': row[3],
            'price': row[4],
            'status': row[5]
        } for row in cursor.fetchall()]
        
        conn.close()
        
        return {
            'current_week': self.current_week_metrics,
            'active_calls': len([c for c in recent_calls if c['status'] == 'completed']),
            'recent_calls': recent_calls,
            'active_appointments': active_appointments,
            'growth_insights': self._generate_growth_insights(),
            'timestamp': datetime.now().isoformat()
        }
    
    def _generate_growth_insights(self) -> Dict[str, Any]:
        """Generate business insights and recommendations"""
        insights = []
        recommendations = []
        
        # Analyze call metrics
        if self.current_week_metrics['total_calls'] > 0:
            answer_rate = (self.current_week_metrics['answered_calls'] / 
                          self.current_week_metrics['total_calls']) * 100
            
            if answer_rate < 80:
                insights.append(f"Call answer rate is {answer_rate:.1f}% - consider improving availability")
                recommendations.append("Extend business hours or add more staff during peak times")
            
            if self.current_week_metrics['after_hour_calls'] > 0:
                insights.append(f"{self.current_week_metrics['after_hour_calls']} after-hours calls received")
                recommendations.append("Consider offering evening appointments to capture after-hours demand")
        
        # Analyze appointment metrics
        if self.current_week_metrics['total_appointments'] > 0:
            completion_rate = (self.current_week_metrics['completed_appointments'] / 
                             self.current_week_metrics['total_appointments']) * 100
            
            if completion_rate < 90:
                insights.append(f"Appointment completion rate is {completion_rate:.1f}%")
                recommendations.append("Implement appointment reminders and confirmation calls")
            
            if self.current_week_metrics['no_shows'] > 0:
                insights.append(f"{self.current_week_metrics['no_shows']} no-shows this week")
                recommendations.append("Consider requiring deposits for appointments")
        
        # Revenue insights
        if self.current_week_metrics['average_revenue_per_appointment'] > 0:
            insights.append(f"Average revenue per appointment: ${self.current_week_metrics['average_revenue_per_appointment']:.2f}")
            
            if self.current_week_metrics['average_revenue_per_appointment'] < 75:
                recommendations.append("Consider upselling additional services to increase average ticket")
        
        return {
            'revenue_growth_4_week': 0,  # Would need historical data
            'insights': insights,
            'recommendations': recommendations
        }
    
    def save_weekly_metrics(self):
        """Save current week metrics to database for historical tracking"""
        import sqlite3
        
        # Calculate week start date (Monday)
        today = datetime.now()
        days_since_monday = today.weekday()
        week_start = today - timedelta(days=days_since_monday)
        week_start_date = week_start.strftime('%Y-%m-%d')
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO weekly_metrics 
            (week_start_date, total_calls, answered_calls, missed_calls, calls_dropped,
             after_hour_calls, total_appointments, completed_appointments, no_shows,
             cancellations, total_revenue, average_revenue_per_appointment)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            week_start_date,
            self.current_week_metrics['total_calls'],
            self.current_week_metrics['answered_calls'],
            self.current_week_metrics['missed_calls'],
            self.current_week_metrics['calls_dropped'],
            self.current_week_metrics['after_hour_calls'],
            self.current_week_metrics['total_appointments'],
            self.current_week_metrics['completed_appointments'],
            self.current_week_metrics['no_shows'],
            self.current_week_metrics['cancellations'],
            self.current_week_metrics['total_revenue'],
            self.current_week_metrics['average_revenue_per_appointment']
        ))
        
        conn.commit()
        conn.close()

class Settings(BaseSettings):
    """Settings with same constants as original phone service"""
    # Twilio
    TWILIO_ACCOUNT_SID: str = ""
    TWILIO_AUTH_TOKEN: str = ""
    TWILIO_PHONE_NUMBER: str = ""  # Will fall back to TWILIO_FROM_NUMBER
    
    # OpenAI
    OPENAI_API_KEY: str = "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"
    
    # ElevenLabs TTS - DISABLED
    ELEVENLABS_API_KEY: str = ""  # Disabled - using OpenAI TTS instead
    ELEVENLABS_VOICE_ID: str = "kdmDKE6EkgrWrrykO9Qt"  # User's preferred voice
    ELEVENLABS_MODEL_ID: str = "eleven_multilingual_v2"
    
    # Remote Whisper Service
    REMOTE_WHISPER_URL: str = "web-production-282ff.up.railway.app"  # Railway Whisper v3 service
    
    # Service endpoints
    VOICE_ENDPOINT: str = "/voice"
    STREAM_ENDPOINT: str = "/stream"  # Align with phone.py
    MEDIA_ENDPOINT: str = "/media"  # Deprecated, use STREAM_ENDPOINT
    EXTERNAL_WEBHOOK_URL: str = "https://39753b74ee49.ngrok-free.app"
    # OpenAI TTS Configuration
    OPENAI_TTS_SPEED: float = 1.25
    SPEECH_GATE_BUFFER_SEC: float = 1.0
    
    # Confidence Thresholds (same as phone.py)
    TRANSCRIPTION_CONFIDENCE_THRESHOLD: float = -0.7  # Optimized based on 99.75% accuracy test
    INTENT_CONFIDENCE_THRESHOLD: float = 0.5  # Higher intent confidence requirement
    OVERALL_CONFIDENCE_THRESHOLD: float = 0.6  # Higher overall confidence requirement
    CONFIDENCE_DEBUG_MODE: bool = True  # Enable detailed confidence logging
    
    # Consecutive Failure Thresholds
    CONSECUTIVE_INTENT_FAILURES_THRESHOLD: int = 2  # Number of consecutive intent confidence failures before handoff
    CONSECUTIVE_OVERALL_FAILURES_THRESHOLD: int = 2  # Number of consecutive overall confidence failures before handoff
    
    # Missing fields thresholds
    MISSING_FIELDS_PER_TURN_THRESHOLD: int = 2  # Number of critical fields missing in a single turn to count as a failure
    CONSECUTIVE_MISSING_FIELDS_FAILURES_THRESHOLD: int = 2  # Consecutive turns with missing fields before handoff
    
    # Other settings
    LOG_LEVEL: str = "INFO"
    DISPATCH_NUMBER: str = "+14693096560"

settings = Settings()

# Load Bold Wings services and names
import os

# Fallback to TWILIO_FROM_NUMBER if TWILIO_PHONE_NUMBER is not set
if not settings.TWILIO_PHONE_NUMBER:
    settings.TWILIO_PHONE_NUMBER = os.getenv("TWILIO_FROM_NUMBER", "")
# Pick up EXTERNAL_WEBHOOK_URL from environment if provided
settings.EXTERNAL_WEBHOOK_URL = os.getenv("EXTERNAL_WEBHOOK_URL", settings.EXTERNAL_WEBHOOK_URL)
SALON_SERVICES_PATH = os.path.join(os.path.dirname(__file__), '..', 'config', 'boldwings.json')
SALON_NAMES_PATH = os.path.join(os.path.dirname(__file__), '..', 'config', 'boldwings_name.json')

try:
    with open(SALON_SERVICES_PATH, 'r') as f:
        SALON_SERVICES = json.load(f)
except (FileNotFoundError, json.JSONDecodeError) as e:
    logging.warning(f"Could not load Bold Wings services: {e}")
    SALON_SERVICES = {"services": {}, "currency": "CAD"}

try:
    with open(SALON_NAMES_PATH, 'r') as f:
        SALON_NAMES = json.load(f)
        NIGERIAN_NAMES = set(name.lower() for name in SALON_NAMES.get('nigerian_names', []))
except (FileNotFoundError, json.JSONDecodeError) as e:
    logging.warning(f"Could not load Bold Wings names: {e}")
    NIGERIAN_NAMES = set()

# Initialize clients
openai_client = OpenAI(api_key=settings.OPENAI_API_KEY) if settings.OPENAI_API_KEY else None
twilio_client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN) if settings.TWILIO_ACCOUNT_SID else None

# Initialize speech recognition and intent extraction
try:
    from ..adapters.speech_recognizer import SpeechRecognizer
    from ..adapters.intent_extractor import IntentExtractor
    whisper_url = settings.REMOTE_WHISPER_URL if settings.REMOTE_WHISPER_URL else None
    speech_recognizer = SpeechRecognizer(settings.OPENAI_API_KEY, whisper_url=whisper_url) if (settings.OPENAI_API_KEY or whisper_url) else None
    intent_extractor = IntentExtractor(settings.OPENAI_API_KEY) if settings.OPENAI_API_KEY else None
    if whisper_url:
        logging.info(f"✅ Speech recognition initialized with remote Whisper: {whisper_url}")
    else:
        logging.info("✅ Speech recognition initialized with OpenAI Whisper")
except ImportError as e:
    speech_recognizer = None
    intent_extractor = None
    logging.warning(f"⚠️ Speech recognition/intent extraction not available: {e}")

# FastAPI app
app = FastAPI(title="Bold Wings Salon Phone Service")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

#---------------AUDIO PROCESSING CONFIGURATION---------------
# VAD Configuration - Tuned for Better Quality (same as phone.py)
VAD_AGGRESSIVENESS = 2  # Most sensitive = catch all speech including quiet/background
VAD_FRAME_DURATION_MS = 20  # 20ms = optimal for speech detection accuracy
SILENCE_TIMEOUT_SEC = 2.0  # Longer timeout to catch natural speech pauses
PROBLEM_DETAILS_SILENCE_TIMEOUT_SEC = 3.0  # Longer timeout specifically for problem details phase
MIN_SPEECH_DURATION_SEC = 0.5  # Very short to catch quick responses
CHUNK_DURATION_SEC = 4.0  # Regular chunk duration for normal conversations
PROBLEM_DETAILS_CHUNK_DURATION_SEC = 15.0  # Extended chunk duration specifically for problem details phase
PREROLL_IGNORE_SEC = 0.05  # Start listening almost immediately
MIN_START_RMS = 90  # Much more sensitive to quiet speech
FAST_RESPONSE_MODE = False  # Disabled for better quality over speed

# Audio format defaults for Twilio Media Streams (mu-law 8k)
SAMPLE_RATE_DEFAULT = 8000
SAMPLE_WIDTH = 2 #bytes (16-bit)

# buffer incoming PCM16 per call and track VAD state
audio_buffers = defaultdict(bytearray)
vad_states = defaultdict(lambda: {
    'is_speaking': False,
    'last_speech_time': 0,
    'speech_start_time': 0,
    'pending_audio': bytearray(),
    'vad': webrtcvad.Vad(VAD_AGGRESSIVENESS),
    'fallback_buffer': bytearray(),
    'last_chunk_time': 0,
    'has_received_media': False,
    'last_listen_log_time': 0.0,
    'bot_speaking': False,  # Track when bot is outputting TTS
    'bot_speech_start_time': 0,  # When bot started speaking
    'speech_gate_active': False,  # Gate to block user speech processing
    'processing_lock': False,  # Prevent multiple simultaneous processing
    'permanent_gate_active': False,  # Track permanent gate state
    'active_gate_timer': None,  # Track active speech gate timer task
})

# Per-call media format (encoding and sample rate)
audio_config_store = defaultdict(lambda: {
    'encoding': 'mulaw',      # 'mulaw' or 'pcm16'
    'sample_rate': SAMPLE_RATE_DEFAULT
})

# Add a simple in-memory dialog state store
call_dialog_state = {}

# Track processed speech segments to avoid duplicates
processed_speech_segments = set()

# Track conversation flow state
conversation_state = defaultdict(lambda: {
    'step': 'greeting',  # greeting, awaiting_name, awaiting_service, questions_about_service, scheduling, confirmation
    'customer_name': None,
    'service_intent': None,
    'attempts': 0,
    'service_attempts': 0,  # Track failed service extraction attempts
    'last_response': None,
    'service_questions_asked': False,
    'awaiting_transfer_decision': False  # Track if we're waiting for yes/no on transfer
})

# Store speech audio for processing
speech_audio_store: dict[str, bytes] = {}

# Track if we should stop listening after first speech
stop_listening_after_first = defaultdict(bool)

# Store call information when calls start
call_info_store = {}

# Track call metrics for enhanced Google Sheets reporting
call_metrics_store = defaultdict(lambda: {
    'call_start_time': 0,
    'first_speech_time': 0,
    'first_response_time': 0,
    'call_end_time': 0,
    'service_price': 0.0,
    'appointment_scheduled': False,
    'response_speed': 0.0,
    'call_duration': 0.0,
    'call_duration_bucket': '',
    'revenue_per_call': 0.0
})

# Store TTS audio in-memory per call for Twilio <Play>
tts_audio_store: dict[str, bytes] = {}
# Store last TwiML per call for fallback delivery via URL
last_twiml_store: dict[str, str] = {}
# Track last TwiML push timestamp to throttle rapid updates
last_twiml_push_ts: dict[str, float] = {}
TWIML_PUSH_MIN_INTERVAL_SEC = 1.5
# Incrementing version per call to bust TwiML dedupe/caching for <Play>
tts_version_counter: dict[str, int] = {}
# Track active TTS playback per call for proper speech gate management
active_tts_playback: dict[str, dict] = {}

# Active WebSocket connections (salon service uses a lightweight map)
active_calls: Dict[str, WebSocket] = {}

#---------------HELPERS TO MATCH phone.py FLOW---------------
def _build_wss_url_from_request(request: Request, call_sid: str, caller_number: str = None) -> tuple[str, str]:
    """Build WSS URL from incoming request host/proto, with safe fallbacks (mirrors phone.py)."""
    try:
        hdrs = request.headers
        host = hdrs.get('x-forwarded-host') or hdrs.get('host')
        proto = (hdrs.get('x-forwarded-proto') or request.url.scheme or 'https').lower()
        ws_scheme = 'wss' if proto == 'https' else 'ws'
        
        logging.info(f"🔗 Building WSS URL for {call_sid}")
        logging.info(f"🔗 Headers: x-forwarded-host={hdrs.get('x-forwarded-host')}, host={hdrs.get('host')}")
        logging.info(f"🔗 Protocol: {proto}, WS scheme: {ws_scheme}")
        
        if host:
            ws_base = f"{ws_scheme}://{host}"
            wss_url = f"{ws_base}{settings.STREAM_ENDPOINT}?callSid={call_sid}"
            if caller_number:
                wss_url += f"&From={caller_number}"
            logging.info(f"🔗 Using host-based URLs - ws_base: {ws_base}, wss_url: {wss_url}")
            return ws_base, wss_url
    except Exception as e:
        logging.error(f"❌ Error building host-based URLs: {e}")
        pass
    
    # Fallback to configured EXTERNAL_WEBHOOK_URL
    base = settings.EXTERNAL_WEBHOOK_URL
    if base.startswith('https://'):
        ws_base = base.replace('https://', 'wss://')
    elif base.startswith('http://'):
        ws_base = base.replace('http://', 'ws://')
    else:
        ws_base = f"wss://{base}"
    
    wss_url = f"{ws_base}{settings.STREAM_ENDPOINT}?callSid={call_sid}"
    if caller_number:
        wss_url += f"&From={caller_number}"
    
    logging.info(f"🔗 Using fallback URLs - base: {base}, ws_base: {ws_base}, wss_url: {wss_url}")
    return ws_base, wss_url

def _http_base_from_ws_base(ws_base: str) -> str:
    if ws_base.startswith('wss://'):
        return ws_base.replace('wss://', 'https://')
    if ws_base.startswith('ws://'):
        return ws_base.replace('ws://', 'http://')
    return ws_base

async def add_tts_or_say_to_twiml(target, call_sid: str, text: str):
    """Prefer ElevenLabs/OpenAI TTS with <Play>; fallback to <Say> (mirrors phone.py behavior)."""
    # Natural name prefixing (simplified)
    dialog = call_dialog_state.get(call_sid, {})
    customer_name = dialog.get('customer_name')
    skip_prefix = any(text.lower().startswith(p) for p in [
        "hello", "who do i have", "thank you for calling", "goodbye", "bye"
    ])
    speak_text = text
    if customer_name and not skip_prefix and dialog.get('step') != 'awaiting_name':
        speak_text = f"{customer_name}, {text}"
    
    try:
        # Try TTS with exact duration
        audio, audio_duration = await generate_tts_audio_with_duration(speak_text, call_sid)
        if audio:
            # Store audio and bump version to avoid caching
            ver = int(tts_version_counter.get(call_sid, 0)) + 1
            tts_version_counter[call_sid] = ver
            tts_audio_store[call_sid] = audio
            
            # Build absolute URL based on ws_base from call_info
            call_info = call_info_store.get(call_sid, {})
            ws_base = call_info.get('ws_base')
            
            if not ws_base:
                # Fallback to EXTERNAL_WEBHOOK_URL
                ws_base = settings.EXTERNAL_WEBHOOK_URL
                if ws_base.startswith('https://'):
                    http_base = ws_base
                elif ws_base.startswith('http://'):
                    http_base = ws_base
                else:
                    http_base = f"https://{ws_base}"
            else:
                http_base = _http_base_from_ws_base(ws_base)
            
            play_url = f"{http_base}/tts/{call_sid}.mp3?v={ver}"
            
            # Use REST API with callback instead of direct TwiML (for consistent callback-based speech gate control)
            # Track this TTS playback for callback-based speech gate management
            active_tts_playback[call_sid] = {
                'text': speak_text,
                'play_url': play_url,
                'start_time': time.time(),
                'audio_size': len(audio),
                'audio_duration': audio_duration
            }
            
            # Send TTS response using REST API with callback support
            await _send_tts_via_rest_api_with_callback(call_sid, play_url, speak_text)
            
            # Activate speech gate - will be deactivated by Twilio callback
            await _activate_speech_gate(call_sid)
            
            logging.info(f"🗣️ TTS sent via REST API for {call_sid}: '{speak_text[:50]}...' ({len(audio)} bytes, {audio_duration:.2f}s)")
            return
        else:
            logging.warning(f"⚠️ TTS generation failed for {call_sid}, using <Say> fallback")
    except Exception as e:
        logging.error(f"❌ TTS generation failed for {call_sid}: {e}")
    
    # Fallback
    target.say(speak_text)

@app.get("/tts/{call_sid}.mp3")
async def serve_tts(call_sid: str):
    audio = tts_audio_store.get(call_sid)
    if not audio:
        raise HTTPException(status_code=404, detail="TTS not found")
    return Response(content=audio, media_type="audio/mpeg")

@app.post("/tts-playback-complete")
async def tts_playback_complete_callback(request: Request):
    """Handle callback when TTS audio finishes playing via Gather timeout - reopen speech gate with precise timing"""
    try:
        form = await request.form()
        call_sid = form.get("CallSid")
        # Gather callback will always be timeout since we removed numDigits
        gather_reason = "timeout"
        
        logging.info(f"🎵 TTS playback callback received for {call_sid} - Reason: {gather_reason}")
        logging.info(f"🎵 Callback form data: {dict(form)}")
        
        if not call_sid:
            logging.warning(f"⚠️ TTS callback received without CallSid: {dict(form)}")
            raise HTTPException(status_code=400, detail="CallSid required")
        
        # Get playback tracking data for validation
        playback_data = active_tts_playback.get(call_sid, {})
        start_time = playback_data.get('start_time', 0)
        expected_duration = playback_data.get('audio_duration', 0)
        
        if start_time > 0 and expected_duration > 0:
            actual_duration = time.time() - start_time
            duration_diff = abs(actual_duration - expected_duration)
            logging.info(f"🎵 TTS timing validation for {call_sid}: expected={expected_duration:.2f}s, actual={actual_duration:.2f}s, diff={duration_diff:.2f}s")
            
            # For gather timeout, we expect the callback to come after the audio finishes
            if actual_duration < (expected_duration * 0.8):
                logging.warning(f"⚠️ Gather timeout came much earlier than expected for {call_sid} - possible playback issue")
        
        # Reopen speech gate for this call
        await _deactivate_speech_gate(call_sid)
        
        # Clean up playback tracking
        if call_sid in active_tts_playback:
            del active_tts_playback[call_sid]
        
        logging.info(f"✅ TTS playback callback processed successfully for {call_sid} via Gather {gather_reason}")
        
        # Return empty TwiML to continue call flow - the main stream is already active
        from fastapi.responses import Response
        return Response(content="<Response></Response>", media_type="application/xml")
        
    except Exception as e:
        logging.error(f"❌ Error processing TTS playback callback: {e}")
        # Return empty TwiML even on error to keep call flowing
        from fastapi.responses import Response
        return Response(content="<Response></Response>", media_type="application/xml")

# Media helpers to match phone.py conversion
try:
    import audioop as _audioop  # type: ignore
except Exception:
    _audioop = None

def _mulaw_byte_to_linear16(mu: int) -> int:
    mu = ~mu & 0xFF
    sign = mu & 0x80
    exponent = (mu >> 4) & 0x07
    mantissa = mu & 0x0F
    sample = ((mantissa << 3) + 132) << exponent
    sample = sample - 132
    if sign:
        sample = -sample
    if sample > 32767:
        sample = 32767
    if sample < -32768:
        sample = -32768
    return sample

def mulaw_to_pcm16(mu_bytes: bytes) -> bytes:
    if _audioop is not None:
        return _audioop.ulaw2lin(mu_bytes, 2)
    out = bytearray()
    for b in mu_bytes:
        s = _mulaw_byte_to_linear16(b)
        out.extend(struct.pack('<h', s))
    return bytes(out)

def convert_media_payload_to_pcm16(call_sid: str, payload_b64: str) -> bytes:
    raw_bytes = base64.b64decode(payload_b64)
    cfg = audio_config_store.get(call_sid, {"encoding": "mulaw", "sample_rate": SAMPLE_RATE_DEFAULT})
    encoding = cfg.get("encoding", "mulaw")
    if encoding == "mulaw":
        return mulaw_to_pcm16(raw_bytes)
    return raw_bytes

# Consecutive confidence failure tracking per call
consecutive_intent_failures: dict[str, int] = defaultdict(int)
consecutive_overall_failures: dict[str, int] = defaultdict(int)
consecutive_missing_fields_failures: dict[str, int] = defaultdict(int)

# Speech gate cycle tracking for comprehensive handoff detection
speech_gate_cycle_tracking: dict[str, dict] = defaultdict(lambda: {
    'total_cycles': 0,                    # Total speech gate cycles in this call
    'consecutive_no_progress': 0,         # Consecutive cycles with no progress
    'last_progress_time': 0,              # Last time we made meaningful progress
    'last_speech_gate_time': 0,           # Last time speech gate was activated
    'last_processed_text': '',            # Last successfully processed text
    'last_intent_extracted': None,        # Last successfully extracted intent
    'last_dialog_step': '',               # Last dialog step
    'call_start_time': 0,                 # When the call started
    'max_cycles_without_progress': 3,     # Max cycles without progress before handoff
    'max_call_duration_without_progress': 120,  # Max seconds without progress before handoff
})

# Global state
call_info_store: Dict[str, Dict] = {}
active_calls: Dict[str, WebSocket] = {}
call_transcripts: Dict[str, List] = defaultdict(list)
salon_crm = HairstylingCRM()

# Service pattern matching for Bold Wings
SERVICE_PATTERNS = {
    # Weaves & Extensions
    r'\b(weave|extension|sew.?in)\b': 'Weaves & Extensions',
    
    # Braids
    r'\b(braid|cornrow|knotless|feed.?in|ghana|twist.*braid)\b': 'Braids',
    
    # Locs
    r'\b(loc|dreadlock|sister.?loc|micro.?loc|relock)\b': 'Locs',
    
    # Twists
    r'\b(twist|kinky.?twist|boho.?twist|mini.?twist|micro.?twist)\b': 'Twists',
    
    # Crochet
    r'\b(crochet|protective.?style)\b': 'Crochet',
    
    # Boho Styles
    r'\b(boho|sade.?adu|bohemian)\b': 'Boho Styles',
    
    # Other Services
    r'\b(french.?curl|faux.?loc|pick.*drop|take.?down|wash|treatment|beading)\b': 'Other Services'
}

async def extract_salon_intent_with_gpt(text: str, call_sid: str) -> Dict[str, Any]:
    """Extract salon service intent using GPT enhancement with fallback pattern matching"""
    text_lower = text.lower()
    
    # First try GPT-enhanced extraction if OpenAI is available
    if openai_client:
        try:
            prompt = f"""
You are analyzing customer requests for Bold Wings Hair Salon. 

Available services and categories:
{json.dumps(SALON_SERVICES, indent=2)}

Customer said: "{text}"

Extract the following information:
1. Is this a clear service request? (yes/no)
2. Which service category best matches? (from the available categories)
3. Which specific service? (from the available services)
4. Confidence level (0.0-1.0)

Respond in JSON format:
{{
    "is_service_request": true/false,
    "service_category": "category name",
    "specific_service": "service name",
    "confidence": 0.0-1.0
}}
"""
            
            response = await openai_client.chat.completions.acreate(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=200
            )
            
            gpt_result = json.loads(response.choices[0].message.content)
            
            if gpt_result.get('is_service_request') and gpt_result.get('confidence', 0) > 0.6:
                # Find the service details from our catalog
                service_category = gpt_result.get('service_category')
                specific_service = gpt_result.get('specific_service')
                
                price = 0
                if service_category in SALON_SERVICES.get('services', {}):
                    services = SALON_SERVICES['services'][service_category]
                    for service in services:
                        if service['name'].lower() == specific_service.lower():
                            price = service['price']
                            break
                
                urgency = "High" if any(word in text_lower for word in ['urgent', 'asap', 'emergency', 'soon', 'today']) else "Normal"
                
                return {
                    'service_category': service_category,
                    'specific_service': specific_service,
                    'price': price,
                    'urgency': urgency,
                    'currency': SALON_SERVICES.get('currency', 'CAD'),
                    'confidence': gpt_result.get('confidence', 0.8)
                }
                
        except Exception as e:
            logging.warning(f"GPT intent extraction failed for {call_sid}: {e}")
    
    # Fallback to pattern matching
    service_category = None
    for pattern, category in SERVICE_PATTERNS.items():
        if re.search(pattern, text_lower, re.IGNORECASE):
            service_category = category
            break
    
    if not service_category:
        # No service detected
        return {
            'service_category': None,
            'specific_service': None,
            'price': 0,
            'urgency': "Normal",
            'currency': SALON_SERVICES.get('currency', 'CAD'),
            'confidence': 0.0
        }
    
    # Find specific service within category
    specific_service = None
    best_price = 0
    
    if service_category in SALON_SERVICES.get('services', {}):
        services = SALON_SERVICES['services'][service_category]
        for service in services:
            service_name_lower = service['name'].lower()
            keywords = service_name_lower.split()
            if any(keyword in text_lower for keyword in keywords if len(keyword) > 3):
                specific_service = service['name']
                best_price = service['price']
                break
        
        # If no specific match, use first service in category
        if not specific_service and services:
            specific_service = services[0]['name']
            best_price = services[0]['price']
    
    urgency = "High" if any(word in text_lower for word in ['urgent', 'asap', 'emergency', 'soon', 'today']) else "Normal"
    
    return {
        'service_category': service_category,
        'specific_service': specific_service,
        'price': best_price,
        'urgency': urgency,
        'currency': SALON_SERVICES.get('currency', 'CAD'),
        'confidence': 0.8 if specific_service else 0.5
    }

def get_audio_duration(audio_bytes: bytes) -> float:
    """Get exact duration of MP3 audio using mutagen"""
    try:
        # Using mutagen for precise audio duration detection
        from mutagen.mp3 import MP3
        import io
        audio_file = io.BytesIO(audio_bytes)
        audio = MP3(audio_file)
        duration = float(audio.info.length)
        logging.debug(f"📏 Detected audio duration: {duration:.2f}s")
        return duration
    except ImportError:
        logging.warning("⚠️ mutagen not available, falling back to estimation")
        # Fallback to estimation if mutagen not available
        return (len(audio_bytes) * 8) / 64000  # Assume 64kbps
    except Exception as e:
        logging.warning(f"⚠️ Audio duration detection failed: {e}, falling back to estimation")
        # Fallback to estimation
        return (len(audio_bytes) * 8) / 64000  # Assume 64kbps

async def generate_tts_audio_with_duration(text: str, call_sid: str) -> tuple[Optional[bytes], float]:
    """Generate TTS audio and return both audio bytes and exact duration"""
    if not text.strip():
        return None, 0.0
        
    try:
        audio_bytes = None
        
        if settings.ELEVENLABS_API_KEY:
            # Use ElevenLabs with user's preferred voice
            import httpx
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"https://api.elevenlabs.io/v1/text-to-speech/{settings.ELEVENLABS_VOICE_ID}",
                    headers={"xi-api-key": settings.ELEVENLABS_API_KEY},
                    json={"text": text, "model_id": "eleven_monolingual_v1"}
                )
                if response.status_code == 200:
                    audio_bytes = response.content
                else:
                    logging.warning(f"⚠️ ElevenLabs TTS failed for {call_sid}: {response.status_code}")
        
        # Fallback to OpenAI TTS
        if not audio_bytes and openai_client:
            response = openai_client.audio.speech.create(
                model="tts-1",
                voice="alloy",
                input=text
            )
            audio_bytes = response.content
        
        if not audio_bytes:
            logging.error(f"❌ No TTS client available for {call_sid}")
            return None, 0.0
            
        # Get exact duration
        duration = get_audio_duration(audio_bytes)
        logging.info(f"🎵 TTS generated for {call_sid}: {len(audio_bytes)} bytes, {duration:.2f}s duration")
        
        return audio_bytes, duration
            
    except Exception as e:
        logging.error(f"❌ TTS generation failed for {call_sid}: {e}")
    
    return None, 0.0

async def generate_tts_audio(text: str, call_sid: str) -> Optional[bytes]:
    """Generate TTS audio using ElevenLabs or OpenAI - legacy function for backward compatibility"""
    audio_bytes, _ = await generate_tts_audio_with_duration(text, call_sid)
    return audio_bytes

def format_salon_response(intent: Dict[str, Any], customer_name: str = "love") -> str:
    """Generate warm, authentic salon response based on intent"""
    service = intent.get('specific_service', 'hair service')
    price = intent.get('price', 0)
    
    if price > 0 and salon_response_generator:
        # Use authentic response generator for warm, cultural responses
        return salon_response_generator.get_confirmation_response(service, price, customer_name)
    elif price > 0:
        # Fallback to simple response if generator not available
        return f"Perfect! I can help you with {service}. The price is CAD ${int(price)}. When would you like to schedule your appointment, {customer_name}?"
    else:
        # Use unclear response for services without pricing
        if salon_response_generator:
            return salon_response_generator.get_unclear_response()
        else:
            return f"I'd be happy to help you with {service}. Let me check our availability and pricing. What day works best for you?"

# Import the webhook functions from phone.py instead of implementing them from scratch
from ops_integrations.adapters.phone import (
    health_check as base_health_check,
    get_metrics_snapshot as base_get_metrics_snapshot,
    ops_metrics_ws as base_ops_metrics_ws
)

# Set up logger for salon service
logger = logging.getLogger(__name__)

@app.post(settings.VOICE_ENDPOINT)
async def voice_webhook(request: Request):
    """Handle incoming voice calls - Salon-specific implementation for Bold Wings Hair Salon"""
    form = await request.form()
    call_sid = form.get("CallSid")
    if not call_sid:
        logger.error("Missing CallSid in webhook payload")
        raise HTTPException(status_code=400, detail="CallSid required")

    # Extract all available call information from Twilio webhook
    call_info = {
        "call_sid": call_sid,
        "account_sid": form.get("AccountSid"),
        "from": form.get("From"),
        "to": form.get("To"),
        "direction": form.get("Direction", "inbound"),
        "call_status": form.get("CallStatus"),
        "api_version": form.get("ApiVersion"),
        "forwarded_from": form.get("ForwardedFrom"),
        "caller_name": form.get("CallerName"),
        # Geographic data
        "from_city": form.get("FromCity"),
        "from_state": form.get("FromState"), 
        "from_zip": form.get("FromZip"),
        "from_country": form.get("FromCountry"),
        "to_city": form.get("ToCity"),
        "to_state": form.get("ToState"),
        "to_zip": form.get("ToZip"),
        "to_country": form.get("ToCountry"),
        # Additional metadata
        "timestamp": datetime.now().isoformat(),
        "start_ts": time.time(),
    }
    
    # Compute per-call WebSocket base from the inbound request
    caller_number = form.get("From")
    ws_base, wss_url = _build_wss_url_from_request(request, call_sid, caller_number)
    call_info["ws_base"] = ws_base
    
    # Store call information for use during the call
    call_info_store[call_sid] = call_info
    
    # Initialize call metrics tracking
    call_metrics_store[call_sid] = {
        'call_start_time': time.time(),
        'first_speech_time': 0,
        'first_response_time': 0,
        'call_end_time': 0,
        'service_price': 0.0,
        'appointment_scheduled': False,
        'response_speed': 0.0,
        'call_duration': 0.0,
        'call_duration_bucket': '',
        'revenue_per_call': 0.0
    }

    # Log the call start with key details
    logging.info(f"💇‍♀️ SALON CALL STARTED - {call_sid}")
    logging.info(f"   📱 From: {call_info['from']} ({call_info['from_city']}, {call_info['from_state']})")
    logging.info(f"   📞 To: {call_info['to']} ({call_info['to_city']}, {call_info['to_state']})")
    logging.info(f"   🌍 Direction: {call_info['direction']}")
    logging.info(f"   📊 Status: {call_info['call_status']}")
    logging.info(f"   🌐 WS Base: {ws_base}")
    if call_info['caller_name']:
        logging.info(f"   👤 Caller: {call_info['caller_name']}")
    if call_info['forwarded_from']:
        logging.info(f"   ↩️  Forwarded from: {call_info['forwarded_from']}")

    # Build TwiML Response for SALON
    resp = VoiceResponse()
    
    # SALON-SPECIFIC GREETING
    greet_text = "Hello, thank you for calling Bold Wings Hair Salon! I'm your AI stylist and I'm here to help you schedule your appointment. Who do I have the pleasure of speaking with?"
    logging.info(f"💇‍♀️ SALON TTS SAY (greeting) for CallSid={call_sid}: {greet_text}")
    
    # Use TTS helper so greeting benefits from ElevenLabs if configured
    await add_tts_or_say_to_twiml(resp, call_sid, greet_text)
    
    # Set initial dialog state to collect name
    call_dialog_state[call_sid] = {'step': 'awaiting_name'}
    
    # Start media stream for AI processing
    start = Start()
    start.stream(url=wss_url, track="inbound_track")
    resp.append(start)
    
    # Add pause to keep call active
    resp.pause(length=3600)
    
    logging.info(f"💇‍♀️ Salon stream will start after greeting for call {call_sid}")
    logging.info(f"🔗 WebSocket URL generated: {wss_url}")
    logging.debug(f"📄 Salon TwiML Response: {str(resp)}")

    # Log to Google Sheets immediately if enabled (salon-specific)
    if sheets_crm and sheets_crm.enabled:
        try:
            sheets_record = {
                "timestamp": call_info.get('timestamp'),
                "call_sid": call_sid,
                "customer_name": "Unknown",
                "phone": call_info.get('from', ''),
                "call_status": "initiated",
                "call_duration": "",
                "after_hours": str(not salon_crm._is_business_hours(datetime.now())),
                "service_requested": "Salon Appointment Booking",
                "appointment_date": "",
                "recording_url": "",
                "notes": f"Salon call initiated - AI stylist handling - After hours: {not salon_crm._is_business_hours(datetime.now())}",
                "source": "salon_phone_system",
                "direction": "inbound"
            }
            result = sheets_crm.sync_booking(sheets_record)
            logging.info(f"📊 Logged salon call {call_sid} to Google Sheets: {result}")
        except Exception as e:
            logging.error(f"Failed to log salon call to Google Sheets: {e}")
    
    # Log call start with real-time tracking (salon-specific)
    log_call_update("initiated", call_sid, {
        'from': call_info['from'],
        'to': call_info['to'],
        'notes': "Salon call received - AI stylist assigned"
    })
    
    # Check if after hours (salon-specific)
    call_time = datetime.now()
    is_after_hours = not salon_crm._is_business_hours(call_time)
    
    if is_after_hours:
        log_call_update("after_hours", call_sid, {
            'from': call_info['from'],
            'after_hours': 'true',
            'notes': "After-hours salon call received"
        })
        salon_crm.current_week_metrics['after_hour_calls'] += 1
    
    log_call_update("ai_handling", call_sid, {
        'notes': "AI stylist now handling salon call - no human forwarding"
    })

    return Response(content=str(resp), media_type="application/xml")

@app.websocket(settings.STREAM_ENDPOINT)
async def media_stream_ws(websocket: WebSocket):
    """Handle media streaming WebSocket - Salon-specific implementation"""
    # Echo Twilio's requested subprotocol when provided; fallback to plain accept for tests/tools
    subprotocol_hdr = websocket.headers.get("sec-websocket-protocol")
    if subprotocol_hdr and any(p.strip() == "audio" for p in subprotocol_hdr.split(",")):
        await websocket.accept(subprotocol="audio")
    else:
        await websocket.accept()
    
    call_sid: Optional[str] = None
    caller_number: Optional[str] = None
    temporary_stream_key: Optional[str] = None
    
    try:
        # Try to extract CallSid from query params (Twilio may pass it)
        call_sid = websocket.query_params.get("callSid")
        caller_number = websocket.query_params.get("From")
        logging.info(f"💇‍♀️ Salon WebSocket connection accepted - potential CallSid={call_sid}")
        logging.info(f"🔌 All query params: {dict(websocket.query_params)}")
        logging.info(f"🔌 WebSocket URL: {websocket.url}")
        logging.info(f"🔌 Caller number: {caller_number}")

        # If not present, wait for 'start' event which contains callSid
        if not call_sid:
            logging.info("CallSid not in query params, waiting for 'start' event from Twilio...")
            handshake_deadline = time.time() + 10.0
            while time.time() < handshake_deadline and not call_sid:
                msg = await websocket.receive_text()
                logging.debug(f"Init/handshake message received: {msg[:200]}...")
                try:
                    data = json.loads(msg)
                except json.JSONDecodeError as e:
                    logging.error(f"Failed to parse handshake message as JSON: {e}")
                    continue

                evt = data.get("event")
                if evt == "connected":
                    continue
                if evt == "start":
                    start_obj = data.get("start") or {}
                    call_sid = start_obj.get("callSid") or start_obj.get("CallSid")
                    stream_sid = start_obj.get("streamSid") or data.get("streamSid")
                    media_format = start_obj.get("mediaFormat", {})
                    enc = str(media_format.get("encoding", "mulaw")).lower()
                    sr = int(media_format.get("sampleRate", SAMPLE_RATE_DEFAULT))
                    if "mulaw" in enc or "pcmu" in enc:
                        audio_config_store[call_sid] = {"encoding": "mulaw", "sample_rate": sr}
                    elif "l16" in enc or "pcm" in enc:
                        audio_config_store[call_sid] = {"encoding": "pcm16", "sample_rate": sr}
                    else:
                        audio_config_store[call_sid] = {"encoding": "mulaw", "sample_rate": SAMPLE_RATE_DEFAULT}
                    logging.info(f"💇‍♀️ Salon media format for {call_sid}: {audio_config_store.get(call_sid)}")
                    if not call_sid and stream_sid:
                        temporary_stream_key = f"stream:{stream_sid}"
                        active_calls[temporary_stream_key] = websocket
                        logging.warning(f"Using streamSid as temporary key before CallSid is available: {temporary_stream_key}")
                    if call_sid:
                        active_calls[call_sid] = websocket
                        logging.info(f"✅ Salon CallSid found in start event: {call_sid}")
                        
                        # Update call info with caller number if we extracted it from query params
                        if caller_number and call_sid in call_info_store:
                            call_info = call_info_store[call_sid]
                            if not call_info.get('from') or call_info.get('from') != caller_number:
                                call_info['from'] = caller_number
                                call_info_store[call_sid] = call_info
                        
                        # CRITICAL: Ensure ws_base is properly set for TTS URL generation
                        if call_sid in call_info_store:
                            call_info = call_info_store[call_sid]
                            # Only set ws_base if it's not already set (preserve voice webhook value)
                            if not call_info.get('ws_base'):
                                ws_base_for_call = f"wss://{websocket.url.hostname}"
                                call_info['ws_base'] = ws_base_for_call
                                call_info_store[call_sid] = call_info
                                logging.info(f"🔗 Salon WebSocket base URL set for {call_sid}: {ws_base_for_call}")
                            else:
                                logging.info(f"🔗 Salon ws_base already set from voice webhook: {call_info.get('ws_base')}")
                        else:
                            logging.error(f"❌ CRITICAL: Salon call info not found for {call_sid} when setting ws_base")
                            logging.error(f"❌ Available call_sids: {list(call_info_store.keys())}")
                            logging.error(f"❌ caller_number: {caller_number}")
                        
                        # Initialize VAD state for this call
                        vad_states[call_sid] = {
                            'is_speaking': False,
                            'last_speech_time': 0,
                            'speech_start_time': 0,
                            'pending_audio': bytearray(),
                            'vad': webrtcvad.Vad(VAD_AGGRESSIVENESS),
                            'fallback_buffer': bytearray(),
                            'last_chunk_time': 0,
                            'has_received_media': False,
                            'last_listen_log_time': 0.0,
                            'bot_speaking': False,
                            'bot_speech_start_time': 0,
                            'speech_gate_active': False,
                            'permanent_gate_active': False,
                            'processing_lock': False,
                            'call_start_time': time.time(),
                            'stream_start_time': time.time(),
                            'has_processed_first_speech': False,
                            'last_vad_process_time': 0,
                            'last_chunk_time': 0
                        }
                        
                        # Initialize audio buffer
                        audio_buffers[call_sid] = bytearray()
                        
                        # No need to start separate media loop - main handler will process messages
                        break
                        
        if not call_sid:
            logging.error("Failed to establish CallSid within handshake deadline")
            await websocket.close(code=1008, reason="Missing CallSid parameter")
            return
            
    except Exception as e:
        logging.error(f"Salon WebSocket setup error: {e}")
        return
    
    # Ensure registration when callSid is provided via query params
    if call_sid and call_sid not in active_calls:
        active_calls[call_sid] = websocket
        logging.info(f"💇‍♀️ Salon WebSocket connection established for CallSid={call_sid}")
        logging.info(f"🎬 Salon MediaStream started for {call_sid} - encoding: {audio_config_store.get(call_sid, {}).get('encoding', 'unknown')}, sample_rate: {audio_config_store.get(call_sid, {}).get('sample_rate', 'unknown')}Hz")
        if caller_number and call_sid in call_info_store:
            call_info = call_info_store[call_sid]
            if not call_info.get('from') or call_info.get('from') != caller_number:
                call_info['from'] = caller_number
                call_info_store[call_sid] = call_info

    try:
        # Main receive loop for salon service
        logging.info(f"🔌 Starting salon WebSocket receive loop for {call_sid}")
        while True:
            msg = await websocket.receive_text()
            logging.debug(f"📨 Salon WebSocket raw message for {call_sid}: {msg[:200]}...")
            try:
                packet = json.loads(msg)
            except json.JSONDecodeError:
                logging.warning(f"⚠️ Non-JSON message on media stream for {call_sid}")
                continue

            event = packet.get("event")
            if event == "start":
                start_obj = packet.get("start") or {}
                stream_sid = start_obj.get("streamSid") or packet.get("streamSid")
                media_format = start_obj.get("mediaFormat", {})
                enc = str(media_format.get("encoding", "mulaw")).lower()
                sr = int(media_format.get("sampleRate", SAMPLE_RATE_DEFAULT))
                if "mulaw" in enc or "pcmu" in enc:
                    audio_config_store[call_sid] = {"encoding": "mulaw", "sample_rate": sr}
                elif "l16" in enc or "pcm" in enc:
                    audio_config_store[call_sid] = {"encoding": "pcm16", "sample_rate": sr}
                else:
                    audio_config_store[call_sid] = {"encoding": "mulaw", "sample_rate": SAMPLE_RATE_DEFAULT}
                logging.info(f"🎬 Salon MediaStream started for {call_sid} - encoding: {audio_config_store.get(call_sid, {}).get('encoding')}, sample_rate: {audio_config_store.get(call_sid, {}).get('sample_rate')}Hz, streamSid={stream_sid}")
                # Mark stream start time for VAD preroll handling
                try:
                    state = vad_states[call_sid]
                    state['stream_start_time'] = time.time()
                    state['has_received_media'] = False
                except Exception:
                    pass

            elif event == "media":
                # First-media heartbeat logging
                try:
                    state = vad_states[call_sid]
                    if not state.get('has_received_media'):
                        state['has_received_media'] = True
                        info = call_info_store.get(call_sid, {})
                        if not info.get('first_media_ts'):
                            first_ts = time.time()
                            info['first_media_ts'] = first_ts
                            call_info_store[call_sid] = info
                        logging.info(f"🎧 Listening active for {call_sid} (first media frame)")
                        if call_sid in call_info_store:
                            call_info_store[call_sid]['last_media_time'] = time.time()
                except Exception:
                    pass

                try:
                    payload_b64 = packet["media"]["payload"]
                    pcm16_bytes = _salon_convert_media_payload_to_pcm16(call_sid, payload_b64)
                    logging.debug(f"📨 Media packet received for {call_sid}: {len(pcm16_bytes)} bytes (PCM16)")
                    await _salon_process_audio(call_sid, pcm16_bytes)
                except Exception as e:
                    logging.error(f"Media decode/process error for {call_sid}: {e}")

            elif event == "stop":
                logging.info(f"📞 Media stream STOPPED for {call_sid}")
                # Best-effort flush of any pending speech
                try:
                    vad_state = vad_states.get(call_sid)
                    if vad_state and vad_state['is_speaking'] and len(vad_state['pending_audio']) > 0:
                        speech_duration = time.time() - vad_state.get('speech_start_time', time.time())
                        pending_ms = len(vad_state['pending_audio']) / (audio_config_store.get(call_sid, {}).get('sample_rate', SAMPLE_RATE_DEFAULT) * SAMPLE_WIDTH) * 1000
                        logging.info(f"🎤 Final speech segment at stream stop for {call_sid}: {speech_duration:.2f}s, {pending_ms:.0f}ms buffered")
                except Exception:
                    pass

            elif event == "connected":
                logging.debug(f"🔌 Media WebSocket connected event for {call_sid}")
            else:
                logging.debug(f"❓ Unknown/other event '{event}' for {call_sid}")
    except WebSocketDisconnect:
        logging.info(f"💇‍♀️ Salon WebSocket disconnected for {call_sid}")
    finally:
        # Calculate final call metrics and log to Google Sheets
        await _finalize_call_metrics(call_sid)
        
        # Clean up salon-specific resources
        if call_sid in active_calls:
            del active_calls[call_sid]
        if call_sid in vad_states:
            del vad_states[call_sid]
        if call_sid in audio_buffers:
            del audio_buffers[call_sid]
        if call_sid in call_dialog_state:
            del call_dialog_state[call_sid]
        if call_sid in active_tts_playback:
            del active_tts_playback[call_sid]
        if call_sid in tts_audio_store:
            del tts_audio_store[call_sid]
        if call_sid in conversation_state:
            del conversation_state[call_sid]
        if call_sid in processed_speech_segments:
            processed_speech_segments.discard(call_sid)
        if call_sid in speech_audio_store:
            del speech_audio_store[call_sid]
        if call_sid in stop_listening_after_first:
            del stop_listening_after_first[call_sid]
        if call_sid in call_metrics_store:
            del call_metrics_store[call_sid]
        logging.info(f"💇‍♀️ Salon call {call_sid} disconnected")

#--------------- Twilio media decode helpers (mu-law -> PCM16) ---------------
def _salon_mulaw_byte_to_linear16(mu: int) -> int:
    mu = ~mu & 0xFF
    sign = mu & 0x80
    exponent = (mu >> 4) & 0x07
    mantissa = mu & 0x0F
    sample = ((mantissa << 3) + 132) << exponent
    sample = sample - 132
    if sign:
        sample = -sample
    if sample > 32767:
        sample = 32767
    if sample < -32768:
        sample = -32768
    return sample

def _salon_mulaw_to_pcm16(mu_bytes: bytes) -> bytes:
    if _audioop is not None:
        return _audioop.ulaw2lin(mu_bytes, 2)
    out = bytearray()
    for b in mu_bytes:
        s = _salon_mulaw_byte_to_linear16(b)
        out.extend(struct.pack('<h', s))
    return bytes(out)

def _salon_convert_media_payload_to_pcm16(call_sid: str, payload_b64: str) -> bytes:
    raw_bytes = base64.b64decode(payload_b64)
    cfg = audio_config_store.get(call_sid, {"encoding": "mulaw", "sample_rate": SAMPLE_RATE_DEFAULT})
    encoding = cfg.get("encoding", "mulaw")
    if encoding == "mulaw":
        return _salon_mulaw_to_pcm16(raw_bytes)
    return raw_bytes

#--------------- Phone.py-style VAD processing with first speech handling ---------------
async def _salon_process_audio(call_sid: str, audio: bytes):
    """Process incoming PCM16 audio using phone.py pattern: process first speech, then use time thresholds"""
    vad_state = vad_states[call_sid]
    vad = vad_state['vad']
    current_time = time.time()
    sample_rate = audio_config_store.get(call_sid, {}).get('sample_rate', SAMPLE_RATE_DEFAULT)
    stream_start_time = vad_state.get('stream_start_time', current_time)
    
    # Check if we should stop listening after first speech
    if stop_listening_after_first.get(call_sid, False):
        logging.debug(f"🛑 Skipping audio processing for {call_sid} - already processed first speech")
        return
    
    # Check if bot is currently speaking (speech gate)
    if vad_state.get('speech_gate_active', False):
        gate_start_time = vad_state.get('bot_speech_start_time', current_time)
        gate_elapsed = current_time - gate_start_time
        logging.debug(f"🔇 Speech gate active for {call_sid} - suppressing user speech processing (elapsed: {gate_elapsed:.2f}s)")
        audio_buffers[call_sid].extend(audio)
        return
    
    # Phone.py pattern: Improved first transcription handling - wait longer for initial speech
    if not vad_state.get('has_processed_first_speech', False):
        # For the first speech, wait longer to ensure we get complete audio
        min_initial_buffer_ms = 2000  # Wait 2 seconds for first speech
        current_buffer_ms = len(audio_buffers[call_sid]) / (sample_rate * SAMPLE_WIDTH) * 1000
        if current_buffer_ms < min_initial_buffer_ms:
            # Still building initial buffer
            audio_buffers[call_sid].extend(audio)
            vad_state['fallback_buffer'].extend(audio)
            return
    
    # Log incoming audio
    logging.debug(f"📡 Received {len(audio)} bytes of PCM16 audio from {call_sid}")
    
    # Add audio to buffer
    audio_buffers[call_sid].extend(audio)
    vad_state['fallback_buffer'].extend(audio)
    
    # Info-level listening heartbeat (throttled)
    try:
        if (current_time - vad_state.get('last_listen_log_time', 0)) >= 1.0:
            fb_ms = len(vad_state['fallback_buffer']) / (sample_rate * SAMPLE_WIDTH) * 1000
            logging.info(f"🎧 Listening ({call_sid}): buffer={fb_ms:.0f}ms, speaking={vad_state['is_speaking']}, sample_rate={sample_rate}")
            vad_state['last_listen_log_time'] = current_time
    except Exception:
        pass
    
    # Process audio in 20ms frames for VAD
    frame_size_bytes = int(sample_rate * VAD_FRAME_DURATION_MS / 1000) * SAMPLE_WIDTH
    buffer = audio_buffers[call_sid]
    
    while len(buffer) >= frame_size_bytes:
        frame_bytes = bytes(buffer[:frame_size_bytes])
        buffer = buffer[frame_size_bytes:]
        try:
            is_speech = vad.is_speech(frame_bytes, sample_rate)
            
            # During preroll window, ignore low-energy detections
            if is_speech and not vad_state['is_speaking']:
                if (current_time - stream_start_time) < PREROLL_IGNORE_SEC:
                    try:
                        if _audioop is not None:
                            frame_rms = _audioop.rms(frame_bytes, 2)
                        else:
                            import array
                            arr = array.array('h', frame_bytes)
                            frame_rms = int((sum(x*x for x in arr) / len(arr)) ** 0.5) if len(arr) else 0
                    except Exception:
                        frame_rms = 0
                    if frame_rms < MIN_START_RMS:
                        is_speech = False
            
            if is_speech:
                if not vad_state['is_speaking']:
                    vad_state['is_speaking'] = True
                    vad_state['speech_start_time'] = current_time
                    vad_state['pending_audio'] = bytearray()
                    logging.info(f"🗣️  SPEECH STARTED for {call_sid}")
                vad_state['last_speech_time'] = current_time
                vad_state['pending_audio'].extend(frame_bytes)
            else:
                if vad_state['is_speaking']:
                    vad_state['pending_audio'].extend(frame_bytes)
                    silence_duration = current_time - vad_state['last_speech_time']
                    dialog = call_dialog_state.get(call_sid, {})
                    current_silence_timeout = PROBLEM_DETAILS_SILENCE_TIMEOUT_SEC if dialog.get('step') == 'questions_about_service' else SILENCE_TIMEOUT_SEC
                    
                    if silence_duration >= current_silence_timeout:
                        speech_duration = current_time - vad_state['speech_start_time']
                        pending_duration_ms = len(vad_state['pending_audio']) / (sample_rate * SAMPLE_WIDTH) * 1000
                        timeout_type = "service_questions" if dialog.get('step') == 'questions_about_service' else "regular"
                        logging.info(f"🔇 SPEECH ENDED for {call_sid}: {speech_duration:.2f}s total, {pending_duration_ms:.0f}ms buffered, {silence_duration:.2f}s silence (timeout: {timeout_type})")
                        
                        # Process speech segment if it meets minimum duration
                        if speech_duration >= MIN_SPEECH_DURATION_SEC:
                            # Activate speech gate immediately after speech ends
                            await _activate_speech_gate(call_sid)
                            await _process_speech_segment(call_sid, vad_state['pending_audio'])
                        else:
                            logging.warning(f"❌ Speech too short for {call_sid} ({speech_duration:.2f}s < {MIN_SPEECH_DURATION_SEC}s), discarding")
                        
                        vad_state['is_speaking'] = False
                        vad_state['pending_audio'] = bytearray()
        except Exception as e:
            logging.warning(f"VAD processing error for {call_sid}: {e}")
            continue
    
    audio_buffers[call_sid] = buffer
    
    # Phone.py pattern: Time-based fallback flush with first speech protection
    try:
        fallback_bytes = len(vad_state['fallback_buffer'])
        last_vad_process = vad_state.get('last_vad_process_time', 0)
        last_chunk_time = vad_state.get('last_chunk_time', 0)
        time_since_vad = current_time - last_vad_process
        time_since_chunk = current_time - last_chunk_time
        
        # Only trigger fallback if:
        # 1. Not currently speaking
        # 2. Have enough audio buffered
        # 3. Haven't processed via VAD recently (prevent double processing)
        # 4. Haven't processed via fallback recently (prevent excessive processing)
        # 5. Not currently processing (check processing lock)
        
        # Determine appropriate fallback duration based on dialog state
        dialog = call_dialog_state.get(call_sid, {})
        if dialog.get('step') == 'questions_about_service':
            min_fallback_duration = 10.0  # Require at least 10 seconds of audio before fallback for service questions
            time_since_vad_threshold = 5.0  # Wait longer after VAD processing
            time_since_chunk_threshold = 8.0  # Wait longer between fallback processes
        else:
            min_fallback_duration = 4.0  # Regular fallback duration for normal conversations
            time_since_vad_threshold = 3.0  # Regular wait time after VAD processing
            time_since_chunk_threshold = 5.0  # Regular wait time between fallback processes
        
        if (not vad_state['is_speaking'] and 
            not vad_state.get('processing_lock', False) and
            fallback_bytes >= int(sample_rate * SAMPLE_WIDTH * min_fallback_duration) and
            time_since_vad > time_since_vad_threshold and
            time_since_chunk > time_since_chunk_threshold):
            logging.info(f"⏱️ Time-based fallback flush for {call_sid}: {fallback_bytes} bytes (~{min_fallback_duration}s)")
            await _process_speech_segment(call_sid, vad_state['fallback_buffer'])
            vad_state['fallback_buffer'] = bytearray()
            vad_state['last_chunk_time'] = current_time
            # Also clear the main buffer to prevent overlap
            audio_buffers[call_sid] = bytearray()
    except Exception as e:
        logging.debug(f"Time-based fallback flush error for {call_sid}: {e}")

#--------------- Speech processing and intent recognition ---------------
async def _process_speech_segment(call_sid: str, audio_data: bytes):
    """Process speech segment: transcribe, extract intent, and generate response"""
    try:
        # Check if we should stop listening after first speech
        if stop_listening_after_first[call_sid]:
            logging.info(f"🛑 Skipping speech processing for {call_sid} - already processed first speech")
            return
        
        # Store audio for processing
        speech_audio_store[call_sid] = audio_data
        
        # Transcribe audio to text
        if speech_recognizer:
            logging.info(f"🎤 Transcribing speech for {call_sid} ({len(audio_data)} bytes)")
            try:
                text, transcription_time, confidence = await speech_recognizer.transcribe_audio(audio_data, call_sid)
            except Exception as e:
                logging.error(f"❌ Speech recognizer error for {call_sid}: {e}")
                text, transcription_time, confidence = None, None, None
            
            # Log detailed transcription results
            logging.info(f"📝 Transcription results for {call_sid}: text='{text}', confidence={confidence}, time={transcription_time}")
            
            # Mark as processed after first transcription attempt (successful or failed)
            stop_listening_after_first[call_sid] = True
            processed_speech_segments.add(call_sid)
            
            if text and confidence and confidence > -0.7:  # Basic confidence check
                logging.info(f"✅ Transcription successful for {call_sid}: '{text}' (confidence: {confidence:.2f})")
                
                # Track first speech time
                if call_metrics_store[call_sid]['first_speech_time'] == 0:
                    call_metrics_store[call_sid]['first_speech_time'] = time.time()
                    logging.info(f"🎤 First speech detected for {call_sid} at {call_metrics_store[call_sid]['first_speech_time']}")
                
                # Extract intent using salon-specific extraction with GPT enhancement
                intent = await extract_salon_intent_with_gpt(text, call_sid)
                logging.info(f"🎯 Salon intent extracted for {call_sid}: {intent}")
                
                # Track service price if available
                if intent and intent.get('price', 0) > 0:
                    call_metrics_store[call_sid]['service_price'] = intent['price']
                
                # Generate response based on intent and start follow-up flow
                await _handle_salon_follow_up_flow(call_sid, text, intent)
                
            else:
                # Enhanced logging for failed transcription
                if not text:
                    logging.warning(f"❌ Transcription returned no text for {call_sid} - audio may be too quiet, unclear, or empty")
                elif not confidence:
                    logging.warning(f"❌ Transcription returned no confidence score for {call_sid} - text: '{text}'")
                elif confidence <= -0.7:
                    logging.warning(f"❌ Transcription confidence too low for {call_sid}: '{text}' (confidence: {confidence:.2f})")
                else:
                    logging.warning(f"❌ Transcription failed for {call_sid}: text='{text}', confidence={confidence}")
                
                # Even if transcription failed, start follow-up flow with default response
                await _handle_salon_follow_up_flow(call_sid, "unknown", None)
        else:
            logging.warning(f"⚠️ Speech recognizer not available for {call_sid} - speech_recognizer={speech_recognizer}")
            # Mark as processed and start follow-up flow
            stop_listening_after_first[call_sid] = True
            await _handle_salon_follow_up_flow(call_sid, "unknown", None)
            
    except Exception as e:
        logging.error(f"❌ Speech processing failed for {call_sid}: {e}")

async def _handle_salon_follow_up_flow(call_sid: str, text: str, intent: Dict[str, Any]):
    """Handle salon follow-up flow similar to phone.py pattern"""
    try:
        # Initialize conversation state if not exists
        if call_sid not in conversation_state:
            conversation_state[call_sid] = {
                'step': 'greeting',
                'customer_name': None,
                'service_intent': None,
                'attempts': 0,
                'service_attempts': 0,
                'last_response': None,
                'service_questions_asked': False,
                'awaiting_transfer_decision': False
            }
        
        conv_state = conversation_state[call_sid]
        
        # Handle name collection if we're still in awaiting_name step
        if conv_state.get('step') == 'awaiting_name':
            # Extract customer name if present - pick up any potential name from speech
            customer_name = None
            name_confidence = 0.0
            
            # More flexible name extraction - look for any capitalized words that could be names
            words = text.split()
            for word in words:
                # Skip common words that aren't names
                if word.lower() in ['i', 'am', 'is', 'my', 'name', 'call', 'me', 'this', 'hello', 'hi', 'yes', 'no']:
                    continue
                # Look for capitalized words or words that could be names
                if word.istitle() or (len(word) > 2 and word.isalpha()):
                    customer_name = word.title()
                    # Simple confidence scoring based on word characteristics
                    if word.istitle():
                        name_confidence = 0.7
                    else:
                        name_confidence = 0.5
                    break
            
            # Always transition to awaiting_service step after name collection attempt
            conv_state['step'] = 'awaiting_service'
            
            # Confidence-based response
            if customer_name and name_confidence > 0.6:
                conv_state['customer_name'] = customer_name
                response_text = f"Nice to meet you, {customer_name}! I'd be happy to help you schedule an appointment. What service are you looking for today?"
            else:
                response_text = "Nice to meet you! I'd be happy to help you schedule an appointment. What service are you looking for today?"
            
            await _send_salon_response(call_sid, response_text)
            return
        
        # Handle transfer decision (yes/no response to transfer question)
        if conv_state.get('awaiting_transfer_decision'):
            text_lower = text.lower()
            if any(word in text_lower for word in ['yes', 'yeah', 'sure', 'okay', 'ok', 'transfer']):
                # Customer wants to be transferred
                response_text = "I'll transfer you to our shop now. Please hold while I connect you."
                await _send_salon_response(call_sid, response_text)
                # Transfer the call using dispatch logic
                await _transfer_call_to_shop(call_sid)
                return
            elif any(word in text_lower for word in ['no', 'nah', 'dont', "don't", 'continue']):
                # Customer doesn't want transfer, reset and try again
                conv_state['awaiting_transfer_decision'] = False
                conv_state['service_attempts'] = 0
                response_text = "I'd be happy to help you schedule an appointment. What service are you looking for today?"
                await _send_salon_response(call_sid, response_text)
                return
            else:
                # Unclear response, ask again
                response_text = "I didn't catch that. Would you like me to transfer you to speak with someone at the shop? Please say yes or no."
                await _send_salon_response(call_sid, response_text)
                return
        
        # Check for service requests
        if intent and intent.get('specific_service'):
            service = intent['specific_service']
            price = intent.get('price', 0)
            conv_state['service_intent'] = intent
            conv_state['step'] = 'questions_about_service'
            conv_state['service_attempts'] = 0  # Reset attempts on successful detection
            
            # Ask questions about the service first
            if not conv_state.get('service_questions_asked'):
                response_text = f"Got it, we can help you with {service}. Before we schedule a time for you, did you have any questions about the service?"
                conv_state['service_questions_asked'] = True
                await _send_salon_response(call_sid, response_text)
                return
            else:
                # Service questions already collected, proceed to scheduling
                customer_name = conv_state.get('customer_name', 'there')
                response_text = f"Perfect! What day works best for your {service} appointment, {customer_name}?"
                conv_state['step'] = 'awaiting_scheduling'
                await _send_salon_response(call_sid, response_text)
                return
        
        # Handle Q&A responses when customer says yes to having questions
        if conv_state.get('step') == 'questions_about_service' and conv_state.get('service_questions_asked'):
            await _handle_service_questions(call_sid, text, conv_state)
            return
        
        # Handle scheduling responses
        if conv_state.get('step') == 'awaiting_scheduling':
            # Mark appointment as scheduled
            call_metrics_store[call_sid]['appointment_scheduled'] = True
            logging.info(f"📅 Appointment scheduled for {call_sid}")
            await _handle_scheduling_response(call_sid, text, conv_state)
            return
        
        # No service detected - implement retry logic
        if conv_state.get('step') == 'awaiting_service':
            conv_state['service_attempts'] += 1
            
            if conv_state['service_attempts'] == 1:
                # First failure
                response_text = "Sorry I didn't catch that, what service did you want?"
                await _send_salon_response(call_sid, response_text)
                return
            elif conv_state['service_attempts'] >= 2:
                # Second failure - transfer directly
                response_text = "I'm not able to understand your service request. Let me transfer you to the shop now."
                await _send_salon_response(call_sid, response_text)
                # Transfer the call using dispatch logic
                await _transfer_call_to_shop(call_sid)
                return
        
        # Default response for unclear requests
        response_text = "I'd be happy to help you schedule an appointment. What service are you looking for today?"
        await _send_salon_response(call_sid, response_text)
        
    except Exception as e:
        logging.error(f"❌ Follow-up flow handling failed for {call_sid}: {e}")
        # Fallback response
        response_text = "I'm sorry, I didn't catch that. Could you please repeat what service you'd like to book?"
        await _send_salon_response(call_sid, response_text)

async def _handle_service_questions(call_sid: str, text: str, conv_state: Dict[str, Any]):
    """Handle customer questions about salon services with comprehensive Q&A system"""
    try:
        # Check if customer said "no" or "no questions"
        text_lower = text.lower()
        if any(phrase in text_lower for phrase in ['no', 'no questions', 'nothing', 'no thanks', "don't have", "don't need"]):
            # Customer has no questions, proceed to scheduling
            customer_name = conv_state.get('customer_name', 'there')
            service_intent = conv_state.get('service_intent', {})
            service = service_intent.get('specific_service', 'appointment')
            response_text = f"Perfect! What day works best for your {service} appointment, {customer_name}?"
            conv_state['step'] = 'awaiting_scheduling'
            await _send_salon_response(call_sid, response_text)
            return
        
        # Customer has questions - use comprehensive Q&A system
        service_intent = conv_state.get('service_intent', {})
        service = service_intent.get('specific_service', 'hair service')
        price = service_intent.get('price', 0)
        
        # Generate comprehensive answer using GPT with salon knowledge
        answer = await _generate_service_answer(call_sid, text, service, price, conv_state)
        
        if answer:
            await _send_salon_response(call_sid, answer)
            
            # Ask if they have more questions
            await asyncio.sleep(1)  # Small delay
            follow_up = "Do you have any other questions about the service, or are you ready to schedule your appointment?"
            await _send_salon_response(call_sid, follow_up)
        else:
            # Fallback response
            response_text = f"I'd be happy to help with any questions about {service}. What would you like to know?"
            await _send_salon_response(call_sid, response_text)
            
    except Exception as e:
        logging.error(f"❌ Service questions handling failed for {call_sid}: {e}")
        # Fallback response
        response_text = "I'm here to help with any questions you might have. What would you like to know?"
        await _send_salon_response(call_sid, response_text)

async def _generate_service_answer(call_sid: str, question: str, service: str, price: float, conv_state: Dict[str, Any]) -> str:
    """Generate comprehensive answer using GPT with salon knowledge and web search"""
    try:
        if not openai_client:
            return None
            
        # Build comprehensive salon knowledge context
        salon_context = _build_salon_knowledge_context(service, price)
        
        # Create system prompt for salon Q&A
        system_prompt = f"""You are a knowledgeable AI assistant for Bold Wings Hair Salon. You have access to comprehensive salon information and can provide detailed answers about services, pricing, and hair care.

SALON INFORMATION:
{salon_context}

CUSTOMER CONTEXT:
- Service: {service}
- Price: ${price} CAD
- Customer Name: {conv_state.get('customer_name', 'there')}

INSTRUCTIONS:
1. Answer the customer's question about salon services comprehensively
2. Be warm, professional, and helpful
3. If the question is about something not in our salon knowledge, use web search to find current information
4. Keep responses conversational and under 100 words
5. Always relate back to how we can help them at Bold Wings Hair Salon

CUSTOMER QUESTION: {question}"""

        # Check if question needs web search (outside salon scope)
        needs_web_search = _needs_web_search(question)
        
        if needs_web_search:
            # Use web search for out-of-scope questions
            web_info = await _search_web_for_question(question)
            if web_info:
                system_prompt += f"\n\nWEB SEARCH RESULTS:\n{web_info}"
        
        # Generate response using GPT
        response = openai_client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": question}
            ],
            max_tokens=200,
            temperature=0.7
        )
        
        answer = response.choices[0].message.content.strip()
        logging.info(f"✅ Generated service answer for {call_sid}: {answer[:100]}...")
        return answer
        
    except Exception as e:
        logging.error(f"❌ Failed to generate service answer for {call_sid}: {e}")
        return None

def _build_salon_knowledge_context(service: str, price: float) -> str:
    """Build comprehensive salon knowledge context"""
    context = f"""
BOLD WINGS HAIR SALON - COMPREHENSIVE SERVICE GUIDE

SERVICES & PRICING:
{json.dumps(SALON_SERVICES, indent=2)}

SPECIFIC SERVICE DETAILS:
- Service: {service}
- Price: ${price} CAD

SERVICE CATEGORIES:
1. WEAVES & EXTENSIONS:
   - Sew-in weaves, clip-in extensions
   - Natural hair blending, length and volume enhancement
   - Maintenance every 6-8 weeks

2. BRAIDS:
   - Cornrow braids, knotless braids, feed-in braids
   - Ghana braids, twist braids
   - Protective styling, lasts 6-8 weeks

3. LOCS:
   - Sister locs, micro locs, traditional locs
   - Relocking services, maintenance
   - Natural hair journey support

4. TWISTS:
   - Kinky twists, boho twists, mini twists
   - Micro twists for fine hair
   - Low-maintenance protective style

5. CROCHET:
   - Protective styling, quick installation
   - Various textures and lengths
   - Great for transitioning hair

6. BOHO STYLES:
   - Sade Adu inspired looks
   - Bohemian, free-spirited styles
   - Perfect for special occasions

BUSINESS HOURS:
- Monday-Thursday: 7:00 AM - 11:00 PM
- Friday-Saturday: 7:00 PM - 11:00 PM
- Sunday: Closed

SALON POLICIES:
- Consultation included with all services
- 24-hour cancellation policy
- Payment accepted: Cash, Card, E-transfer
- All stylists are licensed professionals
- We use high-quality, professional products

HAIR CARE TIPS:
- Moisturize regularly for healthy hair
- Use satin/silk pillowcases and bonnets
- Avoid excessive heat styling
- Regular trims for hair health
- Protective styles help retain length

PREPARATION FOR SERVICES:
- Come with clean, dry hair (unless specified)
- Bring inspiration photos if desired
- Arrive 10 minutes early for consultation
- Bring snacks for longer services (4+ hours)
"""
    return context

def _needs_web_search(question: str) -> bool:
    """Determine if question needs web search (outside salon scope)"""
    question_lower = question.lower()
    
    # Topics that might need web search
    web_search_topics = [
        'hair loss', 'alopecia', 'medical', 'health', 'vitamins', 'supplements',
        'diet', 'nutrition', 'hormones', 'pregnancy', 'menopause', 'thyroid',
        'product ingredients', 'chemical', 'allergic', 'reaction', 'scalp condition',
        'dermatologist', 'doctor', 'prescription', 'medication', 'treatment',
        'hair growth', 'regrowth', 'transplant', 'surgery', 'procedure'
    ]
    
    return any(topic in question_lower for topic in web_search_topics)

async def _search_web_for_question(question: str) -> str:
    """Search web for out-of-scope questions"""
    try:
        # For now, return a helpful response for out-of-scope questions
        # In a production environment, you would integrate with a web search API
        # like Google Custom Search, Bing Search API, or SerpAPI
        
        # Categorize the type of question and provide appropriate guidance
        question_lower = question.lower()
        
        if any(word in question_lower for word in ['hair loss', 'alopecia', 'bald', 'thinning']):
            return """Hair loss can have various causes including genetics, stress, hormonal changes, or medical conditions. 
            While we can help with styling and protective techniques at Bold Wings, we recommend consulting with a 
            dermatologist or trichologist for medical concerns. We can also suggest protective styles that help 
            minimize stress on your hair."""
            
        elif any(word in question_lower for word in ['vitamins', 'supplements', 'nutrition', 'diet']):
            return """Nutrition plays an important role in hair health. Biotin, iron, zinc, and protein are commonly 
            mentioned for hair growth. However, we recommend consulting with a healthcare provider before starting 
            any supplements. At Bold Wings, we focus on proper hair care techniques and protective styling to 
            maintain healthy hair."""
            
        elif any(word in question_lower for word in ['medical', 'doctor', 'dermatologist', 'prescription']):
            return """For medical hair concerns, we always recommend consulting with a healthcare professional or 
            dermatologist. At Bold Wings Hair Salon, we specialize in styling, protective techniques, and hair care 
            that can complement medical treatments. We'd be happy to discuss styling options that work with your 
            hair's current condition."""
            
        else:
            return f"""That's a great question about "{question}". While I don't have specific information about that topic 
            in our salon knowledge base, I'd recommend consulting with a healthcare professional for medical concerns, 
            or feel free to ask our stylists during your consultation at Bold Wings. We're always happy to help with 
            hair care and styling questions!"""
            
    except Exception as e:
        logging.error(f"Web search failed: {e}")
        return "I'd be happy to help with that question. Feel free to ask our stylists during your consultation at Bold Wings Hair Salon."

async def _handle_scheduling_response(call_sid: str, text: str, conv_state: Dict[str, Any]):
    """Handle scheduling response and ask for preferred day"""
    try:
        # Acknowledge the service choice and ask for scheduling day
        response_text = "Sounds good! What day works best in your case?"
        await _send_salon_response(call_sid, response_text)
        
    except Exception as e:
        logging.error(f"❌ Scheduling response handling failed for {call_sid}: {e}")
        # Fallback response
        response_text = "I'm sorry, I didn't catch that. What day would work best for you?"
        await _send_salon_response(call_sid, response_text)

async def _send_salon_response(call_sid: str, response_text: str):
    """Send TTS response using Twilio REST API for media stream calls with exact duration tracking"""
    try:
        # For media stream calls, we need to use Twilio's REST API to send TTS
        # since we can't send webhook responses during media processing
        
        # Generate TTS audio with exact duration
        audio, audio_duration = await generate_tts_audio_with_duration(response_text, call_sid)
        if not audio:
            logging.error(f"❌ Failed to generate TTS audio for {call_sid}")
            return
            
        # Store audio and bump version
        ver = int(tts_version_counter.get(call_sid, 0)) + 1
        tts_version_counter[call_sid] = ver
        tts_audio_store[call_sid] = audio
        
        # Build TTS URL - convert ws_base to http_base
        call_info = call_info_store.get(call_sid, {})
        ws_base = call_info.get('ws_base')
        if not ws_base:
            http_base = settings.EXTERNAL_WEBHOOK_URL
        else:
            # Convert WebSocket base to HTTP base
            http_base = _http_base_from_ws_base(ws_base)
            
        play_url = f"{http_base}/tts/{call_sid}.mp3?v={ver}"
        
        # Track this TTS playback for callback-based speech gate management
        active_tts_playback[call_sid] = {
            'text': response_text,
            'play_url': play_url,
            'start_time': time.time(),
            'audio_size': len(audio),
            'audio_duration': audio_duration
        }
        
        # Track first response time
        if call_metrics_store[call_sid]['first_response_time'] == 0:
            call_metrics_store[call_sid]['first_response_time'] = time.time()
            logging.info(f"🗣️ First response sent for {call_sid} at {call_metrics_store[call_sid]['first_response_time']}")
            
            # Calculate response speed
            first_speech_time = call_metrics_store[call_sid]['first_speech_time']
            first_response_time = call_metrics_store[call_sid]['first_response_time']
            if first_speech_time > 0:
                response_speed = first_response_time - first_speech_time
                call_metrics_store[call_sid]['response_speed'] = round(response_speed, 2)
                logging.info(f"⚡ Response speed calculated for {call_sid}: {response_speed:.2f}s")
        
        # Send TTS response using Twilio REST API with callback support
        await _send_tts_via_rest_api_with_callback(call_sid, play_url, response_text)
        
        # Activate speech gate - will be deactivated by Twilio callback  
        await _activate_speech_gate(call_sid)
        
        # Reset listening flag so we can process the next speech after this TTS finishes
        stop_listening_after_first[call_sid] = False
        
        logging.info(f"✅ Salon response sent via REST API for {call_sid}: '{response_text}'")
        logging.info(f"🔇 Speech gate reactivated for {call_sid}")
        logging.info(f"🔄 Listening reset for {call_sid} - ready for next speech")
        
    except Exception as e:
        logging.error(f"❌ Failed to send salon response to {call_sid}: {e}")

async def _send_tts_via_rest_api(call_sid: str, play_url: str, text: str):
    """Legacy function - Send TTS response using Twilio REST API without callback"""
    try:
        # Fallback to callback-enabled version
        await _send_tts_via_rest_api_with_callback(call_sid, play_url, text)
    except Exception as e:
        logging.error(f"❌ Failed to send TTS via REST API for {call_sid}: {e}")

async def _send_tts_via_rest_api_with_callback(call_sid: str, play_url: str, text: str):
    """Send TTS response using Twilio REST API with callback for precise timing"""
    try:
        # Use Twilio's REST API to send TTS response during media stream
        # This is the proper way to send audio during media stream calls
        
        import httpx
        import base64
        
        # Get callback URL for precise timing
        call_info = call_info_store.get(call_sid, {})
        ws_base = call_info.get('ws_base')
        if not ws_base:
            http_base = settings.EXTERNAL_WEBHOOK_URL
        else:
            # Convert WebSocket base to HTTP base
            http_base = _http_base_from_ws_base(ws_base)
        
        callback_url = f"{http_base}/tts-playback-complete"
        
        # Build TwiML that plays audio with callback AND re-starts the media stream so it persists after playback
        # Reconstruct the WSS stream URL using stored ws_base for this call
        call_info = call_info_store.get(call_sid, {})
        ws_base = call_info.get('ws_base')
        if not ws_base:
            # Fallback to EXTERNAL_WEBHOOK_URL if ws_base is missing
            base = settings.EXTERNAL_WEBHOOK_URL
            if base.startswith('https://'):
                ws_base = base.replace('https://', 'wss://')
            elif base.startswith('http://'):
                ws_base = base.replace('http://', 'ws://')
            else:
                ws_base = f"wss://{base}"
        # Include caller number if available for consistency with initial Start/Stream
        from_number = call_info.get('from')
        wss_url = f"{ws_base}{settings.STREAM_ENDPOINT}?callSid={call_sid}"
        if from_number:
            wss_url += f"&From={from_number}"

        # Important: Re-add <Start><Stream> after <Play> with proper callback and keep the call alive with a long pause
        # XML-escape the URLs so '&' in query params becomes '&amp;' (prevents Twilio 12100 XML parse error)
        wss_url_xml = wss_url.replace("&", "&amp;")
        callback_url_xml = callback_url.replace("&", "&amp;")
        
        # Calculate timeout based on audio duration (add small buffer for network/processing delays)
        audio_duration = active_tts_playback.get(call_sid, {}).get('audio_duration', 5.0)
        timeout_seconds = max(1, int(audio_duration + 1.0))  # Add 1 second buffer, minimum 1 second
        
        twiml = (
            f'<Response>'
            f'<Gather action="{callback_url_xml}" method="POST" timeout="{timeout_seconds}">'
            f'<Play>{play_url}</Play>'
            f'</Gather>'
            f'<Start><Stream url="{wss_url_xml}" track="inbound_track"/></Start>'
            f'<Pause length="3600"/></Response>'
        )
        
        logging.info(f"📤 Sending TTS response via REST API for {call_sid}: {play_url}")
        logging.info(f"📄 TwiML content: {twiml}")
        
        # Get Twilio credentials from settings
        account_sid = settings.TWILIO_ACCOUNT_SID
        auth_token = settings.TWILIO_AUTH_TOKEN
        
        if not account_sid or not auth_token:
            logging.error(f"❌ Twilio credentials not configured for REST API call")
            return
        
        # Create basic auth header
        credentials = f"{account_sid}:{auth_token}"
        encoded_credentials = base64.b64encode(credentials.encode()).decode()
        
        # Make the REST API call to Twilio
        url = f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Calls/{call_sid}.json"
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                headers={
                    "Authorization": f"Basic {encoded_credentials}",
                    "Content-Type": "application/x-www-form-urlencoded"
                },
                data={
                    "Twiml": twiml
                }
            )
            
            if response.status_code == 200:
                logging.info(f"✅ TTS response sent successfully via REST API for {call_sid}")
            else:
                logging.error(f"❌ REST API call failed for {call_sid}: {response.status_code} - {response.text}")
        
    except Exception as e:
        logging.error(f"❌ Failed to send TTS via REST API for {call_sid}: {e}")

async def _transfer_call_to_shop(call_sid: str):
    """Transfer the call to dispatch (shop) using the same logic as phone.py"""
    try:
        # Use the dispatch number (same as phone.py)
        dispatch_number = getattr(settings, 'DISPATCH_NUMBER', '+19404656984')
        
        # Create TwiML to dial the dispatch number
        twiml = VoiceResponse()
        # Say "shop" to customer but dial dispatch
        twiml.say("Connecting you to our shop now.")
        twiml.dial(dispatch_number)
        
        # Mark state to avoid further processing (same as phone.py)
        st = call_info_store.setdefault(call_sid, {})
        st["handoff_requested"] = True
        st["handoff_reason"] = "service_extraction_failed"
        call_info_store[call_sid] = st
        
        # Clear conversation state to prevent further processing
        conversation_state.pop(call_sid, None)
        call_dialog_state.pop(call_sid, None)
        
        # Clear audio processing state
        speech_audio_store.pop(call_sid, None)
        processed_speech_segments.discard(call_sid)
        stop_listening_after_first.pop(call_sid, None)
        
        # Push TwiML to call using the same method as phone.py
        await _push_twiml_to_call(call_sid, twiml)
        
        logging.info(f"✅ Call {call_sid} successfully transferred to shop (dispatch) at {dispatch_number}")
        
        # Log the transfer
        log_call_update("transferred", call_sid, {
            'notes': f"Call transferred to shop (dispatch) at {dispatch_number}",
            'transfer_destination': dispatch_number,
            'transfer_reason': 'service_extraction_failed'
        })
        
    except Exception as e:
        logging.error(f"❌ Failed to transfer call {call_sid} to shop: {e}")

async def _push_twiml_to_call(call_sid: str, twiml: VoiceResponse):
    """Push TwiML to call using Twilio REST API (same as phone.py)"""
    try:
        import httpx
        import base64
        
        # Prepare auth and data for Twilio REST API
        auth_string = f"{settings.TWILIO_ACCOUNT_SID}:{settings.TWILIO_AUTH_TOKEN}"
        auth_b64 = base64.b64encode(auth_string.encode()).decode()
        
        # Update the call with new TwiML
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"https://api.twilio.com/2010-04-01/Accounts/{settings.TWILIO_ACCOUNT_SID}/Calls/{call_sid}.json",
                headers={
                    "Authorization": f"Basic {auth_b64}",
                    "Content-Type": "application/x-www-form-urlencoded"
                },
                data={
                    "Twiml": str(twiml)
                }
            )
            
            if response.status_code == 200:
                logging.info(f"✅ TwiML pushed successfully to call {call_sid}")
            else:
                logging.error(f"❌ Failed to push TwiML to call {call_sid}: {response.status_code} - {response.text}")
        
    except Exception as e:
        logging.error(f"❌ Failed to push TwiML to call {call_sid}: {e}")

@app.post("/status-callback")
async def status_callback(request: Request):
    """Handle call status changes from Twilio for AI calls"""
    form = await request.form()
    call_sid = form.get("CallSid")
    call_status = form.get("CallStatus")
    error_code = form.get("ErrorCode", "")
    
    log_call_update("status_change", call_sid, {
        'status': call_status,
        'error_code': error_code,
        'notes': f"AI call status changed to {call_status}"
    })
    
    # Update call info if we have it
    if call_sid in call_info_store:
        call_info = call_info_store[call_sid]
        call_info['status'] = call_status
        call_info['error_code'] = error_code
        
        # Log status change to Google Sheets immediately (DISABLED - only log initial call)
        # if sheets_crm and sheets_crm.enabled:
        #     try:
        #         status_record = {
        #             "timestamp": datetime.now().isoformat(),
        #             "call_sid": call_sid,
        #             "customer_name": "Unknown",
        #             "phone": call_info.get('from', ''),
        #             "call_status": call_status,
        #             "call_duration": "",
        #             "after_hours": str(not salon_crm._is_business_hours(datetime.now())),
        #             "service_requested": "AI Appointment Scheduling",
        #             "appointment_date": "",
        #             "recording_url": "",
        #             "notes": f"AI call status change: {call_status} - Error: {error_code}",
        #             "source": "phone_system",
        #             "direction": "inbound",
        #             "error_code": error_code or ""
        #         }
        #         sheets_crm.sync_booking(status_record)
        #         logging.info(f"📊 AI call status change for {call_sid} logged to Google Sheets")
        #     except Exception as e:
        #         logging.error(f"Failed to log AI call status change to Google Sheets: {e}")
    
    return {"status": "ok"}


@app.post("/")
async def catch_all_post(request: Request):
    """Catch-all POST endpoint to handle misrouted callbacks"""
    try:
        form = await request.form()
        logging.warning(f"⚠️ POST request to root path - form data: {dict(form)}")
        logging.warning(f"⚠️ Request URL: {request.url}")
        logging.warning(f"⚠️ Request headers: {dict(request.headers)}")
        
        # Check if this looks like a TTS callback
        if "CallSid" in form and "PlaybackStatus" in form:
            logging.info(f"🎵 Redirecting TTS callback to proper endpoint")
            # Redirect to the proper callback endpoint
            return await tts_playback_complete_callback(request)
        
        return {"status": "ok", "message": "Catch-all POST handled"}
    except Exception as e:
        logging.error(f"❌ Error in catch-all POST handler: {e}")
        return {"status": "error", "message": str(e)}

@app.post("/no-answer")
async def no_answer_webhook(request: Request):
    """Handle when AI agent needs to end the call gracefully"""
    form = await request.form()
    call_sid = form.get("CallSid")
    
    log_call_update("ai_call_end", call_sid, {
        'notes': "AI agent ending call gracefully"
    })
    
    # Update call info
    if call_sid in call_info_store:
        call_info = call_info_store[call_sid]
        call_info['status'] = 'completed'
        call_info['end_time'] = datetime.now().isoformat()
        
        # Track as completed call
        salon_crm.current_week_metrics['answered_calls'] += 1
        
        # Log to Google Sheets immediately (DISABLED - only log initial call)
        # if sheets_crm and sheets_crm.enabled:
        #     try:
        #         completion_record = {
        #             "timestamp": call_info.get('timestamp'),
        #             "call_sid": call_sid,
        #             "customer_name": "Unknown",
        #             "phone": call_info.get('from', ''),
        #             "call_status": "completed",
        #             "call_duration": "0",
        #             "after_hours": str(not salon_crm._is_business_hours(datetime.fromisoformat(call_info.get('timestamp').replace('Z', '+00:00')))),
        #             "service_requested": "AI Appointment Scheduling",
        #             "appointment_date": "",
        #             "recording_url": "",
        #             "notes": "Call completed by AI agent - appointment scheduled",
        #             "source": "phone_system",
        #             "direction": "inbound"
        #         }
        #         sheets_crm.sync_booking(completion_record)
        #         logging.info(f"📊 AI call {call_sid} completed and logged to Google Sheets")
        #     except Exception as e:
        #         logging.error(f"Failed to log AI call completion to Google Sheets: {e}")
    
    return {"status": "ok"}

@app.get("/health")
async def health_check():
    """Health check endpoint - delegates to base implementation"""
    return await base_health_check()

@app.get("/metrics")
async def get_metrics_snapshot():
    """Returns operational metrics - delegates to base implementation"""
    return await base_get_metrics_snapshot()

@app.websocket("/ops")
async def ops_metrics_ws(websocket: WebSocket):
    """WebSocket for real-time operations dashboard - delegates to base implementation"""
    await base_ops_metrics_ws(websocket)

@app.get("/")
async def root():
    """Root endpoint"""
    try:
        return {
            "message": "💇‍♀️ Bold Wings Hair Salon Phone Service - AI Stylist",
            "status": "running",
            "description": "AI-powered salon phone service that handles hair appointment calls directly",
            "endpoints": {
                "health": "/health",
                "voice": "/voice",
                "stream": "/stream?callSid={call_sid}",
                "metrics": "/metrics",
                "transcripts": "/calls/{call_sid}/transcript"
            },
            "features": [
                "AI-powered salon call handling",
                "Automatic hair appointment scheduling",
                "Voice recognition and transcription",
                "Natural language processing for salon services",
                "Call recording and logging",
                "Salon CRM integration",
                "Bold Wings service catalog"
            ],
            "salon_info": {
                "name": "Bold Wings Hair Salon",
                "services": "Braids, Locs, Twists, Weaves, Crochet Styles",
                "business_hours": "Mon-Thu 7AM-11PM, Fri-Sat 7PM-11PM",
                "location": "Hair styling and beauty services"
            },
            "active_calls": len(active_calls),
            "total_calls": len(call_info_store),
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logging.error(f"Error in salon root endpoint: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")



@app.get("/calls/{call_sid}/transcript")
async def get_call_transcript(call_sid: str):
    """Get transcript for a specific call"""
    if call_sid not in call_transcripts:
        raise HTTPException(status_code=404, detail="Call not found")
    
    return {
        "call_sid": call_sid,
        "transcript": call_transcripts[call_sid],
        "call_info": call_info_store.get(call_sid, {})
    }

@app.post("/test/sheets-integration")
async def test_sheets_integration():
    """Test Google Sheets integration with enhanced metrics"""
    try:
        if not sheets_crm:
            return {
                "status": "error",
                "message": "Google Sheets CRM not available",
                "result": None
            }
        
        logging.info("🧪 Starting Google Sheets integration test...")
        result = sheets_crm.test_sheets_integration()
        
        return {
            "status": "success",
            "message": "Google Sheets integration test completed",
            "result": result,
            "enhanced_metrics": {
                "call_duration_bucket": "Medium (30s-2min)",
                "response_speed": "2.5 seconds",
                "revenue_per_call": "$85.00",
                "new_columns_added": [
                    "Call Duration Bucket",
                    "Response Speed (sec)", 
                    "Revenue per Call ($)"
                ]
            }
        }
        
    except Exception as e:
        logging.error(f"❌ Google Sheets integration test failed: {e}")
        return {
            "status": "error",
            "message": f"Test failed: {str(e)}",
            "result": None
        }



# Enhanced logging setup with real-time updates
import logging.handlers
import os

# Create logs directory if it doesn't exist
os.makedirs('logs', exist_ok=True)

# Setup comprehensive logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),  # Console output
        logging.handlers.RotatingFileHandler(
            'logs/salon_phone.log',
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5
        ),
        logging.handlers.TimedRotatingFileHandler(
            'logs/salon_phone_daily.log',
            when='midnight',
            interval=1,
            backupCount=30
        )
    ]
)

# Create a custom logger for real-time call tracking
call_logger = logging.getLogger('salon_calls')
call_logger.setLevel(logging.INFO)

# Add a custom formatter for call events
call_formatter = logging.Formatter(
    '%(asctime)s - CALL_EVENT - %(levelname)s - %(message)s'
)

# Add handlers for call-specific logging
call_file_handler = logging.handlers.RotatingFileHandler(
    'logs/salon_calls_realtime.log',
    maxBytes=5*1024*1024,  # 5MB
    backupCount=3
)
call_file_handler.setFormatter(call_formatter)
call_logger.addHandler(call_file_handler)

# Salon-specific logging functions (translated from phone.py)
def log_salon_call_update(event_type, call_sid, details, status="info"):
    """Log salon call updates with real-time tracking (translated from phone.py)"""
    timestamp = datetime.now().isoformat()
    
    # Translate event types to salon terminology
    salon_event_translations = {
        'initiated': '📞 Salon Call Started',
        'ai_handling': '🤖 AI Stylist Assigned',
        'answered': '✅ Call Answered by AI',
        'completed': '💇‍♀️ Appointment Scheduled',
        'failed': '❌ Call Failed',
        'canceled': '🚫 Call Canceled',
        'after_hours': '🌙 After-Hours Call',
        'status_change': '🔄 Call Status Changed',
        'ai_call_end': '👋 AI Stylist Completed Call',
        'recording_status': '🎙️ Call Recording Status'
    }
    
    event_emoji = salon_event_translations.get(event_type, '📱')
    log_message = f"{event_emoji} {event_type.upper()} - Call {call_sid} - {details}"
    
    # Log to call-specific logger
    if status == "error":
        call_logger.error(log_message)
    elif status == "warning":
        call_logger.warning(log_message)
    else:
        call_logger.info(log_message)
    
    # Also log to main logger with salon-specific formatting
    logging.info(f"💇‍♀️ {log_message}")
    
    # Log to Google Sheets if available (DISABLED - only log initial call)
    # if sheets_crm and sheets_crm.enabled:
    #     try:
    #         sheets_record = {
    #             "timestamp": timestamp,
    #             "call_sid": call_sid,
    #             "customer_name": "Unknown",
    #             "phone": details.get('from', ''),
    #             "call_status": event_type,
    #             "call_duration": details.get('duration', ''),
    #             "after_hours": details.get('after_hours', 'false'),
    #             "service_requested": "Salon Appointment Booking",
    #             "appointment_date": "",
    #             "recording_url": details.get('recording_url', ''),
    #             "notes": f"Salon {event_type}: {details.get('notes', '')}",
    #             "source": "salon_phone_system",
    #             "direction": "inbound",
    #             "error_code": details.get('error_code', '')
    #         }
    #         sheets_crm.sync_booking(sheets_record)
    #     except Exception as e:
    #         logging.error(f"Failed to log salon call update to sheets: {e}")

def log_salon_tts(call_sid, message, level="info"):
    """Log salon TTS events (translated from phone.py)"""
    salon_tts_log = f"🗣️ SALON TTS [{call_sid}]: {message}"
    
    if level == "error":
        logging.error(salon_tts_log)
    elif level == "warning":
        logging.warning(salon_tts_log)
    elif level == "debug":
        logging.debug(salon_tts_log)
    else:
        logging.info(salon_tts_log)

def log_salon_error(call_sid, error, context=""):
    """Log salon errors with context (translated from phone.py)"""
    error_context = f" - Context: {context}" if context else ""
    salon_error_log = f"❌ SALON ERROR [{call_sid}]: {error}{error_context}"
    logging.error(salon_error_log)
    call_logger.error(salon_error_log)

def log_salon_success(call_sid, message):
    """Log salon success events (translated from phone.py)"""
    salon_success_log = f"✅ SALON SUCCESS [{call_sid}]: {message}"
    logging.info(salon_success_log)
    call_logger.info(salon_success_log)

# Legacy function for backward compatibility
def log_call_update(event_type, call_sid, details, status="info"):
    """Legacy function - now calls salon-specific logging"""
    log_salon_call_update(event_type, call_sid, details, status)

#---------------SPEECH GATE MANAGEMENT (Callback-Only)---------------
async def _activate_speech_gate(call_sid: str):
    """Activate speech gate - only deactivated by Twilio callback when TTS finishes"""
    try:
        vad_state = vad_states[call_sid]
        current_time = time.time()
        
        # Simple activation - no timers, no duration estimates, no scheduling
        vad_state['speech_gate_active'] = True
        vad_state['bot_speaking'] = True
        vad_state['bot_speech_start_time'] = current_time
        
        log_salon_tts(call_sid, f"🔇 Speech gate ACTIVATED - waiting for Twilio callback to deactivate")
        
    except Exception as e:
        log_salon_error(call_sid, f"Failed to activate speech gate: {e}")

async def _deactivate_speech_gate(call_sid: str):
    """Deactivate speech gate immediately (called by Twilio TTS completion callback)"""
    try:
        vad_state = vad_states.get(call_sid)
        if vad_state:
            vad_state['speech_gate_active'] = False
            vad_state['bot_speaking'] = False
            
            # Calculate how long the gate was active
            gate_start_time = vad_state.get('bot_speech_start_time', 0)
            gate_duration = time.time() - gate_start_time if gate_start_time > 0 else 0
            
            log_salon_tts(call_sid, f"🔓 Speech gate DEACTIVATED by Twilio callback after {gate_duration:.2f}s")
            
            # Clear any accumulated audio during gate period to avoid processing stale audio
            if vad_state.get('is_speaking'):
                vad_state['is_speaking'] = False
                vad_state['pending_audio'] = bytearray()
                logging.debug(f"Cleared pending audio for {call_sid} after speech gate deactivation")
                
    except Exception as e:
        log_salon_error(call_sid, f"Failed to deactivate speech gate: {e}")

async def _finalize_call_metrics(call_sid: str):
    """Calculate final call metrics and log to Google Sheets with enhanced tracking"""
    try:
        if call_sid not in call_metrics_store:
            logging.warning(f"No metrics found for call {call_sid}")
            return
            
        metrics = call_metrics_store[call_sid]
        call_info = call_info_store.get(call_sid, {})
        
        # Calculate call duration
        call_start_time = metrics['call_start_time']
        call_end_time = time.time()
        call_duration = call_end_time - call_start_time
        metrics['call_duration'] = round(call_duration, 2)
        metrics['call_end_time'] = call_end_time
        
        # Calculate call duration bucket
        metrics['call_duration_bucket'] = sheets_crm.calculate_call_duration_bucket(call_duration) if sheets_crm else "Unknown"
        
        # Calculate revenue per call
        service_price = metrics['service_price']
        appointment_scheduled = metrics['appointment_scheduled']
        metrics['revenue_per_call'] = sheets_crm.calculate_revenue_per_call(service_price, appointment_scheduled) if sheets_crm else 0.0
        
        # Log enhanced metrics to Google Sheets
        if sheets_crm and sheets_crm.enabled:
            try:
                enhanced_record = {
                    "timestamp": call_info.get('timestamp', datetime.now().isoformat()),
                    "call_sid": call_sid,
                    "customer_name": "Unknown",  # Could be enhanced to track actual customer name
                    "phone": call_info.get('from', ''),
                    "call_status": "completed",
                    "call_duration": str(metrics['call_duration']),
                    "call_duration_bucket": metrics['call_duration_bucket'],
                    "response_speed": str(metrics['response_speed']),
                    "revenue_per_call": f"{metrics['revenue_per_call']:.2f}",
                    "after_hours": str(not salon_crm._is_business_hours(datetime.now())),
                    "service_requested": "Salon Appointment Booking",
                    "appointment_date": "",
                    "recording_url": "",
                    "notes": f"Call completed - Duration: {metrics['call_duration']:.1f}s, Response: {metrics['response_speed']:.1f}s, Revenue: ${metrics['revenue_per_call']:.2f}",
                    "source": "salon_phone_system",
                    "direction": "inbound"
                }
                
                result = sheets_crm.sync_booking(enhanced_record)
                logging.info(f"📊 Enhanced metrics logged to Google Sheets for {call_sid}: {result}")
                logging.info(f"📊 Call metrics - Duration: {metrics['call_duration']:.1f}s ({metrics['call_duration_bucket']}), Response: {metrics['response_speed']:.1f}s, Revenue: ${metrics['revenue_per_call']:.2f}")
                
            except Exception as e:
                logging.error(f"Failed to log enhanced metrics to Google Sheets for {call_sid}: {e}")
        
        # Update salon CRM metrics
        salon_crm.current_week_metrics['total_calls'] += 1
        salon_crm.current_week_metrics['answered_calls'] += 1
        salon_crm.current_week_metrics['total_revenue'] += metrics['revenue_per_call']
        
        if metrics['appointment_scheduled']:
            salon_crm.current_week_metrics['total_appointments'] += 1
        
        # Log call completion
        log_call_update("completed", call_sid, {
            'duration': f"{metrics['call_duration']:.1f}s",
            'duration_bucket': metrics['call_duration_bucket'],
            'response_speed': f"{metrics['response_speed']:.1f}s",
            'revenue': f"${metrics['revenue_per_call']:.2f}",
            'appointment_scheduled': str(metrics['appointment_scheduled']),
            'notes': "Call completed with enhanced metrics tracking"
        })
        
    except Exception as e:
        logging.error(f"❌ Failed to finalize call metrics for {call_sid}: {e}")

# Legacy aliases for backward compatibility
async def _deactivate_speech_gate_immediate(call_sid: str):
    """Legacy alias - deactivate speech gate immediately"""
    await _deactivate_speech_gate(call_sid)

async def _activate_speech_gate_permanent(call_sid: str):
    """Legacy alias - activate speech gate permanently until next TTS"""
    await _activate_speech_gate(call_sid)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("salon_phone_service:app", host="0.0.0.0", port=5001, reload=True)
