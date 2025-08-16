import asyncio
import os
import logging
import base64
from pyexpat.errors import messages
from dotenv import load_dotenv
from typing import Optional
from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect, BackgroundTasks
from fastapi.responses import JSONResponse, Response
from fastapi.middleware.cors import CORSMiddleware
import json
from pydantic_settings import BaseSettings, SettingsConfigDict
from twilio import twiml
from twilio.rest import Client
from twilio.twiml.voice_response import VoiceResponse, Start
import io
import wave
from openai import OpenAI
from collections import defaultdict
import re
# Replace direct relative imports with dual-mode imports (package + script fallback)
try:
    from .plumbing_services import (
        get_function_definition,
        infer_job_type_from_text,
        infer_multiple_job_types_from_text,
    )
    from core.job_booking import book_emergency_job, book_scheduled_job
    from adapters.external_services.google_calendar import CalendarAdapter
    from adapters.conversation_manager import ConversationManager
    # Import missing functions from adapters.phone
    from adapters.phone import (
        _finalize_call_metrics,
        pcm_to_wav_bytes,
        is_transfer_request,
        perform_dispatch_transfer,
        clean_and_filter_transcription,
        reset_unclear_attempts,
        contains_emergency_keywords,
        is_noise_or_unknown,
        streaming_watchdog,
    )
except Exception:
    import sys as _sys
    import os as _os
    _CURRENT_DIR = _os.path.dirname(__file__)
    _OPS_ROOT = _os.path.abspath(_os.path.join(_CURRENT_DIR, '..'))
    if _OPS_ROOT not in _sys.path:
        _sys.path.insert(0, _OPS_ROOT)
    from services.plumbing_services import (
        get_function_definition,
        infer_job_type_from_text,
        infer_multiple_job_types_from_text,
    )
    from core.job_booking import book_emergency_job, book_scheduled_job
    from adapters.external_services.google_calendar import CalendarAdapter
    from adapters.conversation_manager import ConversationManager
    # Import missing functions from adapters.phone
    from adapters.phone import (
        _finalize_call_metrics,
        pcm_to_wav_bytes,
        is_transfer_request,
        perform_dispatch_transfer,
        clean_and_filter_transcription,
        reset_unclear_attempts,
        contains_emergency_keywords,
        is_noise_or_unknown,
        streaming_watchdog,
    )
from datetime import datetime, timedelta, timezone
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
import struct
import time
import httpx

# Import prompt for intent classification
try:
    from ..prompts.prompt_layer import INTENT_CLASSIFICATION_PROMPT
except Exception:
    from prompts.prompt_layer import INTENT_CLASSIFICATION_PROMPT

# Try to import audioop for mu-law decoding and resampling; may be missing on some Python versions
try:
    import audioop as _audioop  # type: ignore
except Exception:
    _audioop = None

#---------------CONFIGURATION---------------
# Ensure .env is read from repo root (if present)
load_dotenv()

class Settings(BaseSettings):
    # Read .env by default (repo root). You can also export envs directly.
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")
    TWILIO_ACCOUNT_SID: str
    TWILIO_AUTH_TOKEN: str
    EXTERNAL_WEBHOOK_URL: str = os.getenv("EXTERNAL_WEBHOOK_URL", "http://localhost:5001")  # External URL for WebSocket (e.g., ngrok URL)
    SERVER_HOST: str = "0.0.0.0"
    SERVER_PORT: int = 5001
    SSL_CERT_FILE: Optional[str] = None
    SSL_KEY_PATH: Optional[str] = None
    STREAM_ENDPOINT: str = "/stream"
    VOICE_ENDPOINT: str = "/voice"
    LOG_LEVEL: str = "INFO"
    ELEVENLABS_API_KEY: Optional[str] = None
    ELEVENLABS_VOICE_ID: Optional[str] = None  # Set a default in env if desired
    ELEVENLABS_MODEL_ID: Optional[str] = None  # e.g. "eleven_multilingual_v2"
    FORCE_SAY_ONLY: bool = False  # Diagnostics: avoid TTS and use <Say>
    USE_ELEVENLABS_TTS: bool = True  # Control whether to use ElevenLabs (True) or OpenAI TTS (False)
    # OpenAI TTS Configuration - OPTIMIZED FOR SPEED
    OPENAI_TTS_SPEED: float = 1.5  # OPTIMIZED: Increased from 1.25 for faster responses (0.25 to 4.0)
    SPEECH_GATE_BUFFER_SEC: float = 0.3  # OPTIMIZED: Reduced from 1.0s for faster gate release
    # Confidence Thresholds
    TRANSCRIPTION_CONFIDENCE_THRESHOLD: float = -0.7  # Relaxed from -0.6 - allow more transcriptions through (-1.0 = normal, -0.5 = stricter)
    INTENT_CONFIDENCE_THRESHOLD: float = 0.5  # Increased from 0.4 - higher intent confidence requirement
    OVERALL_CONFIDENCE_THRESHOLD: float = 0.6  # Increased from 0.5 - higher overall confidence requirement
    CONFIDENCE_DEBUG_MODE: bool = True  # Enable detailed confidence logging
    # Consecutive Failure Thresholds
    CONSECUTIVE_INTENT_FAILURES_THRESHOLD: int = 2  # Number of consecutive intent confidence failures before handoff
    CONSECUTIVE_OVERALL_FAILURES_THRESHOLD: int = 2  # Number of consecutive overall confidence failures before handoff
    # Missing fields thresholds
    MISSING_FIELDS_PER_TURN_THRESHOLD: int = 2  # Number of critical fields missing in a single turn to count as a failure
    CONSECUTIVE_MISSING_FIELDS_FAILURES_THRESHOLD: int = 2  # Consecutive turns with missing fields before handoff
    # Magiclink integration
    MAGICLINK_API_BASE: str = os.getenv("MAGICLINK_API_BASE", "http://localhost:8000")
    MAGICLINK_APP_URL: str = os.getenv("MAGICLINK_APP_URL", "http://localhost:3000/location")
    MAGICLINK_ADMIN_API_KEY: Optional[str] = os.getenv("MAGICLINK_ADMIN_API_KEY")
    MAGICLINK_BYPASS_LOCATION: bool = True
    # Accept either TWILIO_SMS_FROM or TWILIO_FROM_NUMBER for convenience
    TWILIO_SMS_FROM: Optional[str] = os.getenv("TWILIO_SMS_FROM") or os.getenv("TWILIO_FROM_NUMBER")
    # Human dispatcher transfer number
    DISPATCH_NUMBER: str = os.getenv("DISPATCH_NUMBER", "+14693096560")

settings = Settings()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
# Transcription configuration
USE_LOCAL_WHISPER = False    # Set to False to use remote Whisper service
USE_REMOTE_WHISPER = True  # Set to True to use remote Whisper service
REMOTE_WHISPER_URL = os.getenv("REMOTE_WHISPER_URL", "https://ee7689bd1c73.ngrok-free.app")  # Configurable via .env

# Fallback to OpenAI Whisper if local not available
TRANSCRIPTION_MODEL = "whisper-1"  # Note: Remote service uses large-v3 (Whisper 3) for better performance
# Enhanced prompt for better transcription quality
FAST_TRANSCRIPTION_PROMPT = "Caller describing plumbing issue. Focus on clear human speech. Ignore background noise, dial tones, hangup signals, beeps, clicks, static, and other audio artifacts. Maintain natural speech patterns and context."

# VAD Configuration - OPTIMIZED FOR SPEED
VAD_AGGRESSIVENESS = 1  # Reduced from 3 - less aggressive filtering for better sensitivity
VAD_FRAME_DURATION_MS = 20  # Increased from 20ms - better accuracy for voice detection
SILENCE_TIMEOUT_SEC = 1.2  # OPTIMIZED: Reduced from 1.8s for faster responses
PROBLEM_DETAILS_SILENCE_TIMEOUT_SEC = 2.0  # OPTIMIZED: Reduced from 3.0s for faster responses
MIN_SPEECH_DURATION_SEC = 0.4  # OPTIMIZED: Reduced from 0.5s to capture shorter responses
CHUNK_DURATION_SEC = 3.5  # OPTIMIZED: Reduced from 4.0s for faster processing
PROBLEM_DETAILS_CHUNK_DURATION_SEC = 12.0  # OPTIMIZED: Reduced from 15.0s for faster processing
PREROLL_IGNORE_SEC = 0.1  # Increased from 0.4s - better initial speech detection
MIN_START_RMS = 85  # Reduced from 130 - more sensitive to quiet speech
FAST_RESPONSE_MODE = False  # Disabled - parallel processing with Whisper 1 could hurt performance

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
    'bot_speaking': False,  # NEW: Track when bot is outputting TTS
    'bot_speech_start_time': 0,  # NEW: When bot started speaking
    'speech_gate_active': False,  # NEW: Gate to block user speech processing
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
TWIML_PUSH_MIN_INTERVAL_SEC = 0.8  # OPTIMIZED: Reduced from 1.5s for faster updates
# Incrementing version per call to bust TwiML dedupe/caching for <Play>
tts_version_counter: dict[str, int] = {}

# Consecutive confidence failure tracking per call
consecutive_intent_failures: dict[str, int] = defaultdict(int)
consecutive_overall_failures: dict[str, int] = defaultdict(int)
consecutive_missing_fields_failures: dict[str, int] = defaultdict(int)

# NEW: Speech gate cycle tracking for comprehensive handoff detection
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

# Live Ops metrics aggregation and websocket clients
from collections import deque
ops_metrics_state = {
    "total_calls": 0,
    "answered_calls": 0,
    "abandoned_calls": 0,
    "handle_times_sec": [],            # durations of completed calls
    "answer_times_sec": [],            # time to first media since webhook start
    "call_history": deque(maxlen=200), # recent completed calls
}
ops_ws_clients: set[WebSocket] = set()

from twilio.twiml.voice_response import Gather

# Magiclink per-call state
magiclink_state: dict[str, dict] = {}

MAX_UNCLEAR_ATTEMPTS = 2

#---------------LOGGING SETUP---------------
logging.basicConfig(
    level=settings.LOG_LEVEL,
    format="%(asctime)s %(levelname)s %(name)s %(message)s"  
)
logger = logging.getLogger("voice-intent")

# Twilio REST client (safe init)
try:
    from twilio.base.exceptions import TwilioException as _TwilioException  # type: ignore
except Exception:
    class _TwilioException(Exception):
        pass

twilio_client: Optional[Client] = None
try:
    if settings.TWILIO_ACCOUNT_SID and settings.TWILIO_AUTH_TOKEN:
        twilio_client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
    else:
        logger.warning("Twilio disabled: missing TWILIO_ACCOUNT_SID/TWILIO_AUTH_TOKEN; SMS and TwiML updates will be skipped")
except Exception as e:
    logger.error(f"Twilio client init failed: {e}")
    twilio_client = None

# Initialize conversation manager for tracking clarification attempts
conversation_manager = ConversationManager()

logger.info(
    "env_loaded",
    extra={
        "evt": "env",
        "twilio_sid": bool(os.getenv("TWILIO_ACCOUNT_SID")),
        "twilio_from": bool(os.getenv("TWILIO_SMS_FROM") or os.getenv("TWILIO_FROM_NUMBER")),
    },
)

#---------------FASTAPI APP---------------
app = FastAPI(
    title="Unidirectional Media Stream API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)

# Add health check endpoint
@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

# Metrics snapshot computation and broadcast utilities (restored)

def _format_duration(seconds: float) -> str:
    try:
        seconds = max(0, int(seconds))
        m, s = divmod(seconds, 60)
        h, m = divmod(m, 60)
        if h:
            return f"{h:02d}:{m:02d}:{s:02d}"
        return f"{m:02d}:{s:02d}"
    except Exception:
        return "00:00"


def _compute_ops_snapshot() -> dict:
    try:
        active_calls = len(manager.active_connections) if 'manager' in globals() else 0
    except Exception:
        active_calls = 0
    total = int(ops_metrics_state.get("total_calls", 0))
    answered = int(ops_metrics_state.get("answered_calls", 0))
    abandoned = int(ops_metrics_state.get("abandoned_calls", 0))
    handle_times = list(ops_metrics_state.get("handle_times_sec", []))
    answer_times = list(ops_metrics_state.get("answer_times_sec", []))

    aht_sec = sum(handle_times) / len(handle_times) if handle_times else 0
    avg_wait_sec = sum(answer_times) / len(answer_times) if answer_times else 0
    abandon_rate = (abandoned / total * 100.0) if total else 0.0

    # Construct a lightweight recent-calls table
    recent = list(ops_metrics_state.get("call_history", []))

    # Build a simple SLA time series (percent answered within 20s per 10-min bucket)
    try:
        now_ts = time.time()
        window_seconds = 60 * 60  # last hour
        cutoff = now_ts - window_seconds
        buckets = {}
        for rec in recent:
            st = rec.get("start_ts", 0)
            if st < cutoff:
                continue
            bucket_min = int((st // 600) * 600)  # 10-min buckets
            b = buckets.setdefault(bucket_min, {"answered": 0, "within": 0})
            if rec.get("answered"):
                b["answered"] += 1
                ans = rec.get("answer_time_sec", None)
                if ans is not None and ans <= 20:
                    b["within"] += 1
        series = []
        for k in sorted(buckets.keys()):
            pct = 0
            if buckets[k]["answered"]:
                pct = int(100 * buckets[k]["within"] / buckets[k]["answered"])
            series.append({"date": datetime.fromtimestamp(k).strftime("%H:%M"), "value": pct})
    except Exception:
        series = []

    snapshot = {
        "activeCalls": active_calls,
        "totalCalls": total,
        "answeredCalls": answered,
        "abandonedCalls": abandoned,
        "ahtSec": aht_sec,
        "avgWaitSec": avg_wait_sec,
        "abandonRate": abandon_rate,
        "sla": series,
        "csat": [],  # Not tracked here
        "agents": [],  # Not tracked here
        "recentCalls": recent[-50:],
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "aht": _format_duration(aht_sec),
        "avgWait": _format_duration(avg_wait_sec),
    }
    return snapshot


async def _broadcast_ops_metrics():
    if not ops_ws_clients:
        return
    snapshot = _compute_ops_snapshot()
    disconnected = []
    for ws in list(ops_ws_clients):
        try:
            await ws.send_json({"type": "metrics", "data": snapshot})
        except WebSocketDisconnect:
            disconnected.append(ws)
        except Exception:
            disconnected.append(ws)
    for ws in disconnected:
        try:
            ops_ws_clients.discard(ws)
        except Exception:
            pass


async def _broadcast_transcript(call_sid: str, text: str):
    if not ops_ws_clients:
        return
    
    # Classify intent for the transcript text
    intent, intent_confidence = await classify_transcript_intent(text)
    
    payload = {
        "type": "transcript",
        "data": {
            "callSid": call_sid,
            "text": text,
            "intent": intent,
            "intent_confidence": intent_confidence,
            "timestamp": time.time()
        }
    }
    disconnected: list[WebSocket] = []
    for ws in list(ops_ws_clients):
        try:
            await ws.send_json(payload)
        except WebSocketDisconnect:
            disconnected.append(ws)
        except Exception:
            disconnected.append(ws)
    for ws in disconnected:
        try:
            ops_ws_clients.discard(ws)
        except Exception:
            pass


async def classify_transcript_intent(text: str) -> tuple[str, float]:
    """
    Classify the intent of a transcript text using parallel pattern matching and GPT classification.
    
    Returns:
        tuple: (intent_tag, confidence_score)
    """
    try:
        # Run pattern matching and GPT classification in parallel for speed
        pattern_task = asyncio.create_task(_calculate_pattern_confidence_async(text))
        gpt_task = asyncio.create_task(_gpt_classify_intent_async(text))
        
        # Wait for both to complete
        pattern_confidence, intent = await asyncio.gather(pattern_task, gpt_task)
        
        # Handle UNKNOWN intent
        if intent == "UNKNOWN":
            return "GENERAL_INQUIRY", 0.2
        
        # Validate that the intent is one we recognize
        from ..flows.intents import get_intent_tags
        valid_intents = get_intent_tags()
        if intent not in valid_intents:
            logger.debug(f"Unknown intent returned: {intent}, falling back to GENERAL_INQUIRY")
            intent = "GENERAL_INQUIRY"
        
        # Special handling for booking requests - boost confidence
        if intent == "BOOKING_REQUEST":
            # Booking requests should have high confidence when pattern matched
            final_confidence = max(final_confidence, 0.8)
            logger.info(f"🎯 Booking request detected with confidence {final_confidence:.3f}")
        
        # Calculate final confidence by combining pattern matching and GPT confidence
        pattern_conf = pattern_confidence.get(intent, 0.0)
        gpt_confidence = min(1.0, len(text.split()) / 10.0)  # Basic GPT confidence heuristic
        
        # Boost confidence when both methods agree
        if pattern_conf > 0.7:
            final_confidence = 0.9
        elif pattern_conf > 0.3:
            final_confidence = max(pattern_conf, gpt_confidence)
        else:
            final_confidence = gpt_confidence * 0.8  # Slight penalty for low pattern agreement
        
        if settings.CONFIDENCE_DEBUG_MODE:
            logger.info(f"🎯 Intent classification: '{intent}' with confidence {final_confidence:.3f}")
            logger.info(f"🔍 Pattern confidence: {pattern_confidence}")
            logger.info(f"🔍 GPT confidence: {gpt_confidence:.3f}")
            # Log the specific text being classified for debugging
            logger.info(f"📝 Text being classified: '{text}'")
        
        return intent, final_confidence
            
    except Exception as e:
        logger.debug(f"Error classifying transcript intent: {e}")
        return "GENERAL_INQUIRY", 0.2

async def _calculate_pattern_confidence_async(text: str) -> dict:
    """Async wrapper for pattern matching confidence calculation."""
    try:
        from ..flows.intents import load_intents
        intents_data = load_intents()
        return calculate_pattern_matching_confidence(text, intents_data)
    except Exception:
        return {}

async def _gpt_classify_intent_async(text: str) -> str:
    """Async GPT intent classification."""
    try:
        response = await asyncio.get_event_loop().run_in_executor(
            None, 
            lambda: client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": INTENT_CLASSIFICATION_PROMPT},
                    {"role": "user", "content": text}
                ],
                max_tokens=20,
                temperature=0.1
            )
        )
        return response.choices[0].message.content.strip().upper()
    except Exception:
        return "GENERAL_INQUIRY"

async def _parse_time_parallel(text: str) -> tuple[Optional[datetime], bool]:
    """Parse time and check for emergency keywords in parallel."""
    try:
        # Run both parsing operations concurrently
        time_task = asyncio.get_event_loop().run_in_executor(None, lambda: parse_human_datetime(text) or gpt_infer_datetime_phrase(text))
        emergency_task = asyncio.get_event_loop().run_in_executor(None, lambda: contains_emergency_keywords(text))
        
        explicit_time, explicit_emergency = await asyncio.gather(time_task, emergency_task)
        return explicit_time, explicit_emergency
    except Exception:
        return None, False


def calculate_pattern_matching_confidence(text: str, intents_data: dict) -> dict:
    """
    Calculate confidence scores for intent patterns using keyword and semantic matching.
    
    Returns:
        dict: {intent_tag: confidence_score}
    """
    text_lower = text.lower()
    confidence_scores = {}
    
    for intent in intents_data['intents']:
        intent_tag = intent['tag']
        patterns = intent['patterns']
        
        max_confidence = 0.0
        
        # Check for exact keyword matches (high confidence)
        for pattern in patterns:
            pattern_lower = pattern.lower()
            
            # Exact phrase match (highest confidence)
            if pattern_lower in text_lower:
                max_confidence = max(max_confidence, 0.95)
                logger.debug(f"🎯 Exact pattern match: '{pattern_lower}' in '{text_lower}' -> 0.95 confidence")
                continue
            
            # Partial phrase match (high confidence)
            if len(pattern_lower) > 3 and any(word in text_lower for word in pattern_lower.split()):
                # Check if key words from pattern are present
                pattern_words = pattern_lower.split()
                key_words = [w for w in pattern_words if len(w) > 2]  # Skip short words like "a", "an", "to"
                if key_words:
                    matches = sum(1 for word in key_words if word in text_lower)
                    if matches >= len(key_words) * 0.7:  # 70% of key words match
                        partial_confidence = 0.85
                        max_confidence = max(max_confidence, partial_confidence)
                        logger.debug(f"🎯 Partial pattern match: {matches}/{len(key_words)} key words from '{pattern_lower}' in '{text_lower}' -> {partial_confidence} confidence")
                        continue
            
            # Word overlap scoring (medium confidence)
            pattern_words = set(pattern_lower.split())
            text_words = set(text_lower.split())
            overlap = len(pattern_words.intersection(text_words))
            
            if overlap > 0:
                word_confidence = overlap / len(pattern_words)
                overlap_confidence = word_confidence * 0.75
                max_confidence = max(max_confidence, overlap_confidence)
                logger.debug(f"🎯 Word overlap: {overlap}/{len(pattern_words)} words from '{pattern_lower}' in '{text_lower}' -> {overlap_confidence} confidence")
        
        # Special handling for booking-related keywords
        if intent_tag == "BOOKING_REQUEST":
            booking_keywords = ["book", "schedule", "appointment", "booking", "prefer to book", "want to book", "need to book"]
            for keyword in booking_keywords:
                if keyword in text_lower:
                    booking_confidence = 0.9
                    max_confidence = max(max_confidence, booking_confidence)
                    logger.debug(f"🎯 Booking keyword match: '{keyword}' in '{text_lower}' -> {booking_confidence} confidence")
                    break
        
        # Try semantic similarity if available
        if max_confidence < 0.5:
            semantic_confidence = calculate_semantic_intent_confidence(text_lower, patterns)
            max_confidence = max(max_confidence, semantic_confidence)
        
        confidence_scores[intent_tag] = max_confidence
    
    return confidence_scores


# Global cached semantic model to avoid reloading
_semantic_model = None
_semantic_model_lock = asyncio.Lock()

def calculate_semantic_intent_confidence(text: str, patterns: list) -> float:
    """
    Calculate semantic similarity confidence using basic text similarity.
    
    Returns:
        float: Confidence score (0.0-1.0)
    """
    # Disable semantic matching entirely for now to improve performance
    # TODO: Re-enable with proper caching if needed
    logger.debug("Semantic matching disabled for performance - using word similarity fallback")
    
    try:
        # Fallback to simple word similarity
        text_words = set(text.lower().split())
        max_word_similarity = 0.0
        
        for pattern in patterns:
            pattern_words = set(pattern.lower().split())
            if len(pattern_words) > 0:
                similarity = len(text_words.intersection(pattern_words)) / len(pattern_words)
                max_word_similarity = max(max_word_similarity, similarity)
        
        return max_word_similarity * 0.6  # Lower confidence for word-only matching
        
    except Exception as e:
        logger.debug(f"Error in semantic intent confidence calculation: {e}")
        return 0.0


# New: broadcast job description to ops dashboard when booking is ready
async def _broadcast_job_description(call_sid: str, job_payload: dict):
    if not ops_ws_clients:
        return
    payload = {
        "type": "job_description",
        "data": {
            "callSid": call_sid,
            "job": job_payload,
            "ts": datetime.utcnow().isoformat() + "Z",
        },
    }
    disconnected: list[WebSocket] = []
    for ws in list(ops_ws_clients):
        try:
            await ws.send_json(payload)
        except WebSocketDisconnect:
            disconnected.append(ws)
        except Exception:
            disconnected.append(ws)
    for ws in disconnected:
        try:
            ops_ws_clients.discard(ws)
        except Exception:
            pass


@app.get("/metrics")
async def get_metrics_snapshot():
    return JSONResponse(content=_compute_ops_snapshot())


@app.websocket("/ops")
async def ops_metrics_ws(ws: WebSocket):
    await ws.accept()
    ops_ws_clients.add(ws)
    try:
        # Send initial snapshot
        await ws.send_json({"type": "metrics", "data": _compute_ops_snapshot()})
        # Keepalive loop; actual updates are pushed from call events
        while True:
            try:
                # Optional: receive ping/keepalive from client
                await asyncio.sleep(30)
                try:
                    await ws.send_json({"type": "keepalive", "ts": datetime.utcnow().isoformat() + "Z"})
                except Exception:
                    pass
            except WebSocketDisconnect:
                break
    finally:
        ops_ws_clients.discard(ws)

# Magiclink helper functions
async def _magiclink_mint_token(call_sid: str) -> dict:
    url = f"{settings.MAGICLINK_API_BASE}/tokens/location"
    async with httpx.AsyncClient(timeout=10) as http:
        r = await http.post(url, params={"sid": call_sid})
        r.raise_for_status()
        return r.json()

async def _magiclink_check_status(call_sid: str) -> bool:
    """Return True when bypass is enabled, otherwise check mocked confirmation."""
    # Temporary compliance bypass: auto-accept location when enabled
    if getattr(settings, "MAGICLINK_BYPASS_LOCATION", False):
        logger.info(f"🗺️ BYPASS: Location auto-confirmed for {call_sid}")
        return True
    state = magiclink_state.get(call_sid, {})
    # If this is a mocked session and user has confirmed, return True
    if state.get("mocked") and state.get("user_confirmed"):
        logger.info(f"🗺️ MOCK: Location confirmed for {call_sid}")
        return True
    # Otherwise return False (no location yet)
    return False

async def _send_magiclink_email(to_email: str, link: str) -> bool:
    """Send location verification link via SMTP email. Returns True if sent."""
    try:
        host = os.getenv("SMTP_HOST")
        port = int(os.getenv("SMTP_PORT", "587"))
        user = os.getenv("SMTP_USERNAME")
        password = os.getenv("SMTP_PASSWORD")
        from_email = os.getenv("SMTP_FROM") or user or "no-reply@safeharbour-plumbing.com"
        use_tls = (os.getenv("SMTP_USE_TLS", "true").lower() in ("1", "true", "yes"))
        if not host or not user or not password:
            logger.warning("SMTP not configured; skipping email fallback")
            return False
        subject = "SafeHarbour Plumbing: Location verification link"
        body = f"Please click this link to share your location so we can dispatch a technician: {link}\n\nIf you did not request this, you can ignore this email."
        def _send_sync() -> bool:
            import smtplib
            from email.message import EmailMessage
            msg = EmailMessage()
            msg["Subject"] = subject
            msg["From"] = from_email
            msg["To"] = to_email
            msg.set_content(body)
            with smtplib.SMTP(host, port, timeout=10) as smtp:
                if use_tls:
                    smtp.starttls()
                smtp.login(user, password)
                smtp.send_message(msg)
            return True
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _send_sync)
    except Exception as e:
        logger.error(f"Email fallback failed for {to_email}: {e}")
        return False

