#!/usr/bin/env python3
"""
Test runner for the modularized phone system components.
Runs all unit tests for the 5 core modules.
"""

import sys
import os
import subprocess
import pytest
from pathlib import Path

def run_tests():
    """Run all unit tests for the modularized components"""
    
    # Add the parent directory to Python path
    parent_dir = Path(__file__).parent.parent
    sys.path.insert(0, str(parent_dir))
    
    # Test modules in order
    test_modules = [
        "tests.test_audio_processor",
        "tests.test_speech_recognizer", 
        "tests.test_intent_extractor",
        "tests.test_conversation_manager",
        "tests.test_tts_manager"
    ]
    
    print("🧪 Running Unit Tests for Modularized Phone System")
    print("=" * 60)
    
    total_tests = 0
    passed_tests = 0
    failed_tests = 0
    
    for module in test_modules:
        print(f"\n📋 Testing Module: {module}")
        print("-" * 40)
        
        try:
            # Run pytest for this module
            result = pytest.main([
                module,
                "-v",
                "--tb=short",
                "--no-header",
                "--no-summary"
            ])
            
            if result == 0:
                print(f"✅ {module}: PASSED")
                passed_tests += 1
            else:
                print(f"❌ {module}: FAILED")
                failed_tests += 1
                
        except Exception as e:
            print(f"❌ {module}: ERROR - {e}")
            failed_tests += 1
    
    # Summary
    print("\n" + "=" * 60)
    print("📊 TEST SUMMARY")
    print("=" * 60)
    print(f"Total Modules: {len(test_modules)}")
    print(f"Passed: {passed_tests}")
    print(f"Failed: {failed_tests}")
    
    if failed_tests == 0:
        print("\n🎉 All tests passed! The modularization is working correctly.")
        return True
    else:
        print(f"\n⚠️  {failed_tests} module(s) failed. Please check the test output above.")
        return False

def run_individual_test(module_name):
    """Run tests for a specific module"""
    print(f"🧪 Running tests for: {module_name}")
    print("=" * 40)
    
    result = pytest.main([
        f"tests.test_{module_name}",
        "-v",
        "--tb=long"
    ])
    
    return result == 0

if __name__ == "__main__":
    if len(sys.argv) > 1:
        # Run specific module test
        module = sys.argv[1]
        success = run_individual_test(module)
        sys.exit(0 if success else 1)
    else:
        # Run all tests
        success = run_tests()
        sys.exit(0 if success else 1) 