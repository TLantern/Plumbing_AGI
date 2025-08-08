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
from pydantic_settings import BaseSettings
from twilio import twiml
from twilio.rest import Client
from twilio.twiml.voice_response import VoiceResponse, Start
import io
import wave
from openai import OpenAI
from collections import defaultdict
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

# Try to import audioop for mu-law decoding and resampling; may be missing on some Python versions
try:
    import audioop as _audioop  # type: ignore
except Exception:
    _audioop = None

#---------------CONFIGURATION---------------
class Settings(BaseSettings):
    TWILIO_ACCOUNT_SID: str 
    TWILIO_AUTH_TOKEN: str
    EXTERNAL_WEBHOOK_URL: str  # External URL for WebSocket (e.g., ngrok URL)
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
    FORCE_SAY_ONLY: bool = True  # Diagnostics: avoid TTS and use <Say>
    class Config:
       load_dotenv()

settings = Settings()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
WHISPER_MODEL = "whisper-1"

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

#---------------LOGGING SETUP---------------
logging.basicConfig(
    level=settings.LOG_LEVEL,
    format="%(asctime)s %(levelname)s %(name)s %(message)s"  
)
logger = logging.getLogger("voice-intent")

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

# New: metrics snapshot computation and broadcast utilities

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

twilio_client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)

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
    resp.say("Thank you for calling SafeHarbour Plumbing Services. We're here to help with all your plumbing needs. What can we assist you with today?")
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
async def media_stream(ws: WebSocket):
    """Enhanced WebSocket endpoint for Twilio media streaming with better error handling"""
    try:
        # Accept connection first, then validate
        await ws.accept()
        
        # Extract CallSid from query parameters if available (Twilio may not forward query params)
        callSid = ws.query_params.get("callSid")
        logger.info(f"WebSocket connection accepted for potential CallSid={callSid}")
        logger.info(f"All query params: {dict(ws.query_params)}")
        logger.info(f"WebSocket URL: {ws.url}")
        
        # If CallSid not present in query, wait for Twilio 'start' event which includes it
        if not callSid:
            logger.info("CallSid not in query params, waiting for 'start' event from Twilio...")
            try:
                handshake_deadline = time.time() + 10.0  # seconds
                temporary_stream_key = None
                while time.time() < handshake_deadline and not callSid:
                    msg = await ws.receive_text()
                    logger.debug(f"Init/handshake message received: {msg[:200]}...")
                    try:
                        data = json.loads(msg)
                    except json.JSONDecodeError as e:
                        logger.error(f"Failed to parse handshake message as JSON: {e}")
                        continue

                    event_type = data.get("event")
                    if event_type == "connected":
                        # Initial Twilio message, continue waiting for 'start'
                        logger.debug("Received 'connected' event; awaiting 'start' for CallSid...")
                        continue

                    if event_type == "start":
                        start_obj = data.get("start") or {}
                        # Twilio uses lowercase 'callSid' in WebSocket events
                        callSid = start_obj.get("callSid") or start_obj.get("CallSid")
                        stream_sid = start_obj.get("streamSid") or data.get("streamSid")
                        # Capture media format for decoding
                        media_format = start_obj.get("mediaFormat", {})
                        enc = str(media_format.get("encoding", "mulaw")).lower()
                        sr = int(media_format.get("sampleRate", SAMPLE_RATE_DEFAULT))
                        if "mulaw" in enc or "pcmu" in enc:
                            audio_config_store[callSid] = {"encoding": "mulaw", "sample_rate": sr}
                        elif "l16" in enc or "pcm" in enc:
                            audio_config_store[callSid] = {"encoding": "pcm16", "sample_rate": sr}
                        else:
                            audio_config_store[callSid] = {"encoding": "mulaw", "sample_rate": SAMPLE_RATE_DEFAULT}
                        logger.info(f"Media format for {callSid}: {audio_config_store[callSid]}")
                        if not callSid and stream_sid:
                            # As a temporary fallback, use streamSid until CallSid is available
                            temporary_stream_key = f"stream:{stream_sid}"
                            manager.active_connections[temporary_stream_key] = ws
                            logger.warning(f"Using streamSid as temporary key before CallSid is available: {temporary_stream_key}")
                        if callSid:
                            # Store connection under the real CallSid
                            manager.active_connections[callSid] = ws
                            logger.info(f"✅ CallSid found in start event: {callSid}")
                            # Process the already-received start packet
                            asyncio.create_task(handle_media_packet(callSid, msg))
                            break
                        else:
                            logger.error("Start event received but no callSid present.")
                            continue

                    # In the unlikely case 'media' arrives before 'start', try to recover
                    possible_call_sid = data.get("callSid") or data.get("CallSid")
                    if possible_call_sid:
                        callSid = possible_call_sid
                        manager.active_connections[callSid] = ws
                        logger.info(f"✅ CallSid found outside start event: {callSid}")
                        asyncio.create_task(handle_media_packet(callSid, msg))
                        break

                    stream_sid = data.get("streamSid") or (data.get("start") or {}).get("streamSid")
                    if stream_sid and not temporary_stream_key:
                        temporary_stream_key = f"stream:{stream_sid}"
                        manager.active_connections[temporary_stream_key] = ws
                        logger.warning(f"Temporarily storing connection with key {temporary_stream_key} until CallSid arrives...")
                        continue

                if not callSid:
                    logger.warning("Missing CallSid after waiting for start event")
                    await ws.close(code=1008, reason="Missing CallSid parameter")
                    return
            except WebSocketDisconnect:
                logger.warning("❌ WebSocket disconnected before CallSid could be found.")
                return
            except Exception as e:
                logger.error(f"❌ Error receiving messages to find CallSid: {e}")
                return
        
        # Ensure connection is registered (if query param was present)
        if callSid not in manager.active_connections:
            manager.active_connections[callSid] = ws
            logger.info(f"WebSocket connection established for CallSid={callSid}")
        
        # Push updated metrics for active call count
        try:
            await _broadcast_ops_metrics()
        except Exception:
            pass
        
        # Start receiving messages
        try:
            while True:
                msg = await ws.receive_text()
                asyncio.create_task(handle_media_packet(callSid, msg))
        except WebSocketDisconnect:
            logger.info(f"WebSocket disconnected for CallSid={callSid}")
        except Exception as e:
            logger.error(f"WebSocket error for CallSid={callSid}: {e}")
        finally:
            try:
                _finalize_call_metrics(callSid)
            except Exception:
                pass
            try:
                await _broadcast_ops_metrics()
            except Exception:
                pass
            await manager.disconnect(callSid)
            
    except Exception as e:
        logger.error(f"WebSocket connection failed: {e}")
        try:
            await ws.close(code=1011, reason="Internal server error")
        except:
            pass

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
        
        logger.info(f"Sending audio to Whisper for {call_sid} (model: {WHISPER_MODEL})")
        start_time = time.time()
        
        wav_file = io.BytesIO(wav_for_whisper)
        try:
            wav_file.name = "speech.wav"  # Help the API infer format
        except Exception:
            pass
        
        resp = client.audio.transcriptions.create(
            model=WHISPER_MODEL,
            file=wav_file,
            response_format="verbose_json",
            language="en",
            prompt="Caller is describing a plumbing issue or asking a question. Ignore background noise, dial tones, and hangup signals."
        )
        
        whisper_duration = time.time() - start_time
        logger.info(f"Whisper processing completed for {call_sid} in {whisper_duration:.2f}s")
        
        text = (resp.text or "").strip()
        # Confidence/quality gating using segments avg_logprob
        avg_logprobs = []
        for seg in getattr(resp, 'segments', []) or []:
            lp = getattr(seg, 'avg_logprob', None)
            if isinstance(lp, (int, float)):
                avg_logprobs.append(lp)
        mean_lp = sum(avg_logprobs) / len(avg_logprobs) if avg_logprobs else None
        
        normalized = text.lower().strip().strip(".,!? ")
        short_garbage = {"bye", "hi", "uh", "um", "hmm", "huh"}
        should_suppress = False
        if not text:
            should_suppress = True
        elif len(normalized) <= 3 and normalized in short_garbage:
            should_suppress = True
        elif mean_lp is not None and mean_lp < -1.0:
            should_suppress = True
        
        if should_suppress:
            logger.info(f"Suppressed low-confidence/short transcription for {call_sid}: '{text}' (avg_logprob={mean_lp})")
            return
        
        logger.info(f'🎤 USER SPEECH ({call_sid}): "{text}" [duration: {audio_duration_ms:.0f}ms, whisper_time: {whisper_duration:.2f}s, avg_logprob: {mean_lp}]')
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

        # Scheduling follow-up handling
        if dialog and dialog.get('step') in ('awaiting_time', 'awaiting_time_confirm'):
            logger.info(f"Handling follow-up scheduling utterance for {call_sid}: '{text}'")
            twiml = await handle_intent(call_sid, dialog.get('intent', {}), followup_text=text)
            await push_twiml_to_call(call_sid, twiml)
            return

        # Otherwise, extract a fresh intent
        intent = await extract_intent_from_text(call_sid, text)
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

