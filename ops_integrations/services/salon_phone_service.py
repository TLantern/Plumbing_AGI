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

from fastapi import FastAPI, WebSocket, Request, BackgroundTasks, HTTPException
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

# Import salon integration
try:
    from ops_integrations.core.salon_response_generator import salon_response_generator
except ImportError:
    salon_response_generator = None

# Import Google Sheets integration
try:
    from ops_integrations.adapters.external_services.sheets import GoogleSheetsCRM
    sheets_crm = GoogleSheetsCRM()
    logging.info(f"📊 Google Sheets CRM initialized: enabled={sheets_crm.enabled}, spreadsheet_id={sheets_crm.spreadsheet_id}")
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
    OPENAI_API_KEY: str = ""
    
    # ElevenLabs TTS
    ELEVENLABS_API_KEY: str = ""
    ELEVENLABS_VOICE_ID: str = "kdmDKE6EkgrWrrykO9Qt"  # User's preferred voice
    ELEVENLABS_MODEL_ID: str = "eleven_multilingual_v2"
    
    # Service endpoints
    VOICE_ENDPOINT: str = "/voice"
    MEDIA_ENDPOINT: str = "/media"
    
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

# FastAPI app
app = FastAPI(title="Bold Wings Salon Phone Service")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

#---------------AUDIO PROCESSING CONFIGURATION---------------
# VAD Configuration - Tuned for Better Quality (same as phone.py)
VAD_AGGRESSIVENESS = 1  # Less aggressive = more sensitive to quiet speech
VAD_FRAME_DURATION_MS = 20  # 20ms = optimal for speech detection accuracy
SILENCE_TIMEOUT_SEC = 1.8  # Balanced - allows natural pauses but not too long
PROBLEM_DETAILS_SILENCE_TIMEOUT_SEC = 3.0  # Longer timeout specifically for problem details phase
MIN_SPEECH_DURATION_SEC = 0.5  # Longer = filter out more noise, better quality
CHUNK_DURATION_SEC = 4.0  # Regular chunk duration for normal conversations
PROBLEM_DETAILS_CHUNK_DURATION_SEC = 15.0  # Extended chunk duration specifically for problem details phase
PREROLL_IGNORE_SEC = 0.1  # Shorter = start listening sooner
MIN_START_RMS = 90  # Lower = more sensitive to quiet speech
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
})

# Per-call media format (encoding and sample rate)
audio_config_store = defaultdict(lambda: {
    'encoding': 'mulaw',      # 'mulaw' or 'pcm16'
    'sample_rate': SAMPLE_RATE_DEFAULT
})

# Add a simple in-memory dialog state store
call_dialog_state = {}

# Store call information when calls start
call_info_store = {}

# Store TTS audio in-memory per call for Twilio <Play>
tts_audio_store: dict[str, bytes] = {}
# Store last TwiML per call for fallback delivery via URL
last_twiml_store: dict[str, str] = {}
# Track last TwiML push timestamp to throttle rapid updates
last_twiml_push_ts: dict[str, float] = {}
TWIML_PUSH_MIN_INTERVAL_SEC = 1.5
# Incrementing version per call to bust TwiML dedupe/caching for <Play>
tts_version_counter: dict[str, int] = {}

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

def extract_salon_intent(text: str) -> Dict[str, Any]:
    """Extract salon service intent from customer text"""
    text_lower = text.lower()
    
    # Find matching service category
    service_category = None
    for pattern, category in SERVICE_PATTERNS.items():
        if re.search(pattern, text_lower, re.IGNORECASE):
            service_category = category
            break
    
    if not service_category:
        service_category = "Other Services"  # Default
    
    # Find specific service within category
    specific_service = None
    best_price = 0
    
    if service_category in SALON_SERVICES.get('services', {}):
        services = SALON_SERVICES['services'][service_category]
        for service in services:
            service_name_lower = service['name'].lower()
            # Simple keyword matching for specific services
            keywords = service_name_lower.split()
            if any(keyword in text_lower for keyword in keywords if len(keyword) > 3):
                specific_service = service['name']
                best_price = service['price']
                break
        
        # If no specific match, use first service in category
        if not specific_service and services:
            specific_service = services[0]['name']
            best_price = services[0]['price']
    
    # Extract urgency and customer info
    urgency = "Normal"
    if any(word in text_lower for word in ['urgent', 'asap', 'emergency', 'soon', 'today']):
        urgency = "High"
    
    return {
        'service_category': service_category,
        'specific_service': specific_service,
        'price': best_price,
        'urgency': urgency,
        'currency': SALON_SERVICES.get('currency', 'CAD'),
        'confidence': 0.8 if specific_service else 0.5
    }

