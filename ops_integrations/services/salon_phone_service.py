"""
Salon Phone Service refactor to Twilio ConversationRelay + Conversational Intelligence (CI)
- Low-latency barge-in via ConversationRelay WebSocket
- Post-call transcripts/analytics via CI webhook
"""

import asyncio
import json
import logging
import time
from datetime import datetime
from typing import Dict, Any, Optional

from fastapi import FastAPI, Request, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import Response
from fastapi.middleware.cors import CORSMiddleware
from twilio.request_validator import RequestValidator
from twilio.rest import Client as TwilioClient
from twilio.twiml.voice_response import VoiceResponse, Connect
from openai import AsyncOpenAI
from pydantic_settings import BaseSettings

# Simple call tracking and transcript storage
call_info_store: Dict[str, Dict] = {}
conversation_transcripts: Dict[str, Dict] = {}


class Settings(BaseSettings):
    # Twilio credentials
    TWILIO_ACCOUNT_SID: str = ""
    TWILIO_AUTH_TOKEN: str = ""
    
    # OpenAI for conversational AI
    OPENAI_API_KEY: str = ""
    
    # ElevenLabs Voice selection (used by Twilio TTS provider)
    ELEVENLABS_VOICE_ID: str = "kdmDKE6EkgrWrrykO9Qt"
    
    # Twilio Conversational Intelligence (GA) Service SID
    CI_SERVICE_SID: str = ""

    # Public URLs
    PUBLIC_BASE_URL: str = ""
    WSS_PUBLIC_URL: str = ""
    
    # Service endpoints
    VOICE_ENDPOINT: str = "/voice"
    TRANSCRIPTS_ENDPOINT: str = "/intelligence/transcripts"
    
    # Other
    LOG_LEVEL: str = "INFO"


settings = Settings()

# Initialize OpenAI (async) if configured
openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY) if settings.OPENAI_API_KEY else None

# Initialize Twilio client
twilio_client = TwilioClient(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN) if settings.TWILIO_ACCOUNT_SID and settings.TWILIO_AUTH_TOKEN else None

# FastAPI app
app = FastAPI(title="Salon Phone Service - ConversationRelay + CI")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


def _build_conversation_relay_twiml() -> str:
    """Return TwiML Response XML with <Connect><ConversationRelay .../></Connect>."""
    welcome = "Welcome to Bold Wings Salon! How can I assist you today?"
    ws_url = settings.WSS_PUBLIC_URL.rstrip("/") + "/cr"
    voice = settings.ELEVENLABS_VOICE_ID
    ci_sid = settings.CI_SERVICE_SID
    
    # Build TwiML using VoiceResponse for proper structure
    resp = VoiceResponse()
    connect = Connect()
    
    # Add ConversationRelay XML directly since twilio-python doesn't have ConversationRelay class yet
    connect_xml = f'''<ConversationRelay 
        url="{ws_url}" 
        welcomeGreeting="{welcome}"
        transcriptionProvider="google"
        speechModel="telephony"
        ttsProvider="elevenlabs"
        voice="{voice}"'''
    
    if ci_sid:
        connect_xml += f' intelligenceService="{ci_sid}"'
    
    connect_xml += "/>"
    
    # Create the full TwiML response
    twiml = f'''<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Connect>
        {connect_xml}
    </Connect>
</Response>'''
    
    return twiml


def _validate_twilio_signature(request: Request, full_url: str) -> None:
    signature = request.headers.get("X-Twilio-Signature", "")
    if not signature:
        raise HTTPException(status_code=403, detail="Missing X-Twilio-Signature")
    validator = RequestValidator(settings.TWILIO_AUTH_TOKEN)
    try:
        # Twilio signs form-encoded params for voice webhooks
        # Note: Must read form BEFORE validation to include params
        # The caller of this helper must pass the same form
        pass
    except Exception:
        # No-op; helper is used inline after reading form
        pass
    # Validation is performed by caller with the actual params