# TTS: synthesize with Eleven Labs
async def synthesize_tts(text: str) -> Optional[bytes]:
    if not settings.ELEVENLABS_API_KEY:
        return None
    voice_id = settings.ELEVENLABS_VOICE_ID or "21m00Tcm4TlvDq8ikWAM"  # default voice
    model_id = settings.ELEVENLABS_MODEL_ID or "eleven_multilingual_v2"
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
    headers = {
        "xi-api-key": settings.ELEVENLABS_API_KEY,
        "accept": "audio/mpeg",
        "Content-Type": "application/json",
    }
    payload = {
        "text": text,
        "model_id": model_id,
        "voice_settings": {
            "stability": 0.5,
            "similarity_boost": 0.75
        }
    }
    async with httpx.AsyncClient(timeout=30) as http:
        r = await http.post(url, headers=headers, json=payload)
        if r.status_code == 200 and r.content:
            return r.content
        logger.error(f"ElevenLabs TTS failed: {r.status_code} {r.text}")
        return None

async def add_tts_or_say_to_twiml(target, call_sid: str, text: str):
    speak_text = text.replace("_", " underscore ")
    if settings.FORCE_SAY_ONLY:
        logger.info(f"FORCE_SAY_ONLY enabled; using <Say> for CallSid={call_sid}")
        target.say(speak_text)
        return
    audio = await synthesize_tts(speak_text)
    if audio:
        tts_audio_store[call_sid] = audio
        audio_url = f"{settings.EXTERNAL_WEBHOOK_URL}/tts/{call_sid}.mp3"
        logger.info(f"Using ElevenLabs TTS for CallSid={call_sid} ({len(audio)} bytes)")
        target.play(audio_url)
    else:
        logger.info(f"Using TwiML <Say> for CallSid={call_sid}")
        target.say(speak_text)