async def _send_magiclink_sms(call_sid: str) -> bool:
    """Deliver location verification link via SMS (ClickSend) with email fallback. Returns True if delivered."""
    try:
        token_resp = await _magiclink_mint_token(call_sid)
    except Exception as e:
        logger.error(f"Magiclink token mint failed: {e}")
        token_resp = {"token": f"mock_token_{call_sid}", "jti": f"mock_jti_{call_sid}", "exp": int(time.time()) + 3600, "mocked": True}
    token = token_resp.get("token") or token_resp.get("access_token") or f"mock_token_{call_sid}"
    link = f"{settings.MAGICLINK_APP_URL}?token={token}"
    call_info = call_info_store.get(call_sid, {})
    to_number = call_info.get("from")
    message_text = f"SafeHarbour: Please tap to share your location so we can dispatch a technician: {link}"

    # Attempt SMS via ClickSend (SMSAdapter)
    sms_ok = False
    try:
        try:
            from ..adapters.sms import SMSAdapter  # type: ignore
        except Exception:
            from adapters.sms import SMSAdapter  # type: ignore
        sms_adapter = SMSAdapter()
        if getattr(sms_adapter, 'enabled', False) and to_number:
            result = sms_adapter.send_sms(to_number, message_text)
            sms_ok = bool(result.get("success"))
            if sms_ok:
                logger.info(f"🔗 Magiclink SMS sent to {to_number}")
            else:
                logger.warning(f"Magiclink SMS failed for {to_number}: {result}")
        else:
            logger.info("SMSAdapter disabled or missing destination number; skipping SMS")
    except Exception as e:
        logger.error(f"Magiclink SMS send error: {e}")

    email_ok = False
    if not sms_ok:
        # Attempt email fallback using customer email from intent
        intent = call_dialog_state.get(call_sid, {}).get("intent", {})
        to_email = (intent.get("customer", {}) or {}).get("email")
        if to_email:
            email_ok = await _send_magiclink_email(to_email, link)
            if email_ok:
                logger.info(f"🔗 Magiclink email sent to {to_email}")
        else:
            logger.warning(f"No customer email available for {call_sid}; email fallback not possible")

    ok = sms_ok or email_ok
    try:
        st = magiclink_state.setdefault(call_sid, {})
        st["token"] = token
        st["sent"] = ok
        if token_resp.get("jti"):
            st["jti"] = token_resp.get("jti")
        if token_resp.get("exp"):
            st["exp"] = token_resp.get("exp")
        st["via"] = "sms" if sms_ok else ("email" if email_ok else "none")
        magiclink_state[call_sid] = st
    except Exception:
        pass
    return ok

# Operator-facing endpoints
@app.get("/magiclink/status/{call_sid}")
async def magiclink_status(call_sid: str):
    state = magiclink_state.get(call_sid, {})
    present = await _magiclink_check_status(call_sid)
    return {"sid": call_sid, "sent": bool(state.get("sent")), "operator_confirmed": bool(state.get("operator_confirmed")), "location_present": bool(present)}

@app.post("/magiclink/operator/confirm/{call_sid}")
async def magiclink_operator_confirm(call_sid: str, request: Request):
    # Optional API key enforcement
    api_key = request.headers.get("x-api-key")
    expected = os.getenv("MAGICLINK_OPERATOR_API_KEY") or settings.MAGICLINK_ADMIN_API_KEY
    if expected and api_key != expected:
        raise HTTPException(status_code=403, detail="forbidden")
    
    st = magiclink_state.setdefault(call_sid, {})
    st["operator_confirmed"] = True
    
    # Finalize booking and send confirmation to user
    finalized = await _finalize_booking_if_ready(call_sid)
    if finalized:
        # Send final confirmation message to user
        dialog = call_dialog_state.get(call_sid, {})
        intent = dialog.get('intent', {})
        suggested_time = dialog.get('suggested_time')
        
        if isinstance(suggested_time, datetime):
            time_str = _format_slot(suggested_time)
            confirmation_message = f"Thanks! Your appointment is confirmed for {time_str}. Thanks for choosing SafeHarbour Plumbing Services."
            
            # Create and send TwiML response
            twiml = VoiceResponse()
            await add_tts_or_say_to_twiml(twiml, call_sid, confirmation_message)
            
            # Update dialog state to post-booking Q&A
            call_dialog_state[call_sid] = {'intent': intent, 'step': 'post_booking_qa'}
            
            # Append stream resume
            start = Start()
            ws_base = call_info_store.get(call_sid, {}).get('ws_base')
            if ws_base:
                wss_url = f"{ws_base}{settings.STREAM_ENDPOINT}?callSid={call_sid}"
            else:
                if settings.EXTERNAL_WEBHOOK_URL.startswith('https://'):
                    wss_url = settings.EXTERNAL_WEBHOOK_URL.replace('https://', 'wss://') + settings.STREAM_ENDPOINT + f"?callSid={call_sid}"
                elif settings.EXTERNAL_WEBHOOK_URL.startswith('http://'):
                    wss_url = settings.EXTERNAL_WEBHOOK_URL.replace('http://', 'ws://') + settings.STREAM_ENDPOINT + f"?callSid={call_sid}"
                else:
                    wss_url = f"wss://{settings.EXTERNAL_WEBHOOK_URL}{settings.STREAM_ENDPOINT}?callSid={call_sid}"
            start.stream(url=wss_url, track="inbound_track")
            twiml.append(start)
            twiml.pause(length=3600)
            
            # Push to call
            await push_twiml_to_call(call_sid, twiml)
            logger.info(f"🎉 Sent final confirmation to user for {call_sid}")
    
    return {"sid": call_sid, "operator_confirmed": True, "finalized": finalized}

@app.post("/magiclink/send/{call_sid}")
async def magiclink_send(call_sid: str):
    ok = await _send_magiclink_sms(call_sid)
    if not ok:
        raise HTTPException(status_code=500, detail="failed to send magiclink")
    return {"status": "sent"}

@app.post("/twilio/sms/status")
async def twilio_sms_status(request: Request):
    form = await request.form()
    logger.info(
        f"SMS status callback: sid={form.get('MessageSid')} status={form.get('MessageStatus')} to={form.get('To')} error={form.get('ErrorCode')}"
    )
    return Response(status_code=204)

@app.post("/ops/action/approve")
async def ops_action_approve(request: Request):
    # Optional API key enforcement
    api_key = request.headers.get("x-api-key")
    expected = os.getenv("OPERATOR_ACTION_API_KEY") or settings.MAGICLINK_ADMIN_API_KEY
    if expected and api_key != expected:
        raise HTTPException(status_code=403, detail="forbidden")

    payload = await request.json()
    call_sid = payload.get("call_sid")
    if not call_sid:
        raise HTTPException(status_code=400, detail="missing_call_sid")

    appointment_iso = payload.get("appointment_iso")
    note = payload.get("note", "")
    try:
        if appointment_iso:
            try:
                # Support both Z and offset formats
                appt = datetime.fromisoformat(appointment_iso.replace("Z", "+00:00"))
            except Exception:
                raise HTTPException(status_code=400, detail="invalid_appointment_iso")
        else:
            appt = datetime.utcnow() + timedelta(hours=1)

        intent = call_dialog_state.get(call_sid, {}).get("intent", {})
        dialog = call_dialog_state.get(call_sid, {})
        customer = intent.get("customer", {})
        job = intent.get("job", {})
        location = intent.get("location", {})

        phone = customer.get("phone") or call_info_store.get(call_sid, {}).get("from") or ""
        # Get customer name from dialog state (where it's actually stored)
        name = dialog.get("customer_name") or customer.get("name") or "Customer"
        service = job.get("type") or "Plumbing Service"
        address = location.get("raw_address") or ""

        # Store operator note
        st = call_info_store.setdefault(call_sid, {})
        if note:
            st["operator_note"] = note
            call_info_store[call_sid] = st

        result = book_scheduled_job(
            phone=phone,
            name=name,
            service=service,
            appointment_time=appt,
            address=address,
            notes=note,
        )
        # Sync to Google Sheets CRM (mock or live)
        try:
            from .sheets import GoogleSheetsCRM  # type: ignore
        except Exception:
            try:
                from ops_integrations.adapters.external_services.sheets import GoogleSheetsCRM  # type: ignore
            except Exception:
                from adapters.external_services.sheets import GoogleSheetsCRM  # type: ignore
        sheets = GoogleSheetsCRM()
        booking_row = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "call_sid": call_sid,
            "customer_name": name,
            "phone": phone,
            "service_type": service,
            "appointment_time_iso": appt.isoformat() + ("" if appt.tzinfo else "Z"),
            "address": address,
            "notes": note,
            "operator_note": note,
            "source": "operator_confirmed",
            "city": call_info_store.get(call_sid, {}).get("from_city"),
            "state": call_info_store.get(call_sid, {}).get("from_state"),
            "zip": call_info_store.get(call_sid, {}).get("from_zip"),
            "direction": call_info_store.get(call_sid, {}).get("direction"),
            "caller_name": call_info_store.get(call_sid, {}).get("caller_name"),
        }
        try:
            sync_res = sheets.sync_booking(booking_row)
            logger.info(f"Sheets CRM sync on approve: {sync_res}")
        except Exception as _e:
            logger.debug(f"Sheets CRM sync skipped/failed: {_e}")
        
        # Send appointment confirmation to frontend calendar
        try:
            await _send_appointment_confirmation_to_frontend(call_sid, name, service, appt, address, phone)
        except Exception as e:
            logger.debug(f"Failed to send appointment confirmation to frontend: {e}")
        
        return JSONResponse(content={"ok": True, "result": result})
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Approve action failed for {call_sid}: {e}")
        raise HTTPException(status_code=500, detail="approve_failed")


@app.post("/ops/action/override")
async def ops_action_override(request: Request):
    api_key = request.headers.get("x-api-key")
    expected = os.getenv("OPERATOR_ACTION_API_KEY") or settings.MAGICLINK_ADMIN_API_KEY
    if expected and api_key != expected:
        raise HTTPException(status_code=403, detail="forbidden")

    payload = await request.json()
    call_sid = payload.get("call_sid")
    if not call_sid:
        raise HTTPException(status_code=400, detail="missing_call_sid")
    reason = payload.get("reason", "")

    try:
        st = call_info_store.setdefault(call_sid, {})
        st["operator_override_reason"] = reason
        call_info_store[call_sid] = st
        return JSONResponse(content={"ok": True})
    except Exception as e:
        logger.error(f"Override action failed for {call_sid}: {e}")
        raise HTTPException(status_code=500, detail="override_failed")


@app.post("/ops/action/handoff")
async def ops_action_handoff(request: Request):
    api_key = request.headers.get("x-api-key")
    expected = os.getenv("OPERATOR_ACTION_API_KEY") or settings.MAGICLINK_ADMIN_API_KEY
    if expected and api_key != expected:
        raise HTTPException(status_code=403, detail="forbidden")

    payload = await request.json()
    call_sid = payload.get("call_sid")
    if not call_sid:
        raise HTTPException(status_code=400, detail="missing_call_sid")
    reason = payload.get("reason", "")

    try:
        st = call_info_store.setdefault(call_sid, {})
        st["handoff_requested"] = True
        if reason:
            st["handoff_reason"] = reason
        call_info_store[call_sid] = st
        return JSONResponse(content={"ok": True})
    except Exception as e:
        logger.error(f"Handoff action failed for {call_sid}: {e}")
        raise HTTPException(status_code=500, detail="handoff_failed")

# Send appointment confirmation to frontend calendar
async def _send_appointment_confirmation_to_frontend(call_sid: str, customer_name: str, service_type: str, appointment_time: datetime, address: str, phone: str) -> None:
    """Send appointment confirmation to frontend calendar via WebSocket"""
    try:
        # Normalize appointment time to ISO format
        appt_iso = appointment_time.isoformat()
        if not appt_iso.endswith('Z') and '+' not in appt_iso:
            appt_iso = appt_iso + 'Z'
        
        # Create calendar event payload
        event_payload = {
            "id": f"appointment_{call_sid}",
            "title": f"{service_type} - {customer_name}",
            "start": appt_iso,
            "end": (appointment_time + timedelta(hours=2)).isoformat() + ("" if appointment_time.tzinfo else "Z"),
            "customer_name": customer_name,
            "service_type": service_type,
            "address": address,
            "phone": phone,
            "call_sid": call_sid,
            "backgroundColor": "#10b981",  # Green color for confirmed appointments
            "borderColor": "#059669",
            "textColor": "#ffffff"
        }
        
        payload = {
            "type": "appointment_confirmed",
            "data": {
                "callSid": call_sid,
                "event": event_payload,
                "ts": datetime.utcnow().isoformat() + "Z",
            },
        }
        
        # Broadcast to all connected ops WebSocket clients
        if ops_ws_clients:
            disconnected = set()
            for ws in ops_ws_clients:
                try:
                    await ws.send_json(payload)
                except Exception as e:
                    logger.debug(f"Failed to send appointment confirmation to ops client: {e}")
                    disconnected.add(ws)
            # Clean up disconnected clients
            for ws in disconnected:
                ops_ws_clients.discard(ws)
        
        logger.info(f"📅 Sent appointment confirmation to frontend calendar for {call_sid}")
        
    except Exception as e:
        logger.error(f"Failed to send appointment confirmation to frontend for {call_sid}: {e}")

# Send booking confirmation to operator frontend
async def _send_booking_to_operator(call_sid: str, intent: dict, suggested_time: datetime) -> None:
    """Send booking confirmation to operator frontend via WebSocket"""
    try:
        call_info = call_info_store.get(call_sid, {})
        customer = intent.get('customer', {})
        job = intent.get('job', {})
        location = intent.get('location', {})
        customer_phone = customer.get('phone') or call_info.get('from', '')
        
        # Normalize job payload to match frontend expectation
        appt_iso = suggested_time.isoformat()
        if not appt_iso.endswith('Z') and '+' not in appt_iso:
            appt_iso = appt_iso + 'Z'
        job_payload = {
            "customer_phone": customer.get('phone') or call_info.get('from', ''),
            "customer_name": customer.get('name') or 'Customer',
            "service_type": job.get('type') or 'plumbing_service',
            "appointment_time": appt_iso,
            "address": location.get('raw_address') or f"{call_info.get('from_city', '')}, {call_info.get('from_state', '')}",
            "notes": job.get('description', '') or '',
        }
        payload = {
            "type": "job_description",
            "data": {
                "callSid": call_sid,
                "job": job_payload,
                "ts": datetime.utcnow().isoformat() + "Z",
            },
        }
        
        # Broadcast to all connected ops WebSocket clients
        if ops_ws_clients:
            disconnected = set()
            for ws in ops_ws_clients:
                try:
                    await ws.send_json(payload)
                except Exception as e:
                    logger.debug(f"Failed to send booking to ops client: {e}")
                    disconnected.add(ws)
            # Clean up disconnected clients
            for ws in disconnected:
                ops_ws_clients.discard(ws)
        
        logger.info(f"📤 Sent booking confirmation to {len(ops_ws_clients)} operator client(s)")
        
    except Exception as e:
        logger.error(f"Failed to send booking to operator for {call_sid}: {e}")

# Booking finalization helper
async def _finalize_booking_if_ready(call_sid: str) -> bool:
    try:
        st = magiclink_state.get(call_sid, {})
        operator_ok = bool(st.get("operator_confirmed"))
        # user_ok = await _magiclink_check_status(call_sid)
        # if not (operator_ok and user_ok):
        #     return False
        # TEMP: proceed if operator confirmed, regardless of user/location status
        if not operator_ok:
            return False
        dialog = call_dialog_state.get(call_sid, {})
        intent = dialog.get('intent', {})
        suggested_time = dialog.get('suggested_time')
        job_type = intent.get('job', {}).get('type', 'a plumbing issue')
        customer = intent.get('customer', {})
        phone = customer.get('phone') or call_info_store.get(call_sid, {}).get('from') or ''
        name = customer.get('name') or 'Customer'
        address = intent.get('location', {}).get('raw_address')
        notes = intent.get('job', {}).get('description', '')
        if suggested_time is None:
            return False

        # Prepare job description for frontend drawer
        appt_iso = suggested_time.isoformat()
        if not appt_iso.endswith('Z') and '+' not in appt_iso:
            appt_iso = appt_iso + 'Z'
        job_payload = {
            "customer_phone": phone,
            "customer_name": name,
            "service_type": job_type,
            "appointment_time": appt_iso,
            "address": address or '',
            "notes": notes or '',
        }
        # Notify ops dashboards
        try:
            await _broadcast_job_description(call_sid, job_payload)
        except Exception:
            pass

        book_scheduled_job(
            phone=phone,
            name=name,
            service=job_type,
            appointment_time=suggested_time,
            address=address or '',
            notes=notes,
        )
        # Sync booking to Google Sheets (mock or live)
        try:
            from .adapters.external_services.sheets import GoogleSheetsCRM  # type: ignore
        except Exception:
            from adapters.external_services.sheets import GoogleSheetsCRM  # type: ignore
        sheets = GoogleSheetsCRM()
        appt_iso = suggested_time.isoformat()
        if not appt_iso.endswith('Z') and '+' not in appt_iso:
            appt_iso = appt_iso + 'Z'
        row = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "call_sid": call_sid,
            "customer_name": name,
            "phone": phone,
            "service_type": job_type,
            "appointment_time_iso": appt_iso,
            "address": address or '',
            "notes": notes or '',
            "operator_note": (call_info_store.get(call_sid, {}) or {}).get("operator_note"),
            "source": "operator_confirmed",
            "city": (call_info_store.get(call_sid, {}) or {}).get("from_city"),
            "state": (call_info_store.get(call_sid, {}) or {}).get("from_state"),
            "zip": (call_info_store.get(call_sid, {}) or {}).get("from_zip"),
            "direction": (call_info_store.get(call_sid, {}) or {}).get("direction"),
            "caller_name": (call_info_store.get(call_sid, {}) or {}).get("caller_name"),
        }
        try:
            sync_res = sheets.sync_booking(row)
            logger.info(f"Sheets CRM sync on finalize: {sync_res}")
        except Exception as _e:
            logger.debug(f"Sheets CRM sync skipped/failed: {_e}")
        
        # Send appointment confirmation to frontend calendar
        try:
            await _send_appointment_confirmation_to_frontend(call_sid, name, job_type, suggested_time, address or '', phone)
        except Exception as e:
            logger.debug(f"Failed to send appointment confirmation to frontend: {e}")
        
        logger.info(f"Booking finalized for {call_sid}")
        return True
    except Exception as e:
        logger.error(f"Finalize booking failed for {call_sid}: {e}")
        return False

#---------------METRICS & WS (unchanged code below)---------------
# ... existing code ...

# Add endpoint to serve synthesized TTS audio for Twilio <Play>
@app.get("/tts/{call_sid}.mp3")
async def serve_tts(call_sid: str):
    audio = tts_audio_store.get(call_sid)
    if not audio:
        raise HTTPException(status_code=404, detail="TTS not found")
    return Response(content=audio, media_type="audio/mpeg")

# Add test endpoint for ngrok verification
@app.get("/")
async def root():
    return {"message": "SafeHarbour Plumbing Voice Service", "status": "running"}

# Serve last TwiML as a fallback via URL fetch (Twilio update url=...)
@app.get("/twiml/{call_sid}")
async def serve_twiml(call_sid: str):
    xml = last_twiml_store.get(call_sid)
    if not xml:
        raise HTTPException(status_code=404, detail="No TwiML available")
    return Response(content=xml, media_type="application/xml")

#---------------VOICE WEBHOOK---------------
# Helper to build WSS URL from incoming request host/proto, with safe fallbacks
def _build_wss_url_from_request(request: Request, call_sid: str, caller_number: str = None) -> tuple[str, str]:
    try:
        hdrs = request.headers
        host = hdrs.get('x-forwarded-host') or hdrs.get('host')
        proto = (hdrs.get('x-forwarded-proto') or request.url.scheme or 'https').lower()
        ws_scheme = 'wss' if proto == 'https' else 'ws'
        if host:
            ws_base = f"{ws_scheme}://{host}"
            wss_url = f"{ws_base}{settings.STREAM_ENDPOINT}?callSid={call_sid}"
            if caller_number:
                wss_url += f"&From={caller_number}"
            return ws_base, wss_url
    except Exception:
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
    return ws_base, wss_url

# Helper to build WebSocket URL for resuming streams (uses existing call info)
def _build_wss_url_for_resume(call_sid: str) -> str:
    """Build WebSocket URL for resuming streams, using existing call info for caller number"""
    call_info = call_info_store.get(call_sid, {})
    ws_base = call_info.get('ws_base')
    caller_number = call_info.get('from')
    
    if ws_base:
        wss_url = f"{ws_base}{settings.STREAM_ENDPOINT}?callSid={call_sid}"
        if caller_number:
            wss_url += f"&From={caller_number}"
        return wss_url
    else:
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
        return wss_url

@app.post(settings.VOICE_ENDPOINT)
async def voice_webhook(request: Request):
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
    
    # Compute per-call WebSocket base from the inbound request (robust to ngrok URL changes)
    caller_number = form.get("From")
    ws_base, wss_url = _build_wss_url_from_request(request, call_sid, caller_number)
    call_info["ws_base"] = ws_base
    
    # Store call information for use during the call
    call_info_store[call_sid] = call_info

    # Update ops metrics on call arrival
    try:
        ops_metrics_state["total_calls"] = int(ops_metrics_state.get("total_calls", 0)) + 1
    except Exception:
        ops_metrics_state["total_calls"] = 1
    # Broadcast new snapshot (activeCalls will reflect connection once established)
    try:
        asyncio.create_task(_broadcast_ops_metrics())
    except Exception:
        pass

    # Log the call start with key details
    logger.info(f"📞 CALL STARTED - {call_sid}")
    logger.info(f"   📱 From: {call_info['from']} ({call_info['from_city']}, {call_info['from_state']})")
    logger.info(f"   📞 To: {call_info['to']} ({call_info['to_city']}, {call_info['to_state']})")
    logger.info(f"   🌍 Direction: {call_info['direction']}")
    logger.info(f"   📊 Status: {call_info['call_status']}")
    logger.info(f"   🌐 WS Base: {ws_base}")
    if call_info['caller_name']:
        logger.info(f"   👤 Caller: {call_info['caller_name']}")
    if call_info['forwarded_from']:
        logger.info(f"   ↩️  Forwarded from: {call_info['forwarded_from']}")

    #Build TwiML Response
    resp = VoiceResponse()
    # Greet first and collect name, then start streaming so listening begins after the message
    greet_text = "Hello, thank you for trusting SafeHarbour Plumbing Services for your plumbing issues. Who do I have the pleasure of speaking with?"
    logger.info(f"🗣️ TTS SAY (greeting) for CallSid={call_sid}: {greet_text}")
    # Use TTS helper so greeting benefits from ElevenLabs if configured
    await add_tts_or_say_to_twiml(resp, call_sid, greet_text)
    
    # Set initial dialog state to collect name
    call_dialog_state[call_sid] = {'step': 'awaiting_name'}
    start = Start()
    start.stream(url=wss_url, track="inbound_track")
    resp.append(start)
    resp.pause(length=3600)
    logger.info(f"🎯 Stream will start after greeting for call {call_sid}")
    logger.info(f"🔗 WebSocket URL generated: {wss_url}")
    logger.debug(f"📄 TwiML Response: {str(resp)}")

    # Watchdog: if no media arrives shortly, re-push TwiML to ensure streaming
    try:
        asyncio.create_task((call_sid))
    except Exception as e:
        logger.debug(f"Failed to schedule streaming watchdog for {call_sid}: {e}")

    return Response(content=str(resp), media_type="application/xml")

#---------------MEDIA STREAM HANDLER---------------
class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[str, WebSocket] = {}

    async def connect(self, call_sid: str, websocket: WebSocket):
        await websocket.accept()
        self.active_connections[call_sid] = websocket
        logger.info(f"WebSocket connection established for CallSid={call_sid}")

    async def disconnect(self, call_sid: str):
            ws = self.active_connections.pop(call_sid, None)
            if ws:
                try:
                    await ws.close()
                    logger.info(f"WebSocket connection closed for CallSid={call_sid}")
                except Exception as e:
                    logger.debug(f"Error closing WebSocket for CallSid={call_sid}: {e}")
            
            # Clean up VAD state and audio buffers
            vad_states.pop(call_sid, None)
            audio_buffers.pop(call_sid, None)
            call_dialog_state.pop(call_sid, None)
            call_info_store.pop(call_sid, None)
            audio_config_store.pop(call_sid, None)
            tts_audio_store.pop(call_sid, None)
            last_twiml_store.pop(call_sid, None)
            # Clean up consecutive failure tracking
            consecutive_intent_failures.pop(call_sid, None)
            consecutive_overall_failures.pop(call_sid, None)
            consecutive_missing_fields_failures.pop(call_sid, None)
            # Clean up speech gate cycle tracking
            speech_gate_cycle_tracking.pop(call_sid, None)
            # Clean up speech gate state
            if call_sid in vad_states:
                vad_states[call_sid]['speech_gate_active'] = False
                vad_states[call_sid]['bot_speaking'] = False
            logger.debug(f"Cleaned up resources for CallSid={call_sid}")

    async def receive_loop(self, call_sid: str):
        ws = self.active_connections.get(call_sid)
        if not ws:
            return
        try:
            while True:
                msg = await ws.receive_text()
                asyncio.create_task(handle_media_packet(call_sid, msg))
        except WebSocketDisconnect:
                await self.disconnect(call_sid)
            
manager = ConnectionManager()