async def generate_tts_audio(text: str, call_sid: str) -> Optional[bytes]:
    """Generate TTS audio using ElevenLabs or OpenAI"""
    if not text.strip():
        return None
        
    try:
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
                    return response.content
        
        # Fallback to OpenAI TTS
        if openai_client:
            response = openai_client.audio.speech.create(
                model="tts-1",
                voice="alloy",
                input=text
            )
            return response.content
            
    except Exception as e:
        logging.error(f"TTS generation failed: {e}")
    
    return None

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

@app.post(settings.VOICE_ENDPOINT)
async def voice_webhook(request: Request):
    """Handle incoming voice calls - route to human dispatcher with logging"""
    form = await request.form()
    call_sid = form.get("CallSid")
    
    if not call_sid:
        raise HTTPException(status_code=400, detail="CallSid required")
    
    # Store call info for logging
    call_info = {
        "call_sid": call_sid,
        "from": form.get("From"),
        "to": form.get("To"),
        "timestamp": datetime.now().isoformat(),
        "start_ts": time.time(),
    }
    call_info_store[call_sid] = call_info
    
    # Log call start with real-time tracking
    log_call_update("initiated", call_sid, {
        'from': call_info['from'],
        'to': call_info['to'],
        'notes': "Incoming call received"
    })
    
    # Check if after hours
    call_time = datetime.now()
    is_after_hours = not salon_crm._is_business_hours(call_time)
    
    if is_after_hours:
        log_call_update("after_hours", call_sid, {
            'from': call_info['from'],
            'after_hours': 'true',
            'notes': "After-hours call received"
        })
        salon_crm.current_week_metrics['after_hour_calls'] += 1
    
    # Log to Google Sheets immediately if enabled
    if sheets_crm and sheets_crm.enabled:
        try:
            sheets_record = {
                "timestamp": call_info.get('timestamp'),
                "call_sid": call_sid,
                "customer_name": "Unknown",
                "phone": call_info.get('from', ''),
                "call_status": "initiated",
                "call_duration": "",
                "after_hours": str(is_after_hours),
                "service_requested": "Inbound Call",
                "appointment_date": "",
                "recording_url": "",
                "notes": f"Call initiated - After hours: {is_after_hours}",
                "source": "phone_system",
                "direction": "inbound"
            }
            result = sheets_crm.sync_booking(sheets_record)
            logging.info(f"📊 Logged incoming call {call_sid} to Google Sheets: {result}")
        except Exception as e:
            logging.error(f"Failed to log incoming call to Google Sheets: {e}")
    else:
        logging.warning(f"Google Sheets CRM not enabled or available for call {call_sid}")
    
    # Generate TwiML response - route directly to human dispatcher
    resp = VoiceResponse()
    
    # Optional: Add a brief greeting before transferring
    resp.say("Thank you for calling Bold Wings Hair Salon. Please hold while I connect you to our team.")
    
    # Route call to human dispatcher with recording
    resp.dial(
        settings.DISPATCH_NUMBER,
        record='record-from-answer',
        recording_status_callback=f"{request.url.scheme}://{request.headers.get('host')}/recording-status",
        recording_status_callback_event=['completed'],
        status_callback=f"{request.url.scheme}://{request.headers.get('host')}/status-callback",
        status_callback_event=['initiated', 'ringing', 'answered', 'completed', 'busy', 'no-answer', 'failed', 'canceled'],
        action=f"{request.url.scheme}://{request.headers.get('host')}/no-answer",
        timeout=30
    )
    
    log_call_update("routing", call_sid, {
        'to': settings.DISPATCH_NUMBER,
        'notes': f"Routing call to dispatcher: {settings.DISPATCH_NUMBER}"
    })
    
    return Response(content=str(resp), media_type="application/xml")

