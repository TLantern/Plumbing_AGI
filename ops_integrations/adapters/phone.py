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
    from ..job_booking import book_emergency_job, book_scheduled_job
    from .google_calendar import CalendarAdapter
except Exception:
    import sys as _sys
    import os as _os
    _CURRENT_DIR = _os.path.dirname(__file__)
    _OPS_ROOT = _os.path.abspath(_os.path.join(_CURRENT_DIR, '..'))
    if _OPS_ROOT not in _sys.path:
        _sys.path.insert(0, _OPS_ROOT)
    from plumbing_services import (
        get_function_definition,
        infer_job_type_from_text,
        infer_multiple_job_types_from_text,
    )
    from job_booking import book_emergency_job, book_scheduled_job
    from google_calendar import CalendarAdapter
from datetime import datetime, timedelta
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
TRANSCRIPTION_MODEL = "whisper-1"

# VAD Configuration
VAD_AGGRESSIVENESS = 3  # 0-3, higher = more aggressive filtering
VAD_FRAME_DURATION_MS = 20  # 20ms frames for VAD
SILENCE_TIMEOUT_SEC = 1.5  # How long to wait after speech ends before processing
MIN_SPEECH_DURATION_SEC = 0.5  # Minimum speech duration to consider valid
CHUNK_DURATION_SEC = 3  # Fallback max segment duration before forcing processing
PREROLL_IGNORE_SEC = 0.7  # Ignore low-energy speech detections for first N seconds after start
MIN_START_RMS = 120  # Require at least this RMS on first frame to start a speech segment

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
    intent = await classify_transcript_intent(text)
    
    payload = {
        "type": "transcript",
        "data": {
            "callSid": call_sid,
            "text": text,
            "intent": intent,
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


async def classify_transcript_intent(text: str) -> str:
    """Classify the intent of a transcript text using GPT-3.5-turbo."""
    try:
        # Skip classification for very short texts
        if len(text.strip()) < 5:
            return "GENERAL_INQUIRY"
            
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": INTENT_CLASSIFICATION_PROMPT},
                {"role": "user", "content": text}
            ],
            max_tokens=20,
            temperature=0.1  # Low temperature for deterministic results
        )
        
        intent = response.choices[0].message.content.strip().upper()
        
        # Validate that the intent is one we recognize
        from ops_integrations.flows.intents import get_intent_tags
        valid_intents = get_intent_tags()
        if intent in valid_intents:
            return intent
        else:
            logger.debug(f"Unknown intent returned: {intent}, falling back to GENERAL_INQUIRY")
            return "GENERAL_INQUIRY"
            
    except Exception as e:
        logger.debug(f"Error classifying transcript intent: {e}")
        return "GENERAL_INQUIRY"


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

async def _send_magiclink_sms(call_sid: str) -> bool:
    """Mock SMS sending - return success without actually sending for A2P approval wait"""
    try:
        # Mock the token response
        token_resp = {
            "token": f"mock_token_{call_sid}",
            "jti": f"mock_jti_{call_sid}",
            "exp": int(time.time()) + 3600
        }
        token = token_resp.get("token")
        
        call_info = call_info_store.get(call_sid, {})
        to_number = call_info.get("from")
        from_number = settings.TWILIO_SMS_FROM or call_info.get("to")
        
        # Mock successful SMS send
        logger.info(f"🔗 MOCK: Magiclink SMS would be sent to {to_number} from {from_number} (A2P approval pending)")
        
        magiclink_state[call_sid] = {
            "token": token,
            "jti": token_resp.get("jti"),
            "exp": token_resp.get("exp"),
            "sent": True,
            "user_confirmed": False,
            "operator_confirmed": False,
            "mocked": True  # Flag to indicate this was mocked
        }
        return True
    except Exception as e:
        logger.error(f"Failed to mock magiclink SMS for {call_sid}: {e}")
        return False

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
        customer = intent.get("customer", {})
        job = intent.get("job", {})
        location = intent.get("location", {})

        phone = customer.get("phone") or call_info_store.get(call_sid, {}).get("from") or ""
        name = customer.get("name") or "Customer"
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