@app.websocket(settings.STREAM_ENDPOINT)
async def media_stream_ws(ws: WebSocket):
    await ws.accept()
    call_sid: Optional[str] = None
    caller_number: Optional[str] = None
    temporary_stream_key: Optional[str] = None
    try:
        # Try to extract CallSid from query params (Twilio may pass it)
        call_sid = ws.query_params.get("callSid")
        caller_number = ws.query_params.get("From")
        logger.info(f"WebSocket connection accepted for potential CallSid={call_sid}")
        logger.info(f"All query params: {dict(ws.query_params)}")
        logger.info(f"WebSocket URL: {ws.url}")
        logger.info(f"Caller number: {caller_number}")

        # If not present, wait for 'start' event which contains callSid
        if not call_sid:
            logger.info("CallSid not in query params, waiting for 'start' event from Twilio...")
            handshake_deadline = time.time() + 10.0
            while time.time() < handshake_deadline and not call_sid:
                msg = await ws.receive_text()
                logger.debug(f"Init/handshake message received: {msg[:200]}...")
                try:
                    data = json.loads(msg)
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse handshake message as JSON: {e}")
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
                    logger.info(f"Media format for {call_sid}: {audio_config_store.get(call_sid)}")
                    if not call_sid and stream_sid:
                        temporary_stream_key = f"stream:{stream_sid}"
                        manager.active_connections[temporary_stream_key] = ws
                        logger.warning(f"Using streamSid as temporary key before CallSid is available: {temporary_stream_key}")
                    if call_sid:
                        manager.active_connections[call_sid] = ws
                        logger.info(f"✅ CallSid found in start event: {call_sid}")
                        
                        # Update call info with caller number if we extracted it from query params
                        if caller_number and call_sid in call_info_store:
                            call_info = call_info_store[call_sid]
                            if not call_info.get('from') or call_info.get('from') != caller_number:
                                call_info['from'] = caller_number
                                call_info_store[call_sid] = call_info
                                logger.info(f"📱 Updated caller number for {call_sid}: {caller_number}")
                        
                        # Process this start packet too
                        asyncio.create_task(handle_media_packet(call_sid, msg))
                        break
                    else:
                        logger.error("Start event received but no callSid present.")
                        continue
                # Edge case: media before start
                possible_call_sid = data.get("callSid") or data.get("CallSid")
                if possible_call_sid:
                    call_sid = possible_call_sid
                    manager.active_connections[call_sid] = ws
                    logger.info(f"✅ CallSid found outside start event: {call_sid}")
                    
                    # Update call info with caller number if we extracted it from query params
                    if caller_number and call_sid in call_info_store:
                        call_info = call_info_store[call_sid]
                        if not call_info.get('from') or call_info.get('from') != caller_number:
                            call_info['from'] = caller_number
                            call_info_store[call_sid] = call_info
                            logger.info(f"📱 Updated caller number for {call_sid}: {caller_number}")
                    
                    asyncio.create_task(handle_media_packet(call_sid, msg))
                    break
                stream_sid = data.get("streamSid") or (data.get("start") or {}).get("streamSid")
                if stream_sid and not temporary_stream_key:
                    temporary_stream_key = f"stream:{stream_sid}"
                    manager.active_connections[temporary_stream_key] = ws
                    logger.warning(f"Temporarily storing connection with key {temporary_stream_key} until CallSid arrives...")
                    continue
            if not call_sid:
                logger.warning("Missing CallSid after waiting for start event")
                await ws.close(code=1008, reason="Missing CallSid parameter")
                return
        # Ensure registration when callSid came via query
        if call_sid not in manager.active_connections:
            manager.active_connections[call_sid] = ws
            logger.info(f"WebSocket connection established for CallSid={call_sid}")
            
            # Update call info with caller number if we extracted it from query params
            if caller_number and call_sid in call_info_store:
                call_info = call_info_store[call_sid]
                if not call_info.get('from') or call_info.get('from') != caller_number:
                    call_info['from'] = caller_number
                    call_info_store[call_sid] = call_info
                    logger.info(f"📱 Updated caller number for {call_sid}: {caller_number}")

        # Push updated metrics for active call count
        try:
            await _broadcast_ops_metrics()
        except Exception:
            pass

        # Main receive loop
        while True:
            msg = await ws.receive_text()
            asyncio.create_task(handle_media_packet(call_sid, msg))

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for CallSid={call_sid}")
    except Exception as e:
        logger.error(f"WebSocket error for CallSid={call_sid}: {e}")
        try:
            await ws.close(code=1011, reason="Internal server error")
        except Exception:
            pass
    finally:
        # Finalize metrics and cleanup
        try:
            if call_sid:
                _finalize_call_metrics(call_sid)
        except Exception:
            pass
        try:
            await _broadcast_ops_metrics()
        except Exception:
            pass
        if call_sid:
            tts_version_counter.pop(call_sid, None)
            # Clean up consecutive failure tracking
            consecutive_intent_failures.pop(call_sid, None)
            consecutive_overall_failures.pop(call_sid, None)
            consecutive_missing_fields_failures.pop(call_sid, None)
            # Clean up speech gate cycle tracking
            speech_gate_cycle_tracking.pop(call_sid, None)
            await manager.disconnect(call_sid)

#---------------MEDIA PROCESSING---------------
async def handle_media_packet(call_sid: str, msg: str):
    try:
        packet = json.loads(msg)
    except Exception as e:
        logger.error(f"Invalid JSON in media packet for CallSid={call_sid}: {e}")
        return

    event = packet.get("event")
    if event == "start":
        logger.info(f"📞 Media stream STARTED for {call_sid}: {packet.get('start', {})}")
        # Track stream start time for preroll suppression
        state = vad_states[call_sid]
        state['stream_start_time'] = time.time()
    elif event == "media":
        payload_b64 = packet["media"]["payload"]
        # Log first media frame and update heartbeat
        try:
            state = vad_states[call_sid]
            if not state.get('has_received_media'):
                state['has_received_media'] = True
                # Mark first media for metrics (answer time)
                info = call_info_store.get(call_sid, {})
                if not info.get('first_media_ts'):
                    first_ts = time.time()
                    info['first_media_ts'] = first_ts
                    call_info_store[call_sid] = info
                    try:
                        ops_metrics_state["answered_calls"] = int(ops_metrics_state.get("answered_calls", 0)) + 1
                    except Exception:
                        ops_metrics_state["answered_calls"] = 1
                    try:
                        start_ts = float(info.get('start_ts') or first_ts)
                        ops_metrics_state["answer_times_sec"].append(max(0.0, first_ts - start_ts))
                    except Exception:
                        pass
                    try:
                        asyncio.create_task(_broadcast_ops_metrics())
                    except Exception:
                        pass
                logger.info(f"🎧 Listening active for {call_sid} (first media frame)")
            if call_sid in call_info_store:
                call_info_store[call_sid]['last_media_time'] = time.time()
        except Exception:
            pass
        try:
            pcm16_bytes = convert_media_payload_to_pcm16(call_sid, payload_b64)
            logger.debug(f"📨 Media packet received for {call_sid}: {len(pcm16_bytes)} bytes (PCM16)")
            await process_audio(call_sid, pcm16_bytes)
        except Exception as e:
            logger.error(f"Media decode error for {call_sid}: {e}")
    elif event == "stop":
        logger.info(f"📞 Media stream STOPPED for {call_sid}")
        # Process any remaining audio when stream stops
        vad_state = vad_states.get(call_sid)
        if vad_state and vad_state['is_speaking'] and len(vad_state['pending_audio']) > 0:
            logger.info(f"🎤 Processing final speech segment for {call_sid} on stream stop")
            await process_speech_segment(call_sid, vad_state['pending_audio'])
        # Finalize call metrics before cleanup
        try:
            _finalize_call_metrics(call_sid)
            await _broadcast_ops_metrics()
        except Exception:
            pass
        await manager.disconnect(call_sid)
    elif event == "connected":
        logger.debug(f"🔌 Media WebSocket connected event for {call_sid}")
    else:
        logger.warning(f"❓ Unknown event: '{event}' for CallSid={call_sid}")

# Utility: convert Twilio media payload to PCM16 bytes
def _mulaw_byte_to_linear16(mu: int) -> int:
    mu = ~mu & 0xFF
    sign = mu & 0x80
    exponent = (mu >> 4) & 0x07
    mantissa = mu & 0x0F
    sample = ((mantissa << 3) + 132) << exponent
    sample = sample - 132
    if sign:
        sample = -sample
    # Clamp to int16
    if sample > 32767:
        sample = 32767
    if sample < -32768:
        sample = -32768
    return sample

def mulaw_to_pcm16(mu_bytes: bytes) -> bytes:
    if _audioop is not None:
        return _audioop.ulaw2lin(mu_bytes, 2)
    # Pure Python fallback
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
    # Already PCM16 (audio/l16)
    return raw_bytes

#---------------ASR/INTENT & FOLLOW-UPS (STUBS) ---------------
FUNCTIONS = [get_function_definition()]

async def process_audio(call_sid: str, audio: bytes):
    """Enhanced audio processing with Voice Activity Detection (VAD)"""
    vad_state = vad_states[call_sid]
    vad = vad_state['vad']
    current_time = time.time()
    sample_rate = audio_config_store.get(call_sid, {}).get('sample_rate', SAMPLE_RATE_DEFAULT)
    stream_start_time = vad_state.get('stream_start_time', current_time)
    
    # Check if bot is currently speaking (speech gate)
    if vad_state.get('speech_gate_active', False):
        # Bot is speaking - suppress user speech processing but still log
        gate_start_time = vad_state.get('bot_speech_start_time', current_time)
        gate_elapsed = current_time - gate_start_time
        logger.debug(f"🔇 Speech gate active for {call_sid} - suppressing user speech processing (elapsed: {gate_elapsed:.2f}s)")
        # Still add to buffer to maintain continuity when gate is lifted
        audio_buffers[call_sid].extend(audio)
        return
    
    # Log incoming audio
    logger.debug(f"📡 Received {len(audio)} bytes of PCM16 audio from {call_sid}")
    
    # Add audio to buffer
    audio_buffers[call_sid].extend(audio)
    # Also accumulate into time-based fallback buffer regardless of VAD state
    vad_state['fallback_buffer'].extend(audio)
    total_buffer_size = len(audio_buffers[call_sid])
    buffer_duration_ms = total_buffer_size / (sample_rate * SAMPLE_WIDTH) * 1000
    
    # Info-level listening heartbeat (throttled)
    try:
        if (current_time - vad_state.get('last_listen_log_time', 0)) >= 1.0:
            fb_ms = len(vad_state['fallback_buffer']) / (sample_rate * SAMPLE_WIDTH) * 1000
            logger.info(f"🎧 Listening ({call_sid}): buffer={fb_ms:.0f}ms, speaking={vad_state['is_speaking']}, sample_rate={sample_rate}")
            vad_state['last_listen_log_time'] = current_time
    except Exception:
        pass
    
    logger.debug(f"Audio buffer for {call_sid}: {total_buffer_size} bytes ({buffer_duration_ms:.0f}ms total)")
    
    # Process audio in 20ms frames for VAD
    frame_size_bytes = int(sample_rate * VAD_FRAME_DURATION_MS / 1000) * SAMPLE_WIDTH
    buffer = audio_buffers[call_sid]
    
    while len(buffer) >= frame_size_bytes:
        # Extract frame for VAD analysis
        frame_bytes = bytes(buffer[:frame_size_bytes])
        buffer = buffer[frame_size_bytes:]
        
        try:
            # VAD requires PCM16 mono at specific sample rates
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
                        # Treat as noise; continue without starting a segment
                        is_speech = False

            if is_speech:
                # Speech detected
                if not vad_state['is_speaking']:
                    # Start of speech
                    vad_state['is_speaking'] = True
                    vad_state['speech_start_time'] = current_time
                    vad_state['pending_audio'] = bytearray()
                    logger.info(f"🗣️  SPEECH STARTED for {call_sid}")
                
                vad_state['last_speech_time'] = current_time
                vad_state['pending_audio'].extend(frame_bytes)
                
                # Log periodic speech detection
                if len(vad_state['pending_audio']) % (frame_size_bytes * 25) == 0:  # Every ~500ms
                    speech_duration = current_time - vad_state['speech_start_time']
                    pending_duration_ms = len(vad_state['pending_audio']) / (sample_rate * SAMPLE_WIDTH) * 1000
                    logger.debug(f"Speech continuing for {call_sid}: {speech_duration:.1f}s elapsed, {pending_duration_ms:.0f}ms buffered")
                
            else:
                # No speech in this frame
                if vad_state['is_speaking']:
                    # We were speaking, add this frame to pending audio (might be pause)
                    vad_state['pending_audio'].extend(frame_bytes)
                    
                    # Check if silence timeout exceeded - use longer timeout for problem details phase
                    silence_duration = current_time - vad_state['last_speech_time']
                    
                    # Determine appropriate silence timeout based on dialog state
                    dialog = call_dialog_state.get(call_sid, {})
                    current_silence_timeout = PROBLEM_DETAILS_SILENCE_TIMEOUT_SEC if dialog.get('step') == 'awaiting_problem_details' else SILENCE_TIMEOUT_SEC
                    
                    if silence_duration >= current_silence_timeout:
                        # End of speech detected
                        speech_duration = current_time - vad_state['speech_start_time']
                        pending_duration_ms = len(vad_state['pending_audio']) / (sample_rate * SAMPLE_WIDTH) * 1000
                        
                        # Log which timeout was used
                        timeout_type = "problem_details" if dialog.get('step') == 'awaiting_problem_details' else "regular"
                        logger.info(f"🔇 SPEECH ENDED for {call_sid}: {speech_duration:.2f}s total, {pending_duration_ms:.0f}ms buffered, {silence_duration:.2f}s silence (timeout: {timeout_type})")
                        
                        if speech_duration >= MIN_SPEECH_DURATION_SEC:
                            # Valid speech segment, process it
                            logger.info(f"✅ Processing valid speech segment for {call_sid}")
                            # Check if already processing to prevent multiple simultaneous processing
                            if not vad_state.get('processing_lock', False):
                                await process_speech_segment(call_sid, vad_state['pending_audio'])
                                # Clear fallback buffer too to avoid double-processing the same audio
                                vad_state['fallback_buffer'] = bytearray()
                                # Mark the time when we last processed via VAD to prevent immediate fallback
                                vad_state['last_vad_process_time'] = current_time
                            else:
                                logger.info(f"🚫 Skipping VAD speech processing for {call_sid} - already processing")
                        else:
                            logger.warning(f"❌ Speech too short for {call_sid} ({speech_duration:.2f}s < {MIN_SPEECH_DURATION_SEC}s), discarding")
                        
                        # Reset VAD state
                        vad_state['is_speaking'] = False
                        vad_state['pending_audio'] = bytearray()
                
        except Exception as e:
            logger.warning(f"VAD processing error for {call_sid}: {e}")
            # Fall back to time-based chunking on VAD error
            continue
    
    # Update buffer
    audio_buffers[call_sid] = buffer
    
    # Fallback: if we've been collecting audio for too long, force processing (VAD path)
    if vad_state['is_speaking']:
        speech_duration = current_time - vad_state['speech_start_time']
        
        # Determine appropriate chunk duration based on dialog state
        dialog = call_dialog_state.get(call_sid, {})
        current_chunk_duration = PROBLEM_DETAILS_CHUNK_DURATION_SEC if dialog.get('step') == 'awaiting_problem_details' else CHUNK_DURATION_SEC
        
        if speech_duration >= current_chunk_duration:
            logger.debug(f"Forcing processing due to max duration for {call_sid} (chunk_duration: {current_chunk_duration}s)")
            # Check if already processing to prevent multiple simultaneous processing
            if not vad_state.get('processing_lock', False):
                await process_speech_segment(call_sid, vad_state['pending_audio'])
                # Clear fallback buffer too, since it contains the same recent audio
                vad_state['fallback_buffer'] = bytearray()
                # Mark the time when we processed via VAD to prevent immediate fallback
                vad_state['last_vad_process_time'] = current_time
            else:
                logger.info(f"🚫 Skipping forced processing for {call_sid} - already processing")
            vad_state['is_speaking'] = False
            vad_state['pending_audio'] = bytearray()

    # NEW: Time-based fallback flush every CHUNK_DURATION_SEC even if VAD never triggered
    try:
        fallback_bytes = len(vad_state['fallback_buffer'])
        last_vad_process = vad_state.get('last_vad_process_time', 0)
        last_chunk_time = vad_state.get('last_chunk_time', 0)
        time_since_vad = current_time - last_vad_process
        time_since_chunk = current_time - last_chunk_time
        
        # Only trigger fallback if:
        # 1. Not currently speaking
        # 2. Have enough audio buffered (conditional based on dialog state)
        # 3. Haven't processed via VAD recently (prevent double processing)
        # 4. Haven't processed via fallback recently (prevent excessive processing)
        # 5. Not currently processing (check processing lock)
        
        # Determine appropriate fallback duration based on dialog state
        dialog = call_dialog_state.get(call_sid, {})
        if dialog.get('step') == 'awaiting_problem_details':
            min_fallback_duration = 10.0  # Require at least 10 seconds of audio before fallback for problem details
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
            logger.info(f"⏱️ Time-based fallback flush for {call_sid}: {fallback_bytes} bytes (~{min_fallback_duration}s)")
            await process_speech_segment(call_sid, vad_state['fallback_buffer'])
            vad_state['fallback_buffer'] = bytearray()
            vad_state['last_chunk_time'] = current_time
    except Exception as e:
        logger.debug(f"Time-based fallback flush error for {call_sid}: {e}")

async def process_speech_segment(call_sid: str, audio_data: bytearray):
    """Process a detected speech segment"""
    # Check processing lock to prevent multiple simultaneous processing
    vad_state = vad_states.get(call_sid, {})
    if vad_state.get('processing_lock', False):
        logger.info(f"🚫 Skipping speech processing for {call_sid} - already processing")
        return
    
    # Set processing lock
    vad_state['processing_lock'] = True
    
    try:
        sample_rate = audio_config_store.get(call_sid, {}).get('sample_rate', SAMPLE_RATE_DEFAULT)
        audio_duration_ms = len(audio_data) / (sample_rate * SAMPLE_WIDTH) * 1000
        logger.info(f"Processing speech segment for {call_sid}: {len(audio_data)} bytes, {audio_duration_ms:.0f}ms duration")
        
        # Mark first speech as processed
        if not vad_state.get('has_processed_first_speech', False):
            vad_state['has_processed_first_speech'] = True
            logger.info(f"🎯 First speech processed for {call_sid}")
            
    except Exception as e:
        logger.error(f"Error in speech segment processing for {call_sid}: {e}")
        vad_state['processing_lock'] = False
        return
    
    # Audio fingerprinting to prevent processing the same audio multiple times
    try:
        import hashlib
        audio_hash = hashlib.md5(bytes(audio_data)).hexdigest()[:8]  # First 8 chars of hash
        info = call_info_store.get(call_sid, {})
        last_audio_hash = info.get('last_audio_hash')
        last_audio_ts = info.get('last_audio_ts', 0)
        now_ts = time.time()
        
        if last_audio_hash == audio_hash and (now_ts - last_audio_ts) < 30:
            logger.info(f"Suppressing duplicate audio segment for {call_sid} (hash: {audio_hash})")
            return
        
        info['last_audio_hash'] = audio_hash
        info['last_audio_ts'] = now_ts
        call_info_store[call_sid] = info
    except Exception as e:
        logger.debug(f"Audio fingerprinting failed for {call_sid}: {e}")
    
    # Quality-focused processing - require longer segments for better accuracy
    min_duration_ms = 500  # Increased from 400 - require longer segments for better quality
    min_bytes = sample_rate * SAMPLE_WIDTH * (min_duration_ms / 1000)
    
    if len(audio_data) < min_bytes:
        logger.warning(f"Speech segment too short for {call_sid} ({audio_duration_ms:.0f}ms < {min_duration_ms}ms), skipping Whisper processing")
        return

    # Energy gate to drop very low-energy segments (likely noise/line tones)
    try:
        if _audioop is not None:
            rms = _audioop.rms(bytes(audio_data), 2)
        else:
            # Fallback simple RMS
            import array
            arr = array.array('h', audio_data)
            if len(arr) == 0:
                rms = 0
            else:
                rms = int((sum(x*x for x in arr) / len(arr)) ** 0.5)
        if rms < 60:  # Reduced from 80 - more sensitive to quiet speech
            logger.info(f"Skipping low-energy segment for {call_sid} (RMS={rms})")
            return
    except Exception as e:
        logger.debug(f"RMS calc failed for {call_sid}: {e}")

    try:
        logger.debug(f"Converting PCM16 to WAV for {call_sid} ({len(audio_data)} bytes) @ {sample_rate} Hz")
        wav_bytes = pcm_to_wav_bytes(bytes(audio_data), sample_rate)
        logger.debug(f"WAV conversion complete for {call_sid}: {len(wav_bytes)} bytes")
        
        # Optionally resample to 16k for Whisper if available
        target_rate = 16000
        wav_for_whisper = wav_bytes
        if sample_rate != target_rate and _audioop is not None:
            pcm16 = bytes(audio_data)
            converted, _ = _audioop.ratecv(pcm16, 2, 1, sample_rate, target_rate, None)
            wav_for_whisper = pcm_to_wav_bytes(converted, target_rate)
            logger.debug(f"Resampled audio for Whisper from {sample_rate} Hz to {target_rate} Hz")
        
        logger.info(f"Sending audio to Whisper for {call_sid}")
        
        # Optimized service selection - use fastest service first
        resp = None
        
        # Try remote Whisper first (fastest, ~0.4s)
        if USE_REMOTE_WHISPER:
            try:
                import base64
                import httpx
                
                # Convert WAV to base64
                wav_base64 = base64.b64encode(wav_for_whisper).decode('utf-8')
                
                # Send to remote service with shorter timeout
                start_time = time.time()
                async with httpx.AsyncClient(timeout=5.0) as whisper_http_client:  # Renamed to avoid conflict
                    # Ensure clean URL without double slashes
                    whisper_url = REMOTE_WHISPER_URL.rstrip('/')
                    response = await whisper_http_client.post(
                        f"{whisper_url}/transcribe",
                        json={
                            "audio_base64": wav_base64,
                            "sample_rate": 16000,
                            "language": "en"
                        }
                    )
                    response.raise_for_status()
                    remote_result = response.json()
                transcription_duration = time.time() - start_time
                
                # Convert to OpenAI format
                openai_resp = type('obj', (object,), {
                    'text': remote_result.get('text', ''),
                    'segments': []  # Remote service doesn't provide segments
                })()
                
                resp = openai_resp
                logger.info(f"Remote Whisper transcription completed for {call_sid} in {transcription_duration:.2f}s")
                
            except Exception as e:
                logger.debug(f"Remote Whisper failed for {call_sid}: {e}")
                resp = None
        
        # Fallback to OpenAI Whisper (slower but reliable)
        if resp is None:
            logger.info(f"Using OpenAI Whisper {TRANSCRIPTION_MODEL} for {call_sid}")
            wav_file = io.BytesIO(wav_for_whisper)
            try:
                wav_file.name = "speech.wav"  # Help the API infer format
            except Exception:
                pass
            
            # Simplified prompt for faster processing
            prompt = "Caller describing plumbing issue. Focus on clear speech."
            
            start_time = time.time()
            resp = client.audio.transcriptions.create(
                model=TRANSCRIPTION_MODEL,
                file=wav_file,
                response_format="verbose_json",
                language="en",
                prompt=prompt,
                temperature=0.0
            )
            transcription_duration = time.time() - start_time
            logger.info(f"OpenAI Whisper transcription completed for {call_sid} in {transcription_duration:.2f}s")
        
        text = (resp.text or "").strip()
        
        # Basic text cleaning (simplified for speed)
        text = text.strip()
        if not text:
            return
        
        # Confidence/quality gating using segments avg_logprob
        avg_logprobs = []
        for seg in getattr(resp, 'segments', []) or []:
            lp = getattr(seg, 'avg_logprob', None)
            if isinstance(lp, (int, float)):
                avg_logprobs.append(lp)
        mean_lp = sum(avg_logprobs) / len(avg_logprobs) if avg_logprobs else None
        
        normalized = text.lower().strip().strip(".,!? ")
        # Immediate transfer if user requests it, even with low confidence
        if is_transfer_request(normalized):
            logger.info(f"🟢 Transfer keyword detected for {call_sid}: '{text}' (avg_logprob={mean_lp})")
            await perform_dispatch_transfer(call_sid)
            return
        
        short_garbage = {"bye", "hi", "uh", "um", "hmm", "huh"}
        should_suppress = False
        if not text:
            should_suppress = True
        elif len(normalized) <= 3 and normalized in short_garbage:
            should_suppress = True
        elif mean_lp is not None and mean_lp < settings.TRANSCRIPTION_CONFIDENCE_THRESHOLD:
            should_suppress = True
            if settings.CONFIDENCE_DEBUG_MODE:
                logger.info(f"🔍 Low transcription confidence: {mean_lp:.3f} < {settings.TRANSCRIPTION_CONFIDENCE_THRESHOLD}")
        
        # Only accept confirmation phrases when we're actually in a confirmation dialog step
        dialog = call_dialog_state.get(call_sid, {})
        confirmation_steps = {
            'awaiting_time_confirm', 
            'awaiting_location_confirm', 
            'post_booking_qa'
        }
        
        if dialog.get('step') in confirmation_steps:
            confirm_phrases = {
                "done", "finished", "completed", "yes", "okay", "ok", "no", "nope", "nah", "no thanks", "no thank you",
                "yeah", "yep", "yup", "sure", "right", "correct", "exactly", "absolutely", "definitely",
                "uh huh", "mm hmm", "mhm", "for sure", "of course", "you bet", "indeed", "certainly",
                "uh uh", "nuh uh", "mm mm", "not really", "negative", "that's not right", "that's wrong",
                "incorrect", "maybe not", "probably not"
            }
            if any(p in normalized for p in confirm_phrases):
                should_suppress = False
                logger.info(f"🎯 PATTERN MATCHED: Accepting confirmation phrase '{text}' in step '{dialog.get('step')}' despite low confidence for {call_sid}")
        
        if should_suppress:
            logger.info(f"Suppressed low-confidence/short transcription for {call_sid}: '{text}' (avg_logprob={mean_lp})")
            return
        
        # Clean and filter the transcription text
        cleaned_text, should_suppress_due_to_content = clean_and_filter_transcription(text)
        if should_suppress_due_to_content:
            logger.info(f"Suppressed transcription due to content filtering for {call_sid}: '{text}'")
            return
        
        # Use cleaned text for further processing
        text = cleaned_text
        if not text.strip():
            logger.info(f"Suppressed empty transcription after cleaning for {call_sid}")
            return
        
        logger.info(f'🎤 USER SPEECH ({call_sid}): "{text}" [duration: {audio_duration_ms:.0f}ms, transcription_time: {transcription_duration:.2f}s, avg_logprob: {mean_lp}]')
        
        # Additional filtering for very short or low-confidence transcriptions
        if len(text.strip()) <= 2 and mean_lp is not None and mean_lp < -0.8:
            logger.info(f"Suppressing very short low-confidence transcript for {call_sid}: '{text}' (length={len(text)}, confidence={mean_lp:.3f})")
            return
        
        # Suppress common noise patterns
        noise_patterns = [
            r'^\s*[.,!?;:]\s*$',  # Just punctuation
            r'^\s*[aeiou]\s*$',   # Just a single vowel
            r'^\s*[bcdfghjklmnpqrstvwxyz]\s*$',  # Just a single consonant
            r'^\s*[0-9]\s*$',     # Just a single digit
            r'^\s*[^\w\s]\s*$',   # Just a single special character
        ]
        import re
        for pattern in noise_patterns:
            if re.match(pattern, text, re.IGNORECASE):
                logger.info(f"Suppressing noise pattern transcript for {call_sid}: '{text}'")
                return
        
        # Simple duplicate detection (simplified for speed)
        try:
            normalized_text = " ".join(text.lower().split())
            info = call_info_store.get(call_sid, {})
            prev_text = info.get('asr_last_text')
            prev_ts = info.get('asr_last_ts', 0)
            now_ts = time.time()
            
            # Check for exact duplicates within 10 seconds (reduced from 30)
            if prev_text == normalized_text and (now_ts - prev_ts) < 10:
                logger.info(f"Suppressing duplicate transcript for {call_sid}: '{text}'")
                return
            
            # Update tracking
            info['asr_last_text'] = normalized_text
            info['asr_last_ts'] = now_ts
            call_info_store[call_sid] = info
        except Exception as e:
            logger.debug(f"Duplicate check failed for {call_sid}: {e}")

        # Broadcast real-time transcript to ops dashboard
        try:
            asyncio.create_task(_broadcast_transcript(call_sid, text))
        except Exception:
            pass

        # Handle user speech response
        await response_to_user_speech(call_sid, text)
            
    except Exception as e:
        logger.error(f"Speech processing error for {call_sid}: {e}")
        logger.debug(f"Failed audio details for {call_sid}: {len(audio_data)} bytes, {audio_duration_ms:.0f}ms")
    finally:
        # Release processing lock
        vad_state['processing_lock'] = False