@app.post("/status-callback")
async def status_callback(request: Request):
    """Handle call status changes from Twilio"""
    form = await request.form()
    call_sid = form.get("CallSid")
    call_status = form.get("CallStatus")
    error_code = form.get("ErrorCode", "")
    
    log_call_update("status_change", call_sid, {
        'status': call_status,
        'error_code': error_code,
        'notes': f"Call status changed to {call_status}"
    })
    
    # Update call info if we have it
    if call_sid in call_info_store:
        call_info = call_info_store[call_sid]
        call_info['status'] = call_status
        call_info['error_code'] = error_code
        
        # Log status change to Google Sheets immediately
        if sheets_crm and sheets_crm.enabled:
            try:
                status_record = {
                    "timestamp": datetime.now().isoformat(),
                    "call_sid": call_sid,
                    "customer_name": "Unknown",
                    "phone": call_info.get('from', ''),
                    "call_status": call_status,
                    "call_duration": "",
                    "after_hours": str(not salon_crm._is_business_hours(datetime.now())),
                    "service_requested": "Inbound Call",
                    "appointment_date": "",
                    "recording_url": "",
                    "notes": f"Status change: {call_status} - Error: {error_code}",
                    "source": "phone_system",
                    "direction": "inbound",
                    "error_code": error_code or ""
                }
                sheets_crm.sync_booking(status_record)
                logging.info(f"📊 Status change for {call_sid} logged to Google Sheets")
            except Exception as e:
                logging.error(f"Failed to log status change to Google Sheets: {e}")
    
    return {"status": "ok"}

@app.post("/no-answer")
async def no_answer_webhook(request: Request):
    """Handle when dispatcher doesn't answer the call"""
    form = await request.form()
    call_sid = form.get("CallSid")
    
    log_call_update("no_answer", call_sid, {
        'notes': "Dispatcher did not answer call",
        'error_code': 'no-answer'
    }, "warning")
    
    # Update call info
    if call_sid in call_info_store:
        call_info = call_info_store[call_sid]
        call_info['status'] = 'no-answer'
        call_info['no_answer_time'] = datetime.now().isoformat()
        
        # Track as missed call
        salon_crm.current_week_metrics['missed_calls'] += 1
        
        # Log to Google Sheets immediately
        if sheets_crm and sheets_crm.enabled:
            try:
                no_answer_record = {
                    "timestamp": call_info.get('timestamp'),
                    "call_sid": call_sid,
                    "customer_name": "Unknown",
                    "phone": call_info.get('from', ''),
                    "call_status": "missed",
                    "call_duration": "0",
                    "after_hours": str(not salon_crm._is_business_hours(datetime.fromisoformat(call_info.get('timestamp').replace('Z', '+00:00')))),
                    "service_requested": "Inbound Call",
                    "appointment_date": "",
                    "recording_url": "",
                    "notes": "MISSED CALL - Dispatcher did not answer",
                    "source": "phone_system",
                    "direction": "inbound",
                    "error_code": "no-answer"
                }
                sheets_crm.sync_booking(no_answer_record)
                logging.info(f"📊 Missed call {call_sid} logged to Google Sheets")
            except Exception as e:
                logging.error(f"Failed to log missed call to Google Sheets: {e}")
    
    return {"status": "ok"}

@app.websocket(f"{settings.MEDIA_ENDPOINT}/{{call_sid}}")
async def media_websocket(websocket: WebSocket, call_sid: str):
    """Handle media streaming WebSocket with optimized VAD processing"""
    await websocket.accept()
    active_calls[call_sid] = websocket
    
    # Initialize VAD state for this call
    vad_state = vad_states[call_sid]
    vad_state['call_start_time'] = time.time()
    vad_state['has_received_media'] = False
    
    customer_name = "Customer"
    conversation_state = "awaiting_name"
    
    logging.info(f"🎵 Media stream connected for call: {call_sid}")
    
    try:
        async for message in websocket.iter_text():
            try:
                data = json.loads(message)
                
                if data.get("event") == "media":
                    # Decode audio data
                    payload = data.get("media", {}).get("payload", "")
                    if payload:
                        audio_chunk = base64.b64decode(payload)
                        # Process audio with VAD
                        await process_audio_with_vad(call_sid, audio_chunk, customer_name, conversation_state, websocket)
                
                elif data.get("event") == "start":
                    logging.info(f"🎤 Audio stream started for {call_sid}")
                
                elif data.get("event") == "stop":
                    logging.info(f"🛑 Audio stream stopped for {call_sid}")
                    break
                    
            except Exception as e:
                logging.error(f"Error processing message: {e}")
                continue
                
    except Exception as e:
        logging.error(f"WebSocket error for {call_sid}: {e}")
    finally:
        # Clean up
        active_calls.pop(call_sid, None)
        call_transcripts.pop(call_sid, None)
        
        # Clean up VAD state
        if call_sid in vad_states:
            del vad_states[call_sid]
        
        # Notify salon analytics
        if salon_phone_integration:
            call_info = call_info_store.get(call_sid, {})
            call_info['duration_sec'] = int(time.time() - call_info.get('start_ts', time.time()))
            asyncio.create_task(salon_phone_integration.handle_call_ended(call_info))
        
        logging.info(f"🔌 Call {call_sid} disconnected")

