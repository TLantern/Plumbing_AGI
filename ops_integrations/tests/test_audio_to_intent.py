#!/usr/bin/env python3
"""
Test Complete Audio-to-Intent Pipeline
Audio → Whisper ASR → GPT-4 Intent Extraction
"""
import asyncio
import json
import sys
import os
import wave
import io
from dotenv import load_dotenv
from openai import OpenAI
import tempfile

# Add parent directory to path to import adapters
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

load_dotenv('../../.env')

# Test cases with simulated audio scenarios
AUDIO_TEST_CASES = [
    {
        "name": "leaky_faucet",
        "text": "Hi, I have a leaky faucet in my kitchen that's been dripping for days. My name is John Smith and I'm at 123 Main Street. I need this fixed as soon as possible.",
        "expected": {
            "job_type": "leak",
            "urgency": "same_day",
            "customer_name": "John Smith",
            "address": "123 Main Street"
        }
    },
    {
        "name": "water_heater_emergency",
        "text": "Emergency! My water heater just burst and there's water everywhere. This is Sarah Johnson at 456 Oak Avenue. Please send someone immediately!",
        "expected": {
            "job_type": "water_heater",
            "urgency": "emergency", 
            "customer_name": "Sarah Johnson",
            "address": "456 Oak Avenue"
        }
    },
    {
        "name": "clogged_toilet",
        "text": "My toilet is clogged and won't flush. I'm Mike Davis, 789 Pine Road. Can someone come by tomorrow?",
        "expected": {
            "job_type": "clog",
            "urgency": "flex",
            "customer_name": "Mike Davis", 
            "address": "789 Pine Road"
        }
    },
    {
        "name": "gas_line_inspection",
        "text": "I need a gas line inspection. My name is Lisa Chen, 321 Elm Street. When can you schedule this?",
        "expected": {
            "job_type": "gas_line",
            "urgency": "flex",
            "customer_name": "Lisa Chen",
            "address": "321 Elm Street"
        }
    },
    {
        "name": "sewer_camera",
        "text": "There's a weird smell coming from my drains. I think I need a sewer camera inspection. I'm at 654 Maple Drive.",
        "expected": {
            "job_type": "sewer_cam",
            "urgency": "same_day",
            "customer_name": None,
            "address": "654 Maple Drive"
        }
    }
]

def create_test_audio_with_tts(text: str, filename: str) -> str:
    """Create test audio using OpenAI 4o TTS"""
    print(f"🔊 Generating OpenAI 4o TTS audio for: '{text[:50]}...'")
    
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    
    try:
        # Generate speech using OpenAI TTS
        response = client.audio.speech.create(
            model="tts-1",
            voice="alloy",
            input=text
        )
        
        # Get the current script directory
        current_dir = os.path.dirname(os.path.abspath(__file__))
        audio_path = os.path.join(current_dir, filename)
        
        # Save the audio file
        with open(audio_path, "wb") as f:
            f.write(response.content)
        
        print(f"✅ Audio saved to: {audio_path}")
        return audio_path
        
    except Exception as e:
        print(f"❌ OpenAI 4o TTS generation failed: {e}")
        return None

def create_silent_audio(filename: str, duration_seconds: int = 5) -> str:
    """Create silent audio as fallback"""
    sample_rate = 16000
    samples = duration_seconds * sample_rate
    audio_data = b'\x00' * (samples * 2)  # 16-bit samples
    
    with wave.open(filename, 'wb') as wav_file:
        wav_file.setnchannels(1)  # Mono
        wav_file.setsampwidth(2)  # 16-bit
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(audio_data)
    
    print(f"📁 Created silent audio: {filename}")
    return filename

async def transcribe_audio(audio_file: str) -> str:
    """Transcribe audio using Whisper"""
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    
    try:
        with open(audio_file, 'rb') as f:
            transcript = client.audio.transcriptions.create(
                model="whisper-1",
                file=f,
                response_format="text"
            )
        
        return transcript.strip()
        
    except Exception as e:
        print(f"❌ Whisper transcription failed: {e}")
        return ""

async def extract_intent_from_text(text: str) -> dict:
    """Extract intent from transcribed text"""
    from adapters.phone import extract_intent_from_text
    
    try:
        result = await extract_intent_from_text(text)
        return result
    except Exception as e:
        print(f"❌ Intent extraction failed: {e}")
        return {}

def calculate_pipeline_accuracy(result: dict, expected: dict) -> float:
    """Calculate accuracy of the complete pipeline"""
    score = 0.0
    total_fields = 0
    
    # Check job type
    actual_type = result.get('job', {}).get('type')
    expected_type = expected.get('job_type')
    if actual_type == expected_type:
        score += 1.0
    total_fields += 1
    
    # Check urgency
    actual_urgency = result.get('job', {}).get('urgency')
    expected_urgency = expected.get('urgency')
    if actual_urgency == expected_urgency:
        score += 1.0
    total_fields += 1
    
    # Check customer name
    actual_name = result.get('customer', {}).get('name')
    expected_name = expected.get('customer_name')
    if actual_name and expected_name and actual_name.lower() in expected_name.lower():
        score += 1.0
    elif not expected_name and not actual_name:
        score += 1.0
    total_fields += 1
    
    # Check address
    actual_addr = result.get('location', {}).get('raw_address', '') or ''
    expected_addr = expected.get('address', '') or ''
    if actual_addr and expected_addr and any(word in actual_addr.lower() for word in expected_addr.lower().split()):
        score += 1.0
    total_fields += 1
    
    return score / total_fields if total_fields > 0 else 0.0

