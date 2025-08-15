#!/usr/bin/env python3
"""
Simple test script to verify remote Whisper transcription
"""
import asyncio
import base64
import httpx
import json
import os
from pathlib import Path

# Configuration
REMOTE_WHISPER_URL = "https://8224a1a4accc.ngrok-free.app"

async def test_remote_whisper():
    """Test remote Whisper transcription with a simple audio file"""
    
    # Create a simple test audio file (1 second of silence)
    test_audio_path = "test_audio.wav"
    
    # Create a minimal WAV file (1 second of silence at 16kHz)
    sample_rate = 16000
    duration_seconds = 1
    num_samples = sample_rate * duration_seconds
    
    # Create 16-bit PCM silence
    import struct
    audio_data = struct.pack('<%dh' % num_samples, *([0] * num_samples))
    
    # Create WAV header
    wav_header = struct.pack('<4sI4s4sIHHIIHH4sI',
        b'RIFF',
        36 + len(audio_data),
        b'WAVE',
        b'fmt ',
        16,  # fmt chunk size
        1,   # PCM format
        1,   # mono
        sample_rate,
        sample_rate * 2,  # byte rate
        2,   # block align
        16,  # bits per sample
        b'data',
        len(audio_data)
    )
    
    # Write WAV file
    with open(test_audio_path, 'wb') as f:
        f.write(wav_header)
        f.write(audio_data)
    
    print(f"Created test audio file: {test_audio_path}")
    
    try:
        # Read the audio file and encode as base64
        with open(test_audio_path, 'rb') as f:
            audio_bytes = f.read()
        
        audio_base64 = base64.b64encode(audio_bytes).decode('utf-8')
        
        print(f"Audio file size: {len(audio_bytes)} bytes")
        print(f"Base64 encoded size: {len(audio_base64)} characters")
        
        # Test remote Whisper service
        print(f"\nTesting remote Whisper at: {REMOTE_WHISPER_URL}")
        
        async with httpx.AsyncClient(timeout=30.0) as http_client:
            response = await http_client.post(
                f"{REMOTE_WHISPER_URL}/transcribe",
                json={
                    "audio_base64": audio_base64,
                    "sample_rate": 16000,
                    "language": "en"
                }
            )
            
            print(f"Response status: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                print(f"Transcription result: {json.dumps(result, indent=2)}")
                print("✅ Remote Whisper is working!")
            else:
                print(f"❌ Remote Whisper failed: {response.text}")
                
    except Exception as e:
        print(f"❌ Error testing remote Whisper: {e}")
    
    finally:
        # Clean up test file
        if os.path.exists(test_audio_path):
            os.remove(test_audio_path)
            print(f"Cleaned up: {test_audio_path}")

async def test_health_endpoint():
    """Test the health endpoint of the remote Whisper service"""
    
    try:
        print(f"\nTesting health endpoint at: {REMOTE_WHISPER_URL}/health")
        
        async with httpx.AsyncClient(timeout=10.0) as http_client:
            response = await http_client.get(f"{REMOTE_WHISPER_URL}/health")
            
            print(f"Health check status: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                print(f"Health check result: {json.dumps(result, indent=2)}")
                print("✅ Remote Whisper health check passed!")
            else:
                print(f"❌ Health check failed: {response.text}")
                
    except Exception as e:
        print(f"❌ Error testing health endpoint: {e}")

if __name__ == "__main__":
    print("🔍 Testing Remote Whisper Service")
    print("=" * 50)
    
    asyncio.run(test_health_endpoint())
    asyncio.run(test_remote_whisper()) 