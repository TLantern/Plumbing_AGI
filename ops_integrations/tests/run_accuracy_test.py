#!/usr/bin/env python3
"""
Audio Processing Accuracy Test Runner

This script tests our audio processing pipeline against the target transcription
and iteratively tunes parameters to achieve 95% accuracy.
"""

import asyncio
import logging
import os
import sys
from pathlib import Path
import getpass

# Import our test modules
sys.path.append(str(Path(__file__).parent))
from audio_accuracy_test import AudioAccuracyTester

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def get_api_key():
    """Get OpenAI API key from user"""
    # Use the provided API key
    api_key = "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"
    
    if not api_key:
        print("❌ No API key provided. Exiting.")
        sys.exit(1)
    
    return api_key

async def run_accuracy_test():
    """Run the accuracy test with proper setup"""
    
    print("🎯 Audio Processing Accuracy Test")
    print("=" * 50)
    
    # Get API key
    api_key = get_api_key()
    
    # Set up file paths
    current_dir = Path(__file__).parent
    video_dir = current_dir.parent / "video"
    mp3_path = str(video_dir / "30 Second Elevator Speech.mp3")
    transcription_path = str(video_dir / "transcription.txt")
    
    # Check if files exist
    if not os.path.exists(mp3_path):
        print(f"❌ MP3 file not found: {mp3_path}")
        return
    
    if not os.path.exists(transcription_path):
        print(f"❌ Transcription file not found: {transcription_path}")
        return
    
    print(f"📁 Audio file: {mp3_path}")
    print(f"📄 Target transcription: {transcription_path}")
    print()
    
    # Initialize tester
    print("🚀 Initializing audio processor...")
    tester = AudioAccuracyTester(api_key)
    
    try:
        # Run the test
        print("🔍 Running accuracy test...")
        accuracy = await tester.run_accuracy_test(mp3_path, transcription_path)
        
        print(f"\n📊 RESULTS")
        print("=" * 30)
        print(f"Accuracy: {accuracy:.2f}%")
        
        if accuracy >= 95.0:
            print("🎉 TARGET ACHIEVED! Accuracy >= 95%")
            print("✅ Audio processing pipeline is ready for production!")
        else:
            print(f"📈 Target not reached. Need {95.0 - accuracy:.2f}% more accuracy.")
            print("\n🔧 TUNING SUGGESTIONS:")
            print("-" * 40)
            
            if accuracy < 70:
                print("• Major tuning needed:")
                print("  - Check audio quality and format")
                print("  - Verify Whisper model selection")
                print("  - Review confidence thresholds")
            elif accuracy < 85:
                print("• Moderate tuning needed:")
                print("  - Adjust transcription_confidence_threshold (try -0.8)")
                print("  - Reduce min_speech_duration_sec (try 0.3)")
                print("  - Lower energy_threshold_rms (try 40)")
            elif accuracy < 95:
                print("• Fine tuning needed:")
                print("  - Fine-tune VAD aggressiveness (try 1)")
                print("  - Adjust silence_timeout_sec (try 1.5)")
                print("  - Optimize chunk_duration_sec (try 1.5)")
            
            print("\n💡 To implement changes:")
            print("1. Edit test_audio_processing.py with new parameters")
            print("2. Run this test again")
            print("3. Repeat until 95% accuracy is achieved")
            
    except Exception as e:
        print(f"❌ Test failed: {e}")
        logger.exception("Test execution failed")
    
    print("\n🏁 Test completed.")

if __name__ == "__main__":
    asyncio.run(run_accuracy_test()) 