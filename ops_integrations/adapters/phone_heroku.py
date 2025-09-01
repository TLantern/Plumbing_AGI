"""
Simplified Phone Service for Heroku Deployment
This version removes heavy ML dependencies to stay within Heroku's slug size limits.
"""

import os
import logging
from datetime import datetime
from typing import Optional
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseSettings, SettingsConfigDict
from twilio.rest import Client
from twilio.twiml import VoiceResponse
import json

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")
    TWILIO_ACCOUNT_SID: str
    TWILIO_AUTH_TOKEN: str
    TWILIO_FROM_NUMBER: Optional[str] = None
    OPENAI_API_KEY: Optional[str] = None
    ELEVENLABS_API_KEY: Optional[str] = None
    ELEVENLABS_VOICE_ID: str = "kdmDKE6EkgrWrrykO9Qt"
    EXTERNAL_WEBHOOK_URL: str = "https://salonphone.herokuapp.com"
    SERVER_HOST: str = "0.0.0.0"
    SERVER_PORT: int = 5001

settings = Settings()

# Initialize Twilio client
twilio_client: Optional[Client] = None
try:
    if settings.TWILIO_ACCOUNT_SID and settings.TWILIO_AUTH_TOKEN:
        twilio_client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
        logger.info("Twilio client initialized successfully")
    else:
        logger.warning("Twilio disabled: missing credentials")
except Exception as e:
    logger.error(f"Twilio client init failed: {e}")
    twilio_client = None

# FastAPI app
app = FastAPI(title="Salon Phone Service - Heroku")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy", 
        "timestamp": datetime.now().isoformat(),
        "service": "salon-phone-heroku",
        "twilio_configured": twilio_client is not None
    }

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Salon Phone Service - Heroku",
        "status": "running",
        "endpoints": {
            "health": "/health",
            "voice": "/voice",
            "webhook": "/webhook"
        }
    }

@app.post("/voice")
async def voice_webhook(request: Request):
    """Handle incoming voice calls from Twilio"""
    try:
        # Get form data from Twilio
        form_data = await request.form()
        call_sid = form_data.get("CallSid")
        from_number = form_data.get("From")
        to_number = form_data.get("To")
        
        logger.info(f"Received call from {from_number} to {to_number} (SID: {call_sid})")
        
        # Create TwiML response
        response = VoiceResponse()
        
        # Add a simple greeting
        response.say(
            "Thank you for calling Bold Wings Salon. We're currently setting up our automated booking system. Please call back later or visit our website to book an appointment.",
            voice="alice"
        )
        
        # Log the call
        if twilio_client:
            try:
                # You could log call details to a database here
                logger.info(f"Call logged: {call_sid} from {from_number}")
            except Exception as e:
                logger.error(f"Failed to log call: {e}")
        
        return response
        
    except Exception as e:
        logger.error(f"Error in voice webhook: {e}")
        response = VoiceResponse()
        response.say("We're experiencing technical difficulties. Please try again later.", voice="alice")
        return response

@app.post("/webhook")
async def general_webhook(request: Request):
    """General webhook endpoint for testing"""
    try:
        body = await request.body()
        logger.info(f"Received webhook: {body}")
        return {"status": "received", "timestamp": datetime.now().isoformat()}
    except Exception as e:
        logger.error(f"Error in webhook: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/config")
async def get_config():
    """Get current configuration (without sensitive data)"""
    return {
        "twilio_configured": twilio_client is not None,
        "openai_configured": bool(settings.OPENAI_API_KEY),
        "elevenlabs_configured": bool(settings.ELEVENLABS_API_KEY),
        "external_url": settings.EXTERNAL_WEBHOOK_URL,
        "voice_id": settings.ELEVENLABS_VOICE_ID
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "phone_heroku:app",
        host=settings.SERVER_HOST,
        port=int(os.getenv("PORT", settings.SERVER_PORT)),
        log_level="info"
    )