# Send booking confirmation to operator frontend
async def _send_booking_to_operator(call_sid: str, intent: dict, suggested_time: datetime) -> None:
    """Send booking confirmation to operator frontend via WebSocket"""
    try:
        call_info = call_info_store.get(call_sid, {})
        customer = intent.get('customer', {})
        job = intent.get('job', {})
        location = intent.get('location', {})
        
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
def _build_wss_url_from_request(request: Request, call_sid: str) -> tuple[str, str]:
    try:
        hdrs = request.headers
        host = hdrs.get('x-forwarded-host') or hdrs.get('host')
        proto = (hdrs.get('x-forwarded-proto') or request.url.scheme or 'https').lower()
        ws_scheme = 'wss' if proto == 'https' else 'ws'
        if host:
            ws_base = f"{ws_scheme}://{host}"
            wss_url = f"{ws_base}{settings.STREAM_ENDPOINT}?callSid={call_sid}"
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
    return ws_base, f"{ws_base}{settings.STREAM_ENDPOINT}?callSid={call_sid}"

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
    ws_base, wss_url = _build_wss_url_from_request(request, call_sid)
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
    # Greet first, then start streaming so listening begins after the message
    greet_text = "Thank you for calling SafeHarbour Plumbing Services. If at any point you'd like to speak to a human dispatcher, just say 'transfer'. What can we assist you with today?"
    logger.info(f"🗣️ TTS SAY (greeting) for CallSid={call_sid}: {greet_text}")
    # Use TTS helper so greeting benefits from ElevenLabs if configured
    await add_tts_or_say_to_twiml(resp, call_sid, greet_text)
    start = Start()
    start.stream(url=wss_url, track="inbound_track")
    resp.append(start)
    resp.pause(length=3600)
    logger.info(f"🎯 Stream will start after greeting for call {call_sid}")
    logger.info(f"🔗 WebSocket URL generated: {wss_url}")
    logger.debug(f"📄 TwiML Response: {str(resp)}")

    # Watchdog: if no media arrives shortly, re-push TwiML to ensure streaming
    try:
        asyncio.create_task(streaming_watchdog(call_sid))
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
    temporary_stream_key: Optional[str] = None
    try:
        # Try to extract CallSid from query params (Twilio may pass it)
        call_sid = ws.query_params.get("callSid")
        logger.info(f"WebSocket connection accepted for potential CallSid={call_sid}")
        logger.info(f"All query params: {dict(ws.query_params)}")
        logger.info(f"WebSocket URL: {ws.url}")

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
                    
                    # Check if silence timeout exceeded
                    silence_duration = current_time - vad_state['last_speech_time']
                    if silence_duration >= SILENCE_TIMEOUT_SEC:
                        # End of speech detected
                        speech_duration = current_time - vad_state['speech_start_time']
                        pending_duration_ms = len(vad_state['pending_audio']) / (sample_rate * SAMPLE_WIDTH) * 1000
                        
                        logger.info(f"🔇 SPEECH ENDED for {call_sid}: {speech_duration:.2f}s total, {pending_duration_ms:.0f}ms buffered, {silence_duration:.2f}s silence")
                        
                        if speech_duration >= MIN_SPEECH_DURATION_SEC:
                            # Valid speech segment, process it
                            logger.info(f"✅ Processing valid speech segment for {call_sid}")
                            await process_speech_segment(call_sid, vad_state['pending_audio'])
                            # Clear fallback buffer too to avoid double-processing the same audio
                            vad_state['fallback_buffer'] = bytearray()
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
        if speech_duration >= CHUNK_DURATION_SEC:
            logger.debug(f"Forcing processing due to max duration for {call_sid}")
            await process_speech_segment(call_sid, vad_state['pending_audio'])
            # Clear fallback buffer too, since it contains the same recent audio
            vad_state['fallback_buffer'] = bytearray()
            vad_state['is_speaking'] = False
            vad_state['pending_audio'] = bytearray()

    # NEW: Time-based fallback flush every CHUNK_DURATION_SEC even if VAD never triggered
    try:
        fallback_bytes = len(vad_state['fallback_buffer'])
        if not vad_state['is_speaking'] and fallback_bytes >= int(sample_rate * SAMPLE_WIDTH * CHUNK_DURATION_SEC):
            logger.info(f"⏱️ Time-based fallback flush for {call_sid}: {fallback_bytes} bytes (~{CHUNK_DURATION_SEC}s)")
            await process_speech_segment(call_sid, vad_state['fallback_buffer'])
            vad_state['fallback_buffer'] = bytearray()
            vad_state['last_chunk_time'] = current_time
    except Exception as e:
        logger.debug(f"Time-based fallback flush error for {call_sid}: {e}")