@app.post(settings.VOICE_ENDPOINT)
async def voice_webhook(request: Request):
    """Return TwiML that connects the call to ConversationRelay."""
    form = await request.form()

    # Security: validate Twilio signature
    expected_url = settings.PUBLIC_BASE_URL.rstrip("/") + settings.VOICE_ENDPOINT
    signature = request.headers.get("X-Twilio-Signature", "")
    validator = RequestValidator(settings.TWILIO_AUTH_TOKEN)
    params = {k: v for k, v in form.items()}
    if not signature or not validator.validate(expected_url, params, signature):
        raise HTTPException(status_code=403, detail="Invalid Twilio signature")

    call_sid = form.get("CallSid") or ""
    caller_number = form.get("From") or ""
    if call_sid:
        call_info_store[call_sid] = {
            "call_sid": call_sid,
            "from": caller_number,
            "start_time": datetime.now().isoformat(),
        }
        logging.info(f"Salon call started: {call_sid} from {caller_number}")

    # Return ConversationRelay TwiML
    if not settings.CI_SERVICE_SID:
        logging.warning("CI_SERVICE_SID not set; CI analytics will be disabled in call")
    if not settings.WSS_PUBLIC_URL.startswith("wss://"):
        logging.warning("WSS_PUBLIC_URL should start with wss:// for production")

    xml = _build_conversation_relay_twiml()
    ws_url = settings.WSS_PUBLIC_URL.rstrip("/") + "/cr"
    logging.info(f"Generated ConversationRelay TwiML for {call_sid}: {ws_url}")
    return Response(content=xml, media_type="application/xml")


# WebSocket ConversationRelay endpoint
@app.websocket("/cr")
async def conversation_relay_websocket(websocket: WebSocket):
    """Handle ConversationRelay WebSocket connections from Twilio"""
    
    # Accept the WebSocket connection first
    await websocket.accept()
    logging.info(f"ConversationRelay WebSocket connection accepted from {websocket.client}")
    
    # Optional: Validate WSS in production (but allow HTTP for local testing)
    xf_proto = websocket.headers.get("X-Forwarded-Proto", "")
    url_str = str(websocket.url)
    if not url_str.startswith("wss://") and xf_proto not in ("https", "wss"):
        if "localhost" not in url_str and "127.0.0.1" not in url_str:
            logging.warning(f"Non-WSS connection in production: {url_str}")
    
    # ConversationRelay typically doesn't send Twilio signatures on WebSocket connections
    # So we're permissive here and rely on the fact that only Twilio knows our WebSocket URL

    cancel_event = asyncio.Event()
    current_task: Optional[asyncio.Task] = None
    last_rx = time.time()

    # ConversationRelay manages its own heartbeat, so we don't need our own
    # async def heartbeat() -> None:
    #     try:
    #         while True:
    #             await asyncio.sleep(25)
    #             await websocket.send_json({"type": "ping", "ts": int(time.time())})
    #     except Exception:
    #         return

    async def idle_monitor() -> None:
        try:
            while True:
                await asyncio.sleep(10)
                if time.time() - last_rx > 300:
                    await websocket.close(code=1000)
                    return
        except Exception:
            return

    # hb_task = asyncio.create_task(heartbeat())  # Not needed for ConversationRelay
    idle_task = asyncio.create_task(idle_monitor())

    async def stream_response(prompt_text: str) -> None:
        try:
            if not openai_client:
                await websocket.send_json({
                    "type": "text", "token": "I'm having trouble right now.", "last": True, "interruptible": True
                })
                return
            # Enhanced system instruction tuned for salon assistant
            system_msg = (
                "You are a friendly salon assistant for Bold Wings Salon. "
                "You help customers with bookings, services, and questions. "
                "Be warm, conversational, and brief (under 50 words). "
                "Always ask a helpful follow-up question to continue the conversation."
            )
            stream = await openai_client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": system_msg},
                    {"role": "user", "content": prompt_text},
                ],
                temperature=0.7,
                max_tokens=200,
                stream=True,
            )

            async for event in stream:
                if cancel_event.is_set():
                    break
                try:
                    delta = event.choices[0].delta
                    token = getattr(delta, "content", None)
                    if token:
                        await websocket.send_json({
                            "type": "text", "token": token, "last": False, "interruptible": True
                        })
                except Exception:
                    # Some chunks may not have textual deltas
                    pass

            if not cancel_event.is_set():
                await websocket.send_json({
                    "type": "text", "token": "", "last": True, "interruptible": True
                })
        except Exception as e:
            logging.error(f"Streaming error: {e}")
            try:
                await websocket.send_json({
                    "type": "text", "token": "", "last": True, "interruptible": True
                })
            except Exception:
                pass

    try:
        while True:
            message = await websocket.receive_text()
            last_rx = time.time()
            logging.info(f"WebSocket received message: {message}")
            try:
                payload = json.loads(message)
            except json.JSONDecodeError:
                logging.warning(f"Failed to parse WebSocket message as JSON: {message}")
                continue

            msg_type = payload.get("type")
            logging.info(f"WebSocket message type: {msg_type}, payload: {payload}")

            if msg_type == "setup":
                # Store session state from ConversationRelay setup
                session_id = payload.get("sessionId") or payload.get("conversationId") or ""
                call_sid = payload.get("callSid") or ""
                logging.info(f"🔗 ConversationRelay setup received - CallSid: {call_sid}, SessionId: {session_id}")
                logging.info(f"Setup payload: {payload}")
                
                if call_sid:
                    call_info_store.setdefault(call_sid, {}).update({
                        "session_id": session_id,
                        "setup_time": datetime.now().isoformat(),
                        "websocket_connected": True
                    })
                
                # Send ready response to ConversationRelay
                # Based on Twilio docs, we may need to send a different format or no response
                # Let's try without sending ready first to see if it works
                logging.info(f"✅ ConversationRelay setup complete - ready to receive prompts")

            elif msg_type == "prompt":
                # ConversationRelay sends transcribed text in 'voicePrompt' field
                text = payload.get("voicePrompt", "").strip()
                logging.info(f"ConversationRelay prompt received: '{text}'")
                if not text:
                    continue
                # Interrupt any existing stream
                if current_task and not current_task.done():
                    cancel_event.set()
                    try:
                        await asyncio.wait_for(current_task, timeout=1.0)
                    except Exception:
                        pass
                    cancel_event.clear()
                current_task = asyncio.create_task(stream_response(text))

            elif msg_type == "interrupt":
                if current_task and not current_task.done():
                    cancel_event.set()
                    await websocket.send_json({"type": "interrupted"})

            elif msg_type == "ping":
                # ConversationRelay might not expect a pong response, just log it
                logging.info(f"Received ping from ConversationRelay: {payload}")
                # Don't send pong to avoid 64107 error
                
            elif msg_type == "error":
                # Log ConversationRelay errors for debugging
                error_desc = payload.get("description", "Unknown error")
                logging.warning(f"ConversationRelay error: {error_desc}")
                
            else:
                # Log unknown message types
                logging.info(f"Unknown ConversationRelay message type: {msg_type}, payload: {payload}")

    except WebSocketDisconnect:
        pass
    except Exception as e:
        logging.error(f"WebSocket error: {e}")
    finally:
        try:
            if current_task and not current_task.done():
                cancel_event.set()
            # hb_task.cancel()  # Not used for ConversationRelay
            idle_task.cancel()
        except Exception:
            pass