async def process_audio_with_vad(call_sid: str, audio_chunk: bytes, customer_name: str, 
                                conversation_state: str, websocket: WebSocket):
    """Process audio with Voice Activity Detection (VAD) - optimized from phone.py"""
    try:
        vad_state = vad_states[call_sid]
        vad_state['has_received_media'] = True
        
        # Add audio to buffer
        audio_buffers[call_sid].extend(audio_chunk)
        
        # Process audio in frames for VAD
        buffer = audio_buffers[call_sid]
        frame_size_bytes = VAD_FRAME_DURATION_MS * SAMPLE_RATE_DEFAULT * SAMPLE_WIDTH // 1000
        
        # Only process complete frames, leave remainder in buffer
        complete_frames = len(buffer) // frame_size_bytes
        if complete_frames > 0:
            for i in range(complete_frames):
                start_idx = i * frame_size_bytes
                end_idx = start_idx + frame_size_bytes
                frame = buffer[start_idx:end_idx]
                
                # Check if frame contains speech
                is_speech = vad_state['vad'].is_speech(frame, SAMPLE_RATE_DEFAULT)
                _update_vad_state(call_sid, is_speech)
            
            # Remove processed frames from buffer
            processed_bytes = complete_frames * frame_size_bytes
            buffer[:processed_bytes] = b''
        
        # Check for speech segments and process
        await _check_and_process_speech(call_sid, customer_name, conversation_state, websocket)
        
        # Log VAD state periodically
        current_time = time.time()
        if current_time - vad_state.get('last_listen_log_time', 0) > 1.0:
            vad_state['last_listen_log_time'] = current_time
            buffer_ms = len(audio_buffers[call_sid]) * 1000 // (SAMPLE_RATE_DEFAULT * SAMPLE_WIDTH)
            logging.info(f"🎧 Listening ({call_sid}): buffer={buffer_ms}ms, speaking={vad_state['is_speaking']}")
            
    except Exception as e:
        logging.error(f"VAD processing error for {call_sid}: {e}")

def _update_vad_state(call_sid: str, is_speech: bool):
    """Update VAD state based on speech detection"""
    vad_state = vad_states[call_sid]
    current_time = time.time()
    
    if is_speech:
        if not vad_state['is_speaking']:
            # Speech started
            vad_state['is_speaking'] = True
            vad_state['speech_start_time'] = current_time
        vad_state['last_speech_time'] = current_time
    else:
        if vad_state['is_speaking']:
            # Check if silence duration exceeds threshold
            silence_duration = current_time - vad_state['last_speech_time']
            # Use default silence timeout for salon service
            current_silence_timeout = SILENCE_TIMEOUT_SEC
            
            if silence_duration >= current_silence_timeout:
                # Speech ended
                vad_state['is_speaking'] = False
                speech_duration = vad_state['last_speech_time'] - vad_state['speech_start_time']
                
                if speech_duration >= MIN_SPEECH_DURATION_SEC:
                    # Valid speech segment detected
                    vad_state['pending_audio'] = audio_buffers[call_sid].copy()
                    audio_buffers[call_sid].clear()
                else:
                    logging.warning(f"❌ Speech too short for {call_sid} ({speech_duration:.2f}s < {MIN_SPEECH_DURATION_SEC}s), discarding")