async def test_audio_to_intent_pipeline():
    """Test the complete audio-to-intent pipeline"""
    print("🎵 Testing Complete Audio-to-Intent Pipeline")
    print("=" * 70)
    print("Pipeline: Audio → Whisper ASR → GPT-4 Intent Extraction")
    print("=" * 70)
    
    total_tests = len(AUDIO_TEST_CASES)
    passed_tests = 0
    accuracy_scores = []
    transcription_accuracy = []
    
    for i, test_case in enumerate(AUDIO_TEST_CASES, 1):
        print(f"\n🎤 Test {i}/{total_tests}: {test_case['name']}")
        print(f"Expected text: '{test_case['text']}'")
        
        # Step 1: Generate audio
        audio_file = f"test_audio_{test_case['name']}.wav"
        try:
            create_test_audio_with_tts(test_case['text'], audio_file)
            
            # Step 2: Transcribe audio with Whisper
            print("🔄 Transcribing with Whisper...")
            transcribed_text = await transcribe_audio(audio_file)
            print(f"📝 Transcribed: '{transcribed_text}'")
            
            # Calculate transcription accuracy
            trans_accuracy = calculate_transcription_accuracy(transcribed_text, test_case['text'])
            transcription_accuracy.append(trans_accuracy)
            print(f"📊 Transcription accuracy: {trans_accuracy:.2%}")
            
            # Step 3: Extract intent from transcribed text
            print("🤖 Extracting intent with GPT-4...")
            intent_result = await extract_intent_from_text(transcribed_text)
            print(f"🎯 Intent result: {json.dumps(intent_result, indent=2)}")
            
            # Step 4: Calculate pipeline accuracy
            pipeline_accuracy = calculate_pipeline_accuracy(intent_result, test_case['expected'])
            accuracy_scores.append(pipeline_accuracy)
            print(f"🎯 Pipeline accuracy: {pipeline_accuracy:.2%}")
            
            if pipeline_accuracy >= 0.75:
                passed_tests += 1
                print("✅ PASS")
            else:
                print("❌ FAIL")
                
        except Exception as e:
            print(f"❌ Test failed: {e}")
            accuracy_scores.append(0.0)
            transcription_accuracy.append(0.0)
        
        finally:
            # Cleanup audio file
            if os.path.exists(audio_file):
                os.remove(audio_file)
    
    # Summary
    print(f"\n📊 PIPELINE SUMMARY")
    print("=" * 70)
    print(f"Total Tests: {total_tests}")
    print(f"Passed: {passed_tests}")
    print(f"Failed: {total_tests - passed_tests}")
    print(f"Success Rate: {passed_tests/total_tests:.2%}")
    print(f"Average Pipeline Accuracy: {sum(accuracy_scores)/len(accuracy_scores):.2%}")
    print(f"Average Transcription Accuracy: {sum(transcription_accuracy)/len(transcription_accuracy):.2%}")
    
    return {
        "success_rate": passed_tests/total_tests,
        "pipeline_accuracy": sum(accuracy_scores)/len(accuracy_scores),
        "transcription_accuracy": sum(transcription_accuracy)/len(transcription_accuracy),
        "passed_tests": passed_tests,
        "total_tests": total_tests
    }

def calculate_transcription_accuracy(actual: str, expected: str) -> float:
    """Calculate transcription accuracy using word matching"""
    if not actual or not expected:
        return 0.0
    
    actual_words = set(actual.lower().split())
    expected_words = set(expected.lower().split())
    
    if not expected_words:
        return 0.0
    
    intersection = actual_words.intersection(expected_words)
    return len(intersection) / len(expected_words)

async def test_real_audio_files():
    """Test with real audio files if available"""
    print(f"\n🎵 Testing with Real Audio Files")
    print("=" * 70)
    
    test_audio_dir = "test_audio"
    if os.path.exists(test_audio_dir):
        audio_files = [f for f in os.listdir(test_audio_dir) if f.endswith(('.wav', '.mp3', '.m4a'))]
        
        if audio_files:
            print(f"Found {len(audio_files)} real audio files:")
            for audio_file in audio_files[:3]:  # Test first 3 files
                print(f"\n🎤 Processing: {audio_file}")
                audio_path = os.path.join(test_audio_dir, audio_file)
                
                try:
                    # Transcribe
                    transcribed_text = await transcribe_audio(audio_path)
                    print(f"📝 Transcribed: '{transcribed_text}'")
                    
                    # Extract intent
                    if transcribed_text:
                        intent_result = await extract_intent_from_text(transcribed_text)
                        print(f"🎯 Intent: {json.dumps(intent_result, indent=2)}")
                    
                except Exception as e:
                    print(f"❌ Error processing {audio_file}: {e}")
        else:
            print("No audio files found in test_audio directory")
    else:
        print("No test_audio directory found")
        print("To test real audio files:")
        print("1. Create 'test_audio' directory")
        print("2. Add WAV/MP3 files with plumbing requests")
        print("3. Run this test again")

async def main():
    """Run all audio-to-intent tests"""
    try:
        # Test TTS generated audio
        results = await test_audio_to_intent_pipeline()
        
        # Test real audio files if available
        await test_real_audio_files()
        
        print(f"\n🎉 Audio-to-Intent test suite completed!")
        print(f"Final Results:")
        print(f"  - Success Rate: {results['success_rate']:.2%}")
        print(f"  - Pipeline Accuracy: {results['pipeline_accuracy']:.2%}")
        print(f"  - Transcription Accuracy: {results['transcription_accuracy']:.2%}")
        
    except Exception as e:
        print(f"❌ Test suite failed: {e}")

if __name__ == "__main__":
    asyncio.run(main()) 