@app.post(settings.TRANSCRIPTS_ENDPOINT)
async def intelligence_transcripts(request: Request):
    """Receive CI transcript payload; store and log core insights."""
    try:
        content_type = request.headers.get("con                                                                                                                           tent-type", "")
        data: Dict[str, Any]
        if content_type.startswith("application/json"):
            data = await request.json()
        else:
            form = await request.form()
            data = {k: v for k, v in form.items()}

        call_sid = data.get("CallSid") or data.get("call_sid") or data.get("callSid") or ""
        transcript_sid = data.get("TranscriptSid") or data.get("transcript_sid") or data.get("transcriptSid") or ""
        conversation_transcripts[transcript_sid or call_sid or str(time.time())] = data

        # Try to extract common CI summary fields if present
        try:
            insights = data.get("insights") or {}
            outcome = insights.get("outcome") or data.get("outcome")
            intent = insights.get("intent") or data.get("intent")
            sentiment = insights.get("sentiment") or data.get("sentiment")
            logging.info(f"CI summary for {call_sid}: outcome={outcome}, intent={intent}, sentiment={sentiment}")
        except Exception:
            pass

        return {"status": "ok"}
    except Exception as e:
        logging.error(f"CI transcripts error: {e}")
        return {"status": "error"}


@app.get("/health")
async def health_check():
    return {"ok": True, "ci": bool(settings.CI_SERVICE_SID), "relay": settings.WSS_PUBLIC_URL.startswith("wss://")} 


# Basic logging setup
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("salon_phone_service:app", host="0.0.0.0", port=5001, reload=True)