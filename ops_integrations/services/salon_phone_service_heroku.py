"""
Salon Phone Service - Bold Wings Hair Salon (Heroku Compatible)
Simplified version for Heroku deployment without heavy ML dependencies
"""

import asyncio
import json
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from collections import defaultdict

from fastapi import FastAPI, Request, BackgroundTasks, HTTPException
from fastapi.responses import Response
from fastapi.middleware.cors import CORSMiddleware
from twilio.twiml.voice_response import VoiceResponse
from twilio.rest import Client
from pydantic_settings import BaseSettings

# Import salon integration (without heavy ML)
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
        """Initialize SQLite database"""
        try:
            import sqlite3
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Create tables if they don't exist
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS customers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    phone TEXT UNIQUE NOT NULL,
                    email TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS appointments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    customer_id INTEGER,
                    service TEXT NOT NULL,
                    date TEXT NOT NULL,
                    time TEXT NOT NULL,
                    status TEXT DEFAULT 'scheduled',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (customer_id) REFERENCES customers (id)
                )
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS calls (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    call_sid TEXT UNIQUE NOT NULL,
                    from_number TEXT,
                    to_number TEXT,
                    status TEXT,
                    duration INTEGER,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            conn.commit()
            conn.close()
            logging.info("Database initialized successfully")
        except Exception as e:
            logging.error(f"Database initialization failed: {e}")
    
    def _is_business_hours(self, call_time: datetime) -> bool:
        """Check if call is during business hours"""
        weekday = call_time.weekday()
        if weekday not in self.business_hours or self.business_hours[weekday] is None:
            return False
        
        hour = call_time.hour
        start = self.business_hours[weekday]['start']
        end = self.business_hours[weekday]['end']
        
        return start <= hour < end
    
    def track_call(self, call_info: Dict[str, Any]):
        """Track call information"""
        try:
            import sqlite3
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT OR REPLACE INTO calls (call_sid, from_number, to_number, status, duration, timestamp)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                call_info.get('call_sid'),
                call_info.get('from'),
                call_info.get('to'),
                call_info.get('status', 'unknown'),
                call_info.get('duration_sec', 0),
                call_info.get('timestamp')
            ))
            
            conn.commit()
            conn.close()
            
            # Update metrics
            self.current_week_metrics['total_calls'] += 1
            
        except Exception as e:
            logging.error(f"Failed to track call: {e}")

class Settings(BaseSettings):
    """Settings for Heroku deployment"""
    # Twilio
    TWILIO_ACCOUNT_SID: str = ""
    TWILIO_AUTH_TOKEN: str = ""
    TWILIO_PHONE_NUMBER: str = ""
    
    # OpenAI
    OPENAI_API_KEY: str = ""
    
    # ElevenLabs TTS
    ELEVENLABS_API_KEY: str = ""
    ELEVENLABS_VOICE_ID: str = "kdmDKE6EkgrWrrykO9Qt"
    ELEVENLABS_MODEL_ID: str = "eleven_multilingual_v2"
    
    # Service endpoints
    VOICE_ENDPOINT: str = "/voice"
    MEDIA_ENDPOINT: str = "/media"
    
    # Other settings
    LOG_LEVEL: str = "INFO"
    DISPATCH_NUMBER: str = "+14693096560"

settings = Settings()

# Initialize clients
twilio_client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN) if settings.TWILIO_ACCOUNT_SID else None

# FastAPI app
app = FastAPI(title="Bold Wings Salon Phone Service - Heroku")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# Global state
call_info_store: Dict[str, Dict] = {}
active_calls: Dict[str, Any] = {}
salon_crm = HairstylingCRM()

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

# Setup logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Bold Wings Salon Phone Service - Heroku",
        "status": "running",
        "endpoints": {
            "health": "/health",
            "voice": "/voice",
            "metrics": "/metrics"
        }
    }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "service": "salon-phone-heroku",
        "twilio_configured": twilio_client is not None
    }

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
    
    # Log call start
    logging.info(f"📞 Incoming call {call_sid} from {call_info['from']} to {call_info['to']}")
    
    # Check if after hours
    call_time = datetime.now()
    is_after_hours = not salon_crm._is_business_hours(call_time)
    
    if is_after_hours:
        logging.info(f"📞 After-hours call {call_sid}")
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
    
    # Add a brief greeting before transferring
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
    
    logging.info(f"📞 Routing call {call_sid} to dispatcher: {settings.DISPATCH_NUMBER}")
    
    return Response(content=str(resp), media_type="application/xml")

@app.post("/status-callback")
async def status_callback(request: Request):
    """Handle call status updates from Twilio"""
    form = await request.form()
    call_sid = form.get("CallSid")
    call_status = form.get("CallStatus")
    call_duration = form.get("CallDuration")
    recording_url = form.get("RecordingUrl")
    error_code = form.get("ErrorCode")
    
    if not call_sid:
        return {"status": "error", "message": "CallSid required"}
    
    # Update call info
    if call_sid in call_info_store:
        call_info = call_info_store[call_sid]
        call_info['status'] = call_status
        call_info['duration_sec'] = int(call_duration) if call_duration else 0
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
        
        # Update CRM metrics based on call outcome
        if call_outcome == "completed":
            salon_crm.current_week_metrics['answered_calls'] += 1
            logging.info(f"📞 Call {call_sid} answered successfully")
        elif call_outcome == "missed":
            salon_crm.current_week_metrics['missed_calls'] += 1
            logging.warning(f"📞 Call {call_sid} missed")
        elif call_outcome in ["busy", "failed", "canceled"]:
            salon_crm.current_week_metrics['calls_dropped'] += 1
            logging.warning(f"📞 Call {call_sid} {call_outcome}")
    
    return {"status": "ok"}

@app.post("/recording-status")
async def recording_status(request: Request):
    """Handle recording status updates"""
    form = await request.form()
    call_sid = form.get("CallSid")
    recording_url = form.get("RecordingUrl")
    recording_status = form.get("RecordingStatus")
    
    logging.info(f"📹 Recording {recording_status} for call {call_sid}: {recording_url}")
    
    return {"status": "ok"}

@app.post("/no-answer")
async def no_answer(request: Request):
    """Handle when dispatcher doesn't answer"""
    form = await request.form()
    call_sid = form.get("CallSid")
    
    logging.warning(f"📞 No answer from dispatcher for call {call_sid}")
    
    # Create fallback response
    resp = VoiceResponse()
    resp.say("We're sorry, but our team is currently unavailable. Please leave a message with your name and phone number, and we'll call you back as soon as possible.")
    resp.record(
        action=f"{request.url.scheme}://{request.headers.get('host')}/voicemail",
        maxLength="60",
        playBeep="true"
    )
    
    return Response(content=str(resp), media_type="application/xml")

@app.post("/voicemail")
async def voicemail(request: Request):
    """Handle voicemail recordings"""
    form = await request.form()
    call_sid = form.get("CallSid")
    recording_url = form.get("RecordingUrl")
    
    logging.info(f"📹 Voicemail received for call {call_sid}: {recording_url}")
    
    resp = VoiceResponse()
    resp.say("Thank you for your message. We'll get back to you as soon as possible. Goodbye!")
    
    return Response(content=str(resp), media_type="application/xml")

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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("salon_phone_service_heroku:app", host="0.0.0.0", port=5001, reload=True)
