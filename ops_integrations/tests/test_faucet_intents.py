#!/usr/bin/env python3
"""
Test Faucet Intent Detection with Location Specificity
Tests the new location-specific faucet services
"""
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from adapters.plumbing_services import infer_multiple_job_types_from_text

def test_faucet_intents():
    """Test the new location-specific faucet intent detection."""
    print("🚰 TESTING FAUCET INTENT DETECTION WITH LOCATION SPECIFICITY")
    print("=" * 60)
    
    faucet_tests = [
        {
            "text": "Kitchen faucet is dripping and needs to be replaced",
            "description": "Kitchen faucet leak with replacement",
            "expected_primary": "kitchen_faucet_leak",
            "expected_secondary": []
        },
        {
            "text": "Bathroom sink faucet is leaking under the sink",
            "description": "Bathroom faucet leak",
            "expected_primary": "bathroom_faucet_leak",
            "expected_secondary": []
        },
        {
            "text": "Need to replace the kitchen faucet with a new one",
            "description": "Kitchen faucet replacement",
            "expected_primary": "kitchen_faucet_replacement",
            "expected_secondary": []
        },
        {
            "text": "Bathroom faucet is broken and needs repair",
            "description": "Bathroom faucet repair",
            "expected_primary": "bathroom_faucet_repair",
            "expected_secondary": []
        },
        {
            "text": "Kitchen faucet is not working properly",
            "description": "Kitchen faucet repair",
            "expected_primary": "kitchen_faucet_repair",
            "expected_secondary": []
        },
        {
            "text": "Bathroom sink faucet replacement needed",
            "description": "Bathroom faucet replacement",
            "expected_primary": "bathroom_faucet_replacement",
            "expected_secondary": []
        },
        {
            "text": "Kitchen sink faucet is leaking and the disposal is jammed",
            "description": "Kitchen faucet leak with disposal issue",
            "expected_primary": "kitchen_faucet_leak",
            "expected_secondary": ["garbage_disposal"]
        },
        {
            "text": "Bathroom faucet needs replacement and shower valve is broken",
            "description": "Bathroom faucet replacement with shower valve",
            "expected_primary": "bathroom_faucet_replacement",
            "expected_secondary": ["shower_valve"]
        },
        {
            "text": "Generic faucet is dripping",
            "description": "Generic faucet leak (should use general leaky_faucet)",
            "expected_primary": "leaky_faucet",
            "expected_secondary": []
        },
        {
            "text": "Need to replace faucet in kitchen sink area",
            "description": "Kitchen faucet replacement with area context",
            "expected_primary": "kitchen_faucet_replacement",
            "expected_secondary": []
        }
    ]
    
    passed = 0
    total = len(faucet_tests)
    
    for i, test in enumerate(faucet_tests, 1):
        result = infer_multiple_job_types_from_text(test["text"])
        
        print(f"\nTest {i}: {test['description']}")
        print(f"  Text: '{test['text']}'")
        print(f"  Expected Primary: {test['expected_primary']}")
        print(f"  Actual Primary: {result['primary']}")
        print(f"  Expected Secondary: {test['expected_secondary']}")
        print(f"  Actual Secondary: {result['secondary']}")
        print(f"  Description Suffix: '{result['description_suffix']}'")
        
        primary_match = result['primary'] == test['expected_primary']
        secondary_match = result['secondary'] == test['expected_secondary']
        
        if primary_match and secondary_match:
            print(f"  ✅ PASS")
            passed += 1
        else:
            print(f"  ❌ FAIL")
            if not primary_match:
                print(f"    Primary mismatch")
            if not secondary_match:
                print(f"    Secondary mismatch")
    
    print(f"\n" + "=" * 60)
    print(f"📊 FAUCET INTENT TEST RESULTS: {passed}/{total} passed ({passed/total*100:.1f}%)")
    
    if passed == total:
        print("🌟 PERFECT! All faucet intent tests passed.")
    elif passed >= total * 0.8:
        print("✅ EXCELLENT! Faucet intent detection working well.")
    elif passed >= total * 0.6:
        print("⚠️  GOOD! Faucet intent detection needs some improvement.")
    else:
        print("❌ NEEDS WORK! Faucet intent detection needs significant improvement.")
    
    return passed == total

if __name__ == "__main__":
    success = test_faucet_intents()
    sys.exit(0 if success else 1) 