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
from typing import Dict, Any, Optional, List, Set

from fastapi import FastAPI, Request, HTTPException, WebSocket, WebSocketDisconnect, Depends
from fastapi.responses import Response
from fastapi.middleware.cors import CORSMiddleware
from twilio.request_validator import RequestValidator
from twilio.rest import Client as TwilioClient
from twilio.twiml.voice_response import VoiceResponse, Connect
from openai import AsyncOpenAI
from pydantic_settings import BaseSettings
# Import our services (no longer using SQLAlchemy)
from .booking_service import booking_service
from .knowledge_service import knowledge_service
from .static_data_manager import static_data_manager, setup_location_data, get_location_status
from .unified_supabase_service import get_unified_supabase_service, CallData, AppointmentData

# Conversation context storage (replaced DB storage for call tracking)
conversation_context: Dict[str, Dict[str, Any]] = {}  # call_sid -> call data with location info

# WebSocket clients for real-time updates
ops_ws_clients: Set[WebSocket] = set()


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
    
    # Database
    DATABASE_URL: str = ""
    
    # Default location (for single-location deployments)
    DEFAULT_LOCATION_ID: int = 1
    
    # Phone number to location mapping (JSON string)
    # +18084826296 (808 number) -> Location 1 (SafeHarbour's Salon)
    # +1234567890 (placeholder) -> Location 2 (Teni's Salon)
    PHONE_TO_LOCATION_MAP: str = '{"+18084826296": 1, "+1234567890": 2}'
    
    # Other
    LOG_LEVEL: str = "INFO"


settings = Settings()

def get_location_from_phone_number(to_number: str) -> int:
    """Determine location ID from incoming phone number"""
    try:
        phone_map = json.loads(settings.PHONE_TO_LOCATION_MAP)
        location_id = phone_map.get(to_number, settings.DEFAULT_LOCATION_ID)
        logging.info(f"📍 Phone {to_number} mapped to location {location_id}")
        return location_id
    except Exception as e:
        logging.warning(f"Failed to parse phone mapping, using default location: {e}")
        return settings.DEFAULT_LOCATION_ID

# Initialize OpenAI (async) if configured
openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY) if settings.OPENAI_API_KEY else None

# Initialize Twilio client
twilio_client = TwilioClient(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN) if settings.TWILIO_ACCOUNT_SID and settings.TWILIO_AUTH_TOKEN else None

# Initialize unified Supabase service
supabase_service = get_unified_supabase_service()
logging.info("✅ Using unified Supabase storage backend")

# FastAPI app
app = FastAPI(title="Salon Phone Service - ConversationRelay + CI")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

