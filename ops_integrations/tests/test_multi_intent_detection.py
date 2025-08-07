#!/usr/bin/env python3
"""
Test Multi-Intent Detection for Phone Text Processing
"""
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from adapters.plumbing_services import infer_multiple_job_types_from_text, infer_job_type_from_text

def test_single_intent_detection():
    """Test detection of single intents (existing behavior)."""
    print("🧪 Testing Single Intent Detection...")
    
    test_cases = [
        {
            "text": "My kitchen sink is clogged",
            "expected_primary": "clogged_kitchen_sink",
            "expected_secondary": []
        },
        {
            "text": "The toilet is running constantly",
            "expected_primary": "running_toilet",
            "expected_secondary": []
        },
        {
            "text": "Water heater burst emergency",
            "expected_primary": "water_heater_repair",
            "expected_secondary": []
        }
    ]
    
    passed = 0
    for i, case in enumerate(test_cases, 1):
        result = infer_multiple_job_types_from_text(case["text"])
        
        print(f"\nTest {i}: '{case['text']}'")
        print(f"  Expected Primary: {case['expected_primary']}")
        print(f"  Actual Primary: {result['primary']}")
        print(f"  Expected Secondary: {case['expected_secondary']}")
        print(f"  Actual Secondary: {result['secondary']}")
        print(f"  Description Suffix: '{result['description_suffix']}'")
        
        if (result['primary'] == case['expected_primary'] and 
            result['secondary'] == case['expected_secondary']):
            print(f"  ✅ PASS")
            passed += 1
        else:
            print(f"  ❌ FAIL")
    
    print(f"\n📊 Single Intent Tests: {passed}/{len(test_cases)} passed")
    return passed, len(test_cases)

def test_multi_intent_detection():
    """Test detection of multiple intents with primary/secondary ordering."""
    print("\n🧪 Testing Multi-Intent Detection...")
    
    test_cases = [
        {
            "text": "My kitchen sink is clogged and the toilet is running",
            "expected_primary": "clogged_kitchen_sink",  # First mentioned
            "expected_secondary": ["running_toilet"],
            "should_have_suffix": True
        },
        {
            "text": "I have a leak under the sink and need a new faucet installed",
            "expected_primary": "leak_detection",  # First mentioned
            "expected_secondary": ["faucet_replacement"],
            "should_have_suffix": True
        },
        {
            "text": "Water heater is leaking and the bathroom drain is clogged",
            "expected_primary": "water_heater_repair",
            "expected_secondary": ["clogged_bathroom_sink"],
            "should_have_suffix": True
        },
        {
            "text": "Emergency burst pipe and toilet replacement needed",
            "expected_primary": "burst_pipe",  # First mentioned
            "expected_secondary": ["toilet_replacement"],
            "should_have_suffix": True
        },
        {
            "text": "Sump pump install and hydro jetting for main sewer backup",
            "expected_primary": "sump_pump_install",
            "expected_secondary": ["hydro_jetting", "main_sewer_backup"],
            "should_have_suffix": True
        }
    ]
    
    passed = 0
    for i, case in enumerate(test_cases, 1):
        result = infer_multiple_job_types_from_text(case["text"])
        
        print(f"\nTest {i}: '{case['text']}'")
        print(f"  Expected Primary: {case['expected_primary']}")
        print(f"  Actual Primary: {result['primary']}")
        print(f"  Expected Secondary: {case['expected_secondary']}")
        print(f"  Actual Secondary: {result['secondary']}")
        print(f"  Description Suffix: '{result['description_suffix']}'")
        
        primary_match = result['primary'] == case['expected_primary']
        secondary_match = set(result['secondary']) == set(case['expected_secondary'])
        has_suffix = bool(result['description_suffix']) == case['should_have_suffix']
        
        if primary_match and secondary_match and has_suffix:
            print(f"  ✅ PASS")
            passed += 1
        else:
            print(f"  ❌ FAIL")
            if not primary_match:
                print(f"    Primary mismatch")
            if not secondary_match:
                print(f"    Secondary mismatch")
            if not has_suffix:
                print(f"    Description suffix mismatch")
    
    print(f"\n📊 Multi-Intent Tests: {passed}/{len(test_cases)} passed")
    return passed, len(test_cases)

