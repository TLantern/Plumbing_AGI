#!/usr/bin/env python3
"""
Audio Processing Test Starter

This script helps you run the audio processing accuracy tests step by step.
"""

import os
import sys
from pathlib import Path

def main():
    print("🎯 Audio Processing Accuracy Test Suite")
    print("=" * 50)
    
    # Check current directory
    current_dir = Path.cwd()
    if not current_dir.name == "tests":
        print("⚠️  Please run this script from the ops_integrations/tests directory")
        print(f"Current directory: {current_dir}")
        print("Expected: .../ops_integrations/tests")
        return
    
    # Check required files
    required_files = [
        "test_audio_processing.py",
        "audio_accuracy_test.py", 
        "simple_audio_test.py",
        "run_accuracy_test.py",
        "../video/30 Second Elevator Speech.mp3",
        "../video/transcription.txt"
    ]
    
    missing_files = []
    for file_path in required_files:
        if not os.path.exists(file_path):
            missing_files.append(file_path)
    
    if missing_files:
        print("❌ Missing required files:")
        for file_path in missing_files:
            print(f"   - {file_path}")
        return
    
    print("✅ All required files found!")
    print()
    
    # Check dependencies
    print("📦 Checking dependencies...")
    try:
        import pydub
        import webrtcvad
        import openai
        import httpx
        print("✅ Core dependencies available")
    except ImportError as e:
        print(f"❌ Missing dependency: {e}")
        print("Install with: pip install pydub webrtcvad openai httpx")
        return
    
    print()
    print("🚀 Ready to run tests!")
    print()
    print("Choose an option:")
    print("1. Basic audio test (no API key required)")
    print("2. Full accuracy test (requires OpenAI API key)")
    print("3. Read documentation")
    print("4. Exit")
    
    while True:
        choice = input("\nEnter choice (1-4): ").strip()
        
        if choice == "1":
            print("\n🔧 Running basic audio test...")
            os.system("python3 simple_audio_test.py")
            break
            
        elif choice == "2":
            print("\n🎯 Running full accuracy test...")
            print("You will be prompted for your OpenAI API key.")
            os.system("python3 run_accuracy_test.py")
            break
            
        elif choice == "3":
            print("\n📖 Opening documentation...")
            doc_path = "README_AUDIO_TEST.md"
            if os.path.exists(doc_path):
                with open(doc_path, 'r') as f:
                    print(f.read())
            else:
                print("Documentation file not found.")
            continue
            
        elif choice == "4":
            print("👋 Goodbye!")
            break
            
        else:
            print("Invalid choice. Please enter 1-4.")

if __name__ == "__main__":
    main() 