async def process_speech_segment(call_sid: str, audio_data: bytearray):
    """Process a detected speech segment"""
    sample_rate = audio_config_store.get(call_sid, {}).get('sample_rate', SAMPLE_RATE_DEFAULT)
    audio_duration_ms = len(audio_data) / (sample_rate * SAMPLE_WIDTH) * 1000
    logger.info(f"Processing speech segment for {call_sid}: {len(audio_data)} bytes, {audio_duration_ms:.0f}ms duration")
    
    if len(audio_data) < sample_rate * SAMPLE_WIDTH * 0.3:  # Less than 300ms
        logger.warning(f"Speech segment too short for {call_sid} ({audio_duration_ms:.0f}ms < 300ms), skipping Whisper processing")
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
        if rms < 80:  # lowered threshold to allow quieter segments
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
        
        logger.info(f"Sending audio to Whisper for {call_sid} (model: {TRANSCRIPTION_MODEL})")
        start_time = time.time()
        
        wav_file = io.BytesIO(wav_for_whisper)
        try:
            wav_file.name = "speech.wav"  # Help the API infer format
        except Exception:
            pass
        
        resp = client.audio.transcriptions.create(
            model=TRANSCRIPTION_MODEL,
            file=wav_file,
            response_format="verbose_json",
            language="en",
            prompt="Caller is describing a plumbing issue or asking a question. Ignore background noise, dial tones, and hangup signals."
        )
        
        transcription_duration = time.time() - start_time
        logger.info(f"Whisper transcription completed for {call_sid} in {transcription_duration:.2f}s")
        
        text = (resp.text or "").strip()
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
        elif mean_lp is not None and mean_lp < -1.0:
            should_suppress = True
        
        # Always accept brief confirmations even if low-confidence
        confirm_phrases = {
            "done", "finished", "completed", "yes", "okay", "ok", "no", "nope", "nah", "no thanks", "no thank you",
            "yeah", "yep", "yup", "sure", "right", "correct", "exactly", "absolutely", "definitely",
            "uh huh", "mm hmm", "mhm", "for sure", "of course", "you bet", "indeed", "certainly",
            "uh uh", "nuh uh", "mm mm", "not really", "negative", "that's not right", "that's wrong",
            "incorrect", "maybe not", "probably not"
        }
        if any(p in normalized for p in confirm_phrases):
            should_suppress = False
            logger.info(f"🎯 Accepting confirmation phrase '{text}' despite low confidence for {call_sid}")
        
        if should_suppress:
            logger.info(f"Suppressed low-confidence/short transcription for {call_sid}: '{text}' (avg_logprob={mean_lp})")
            return
        
        logger.info(f'🎤 USER SPEECH ({call_sid}): "{text}" [duration: {audio_duration_ms:.0f}ms, transcription_time: {transcription_duration:.2f}s, avg_logprob: {mean_lp}]')
        # Suppress duplicate transcripts within a short window to avoid repeated prompts
        try:
            normalized_text = " ".join(text.lower().split())
            info = call_info_store.get(call_sid, {})
            prev_text = info.get('asr_last_text')
            prev_ts = info.get('asr_last_ts', 0)
            now_ts = time.time()
            if prev_text == normalized_text and (now_ts - prev_ts) < 10:
                logger.info(f"Suppressing duplicate transcript for {call_sid}: '{text}'")
                return
            info['asr_last_text'] = normalized_text
            info['asr_last_ts'] = now_ts
            call_info_store[call_sid] = info
        except Exception as e:
            logger.debug(f"Duplicate transcript guard failed for {call_sid}: {e}")

        # Broadcast real-time transcript to ops dashboard
        try:
            asyncio.create_task(_broadcast_transcript(call_sid, text))
        except Exception:
            pass

        # Post-booking Q&A flow
        dialog = call_dialog_state.get(call_sid)
        if dialog and dialog.get('step') == 'post_booking_qa':
            if is_negative_response(text):
                twiml = VoiceResponse()
                await add_tts_or_say_to_twiml(twiml, call_sid, "Thanks for trusting SafeHarbour to help you with your plumbing needs. Goodbye.")
                twiml.hangup()
                call_dialog_state.pop(call_sid, None)
                await push_twiml_to_call(call_sid, twiml)
                return
            # Answer with GPT-4o and re-prompt
            answer = await answer_customer_question(call_sid, text)
            reply = f"{answer} Please let me know if you have any other questions."
            twiml = VoiceResponse()
            await add_tts_or_say_to_twiml(twiml, call_sid, reply)
            # Keep in QA mode and resume stream
            def append_stream_and_pause_local(resp: VoiceResponse):
                start = Start()
                ws_base = call_info_store.get(call_sid, {}).get('ws_base')
                if ws_base:
                    wss_url_local = f"{ws_base}{settings.STREAM_ENDPOINT}?callSid={call_sid}"
                else:
                    if settings.EXTERNAL_WEBHOOK_URL.startswith('https://'):
                        wss_url_local = settings.EXTERNAL_WEBHOOK_URL.replace('https://', 'wss://') + settings.STREAM_ENDPOINT + f"?callSid={call_sid}"
                    elif settings.EXTERNAL_WEBHOOK_URL.startswith('http://'):
                        wss_url_local = settings.EXTERNAL_WEBHOOK_URL.replace('http://', 'ws://') + settings.STREAM_ENDPOINT + f"?callSid={call_sid}"
                    else:
                        wss_url_local = f"wss://{settings.EXTERNAL_WEBHOOK_URL}{settings.STREAM_ENDPOINT}?callSid={call_sid}"
                start.stream(url=wss_url_local, track="inbound_track")
                resp.append(start)
                resp.pause(length=3600)
            append_stream_and_pause_local(twiml)
            await push_twiml_to_call(call_sid, twiml)
            return

        # Scheduling/path and confirmation follow-up handling
        if dialog and dialog.get('step') in (
            'awaiting_path_choice',
            'awaiting_time',
            'awaiting_time_confirm',
            'awaiting_location_confirm',
            'awaiting_operator_confirm',
        ):
            logger.info(f"Handling follow-up scheduling/path utterance for {call_sid}: '{text}'")
            twiml = await handle_intent(call_sid, dialog.get('intent', {}), followup_text=text)
            await push_twiml_to_call(call_sid, twiml)
            return

        # Otherwise, extract a fresh intent
        intent = await extract_intent_from_text(call_sid, text)
        # Defer prompting/booking until caller provides explicit signals (date/time or emergency) or after at least 2 segments
        info = call_info_store.get(call_sid, {})
        segments_count = int(info.get('segments_count', 0)) + 1
        info['segments_count'] = segments_count
        call_info_store[call_sid] = info
        explicit_time = parse_human_datetime(text) or gpt_infer_datetime_phrase(text)
        explicit_emergency = contains_emergency_keywords(text)
        if segments_count < 2 and not explicit_time and not explicit_emergency and not is_affirmative_response(text):
            call_dialog_state[call_sid] = {'intent': intent, 'step': 'awaiting_path_choice'}
            logger.info(f"Deferring prompt; continuing to listen for {call_sid} (segments={segments_count})")
            return
        twiml = await handle_intent(call_sid, intent)
        await push_twiml_to_call(call_sid, twiml)
            
    except Exception as e:
        logger.error(f"Speech processing error for {call_sid}: {e}")
        logger.debug(f"Failed audio details for {call_sid}: {len(audio_data)} bytes, {audio_duration_ms:.0f}ms")

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
    validated_args = validate_and_enhance_extraction(args, text)
    return validated_args

   # Fallback: no function call, return freeform description
   return create_fallback_response(text)

