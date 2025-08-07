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
from flask import json
from pydantic_settings import BaseSettings
from twilio import twiml
from twilio.rest import Client
from twilio.twiml.voice_response import VoiceResponse, Start
import io
import wave
from openai import OpenAI
from collections import defaultdict
from .plumbing_services import get_function_definition, infer_job_type_from_text, infer_multiple_job_types_from_text
from ops_integrations.job_booking import book_emergency_job, book_scheduled_job
from datetime import datetime, timedelta

#---------------CONFIGURATION---------------
class Settings(BaseSettings):
    TWILIO_ACCOUNT_SID: str 
    TWILIO_AUTH_TOKEN: str
    SERVER_HOST: str = "0.0.0.0"
    SERVER_PORT: int = 8000
    SSL_CERT_FILE: Optional[str] = None
    SSL_KEY_PATH: Optional[str] = None
    STREAM_ENDPOINT: str = "/stream"
    VOICE_ENDPOINT: str = "/voice"
    LOG_LEVEL: str = "INFO"
    class Config:
       load_dotenv()

settings = Settings()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
WHISPER_MODEL = "whisper-1"
#Collect ~5s of audio (16kHz mono PCM) per chunk
CHUNK_DURATION_SEC = 5
SAMPLE_RATE = 16000
SAMPLE_WIDTH = 2 #bytes (16-bit)
#buffer incoming PCM per call
audio_buffers = defaultdict(bytearray)
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
)

twilio_client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)

#---------------VOICE WEBHOOK---------------
@app.post(settings.VOICE_ENDPOINT)
async def voice_webhook(request: Request):
    form = await request.form()
    call_sid = form.get("CallSid")
    if not call_sid:
        logger.error("Missing CallSid in webhook payload")
        raise HTTPException(status_code=400, detail="CallSid required")

    #Build TwiML Response
    resp = VoiceResponse()
    start = Start()
    wss_url = f"wss://{request.client.host}:{settings.SERVER_PORT}{settings.STREAM_ENDPOINT}?callSid={call_sid}"
    start.stream(url=wss_url, track="inbound_track")
    resp.append(start)
    resp.say("Hello, Welcome to SafeHarbour Plumbing. How can we help you with your plumbing needs today?")
    resp.pause(length=3600)
    logger.info(f"started media stream for call {call_sid}")
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
async def media_stream(ws: WebSocket, callSid: str):
    if not callSid:
        await ws.close(code=1008)
        return
    await manager.connect(callSid, ws)
    await manager.receive_loop(callSid)

#---------------MEDIA PROCESSING---------------
async def handle_media_packet(call_sid: str, msg: str):
    try:
        packet = json.loads(msg)
    except Exception as e:
        logger.error(f"Invalid JSON in media packet for CallSid={call_sid}: {e}")
        return

    event = packet.get("event")
    if event == "start":
        logger.debug(f"Stream Started: {packet}")
    elif event == "media":
        payload_b64 = packet["media"]["payload"]
        audio_bytes = base64.b64decode(payload_b64)
        # TODO: Send to ASR/Intent Engine
        await process_audio(call_sid, audio_bytes)
    elif event == "stop":
        logger.debug(f"Stream Stopped: {call_sid}")
    else:
        logger.warning(f"Unknown event: '{event}' for CallSid={call_sid}")

#---------------ASR/INTENT & FOLLOW-UPS (STUBS) ---------------
FUNCTIONS = [get_function_definition()]

async def process_audio(call_sid: str, audio: bytes):
    buf =  audio_buffers[call_sid]
    buf.extend(audio)

    # once we have ~CHUNK_DURATION_SEC seconds, send to Whisper
    if len(buf) >= SAMPLE_RATE * CHUNK_DURATION_SEC:
        wav_bytes = pcm_to_wav_bytes(bytes(buf))
        audio_buffers[call_sid].clear()

        try:
            resp = client.audio.transcriptions.create(
                model=WHISPER_MODEL,
                file=io.BytesIO(wav_bytes),
                response_format="json",
                language="en",
            )
        except Exception as e:
            logger.error(f"Whisper ASR error for {call_sid}: {e}")
            return

        text = resp.text.strip()
        logger.debug(f'ASR ({call_sid}): "{text}"')
        # now feed into NLU/intent extractor
        intent = await extract_intent_from_text(text)
        await handle_intent(call_sid, intent)

async def extract_intent_from_text(text:str) -> dict:
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

async def handle_intent(call_sid: str, intent: dict):
    twiml = VoiceResponse()
    job_type = intent.get('job', {}).get('type', 'a plumbing issue')
    urgency = intent.get('job', {}).get('urgency', 'flex')
    customer = intent.get('customer', {})
    customer_name = customer.get('name', 'Customer')
    customer_phone = customer.get('phone', None)
    address = intent.get('location', {}).get('raw_address', '')
    notes = intent.get('job', {}).get('description', '')

    if urgency == 'emergency':
        # Book the next available slot for emergency
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
            twiml.say(f"This is an emergency. We'll send the best available technician for {job_type} at the next available slot: {appointment_time}.")
        except Exception as e:
            logger.error(f"Emergency booking failed: {e}")
            twiml.say("We're having trouble booking the next available technician. Please hold while we connect you to a human agent.")
    else:
        # Not an emergency: ask for preferred time
        twiml.say(f"Would you like to schedule a plumber for your {job_type}? Please state your preferred date and time.")
        # In a real system, you'd capture the user's response and check availability
        # For now, this is a placeholder for follow-up logic

    logger.info(f"Handled intent {intent} for CallSid={call_sid}")

#---------------AUDIO PROCESSING---------------
def pcm_to_wav_bytes(pcm: bytes) -> bytes:
    """Wrap raw PCM into a WAV container for Whisper."""
    buf = io.BytesIO()
    with wave.open(buf,"wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(SAMPLE_WIDTH)
        wf.setframerate(SAMPLE_RATE)
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