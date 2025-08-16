#!/usr/bin/env python3
"""
Test script to verify Whisper installation and basic functionality
"""

import sys
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_whisper_import():
    """Test that Whisper can be imported"""
    try:
        import whisper
        logger.info(f"✅ Whisper imported successfully: {whisper.__version__}")
        return True
    except ImportError as e:
        logger.error(f"❌ Failed to import Whisper: {e}")
        return False

def test_torch_import():
    """Test that PyTorch can be imported"""
    try:
        import torch
        logger.info(f"✅ PyTorch imported successfully: {torch.__version__}")
        logger.info(f"   CUDA available: {torch.cuda.is_available()}")
        return True
    except ImportError as e:
        logger.error(f"❌ Failed to import PyTorch: {e}")
        return False

def test_torchvision_import():
    """Test that torchvision can be imported"""
    try:
        import torchvision
        logger.info(f"✅ TorchVision imported successfully: {torchvision.__version__}")
        return True
    except ImportError as e:
        logger.error(f"❌ Failed to import TorchVision: {e}")
        return False

def test_torchaudio_import():
    """Test that torchaudio can be imported"""
    try:
        import torchaudio
        logger.info(f"✅ TorchAudio imported successfully: {torchaudio.__version__}")
        return True
    except ImportError as e:
        logger.error(f"❌ Failed to import TorchAudio: {e}")
        return False

def test_audio_dependencies():
    """Test audio processing dependencies"""
    try:
        import numpy
        logger.info(f"✅ NumPy imported successfully: {numpy.__version__}")
    except ImportError as e:
        logger.error(f"❌ Failed to import NumPy: {e}")
        return False
    
    try:
        import scipy
        logger.info(f"✅ SciPy imported successfully: {scipy.__version__}")
    except ImportError as e:
        logger.error(f"❌ Failed to import SciPy: {e}")
        return False
    
    return True

def main():
    """Run all tests"""
    logger.info("🧪 Testing Whisper installation and dependencies...")
    
    tests = [
        test_whisper_import,
        test_torch_import,
        test_torchvision_import,
        test_torchaudio_import,
        test_audio_dependencies,
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test():
            passed += 1
        logger.info("")  # Add spacing between tests
    
    logger.info(f"📊 Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        logger.info("🎉 All tests passed! Whisper installation is working correctly.")
        return 0
    else:
        logger.error("❌ Some tests failed. Please check the installation.")
        return 1

if __name__ == "__main__":
    sys.exit(main()) 