async def _check_and_process_speech(call_sid: str, customer_name: str, conversation_state: str, websocket: WebSocket):
    """Check for speech segments and process them"""
    vad_state = vad_states[call_sid]
    
    if vad_state['pending_audio']:
        # Process pending audio
        audio_data = bytes(vad_state['pending_audio'])
        vad_state['pending_audio'].clear()
        
        # Check if speech duration exceeds chunk duration
        speech_duration = vad_state['last_speech_time'] - vad_state['speech_start_time']
        # Use default chunk duration for salon service
        current_chunk_duration = CHUNK_DURATION_SEC
        
        if speech_duration >= current_chunk_duration:
            logging.debug(f"Forcing processing due to max duration for {call_sid} (chunk_duration: {current_chunk_duration}s)")
        
        # Process the audio chunk
        await process_audio_chunk(call_sid, audio_data, customer_name, conversation_state, websocket)
    
    # Time-based fallback flush every CHUNK_DURATION_SEC even if VAD never triggered
    current_time = time.time()
    if (current_time - vad_state.get('last_chunk_time', 0) >= CHUNK_DURATION_SEC and 
        len(audio_buffers[call_sid]) > 0):
        
        fallback_bytes = len(audio_buffers[call_sid])
        if (fallback_bytes >= int(SAMPLE_RATE_DEFAULT * SAMPLE_WIDTH * CHUNK_DURATION_SEC) and
            current_time - vad_state.get('last_speech_time', 0) >= SILENCE_TIMEOUT_SEC):
            
            logging.info(f"⏱️ Time-based fallback flush for {call_sid}: {fallback_bytes} bytes (~{CHUNK_DURATION_SEC}s)")
            audio_data = bytes(audio_buffers[call_sid])
            audio_buffers[call_sid].clear()
            await process_audio_chunk(call_sid, audio_data, customer_name, conversation_state, websocket)
        
        vad_state['last_chunk_time'] = current_time

async def process_audio_chunk(call_sid: str, audio_data: bytes, customer_name: str, 
                            conversation_state: str, websocket: WebSocket):
    """Process audio chunk and handle conversation"""
    if not openai_client:
        return
    
    try:
        # Convert audio to WAV format for Whisper
        wav_audio = convert_to_wav(audio_data)
        if not wav_audio:
            return
        
        # Enhanced prompt for better transcription quality (same as phone.py)
        FAST_TRANSCRIPTION_PROMPT = "Caller describing salon service needs. Focus on clear human speech. Ignore background noise, dial tones, hangup signals, beeps, clicks, static, and other audio artifacts. Maintain natural speech patterns and context."
        
        # Transcribe audio
        response = openai_client.audio.transcriptions.create(
            model="whisper-1",
            file=("audio.wav", wav_audio, "audio/wav"),
            language="en",
            prompt=FAST_TRANSCRIPTION_PROMPT
        )
        
        transcript = response.text.strip()
        if not transcript or len(transcript) < 3:
            return
        
        # Store transcript
        call_transcripts[call_sid].append({
            'text': transcript,
            'timestamp': datetime.now().isoformat(),
            'speaker': 'customer'
        })
        
        logging.info(f"📝 Transcript [{call_sid}]: {transcript}")
        
        # Process based on conversation state
        if conversation_state == "awaiting_name":
            # Extract customer name
            customer_name = extract_customer_name(transcript)
            if customer_name != "Customer":
                # Check if it's a Nigerian name for culturally appropriate response
                is_nigerian_name = customer_name.lower() in NIGERIAN_NAMES
                
                if salon_response_generator:
                    if is_nigerian_name:
                        # Special welcome for Nigerian names
                        nigerian_greetings = [
                            f"Ah, {customer_name}! What a beautiful name, sis! Welcome to Bold Wings. How can we make your hair beautiful today, love?",
                            f"Hello {customer_name}! So nice to meet you, queen! I'm excited to help you with your hair today. What are you thinking?",
                            f"Welcome {customer_name}, darling! I love your name! What kind of hair magic can we create for you today, hun?",
                            f"{customer_name}! Beautiful name for a beautiful queen! How can Bold Wings help you feel even more gorgeous today?",
                            f"Ah, {customer_name}! Welcome to Bold Wings, sis! What hair service can we do for you today, love?"
                        ]
                        response_text = random.choice(nigerian_greetings)
                        logging.info(f"🌟 Using culturally appropriate greeting for Nigerian name: {customer_name}")
                    else:
                        response_text = f"Nice to meet you, {customer_name}! How can I help you with your hair today, love? We do braids, locs, twists, weaves, crochet styles, and so much more!"
                else:
                    response_text = f"Nice to meet you, {customer_name}! How can I help you with your hair today? We offer braids, locs, twists, weaves, crochet styles, and many other services."
                conversation_state = "service_inquiry"
            else:
                if salon_response_generator:
                    response_text = salon_response_generator.get_unclear_response()
                else:
                    response_text = "I didn't catch your name clearly. Could you please tell me your name again?"
        
        elif conversation_state == "service_inquiry":
            # Extract service intent
            intent = extract_salon_intent(transcript)
            response_text = format_salon_response(intent, customer_name)
            
            if intent['confidence'] > 0.6:
                conversation_state = "scheduling"
                
                # Create potential appointment
                if salon_crm and intent.get('specific_service'):
                    try:
                        call_info = call_info_store.get(call_sid, {})
                        customer_phone = call_info.get('from', '')
                        
                        # This would typically lead to appointment scheduling
                        logging.info(f"💼 Service intent: {intent['specific_service']} for {customer_name}")
                        
                    except Exception as e:
                        logging.error(f"Failed to process service intent: {e}")
            else:
                if salon_response_generator:
                    response_text = salon_response_generator.get_unclear_response()
                else:
                    response_text = "I want to make sure I understand your needs correctly. Could you tell me more about what hair service you're looking for today?"
        
        elif conversation_state == "scheduling":
            # Handle scheduling logic
            if any(word in transcript.lower() for word in ['book', 'schedule', 'appointment', 'when', 'available']):
                if salon_response_generator:
                    response_text = salon_response_generator.get_scheduling_response(customer_name)
                else:
                    response_text = "Great! Let me check our availability. What day works best for you this week? We're open Monday through Thursday 7 AM to 11 PM, and Friday-Saturday 7 PM to 11 PM."
                conversation_state = "booking"
            else:
                response_text = "Would you like to schedule an appointment for this service, love?"
        
        elif conversation_state == "booking":
            # Simple booking confirmation
            if salon_response_generator:
                response_text = salon_response_generator.get_goodbye_response(customer_name)
            else:
                response_text = f"Perfect! I'll get that scheduled for you, {customer_name}. You'll receive a confirmation shortly. Is there anything else I can help you with today?"
            conversation_state = "completed"
        
        # Generate and send TTS response
        if response_text:
            await send_tts_response(websocket, response_text, call_sid)
            
            # Store assistant response
            call_transcripts[call_sid].append({
                'text': response_text,
                'timestamp': datetime.now().isoformat(),
                'speaker': 'assistant'
            })
        
    except Exception as e:
        logging.error(f"Error processing audio chunk: {e}")