@app.on_event("startup")
async def startup_event():
    """Initialize services on startup"""
    try:
        # Initialize static data for all locations
        # Note: setup_location_data requires specific location_id and website_url
        # For now, we'll skip this and let the service load data on-demand
        
        # Pre-load knowledge for all locations
        await knowledge_service._load_all_locations_on_startup()
        
        logging.info("✅ Salon phone service startup completed")
    except Exception as e:
        logging.error(f"Failed to initialize services: {e}")


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
        voice="{voice}"
        bargeIn="true"
        bargeInGracePeriod="3000"
        endOfSpeechTimeout="2500"
        interruptByDtmf="false"'''
    
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
    to_number = form.get("To") or ""
    
    # Determine location from phone number
    location_id = get_location_from_phone_number(to_number)
    
    # Initialize conversation context and log call to Supabase
    if call_sid:
        try:
            # Initialize conversation context with location info
            conversation_context[call_sid] = {
                'location_id': location_id,
                'caller_number': caller_number,
                'to_number': to_number,
                'messages': [],
                'start_time': datetime.now().isoformat()
            }
            
            # Log call to Supabase using unified service
            call_data = CallData(
                call_sid=call_sid,
                salon_id=str(location_id),  # Convert to string for UUID compatibility
                caller_phone=caller_number,
                call_type="answered",
                outcome="in_progress",
                timestamp=datetime.now().isoformat()
            )
            
            await supabase_service.log_call(call_data)
            
            logging.info(f"🏪 Salon call started: {call_sid} from {caller_number} to {to_number} (Location {location_id})")
            
            # Broadcast call start to dashboard
            await _broadcast_to_dashboard("call_started", {
                "call_sid": call_sid,
                "location_id": location_id,
                "caller_number": caller_number,
                "to_number": to_number,
                "timestamp": datetime.now().isoformat()
            })
        except Exception as e:
            logging.error(f"Failed to create call record: {e}")

    # Return ConversationRelay TwiML
    if not settings.CI_SERVICE_SID:
        logging.warning("CI_SERVICE_SID not set; CI analytics will be disabled in call")
    if not settings.WSS_PUBLIC_URL.startswith("wss://"):
        logging.warning("WSS_PUBLIC_URL should start with wss:// for production")

    xml = _build_conversation_relay_twiml()
    ws_url = settings.WSS_PUBLIC_URL.rstrip("/") + "/cr"
    logging.info(f"Generated ConversationRelay TwiML for {call_sid}: {ws_url}")
    logging.info(f"🔧 ConversationRelay config - bargeInGracePeriod: 3000ms, endOfSpeechTimeout: 2500ms")
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
        start_time = time.time()
        try:
            if not openai_client:
                await websocket.send_json({
                    "type": "text", "token": "I'm having trouble right now.", "last": True, "interruptible": True
                })
                return
            
            logging.info(f"🤖 Starting GPT-4o AI response generation for: '{prompt_text[:30]}{'...' if len(prompt_text) > 30 else ''}'")
            
            # Get location-specific context from call
            call_data = conversation_context.get(call_sid, {})
            location_id = call_data.get('location_id', settings.DEFAULT_LOCATION_ID)
            
            # Get location knowledge for enhanced responses (pre-loaded, no delay)
            location_context = await knowledge_service.get_ai_context_for_location(location_id)
            if not location_context:
                location_context = f"I'm a salon assistant for location {location_id}. I can help with basic questions and appointments."
            
            # Check if we should confirm booking  
            call_context = call_data.get('messages', [])
            should_confirm = await booking_service.should_confirm_booking(call_context, prompt_text)
            
            # Enhanced system instruction with location knowledge
            system_msg = (
                "You are a friendly salon assistant. Use the following information to help customers:\n\n"
                f"{location_context}\n\n"
                "Guidelines:\n"
                "- Be warm, conversational, and brief (under 50 words)\n"
                "- Use specific service names, prices, and durations when available\n"
                "- Mention staff specialties when relevant\n"
                "- Answer questions using the FAQ information\n"
                "- When customers show booking intent, offer to schedule appointments\n"
                f"- {'ASK FOR BOOKING CONFIRMATION NOW - they seem ready to book!' if should_confirm else 'Continue the conversation naturally'}\n"
                "- Always ask a helpful follow-up question"
            )
            
            # Add conversation history for better context
            messages = [{"role": "system", "content": system_msg}]
            
            # Add recent conversation history
            if call_context:
                for i, msg in enumerate(call_context[-6:]):  # Last 6 messages
                    role = "assistant" if i % 2 == 1 else "user"
                    messages.append({"role": role, "content": msg})
            
            messages.append({"role": "user", "content": prompt_text})
            
            stream = await openai_client.chat.completions.create(
                model="gpt-4o",
                messages=messages,
                temperature=0.7,
                max_tokens=250,
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
                duration = time.time() - start_time
                logging.info(f"✅ AI response completed in {duration:.2f}s (not interrupted)")
                
                # Broadcast transcript to dashboard
                try:
                    await _broadcast_to_dashboard("transcript", {
                        "call_sid": call_sid,
                        "location_id": location_id,
                        "prompt": prompt_text,
                        "response": "AI response completed",  # Response content not available in this scope
                        "duration": f"{duration:.2f}s",
                        "timestamp": datetime.now().isoformat()
                    })
                except Exception as broadcast_error:
                    logging.warning(f"Failed to broadcast transcript: {broadcast_error}")
            else:
                duration = time.time() - start_time
                logging.info(f"❌ AI response cancelled after {duration:.2f}s (interrupted)")
        except Exception as e:
            duration = time.time() - start_time
            logging.error(f"💥 AI response error after {duration:.2f}s: {e}")
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
                    # Store session info in conversation context
                    if call_sid not in conversation_context:
                        conversation_context[call_sid] = []
                    
                    logging.info(f"Session {session_id} connected for call {call_sid}")
                
                # Send ready response to ConversationRelay
                # Based on Twilio docs, we may need to send a different format or no response
                # Let's try without sending ready first to see if it works
                logging.info(f"✅ ConversationRelay setup complete - ready to receive prompts")

            elif msg_type == "prompt":
                # ConversationRelay sends transcribed text in 'voicePrompt' field
                text = payload.get("voicePrompt", "").strip()
                is_last = payload.get("last", False)
                logging.info(f"💬 PROMPT received: '{text}' (last: {is_last})")
                if not text:
                    continue
                
                # Store conversation context
                session_id = payload.get("sessionId") or payload.get("conversationId") or ""
                if session_id and call_sid in conversation_context:
                    # Update the messages in the call context
                    if 'messages' not in conversation_context[call_sid]:
                        conversation_context[call_sid]['messages'] = []
                    conversation_context[call_sid]['messages'].append(text)
                    
                    # Keep only last 20 messages to prevent memory issues
                    if len(conversation_context[call_sid]['messages']) > 20:
                        conversation_context[call_sid]['messages'] = conversation_context[call_sid]['messages'][-20:]
                
                # Extract booking intent
                call_sid = payload.get("callSid") or ""
                intent_data = await booking_service.extract_booking_intent(text, call_sid)
                
                if intent_data.get("is_confirmation"):
                    logging.info(f"🎯 Booking confirmation detected in: '{text}'")
                    # Update call outcome in Supabase
                    await supabase_service.update_call_outcome(
                        call_sid, 
                        outcome="booked", 
                        intent=intent_data.get("detected_services", "appointment_booking"),
                        sentiment="positive"
                    )
                elif intent_data.get("has_booking_intent"):
                    logging.info(f"📅 Booking intent detected: {intent_data['detected_services']}")
                    # Update call outcome in Supabase
                    await supabase_service.update_call_outcome(
                        call_sid, 
                        outcome="inquiry", 
                        intent=intent_data.get("detected_services", "general_inquiry")
                    )
                
                # Interrupt any existing stream
                if current_task and not current_task.done():
                    logging.info(f"🔄 Interrupting previous AI response to handle new prompt")
                    cancel_event.set()
                    try:
                        await asyncio.wait_for(current_task, timeout=1.0)
                    except Exception:
                        pass
                    cancel_event.clear()
                current_task = asyncio.create_task(stream_response(text))

            elif msg_type == "interrupt":
                # Log interrupt details for debugging grace period effectiveness
                utterance = payload.get("utteranceUntilInterrupt", "")
                duration_ms = payload.get("durationUntilInterruptMs", 0)
                logging.info(f"🚫 INTERRUPT detected after {duration_ms}ms - Grace period: {'ACTIVE' if duration_ms < 2000 else 'EXPIRED'}")
                logging.info(f"   Interrupted utterance: '{utterance[:50]}{'...' if len(utterance) > 50 else ''}'")
                
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
        # Store transcript data (could be saved to database in future)
        logging.info(f"Received CI transcript for call {call_sid}, transcript {transcript_sid}")

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
    return {
        "ok": True, 
        "ci": bool(settings.CI_SERVICE_SID), 
        "relay": settings.WSS_PUBLIC_URL.startswith("wss://"),
        "storage": "unified_supabase",
        "knowledge_cache": len(knowledge_service.knowledge_cache)
    }

@app.post("/setup-location/{location_id}")
async def setup_location_data_endpoint(location_id: int, website_url: str = None):
    """One-time setup for location data (scrape and store statically)"""
    if not website_url:
        return {"error": "website_url parameter required"}
    
    try:
        result = await setup_location_data(location_id, website_url)
        return result
    except Exception as e:
        logging.error(f"Error setting up location {location_id}: {e}")
        return {"error": str(e)}

@app.get("/location/{location_id}/status")
async def get_location_data_status(location_id: int):
    """Get current status of location data"""
    return await get_location_status(location_id)

@app.get("/locations")
async def list_all_locations():
    """List all locations with static data"""
    return {"locations": static_data_manager.list_all_locations()}

@app.get("/location/{location_id}/knowledge")
async def get_location_knowledge(location_id: int):
    """Get current knowledge for a location"""
    knowledge = await knowledge_service.get_location_knowledge(location_id)
    
    if not knowledge:
        return {"error": "No knowledge available for this location"}
    
    return {
        "location_id": knowledge.location_id,
        "business_name": knowledge.business_name,
        "last_updated": knowledge.last_updated.isoformat(),
        "services_count": len(knowledge.services),
        "professionals_count": len(knowledge.professionals),
        "faq_count": len(knowledge.faq_items),
        "categories": knowledge.get_available_categories(),
        "price_range": knowledge.get_price_range()
    } 

@app.post("/shop/setup")
async def setup_new_shop(
    location_id: int,
    phone_number: str,
    website_url: str,
    business_name: str = None,
    voice_id: str = None
):
    """Setup a new shop with phone number mapping and website scraping"""
    try:
        # 1. Setup location data from website
        result = await setup_location_data(location_id, website_url)
        
        # 2. Create shop profile in Supabase using unified service
        shop_data = {
            'salon_id': str(location_id),  # Convert to string for UUID compatibility
            'salon_name': business_name or result.get("business_name", f"Shop {location_id}"),
            'business_name': business_name or result.get("business_name", "Unknown"),
            'website_url': website_url,
            'phone': phone_number,
            'timezone': 'America/New_York'  # Default timezone
        }
        
        shop_result = await supabase_service.create_or_update_shop(shop_data)
        if not shop_result['success']:
            raise Exception(f"Failed to create shop profile: {shop_result.get('error')}")
        
        # 3. Store services if available
        if 'services' in result:
            services_result = await supabase_service.store_services(str(location_id), result['services'])
            logging.info(f"Stored {services_result.get('services_count', 0)} services for shop {location_id}")
        
        # 4. Update phone number mapping
        current_map = json.loads(settings.PHONE_TO_LOCATION_MAP)
        current_map[phone_number] = location_id
        
        # Note: In production, you'd want to persist this to environment variables or database
        logging.info(f"📞 Phone {phone_number} mapped to location {location_id}")
        
        # 5. Broadcast shop update to dashboard
        await _broadcast_to_dashboard("shop_added", {
            "location_id": location_id,
            "phone_number": phone_number,
            "business_name": shop_data['business_name'],
            "timestamp": datetime.now().isoformat()
        })
        
        return {
            "success": True,
            "location_id": location_id,
            "phone_number": phone_number,
            "website_url": website_url,
            "business_name": shop_data['business_name'],
            "voice_id": voice_id or settings.ELEVENLABS_VOICE_ID,
            "phone_mapping": current_map,
            "services_count": services_result.get('services_count', 0) if 'services_result' in locals() else 0,
            "message": f"Shop {location_id} setup complete. Update PHONE_TO_LOCATION_MAP environment variable with: {json.dumps(current_map)}"
        }
    except Exception as e:
        logging.error(f"Error setting up shop {location_id}: {e}")
        return {"error": str(e)}

@app.get("/shop/{location_id}/config")
async def get_shop_config(location_id: int):
    """Get complete configuration for a shop"""
    try:
        # Get location data
        status = await get_location_status(location_id)
        knowledge = await knowledge_service.get_location_knowledge(location_id)
        
        # Find phone number for this location
        phone_map = json.loads(settings.PHONE_TO_LOCATION_MAP)
        phone_number = next((phone for phone, loc_id in phone_map.items() if loc_id == location_id), None)
        
        return {
            "location_id": location_id,
            "phone_number": phone_number,
            "status": status,
            "knowledge": {
                "business_name": knowledge.business_name if knowledge else None,
                "services_count": len(knowledge.services) if knowledge else 0,
                "professionals_count": len(knowledge.professionals) if knowledge else 0,
                "last_updated": knowledge.last_updated.isoformat() if knowledge else None
            },
            "voice_settings": {
                "voice_id": settings.ELEVENLABS_VOICE_ID,
                "barge_in_grace_period": "3000ms",
                "end_of_speech_timeout": "2500ms"
            }
        }
    except Exception as e:
        logging.error(f"Error getting shop config {location_id}: {e}")
        return {"error": str(e)}

@app.post("/shop/{location_id}/update")
async def update_shop_config(
    location_id: int,
    business_name: str = None,
    phone_number: str = None,
    website_url: str = None
):
    """Update existing shop configuration"""
    try:
        # Prepare shop data for update
        shop_data = {
            'salon_id': str(location_id),
            'salon_name': business_name,
            'phone': phone_number,
            'timezone': 'America/New_York'
        }
        
        # Remove None values
        shop_data = {k: v for k, v in shop_data.items() if v is not None}
        
        if not shop_data:
            return {"error": "No data provided for update"}
        
        # Update shop profile in Supabase
        shop_result = await supabase_service.create_or_update_shop(shop_data)
        if not shop_result['success']:
            raise Exception(f"Failed to update shop profile: {shop_result.get('error')}")
        
        # Update phone number mapping if phone provided
        if phone_number:
            current_map = json.loads(settings.PHONE_TO_LOCATION_MAP)
            current_map[phone_number] = location_id
            logging.info(f"📞 Phone {phone_number} mapped to location {location_id}")
        
        # Broadcast shop update to dashboard
        await _broadcast_to_dashboard("shop_updated", {
            "location_id": location_id,
            "business_name": business_name,
            "phone_number": phone_number,
            "timestamp": datetime.now().isoformat()
        })
        
        return {
            "success": True,
            "location_id": location_id,
            "business_name": business_name,
            "phone_number": phone_number,
            "message": f"Shop {location_id} updated successfully"
        }
    except Exception as e:
        logging.error(f"Error updating shop {location_id}: {e}")
        return {"error": str(e)}

@app.get("/shops")
async def list_all_shops():
    """List all configured shops with their phone numbers"""
    try:
        # Get shops from Supabase using unified service
        shops_data = await supabase_service.list_all_shops()
        
        # Get phone number mapping
        phone_map = json.loads(settings.PHONE_TO_LOCATION_MAP)
        
        shops = []
        for shop in shops_data:
            location_id = int(shop['id']) if shop['id'].isdigit() else shop['id']
            
            # Find phone number for this shop
            phone_number = next((phone for phone, loc_id in phone_map.items() if loc_id == location_id), None)
            
            # Get additional status info
            status = await get_location_status(location_id)
            knowledge = await knowledge_service.get_location_knowledge(location_id)
            
            shops.append({
                "location_id": location_id,
                "phone_number": phone_number,
                "business_name": shop.get('salon_name', f"Shop {location_id}"),
                "has_data": status.get("has_data", False),
                "data_age_days": status.get("data_age_days", None),
                "last_updated": knowledge.last_updated.isoformat() if knowledge else None,
                "timezone": shop.get('timezone', 'America/New_York')
            })
        
        return {"shops": shops, "total": len(shops)}
    except Exception as e:
        logging.error(f"Error listing shops: {e}")
        return {"error": str(e)}

# WebSocket endpoints for real-time frontend updates
@app.websocket("/ops")
async def ops_metrics_websocket(websocket: WebSocket):
    """WebSocket endpoint for real-time dashboard updates"""
    await websocket.accept()
    ops_ws_clients.add(websocket)
    logging.info(f"👀 Frontend dashboard connected. Total clients: {len(ops_ws_clients)}")
    
    try:
        # Send initial metrics snapshot
        snapshot = await _compute_salon_metrics()
        await websocket.send_json({"type": "metrics", "data": snapshot})
        
        # Keep connection alive and handle client messages
        while True:
            try:
                # Wait for client messages (ping/pong, etc.)
                await asyncio.sleep(30)
                await websocket.send_json({
                    "type": "keepalive", 
                    "timestamp": datetime.now().isoformat()
                })
            except WebSocketDisconnect:
                break
            except Exception as e:
                logging.warning(f"WebSocket error: {e}")
                break
    finally:
        ops_ws_clients.discard(websocket)
        logging.info(f"👋 Frontend dashboard disconnected. Remaining: {len(ops_ws_clients)}")

async def _compute_salon_metrics() -> Dict[str, Any]:
    """Compute real-time salon metrics for dashboard"""
    try:
        # Get active calls and recent activity
        active_calls = []
        recent_calls = []
        
        for call_sid, call_data in conversation_context.items():
            call_info = {
                "call_sid": call_sid,
                "location_id": call_data.get('location_id'),
                "caller_number": call_data.get('caller_number'),
                "to_number": call_data.get('to_number'),
                "message_count": len(call_data.get('messages', [])),
                "start_time": call_data.get('start_time', datetime.now().isoformat())
            }
            active_calls.append(call_info)
            recent_calls.append(call_info)
        
        # Get shop information
        shops_info = []
        try:
            phone_map = json.loads(settings.PHONE_TO_LOCATION_MAP)
            for phone_number, location_id in phone_map.items():
                knowledge = await knowledge_service.get_location_knowledge(location_id)
                shops_info.append({
                    "location_id": location_id,
                    "phone_number": phone_number,
                    "business_name": knowledge.business_name if knowledge else f"Location {location_id}",
                    "active_calls": len([c for c in active_calls if c['location_id'] == location_id])
                })
        except Exception as e:
            logging.warning(f"Error getting shops info: {e}")
        
        return {
            "timestamp": datetime.now().isoformat(),
            "active_calls": len(active_calls),
            "total_shops": len(shops_info),
            "shops": shops_info,
            "recent_calls": recent_calls[-20:],  # Last 20 calls
            "system_status": "operational"
        }
    except Exception as e:
        logging.error(f"Error computing salon metrics: {e}")
        return {
            "timestamp": datetime.now().isoformat(),
            "active_calls": 0,
            "total_shops": 0,
            "shops": [],
            "recent_calls": [],
            "system_status": "error",
            "error": str(e)
        }

async def _broadcast_to_dashboard(message_type: str, data: Dict[str, Any]):
    """Broadcast updates to all connected dashboard clients"""
    if not ops_ws_clients:
        return
    
    message = {"type": message_type, "data": data}
    disconnected_clients = []
    
    for client in list(ops_ws_clients):
        try:
            await client.send_json(message)
        except Exception as e:
            logging.warning(f"Failed to send to WebSocket client: {e}")
            disconnected_clients.append(client)
    
    # Clean up disconnected clients
    for client in disconnected_clients:
        ops_ws_clients.discard(client)
    
    if disconnected_clients:
        logging.info(f"🧹 Cleaned up {len(disconnected_clients)} disconnected clients")

@app.get("/metrics")
async def get_current_metrics():
    """REST endpoint for current salon metrics"""
    return await _compute_salon_metrics()

@app.get("/admin/platform-metrics")
async def get_platform_metrics():
    """Get platform-wide metrics for admin oversight"""
    try:
        metrics = await supabase_service.get_platform_metrics()
        return {
            "success": True,
            "metrics": metrics,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logging.error(f"Error getting platform metrics: {e}")
        return {"error": str(e)}

@app.get("/admin/shop/{shop_id}/metrics")
async def get_shop_metrics(shop_id: str, days: int = 30):
    """Get detailed metrics for a specific shop"""
    try:
        metrics = await supabase_service.get_shop_metrics(shop_id, days)
        calls_timeseries = await supabase_service.get_calls_timeseries(shop_id, days)
        
        return {
            "success": True,
            "shop_id": shop_id,
            "period_days": days,
            "metrics": metrics,
            "calls_timeseries": calls_timeseries,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logging.error(f"Error getting shop metrics for {shop_id}: {e}")
        return {"error": str(e)}

@app.get("/admin/shop/{shop_id}/services")
async def get_shop_services(shop_id: str):
    """Get services for a specific shop"""
    try:
        services = await supabase_service.get_shop_services(shop_id)
        return {
            "success": True,
            "shop_id": shop_id,
            "services": services,
            "count": len(services)
        }
    except Exception as e:
        logging.error(f"Error getting shop services for {shop_id}: {e}")
        return {"error": str(e)}

@app.post("/admin/shop/{shop_id}/appointment")
async def create_shop_appointment(
    shop_id: str,
    call_id: str = None,
    service_id: str = None,
    appointment_date: str = None,
    estimated_revenue_cents: int = 0
):
    """Create an appointment for a shop"""
    try:
        appointment_data = AppointmentData(
            salon_id=shop_id,
            call_id=call_id,
            service_id=service_id,
            appointment_date=appointment_date,
            estimated_revenue_cents=estimated_revenue_cents,
            status="scheduled"
        )
        
        result = await supabase_service.create_appointment(appointment_data)
        
        if result['success']:
            # Broadcast appointment creation to dashboard
            await _broadcast_to_dashboard("appointment_created", {
                "shop_id": shop_id,
                "appointment_id": result['appointment_id'],
                "call_id": call_id,
                "estimated_revenue_cents": estimated_revenue_cents,
                "timestamp": datetime.now().isoformat()
            })
        
        return result
    except Exception as e:
        logging.error(f"Error creating appointment for shop {shop_id}: {e}")
        return {"error": str(e)}


# Basic logging setup
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)


if __name__ == "__main__":
    import uvicorn
    import os
    
    # For Heroku deployment
    port = int(os.environ.get("PORT", 5001))
    host = "0.0.0.0"
    
    uvicorn.run(
        "ops_integrations.services.salon_phone_service:app", 
        host=host, 
        port=port, 
        reload=False  # Disable reload in production
    )