async def response_to_user_speech(call_sid: str, text: str) -> None:
    """Handle user speech response after transcription is complete"""
    # Post-booking Q&A flow
    dialog = call_dialog_state.get(call_sid)
    if dialog and dialog.get('step') == 'post_booking_qa':
        if is_negative_response(text):
            twiml = VoiceResponse()
            await add_tts_or_say_to_twiml(twiml, call_sid, "Thanks for trusting SafeHarbour to help you with your plumbing needs. Goodbye.")
            twiml.hangup()
            call_dialog_state.pop(call_sid, None)
            await push_twiml_to_call(call_sid, twiml)
            _mark_progress(call_sid, "post_booking_qa_completed", "user ended call")
            return
        # Answer with GPT-4o and re-prompt
        answer = await answer_customer_question(call_sid, text)
        reply = f"{answer} Please let me know if you have any other questions."
        twiml = VoiceResponse()
        await add_tts_or_say_to_twiml(twiml, call_sid, reply)
        # Keep in QA mode and resume stream
        def append_stream_and_pause_local(resp: VoiceResponse):
            start = Start()
            wss_url_local = _build_wss_url_for_resume(call_sid)
            start.stream(url=wss_url_local, track="inbound_track")
            resp.append(start)
            resp.pause(length=3600)
        append_stream_and_pause_local(twiml)
        await push_twiml_to_call(call_sid, twiml)
        _mark_progress(call_sid, "post_booking_qa_response", f"answered question: {text[:50]}...")
        return

    # Name collection handling
    if dialog and dialog.get('step') == 'awaiting_name':
        # Extract name from user response
        customer_name = extract_name_from_text(text)
        if customer_name:
            # Store the name and acknowledge it
            dialog['customer_name'] = customer_name
            # Update dialog state to continue with normal flow
            dialog['step'] = 'name_collected'
            call_dialog_state[call_sid] = dialog
            
            # Reset name collection attempts since we succeeded
            conversation_manager.reset_name_collection_attempts(call_sid)
            
            twiml = VoiceResponse()
            await add_tts_or_say_to_twiml(
                twiml, 
                call_sid, 
                f"Nice to meet you, {customer_name}. If at any point you'd like to speak to a human dispatcher, just say 'transfer'. What can we assist you with today?"
            )
            # Resume streaming to listen for their plumbing issue
            start = Start()
            wss_url = _build_wss_url_for_resume(call_sid)
            start.stream(url=wss_url, track="inbound_track")
            twiml.append(start)
            twiml.pause(length=3600)
            await push_twiml_to_call(call_sid, twiml)
            logger.info(f"👤 Collected name '{customer_name}' for {call_sid}")
            _mark_progress(call_sid, "name_collected", f"extracted name: {customer_name}")
            return
        else:
            # Couldn't extract a clear name, increment attempts
            attempts = conversation_manager.increment_name_collection_attempts(call_sid)
            
            # Check if we should transfer to human dispatch
            if conversation_manager.should_handoff_due_to_name_collection_attempts(call_sid):
                logger.info(f"🤝 HANDOFF: Too many name collection attempts ({attempts}) for {call_sid} - transferring to human dispatch")
                twiml = VoiceResponse()
                await add_tts_or_say_to_twiml(
                    twiml, 
                    call_sid, 
                    "I'm having trouble understanding your name clearly. Let me connect you with our dispatch team who can better assist you."
                )
                twiml.dial(settings.DISPATCH_NUMBER)
                # Mark state to avoid further processing
                st = call_info_store.setdefault(call_sid, {})
                st["handoff_requested"] = True
                st["handoff_reason"] = "too_many_name_collection_attempts"
                call_info_store[call_sid] = st
                # Clear dialog state
                call_dialog_state.pop(call_sid, None)
                await push_twiml_to_call(call_sid, twiml)
                _mark_progress(call_sid, "handoff_to_dispatch", f"transferred after {attempts} name collection attempts")
                return
            
            # Ask again for the name
            twiml = VoiceResponse()
            await add_tts_or_say_to_twiml(
                twiml, 
                call_sid, 
                "I didn't catch your name clearly. Could you please tell me your name?"
            )
            # Keep the same dialog state and resume streaming
            start = Start()
            wss_url = _build_wss_url_for_resume(call_sid)
            start.stream(url=wss_url, track="inbound_track")
            twiml.append(start)
            twiml.pause(length=3600)
            await push_twiml_to_call(call_sid, twiml)
            _mark_no_progress(call_sid, f"could not extract name from response (attempt {attempts})")
            return

    # Transfer confirmation handling
    if dialog and dialog.get('step') == 'awaiting_transfer_confirm':
        if is_affirmative_response(text):
            # User said yes - transfer to dispatch
            twiml = VoiceResponse()
            await add_tts_or_say_to_twiml(twiml, call_sid, "Connecting you to our dispatch team now.")
            twiml.dial(settings.DISPATCH_NUMBER)
            # Mark state to avoid further processing
            st = call_info_store.setdefault(call_sid, {})
            st["handoff_requested"] = True
            st["handoff_reason"] = "user_confirmed_transfer_after_unclear_attempts"
            call_info_store[call_sid] = st
            # Clear dialog state
            call_dialog_state.pop(call_sid, None)
            await push_twiml_to_call(call_sid, twiml)
            logger.info(f"📞 User confirmed transfer for {call_sid} after unclear attempts")
            _mark_progress(call_sid, "transfer_confirmed", "user confirmed transfer to dispatch")
            return
        elif is_negative_response(text):
            # User said no - continue with clarification
            twiml = VoiceResponse()
            await add_tts_or_say_to_twiml(
                twiml, 
                call_sid, 
                "No problem. Let me try to help you differently. What exactly do you need? For example: water heater repair, drain unclog, leak detection, toilet issue, or a new install."
            )
            # Clear dialog state and reset unclear attempts to give them another chance
            call_dialog_state.pop(call_sid, None)
            reset_unclear_attempts(call_sid)
            # Resume streaming to listen for their response
            start = Start()
            wss_url = _build_wss_url_for_resume(call_sid)
            start.stream(url=wss_url, track="inbound_track")
            twiml.append(start)
            twiml.pause(length=3600)
            await push_twiml_to_call(call_sid, twiml)
            logger.info(f"💬 User declined transfer for {call_sid}, continuing with clarification")
            _mark_progress(call_sid, "transfer_declined", "user declined transfer, continuing clarification")
            return
        else:
            # Unclear response to transfer confirmation - ask again more directly
            twiml = VoiceResponse()
            await add_tts_or_say_to_twiml(twiml, call_sid, "I didn't catch that. Should I transfer you to a representative? Please say yes or no.")
            # Keep the same dialog state
            start = Start()
            wss_url = _build_wss_url_for_resume(call_sid)
            start.stream(url=wss_url, track="inbound_track")
            twiml.append(start)
            twiml.pause(length=3600)
            await push_twiml_to_call(call_sid, twiml)
            _mark_no_progress(call_sid, "unclear response to transfer confirmation")
            return

    # Scheduling/path and confirmation follow-up handling
    if dialog and dialog.get('step') in (
        'awaiting_path_choice',
        'awaiting_problem_details',
        'awaiting_time',
        'awaiting_time_confirm',
        'awaiting_location_confirm',
        'awaiting_operator_confirm',
    ):
        logger.info(f"Handling follow-up scheduling/path utterance for {call_sid}: '{text}'")
        twiml = await handle_intent(call_sid, dialog.get('intent', {}), followup_text=text)
        await push_twiml_to_call(call_sid, twiml)
        return

    # Otherwise, extract a fresh intent with parallel processing for speed
    if FAST_RESPONSE_MODE:
        # Run intent extraction and time parsing in parallel
        intent_task = asyncio.create_task(extract_intent_from_text(call_sid, text))
        time_task = asyncio.create_task(_parse_time_parallel(text))
        intent, (explicit_time, explicit_emergency) = await asyncio.gather(intent_task, time_task)
    else:
        intent = await extract_intent_from_text(call_sid, text)
        explicit_time = parse_human_datetime(text) or gpt_infer_datetime_phrase(text)
        explicit_emergency = contains_emergency_keywords(text)
    
    # NEW: Mark progress if we successfully extracted intent
    if intent and intent.get('job', {}).get('type'):
        _mark_progress(call_sid, "intent_extracted", f"extracted job type: {intent.get('job', {}).get('type')}")
    else:
        _mark_no_progress(call_sid, "failed to extract meaningful intent")
    
    # Check if this is a plumbing issue and we haven't asked for problem details yet
    info = call_info_store.get(call_sid, {})
    segments_count = int(info.get('segments_count', 0)) + 1
    info['segments_count'] = segments_count
    call_info_store[call_sid] = info
    
    dialog = call_dialog_state.get(call_sid, {})
    
    # Accumulate audio for the entire call and save to step1 directory
    try:
        import os
        import time
        from datetime import datetime
        
        # Create step1 directory if it doesn't exist
        step1_dir = "step1"
        os.makedirs(step1_dir, exist_ok=True)
        
        # Get or create the accumulated audio buffer for this call
        if 'accumulated_audio' not in call_info_store.get(call_sid, {}):
            call_info_store[call_sid] = call_info_store.get(call_sid, {})
            call_info_store[call_sid]['accumulated_audio'] = bytearray()
        
        # Get the most recent audio data for this call
        vad_state = vad_states.get(call_sid, {})
        if vad_state.get('pending_audio'):
            audio_data = bytes(vad_state['pending_audio'])
        else:
            # Fallback: try to get from audio buffers
            audio_data = bytes(audio_buffers.get(call_sid, bytearray()))
        
        if audio_data:
            # Add this audio segment to the accumulated buffer
            call_info_store[call_sid]['accumulated_audio'].extend(audio_data)
            
            # Save the accumulated audio to file
            accumulated_audio = bytes(call_info_store[call_sid]['accumulated_audio'])
            filename = f"{step1_dir}/step1_{call_sid}.wav"
            
            # Convert to WAV and save
            sample_rate = audio_config_store.get(call_sid, {}).get('sample_rate', SAMPLE_RATE_DEFAULT)
            wav_bytes = pcm_to_wav_bytes(accumulated_audio, sample_rate)
            
            with open(filename, 'wb') as f:
                f.write(wav_bytes)
            
            logger.info(f"💾 Updated step1 audio for {call_sid} to {filename} (total: {len(accumulated_audio)} bytes)")
        else:
            logger.warning(f"⚠️ No audio data available to accumulate for {call_sid}")
            
    except Exception as e:
        logger.error(f"Failed to save step1 audio for {call_sid}: {e}")
    
    # Check if this is a plumbing issue and we haven't asked for problem details yet
    job_type = intent.get('job', {}).get('type', '')
    is_plumbing_issue = job_type and job_type != 'general_inquiry'
    
    # Debug logging to understand why problem details question isn't being asked
    logger.info(f"🔍 DEBUG: Checking problem details condition for {call_sid}:")
    logger.info(f"   - is_plumbing_issue: {is_plumbing_issue}")
    logger.info(f"   - job_type: {job_type}")
    logger.info(f"   - explicit_time: {explicit_time}")
    logger.info(f"   - explicit_emergency: {explicit_emergency}")
    logger.info(f"   - is_affirmative_response: {is_affirmative_response(text)}")
    logger.info(f"   - problem_details_asked: {dialog.get('problem_details_asked')}")
    logger.info(f"   - dialog state: {dialog}")
    
    if (is_plumbing_issue and 
        not explicit_time and 
        not explicit_emergency and 
        not dialog.get('problem_details_asked')):
        
        call_dialog_state[call_sid] = {'intent': intent, 'step': 'awaiting_problem_details', 'problem_details_asked': True}
        logger.info(f"🔍 ASKING FOR PROBLEM DETAILS: Plumbing issue identified from {call_sid} - asking specifically how and when it started")
        twiml = VoiceResponse()
        await add_tts_or_say_to_twiml(
            twiml,
            call_sid,
            f"Tell me more about your {_speakable(job_type)}, specifically how and when it started."
        )
        start = Start()
        wss_url = _build_wss_url_for_resume(call_sid)
        start.stream(url=wss_url, track="inbound_track")
        twiml.append(start)
        twiml.pause(length=3600)
        await push_twiml_to_call(call_sid, twiml)
        _mark_progress(call_sid, "problem_details_requested", f"asked for details about {job_type}")
        return
    
    # Defer prompting/booking until caller provides explicit signals (date/time or emergency) or after at least 2 segments
    if (segments_count < 2 and not explicit_time and not explicit_emergency and 
        not is_affirmative_response(text)):
        # Don't set any step yet - just continue listening
        logger.info(f"Deferring prompt; continuing to listen for {call_sid} (segments={segments_count})")
        _mark_no_progress(call_sid, f"deferring prompt - segments={segments_count}, no explicit signals")
        return
    twiml = await handle_intent(call_sid, intent)
    await push_twiml_to_call(call_sid, twiml)
    _mark_progress(call_sid, "intent_handled", f"processed intent: {intent.get('job', {}).get('type', 'unknown')}")

async def extract_intent_from_text(call_sid: str, text:str) -> dict:
   # Enhanced prompt with better context and examples
   enhanced_prompt = f"""
You are a plumbing service booking assistant. Extract structured information from customer requests.

CUSTOMER REQUEST: "{text}"

INSTRUCTIONS:
1. Identify the specific plumbing job type from the comprehensive list of services
2. Determine urgency: emergency (immediate), same_day (today), flex (anytime)
3. Extract customer name and contact info
4. Parse address information
5. Assess confidence and handoff needs

EXAMPLES:
- "kitchen sink is clogged" → job_type: clogged_kitchen_sink
- "bathroom sink won't drain" → job_type: clogged_bathroom_sink
- "toilet is running constantly" → job_type: running_toilet
- "water heater burst" → job_type: water_heater_repair, urgency: emergency
- "need new faucet installed" → job_type: faucet_replacement
- "sewer camera inspection" → job_type: camera_inspection
- "drain smells bad" → job_type: camera_inspection
- "can come tomorrow" → urgency: flex
- "need today" → urgency: same_day
- "emergency leak" → urgency: emergency

Be precise and extract all available information. Match to the most specific service type available.
"""

   # Send user text to ChatCompletion with function calling
   resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": enhanced_prompt}],
        tools=FUNCTIONS,
        tool_choice="auto",
        temperature=0.1,  # Lower temperature for more consistent results
        max_tokens=1000
   )
   msg = resp.choices[0].message
   if msg.tool_calls:
    tool_call = msg.tool_calls[0]
    args = json.loads(tool_call.function.arguments)
    
    # Post-process and validate the extracted data
    validated_args = validate_and_enhance_extraction(args, text, call_sid)
    return validated_args

   # Fallback: no function call, return freeform description
   return create_fallback_response(text)

def validate_and_enhance_extraction(args: dict, original_text: str, call_sid: str = None) -> dict:
    """Validate and enhance extracted data with additional processing"""
    
    # Ensure required fields exist
    if 'intent' not in args:
        args['intent'] = 'BOOK_JOB'
    
    # Calculate intent confidence for the original text
    try:
        # Use the same intent classification system for confidence
        import asyncio
        if asyncio.iscoroutinefunction(classify_transcript_intent):
            # If in async context, calculate intent confidence
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Schedule intent confidence calculation
                intent_confidence = 0.7  # Default for now, will be calculated properly
            else:
                intent, intent_confidence = loop.run_until_complete(classify_transcript_intent(original_text))
        else:
            intent_confidence = 0.7  # Default fallback
    except:
        intent_confidence = 0.7  # Default fallback if async context issues
    
    # Enhance job type recognition with keyword matching and multi-intent detection
    multi_intent_result = infer_multiple_job_types_from_text(original_text)
    
    if not args.get('job', {}).get('type'):
        args['job'] = args.get('job', {})
        args['job']['type'] = multi_intent_result['primary'] or infer_job_type_from_text(original_text)
    
    # Add secondary intents if detected
    if multi_intent_result['secondary']:
        args['job']['secondary_intents'] = multi_intent_result['secondary']
    
    # Enhance description with secondary intents
    if multi_intent_result['description_suffix']:
        current_description = args.get('job', {}).get('description', '')
        if current_description:
            # Add suffix with a space separator
            args['job']['description'] = f"{current_description} {multi_intent_result['description_suffix']}"
        else:
            # Create a basic description with the detected intents
            args['job']['description'] = multi_intent_result['description_suffix']
    
    # Improve urgency classification
    if not args.get('job', {}).get('urgency'):
        args['job']['urgency'] = infer_urgency_from_text(original_text)
    
    # Extract phone numbers if missing
    if not args.get('customer', {}).get('phone'):
        phone = extract_phone_number(original_text)
        if phone:
            args['customer'] = args.get('customer', {})
            args['customer']['phone'] = phone
    
    # Include collected customer name from dialog state
    if call_sid:
        dialog = call_dialog_state.get(call_sid, {})
        customer_name = dialog.get('customer_name')
        if customer_name and not args.get('customer', {}).get('name'):
            args['customer'] = args.get('customer', {})
            args['customer']['name'] = customer_name
    
    # Enhance address extraction
    if not args.get('location', {}).get('raw_address'):
        address = extract_address(original_text)
        if address:
            args['location'] = args.get('location', {})
            args['location']['raw_address'] = address
    
    # Calculate confidence scores with intent confidence
    confidence = calculate_confidence_scores(args, original_text, intent_confidence)
    args['confidence'] = confidence
    
    # Determine handoff based on confidence and completeness
    args['handoff_needed'] = should_handoff_to_human(args, confidence, call_sid)
    
    return args



def infer_urgency_from_text(text: str) -> str:
    """Infer urgency from text using keyword matching"""
    text_lower = text.lower()
    
    # Emergency indicators
    if any(word in text_lower for word in ['emergency', 'burst', 'flooding', 'water everywhere', 'immediately', 'urgent']):
        return 'emergency'
    
    # Same day indicators
    if any(word in text_lower for word in ['today', 'asap', 'soon', 'quickly', 'urgent']):
        return 'same_day'
    
    # Flexible indicators
    if any(word in text_lower for word in ['tomorrow', 'next week', 'when convenient', 'schedule', 'appointment']):
        return 'flex'
    
    return 'flex'  # Default to flexible

# TTS: synthesize with ElevenLabs or OpenAI 4o TTS
async def synthesize_tts(text: str) -> Optional[bytes]:
    # Check if ElevenLabs TTS is enabled and configured
    if (settings.USE_ELEVENLABS_TTS and 
        settings.ELEVENLABS_API_KEY and 
        settings.ELEVENLABS_VOICE_ID):
        try:
            from elevenlabs import ElevenLabs
            
            # Create ElevenLabs client with API key
            elevenlabs_client = ElevenLabs(api_key=settings.ELEVENLABS_API_KEY)
            
            # Use configured voice ID or default to the specified one
            voice_id = settings.ELEVENLABS_VOICE_ID
            model_id = settings.ELEVENLABS_MODEL_ID or "eleven_multilingual_v2"
            
            # Generate audio using ElevenLabs
            logger.info(f"🎤 Using ElevenLabs TTS (voice: {voice_id}, model: {model_id})")
            audio_stream = elevenlabs_client.text_to_speech.convert(
                voice_id=voice_id,
                text=text,
                model_id=model_id
            )
            
            # Convert iterator to bytes
            audio = b"".join(audio_stream)
            
            if audio:
                logger.debug(f"ElevenLabs TTS generated {len(audio)} bytes for text: {text[:50]}...")
                return audio
            else:
                logger.error("ElevenLabs TTS returned empty response")
                
        except Exception as e:
            logger.error(f"ElevenLabs TTS failed: {e}")
            logger.info("Falling back to OpenAI TTS...")
    
    # If ElevenLabs is disabled or not configured, use OpenAI TTS
    if not settings.USE_ELEVENLABS_TTS:
        logger.info("🎤 ElevenLabs TTS disabled via USE_ELEVENLABS_TTS=False, using OpenAI TTS")
    
    # Use OpenAI TTS (either as fallback or primary choice)
    try:
        # Use the existing global OpenAI client
        voice = getattr(settings, 'OPENAI_TTS_VOICE', 'alloy')  # Default to 'alloy' voice
        model = getattr(settings, 'OPENAI_TTS_MODEL', 'tts-1')  # Default to 'tts-1' model
        speed = settings.OPENAI_TTS_SPEED  # Use configured speed (0.25 to 4.0)
        
        logger.info(f"🎤 Using OpenAI TTS (voice: {voice}, model: {model}, speed: {speed})")
        
        response = client.audio.speech.create(
            model=model,
            voice=voice,
            input=text,
            response_format="mp3",
            speed=speed
        )
        
        # Convert response to bytes
        audio_content = b""
        for chunk in response.iter_bytes():
            audio_content += chunk
            
        if audio_content:
            logger.debug(f"OpenAI TTS generated {len(audio_content)} bytes for text: {text[:50]}...")
            return audio_content
        else:
            logger.error("OpenAI TTS returned empty response")
            return None
            
    except Exception as e:
        logger.error(f"OpenAI TTS failed: {e}")
        return None

async def _activate_speech_gate(call_sid: str, text: str):
    """Activate speech gate to prevent user speech processing during bot TTS output"""
    logger.info(f"🔇 ACTIVATING SPEECH GATE for {call_sid} with text length: {len(text)}")
    try:
        # Ensure vad_state exists
        if call_sid not in vad_states:
            vad_states[call_sid] = {
                'speech_gate_active': False,
                'bot_speaking': False,
                'is_speaking': False,
                'pending_audio': bytearray(),
                'stream_start_time': time.time(),
                'has_received_media': False,
            }
            logger.info(f"🔄 Initialized vad_state for {call_sid}")
        
        vad_state = vad_states[call_sid]
        current_time = time.time()
        
        # OPTIMIZED: Much more aggressive timing for faster responses
        # Use character count instead of word count for better accuracy
        char_count = len(text)
        # Estimate ~15 chars per second at 1.5x speed (much faster calculation)
        base_duration = char_count / (15 * settings.OPENAI_TTS_SPEED)
        
        # Cap maximum gate duration to prevent long blocks
        max_gate_duration = 3.0  # Never block longer than 3 seconds
        actual_duration = min(base_duration, max_gate_duration)
        
        # Minimal buffer time for speed
        buffer_time = 0.3  # Reduced from 0.5s
        gate_duration = actual_duration + buffer_time
        
        # Activate the speech gate
        vad_state['speech_gate_active'] = True
        vad_state['bot_speaking'] = True
        vad_state['bot_speech_start_time'] = current_time
        
        # NEW: Track speech gate cycle for comprehensive handoff detection
        # Ensure tracking is properly initialized
        if call_sid not in speech_gate_cycle_tracking:
            speech_gate_cycle_tracking[call_sid] = {
                'total_cycles': 0,
                'consecutive_no_progress': 0,
                'last_progress_time': 0,
                'last_speech_gate_time': 0,
                'last_processed_text': '',
                'last_intent_extracted': None,
                'last_dialog_step': '',
                'call_start_time': current_time,
                'max_cycles_without_progress': 3,
                'max_call_duration_without_progress': 120,
            }
            logger.info(f"🔄 Initialized speech gate cycle tracking for {call_sid}")
        else:
            logger.info(f"🔄 Using existing speech gate cycle tracking for {call_sid}")
        
        cycle_tracking = speech_gate_cycle_tracking[call_sid]
        cycle_tracking['total_cycles'] += 1
        cycle_tracking['last_speech_gate_time'] = current_time
        
        # Initialize call start time if not set
        if cycle_tracking['call_start_time'] == 0:
            cycle_tracking['call_start_time'] = current_time
        
        logger.info(f"🔇 Speech gate activated for {call_sid}: {gate_duration:.2f}s (text: {len(text)} chars) - Cycle #{cycle_tracking['total_cycles']} (no_progress: {cycle_tracking['consecutive_no_progress']})")
        
        # Schedule gate deactivation with shorter delay for more responsive listening
        asyncio.create_task(_deactivate_speech_gate_after_delay(call_sid, gate_duration))
        
    except Exception as e:
        logger.error(f"Failed to activate speech gate for {call_sid}: {e}")

async def _deactivate_speech_gate_after_delay(call_sid: str, delay: float):
    """Deactivate speech gate after estimated TTS completion"""
    try:
        await asyncio.sleep(delay)
        
        vad_state = vad_states.get(call_sid)
        if vad_state:
            vad_state['speech_gate_active'] = False
            vad_state['bot_speaking'] = False
            logger.info(f"🔊 Speech gate deactivated for {call_sid} after {delay:.2f}s")
            
            # Clear any accumulated audio during gate period to avoid processing stale audio
            if vad_state.get('is_speaking'):
                vad_state['is_speaking'] = False
                vad_state['pending_audio'] = bytearray()
                logger.debug(f"Cleared pending audio for {call_sid} after speech gate")
            
            # NEW: Check for handoff conditions after speech gate deactivation
            logger.info(f"🔍 Checking handoff conditions after speech gate deactivation for {call_sid}")
            await _check_speech_gate_handoff_conditions(call_sid)
                
    except Exception as e:
        logger.error(f"Failed to deactivate speech gate for {call_sid}: {e}")

async def _check_speech_gate_handoff_conditions(call_sid: str):
    """Check if handoff is needed based on speech gate cycle tracking"""
    try:
        cycle_tracking = speech_gate_cycle_tracking.get(call_sid, {})
        if not cycle_tracking:
            logger.info(f"🔍 No cycle tracking found for {call_sid}")
            return
        
        logger.info(f"🔍 Checking handoff conditions for {call_sid}: cycles={cycle_tracking.get('total_cycles', 0)}, no_progress={cycle_tracking.get('consecutive_no_progress', 0)}")
        
        current_time = time.time()
        total_cycles = cycle_tracking.get('total_cycles', 0)
        consecutive_no_progress = cycle_tracking.get('consecutive_no_progress', 0)
        last_progress_time = cycle_tracking.get('last_progress_time', 0)
        call_start_time = cycle_tracking.get('call_start_time', current_time)
        max_cycles = cycle_tracking.get('max_cycles_without_progress', 3)
        max_duration = cycle_tracking.get('max_call_duration_without_progress', 120)
        
        # Calculate time since last progress
        time_since_progress = current_time - last_progress_time if last_progress_time > 0 else current_time - call_start_time
        call_duration = current_time - call_start_time
        
        # Check handoff conditions
        handoff_reasons = []
        
        # Condition 1: Too many consecutive cycles without progress
        if consecutive_no_progress >= max_cycles:
            handoff_reasons.append(f"{consecutive_no_progress} consecutive cycles without progress >= {max_cycles}")
        
        # Condition 2: Too much time without progress
        if time_since_progress >= max_duration:
            handoff_reasons.append(f"{time_since_progress:.1f}s without progress >= {max_duration}s")
        
        # Condition 3: Call has been going too long without meaningful progress
        if call_duration >= max_duration * 2 and consecutive_no_progress >= 2:
            handoff_reasons.append(f"call duration {call_duration:.1f}s with {consecutive_no_progress} cycles without progress")
        
        if handoff_reasons:
            reasons_str = ", ".join(handoff_reasons)
            logger.warning(f"🚨 SPEECH GATE HANDOFF TRIGGERED for {call_sid}: {reasons_str}")
            logger.warning(f"   📊 Cycle stats: total={total_cycles}, no_progress={consecutive_no_progress}, time_since_progress={time_since_progress:.1f}s")
            logger.error(f"🚨 AUTOMATIC HANDOFF REQUIRED: {call_sid} will be transferred to dispatch")
            
            # Perform automatic handoff to dispatch
            await _perform_automatic_handoff(call_sid, f"speech_gate_cycles: {reasons_str}")
        
    except Exception as e:
        logger.error(f"Error checking speech gate handoff conditions for {call_sid}: {e}")