def extract_customer_name(text: str) -> str:
    """Extract customer name from text with Nigerian name recognition"""
    text_lower = text.lower().strip()
    
    # Common greeting patterns
    patterns = [
        r"my name is (\w+)",
        r"i'm (\w+)", 
        r"this is (\w+)",
        r"call me (\w+)",
        r"name's (\w+)",
        r"it's (\w+)",
        r"^(\w+)$",  # Single word response
    ]
    
    # First try pattern matching
    for pattern in patterns:
        match = re.search(pattern, text_lower)
        if match:
            potential_name = match.group(1)
            
            # Check if it's a Nigerian name (high confidence)
            if potential_name in NIGERIAN_NAMES:
                # Return with proper capitalization
                original_name = next(name for name in SALON_NAMES.get('nigerian_names', []) 
                                   if name.lower() == potential_name)
                logging.info(f"✅ Recognized Nigerian name: {original_name}")
                return original_name
            
            # Check if it's a regular name (not a common word)
            name_capitalized = potential_name.capitalize()
            if potential_name not in ['yes', 'no', 'hello', 'hi', 'hey', 'good', 'fine', 'okay', 'sure', 'right']:
                return name_capitalized
    
    # If no pattern match, check for Nigerian names in the text
    words = text_lower.split()
    for word in words:
        if word in NIGERIAN_NAMES:
            # Return with proper capitalization
            original_name = next(name for name in SALON_NAMES.get('nigerian_names', []) 
                               if name.lower() == word)
            logging.info(f"✅ Found Nigerian name in text: {original_name}")
            return original_name
    
    # Fallback: try to extract any capitalized word that looks like a name
    import string
    words = text.split()
    for word in words:
        clean_word = word.strip(string.punctuation)
        if (len(clean_word) > 2 and 
            clean_word[0].isupper() and 
            clean_word.lower() not in ['yes', 'no', 'hello', 'hi', 'hey', 'good', 'fine', 'okay']):
            return clean_word
    
    return "Customer"

def convert_to_wav(audio_data: bytes) -> Optional[bytes]:
    """Convert audio data to WAV format"""
    try:
        # Simple conversion for mu-law audio (Twilio format)
        import io
        import wave
        
        # Create WAV file in memory
        wav_buffer = io.BytesIO()
        with wave.open(wav_buffer, 'wb') as wav_file:
            wav_file.setnchannels(1)  # Mono
            wav_file.setsampwidth(2)  # 16-bit
            wav_file.setframerate(8000)  # 8kHz
            wav_file.writeframes(audio_data)
        
        wav_buffer.seek(0)
        return wav_buffer.read()
        
    except Exception as e:
        logging.error(f"Audio conversion failed: {e}")
        return None