def test_general_to_specific_priority():
    """Test that specific services take priority over general categories."""
    print("\n🧪 Testing General-to-Specific Priority...")
    
    test_cases = [
        {
            "text": "I have a clog in my kitchen sink",
            "expected_primary": "clogged_kitchen_sink",  # Specific over general "clog"
            "description": "Should prefer specific 'clogged_kitchen_sink' over general 'clog'"
        },
        {
            "text": "Leak detection needed for bathroom sink leak",
            "expected_primary": "leak_detection",  # First mentioned specific service
            "description": "Should prefer first mentioned specific service"
        },
        {
            "text": "Need install for new water heater installation",
            "expected_primary": "water_heater_install",  # Specific over general "install"
            "description": "Should prefer specific service over general install"
        }
    ]
    
    passed = 0
    for i, case in enumerate(test_cases, 1):
        result = infer_multiple_job_types_from_text(case["text"])
        
        print(f"\nTest {i}: '{case['text']}'")
        print(f"  Expected Primary: {case['expected_primary']}")
        print(f"  Actual Primary: {result['primary']}")
        print(f"  Description: {case['description']}")
        
        if result['primary'] == case['expected_primary']:
            print(f"  ✅ PASS")
            passed += 1
        else:
            print(f"  ❌ FAIL")
    
    print(f"\n📊 Priority Tests: {passed}/{len(test_cases)} passed")
    return passed, len(test_cases)

def test_description_suffix_formatting():
    """Test that description suffixes are properly formatted."""
    print("\n🧪 Testing Description Suffix Formatting...")
    
    test_cases = [
        {
            "text": "Kitchen sink clog and toilet running",
            "expected_pattern": "Also detected:",
            "expected_count": 1  # One secondary intent
        },
        {
            "text": "Leak detection, faucet replacement, and toilet install",
            "expected_pattern": "Also detected:",
            "expected_count": 2  # Two secondary intents
        },
        {
            "text": "Water heater repair, sump pump install, and drain snaking needed",
            "expected_pattern": "and",  # Should use "and" for multiple items
            "expected_count": 2
        }
    ]
    
    passed = 0
    for i, case in enumerate(test_cases, 1):
        result = infer_multiple_job_types_from_text(case["text"])
        
        print(f"\nTest {i}: '{case['text']}'")
        print(f"  Secondary Count: {len(result['secondary'])}")
        print(f"  Description Suffix: '{result['description_suffix']}'")
        
        has_pattern = case['expected_pattern'] in result['description_suffix']
        has_content = len(result['description_suffix']) > 0 if result['secondary'] else True
        
        if has_pattern and has_content:
            print(f"  ✅ PASS")
            passed += 1
        else:
            print(f"  ❌ FAIL")
    
    print(f"\n📊 Formatting Tests: {passed}/{len(test_cases)} passed")
    return passed, len(test_cases)

def test_edge_cases():
    """Test edge cases and boundary conditions."""
    print("\n🧪 Testing Edge Cases...")
    
    test_cases = [
        {
            "text": "",
            "expected_primary": None,
            "description": "Empty string"
        },
        {
            "text": "Hello, I need help",
            "expected_primary": None,
            "description": "No plumbing keywords"
        },
        {
            "text": "sink sink sink kitchen",
            "expected_primary": "clogged_kitchen_sink",
            "description": "Repeated keywords with context"
        },
        {
            "text": "The same leak is happening again with the same toilet issue",
            "expected_primary": "leak",  # First mentioned
            "description": "Repeated issues with same keyword"
        }
    ]
    
    passed = 0
    for i, case in enumerate(test_cases, 1):
        result = infer_multiple_job_types_from_text(case["text"])
        
        print(f"\nTest {i}: '{case['text']}'" if case["text"] else "\nTest {i}: (empty string)")
        print(f"  Expected Primary: {case['expected_primary']}")
        print(f"  Actual Primary: {result['primary']}")
        print(f"  Description: {case['description']}")
        
        if result['primary'] == case['expected_primary']:
            print(f"  ✅ PASS")
            passed += 1
        else:
            print(f"  ❌ FAIL")
    
    print(f"\n📊 Edge Case Tests: {passed}/{len(test_cases)} passed")
    return passed, len(test_cases)

def run_comprehensive_tests():
    """Run all multi-intent detection tests."""
    print("🎯 COMPREHENSIVE MULTI-INTENT DETECTION TESTS")
    print("=" * 60)
    
    total_passed = 0
    total_tests = 0
    
    # Run all test suites
    passed, tests = test_single_intent_detection()
    total_passed += passed
    total_tests += tests
    
    passed, tests = test_multi_intent_detection()
    total_passed += passed
    total_tests += tests
    
    passed, tests = test_general_to_specific_priority()
    total_passed += passed
    total_tests += tests
    
    passed, tests = test_description_suffix_formatting()
    total_passed += passed
    total_tests += tests
    
    passed, tests = test_edge_cases()
    total_passed += passed
    total_tests += tests
    
    # Final results
    print("\n" + "=" * 60)
    print(f"🎉 FINAL RESULTS: {total_passed}/{total_tests} tests passed")
    print(f"📈 Success Rate: {(total_passed/total_tests)*100:.1f}%")
    
    if total_passed == total_tests:
        print("🌟 ALL TESTS PASSED! Multi-intent detection is working correctly.")
    else:
        print(f"⚠️  {total_tests - total_passed} tests failed. Review implementation.")
    
    return total_passed == total_tests

if __name__ == "__main__":
    success = run_comprehensive_tests()
    sys.exit(0 if success else 1) 