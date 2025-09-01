#!/usr/bin/env python3
"""
Test remote Whisper with a real audio file
"""
import asyncio
import base64
import httpx
import json
import os
import wave
import numpy as np

# Configuration
REMOTE_WHISPER_URL = "https://ee7689bd1c73.ngrok-free.app"

def create_test_audio_with_speech():
    """Create a test audio file with some speech-like content"""
    
    # Create a simple sine wave that sounds like speech
    sample_rate = 16000
    duration_seconds = 3
    num_samples = sample_rate * duration_seconds
    
    # Create a frequency-modulated sine wave to simulate speech
    t = np.linspace(0, duration_seconds, num_samples)
    
    # Create a simple tone that varies in frequency (like speech)
    frequency = 200 + 100 * np.sin(2 * np.pi * 0.5 * t)  # Varying frequency
    audio_data = np.sin(2 * np.pi * frequency * t) * 0.3  # Amplitude 0.3
    
    # Convert to 16-bit PCM
    audio_int16 = (audio_data * 32767).astype(np.int16)
    
    # Create WAV file
    test_audio_path = "test_speech.wav"
    
    with wave.open(test_audio_path, 'wb') as wav_file:
        wav_file.setnchannels(1)  # Mono
        wav_file.setsampwidth(2)  # 16-bit
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(audio_int16.tobytes())
    
    print(f"Created test speech audio file: {test_audio_path}")
    return test_audio_path

async def test_transcription_with_speech():
    """Test transcription with speech-like audio"""
    
    test_audio_path = create_test_audio_with_speech()
    
    try:
        # Read the audio file and encode as base64
        with open(test_audio_path, 'rb') as f:
            audio_bytes = f.read()
        
        audio_base64 = base64.b64encode(audio_bytes).decode('utf-8')
        
        print(f"Audio file size: {len(audio_bytes)} bytes")
        print(f"Base64 encoded size: {len(audio_base64)} characters")
        
        # Test remote Whisper service
        print(f"\nTesting transcription with speech-like audio...")
        
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
                print("✅ Transcription completed!")
            else:
                print(f"❌ Transcription failed: {response.text}")
                
    except Exception as e:
        print(f"❌ Error testing transcription: {e}")
    
    finally:
        # Clean up test file
        if os.path.exists(test_audio_path):
            os.remove(test_audio_path)
            print(f"Cleaned up: {test_audio_path}")

if __name__ == "__main__":
    print("🔍 Testing Remote Whisper with Speech Audio")
    print("=" * 50)
    
    asyncio.run(test_transcription_with_speech()) 