async def _perform_automatic_handoff(call_sid: str, reason: str):
    """Perform automatic handoff to dispatch due to speech gate cycle failures"""
    try:
        logger.info(f"🤖 AUTOMATIC HANDOFF: Transferring {call_sid} to dispatch due to: {reason}")
        
        # Create TwiML for handoff
        twiml = VoiceResponse()
        await add_tts_or_say_to_twiml(
            twiml, 
            call_sid, 
            "I'm having trouble understanding your request clearly. Let me connect you with our dispatch team who can better assist you."
        )
        twiml.dial(settings.DISPATCH_NUMBER)
        
        # Mark state to avoid further processing
        st = call_info_store.setdefault(call_sid, {})
        st["handoff_requested"] = True
        st["handoff_reason"] = f"automatic_handoff: {reason}"
        call_info_store[call_sid] = st
        
        # Clear dialog state
        call_dialog_state.pop(call_sid, None)
        
        # Push the handoff TwiML
        await push_twiml_to_call(call_sid, twiml)
        
        logger.info(f"✅ Automatic handoff completed for {call_sid}")
        
    except Exception as e:
        logger.error(f"Failed to perform automatic handoff for {call_sid}: {e}")

def _mark_progress(call_sid: str, progress_type: str, details: str = ""):
    """Mark that meaningful progress has been made in the conversation"""
    try:
        cycle_tracking = speech_gate_cycle_tracking.get(call_sid, {})
        if not cycle_tracking:
            logger.info(f"🔍 No cycle tracking found for progress marking on {call_sid}")
            return
        
        current_time = time.time()
        cycle_tracking['last_progress_time'] = current_time
        cycle_tracking['consecutive_no_progress'] = 0  # Reset counter
        
        logger.info(f"✅ PROGRESS MARKED for {call_sid}: {progress_type} - {details}")
        logger.debug(f"   📊 Progress stats: consecutive_no_progress reset to 0, last_progress_time={current_time}")
        
    except Exception as e:
        logger.error(f"Error marking progress for {call_sid}: {e}")

def _mark_no_progress(call_sid: str, reason: str = ""):
    """Mark that no progress was made in this cycle"""
    try:
        cycle_tracking = speech_gate_cycle_tracking.get(call_sid, {})
        if not cycle_tracking:
            logger.info(f"🔍 No cycle tracking found for no-progress marking on {call_sid}")
            return
        
        cycle_tracking['consecutive_no_progress'] += 1
        current_count = cycle_tracking['consecutive_no_progress']
        
        logger.info(f"❌ NO PROGRESS for {call_sid}: {reason} - consecutive_no_progress={current_count}")
        logger.warning(f"🚨 NO PROGRESS DETECTED: {call_sid} has {current_count} consecutive cycles without progress")
        
    except Exception as e:
        logger.error(f"Error marking no progress for {call_sid}: {e}")

def get_natural_conversation_starter(text: str, dialog: dict, call_sid: str) -> str:
    """
    Choose natural conversation starters based on context to make responses less robotic.
    Returns appropriate phrases like 'Thanks', 'Sounds good', 'OK', etc.
    """
    text_lower = text.lower()
    current_step = dialog.get('step', '')
    
    # Get conversation context
    info = call_info_store.get(call_sid, {})
    segments_count = info.get('segments_count', 0)
    
    # Confirmation and booking contexts
    if any(phrase in text_lower for phrase in ['do you want this time', 'please say yes or no', 'confirm']):
        return "Alright"
    
    # Time-related responses
    if any(phrase in text_lower for phrase in ['i can schedule', 'available', 'earliest', 'time looks busy']):
        return "OK"
    
    # After user provides information (booking details, preferences, etc.)
    if current_step in ['awaiting_time_confirm', 'awaiting_location_confirm'] or segments_count > 1:
        starters = ["Thanks", "Sounds good", "Got it", "Perfect"]
        # Simple rotation based on call activity to add variety
        import time
        starter_index = int(time.time() // 10) % len(starters)  # Changes every 10 seconds
        return starters[starter_index]
    
    # Problem-solving and clarification contexts
    if any(phrase in text_lower for phrase in ['what exactly', 'could you', 'tell me', 'what can we assist']):
        return "Alright"
    
    # Error recovery and re-prompting
    if any(phrase in text_lower for phrase in ["didn't catch", "sorry", "trouble understanding"]):
        return "OK"
    
    # Transfer and handoff contexts
    if any(phrase in text_lower for phrase in ['would you like me to transfer', 'connect you']):
        return "Alright"
    
    # Positive acknowledgments
    if any(phrase in text_lower for phrase in ['great', 'perfect', 'excellent']):
        return "Sounds good"
    
    # Follow-up questions and continued conversation
    if any(phrase in text_lower for phrase in ['what date', 'which time', 'any other', 'anything else']):
        return "OK"
    
    # Default starters for general responses - rotate for variety
    if segments_count > 0:  # Only after initial exchange
        default_starters = ["Alright", "OK", "Thanks"]
        import time
        starter_index = int(time.time() // 15) % len(default_starters)  # Changes every 15 seconds
        return default_starters[starter_index]
    
    # Return empty string for initial responses or when no starter is appropriate
    return ""

async def add_tts_or_say_to_twiml(target, call_sid: str, text: str):
    # Get customer name from dialog state and prepend it to most messages
    dialog = call_dialog_state.get(call_sid, {})
    customer_name = dialog.get('customer_name')
    
    # Don't add name to certain types of messages
    skip_name_prefixes = [
        "hello", "who do i have", "i didn't catch your name", "connecting you", 
        "thanks for trusting", "thank you for calling", "goodbye", "bye",
        "nice to meet you"
    ]
    
    # Check if this message should skip name prefixing
    should_skip_name = any(text.lower().startswith(prefix) for prefix in skip_name_prefixes)
    
    # Prepend name if available and appropriate with natural conversation starters
    if customer_name and not should_skip_name and dialog.get('step') != 'awaiting_name':
        # Choose natural conversation starter based on context
        conversation_starters = get_natural_conversation_starter(text, dialog, call_sid)
        if conversation_starters:
            speak_text = f"{conversation_starters}, {customer_name}, {text}".replace("_", " ")
        else:
            speak_text = f"{customer_name}, {text}".replace("_", " ")
    else:
        speak_text = text.replace("_", " ")
    
    preview = speak_text if len(speak_text) <= 200 else speak_text[:200] + "..."
    
    # Activate speech gate when bot starts speaking
    await _activate_speech_gate(call_sid, speak_text)
    
    if settings.FORCE_SAY_ONLY:
        logger.info(f"🗣️ OpenAI TTS SAY for CallSid={call_sid}: {preview}")
        target.say(speak_text)
        return
    audio = await synthesize_tts(speak_text)
    if audio:
        tts_audio_store[call_sid] = audio
        # Bump version so TwiML <Play> URL changes each time (prevents identical-string dedupe)
        v = int(tts_version_counter.get(call_sid, 0)) + 1
        tts_version_counter[call_sid] = v
        audio_url = f"{settings.EXTERNAL_WEBHOOK_URL}/tts/{call_sid}.mp3?v={v}"
        logger.info(f"🗣️ OpenAI TTS PLAY for CallSid={call_sid}: url={audio_url} bytes={len(audio)} text={preview}")
        target.play(audio_url)
    else:
        logger.info(f"🗣️ OpenAI TTS SAY (fallback) for CallSid={call_sid}: {preview}")
        target.say(speak_text)

# Push updated TwiML mid-call to Twilio
async def push_twiml_to_call(call_sid: str, response: VoiceResponse):
     try:
         twiml_str = str(response)
         # Skip if identical to last TwiML pushed
         prev = last_twiml_store.get(call_sid)
         now_ts = time.time()
         if prev == twiml_str:
             logger.info(f"Skipping TwiML push for {call_sid}: identical to last")
             return
         # Throttle frequent pushes
         last_ts = last_twiml_push_ts.get(call_sid, 0)
         if now_ts - last_ts < TWIML_PUSH_MIN_INTERVAL_SEC:
             logger.info(f"Throttling TwiML push for {call_sid}: pushed {now_ts - last_ts:.2f}s ago")
             return
         last_twiml_store[call_sid] = twiml_str
         last_twiml_push_ts[call_sid] = now_ts
         logger.info(f"🔊 Pushing TwiML to call {call_sid}")
         logger.debug(f"Updating call {call_sid} with TwiML: {twiml_str}")
         if twilio_client is None:
             logger.warning("TwiML push skipped: Twilio client unavailable")
             return
         loop = asyncio.get_event_loop()
         def _update():
             return twilio_client.calls(call_sid).update(twiml=twiml_str)  # type: ignore[union-attr]
         result = await loop.run_in_executor(None, _update)
         logger.info(f"Pushed TwiML update to call {call_sid}; status={getattr(result, 'status', 'unknown')}")
     except Exception as e:
         logger.error(f"Failed to push TwiML directly to call {call_sid}: {e}; attempting URL fallback")
         if twilio_client is None:
             return
         try:
             url = f"{settings.EXTERNAL_WEBHOOK_URL}/twiml/{call_sid}"
             loop = asyncio.get_event_loop()
             def _update_url():
                 return twilio_client.calls(call_sid).update(url=url, method="GET")  # type: ignore[union-attr]
             result = await loop.run_in_executor(None, _update_url)
             logger.info(f"Pushed TwiML via URL to call {call_sid}; status={getattr(result, 'status', 'unknown')} url={url}")
         except Exception as e2:
             logger.error(f"URL fallback also failed for call {call_sid}: {e2}")

def extract_name_from_text(text: str) -> str:
    """Extract customer name from text response"""
    import re
    
    # Normalize and clean the text
    text = text.strip().lower()
    
    # Common name introduction patterns
    name_patterns = [
        r"(?:my name is|i'm|i am|this is|it's|it is|call me)\s+([a-zA-ZÀ-ÿ][a-zA-ZÀ-ÿ\s\-']+)",
        r"^([a-zA-ZÀ-ÿ][a-zA-ZÀ-ÿ\s\-']+?)(?:\s+here|[.,!?]?\s*$)",  # Simple name at start, with optional punctuation
        r"(?:i saw|i met|i know)\s+([a-zA-ZÀ-ÿ][a-zA-ZÀ-ÿ\s\-']+)",  # "I saw Daniel" type patterns
        r"(?:this is|that's|that is)\s+([a-zA-ZÀ-ÿ][a-zA-ZÀ-ÿ\s\-']+)",  # "This is Daniel" type patterns
        r"^(?:um|uh|well|so|like|just)\s+([a-zA-ZÀ-ÿ][a-zA-ZÀ-ÿ\s\-']+)",  # Handle filler words before names
    ]
    
    for pattern in name_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            name = match.group(1).strip().title()
            # Filter out common non-name words
            skip_words = {
                'hello', 'hi', 'hey', 'good', 'morning', 'afternoon', 'evening', 
                'yes', 'yeah', 'yep', 'sure', 'okay', 'ok', 'calling', 'about',
                'speaking', 'here', 'with', 'you', 'the', 'a', 'an', 'and',
                'saw', 'met', 'know', 'is', 'that',
                'thank', 'thanks', 'no', 'nope', 'nah',
                'um', 'uh', 'well', 'so', 'like', 'just'
            }
            # Check if any word in the name is in skip words
            name_words = name.lower().split()
            if (not any(word in skip_words for word in name_words) and 
                len(name) >= 2 and len(name) <= 50 and 
                not any(char.isdigit() for char in name) and
                all(char.isalpha() or char in ['-', "'", ' '] for char in name)):
                
                # For multi-word names, return only the first word
                if ' ' in name:
                    first_name = name.split()[0]
                    # Only return if first name is not a skip word
                    if first_name.lower() not in skip_words:
                        return first_name
                else:
                    return name
    
    # If no name found with regex patterns, try GPT as fallback
    try:
        from openai import OpenAI
        import os
        
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        
        prompt = f"""
        Extract the person's name from this text. Return ONLY the name, nothing else.
        If no clear name is found, return "None".
        
        Examples:
        "um Sean" -> "Sean"
        "I'm John" -> "John"
        "My name is Sarah" -> "Sarah"
        "Thank you" -> "None"
        "Hello" -> "None"
        
        Text: "{text}"
        """
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=10,
            temperature=0
        )
        
        name = response.choices[0].message.content.strip()
        
        # Validate the response
        if name.lower() in ['none', 'no', 'n/a', '']:
            return None
            
        # Basic validation - should be letters, hyphens, apostrophes, reasonable length
        # Allow common punctuation like periods, commas, exclamation marks
        if (name and len(name) >= 2 and len(name) <= 50 and 
            all(char.isalpha() or char in ['-', "'", ' '] for char in name) and
            not any(char.isdigit() for char in text) and
            not any(char in ['@', '#', '$', '%', '&', '*', '+', '=', '<', '>', '[', ']', '{', '}', '(', ')', '|', '\\', '/', '`', '~', '^'] for char in text)):
            return name.title()
            
    except Exception as e:
        logger.debug(f"GPT name extraction failed: {e}")
    
    return None

def extract_phone_number(text: str) -> str:
    """Extract phone number from text"""
    import re
    # Phone number patterns
    patterns = [
        r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b',  # 123-456-7890
        r'\b\(\d{3}\)\s*\d{3}[-.]?\d{4}\b',  # (123) 456-7890
        r'\b\d{10}\b',  # 1234567890
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group()
    
    return None

def extract_address(text: str) -> str:
    """Extract address from text"""
    import re
    # Simple address pattern (number + street)
    pattern = r'\b\d+\s+[A-Za-z\s]+(?:Street|St|Avenue|Ave|Road|Rd|Drive|Dr|Lane|Ln|Boulevard|Blvd)\b'
    match = re.search(pattern, text, re.IGNORECASE)
    if match:
        return match.group()
    
    return None

def calculate_confidence_scores(args: dict, original_text: str, intent_confidence: float = 0.0) -> dict:
    """Calculate confidence scores for extracted data including intent confidence"""
    confidence = {
        "overall": 0.0,
        "fields": {},
        "intent": intent_confidence
    }
    
    # Job type confidence
    job_type = args.get('job', {}).get('type')
    if job_type:
        confidence["fields"]["type"] = 0.9 if job_type in ['leak', 'water_heater', 'clog', 'gas_line', 'sewer_cam', 'plumbing', 'drain_cleaning', 'plumbing_repair', 'plumbing_installation', 'plumbing_replacement', 'plumbing_maintenance', 'plumbing_inspection', 'plumbing_repair', 'plumbing_installation', 'plumbing_replacement', 'plumbing_maintenance', 'plumbing_inspection'] else 0.7
    else:
        confidence["fields"]["type"] = 0.0
    
    # Urgency confidence
    urgency = args.get('job', {}).get('urgency')
    if urgency:
        confidence["fields"]["urgency"] = 0.8 if urgency in ['emergency', 'same_day', 'flex', 'as soon as possible', 'urgent', 'immediately', 'today', 'soon', 'quickly', 'right now'] else 0.5
    else:
        confidence["fields"]["urgency"] = 0.0
       
    # Overall confidence (include intent confidence in calculation)
    field_scores = list(confidence["fields"].values())
    field_scores.append(intent_confidence)  # Include intent confidence
    if field_scores:
        confidence["overall"] = sum(field_scores) / len(field_scores)
    
    if settings.CONFIDENCE_DEBUG_MODE:
        logger.info(f"🔍 Confidence breakdown: overall={confidence['overall']:.3f}, intent={intent_confidence:.3f}, fields={confidence['fields']}")
    
    return confidence

def should_handoff_to_human(args: dict, confidence: dict, call_sid: str = None) -> bool:
    """Determine if human handoff is needed using configurable thresholds and consecutive failure tracking"""
    overall_confidence = confidence.get("overall", 0.0)
    intent_confidence = confidence.get("intent", 0.0)
    
    # Initialize handoff reasons for logging
    handoff_reasons = []
    
    # Track consecutive failures if call_sid is provided
    consecutive_handoff = False
    single_instance_handoff = False
    if call_sid:
        # Track intent confidence failures
        if intent_confidence < settings.INTENT_CONFIDENCE_THRESHOLD:
            consecutive_intent_failures[call_sid] += 1
            if settings.CONFIDENCE_DEBUG_MODE:
                logger.info(f"🔢 Intent failure #{consecutive_intent_failures[call_sid]} for {call_sid}")
        else:
            # Reset counter on success
            if consecutive_intent_failures[call_sid] > 0:
                if settings.CONFIDENCE_DEBUG_MODE:
                    logger.info(f"✅ Intent confidence recovered for {call_sid}, resetting counter")
                consecutive_intent_failures[call_sid] = 0
        
        # Track overall confidence failures
        if overall_confidence < settings.OVERALL_CONFIDENCE_THRESHOLD:
            consecutive_overall_failures[call_sid] += 1
            if settings.CONFIDENCE_DEBUG_MODE:
                logger.info(f"🔢 Overall failure #{consecutive_overall_failures[call_sid]} for {call_sid}")
        else:
            # Reset counter on success
            if consecutive_overall_failures[call_sid] > 0:
                if settings.CONFIDENCE_DEBUG_MODE:
                    logger.info(f"✅ Overall confidence recovered for {call_sid}, resetting counter")
                consecutive_overall_failures[call_sid] = 0
        
        # Check consecutive failure thresholds
        if consecutive_intent_failures[call_sid] >= settings.CONSECUTIVE_INTENT_FAILURES_THRESHOLD:
            handoff_reasons.append(f"{consecutive_intent_failures[call_sid]} consecutive intent failures >= {settings.CONSECUTIVE_INTENT_FAILURES_THRESHOLD}")
            consecutive_handoff = True
        
        if consecutive_overall_failures[call_sid] >= settings.CONSECUTIVE_OVERALL_FAILURES_THRESHOLD:
            handoff_reasons.append(f"{consecutive_overall_failures[call_sid]} consecutive overall failures >= {settings.CONSECUTIVE_OVERALL_FAILURES_THRESHOLD}")
            consecutive_handoff = True
    
    # Check for missing critical fields
    required_fields = ['job.type', 'job.urgency', 'location.raw_address']
    missing_fields = 0
    
    for field in required_fields:
        field_parts = field.split('.')
        value = args
        for part in field_parts:
            value = value.get(part, {}) if isinstance(value, dict) else None
            if value is None:
                break
        
        if not value:
            missing_fields += 1
    
    missing_fields_handoff = False
    # Track consecutive missing field failures per call
    if call_sid:
        if missing_fields >= settings.MISSING_FIELDS_PER_TURN_THRESHOLD:
            consecutive_missing_fields_failures[call_sid] += 1
            if settings.CONFIDENCE_DEBUG_MODE:
                logger.info(f"🔢 Missing fields failure #{consecutive_missing_fields_failures[call_sid]} for {call_sid} ({missing_fields} missing >= {settings.MISSING_FIELDS_PER_TURN_THRESHOLD})")
            # Only trigger handoff once we've reached the consecutive threshold
            if consecutive_missing_fields_failures[call_sid] >= settings.CONSECUTIVE_MISSING_FIELDS_FAILURES_THRESHOLD:
                handoff_reasons.append(f"{consecutive_missing_fields_failures[call_sid]} consecutive turns with >= {settings.MISSING_FIELDS_PER_TURN_THRESHOLD} critical fields missing")
                missing_fields_handoff = True
        else:
            if consecutive_missing_fields_failures[call_sid] > 0 and settings.CONFIDENCE_DEBUG_MODE:
                logger.info(f"✅ Required fields present for {call_sid}, resetting missing fields counter")
            consecutive_missing_fields_failures[call_sid] = 0
    else:
        # Fallback: if no call_sid tracking, use single-turn decision
        if missing_fields >= settings.MISSING_FIELDS_PER_TURN_THRESHOLD:
            handoff_reasons.append(f"{missing_fields} critical fields missing (no call tracking)")
            missing_fields_handoff = True
    
    # Determine final handoff decision
    should_handoff = single_instance_handoff or consecutive_handoff or missing_fields_handoff
    
    # Log handoff decision
    if should_handoff and settings.CONFIDENCE_DEBUG_MODE:
        reasons_str = ", ".join(handoff_reasons)
        logger.info(f"🚨 Handoff triggered for {call_sid or 'unknown'}: {reasons_str}")
    elif settings.CONFIDENCE_DEBUG_MODE and call_sid:
        logger.info(f"✅ Continuing automation for {call_sid}: confidence OK")
    
    return should_handoff

def create_fallback_response(text: str) -> dict:
    """Create a fallback response when function calling fails"""
    return {
        "intent": "BOOK_JOB",
        "customer": {"name": None, "phone": None, "email": None},
        "job": {"type": None, "urgency": None, "description": text},
        "location": {"raw_address": None, "validated": False, "address_id": None, "lat": None, "lng": None},
        "constraints": {},
        "proposed_slot": {},
        "fsm_backend": None,
        "confidence": {"overall": 0.0, "fields": {}},
        "handoff_needed": True
    }

# Simple negative/closing intent detection
NEGATIVE_PATTERNS = {
    "no", "no thanks", "no thank you", "that's all", "that is all", "nothing else", "nope",
    "nah", "we're good", "we are good", "all good", "goodbye", "bye", "hang up", "end call"
}

# Goodbye/closing statement patterns
GOODBYE_PATTERNS = {
    "thank you for listening", "thank you for watching", "see you next time", "goodbye", "bye",
    "that's all", "that is all", "we're done", "we are done", "have a good day", "take care",
    "thanks for your time", "appreciate it", "no thank you", "nothing else", "all set", "we're good"
}

def is_goodbye_statement(text: str) -> bool:
    """Detect if user is trying to end the call politely"""
    norm = " ".join(text.lower().split())
    
    # Check for exact matches
    if norm in GOODBYE_PATTERNS:
        return True
    
    # Check for partial matches
    goodbye_keywords = [
        "thank you for listening", "thank you for watching", "see you next time",
        "have a good day", "take care", "thanks for your time", "appreciate it",
        "we're done", "we are done", "all set", "we're good", "we are good"
    ]
    
    for pattern in goodbye_keywords:
        if pattern in norm:
            return True
    
    return False

def has_no_clear_service_intent(intent: dict) -> bool:
    """Check if the intent lacks clear plumbing service indicators"""
    confidence = intent.get('confidence', {})
    overall_confidence = confidence.get('overall', 0.0)
    
    # Very low confidence indicates unclear intent
    if overall_confidence < 0.5:
        return True
    
    # Missing critical information
    job_type = intent.get('job', {}).get('type')
    job_description = intent.get('job', {}).get('description', '')
    
    # No specific job type and very generic description
    if not job_type or job_type == 'None':
        return True
    
    return False

def is_negative_response(text: str) -> bool:
    norm = " ".join(text.lower().split())
    if norm in NEGATIVE_PATTERNS:
        return True
    # Prefix matches for common closers
    for p in ("no ", "no,", "no.", "nope", "nah"):
        if norm.startswith(p):
            return True
    return False

# Positive/affirmative detection
AFFIRMATIVE_PATTERNS = {
    "yes", "yeah", "yep", "affirmative", "correct", "that works", "sounds good", "please do",
    "book it", "go ahead", "confirm", "let's do it", "schedule it", "do it", "done", "sure",
    "okay", "ok", "right", "exactly", "absolutely", "definitely", "uh huh", "mm hmm", "mhm",
    "for sure", "of course", "you bet", "indeed", "certainly", "sounds right", "looks good",
    "that sounds right", "that's right", "that is right", "i agree", "agreed"
}

def is_affirmative_response(text: str) -> bool:
    norm = " ".join((text or "").lower().strip().strip(".,!?").split())
    if norm in AFFIRMATIVE_PATTERNS:
        return True
    # Check if "yes" appears anywhere in the text (for phrases like "I said yes")
    if "yes" in norm:
        return True
    # Token-based checks
    words = norm.split()
    # Short generic confirmations only (avoid long sentences like "yeah, my ...")
    if len(words) <= 3 and words[0] in {"yes", "yeah", "yep", "yup", "ok", "okay", "sure", "correct", "affirmative", "done", "right", "exactly", "absolutely", "definitely"}:
        return True
    # Vocal confirmations that might be transcribed differently
    vocal_confirms = ["uh huh", "mm hmm", "mhm", "for sure", "of course", "you bet"]
    if norm in vocal_confirms:
        return True
    # Explicit booking/confirmation phrases anywhere in the utterance
    explicit_patterns = [
        r"\bbook(\s+it|\s+that)?\b",
        r"\bconfirm\b",
        r"\bschedule(\s+it)?\b",
        r"\bgo ahead\b",
        r"\bthat works\b",
        r"\bsounds good\b",
        r"\blet'?s do it\b",
        r"\bdo it\b",
        r"\bplease book\b",
    ]
    for pat in explicit_patterns:
        if re.search(pat, norm):
            return True
    return False

# STRICT yes/no confirmation for appointment scheduling
STRICT_YES_PATTERNS = {
    "yes", "yeah", "yep", "yup", "affirmative", "correct", "that's right", "that is right",
    "sure", "okay", "ok", "right", "exactly", "absolutely", "definitely", 
    "uh huh", "mm hmm", "mhm", "for sure", "of course", "you bet", "indeed", "certainly"
}

STRICT_NO_PATTERNS = {
    "no", "nope", "nah", "not that time", "that doesn't work", "that does not work",
    "uh uh", "nuh uh", "mm mm", "not really", "negative", "that's not right", "that's wrong",
    "incorrect", "maybe not", "probably not", "i don't think so", "i don't agree"
}

def is_strict_affirmative_response(text: str) -> bool:
    """Flexible yes detection for appointment confirmation - accepts any response with affirmative intent"""
    norm = " ".join((text or "").lower().strip().strip(".,!?").split())
    
    # Check for any form of "yes" anywhere in the text
    if any(word in norm for word in ["yes", "yeah", "yep", "yup"]):
        return True
    
    # Check for positive confirmation words
    positive_words = ["sure", "okay", "ok", "correct", "right", "absolutely", "definitely", "perfect", "great", "good", "sounds good", "works", "fine"]
    if any(word in norm for word in positive_words):
        return True
    
    # Check for positive phrases
    positive_phrases = ["let's do it", "that works", "that sounds good", "i'll take it", "book it", "schedule it", "go ahead", "do it", "sounds great", "looks good", "works for me", "i'm good", "that's good"]
    if any(phrase in norm for phrase in positive_phrases):
        return True
    
    # Vocal confirmations
    if any(vocal in norm for vocal in ["uh huh", "mm hmm", "mhm", "for sure", "of course", "you bet"]):
        return True
    
    return False

def is_strict_negative_response(text: str) -> bool:
    """Flexible no detection for appointment confirmation - accepts any response with negative intent"""
    norm = " ".join((text or "").lower().strip().strip(".,!?").split())
    
    # Check for any form of "no" anywhere in the text
    if any(word in norm for word in ["no", "nope", "nah"]):
        return True
    
    # Check for negative words
    negative_words = ["not", "can't", "cannot", "won't", "will not", "don't", "do not", "doesn't", "does not", "unable", "unavailable", "busy", "conflict"]
    if any(word in norm for word in negative_words):
        return True
    
    # Check for negative phrases
    negative_phrases = ["that doesn't work", "that does not work", "not that time", "not today", "can't make it", "cannot make it", "not available", "busy then", "have other plans", "doesn't work", "does not work", "not good", "not right", "wrong time", "bad time"]
    if any(phrase in norm for phrase in negative_phrases):
        return True
    
    # Vocal negations
    if any(vocal in norm for vocal in ["uh uh", "nuh uh", "mm mm", "not really", "maybe not", "probably not"]):
        return True
    
    # Common negative expressions
    if any(expr in norm for expr in ["i don't think so", "i don't agree", "that's not right", "that's wrong"]):
        return True
    
    return False

def _speakable(text: Optional[str]) -> str:
    if not text:
        return ""
    return " ".join(text.replace("_", " ").split())

def _format_slot(dt: datetime) -> str:
    # Format: Month D at H:MM AM/PM (no year)
    month = dt.strftime("%B")
    day = str(dt.day)
    time_part = dt.strftime("%I:%M %p").lstrip("0")
    return f"{month} {day} at {time_part}"

# Slot rules helpers

def _ceil_to_quarter_hour(dt: datetime) -> datetime:
    dt = dt.replace(second=0, microsecond=0)
    minutes = dt.minute
    remainder = (15 - (minutes % 15)) % 15
    if remainder == 0:
        return dt
    return dt + timedelta(minutes=remainder)


def _is_slot_free_with_buffer(
    candidate_start: datetime,
    duration_minutes: int = 120,
    buffer_minutes: int = 60,
    calendar: Optional[CalendarAdapter] = None,
) -> bool:
    try:
        if calendar is None:
            calendar = CalendarAdapter()
        if not getattr(calendar, "enabled", False):
            return True
        candidate_start = candidate_start.replace(second=0, microsecond=0)
        candidate_end = candidate_start + timedelta(minutes=duration_minutes)
        check_start = candidate_start - timedelta(minutes=buffer_minutes)
        check_end = candidate_end + timedelta(minutes=buffer_minutes)
        events = calendar.get_events(start_date=check_start, end_date=check_end)
        for ev in events or []:
            s_raw = ((ev.get("start") or {}).get("dateTime") or "")
            e_raw = ((ev.get("end") or {}).get("dateTime") or "")
            if not s_raw or not e_raw:
                continue
            try:
                s = datetime.fromisoformat(s_raw.replace("Z", "+00:00"))
                e = datetime.fromisoformat(e_raw.replace("Z", "+00:00"))
                # Normalize to naive UTC for comparison with naive check_start/check_end
                if s.tzinfo is not None:
                    s = s.astimezone(timezone.utc).replace(tzinfo=None)
                if e.tzinfo is not None:
                    e = e.astimezone(timezone.utc).replace(tzinfo=None)
            except Exception:
                continue
            # Overlap if event intersects the [check_start, check_end) window
            if not (e <= check_start or s >= check_end):
                return False
        return True
    except Exception:
        return True


def find_next_compliant_slot(
    earliest_start: datetime,
    emergency: bool = False,
    duration_minutes: int = 120,
    search_horizon_hours: int = 72,
) -> datetime:
    now = datetime.now()
    base = earliest_start
    if emergency:
        min_emergency_start = now + timedelta(minutes=30)
        if base < min_emergency_start:
            base = min_emergency_start
    try:
        cal = CalendarAdapter()
    except Exception:
        cal = None
    # Align to next quarter hour
    start = _ceil_to_quarter_hour(base)
    # If calendar disabled, just return aligned start
    if not getattr(cal, "enabled", False):
        return start
    # Scan forward in 15-minute increments for an available slot
    horizon_end = start + timedelta(hours=search_horizon_hours)
    step = timedelta(minutes=15)
    candidate = start
    while candidate <= horizon_end:
        if _is_slot_free_with_buffer(candidate, duration_minutes=duration_minutes, buffer_minutes=60, calendar=cal):
            return candidate
        candidate += step
    # Fallback to start if nothing found
    return start

def _normalize_relative_datetime_phrases(text: str, now: datetime) -> str:
    norm = text
    # Normalize possessives like "today's", "tuesday's"
    norm = re.sub(r"\b(today)'?s\b", r"\1", norm, flags=re.I)
    norm = re.sub(r"\b(monday|tuesday|wednesday|thursday|friday|saturday|sunday)'?s\b", r"\1", norm, flags=re.I)

    # Handle today/tomorrow/tonight
    if re.search(r"\btomorrow\b", norm, re.I):
        d = (now + timedelta(days=1)).strftime("%Y-%m-%d")
        norm = re.sub(r"\btomorrow\b", d, norm, flags=re.I)
    if re.search(r"\btoday\b", norm, re.I):
        d = now.strftime("%Y-%m-%d")
        norm = re.sub(r"\btoday\b", d, norm, flags=re.I)
    if re.search(r"\btonight\b", norm, re.I):
        d = now.strftime("%Y-%m-%d")
        norm = re.sub(r"\btonight\b", f"{d} 7 pm", norm, flags=re.I)

    # Handle "in N days/weeks/hours" (digits or words)
    number_words = {
        'zero': 0, 'one': 1, 'a': 1, 'an': 1, 'two': 2, 'couple': 2, 'three': 3, 'four': 4, 'five': 5,
        'six': 6, 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10, 'eleven': 11, 'twelve': 12, 'thirteen': 13,
        'fourteen': 14, 'fifteen': 15, 'sixteen': 16, 'seventeen': 17, 'eighteen': 18, 'nineteen': 19,
        'twenty': 20, 'thirty': 30
    }

    def repl_in_duration(m: re.Match) -> str:
        qty_str = m.group(1).lower()
        unit = m.group(2).lower()
        if qty_str.isdigit():
            qty = int(qty_str)
        else:
            qty = number_words.get(qty_str)
        if qty is None:
            return m.group(0)
        if unit.startswith('hour'):
            target = now + timedelta(hours=qty)
            return target.strftime('%Y-%m-%d %H:%M')
        if unit.startswith('week'):
            target = now + timedelta(days=qty * 7)
            return target.strftime('%Y-%m-%d')
        # default days
        target = now + timedelta(days=qty)
        return target.strftime('%Y-%m-%d')

    norm = re.sub(r"\bin\s+(\d+|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty|thirty|a|an|couple)\s+(day|days|week|weeks|hour|hours)\b",
                   repl_in_duration, norm, flags=re.I)

    # Handle parts of day when no explicit time provided
    norm = re.sub(r"\bmorning\b", "9 am", norm, flags=re.I)
    norm = re.sub(r"\bafternoon\b", "2 pm", norm, flags=re.I)
    norm = re.sub(r"\bevening\b", "6 pm", norm, flags=re.I)

    # Weekday handling
    days = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]

    def date_for_weekday(name: str, use_next: bool) -> str:
        wd = days.index(name)
        delta = (wd - now.weekday()) % 7
        if delta == 0:
            delta = 7 if use_next else 0
        target = now + timedelta(days=delta)
        return target.strftime("%Y-%m-%d")

    # next <weekday>
    for dname in days:
        norm = re.sub(rf"\bnext\s+{dname}\b", date_for_weekday(dname, True), norm, flags=re.I)
    # this <weekday>
    for dname in days:
        norm = re.sub(rf"\bthis\s+{dname}\b", date_for_weekday(dname, False), norm, flags=re.I)
    # bare weekday → pick next occurrence if same-day has likely passed
    for dname in days:
        norm = re.sub(rf"\b{dname}\b", date_for_weekday(dname, False), norm, flags=re.I)

    return norm


def parse_human_datetime(text: str, now: Optional[datetime] = None) -> Optional[datetime]:
    try:
        from dateutil import parser as _dtparser  # lazy import
    except Exception:
        return None
    if now is None:
        now = datetime.now()
    
    # Create a clean default time (same date as now, but at midnight)
    # This prevents inheriting current minutes/seconds when only hour is specified
    clean_default = now.replace(hour=0, minute=0, second=0, microsecond=0)
    
    prepared = _normalize_relative_datetime_phrases(text, now)
    try:
        dt = _dtparser.parse(prepared, fuzzy=True, default=clean_default)
        
        # If the parsed time is in the past and only a time was specified,
        # assume it's for tomorrow
        if dt < now and not any(word in text.lower() for word in ['today', 'tomorrow', 'yesterday']):
            # Check if it looks like just a time specification
            import re
            if re.search(r'\b\d{1,2}(:\d{2})?\s*(am|pm|a\.?m\.?|p\.?m\.?)\b', text.lower()):
                dt = dt + timedelta(days=1)
        
        return dt
    except Exception:
        return None


def gpt_infer_datetime_phrase(text: str, now_dt: Optional[datetime] = None) -> Optional[datetime]:
    try:
        if now_dt is None:
            now_dt = datetime.now()
        system = (
            "You extract a single scheduling datetime from a short phrase. "
            "Use the provided NOW as the reference for relative expressions. "
            "Return a compact JSON object only."
        )
        user = json.dumps({
            "now": now_dt.strftime("%Y-%m-%d %H:%M"),
            "phrase": text,
            "format": "YYYY-MM-DD HH:MM"
        })
        resp = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": (
                    "Given NOW and a phrase, respond with JSON: {\"iso\": \"YYYY-MM-DD HH:MM\"}. "
                    "PRIORITY: Always preserve explicit times mentioned by user (e.g., 'six o'clock' = 6:00 PM if evening context, 'three' = 3:00 PM). "
                    "If no time given, choose 3:00 PM. If only part of day given, pick within that (morning=9:00 AM, afternoon=2:00 PM, evening=6:00 PM). "
                    "If weekday given, pick the next occurrence. If the phrase implies the past, move to the next future occurrence. "
                    "Do not include any other keys.\n\n" + user
                )}
            ],
            temperature=0,
            max_tokens=60,
        )
        content = resp.choices[0].message.content or ""
        iso_str = None
        try:
            data = json.loads(content)
            iso_str = data.get("iso")
        except Exception:
            m = re.search(r"(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2})", content)
            if m:
                iso_str = m.group(1)
        if not iso_str:
            return None
        from dateutil import parser as _dtparser  # type: ignore
        return _dtparser.parse(iso_str)
    except Exception as e:
        logger.debug(f"GPT datetime inference failed: {e}")
        return None