async def send_tts_response(websocket: WebSocket, text: str, call_sid: str):
    """Send TTS response back to caller"""
    try:
        # Generate TTS audio
        tts_audio = await generate_tts_audio(text, call_sid)
        if not tts_audio:
            return
        
        # Convert to base64 and send via WebSocket
        # This is a simplified version - real implementation would need proper audio formatting
        audio_b64 = base64.b64encode(tts_audio).decode()
        
        # Send media message (simplified)
        message = {
            "event": "media",
            "media": {
                "payload": audio_b64
            }
        }
        
        await websocket.send_text(json.dumps(message))
        logging.info(f"🔊 TTS sent to {call_sid}: {text[:50]}...")
        
    except Exception as e:
        logging.error(f"Failed to send TTS response: {e}")

# Health check and utility endpoints
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "bold_wings_salon_phone",
        "active_calls": len(active_calls),
        "timestamp": datetime.now().isoformat()
    }

@app.get("/salon/services")
async def get_salon_services():
    """Get available salon services"""
    return SALON_SERVICES

@app.post("/recording-status")
async def recording_status_webhook(request: Request):
    """Handle recording status callback from Twilio"""
    form = await request.form()
    call_sid = form.get("CallSid")
    recording_url = form.get("RecordingUrl")
    recording_duration = form.get("RecordingDuration")
    call_duration = form.get("CallDuration")
    call_status = form.get("CallStatus")
    error_code = form.get("ErrorCode", "")
    
    # Log call completion with real-time tracking
    log_call_update("completed", call_sid, {
        'status': call_status,
        'duration': call_duration,
        'error_code': error_code,
        'notes': f"Call {call_status} completed"
    })
    
    # Update CRM metrics
    if call_sid in call_info_store:
        call_info = call_info_store[call_sid]
        call_info['duration_sec'] = int(call_duration) if call_duration else 0
        call_info['status'] = call_status
        call_info['recording_url'] = recording_url
        call_info['error_code'] = error_code
        
        # Track call in CRM
        salon_crm.track_call(call_info)
        
        # Determine call outcome for better tracking
        call_outcome = "completed"
        outcome_notes = f"Call {call_status} - Duration: {call_duration}s"
        
        if call_status == 'no-answer':
            call_outcome = "missed"
            outcome_notes = f"Missed call - No answer from dispatcher - Duration: {call_duration}s"
        elif call_status == 'busy':
            call_outcome = "busy"
            outcome_notes = f"Busy signal - Dispatcher line busy - Duration: {call_duration}s"
        elif call_status == 'failed':
            call_outcome = "failed"
            outcome_notes = f"Call failed - Error: {error_code} - Duration: {call_duration}s"
        elif call_status == 'canceled':
            call_outcome = "canceled"
            outcome_notes = f"Call canceled - Duration: {call_duration}s"
        
        # Update Google Sheets record with detailed call completion info
        if sheets_crm and sheets_crm.enabled:
            try:
                # Create detailed completion record
                completion_record = {
                    "timestamp": call_info.get('timestamp'),
                    "call_sid": call_sid,
                    "customer_name": "Unknown",
                    "phone": call_info.get('from', ''),
                    "call_status": call_outcome,
                    "call_duration": call_duration or "0",
                    "after_hours": str(not salon_crm._is_business_hours(datetime.fromisoformat(call_info.get('timestamp').replace('Z', '+00:00')))),
                    "service_requested": "Inbound Call",
                    "appointment_date": "",
                    "recording_url": recording_url or "",
                    "notes": outcome_notes,
                    "source": "phone_system",
                    "direction": "inbound",
                    "error_code": error_code or ""
                }
                sheets_crm.sync_booking(completion_record)
                logging.info(f"📊 Call {call_sid} {call_outcome} logged to Google Sheets")
            except Exception as e:
                logging.error(f"Failed to update Google Sheets: {e}")
        
        # Update CRM metrics based on call outcome with real-time logging
        if call_outcome == "completed":
            salon_crm.current_week_metrics['answered_calls'] += 1
            log_call_update("answered", call_sid, {
                'duration': call_duration,
                'notes': "Call successfully answered by dispatcher"
            })
        elif call_outcome == "missed":
            salon_crm.current_week_metrics['missed_calls'] += 1
            log_call_update("missed", call_sid, {
                'duration': call_duration,
                'notes': "Call missed - no answer from dispatcher",
                'error_code': error_code
            }, "warning")
        elif call_outcome == "busy":
            salon_crm.current_week_metrics['calls_dropped'] += 1
            log_call_update("busy", call_sid, {
                'duration': call_duration,
                'notes': "Call got busy signal from dispatcher",
                'error_code': error_code
            }, "warning")
        elif call_outcome == "failed":
            salon_crm.current_week_metrics['calls_dropped'] += 1
            log_call_update("failed", call_sid, {
                'duration': call_duration,
                'notes': f"Call failed with error: {error_code}",
                'error_code': error_code
            }, "error")
        elif call_outcome == "canceled":
            salon_crm.current_week_metrics['calls_dropped'] += 1
            log_call_update("canceled", call_sid, {
                'duration': call_duration,
                'notes': "Call was canceled"
            })

    
    return {"status": "ok"}

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