# Push updated TwiML mid-call to Twilio
async def push_twiml_to_call(call_sid: str, response: VoiceResponse):
    try:
        twiml_str = str(response)
        last_twiml_store[call_sid] = twiml_str
        logger.info(f"🔊 Pushing TwiML to call {call_sid}")
        logger.debug(f"Updating call {call_sid} with TwiML: {twiml_str}")
        loop = asyncio.get_event_loop()
        def _update():
            return twilio_client.calls(call_sid).update(twiml=twiml_str)
        result = await loop.run_in_executor(None, _update)
        logger.info(f"Pushed TwiML update to call {call_sid}; status={getattr(result, 'status', 'unknown')}")
    except Exception as e:
        logger.error(f"Failed to push TwiML directly to call {call_sid}: {e}; attempting URL fallback")
        try:
            url = f"{settings.EXTERNAL_WEBHOOK_URL}/twiml/{call_sid}"
            loop = asyncio.get_event_loop()
            def _update_url():
                return twilio_client.calls(call_sid).update(url=url, method="GET")
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
    if overall_confidence < 0.6:
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

def is_negative_response(text: str) -> bool:
    norm = " ".join(text.lower().split())
    if norm in NEGATIVE_PATTERNS:
        return True
    # Prefix matches for common closers
    for p in ("no ", "no,", "no.", "nope", "nah"):
        if norm.startswith(p):
            return True
    return False

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

    # If followup_text is provided, treat as user's response to scheduling prompt (no <Gather>, keep streaming)
    if followup_text:
        import dateutil.parser
        try:
            preferred_time = dateutil.parser.parse(followup_text, fuzzy=True)
        except Exception:
            preferred_time = None
        if preferred_time:
            try:
                start_time = preferred_time
                # Use calendar adapter only if available
                calendar_adapter = CalendarAdapter()
                events = []
                if getattr(calendar_adapter, 'enabled', False):
                    end_time = preferred_time + timedelta(hours=2)
                    events = calendar_adapter.get_events(start_date=start_time, end_date=end_time)
                if not events:
                    book_scheduled_job(
                        phone=customer_phone or '',
                        name=customer_name,
                        service=job_type,
                        appointment_time=start_time,
                        address=address,
                        notes=notes
                    )
                    await add_tts_or_say_to_twiml(twiml, call_sid, f"Your appointment for {job_type} is scheduled at {start_time.strftime('%Y-%m-%d %H:%M')}. Thanks for trusting SafeHarbour to help you with your plumbing needs. Please let me know if you have any other questions.")
                    call_dialog_state[call_sid] = {'intent': intent, 'step': 'post_booking_qa'}
                else:
                    next_available = start_time + timedelta(hours=2)
                    if getattr(calendar_adapter, 'enabled', False):
                        for i in range(1, 8):
                            slot_start = start_time + timedelta(hours=2*i)
                            slot_end = slot_start + timedelta(hours=2)
                            slot_events = calendar_adapter.get_events(start_date=slot_start, end_date=slot_end)
                            if not slot_events:
                                next_available = slot_start
                                break
                    await add_tts_or_say_to_twiml(twiml, call_sid, f"The requested time is unavailable. The next available slot is {next_available.strftime('%Y-%m-%d %H:%M')}.")
                    call_dialog_state[call_sid] = {'intent': intent, 'step': 'awaiting_time_confirm', 'suggested_time': next_available}
            except Exception as e:
                logger.error(f"Scheduling failed: {e}")
                await add_tts_or_say_to_twiml(twiml, call_sid, "We're having trouble checking availability. Please hold while we connect you to a human agent.")
                call_dialog_state.pop(call_sid, None)
        else:
            await add_tts_or_say_to_twiml(twiml, call_sid, "I didn't catch a valid date and time. Please repeat the date and time you'd like to schedule, or say 'anytime'.")
            call_dialog_state[call_sid] = {'intent': intent, 'step': 'awaiting_time'}
        append_stream_and_pause(twiml)
        logger.info(f"Handled followup scheduling for CallSid={call_sid}")
        return twiml

    # Initial intent handling (no <Gather>; we keep streaming and listen continuously)
    if urgency == 'emergency':
        try:
            booking_result = book_emergency_job(
                phone=customer_phone or '',
                name=customer_name,
                service=job_type,
                address=address,
                notes=notes
            )
            appointment_time = booking_result.get('appointment_time')
            if not appointment_time:
                appointment_time = (datetime.now() + timedelta(hours=1)).strftime('%Y-%m-%d %H:%M')
            await add_tts_or_say_to_twiml(twiml, call_sid, f"This is an emergency. We'll send the best available technician for {job_type} at the next available slot: {appointment_time}.")
            # Transition to post-booking Q&A prompt
            await add_tts_or_say_to_twiml(twiml, call_sid, "Thanks for trusting SafeHarbour to help you with your plumbing needs. Please let me know if you have any other questions.")
            call_dialog_state[call_sid] = {'intent': intent, 'step': 'post_booking_qa'}
        except Exception as e:
            logger.error(f"Emergency booking failed: {e}")
            await add_tts_or_say_to_twiml(twiml, call_sid, "We're having trouble booking the next available technician. Please hold while we connect you to a human agent.")
            call_dialog_state.pop(call_sid, None)
    else:
        await add_tts_or_say_to_twiml(twiml, call_sid, f"Got it. For your {job_type}, what date and time works best?")
        call_dialog_state[call_sid] = {'intent': intent, 'step': 'awaiting_time'}
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