async def answer_customer_question(call_sid: str, text: str) -> str:
    try:
        system_prompt = (
            "You are SafeHarbour Plumbing's helpful assistant. Answer the customer's question clearly,"
            " briefly, and accurately. If the answer depends on specifics you don't have, explain the options"
            " and what information is needed. Avoid making appointments or pricing unless stated."
        )
        resp = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": text}
            ],
            temperature=0.3,
            max_tokens=300,
        )
        msg = resp.choices[0].message.content or "I can help with that."
        return msg.strip()
    except Exception as e:
        logger.error(f"Q&A completion failed for {call_sid}: {e}")
        return "I can help with that."

async def handle_intent(call_sid: str, intent: dict, followup_text: str = None):
    # Get call information if available
    call_info = call_info_store.get(call_sid, {})
    
    twiml = VoiceResponse()
    job_type = intent.get('job', {}).get('type', 'a plumbing issue')
    urgency = intent.get('job', {}).get('urgency', 'flex')
    customer = intent.get('customer', {})
    customer_name = customer.get('name', 'Customer')
    
    # Use caller's phone number from call info if not extracted from speech
    customer_phone = customer.get('phone') or call_info.get('from')
    
    # Use geographic data from call info if no address extracted from speech
    address = intent.get('location', {}).get('raw_address', '')
    if not address and call_info.get('from_city') and call_info.get('from_state'):
        address = f"{call_info.get('from_city')}, {call_info.get('from_state')}"
        if call_info.get('from_zip'):
            address += f" {call_info.get('from_zip')}"
    
    notes = intent.get('job', {}).get('description', '')
    
    # If earlier stages determined a handoff is needed, transfer immediately
    if intent.get('handoff_needed'):
        try:
            await add_tts_or_say_to_twiml(
                twiml,
                call_sid,
                "I'm having trouble confidently handling this automatically. I'll connect you with our dispatcher now."
            )
        except Exception:
            pass
        # Dial dispatcher and return TwiML so caller pushes it
        number = getattr(settings, "DISPATCH_NUMBER", "+14693096560")
        twiml.dial(number)
        st = call_info_store.setdefault(call_sid, {})
        st["handoff_requested"] = True
        st["handoff_reason"] = "confidence_or_missing_fields"
        call_info_store[call_sid] = st
        # Clear dialog state to avoid further automation
        call_dialog_state.pop(call_sid, None)
        logger.info(f"🤝 Immediate transfer for {call_sid} due to handoff_needed=True (dispatcher {number})")
        return twiml
    
    # Add call context to notes
    if call_info.get('caller_name'):
        notes += f" [Caller: {call_info['caller_name']}]"
    if call_info.get('forwarded_from'):
        notes += f" [Forwarded from: {call_info['forwarded_from']}]"
    
    logger.info(f"🔧 BOOKING REQUEST from {call_sid}:")
    logger.info(f"   📱 Phone: {customer_phone}")
    logger.info(f"   👤 Name: {customer_name}")
    logger.info(f"   🏠 Address: {address}")
    logger.info(f"   🔧 Service: {job_type}")
    logger.info(f"   ⚡ Urgency: {urgency}")
    logger.info(f"   📝 Notes: {notes}")

    # Helper: append stream-and-pause so audio resumes streaming after we speak
    def append_stream_and_pause(resp: VoiceResponse):
        start = Start()
        wss_url_local = _build_wss_url_for_resume(call_sid)
        start.stream(url=wss_url_local, track="inbound_track")
        resp.append(start)
        resp.pause(length=3600)
        logger.info(f"Appended stream resume to TwiML for {call_sid} -> {wss_url_local}")

    # Check for goodbye statements or unclear service intent BEFORE proceeding with booking flow
    original_text = followup_text or intent.get('job', {}).get('description', '')
    confidence = intent.get('confidence', {})
    
    # Handle goodbye/closing statements
    if original_text and is_goodbye_statement(original_text):
        await add_tts_or_say_to_twiml(twiml, call_sid, "Thank you for calling SafeHarbour Plumbing Services. Have a great day!")
        _mark_progress(call_sid, "goodbye_statement", "user ended call with goodbye")
        return twiml
    
    # Handle very low confidence or no clear service intent
    if not followup_text and has_no_clear_service_intent(intent):
        logger.info(f"🔍 ASKING FOR CLEARER INTENT: No clear service intent detected for {call_sid} - requesting specific plumbing issue details")
        await add_tts_or_say_to_twiml(
            twiml, 
            call_sid, 
            "I want to make sure I understand you correctly. What specific plumbing issue can we help you with today? For example, do you have a leak, clog, or need a repair?"
        )
        # Set state to await clearer intent
        call_dialog_state[call_sid] = {'intent': intent, 'step': 'awaiting_clear_intent'}
        append_stream_and_pause(twiml)
        _mark_progress(call_sid, "clearer_intent_requested", "asked for clearer plumbing issue details")
        return twiml

    # If followup_text is provided, treat as user's response to scheduling prompt (no <Gather>, keep streaming)
    if followup_text:
        text_norm = (followup_text or '').lower().strip()
        state = call_dialog_state.get(call_sid, {}) or {}
        logger.info(f"🔍 Processing followup '{followup_text}' for {call_sid}, current state: {state.get('step', 'none')}")
        # New: if utterance doesn't match any recognizable intent cues, ask to repeat
        if is_noise_or_unknown(text_norm):
            await add_tts_or_say_to_twiml(twiml, call_sid, "Sorry, I didn't catch that. Could you please repeat what you said?")
            # Keep current step or default to path choice
            if not state.get('step'):
                call_dialog_state[call_sid] = {'intent': intent, 'step': 'awaiting_path_choice'}
            else:
                call_dialog_state[call_sid] = state
            # Per-step attempts and escalation
            effective_state = call_dialog_state.get(call_sid, {})
            current_step = effective_state.get('step', 'unknown')
            step_attempts = conversation_manager.increment_step_attempts(call_sid, current_step)
            if conversation_manager.should_handoff_due_to_step_attempts(call_sid, current_step):
                logger.info(f"🤝 HANDOFF: Too many attempts ({step_attempts}) at step '{current_step}' for {call_sid} - transferring to human dispatch")
                try:
                    await add_tts_or_say_to_twiml(
                        twiml,
                        call_sid,
                        "I'm having trouble understanding. Let me connect you with our dispatch team who can better assist you."
                    )
                except Exception:
                    pass
                number = getattr(settings, "DISPATCH_NUMBER", "+14693096560")
                twiml.dial(number)
                st = call_info_store.setdefault(call_sid, {})
                st["handoff_requested"] = True
                st["handoff_reason"] = f"too_many_attempts_{current_step}"
                call_info_store[call_sid] = st
                call_dialog_state.pop(call_sid, None)
                return twiml
            append_stream_and_pause(twiml)
            _mark_no_progress(call_sid, f"noise_or_unknown: {text_norm}")
            return twiml
        
        # Handle awaiting_clear_intent step - user responding to clarification request
        if state.get('step') == 'awaiting_clear_intent':
            # Check if this is still a goodbye statement
            if is_goodbye_statement(followup_text):
                await add_tts_or_say_to_twiml(twiml, call_sid, "Thank you for calling SafeHarbour Plumbing Services. Have a great day!")
                return twiml
            
            # Try to extract intent from the clarified response
            try:
                from ..flows.intents import extract_plumbing_intent
                new_intent = await extract_plumbing_intent(followup_text)
                
                # Check if we now have a clearer intent
                if new_intent and has_no_clear_service_intent(new_intent):
                    # Still unclear - check clarification attempts
                    clarification_count = conversation_manager.increment_clarification_attempts(call_sid)
                    logger.info(f"❓ STILL UNCLEAR: Intent still unclear after clarification attempt #{clarification_count} for {call_sid}")
                    
                    # If we've asked for clarification too many times, transfer to human dispatch
                    if conversation_manager.should_handoff_due_to_clarification_attempts(call_sid):
                        logger.info(f"🤝 HANDOFF: Too many clarification attempts ({clarification_count}) for unclear intent - transferring to human dispatch")
                        await add_tts_or_say_to_twiml(
                            twiml, 
                            call_sid, 
                            "I'm having trouble understanding the specific plumbing issue you need help with. Let me connect you with our dispatch team who can better assist you."
                        )
                        conversation_manager.reset_clarification_attempts(call_sid)
                        return twiml
                    else:
                        # Ask for clarification one more time
                        await add_tts_or_say_to_twiml(
                            twiml, 
                            call_sid, 
                            "I'm still having trouble understanding your specific plumbing issue. Could you tell me in simple terms what's wrong? For example, 'my toilet is clogged' or 'my faucet is leaking'."
                        )
                        # Keep them in the clarification state
                        return twiml
                else:
                    # Now we have a clear intent - proceed with booking flow
                    logger.info(f"✅ Clarified intent for {call_sid}: {new_intent}")
                    # Update the intent and proceed with normal flow
                    intent.update(new_intent)
                    # Continue to normal flow handling below
                    
            except Exception as e:
                logger.error(f"Failed to re-extract intent for {call_sid}: {e}")
                await add_tts_or_say_to_twiml(
                    twiml, 
                    call_sid, 
                    "I'm having trouble understanding. Let me connect you with one of our dispatchers who can better assist you."
                )
                return twiml
        
        # Handle awaiting_problem_details step - user providing more details about their problem
        if state.get('step') == 'awaiting_problem_details':
            # Save the detailed response as notes with specific how/when information
            detailed_notes = f"Customer details - How and when it started: {followup_text}"
            
            # Ensure job section exists and update description
            if 'job' not in intent:
                intent['job'] = {}
            intent['job']['description'] = detailed_notes
            
            # Update the dialog state to preserve the enhanced intent
            state['intent'] = intent
            call_dialog_state[call_sid] = state
            
            # Log the detailed information prominently
            logger.info(f"💬 RECEIVED DETAILED PROBLEM DESCRIPTION for {call_sid}:")
            logger.info(f"   🔧 Service Type: {intent.get('job', {}).get('type', 'plumbing issue')}")
            logger.info(f"   📝 Customer's description of how and when it started: {followup_text}")
            logger.info(f"   💾 Saved as job notes: {detailed_notes}")
            logger.info(f"   ✅ Problem details collected successfully for {call_sid}")
            
            # Get job type for the response
            job_type = intent.get('job', {}).get('type', 'plumbing issue')
            urgency = intent.get('job', {}).get('urgency', 'flex')
            
            # Now proceed with the original emergency vs scheduling flow
            if urgency == 'emergency':
                try:
                    calendar_adapter = CalendarAdapter()
                    now = datetime.now()
                    # Emergency: at least 30 minutes from now, quarter-hour aligned, 1h buffer from other jobs
                    earliest = now + timedelta(minutes=30)
                    suggested = find_next_compliant_slot(earliest, emergency=True)
                    # Send magiclink immediately and hold this time (skip actual SMS in flow for now)
                    ok = True
                    await add_tts_or_say_to_twiml(twiml, call_sid, f"Thanks for telling me more about your {_speakable(job_type)}. This sounds urgent. The closest available technician is {_format_slot(suggested)}. Do you want this time? Please say YES or NO.")
                    call_dialog_state[call_sid] = {'intent': intent, 'step': 'awaiting_time_confirm', 'suggested_time': suggested}
                except Exception as e:
                    logger.error(f"Emergency slot suggestion failed: {e}")
                    await add_tts_or_say_to_twiml(twiml, call_sid, "Thanks. Checking availability now.")
                    call_dialog_state[call_sid] = {'intent': intent, 'step': 'awaiting_time_confirm'}
            else:
                # Ask for path: emergency vs schedule (combined with thank you message)
                await add_tts_or_say_to_twiml(
                    twiml,
                    call_sid,
                    f"Thanks for telling me more about your {_speakable(job_type)}. For your {_speakable(job_type)}, is this an emergency, or would you like to book a technician to come check it out?"
                )
                call_dialog_state[call_sid] = {'intent': intent, 'step': 'awaiting_path_choice'}
            
            append_stream_and_pause(twiml)
            _mark_progress(call_sid, "problem_details_collected", f"collected detailed problem description: {followup_text[:50]}...")
            return twiml
        
        # New: awaiting_location_confirm step
        if False and state.get('step') == 'awaiting_location_confirm':
            logger.info(f"🔍 In awaiting_location_confirm step for {call_sid}, text: '{text_norm}'")
            # Check if this is a duplicate of last processed text to prevent double-processing
            last_processed = state.get('last_processed_text', '')
            if text_norm.strip() == last_processed.strip() and text_norm.strip():
                logger.info(f"🚫 Ignoring duplicate input: '{text_norm}' for {call_sid}")
                await add_tts_or_say_to_twiml(twiml, call_sid, "Sorry, I didn't catch that. Could you please repeat what you said?")
                append_stream_and_pause(twiml)
                return twiml
            # Flexible confirmation and noise filtering
            confirmation_keywords = ['done', 'finished', 'completed', 'yes', 'okay', 'ok', 'ready', 'confirm', 'confirmed']
            is_confirmation = any(k in text_norm for k in confirmation_keywords)
            # Very short responses are often 'done' misheard
            if not is_confirmation and len(text_norm) < 10:
                is_confirmation = True
            # Ignore unrelated URL/review chatter and background noise
            if not is_confirmation:
                noise_patterns = [
                    r'(https?://|www\.|\.[a-z]{2,6}\b)', 
                    r'thank you for watching',
                    r'subscribe.*channel',
                    r'like.*comment',
                    r'video.*description',
                    r'pissedconsumer',
                    r'review'
                ]
                if any(re.search(pattern, text_norm) for pattern in noise_patterns):
                    await add_tts_or_say_to_twiml(twiml, call_sid, "Please just say 'done' when you're ready to confirm your appointment.")
                    append_stream_and_pause(twiml)
                    return twiml
            if is_confirmation:
                logger.info(f"✅ User confirmed location with: '{text_norm}' for {call_sid}")
                # Mark this text as processed to prevent duplicates
                state['last_processed_text'] = text_norm
                call_dialog_state[call_sid] = state
                # Mark user as confirmed in mocked state
                ml_state = magiclink_state.get(call_sid, {})
                if ml_state.get("mocked"):
                    ml_state["user_confirmed"] = True
                    magiclink_state[call_sid] = ml_state
                    logger.info(f"📍 MOCK: User confirmed location for {call_sid}")
                
                # Check location status (will now return True for mocked confirmed users)
                present = await _magiclink_check_status(call_sid)
                logger.info(f"🗺️ Location status check result for {call_sid}: {present}")
                if present:
                    # After location is received, send booking to operator and tell user to hold
                    suggested_time = state.get('suggested_time')
                    logger.info(f"🕒 DEBUG: suggested_time type={type(suggested_time)}, value={suggested_time}")
                    if isinstance(suggested_time, datetime):
                        # Send booking confirmation to operator frontend
                        await _send_booking_to_operator(call_sid, intent, suggested_time)
                        logger.info(f"✅ Confirmation sent to operator for {call_sid}")
                        
                        await add_tts_or_say_to_twiml(
                            twiml,
                            call_sid,
                            f"Perfect! Please hold while our operator confirms your appointment for {_format_slot(suggested_time)}."
                        )
                        state['step'] = 'awaiting_operator_confirm'
                        call_dialog_state[call_sid] = state
                        logger.info(f"🔄 DEBUG: Advanced state to awaiting_operator_confirm for {call_sid}")
                        append_stream_and_pause(twiml)
                        return twiml
                    else:
                        logger.error(f"🚨 DEBUG: suggested_time is not datetime: {suggested_time}, skipping operator confirmation")
                    # No time held; ask for date/time
                    await add_tts_or_say_to_twiml(twiml, call_sid, "Got your location. What date and time?")
                    state['step'] = 'awaiting_time'
                    call_dialog_state[call_sid] = state
                    append_stream_and_pause(twiml)
                    return twiml
                else:
                    await add_tts_or_say_to_twiml(twiml, call_sid, "I haven't received your location yet. Please open the link I texted and allow location access, then say 'done'.")
                    append_stream_and_pause(twiml)
                    return twiml
        if state.get('step') == 'awaiting_operator_confirm':
            finalized = await _finalize_booking_if_ready(call_sid)
            if finalized:
                suggested_time = state.get('suggested_time')
                job_type = intent.get('job', {}).get('type', 'plumbing service')
                time_str = _format_slot(suggested_time) if isinstance(suggested_time, datetime) else "your requested time"
                await add_tts_or_say_to_twiml(
                    twiml, 
                    call_sid, 
                    f"Thanks! Your appointment is confirmed for {time_str}. Thanks for choosing SafeHarbour Plumbing Services."
                )
                call_dialog_state[call_sid] = {'intent': intent, 'step': 'post_booking_qa'}
                append_stream_and_pause(twiml)
                return twiml
            else:
                await add_tts_or_say_to_twiml(twiml, call_sid, "Please continue to hold while our operator confirms your booking.")
                append_stream_and_pause(twiml)
                return twiml
        # Confirmation step: user can confirm or change the suggested slot - STRICT YES/NO ONLY
        if state.get('step') == 'awaiting_time_confirm':
            if is_strict_affirmative_response(followup_text):
                logger.info(f"✅ YES DETECTED: User confirmed appointment for {call_sid} with response: '{followup_text}'")
                # Reset clarification attempts on successful confirmation
                conversation_manager.reset_clarification_attempts(call_sid)
                conversation_manager.reset_step_attempts(call_sid, 'awaiting_time_confirm')
                # User said YES - proceed to operator
                suggested_time = state.get('suggested_time')
                if isinstance(suggested_time, datetime):
                    try:
                        await _send_booking_to_operator(call_sid, intent, suggested_time)
                    except Exception as e:
                        logger.debug(f"Failed to broadcast booking to operator: {e}")
                    await add_tts_or_say_to_twiml(twiml, call_sid, "Perfect! You'll get an SMS confirmation. Thanks for choosing SafeHarbour!")
                    twiml.hangup()
                    state['step'] = 'awaiting_operator_confirm'
                    call_dialog_state[call_sid] = state
                    _mark_progress(call_sid, "appointment_confirmed", f"user confirmed appointment for {_format_slot(suggested_time)}")
                    return twiml
            elif is_strict_negative_response(followup_text):
                logger.info(f"❌ NO DETECTED: User declined appointment for {call_sid} with response: '{followup_text}'")
                # Reset clarification attempts on clear negative response
                conversation_manager.reset_clarification_attempts(call_sid)
                conversation_manager.reset_step_attempts(call_sid, 'awaiting_time_confirm')
                # User said NO - go back to scheduling
                await add_tts_or_say_to_twiml(twiml, call_sid, "No problem. What date and time works better?")
                call_dialog_state[call_sid] = {'intent': intent, 'step': 'awaiting_time'}
                append_stream_and_pause(twiml)
                _mark_progress(call_sid, "appointment_declined", "user declined appointment, asking for different time")
                return twiml
            else:
                # Ambiguous response - check clarification attempts before asking again
                clarification_count = conversation_manager.increment_clarification_attempts(call_sid)
                logger.info(f"❓ AMBIGUOUS RESPONSE: User response '{followup_text}' for {call_sid} was not clearly yes or no - clarification attempt #{clarification_count}")
                # Also track per-step attempts for awaiting_time_confirm
                step_attempts = conversation_manager.increment_step_attempts(call_sid, 'awaiting_time_confirm')
                if conversation_manager.should_handoff_due_to_step_attempts(call_sid, 'awaiting_time_confirm'):
                    logger.info(f"🤝 HANDOFF: Too many attempts ({step_attempts}) at step 'awaiting_time_confirm' for {call_sid} - transferring to human dispatch")
                    try:
                        await add_tts_or_say_to_twiml(twiml, call_sid, "I'm having trouble understanding your response. Let me connect you with our dispatch team who can help you schedule your appointment.")
                    except Exception:
                        pass
                    number = getattr(settings, "DISPATCH_NUMBER", "+14693096560")
                    twiml.dial(number)
                    st = call_info_store.setdefault(call_sid, {})
                    st["handoff_requested"] = True
                    st["handoff_reason"] = "too_many_attempts_awaiting_time_confirm"
                    call_info_store[call_sid] = st
                    call_dialog_state.pop(call_sid, None)
                    return twiml
                
                # If we've asked for clarification too many times, transfer to human dispatch
                if conversation_manager.should_handoff_due_to_clarification_attempts(call_sid):
                    logger.info(f"🤝 HANDOFF: Too many clarification attempts ({clarification_count}) for {call_sid} - transferring to human dispatch")
                    await add_tts_or_say_to_twiml(twiml, call_sid, "I'm having trouble understanding your response. Let me connect you with our dispatch team who can help you schedule your appointment.")
                    # Reset attempts and transition to operator handoff
                    conversation_manager.reset_clarification_attempts(call_sid)
                    state['step'] = 'awaiting_operator_confirm'
                    call_dialog_state[call_sid] = state
                    append_stream_and_pause(twiml)
                    return twiml
                else:
                    await add_tts_or_say_to_twiml(twiml, call_sid, "I'm having trouble understanding your response. Let me connect you with our dispatch team who can help you schedule your appointment.")
                    # Reset attempts and transition to operator handoff
                    conversation_manager.reset_step_attempts(call_sid, 'awaiting_operator_confirm')
                    state['step'] = 'awaiting_operator_confirm'
                    call_dialog_state[call_sid] = state
                    append_stream_and_pause(twiml)
                    return twiml
            # If user provided a new date/time at confirmation step, re-parse and re-suggest
            newly_parsed = parse_human_datetime(followup_text)
            if newly_parsed:
                calendar_adapter = CalendarAdapter()
                events = []
                if getattr(calendar_adapter, 'enabled', False):
                    end_time = newly_parsed + timedelta(hours=2)
                    events = calendar_adapter.get_events(start_date=newly_parsed, end_date=end_time)
                if not events:
                    # Skip SMS and just set up mock state directly
                    magiclink_state[call_sid] = {
                        "token": f"mock_token_{call_sid}",
                        "sent": True,
                        "user_confirmed": False,
                        "operator_confirmed": False,
                        "mocked": True
                    }
                    await add_tts_or_say_to_twiml(twiml, call_sid, f"I can schedule you for {_format_slot(newly_parsed)}. Do you want this time? Please say YES or NO.")
                    call_dialog_state[call_sid] = {'intent': intent, 'step': 'awaiting_time_confirm', 'suggested_time': newly_parsed}
                else:
                    # Suggest next available 2h window and send location link
                    next_available = newly_parsed + timedelta(hours=2)
                    if getattr(calendar_adapter, 'enabled', False):
                        for i in range(1, 8):
                            slot_start = newly_parsed + timedelta(hours=2*i)
                            slot_end = slot_start + timedelta(hours=2)
                            slot_events = calendar_adapter.get_events(start_date=slot_start, end_date=slot_end)
                            if not slot_events:
                                next_available = slot_start
                                break
                    # try:
                    #     ok = await _send_magiclink_sms(call_sid)
                    # except Exception:
                    #     ok = False
                    ok = True  # Skip SMS for now, just wait for "done"
                    if ok:
                        await add_tts_or_say_to_twiml(twiml, call_sid, f"That time looks busy. The next available is {_format_slot(next_available)}. Do you want this time? Please say YES or NO.")
                        call_dialog_state[call_sid] = {'intent': intent, 'step': 'awaiting_time_confirm', 'suggested_time': next_available}
                    else:
                        await add_tts_or_say_to_twiml(twiml, call_sid, f"That time looks busy. The next available is {_format_slot(next_available)}. Do you want this time? Please say YES or NO.")
                        call_dialog_state[call_sid] = {'intent': intent, 'step': 'awaiting_time_confirm', 'suggested_time': next_available}
                append_stream_and_pause(twiml)
                return twiml
        # Path choice handling first
        if call_dialog_state.get(call_sid, {}).get('step') == 'awaiting_path_choice':
            if any(k in text_norm for k in ['emergency', 'urgent', 'immediately']):
                # Immediate path: choose closest slot, do not book yet
                try:
                    # Emergency path: at least 30 minutes from now, quarter-hour aligned, 1h buffer
                    now = datetime.now()
                    earliest = now + timedelta(minutes=30)
                    suggested = find_next_compliant_slot(earliest, emergency=True)
                    await add_tts_or_say_to_twiml(
                        twiml,
                        call_sid,
                        f"Understood. The closest available slot is {_format_slot(suggested)}. Do you want this time? Please say YES or NO."
                    )
                    call_dialog_state[call_sid] = {'intent': intent, 'step': 'awaiting_time_confirm', 'suggested_time': suggested}
                except Exception as e:
                    logger.error(f"Emergency path suggestion failed: {e}")
                    await add_tts_or_say_to_twiml(twiml, call_sid, "I'm checking the earliest availability. One moment, please.")
                    call_dialog_state[call_sid] = {'intent': intent, 'step': 'awaiting_time_confirm'}
                append_stream_and_pause(twiml)
                logger.info(f"Handled path choice (emergency) for CallSid={call_sid}")
                _mark_progress(call_sid, "emergency_path_chosen", f"user chose emergency path for {job_type}")
                return twiml
            elif any(k in text_norm for k in ['schedule', 'book', 'technician', 'come check', 'come out', 'appointment']):
                await add_tts_or_say_to_twiml(twiml, call_sid, f"Great. Tell me your preferred time, or say 'earliest'.")
                call_dialog_state[call_sid] = {'intent': intent, 'step': 'awaiting_time'}
                # Reset attempts for previous step and proceed
                conversation_manager.reset_step_attempts(call_sid, 'awaiting_path_choice')
                append_stream_and_pause(twiml)
                logger.info(f"Handled path choice (schedule) for CallSid={call_sid}")
                _mark_progress(call_sid, "schedule_path_chosen", f"user chose schedule path for {job_type}")
                return twiml
        # If user gives a date/time directly, recognize but don't book yet
        try:
            preferred_time = parse_human_datetime(followup_text)
            if not preferred_time:
                preferred_time = gpt_infer_datetime_phrase(followup_text)
            if preferred_time:
                try:
                    # Regular jobs: align to quarter-hour and respect 1h buffer
                    requested = _ceil_to_quarter_hour(preferred_time)
                    cal = CalendarAdapter()
                    if _is_slot_free_with_buffer(requested, duration_minutes=120, buffer_minutes=60, calendar=cal):
                        await add_tts_or_say_to_twiml(
                            twiml,
                            call_sid,
                            f"Thanks. I can schedule you for {_format_slot(requested)} for your {_speakable(job_type)}. Do you want this time? Please say YES or NO."
                        )
                        call_dialog_state[call_sid] = {'intent': intent, 'step': 'awaiting_time_confirm', 'suggested_time': requested}
                    else:
                        # Find the next compliant slot after the requested time
                        next_available = find_next_compliant_slot(requested, emergency=False)
                        await add_tts_or_say_to_twiml(
                            twiml,
                            call_sid,
                            f"That time looks busy. The next available is {_format_slot(next_available)}. Do you want this time? Please say YES or NO."
                        )
                        call_dialog_state[call_sid] = {'intent': intent, 'step': 'awaiting_time_confirm', 'suggested_time': next_available}
                except Exception as e:
                    logger.error(f"Scheduling suggestion failed: {e}")
                    await add_tts_or_say_to_twiml(twiml, call_sid, "I'm having trouble checking availability right now. I can connect you to a human if you prefer.")
                    call_dialog_state[call_sid] = {'intent': intent, 'step': 'awaiting_time_confirm'}
                append_stream_and_pause(twiml)
                logger.info(f"Handled followup date/time recognition for CallSid={call_sid}")
                _mark_progress(call_sid, "date_time_recognized", f"recognized date/time: {preferred_time}")
                return twiml
        except Exception as e:
            logger.error(f"Datetime parsing failed: {e}")
        # Prompt again if nothing parsed
        await add_tts_or_say_to_twiml(twiml, call_sid, "Please say a date and time, like 'Friday at 3 PM', or say 'earliest'.")
        call_dialog_state[call_sid] = {'intent': intent, 'step': 'awaiting_time'}
        # Per-step attempts and escalation for awaiting_time
        step_attempts = conversation_manager.increment_step_attempts(call_sid, 'awaiting_time')
        if conversation_manager.should_handoff_due_to_step_attempts(call_sid, 'awaiting_time'):
            logger.info(f"🤝 HANDOFF: Too many attempts ({step_attempts}) at step 'awaiting_time' for {call_sid} - transferring to human dispatch")
            try:
                await add_tts_or_say_to_twiml(
                    twiml,
                    call_sid,
                    "I'm having trouble scheduling via voice. Let me connect you with our dispatcher who can help schedule your appointment."
                )
            except Exception:
                pass
            number = getattr(settings, "DISPATCH_NUMBER", "+14693096560")
            twiml.dial(number)
            st = call_info_store.setdefault(call_sid, {})
            st["handoff_requested"] = True
            st["handoff_reason"] = "too_many_attempts_awaiting_time"
            call_info_store[call_sid] = st
            call_dialog_state.pop(call_sid, None)
            return twiml
        append_stream_and_pause(twiml)
        logger.info(f"Handled followup prompting for CallSid={call_sid}")
        _mark_no_progress(call_sid, "could not parse date/time, prompting again")
        return twiml

    # Initial intent handling (no <Gather>; we keep streaming and listen continuously)
    # This section is now handled in response_to_user_speech for the first plumbing issue
    # For followup responses, proceed with the original emergency vs scheduling flow
    if urgency == 'emergency':
        try:
            calendar_adapter = CalendarAdapter()
            now = datetime.now()
            # Emergency: at least 30 minutes from now, quarter-hour aligned, 1h buffer from other jobs
            earliest = now + timedelta(minutes=30)
            suggested = find_next_compliant_slot(earliest, emergency=True)
            # Send magiclink immediately and hold this time (skip actual SMS in flow for now)
            ok = True
            await add_tts_or_say_to_twiml(twiml, call_sid, f"This sounds urgent. The closest available technician for {_speakable(job_type)} is {_format_slot(suggested)}. Do you want this time? Please say YES or NO.")
            call_dialog_state[call_sid] = {'intent': intent, 'step': 'awaiting_time_confirm', 'suggested_time': suggested}
            _mark_progress(call_sid, "emergency_slot_suggested", f"suggested emergency slot: {_format_slot(suggested)}")
            conversation_manager.reset_step_attempts(call_sid, 'awaiting_path_choice')
        except Exception as e:
            logger.error(f"Emergency slot suggestion failed: {e}")
            await add_tts_or_say_to_twiml(twiml, call_sid, "I'm checking the earliest availability. One moment, please.")
            call_dialog_state[call_sid] = {'intent': intent, 'step': 'awaiting_time_confirm'}
            _mark_no_progress(call_sid, "emergency slot suggestion failed")
    else:
        # Check if we need to ask for problem details first
        dialog = call_dialog_state.get(call_sid, {})
        if not dialog.get('problem_details_asked'):
            # Ask for problem details first
            await add_tts_or_say_to_twiml(
                twiml,
                call_sid,
                f"Tell me more about your {_speakable(job_type)}, specifically how and when it started."
            )
            call_dialog_state[call_sid] = {'intent': intent, 'step': 'awaiting_problem_details', 'problem_details_asked': True}
            _mark_progress(call_sid, "problem_details_requested_initial", f"asked for problem details for {job_type}")
        else:
            # Problem details already collected, proceed to path choice
            await add_tts_or_say_to_twiml(
                twiml,
                call_sid,
                f"Got it. For your {_speakable(job_type)}, is this an emergency, or would you like to book a technician to come check it out?"
            )
            call_dialog_state[call_sid] = {'intent': intent, 'step': 'awaiting_path_choice'}
            _mark_progress(call_sid, "path_choice_requested", f"asked for emergency vs schedule choice for {job_type}")
            conversation_manager.reset_step_attempts(call_sid, 'awaiting_time')
        append_stream_and_pause(twiml)
        logger.info(f"Handled intent {intent} for CallSid={call_sid}")
        _mark_progress(call_sid, "intent_handled_final", f"completed intent handling for {job_type}")
        return twiml