def validate_and_enhance_extraction(args: dict, original_text: str) -> dict:
    """Validate and enhance extracted data with additional processing"""
    
    # Ensure required fields exist
    if 'intent' not in args:
        args['intent'] = 'BOOK_JOB'
    
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
    
    # Enhance address extraction
    if not args.get('location', {}).get('raw_address'):
        address = extract_address(original_text)
        if address:
            args['location'] = args.get('location', {})
            args['location']['raw_address'] = address
    
    # Calculate confidence scores
    confidence = calculate_confidence_scores(args, original_text)
    args['confidence'] = confidence
    
    # Determine handoff based on confidence and completeness
    args['handoff_needed'] = should_handoff_to_human(args, confidence)
    
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

# TTS: synthesize with OpenAI 4o TTS
async def synthesize_tts(text: str) -> Optional[bytes]:
    try:
        voice = getattr(settings, 'OPENAI_TTS_VOICE', 'alloy')  # Default to 'alloy' voice
        model = getattr(settings, 'OPENAI_TTS_MODEL', 'tts-1')  # Default to 'tts-1' model
        
        response = client.audio.speech.create(
            model=model,
            voice=voice,
            input=text,
            response_format="mp3"
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

async def add_tts_or_say_to_twiml(target, call_sid: str, text: str):
    speak_text = text.replace("_", " ")
    preview = speak_text if len(speak_text) <= 200 else speak_text[:200] + "..."
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

def calculate_confidence_scores(args: dict, original_text: str) -> dict:
    """Calculate confidence scores for extracted data"""
    confidence = {
        "overall": 0.0,
        "fields": {}
    }
    
    # Job type confidence
    job_type = args.get('job', {}).get('type')
    if job_type:
        confidence["fields"]["type"] = 0.9 if job_type in ['leak', 'water_heater', 'clog', 'gas_line', 'sewer_cam'] else 0.7
    else:
        confidence["fields"]["type"] = 0.0
    
    # Urgency confidence
    urgency = args.get('job', {}).get('urgency')
    if urgency:
        confidence["fields"]["urgency"] = 0.8 if urgency in ['emergency', 'same_day', 'flex'] else 0.5
    else:
        confidence["fields"]["urgency"] = 0.0
    
    # Address confidence
    address = args.get('location', {}).get('raw_address')
    if address:
        confidence["fields"]["address"] = 0.8
    else:
        confidence["fields"]["address"] = 0.0
    
    # Customer name confidence
    customer_name = args.get('customer', {}).get('name')
    if customer_name:
        confidence["fields"]["customer"] = 0.9
    else:
        confidence["fields"]["customer"] = 0.0
    
    # Overall confidence
    field_scores = list(confidence["fields"].values())
    if field_scores:
        confidence["overall"] = sum(field_scores) / len(field_scores)
    
    return confidence

def should_handoff_to_human(args: dict, confidence: dict) -> bool:
    """Determine if human handoff is needed"""
    overall_confidence = confidence.get("overall", 0.0)
    
    # Handoff if overall confidence is low
    if overall_confidence < 0.7:
        return True
    
    # Handoff if critical fields are missing
    required_fields = ['job.type', 'job.urgency', 'location.raw_address']
    missing_fields = 0
    
    for field in required_fields:
        keys = field.split('.')
        value = args
        for key in keys:
            value = value.get(key, {})
        if not value:
            missing_fields += 1
    
    if missing_fields >= 2:
        return True
    
    return False

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
    if overall_confidence < 0.3:
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
    """Strict yes detection for appointment confirmation - only accepts clear affirmatives"""
    norm = " ".join((text or "").lower().strip().strip(".,!?").split())
    # Must be exact match or start with yes/yeah/yep
    if norm in STRICT_YES_PATTERNS:
        return True
    words = norm.split()
    if len(words) <= 2 and words[0] in {"yes", "yeah", "yep", "yup", "correct", "affirmative", "sure", "okay", "ok", "right", "exactly", "absolutely", "definitely"}:
        return True
    # Accept repeated affirmative tokens only (e.g., "yes yes yes", "yeah yep")
    allowed_yes_tokens = {"yes", "yeah", "yep", "yup", "ok", "okay", "correct", "affirmative", "sure", "right", "exactly", "absolutely", "definitely"}
    if words and all(w in allowed_yes_tokens for w in words):
        return True
    # Vocal confirmations
    vocal_confirms = ["uh huh", "mm hmm", "mhm", "for sure", "of course", "you bet"]
    if norm in vocal_confirms:
        return True
    return False

def is_strict_negative_response(text: str) -> bool:
    """Strict no detection for appointment confirmation - only accepts clear negatives"""
    norm = " ".join((text or "").lower().strip().strip(".,!?").split())
    if norm in STRICT_NO_PATTERNS:
        return True
    words = norm.split()
    if len(words) <= 2 and words[0] in {"no", "nope", "nah", "negative"}:
        return True
    # Accept repeated negative tokens and common polite closers (e.g., "no no nah no thanks")
    filler_tokens = {"thanks", "thank", "you"}
    filtered = [w for w in words if w not in filler_tokens]
    allowed_no_tokens = {"no", "nope", "nah", "negative"}
    if filtered and all(w in allowed_no_tokens for w in filtered):
        return True
    # Vocal negations
    vocal_negatives = ["uh uh", "nuh uh", "mm mm", "not really", "maybe not", "probably not"]
    if norm in vocal_negatives:
        return True
    # Common negative phrases
    negative_phrases = ["i don't think so", "i don't agree", "that's not right", "that's wrong"]
    if norm in negative_phrases:
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
        ws_base = call_info_store.get(call_sid, {}).get('ws_base')
        if ws_base:
            wss_url_local = f"{ws_base}{settings.STREAM_ENDPOINT}?callSid={call_sid}"
        else:
            if settings.EXTERNAL_WEBHOOK_URL.startswith('https://'):
                wss_url_local = settings.EXTERNAL_WEBHOOK_URL.replace('https://', 'wss://') + settings.STREAM_ENDPOINT + f"?callSid={call_sid}"
            elif settings.EXTERNAL_WEBHOOK_URL.startswith('http://'):
                wss_url_local = settings.EXTERNAL_WEBHOOK_URL.replace('http://', 'ws://') + settings.STREAM_ENDPOINT + f"?callSid={call_sid}"
            else:
                wss_url_local = f"wss://{settings.EXTERNAL_WEBHOOK_URL}{settings.STREAM_ENDPOINT}?callSid={call_sid}"
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
        return twiml
    
    # Handle very low confidence or no clear service intent
    if not followup_text and has_no_clear_service_intent(intent):
        await add_tts_or_say_to_twiml(
            twiml, 
            call_sid, 
            "I want to make sure I understand you correctly. What specific plumbing issue can we help you with today? For example, do you have a leak, clog, or need a repair?"
        )
        # Set state to await clearer intent
        call_dialog_state[call_sid] = {'intent': intent, 'step': 'awaiting_clear_intent'}
        append_stream_and_pause(twiml)
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
            append_stream_and_pause(twiml)
            return twiml
        
        # Handle awaiting_clear_intent step - user responding to clarification request
        if state.get('step') == 'awaiting_clear_intent':
            # Check if this is still a goodbye statement
            if is_goodbye_statement(followup_text):
                await add_tts_or_say_to_twiml(twiml, call_sid, "Thank you for calling SafeHarbour Plumbing Services. Have a great day!")
                return twiml
            
            # Try to extract intent from the clarified response
            try:
                from ops_integrations.flows.intents import extract_plumbing_intent
                new_intent = await extract_plumbing_intent(followup_text)
                
                # Check if we now have a clearer intent
                if new_intent and has_no_clear_service_intent(new_intent):
                    # Still unclear - politely end the call
                    await add_tts_or_say_to_twiml(
                        twiml, 
                        call_sid, 
                        "I'm having trouble understanding the specific plumbing issue you need help with. Please feel free to call back when you have a specific plumbing problem, or you can speak directly to one of our dispatchers. Thank you for calling!"
                    )
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
                    await add_tts_or_say_to_twiml(twiml, call_sid, "Thanks, we received your location. Please say a date and time, like 'Friday at 3 PM'.")
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
                # User said YES - proceed to operator
                suggested_time = state.get('suggested_time')
                if isinstance(suggested_time, datetime):
                    try:
                        await _send_booking_to_operator(call_sid, intent, suggested_time)
                    except Exception as e:
                        logger.debug(f"Failed to broadcast booking to operator: {e}")
                    await add_tts_or_say_to_twiml(twiml, call_sid, "Perfect! I've sent your appointment request to our dispatcher for confirmation. They'll be with you shortly.")
                    state['step'] = 'awaiting_operator_confirm'
                    call_dialog_state[call_sid] = state
                    append_stream_and_pause(twiml)
                    return twiml
            elif is_strict_negative_response(followup_text):
                # User said NO - go back to scheduling
                await add_tts_or_say_to_twiml(twiml, call_sid, "No problem. Tell me what date and time would work better for you, or say 'earliest' for the next available slot.")
                call_dialog_state[call_sid] = {'intent': intent, 'step': 'awaiting_time'}
                append_stream_and_pause(twiml)
                return twiml
            else:
                # Ambiguous response - ask again with strict instructions
                suggested_time = state.get('suggested_time')
                if isinstance(suggested_time, datetime):
                    await add_tts_or_say_to_twiml(twiml, call_sid, f"I need a clear answer. Do you want the appointment at {_format_slot(suggested_time)}? Please say exactly YES if you want it, or NO if you don't.")
                    # Keep the same state - they stay in confirmation mode
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
                    calendar_adapter = CalendarAdapter()
                    now = datetime.now()
                    suggested = now + timedelta(hours=1)
                    if getattr(calendar_adapter, 'enabled', False):
                        # Find nearest 2h slot with no events
                        for i in range(0, 24):
                            slot_start = now + timedelta(hours=i)
                            slot_end = slot_start + timedelta(hours=2)
                            events = calendar_adapter.get_events(start_date=slot_start, end_date=slot_end)
                            if not events:
                                suggested = slot_start
                                break
                    # Send location link immediately and hold this time
                    # try:
                    #     ok = await _send_magiclink_sms(call_sid)
                    # except Exception:
                    #     ok = False
                    ok = True  # Skip SMS for now, just wait for "done"
                    if ok:
                        await add_tts_or_say_to_twiml(
                            twiml,
                            call_sid,
                            f"Understood. The closest available slot is {_format_slot(suggested)}. Do you want this time? Please say YES or NO."
                        )
                        call_dialog_state[call_sid] = {'intent': intent, 'step': 'awaiting_time_confirm', 'suggested_time': suggested}
                    else:
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
                return twiml
            elif any(k in text_norm for k in ['schedule', 'book', 'technician', 'come check', 'come out', 'appointment']):
                await add_tts_or_say_to_twiml(twiml, call_sid, f"Great. If you have a date and time in mind, tell me now, otherwise I can suggest the earliest available.")
                call_dialog_state[call_sid] = {'intent': intent, 'step': 'awaiting_time'}
                append_stream_and_pause(twiml)
                logger.info(f"Handled path choice (schedule) for CallSid={call_sid}")
                return twiml
        # If user gives a date/time directly, recognize but don't book yet
        try:
            preferred_time = parse_human_datetime(followup_text)
            if not preferred_time:
                preferred_time = gpt_infer_datetime_phrase(followup_text)
            if preferred_time:
                try:
                    start_time = preferred_time
                    calendar_adapter = CalendarAdapter()
                    events = []
                    if getattr(calendar_adapter, 'enabled', False):
                        end_time = preferred_time + timedelta(hours=2)
                        events = calendar_adapter.get_events(start_date=start_time, end_date=end_time)
                    if not events:
                        # Hold time and send location link immediately
                        # try:
                        #     ok = await _send_magiclink_sms(call_sid)
                        # except Exception:
                        #     ok = False
                        ok = True  # Skip SMS for now, just wait for "done"
                        if ok:
                            await add_tts_or_say_to_twiml(
                                twiml,
                                call_sid,
                                f"Thanks. I can schedule you for {_format_slot(start_time)} for your {_speakable(job_type)}. Do you want this time? Please say YES or NO."
                            )
                            call_dialog_state[call_sid] = {'intent': intent, 'step': 'awaiting_time_confirm', 'suggested_time': start_time}
                        else:
                            await add_tts_or_say_to_twiml(
                                twiml,
                                call_sid,
                                f"Thanks. I can schedule you for {_format_slot(start_time)} for your {_speakable(job_type)}. Do you want this time? Please say YES or NO."
                            )
                            call_dialog_state[call_sid] = {'intent': intent, 'step': 'awaiting_time_confirm', 'suggested_time': start_time}
                    else:
                        # Suggest next available, send location link
                        next_available = start_time + timedelta(hours=2)
                        if getattr(calendar_adapter, 'enabled', False):
                            for i in range(1, 8):
                                slot_start = start_time + timedelta(hours=2*i)
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
                            await add_tts_or_say_to_twiml(
                                twiml,
                                call_sid,
                                f"That time looks busy. The next available is {_format_slot(next_available)}. Do you want this time? Please say YES or NO."
                            )
                            call_dialog_state[call_sid] = {'intent': intent, 'step': 'awaiting_time_confirm', 'suggested_time': next_available}
                        else:
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
                return twiml
        except Exception as e:
            logger.error(f"Datetime parsing failed: {e}")
        # Prompt again if nothing parsed
        await add_tts_or_say_to_twiml(twiml, call_sid, "Please say a date and time, like 'Friday at 3 PM', or say 'earliest'.")
        call_dialog_state[call_sid] = {'intent': intent, 'step': 'awaiting_time'}
        append_stream_and_pause(twiml)
        logger.info(f"Handled followup prompting for CallSid={call_sid}")
        return twiml

    # Initial intent handling (no <Gather>; we keep streaming and listen continuously)
    if urgency == 'emergency':
        try:
            calendar_adapter = CalendarAdapter()
            now = datetime.now()
            suggested = now + timedelta(hours=1)
            if getattr(calendar_adapter, 'enabled', False):
                for i in range(0, 24):
                    slot_start = now + timedelta(hours=i)
                    slot_end = slot_start + timedelta(hours=2)
                    events = calendar_adapter.get_events(start_date=slot_start, end_date=slot_end)
                    if not events:
                        suggested = slot_start
                        break
            # Send magiclink immediately and hold this time
            # try:
            #     ok = await _send_magiclink_sms(call_sid)
            # except Exception:
            #     ok = False
            ok = True  # Skip SMS for now, just wait for "done"
            if ok:
                await add_tts_or_say_to_twiml(twiml, call_sid, f"This sounds urgent. The closest available technician for {_speakable(job_type)} is {_format_slot(suggested)}. Do you want this time? Please say YES or NO.")
                call_dialog_state[call_sid] = {'intent': intent, 'step': 'awaiting_time_confirm', 'suggested_time': suggested}
            else:
                await add_tts_or_say_to_twiml(twiml, call_sid, f"This sounds urgent. The closest available technician for {_speakable(job_type)} is {_format_slot(suggested)}. Do you want this time? Please say YES or NO.")
                call_dialog_state[call_sid] = {'intent': intent, 'step': 'awaiting_time_confirm', 'suggested_time': suggested}
        except Exception as e:
            logger.error(f"Emergency slot suggestion failed: {e}")
            await add_tts_or_say_to_twiml(twiml, call_sid, "I'm checking the earliest availability. One moment, please.")
            call_dialog_state[call_sid] = {'intent': intent, 'step': 'awaiting_time_confirm'}
    else:
        # Ask for path: emergency vs schedule
        await add_tts_or_say_to_twiml(
            twiml,
            call_sid,
            f"Got it. For your {_speakable(job_type)}, is this an emergency, or would you like to book a technician to come check it out?"
        )
        call_dialog_state[call_sid] = {'intent': intent, 'step': 'awaiting_path_choice'}
    append_stream_and_pause(twiml)
    logger.info(f"Handled intent {intent} for CallSid={call_sid}")
    return twiml

# Watchdog to ensure streaming begins; re-push TwiML if no media seen soon
async def streaming_watchdog(call_sid: str, delay_seconds: float = 5.0):
    try:
        await asyncio.sleep(delay_seconds)
        info = call_info_store.get(call_sid, {})
        last_media_time = info.get('last_media_time')
        start_ts = info.get('start_ts', 0)
        has_conn = call_sid in manager.active_connections
        if has_conn and (not last_media_time or last_media_time < start_ts):
            logger.info(f"🛡️ Watchdog: no media received for {call_sid} after {delay_seconds:.0f}s; re-pushing TwiML to restart streaming")
            resp = VoiceResponse()
            start = Start()
            ws_base = info.get('ws_base')
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
            resp.append(start)
            resp.pause(length=3600)
            await push_twiml_to_call(call_sid, resp)
        else:
            logger.debug(f"Watchdog: media already flowing for {call_sid}; no action needed")
    except Exception as e:
        logger.error(f"Watchdog error for {call_sid}: {e}")

# Finalize metrics aggregation for a call

def _finalize_call_metrics(call_sid: str) -> None:
    try:
        info = call_info_store.get(call_sid)
        if not info:
            return
        if info.get('_finalized'):
            return
        end_ts = time.time()
        start_ts = float(info.get('start_ts') or end_ts)
        duration = max(0.0, end_ts - start_ts)
        # Abandoned if no media was received
        answered = bool(info.get('first_media_ts')) or bool(vad_states.get(call_sid, {}).get('has_received_media'))
        if not answered:
            try:
                ops_metrics_state["abandoned_calls"] = int(ops_metrics_state.get("abandoned_calls", 0)) + 1
            except Exception:
                ops_metrics_state["abandoned_calls"] = 1
        try:
            ops_metrics_state["handle_times_sec"].append(duration)
        except Exception:
            pass
        # Record into recent history
        try:
            rec = {
                "call_sid": call_sid,
                "from": info.get("from"),
                "to": info.get("to"),
                "start_ts": start_ts,
                "end_ts": end_ts,
                "duration_sec": duration,
                "answered": answered,
                "answer_time_sec": max(0.0, float(info.get('first_media_ts') - start_ts)) if info.get('first_media_ts') else None,
            }
            ops_metrics_state["call_history"].append(rec)
        except Exception:
            pass
        info['_finalized'] = True
        call_info_store[call_sid] = info
    except Exception as e:
        logger.debug(f"Finalize metrics failed for {call_sid}: {e}")

#---------------AUDIO PROCESSING---------------
def pcm_to_wav_bytes(pcm: bytes, sample_rate: int) -> bytes:
    """Wrap raw PCM into a WAV container for Whisper."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(SAMPLE_WIDTH)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm)
    return buf.getvalue()

def contains_emergency_keywords(text: str) -> bool:
    norm = " ".join((text or "").lower().split())
    keywords = [
        "emergency",
        "burst pipe",
        "pipe burst",
        "water everywhere",
        "flooding",
        "sewage",
        "sewer backup",
        "gas leak",
    ]
    for k in keywords:
        if k in norm:
            return True
    return False

#---------------MAIN---------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "phone:app",
        host=settings.SERVER_HOST,
        port=settings.SERVER_PORT,
        ssl_keyfile=settings.SSL_KEY_PATH,
        ssl_certfile=settings.SSL_CERT_FILE,
        log_level=settings.LOG_LEVEL.lower()
    )

# Heuristic: detect noise/unknown utterances with no recognizable intent cues
def is_noise_or_unknown(text: str) -> bool:
    norm = " ".join((text or "").lower().strip().strip(".,!?").split())
    if not norm:
        return True
    # If affirmative/negative or contains path/time cues, it's not noise
    if is_affirmative_response(norm) or is_negative_response(norm):
        return False
    # Common scheduling and intent cue words
    cue_words = {
        'emergency','urgent','immediately','schedule','book','appointment','technician','today','tomorrow','tonight',
        'morning','afternoon','evening','am','pm','earliest','soon','asap','next','this','monday','tuesday','wednesday','thursday','friday','saturday','sunday'
    }
    tokens = set(norm.split())
    if tokens & cue_words:
        return False
    # Accept explicit time-like expressions (e.g., 3 pm, 10:30 am)
    if re.search(r"\b\d{1,2}(:\d{2})?\s*(am|pm)\b", norm):
        return False
    # Treat URLs/domains and review chatter as noise
    if re.search(r"(https?://|www\.|\.[a-z]{2,6}\b)", norm) or 'pissedconsumer' in norm or 'review' in norm:
        return True
    # Single very short/uncommon word → treat as noise
    return len(tokens) <= 2

# Transfer intent detection
def is_transfer_request(text: str) -> bool:
    norm = " ".join((text or "").lower().strip().split())
    # Keywords that indicate a transfer request
    transfer_keywords = [
        "transfer", "transfer me", "dispatcher", "operator", "human", "representative", "agent"
    ]
    return any(k in norm for k in transfer_keywords)

async def perform_dispatch_transfer(call_sid: str) -> None:
    try:
        number = getattr(settings, "DISPATCH_NUMBER", "+14693096560")
        twiml = VoiceResponse()
        # Minimal prompt then transfer
        try:
            twiml.say("Connecting you to our dispatcher now.")
        except Exception:
            pass
        twiml.dial(number)
        # Mark state to avoid further processing
        st = call_info_store.setdefault(call_sid, {})
        st["handoff_requested"] = True
        st["handoff_reason"] = "user_requested_transfer"
        call_info_store[call_sid] = st
        await push_twiml_to_call(call_sid, twiml)
        logger.info(f"📞 Initiated transfer for {call_sid} to dispatcher {number}")
    except Exception as e:
        logger.error(f"Failed to perform dispatch transfer for {call_sid}: {e}")