@app.get("/metrics")
async def get_metrics():
    """Get real-time metrics for the salon phone service"""
    try:
        # Get current metrics from CRM
        current_metrics = salon_crm.current_week_metrics
        
        # Calculate active calls (calls in progress)
        active_calls_count = len(active_calls) if 'active_calls' in globals() else 0
        
        # Get recent calls from call info store
        recent_calls = []
        for call_sid, call_info in list(call_info_store.items())[-10:]:  # Last 10 calls
            recent_calls.append({
                "call_sid": call_sid,
                "from": call_info.get('from', ''),
                "to": call_info.get('to', ''),
                "start_time": call_info.get('timestamp', ''),
                "status": call_info.get('status', 'unknown'),
                "duration_sec": call_info.get('duration_sec', 0),
                "answered": call_info.get('status') in ['completed', 'answered']
            })
        
        # Calculate SLA and other metrics
        total_calls = current_metrics.get('total_calls', 0)
        answered_calls = current_metrics.get('answered_calls', 0)
        missed_calls = current_metrics.get('missed_calls', 0)
        
        sla_percentage = (answered_calls / total_calls * 100) if total_calls > 0 else 0
        abandon_rate = (missed_calls / total_calls * 100) if total_calls > 0 else 0
        
        return {
            "activeCalls": active_calls,
            "totalCalls": total_calls,
            "answeredCalls": answered_calls,
            "abandonedCalls": missed_calls,
            "ahtSec": 0,  # Average handle time - would need to calculate from call durations
            "avgWaitSec": 0,  # Average wait time
            "abandonRate": abandon_rate,
            "sla": [{"date": datetime.now().strftime("%Y-%m-%d"), "value": sla_percentage}],
            "csat": [],  # Customer satisfaction - would need to implement
            "agents": [],  # Agent info - not applicable for salon
            "recentCalls": recent_calls,
            "timestamp": datetime.now().isoformat(),
            "aht": "00:00",  # Format as MM:SS
            "avgWait": "00:00"  # Format as MM:SS
        }
    except Exception as e:
        logging.error(f"Error getting metrics: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get metrics: {str(e)}")

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

# Function to log real-time call updates
def log_call_update(event_type, call_sid, details, status="info"):
    """Log call updates with real-time tracking"""
    timestamp = datetime.now().isoformat()
    log_message = f"[{event_type.upper()}] Call {call_sid} - {details}"
    
    # Log to call-specific logger
    if status == "error":
        call_logger.error(log_message)
    elif status == "warning":
        call_logger.warning(log_message)
    else:
        call_logger.info(log_message)
    
    # Also log to main logger
    logging.info(f"📞 {log_message}")
    
    # Log to Google Sheets if available
    if sheets_crm and sheets_crm.enabled:
        try:
            sheets_record = {
                "timestamp": timestamp,
                "call_sid": call_sid,
                "customer_name": "Unknown",
                "phone": details.get('from', ''),
                "call_status": event_type,
                "call_duration": details.get('duration', ''),
                "after_hours": details.get('after_hours', 'false'),
                "service_requested": "Real-time Update",
                "appointment_date": "",
                "recording_url": details.get('recording_url', ''),
                "notes": f"Real-time {event_type}: {details.get('notes', '')}",
                "source": "phone_system_realtime",
                "direction": "inbound",
                "error_code": details.get('error_code', '')
            }
            sheets_crm.sync_booking(sheets_record)
        except Exception as e:
            logging.error(f"Failed to log real-time update to sheets: {e}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("salon_phone_service:app", host="0.0.0.0", port=5001, reload=True)