def validate_and_enhance_extraction(args: dict, original_text: str, call_sid: str = None) -> dict:
    """Validate and enhance extracted data with additional processing"""
    
    # Ensure required fields exist
    if 'intent' not in args:
        args['intent'] = 'BOOK_JOB'
    
    # Calculate intent confidence for the original text
    try:
        # Use the same intent classification system for confidence
        import asyncio
        if asyncio.iscoroutinefunction(classify_transcript_intent):
            # If in async context, calculate intent confidence
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Schedule intent confidence calculation
                intent_confidence = 0.7  # Default for now, will be calculated properly
            else:
                intent, intent_confidence = loop.run_until_complete(classify_transcript_intent(original_text))
        else:
            intent_confidence = 0.7  # Default fallback
    except:
        intent_confidence = 0.7  # Default fallback if async context issues
    
    # Enhance job type recognition with keyword matching and multi-intent detection
    multi_intent_result = infer_multiple_job_types_from_text(original_text)
    
    if not args.get('job', {}).get('type'):
        args['job'] = args.get('job', {})
        args['job']['type'] = multi_intent_result['primary'] or infer_job_type_from_text(original_text)
    
    # Add secondary intents if detected
    if multi_intent_result['secondary']:
        args['job']['secondary_intents'] = multi_intent_result['secondary']
    
    # Enhance description with secondary intents
    if multi_intent_result['description_suffix']:
        current_description = args.get('job', {}).get('description', '')
        if current_description:
            # Add suffix with a space separator
            args['job']['description'] = f"{current_description} {multi_intent_result['description_suffix']}"
        else:
            # Create a basic description with the detected intents
            args['job']['description'] = multi_intent_result['description_suffix']
    
    # Improve urgency classification
    if not args.get('job', {}).get('urgency'):
        args['job']['urgency'] = infer_urgency_from_text(original_text)
    
    # Extract phone numbers if missing
    if not args.get('customer', {}).get('phone'):
        phone = extract_phone_number(original_text)
        if phone:
            args['customer'] = args.get('customer', {})
            args['customer']['phone'] = phone
    
    # Include collected customer name from dialog state
    if call_sid:
        dialog = call_dialog_state.get(call_sid, {})
        customer_name = dialog.get('customer_name')
        if customer_name and not args.get('customer', {}).get('name'):
            args['customer'] = args.get('customer', {})
            args['customer']['name'] = customer_name
    
    # Enhance address extraction
    if not args.get('location', {}).get('raw_address'):
        address = extract_address(original_text)
        if address:
            args['location'] = args.get('location', {})
            args['location']['raw_address'] = address
    
    # Calculate confidence scores with intent confidence
    confidence = calculate_confidence_scores(args, original_text, intent_confidence)
    args['confidence'] = confidence
    
    # Determine handoff based on confidence and completeness
    args['handoff_needed'] = should_handoff_to_human(args, confidence, call_sid)
    
    return args



def infer_urgency_from_text(text: str) -> str:
    """Infer urgency from text using keyword matching"""
    text_lower = text.lower()
    
    # Emergency indicators
    if any(word in text_lower for word in ['emergency', 'burst', 'flooding', 'water everywhere', 'immediately', 'urgent']):
        return 'emergency'
    
    # Same day indicators
    if any(word in text_lower for word in ['today', 'asap', 'soon', 'quickly', 'urgent']):
        return 'same_day'
    
    # Flexible indicators
    if any(word in text_lower for word in ['tomorrow', 'next week', 'when convenient', 'schedule', 'appointment']):
        return 'flex'
    
    return 'flex'  # Default to flexible

# TTS: synthesize with ElevenLabs or OpenAI 4o TTS
async def synthesize_tts(text: str) -> Optional[bytes]:
    # Check if ElevenLabs TTS is enabled and configured
    if (settings.USE_ELEVENLABS_TTS and 
        settings.ELEVENLABS_API_KEY and 
        settings.ELEVENLABS_VOICE_ID):
        try:
            from elevenlabs import ElevenLabs
            
            # Create ElevenLabs client with API key
            elevenlabs_client = ElevenLabs(api_key=settings.ELEVENLABS_API_KEY)
            
            # Use configured voice ID or default to the specified one
            voice_id = settings.ELEVENLABS_VOICE_ID
            model_id = settings.ELEVENLABS_MODEL_ID or "eleven_multilingual_v2"
            
            # Generate audio using ElevenLabs
            logger.info(f"🎤 Using ElevenLabs TTS (voice: {voice_id}, model: {model_id})")
            audio_stream = elevenlabs_client.text_to_speech.convert(
                voice_id=voice_id,
                text=text,
                model_id=model_id
            )
            
            # Convert iterator to bytes
            audio = b"".join(audio_stream)
            
            if audio:
                logger.debug(f"ElevenLabs TTS generated {len(audio)} bytes for text: {text[:50]}...")
                return audio
            else:
                logger.error("ElevenLabs TTS returned empty response")
                
        except Exception as e:
            logger.error(f"ElevenLabs TTS failed: {e}")
            logger.info("Falling back to OpenAI TTS...")
    
    # If ElevenLabs is disabled or not configured, use OpenAI TTS
    if not settings.USE_ELEVENLABS_TTS:
        logger.info("🎤 ElevenLabs TTS disabled via USE_ELEVENLABS_TTS=False, using OpenAI TTS")
    
    # Use OpenAI TTS (either as fallback or primary choice)
    try:
        # Use the existing global OpenAI client
        voice = getattr(settings, 'OPENAI_TTS_VOICE', 'alloy')  # Default to 'alloy' voice
        model = getattr(settings, 'OPENAI_TTS_MODEL', 'tts-1')  # Default to 'tts-1' model
        speed = settings.OPENAI_TTS_SPEED  # Use configured speed (0.25 to 4.0)
        
        logger.info(f"🎤 Using OpenAI TTS (voice: {voice}, model: {model}, speed: {speed})")
        
        response = client.audio.speech.create(
            model=model,
            voice=voice,
            input=text,
            response_format="mp3",
            speed=speed
        )
        
        # Convert response to bytes
        audio_content = b""
        for chunk in response.iter_bytes():
            audio_content += chunk
            
        if audio_content:
            logger.debug(f"OpenAI TTS generated {len(audio_content)} bytes for text: {text[:50]}...")
            return audio_content
        else:
            logger.error("OpenAI TTS returned empty response")
            return None
            
    except Exception as e:
        logger.error(f"OpenAI TTS failed: {e}")
        return None

async def _activate_speech_gate(call_sid: str, text: str):
    """Activate speech gate to prevent user speech processing during bot TTS output"""
    logger.info(f"🔇 ACTIVATING SPEECH GATE for {call_sid} with text length: {len(text)}")
    try:
        # Ensure vad_state exists
        if call_sid not in vad_states:
            vad_states[call_sid] = {
                'speech_gate_active': False,
                'bot_speaking': False,
                'is_speaking': False,
                'pending_audio': bytearray(),
                'stream_start_time': time.time(),
                'has_received_media': False,
            }
            logger.info(f"🔄 Initialized vad_state for {call_sid}")
        
        vad_state = vad_states[call_sid]
        current_time = time.time()
        
        # OPTIMIZED: Much more aggressive timing for faster responses
        # Use character count instead of word count for better accuracy
        char_count = len(text)
        # Estimate ~15 chars per second at 1.5x speed (much faster calculation)
        base_duration = char_count / (15 * settings.OPENAI_TTS_SPEED)
        
        # Cap maximum gate duration to prevent long blocks
        max_gate_duration = 3.0  # Never block longer than 3 seconds
        actual_duration = min(base_duration, max_gate_duration)
        
        # Minimal buffer time for speed
        buffer_time = 0.3  # Reduced from 0.5s
        gate_duration = actual_duration + buffer_time
        
        # Activate the speech gate
        vad_state['speech_gate_active'] = True
        vad_state['bot_speaking'] = True
        vad_state['bot_speech_start_time'] = current_time
        
        # NEW: Track speech gate cycle for comprehensive handoff detection
        # Ensure tracking is properly initialized
        if call_sid not in speech_gate_cycle_tracking:
            speech_gate_cycle_tracking[call_sid] = {
                'total_cycles': 0,
                'consecutive_no_progress': 0,
                'last_progress_time': 0,
                'last_speech_gate_time': 0,
                'last_processed_text': '',
                'last_intent_extracted': None,
                'last_dialog_step': '',
                'call_start_time': current_time,
                'max_cycles_without_progress': 3,
                'max_call_duration_without_progress': 120,
            }
            logger.info(f"🔄 Initialized speech gate cycle tracking for {call_sid}")
        else:
            logger.info(f"🔄 Using existing speech gate cycle tracking for {call_sid}")
        
        cycle_tracking = speech_gate_cycle_tracking[call_sid]
        cycle_tracking['total_cycles'] += 1
        cycle_tracking['last_speech_gate_time'] = current_time
        
        # Initialize call start time if not set
        if cycle_tracking['call_start_time'] == 0:
            cycle_tracking['call_start_time'] = current_time
        
        logger.info(f"🔇 Speech gate activated for {call_sid}: {gate_duration:.2f}s (text: {len(text)} chars) - Cycle #{cycle_tracking['total_cycles']} (no_progress: {cycle_tracking['consecutive_no_progress']})")
        
        # Schedule gate deactivation with shorter delay for more responsive listening
        asyncio.create_task(_deactivate_speech_gate_after_delay(call_sid, gate_duration))
        
    except Exception as e:
        logger.error(f"Failed to activate speech gate for {call_sid}: {e}")

async def _deactivate_speech_gate_after_delay(call_sid: str, delay: float):
    """Deactivate speech gate after estimated TTS completion"""
    try:
        await asyncio.sleep(delay)
        
        vad_state = vad_states.get(call_sid)
        if vad_state:
            vad_state['speech_gate_active'] = False
            vad_state['bot_speaking'] = False
            logger.info(f"🔊 Speech gate deactivated for {call_sid} after {delay:.2f}s")
            
            # Clear any accumulated audio during gate period to avoid processing stale audio
            if vad_state.get('is_speaking'):
                vad_state['is_speaking'] = False
                vad_state['pending_audio'] = bytearray()
                logger.debug(f"Cleared pending audio for {call_sid} after speech gate")
            
            # NEW: Check for handoff conditions after speech gate deactivation
            logger.info(f"🔍 Checking handoff conditions after speech gate deactivation for {call_sid}")
            await _check_speech_gate_handoff_conditions(call_sid)
                
    except Exception as e:
        logger.error(f"Failed to deactivate speech gate for {call_sid}: {e}")

async def _check_speech_gate_handoff_conditions(call_sid: str):
    """Check if handoff is needed based on speech gate cycle tracking"""
    try:
        cycle_tracking = speech_gate_cycle_tracking.get(call_sid, {})
        if not cycle_tracking:
            logger.info(f"🔍 No cycle tracking found for {call_sid}")
            return
        
        logger.info(f"🔍 Checking handoff conditions for {call_sid}: cycles={cycle_tracking.get('total_cycles', 0)}, no_progress={cycle_tracking.get('consecutive_no_progress', 0)}")
        
        current_time = time.time()
        total_cycles = cycle_tracking.get('total_cycles', 0)
        consecutive_no_progress = cycle_tracking.get('consecutive_no_progress', 0)
        last_progress_time = cycle_tracking.get('last_progress_time', 0)
        call_start_time = cycle_tracking.get('call_start_time', current_time)
        max_cycles = cycle_tracking.get('max_cycles_without_progress', 3)
        max_duration = cycle_tracking.get('max_call_duration_without_progress', 120)
        
        # Calculate time since last progress
        time_since_progress = current_time - last_progress_time if last_progress_time > 0 else current_time - call_start_time
        call_duration = current_time - call_start_time
        
        # Check handoff conditions
        handoff_reasons = []
        
        # Condition 1: Too many consecutive cycles without progress
        if consecutive_no_progress >= max_cycles:
            handoff_reasons.append(f"{consecutive_no_progress} consecutive cycles without progress >= {max_cycles}")
        
        # Condition 2: Too much time without progress
        if time_since_progress >= max_duration:
            handoff_reasons.append(f"{time_since_progress:.1f}s without progress >= {max_duration}s")
        
        # Condition 3: Call has been going too long without meaningful progress
        if call_duration >= max_duration * 2 and consecutive_no_progress >= 2:
            handoff_reasons.append(f"call duration {call_duration:.1f}s with {consecutive_no_progress} cycles without progress")
        
        if handoff_reasons:
            reasons_str = ", ".join(handoff_reasons)
            logger.warning(f"🚨 SPEECH GATE HANDOFF TRIGGERED for {call_sid}: {reasons_str}")
            logger.warning(f"   📊 Cycle stats: total={total_cycles}, no_progress={consecutive_no_progress}, time_since_progress={time_since_progress:.1f}s")
            logger.error(f"🚨 AUTOMATIC HANDOFF REQUIRED: {call_sid} will be transferred to dispatch")
            
            # Perform automatic handoff to dispatch
            await _perform_automatic_handoff(call_sid, f"speech_gate_cycles: {reasons_str}")
        
    except Exception as e:
        logger.error(f"Error checking speech gate handoff conditions for {call_sid}: {e}")

