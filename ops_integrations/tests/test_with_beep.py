#!/usr/bin/env python3
"""
Test remote Whisper with the existing beep.wav file
"""
import asyncio
import base64
import httpx
import json
import os

# Configuration
REMOTE_WHISPER_URL = "https://ee7689bd1c73.ngrok-free.app"
BEEP_AUDIO_PATH = "adapters/static/beep.wav"

async def test_transcription_with_beep():
    """Test transcription with the beep.wav file"""
    
    if not os.path.exists(BEEP_AUDIO_PATH):
        print(f"❌ Beep audio file not found: {BEEP_AUDIO_PATH}")
        return
    
    try:
        # Read the audio file and encode as base64
        with open(BEEP_AUDIO_PATH, 'rb') as f:
            audio_bytes = f.read()
        
        audio_base64 = base64.b64encode(audio_bytes).decode('utf-8')
        
        print(f"Audio file: {BEEP_AUDIO_PATH}")
        print(f"Audio file size: {len(audio_bytes)} bytes")
        print(f"Base64 encoded size: {len(audio_base64)} characters")
        
        # Test remote Whisper service
        print(f"\nTesting transcription with beep audio...")
        
        async with httpx.AsyncClient(timeout=30.0) as http_client:
            response = await http_client.post(
                f"{REMOTE_WHISPER_URL}/transcribe",
                json={
                    "audio_base64": audio_base64,
                    "sample_rate": 8000,  # Beep is likely 8kHz
                    "language": "en"
                }
            )
            
            print(f"Response status: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                print(f"Transcription result: {json.dumps(result, indent=2)}")
                print("✅ Transcription completed!")
            else:
                print(f"❌ Transcription failed: {response.text}")
                
    except Exception as e:
        print(f"❌ Error testing transcription: {e}")

if __name__ == "__main__":
    print("🔍 Testing Remote Whisper with Beep Audio")
    print("=" * 50)
    
    asyncio.run(test_transcription_with_beep()) 