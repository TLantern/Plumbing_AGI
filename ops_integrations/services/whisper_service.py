#!/usr/bin/env python3
"""
Standalone Whisper Transcription Service
Run this on a separate server (preferably with GPU) for fast transcription.
"""

import asyncio
import uvicorn
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import torch
import numpy as np
import io
import wave
import logging
import time
from pydantic import BaseModel
from typing import Optional

try:
    import whisper
    WHISPER_AVAILABLE = True
except ImportError:
    WHISPER_AVAILABLE = False
    whisper = None

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("whisper-service")

# Configuration
WHISPER_MODEL = "large-v3"  # Use best model on dedicated server
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
HOST = "0.0.0.0"
PORT = 8081

# Global model instance
model = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for FastAPI."""
    # Startup
    global model
    if not WHISPER_AVAILABLE:
        logger.error("Whisper not available - service will not function properly")
        model = None
    else:
        logger.info(f"Loading Whisper model '{WHISPER_MODEL}' on device '{DEVICE}'...")
        start_time = time.time()
        try:
            model = whisper.load_model(WHISPER_MODEL, device=DEVICE)
            load_time = time.time() - start_time
            logger.info(f"Whisper model loaded in {load_time:.2f}s")
            
            # Test transcription to warm up
            logger.info("Warming up model with test audio...")
            test_audio = np.zeros(16000, dtype=np.float32)  # 1 second of silence
            try:
                model.transcribe(test_audio, language="en", fp16=DEVICE=="cuda")
                logger.info("Model warmed up successfully")
            except Exception as e:
                logger.warning(f"Model warmup failed: {e}")
        except Exception as e:
            logger.error(f"Failed to load Whisper model: {e}")
            model = None
    
    yield
    
    # Shutdown
    logger.info("Shutting down Whisper service...")

app = FastAPI(title="Whisper Transcription Service", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class TranscriptionRequest(BaseModel):
    audio_base64: str
    sample_rate: int = 16000
    language: str = "en"

class TranscriptionResponse(BaseModel):
    text: str
    language: str
    duration: float
    transcription_time: float
    model: str
    device: str



@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy" if WHISPER_AVAILABLE and model is not None else "degraded",
        "whisper_available": WHISPER_AVAILABLE,
        "model": WHISPER_MODEL if WHISPER_AVAILABLE else None,
        "device": DEVICE,
        "cuda_available": torch.cuda.is_available()
    }

@app.post("/transcribe", response_model=TranscriptionResponse)
async def transcribe_audio(request: TranscriptionRequest):
    """Transcribe audio from base64 encoded data."""
    global model
    
    if model is None:
        raise HTTPException(status_code=503, detail="Model not loaded")
    
    try:
        # Decode base64 audio
        import base64
        audio_bytes = base64.b64decode(request.audio_base64)
        
        # Convert to numpy array
        audio_array = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32768.0
        
        # Resample if needed
        if request.sample_rate != 16000:
            from scipy import signal
            samples = len(audio_array)
            new_samples = int(samples * 16000 / request.sample_rate)
            audio_array = signal.resample(audio_array, new_samples).astype(np.float32)
        
        start_time = time.time()
        
        # Transcribe
        result = model.transcribe(
            audio_array,
            language=request.language,
            fp16=DEVICE=="cuda",
            verbose=False
        )
        
        transcription_time = time.time() - start_time
        audio_duration = len(audio_array) / 16000
        
        logger.info(f"Transcribed {audio_duration:.2f}s audio in {transcription_time:.2f}s")
        
        return TranscriptionResponse(
            text=result["text"],
            language=result["language"],
            duration=audio_duration,
            transcription_time=transcription_time,
            model=WHISPER_MODEL,
            device=DEVICE
        )
        
    except Exception as e:
        logger.error(f"Transcription failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/transcribe/file")
async def transcribe_file(file: UploadFile = File(...)):
    """Transcribe audio from uploaded file."""
    global model
    
    if model is None:
        raise HTTPException(status_code=503, detail="Model not loaded")
    
    try:
        # Read file
        audio_bytes = await file.read()
        
        # Handle WAV files
        if file.filename.endswith('.wav'):
            wav_io = io.BytesIO(audio_bytes)
            with wave.open(wav_io, 'rb') as wav_file:
                sample_rate = wav_file.getframerate()
                pcm_data = wav_file.readframes(wav_file.getnframes())
                audio_array = np.frombuffer(pcm_data, dtype=np.int16).astype(np.float32) / 32768.0
        else:
            # For other formats, assume PCM16
            audio_array = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32768.0
            sample_rate = 16000
        
        # Resample if needed
        if sample_rate != 16000:
            from scipy import signal
            samples = len(audio_array)
            new_samples = int(samples * 16000 / sample_rate)
            audio_array = signal.resample(audio_array, new_samples).astype(np.float32)
        
        start_time = time.time()
        
        # Transcribe
        result = model.transcribe(
            audio_array,
            language="en",
            fp16=DEVICE=="cuda",
            verbose=False
        )
        
        transcription_time = time.time() - start_time
        audio_duration = len(audio_array) / 16000
        
        logger.info(f"Transcribed {audio_duration:.2f}s audio in {transcription_time:.2f}s")
        
        return TranscriptionResponse(
            text=result["text"],
            language=result["language"],
            duration=audio_duration,
            transcription_time=transcription_time,
            model=WHISPER_MODEL,
            device=DEVICE
        )
        
    except Exception as e:
        logger.error(f"File transcription failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    logger.info(f"Starting Whisper Service on {HOST}:{PORT}")
    logger.info(f"Model: {WHISPER_MODEL}, Device: {DEVICE}")
    uvicorn.run(app, host=HOST, port=PORT) 