async def _perform_automatic_handoff(call_sid: str, reason: str):
    """Perform automatic handoff to dispatch due to speech gate cycle failures"""
    try:
        logger.info(f"🤖 AUTOMATIC HANDOFF: Transferring {call_sid} to dispatch due to: {reason}")
        
        # Create TwiML for handoff
        twiml = VoiceResponse()
        await add_tts_or_say_to_twiml(
            twiml, 
            call_sid, 
            "I'm having trouble understanding your request clearly. Let me connect you with our dispatch team who can better assist you."
        )
        twiml.dial(settings.DISPATCH_NUMBER)
        
        # Mark state to avoid further processing
        st = call_info_store.setdefault(call_sid, {})
        st["handoff_requested"] = True
        st["handoff_reason"] = f"automatic_handoff: {reason}"
        call_info_store[call_sid] = st
        
        # Clear dialog state
        call_dialog_state.pop(call_sid, None)
        
        # Push the handoff TwiML
        await push_twiml_to_call(call_sid, twiml)
        
        logger.info(f"✅ Automatic handoff completed for {call_sid}")
        
    except Exception as e:
        logger.error(f"Failed to perform automatic handoff for {call_sid}: {e}")

def _mark_progress(call_sid: str, progress_type: str, details: str = ""):
    """Mark that meaningful progress has been made in the conversation"""
    try:
        cycle_tracking = speech_gate_cycle_tracking.get(call_sid, {})
        if not cycle_tracking:
            logger.info(f"🔍 No cycle tracking found for progress marking on {call_sid}")
            return
        
        current_time = time.time()
        cycle_tracking['last_progress_time'] = current_time
        cycle_tracking['consecutive_no_progress'] = 0  # Reset counter
        
        logger.info(f"✅ PROGRESS MARKED for {call_sid}: {progress_type} - {details}")
        logger.debug(f"   📊 Progress stats: consecutive_no_progress reset to 0, last_progress_time={current_time}")
        
    except Exception as e:
        logger.error(f"Error marking progress for {call_sid}: {e}")

def _mark_no_progress(call_sid: str, reason: str = ""):
    """Mark that no progress was made in this cycle"""
    try:
        cycle_tracking = speech_gate_cycle_tracking.get(call_sid, {})
        if not cycle_tracking:
            logger.info(f"🔍 No cycle tracking found for no-progress marking on {call_sid}")
            return
        
        cycle_tracking['consecutive_no_progress'] += 1
        current_count = cycle_tracking['consecutive_no_progress']
        
        logger.info(f"❌ NO PROGRESS for {call_sid}: {reason} - consecutive_no_progress={current_count}")
        logger.warning(f"🚨 NO PROGRESS DETECTED: {call_sid} has {current_count} consecutive cycles without progress")
        
    except Exception as e:
        logger.error(f"Error marking no progress for {call_sid}: {e}")

def get_natural_conversation_starter(text: str, dialog: dict, call_sid: str) -> str:
    """
    Choose natural conversation starters based on context to make responses less robotic.
    Returns appropriate phrases like 'Thanks', 'Sounds good', 'OK', etc.
    """
    text_lower = text.lower()
    current_step = dialog.get('step', '')
    
    # Get conversation context
    info = call_info_store.get(call_sid, {})
    segments_count = info.get('segments_count', 0)
    
    # Confirmation and booking contexts
    if any(phrase in text_lower for phrase in ['do you want this time', 'please say yes or no', 'confirm']):
        return "Alright"
    
    # Time-related responses
    if any(phrase in text_lower for phrase in ['i can schedule', 'available', 'earliest', 'time looks busy']):
        return "OK"
    
    # After user provides information (booking details, preferences, etc.)
    if current_step in ['awaiting_time_confirm', 'awaiting_location_confirm'] or segments_count > 1:
        starters = ["Thanks", "Sounds good", "Got it", "Perfect"]
        # Simple rotation based on call activity to add variety
        import time
        starter_index = int(time.time() // 10) % len(starters)  # Changes every 10 seconds
        return starters[starter_index]
    
    # Problem-solving and clarification contexts
    if any(phrase in text_lower for phrase in ['what exactly', 'could you', 'tell me', 'what can we assist']):
        return "Alright"
    
    # Error recovery and re-prompting
    if any(phrase in text_lower for phrase in ["didn't catch", "sorry", "trouble understanding"]):
        return "OK"
    
    # Transfer and handoff contexts
    if any(phrase in text_lower for phrase in ['would you like me to transfer', 'connect you']):
        return "Alright"
    
    # Positive acknowledgments
    if any(phrase in text_lower for phrase in ['great', 'perfect', 'excellent']):
        return "Sounds good"
    
    # Follow-up questions and continued conversation
    if any(phrase in text_lower for phrase in ['what date', 'which time', 'any other', 'anything else']):
        return "OK"
    
    # Default starters for general responses - rotate for variety
    if segments_count > 0:  # Only after initial exchange
        default_starters = ["Alright", "OK", "Thanks"]
        import time
        starter_index = int(time.time() // 15) % len(default_starters)  # Changes every 15 seconds
        return default_starters[starter_index]
    
    # Return empty string for initial responses or when no starter is appropriate
    return ""

async def add_tts_or_say_to_twiml(target, call_sid: str, text: str):
    # Get customer name from dialog state and prepend it to most messages
    dialog = call_dialog_state.get(call_sid, {})
    customer_name = dialog.get('customer_name')
    
    # Don't add name to certain types of messages
    skip_name_prefixes = [
        "hello", "who do i have", "i didn't catch your name", "connecting you", 
        "thanks for trusting", "thank you for calling", "goodbye", "bye",
        "nice to meet you"
    ]
    
    # Check if this message should skip name prefixing
    should_skip_name = any(text.lower().startswith(prefix) for prefix in skip_name_prefixes)
    
    # Prepend name if available and appropriate with natural conversation starters
    if customer_name and not should_skip_name and dialog.get('step') != 'awaiting_name':
        # Choose natural conversation starter based on context
        conversation_starters = get_natural_conversation_starter(text, dialog, call_sid)
        if conversation_starters:
            speak_text = f"{conversation_starters}, {customer_name}, {text}".replace("_", " ")
        else:
            speak_text = f"{customer_name}, {text}".replace("_", " ")
    else:
        speak_text = text.replace("_", " ")
    
    preview = speak_text if len(speak_text) <= 200 else speak_text[:200] + "..."
    
    # Activate speech gate when bot starts speaking
    await _activate_speech_gate(call_sid, speak_text)
    
    if settings.FORCE_SAY_ONLY:
        logger.info(f"🗣️ OpenAI TTS SAY for CallSid={call_sid}: {preview}")
        target.say(speak_text)
        return
    audio = await synthesize_tts(speak_text)
    if audio:
        tts_audio_store[call_sid] = audio
        # Bump version so TwiML <Play> URL changes each time (prevents identical-string dedupe)
        v = int(tts_version_counter.get(call_sid, 0)) + 1
        tts_version_counter[call_sid] = v
        audio_url = f"{settings.EXTERNAL_WEBHOOK_URL}/tts/{call_sid}.mp3?v={v}"
        logger.info(f"🗣️ OpenAI TTS PLAY for CallSid={call_sid}: url={audio_url} bytes={len(audio)} text={preview}")
        target.play(audio_url)
    else:
        logger.info(f"🗣️ OpenAI TTS SAY (fallback) for CallSid={call_sid}: {preview}")
        target.say(speak_text)

# Push updated TwiML mid-call to Twilio
async def push_twiml_to_call(call_sid: str, response: VoiceResponse):
     try:
         twiml_str = str(response)
         # Skip if identical to last TwiML pushed
         prev = last_twiml_store.get(call_sid)
         now_ts = time.time()
         if prev == twiml_str:
             logger.info(f"Skipping TwiML push for {call_sid}: identical to last")
             return
         # Throttle frequent pushes
         last_ts = last_twiml_push_ts.get(call_sid, 0)
         if now_ts - last_ts < TWIML_PUSH_MIN_INTERVAL_SEC:
             logger.info(f"Throttling TwiML push for {call_sid}: pushed {now_ts - last_ts:.2f}s ago")
             return
         last_twiml_store[call_sid] = twiml_str
         last_twiml_push_ts[call_sid] = now_ts
         logger.info(f"🔊 Pushing TwiML to call {call_sid}")
         logger.debug(f"Updating call {call_sid} with TwiML: {twiml_str}")
         if twilio_client is None:
             logger.warning("TwiML push skipped: Twilio client unavailable")
             return
         loop = asyncio.get_event_loop()
         def _update():
             return twilio_client.calls(call_sid).update(twiml=twiml_str)  # type: ignore[union-attr]
         result = await loop.run_in_executor(None, _update)
         logger.info(f"Pushed TwiML update to call {call_sid}; status={getattr(result, 'status', 'unknown')}")
     except Exception as e:
         logger.error(f"Failed to push TwiML directly to call {call_sid}: {e}; attempting URL fallback")
         if twilio_client is None:
             return
         try:
             url = f"{settings.EXTERNAL_WEBHOOK_URL}/twiml/{call_sid}"
             loop = asyncio.get_event_loop()
             def _update_url():
                 return twilio_client.calls(call_sid).update(url=url, method="GET")  # type: ignore[union-attr]
             result = await loop.run_in_executor(None, _update_url)
             logger.info(f"Pushed TwiML via URL to call {call_sid}; status={getattr(result, 'status', 'unknown')} url={url}")
         except Exception as e2:
             logger.error(f"URL fallback also failed for call {call_sid}: {e2}")

def extract_name_from_text(text: str) -> str:
    """Extract customer name from text response"""
    import re
    
    # Normalize and clean the text
    text = text.strip().lower()
    
    # Common name introduction patterns
    name_patterns = [
        r"(?:my name is|i'm|i am|this is|it's|it is|call me)\s+([a-zA-ZÀ-ÿ][a-zA-ZÀ-ÿ\s\-']+)",
        r"^([a-zA-ZÀ-ÿ][a-zA-ZÀ-ÿ\s\-']+?)(?:\s+here|[.,!?]?\s*$)",  # Simple name at start, with optional punctuation
        r"(?:i saw|i met|i know)\s+([a-zA-ZÀ-ÿ][a-zA-ZÀ-ÿ\s\-']+)",  # "I saw Daniel" type patterns
        r"(?:this is|that's|that is)\s+([a-zA-ZÀ-ÿ][a-zA-ZÀ-ÿ\s\-']+)",  # "This is Daniel" type patterns
        r"^(?:um|uh|well|so|like|just)\s+([a-zA-ZÀ-ÿ][a-zA-ZÀ-ÿ\s\-']+)",  # Handle filler words before names
    ]
    
    for pattern in name_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            name = match.group(1).strip().title()
            # Filter out common non-name words
            skip_words = {
                'hello', 'hi', 'hey', 'good', 'morning', 'afternoon', 'evening', 
                'yes', 'yeah', 'yep', 'sure', 'okay', 'ok', 'calling', 'about',
                'speaking', 'here', 'with', 'you', 'the', 'a', 'an', 'and',
                'saw', 'met', 'know', 'is', 'that',
                'thank', 'thanks', 'no', 'nope', 'nah',
                'um', 'uh', 'well', 'so', 'like', 'just'
            }
            # Check if any word in the name is in skip words
            name_words = name.lower().split()
            if (not any(word in skip_words for word in name_words) and 
                len(name) >= 2 and len(name) <= 50 and 
                not any(char.isdigit() for char in name) and
                all(char.isalpha() or char in ['-', "'", ' '] for char in name)):
                
                # For multi-word names, return only the first word
                if ' ' in name:
                    first_name = name.split()[0]
                    # Only return if first name is not a skip word
                    if first_name.lower() not in skip_words:
                        return first_name
                else:
                    return name
    
    # If no name found with regex patterns, try GPT as fallback
    try:
        from openai import OpenAI
        import os
        
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        
        prompt = f"""
        Extract the person's name from this text. Return ONLY the name, nothing else.
        If no clear name is found, return "None".
        
        Examples:
        "um Sean" -> "Sean"
        "I'm John" -> "John"
        "My name is Sarah" -> "Sarah"
        "Thank you" -> "None"
        "Hello" -> "None"
        
        Text: "{text}"
        """
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=10,
            temperature=0
        )
        
        name = response.choices[0].message.content.strip()
        
        # Validate the response
        if name.lower() in ['none', 'no', 'n/a', '']:
            return None
            
        # Basic validation - should be letters, hyphens, apostrophes, reasonable length
        # Allow common punctuation like periods, commas, exclamation marks
        if (name and len(name) >= 2 and len(name) <= 50 and 
            all(char.isalpha() or char in ['-', "'", ' '] for char in name) and
            not any(char.isdigit() for char in text) and
            not any(char in ['@', '#', '$', '%', '&', '*', '+', '=', '<', '>', '[', ']', '{', '}', '(', ')', '|', '\\', '/', '`', '~', '^'] for char in text)):
            return name.title()
            
    except Exception as e:
        logger.debug(f"GPT name extraction failed: {e}")
    
    return None

def extract_phone_number(text: str) -> str:
    """Extract phone number from text"""
    import re
    # Phone number patterns
    patterns = [
        r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b',  # 123-456-7890
        r'\b\(\d{3}\)\s*\d{3}[-.]?\d{4}\b',  # (123) 456-7890
        r'\b\d{10}\b',  # 1234567890
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group()
    
    return None

def extract_address(text: str) -> str:
    """Extract address from text"""
    import re
    # Simple address pattern (number + street)
    pattern = r'\b\d+\s+[A-Za-z\s]+(?:Street|St|Avenue|Ave|Road|Rd|Drive|Dr|Lane|Ln|Boulevard|Blvd)\b'
    match = re.search(pattern, text, re.IGNORECASE)
    if match:
        return match.group()
    
    return None

def calculate_confidence_scores(args: dict, original_text: str, intent_confidence: float = 0.0) -> dict:
    """Calculate confidence scores for extracted data including intent confidence"""
    confidence = {
        "overall": 0.0,
        "fields": {},
        "intent": intent_confidence
    }
    
    # Job type confidence
    job_type = args.get('job', {}).get('type')
    if job_type:
        confidence["fields"]["type"] = 0.9 if job_type in ['leak', 'water_heater', 'clog', 'gas_line', 'sewer_cam', 'plumbing', 'drain_cleaning', 'plumbing_repair', 'plumbing_installation', 'plumbing_replacement', 'plumbing_maintenance', 'plumbing_inspection', 'plumbing_repair', 'plumbing_installation', 'plumbing_replacement', 'plumbing_maintenance', 'plumbing_inspection'] else 0.7
    else:
        confidence["fields"]["type"] = 0.0
    
    # Urgency confidence
    urgency = args.get('job', {}).get('urgency')
    if urgency:
        confidence["fields"]["urgency"] = 0.8 if urgency in ['emergency', 'same_day', 'flex', 'as soon as possible', 'urgent', 'immediately', 'today', 'soon', 'quickly', 'right now'] else 0.5
    else:
        confidence["fields"]["urgency"] = 0.0
       
    # Overall confidence (include intent confidence in calculation)
    field_scores = list(confidence["fields"].values())
    field_scores.append(intent_confidence)  # Include intent confidence
    if field_scores:
        confidence["overall"] = sum(field_scores) / len(field_scores)
    
    if settings.CONFIDENCE_DEBUG_MODE:
        logger.info(f"🔍 Confidence breakdown: overall={confidence['overall']:.3f}, intent={intent_confidence:.3f}, fields={confidence['fields']}")
    
    return confidence

def should_handoff_to_human(args: dict, confidence: dict, call_sid: str = None) -> bool:
    """Determine if human handoff is needed using configurable thresholds and consecutive failure tracking"""
    overall_confidence = confidence.get("overall", 0.0)
    intent_confidence = confidence.get("intent", 0.0)
    
    # Initialize handoff reasons for logging
    handoff_reasons = []
    
    # Track consecutive failures if call_sid is provided
    consecutive_handoff = False
    single_instance_handoff = False
    
    if call_sid:
        # Track intent confidence failures
        if intent_confidence < settings.INTENT_CONFIDENCE_THRESHOLD:
            consecutive_intent_failures[call_sid] += 1
            if settings.CONFIDENCE_DEBUG_MODE:
                logger.info(f"🔢 Intent failure #{consecutive_intent_failures[call_sid]} for {call_sid}")
        else:
            # Reset counter on success
            if consecutive_intent_failures[call_sid] > 0:
                if settings.CONFIDENCE_DEBUG_MODE:
                    logger.info(f"✅ Intent confidence recovered for {call_sid}, resetting counter")
                consecutive_intent_failures[call_sid] = 0
        
        # Track overall confidence failures
        if overall_confidence < settings.OVERALL_CONFIDENCE_THRESHOLD:
            consecutive_overall_failures[call_sid] += 1
            if settings.CONFIDENCE_DEBUG_MODE:
                logger.info(f"🔢 Overall failure #{consecutive_overall_failures[call_sid]} for {call_sid}")
        else:
            # Reset counter on success
            if consecutive_overall_failures[call_sid] > 0:
                if settings.CONFIDENCE_DEBUG_MODE:
                    logger.info(f"✅ Overall confidence recovered for {call_sid}, resetting counter")
                consecutive_overall_failures[call_sid] = 0
        
        # Check consecutive failure thresholds
        if consecutive_intent_failures[call_sid] >= settings.CONSECUTIVE_INTENT_FAILURES_THRESHOLD:
            handoff_reasons.append(f"{consecutive_intent_failures[call_sid]} consecutive intent failures >= {settings.CONSECUTIVE_INTENT_FAILURES_THRESHOLD}")
            consecutive_handoff = True
        
        if consecutive_overall_failures[call_sid] >= settings.CONSECUTIVE_OVERALL_FAILURES_THRESHOLD:
            handoff_reasons.append(f"{consecutive_overall_failures[call_sid]} consecutive overall failures >= {settings.CONSECUTIVE_OVERALL_FAILURES_THRESHOLD}")
            consecutive_handoff = True
    
    # Check for missing critical fields
    required_fields = ['job.type', 'job.urgency', 'location.raw_address']
    missing_fields = 0
    
    for field in required_fields:
        field_parts = field.split('.')
        value = args
        for part in field_parts:
            value = value.get(part, {}) if isinstance(value, dict) else None
            if value is None:
                break
        
        if not value:
            missing_fields += 1
    
    missing_fields_handoff = False
    if call_sid:
        if missing_fields >= settings.MISSING_FIELDS_PER_TURN_THRESHOLD:
            consecutive_missing_fields_failures[call_sid] += 1
            if settings.CONFIDENCE_DEBUG_MODE:
                logger.info(f"🔢 Missing fields failure #{consecutive_missing_fields_failures[call_sid]} for {call_sid} ({missing_fields} missing >= {settings.MISSING_FIELDS_PER_TURN_THRESHOLD})")
        else:
            if consecutive_missing_fields_failures[call_sid] > 0:
                if settings.CONFIDENCE_DEBUG_MODE:
                    logger.info(f"✅ Required fields present for {call_sid}, resetting missing fields counter")
                consecutive_missing_fields_failures[call_sid] = 0
        
        if consecutive_missing_fields_failures[call_sid] >= settings.CONSECUTIVE_MISSING_FIELDS_FAILURES_THRESHOLD:
            handoff_reasons.append(f"{consecutive_missing_fields_failures[call_sid]} consecutive turns with >= {settings.MISSING_FIELDS_PER_TURN_THRESHOLD} critical fields missing")
            missing_fields_handoff = True
    else:
        if missing_fields >= settings.MISSING_FIELDS_PER_TURN_THRESHOLD:
            handoff_reasons.append(f"{missing_fields} critical fields missing (no call tracking)")
            missing_fields_handoff = True
    
    # Determine final handoff decision
    should_handoff = single_instance_handoff or consecutive_handoff or missing_fields_handoff
    
    # Log handoff decision
    if should_handoff and settings.CONFIDENCE_DEBUG_MODE:
        reasons_str = ", ".join(handoff_reasons)
        logger.info(f"🚨 Handoff triggered for {call_sid or 'unknown'}: {reasons_str}")
    elif settings.CONFIDENCE_DEBUG_MODE and call_sid:
        logger.info(f"✅ Continuing automation for {call_sid}: confidence OK")
    
    return should_handoff

def create_fallback_response(text: str) -> dict:
    """Create a fallback response when function calling fails"""
    return {
        "intent": "BOOK_JOB",
        "customer": {"name": None, "phone": None, "email": None},
        "job": {"type": None, "urgency": None, "description": text},
        "location": {"raw_address": None, "validated": False, "address_id": None, "lat": None, "lng": None},
        "constraints": {},
        "proposed_slot": {},
        "fsm_backend": None,
        "confidence": {"overall": 0.0, "fields": {}},
        "handoff_needed": True
    }

# Simple negative/closing intent detection
NEGATIVE_PATTERNS = {
    "no", "no thanks", "no thank you", "that's all", "that is all", "nothing else", "nope",
    "nah", "we're good", "we are good", "all good", "goodbye", "bye", "hang up", "end call"
}

# Goodbye/closing statement patterns
GOODBYE_PATTERNS = {
    "thank you for listening", "thank you for watching", "see you next time", "goodbye", "bye",
    "that's all", "that is all", "we're done", "we are done", "have a good day", "take care",
    "thanks for your time", "appreciate it", "no thank you", "nothing else", "all set", "we're good"
}

def is_goodbye_statement(text: str) -> bool:
    """Detect if user is trying to end the call politely"""
    norm = " ".join(text.lower().split())
    
    # Check for exact matches
    if norm in GOODBYE_PATTERNS:
        return True
    
    # Check for partial matches
    goodbye_keywords = [
        "thank you for listening", "thank you for watching", "see you next time",
        "have a good day", "take care", "thanks for your time", "appreciate it",
        "we're done", "we are done", "all set", "we're good", "we are good"
    ]
    
    for pattern in goodbye_keywords:
        if pattern in norm:
            return True
    
    return False

def has_no_clear_service_intent(intent: dict) -> bool:
    """Check if the intent lacks clear plumbing service indicators"""
    confidence = intent.get('confidence', {})
    overall_confidence = confidence.get('overall', 0.0)
    
    # Very low confidence indicates unclear intent
    if overall_confidence < 0.5:
        return True
    
    # Missing critical information
    job_type = intent.get('job', {}).get('type')
    job_description = intent.get('job', {}).get('description', '')
    
    # No specific job type and very generic description
    if not job_type or job_type == 'None':
        return True
    
    return False

def is_negative_response(text: str) -> bool:
    norm = " ".join(text.lower().split())
    if norm in NEGATIVE_PATTERNS:
        return True
    # Prefix matches for common closers
    for p in ("no ", "no,", "no.", "nope", "nah"):
        if norm.startswith(p):
            return True
    return False

# Positive/affirmative detection
AFFIRMATIVE_PATTERNS = {
    "yes", "yeah", "yep", "affirmative", "correct", "that works", "sounds good", "please do",
    "book it", "go ahead", "confirm", "let's do it", "schedule it", "do it", "done", "sure",
    "okay", "ok", "right", "exactly", "absolutely", "definitely", "uh huh", "mm hmm", "mhm",
    "for sure", "of course", "you bet", "indeed", "certainly", "sounds right", "looks good",
    "that sounds right", "that's right", "that is right", "i agree", "agreed"
}

def is_affirmative_response(text: str) -> bool:
    norm = " ".join((text or "").lower().strip().strip(".,!?").split())
    if norm in AFFIRMATIVE_PATTERNS:
        return True
    # Check if "yes" appears anywhere in the text (for phrases like "I said yes")
    if "yes" in norm:
        return True
    # Token-based checks
    words = norm.split()
    # Short generic confirmations only (avoid long sentences like "yeah, my ...")
    if len(words) <= 3 and words[0] in {"yes", "yeah", "yep", "yup", "ok", "okay", "sure", "correct", "affirmative", "done", "right", "exactly", "absolutely", "definitely"}:
        return True
    # Vocal confirmations that might be transcribed differently
    vocal_confirms = ["uh huh", "mm hmm", "mhm", "for sure", "of course", "you bet"]
    if norm in vocal_confirms:
        return True
    # Explicit booking/confirmation phrases anywhere in the utterance
    explicit_patterns = [
        r"\bbook(\s+it|\s+that)?\b",
        r"\bconfirm\b",
        r"\bschedule(\s+it)?\b",
        r"\bgo ahead\b",
        r"\bthat works\b",
        r"\bsounds good\b",
        r"\blet'?s do it\b",
        r"\bdo it\b",
        r"\bplease book\b",
    ]
    for pat in explicit_patterns:
        if re.search(pat, norm):
            return True
    return False

# STRICT yes/no confirmation for appointment scheduling
STRICT_YES_PATTERNS = {
    "yes", "yeah", "yep", "yup", "affirmative", "correct", "that's right", "that is right",
    "sure", "okay", "ok", "right", "exactly", "absolutely", "definitely", 
    "uh huh", "mm hmm", "mhm", "for sure", "of course", "you bet", "indeed", "certainly"
}

STRICT_NO_PATTERNS = {
    "no", "nope", "nah", "not that time", "that doesn't work", "that does not work",
    "uh uh", "nuh uh", "mm mm", "not really", "negative", "that's not right", "that's wrong",
    "incorrect", "maybe not", "probably not", "i don't think so", "i don't agree"
}

def is_strict_affirmative_response(text: str) -> bool:
    """Flexible yes detection for appointment confirmation - accepts any response with affirmative intent"""
    norm = " ".join((text or "").lower().strip().strip(".,!?").split())
    
    # Check for any form of "yes" anywhere in the text
    if any(word in norm for word in ["yes", "yeah", "yep", "yup"]):
        return True
    
    # Check for positive confirmation words
    positive_words = ["sure", "okay", "ok", "correct", "right", "absolutely", "definitely", "perfect", "great", "good", "sounds good", "works", "fine"]
    if any(word in norm for word in positive_words):
        return True
    
    # Check for positive phrases
    positive_phrases = ["let's do it", "that works", "that sounds good", "i'll take it", "book it", "schedule it", "go ahead", "do it", "sounds great", "looks good", "works for me", "i'm good", "that's good"]
    if any(phrase in norm for phrase in positive_phrases):
        return True
    
    # Vocal confirmations
    if any(vocal in norm for vocal in ["uh huh", "mm hmm", "mhm", "for sure", "of course", "you bet"]):
        return True
    
    return False

def is_strict_negative_response(text: str) -> bool:
    """Flexible no detection for appointment confirmation - accepts any response with negative intent"""
    norm = " ".join((text or "").lower().strip().strip(".,!?").split())
    
    # Check for any form of "no" anywhere in the text
    if any(word in norm for word in ["no", "nope", "nah"]):
        return True
    