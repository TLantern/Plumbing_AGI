#!/usr/bin/env python3
"""
Test script for local Whisper v3 setup.
Run this to verify your installation is working correctly.
"""

import sys
import os
import time

def test_imports():
    """Test if all required modules can be imported."""
    print("🔍 Testing imports...")
    
    try:
        import torch
        print(f"✅ PyTorch: {torch.__version__}")
        print(f"   CUDA available: {torch.cuda.is_available()}")
        if torch.cuda.is_available():
            print(f"   CUDA version: {torch.version.cuda}")
            print(f"   GPU count: {torch.cuda.device_count()}")
    except ImportError as e:
        print(f"❌ PyTorch import failed: {e}")
        return False
    
    try:
        import whisper
        print(f"✅ Whisper: {whisper.__version__}")
    except ImportError as e:
        print(f"❌ Whisper import failed: {e}")
        return False
    
    try:
        import numpy as np
        print(f"✅ NumPy: {np.__version__}")
    except ImportError as e:
        print(f"❌ NumPy import failed: {e}")
        return False
    
    try:
        import scipy
        print(f"✅ SciPy: {scipy.__version__}")
    except ImportError as e:
        print(f"❌ SciPy import failed: {e}")
        return False
    
    return True

def test_model_loading():
    """Test loading the Whisper model."""
    print("\n🔍 Testing model loading...")
    
    try:
        import whisper
        
        # Test with a smaller model first
        print("Loading base model for quick test...")
        start_time = time.time()
        model = whisper.load_model("base")
        load_time = time.time() - start_time
        print(f"✅ Base model loaded in {load_time:.2f}s")
        
        # Test large-v3 model
        print("Loading large-v3 model (this may take a while on first run)...")
        start_time = time.time()
        model = whisper.load_model("large-v3")
        load_time = time.time() - start_time
        print(f"✅ Large-v3 model loaded in {load_time:.2f}s")
        
        return True
        
    except Exception as e:
        print(f"❌ Model loading failed: {e}")
        return False

def test_local_whisper_adapter():
    """Test the local Whisper adapter."""
    print("\n🔍 Testing local Whisper adapter...")
    
    try:
        sys.path.append(os.path.join(os.path.dirname(__file__), 'adapters'))
        from local_whisper import LocalWhisperAdapter, get_local_whisper
        
        # Test adapter creation
        print("Creating local Whisper adapter...")
        adapter = LocalWhisperAdapter("base")  # Use base for quick test
        
        # Test model info
        info = adapter.get_model_info()
        print(f"✅ Adapter created successfully:")
        print(f"   Model: {info['model_name']}")
        print(f"   Device: {info['device']}")
        print(f"   CUDA available: {info['cuda_available']}")
        print(f"   Model loaded: {info['model_loaded']}")
        
        return True
        
    except Exception as e:
        print(f"❌ Local Whisper adapter test failed: {e}")
        return False

def test_transcription():
    """Test transcription with a simple audio file."""
    print("\n🔍 Testing transcription...")
    
    try:
        import whisper
        import numpy as np
        
        # Create a simple test audio (sine wave)
        print("Creating test audio...")
        sample_rate = 16000
        duration = 2.0  # 2 seconds
        frequency = 440  # A4 note
        
        t = np.linspace(0, duration, int(sample_rate * duration), False)
        audio = np.sin(2 * np.pi * frequency * t) * 0.3  # 30% volume
        audio = audio.astype(np.float32)  # Ensure float32 dtype
        
        # Test transcription
        print("Testing transcription with base model...")
        model = whisper.load_model("base")
        
        start_time = time.time()
        result = model.transcribe(audio, language="en")
        transcription_time = time.time() - start_time
        
        print(f"✅ Transcription completed in {transcription_time:.2f}s")
        print(f"   Text: '{result['text']}'")
        print(f"   Language: {result.get('language', 'unknown')}")
        
        return True
        
    except Exception as e:
        print(f"❌ Transcription test failed: {e}")
        return False

def main():
    """Run all tests."""
    print("🧪 Local Whisper v3 Test Suite")
    print("=" * 40)
    
    tests = [
        ("Import Test", test_imports),
        ("Model Loading Test", test_model_loading),
        ("Adapter Test", test_local_whisper_adapter),
        ("Transcription Test", test_transcription),
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n📋 Running {test_name}...")
        try:
            if test_func():
                print(f"✅ {test_name} PASSED")
                passed += 1
            else:
                print(f"❌ {test_name} FAILED")
        except Exception as e:
            print(f"❌ {test_name} FAILED with exception: {e}")
    
    print("\n" + "=" * 40)
    print(f"📊 Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! Local Whisper v3 is ready to use.")
        print("\nNext steps:")
        print("1. Set USE_LOCAL_WHISPER = True in phone.py")
        print("2. Set LOCAL_WHISPER_MODEL = 'large-v3' for best quality")
        print("3. Restart your phone service")
    else:
        print("⚠️  Some tests failed. Please check the installation.")
        print("\nTroubleshooting:")
        print("1. Run: ./setup_local_whisper.sh")
        print("2. Check CUDA installation if using GPU")
        print("3. Ensure sufficient disk space for models")

if __name__ == "__main__":
    main() 