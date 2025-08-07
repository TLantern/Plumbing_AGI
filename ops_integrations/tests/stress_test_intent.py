#!/usr/bin/env python3
"""
Random Stress Test for Text to Intent System
Tests the enhanced system with 25 new random challenging scenarios
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from adapters.plumbing_services import infer_multiple_job_types_from_text

def run_random_stress_test():
    """Run random stress test with new challenging scenarios."""
    print("🎲 RANDOM STRESS TESTING TEXT TO INTENT SYSTEM")
    print("=" * 70)
    print("25 NEW RANDOM challenging test cases")
    print("15 multi-intent scenarios (max 1 secondary) | 10 single intent scenarios")
    print("=" * 70)

    # Multi-Intent Tests (15 scenarios)
    multi_intent_tests = [
        {
            "text": "Dishwasher won't drain and kitchen sink is clogged",
            "description": "Appliance with drain issue",
            "expected_primary": "dishwasher_hookup",
            "expected_secondary_count": 1,
            "expected_secondary": ["clogged_kitchen_sink"]
        },
        {
            "text": "Water heater is leaking and expansion tank needs replacement",
            "description": "Water heater with component issue",
            "expected_primary": "water_heater_repair",
            "expected_secondary_count": 1,
            "expected_secondary": ["water_heater_expansion"]
        },
        {
            "text": "Sewer line is backed up and need camera inspection",
            "description": "Sewer with diagnostic",
            "expected_primary": "main_sewer_backup",
            "expected_secondary_count": 1,
            "expected_secondary": ["camera_inspection"]
        },
        {
            "text": "Bathroom faucet is dripping and shower valve broken",
            "description": "Faucet with valve issue",
            "expected_primary": "bathroom_faucet_leak",
            "expected_secondary_count": 1,
            "expected_secondary": ["shower_valve"]
        },
        {
            "text": "Toilet is running and tank is leaking",
            "description": "Toilet with multiple issues",
            "expected_primary": "running_toilet",
            "expected_secondary_count": 1,
            "expected_secondary": ["toilet_leak"]
        },
        {
            "text": "Gas line leak and emergency shutoff needed",
            "description": "Gas safety emergency",
            "expected_primary": "gas_line_leak",
            "expected_secondary_count": 1,
            "expected_secondary": ["emergency_shutoff"]
        },
        {
            "text": "Sump pump failed and basement flooding",
            "description": "Emergency pump failure",
            "expected_primary": "sump_pump_repair",
            "expected_secondary_count": 0,
            "expected_secondary": []
        },
        {
            "text": "Grease trap needs cleaning and backflow prevention",
            "description": "Commercial services",
            "expected_primary": "grease_trap",
            "expected_secondary_count": 1,
            "expected_secondary": ["backflow_prevention"]
        },
        {
            "text": "Whole house re-piping and trenchless sewer repair",
            "description": "Major plumbing project",
            "expected_primary": "whole_house_re_piping",
            "expected_secondary_count": 1,
            "expected_secondary": ["trenchless_sewer"]
        },
        {
            "text": "Water filtration system and ice maker line hookup",
            "description": "Water treatment with appliance",
            "expected_primary": "water_filtration",
            "expected_secondary_count": 1,
            "expected_secondary": ["ice_maker_line"]
        },
        {
            "text": "Slab leak repair and drain tile installation",
            "description": "Underground leak with drainage",
            "expected_primary": "slab_leak_repair",
            "expected_secondary_count": 1,
            "expected_secondary": ["drain_tile"]
        },
        {
            "text": "Burst pipe in wall and pipe thawing needed",
            "description": "Emergency with frozen pipes",
            "expected_primary": "burst_pipe",
            "expected_secondary_count": 1,
            "expected_secondary": ["pipe_thawing"]
        },
        {
            "text": "Kitchen faucet replacement and garbage disposal jammed",
            "description": "Faucet with disposal issue",
            "expected_primary": "kitchen_faucet_replacement",
            "expected_secondary_count": 1,
            "expected_secondary": ["garbage_disposal"]
        },
        {
            "text": "Pressure reducing valve and water softener system",
            "description": "Pressure and treatment services",
            "expected_primary": "pressure_reducing_valve",
            "expected_secondary_count": 1,
            "expected_secondary": ["water_softener"]
        },
        {
            "text": "Tankless water heater installation and expansion tank",
            "description": "Water heater with component",
            "expected_primary": "tankless_water_heater",
            "expected_secondary_count": 1,
            "expected_secondary": ["water_heater_expansion"]
        }
    ]

    # Single Intent Tests (10 scenarios)
    single_intent_tests = [
        {
            "text": "Outdoor spigot is frozen",
            "description": "Outdoor faucet freezing",
            "expected_primary": "hose_bib",
            "expected_secondary_count": 0,
            "expected_secondary": []
        },
        {
            "text": "Shower mixing valve replacement needed",
            "description": "Shower valve replacement",
            "expected_primary": "shower_valve",
            "expected_secondary_count": 0,
            "expected_secondary": []
        },
        {
            "text": "Dishwasher drainage problem",
            "description": "Dishwasher drainage",
            "expected_primary": "dishwasher_hookup",
            "expected_secondary_count": 0,
            "expected_secondary": []
        },
        {
            "text": "Water pressure extremely low",
            "description": "Water pressure issue",
            "expected_primary": "water_pressure_adjustment",
            "expected_secondary_count": 0,
            "expected_secondary": []
        },
        {
            "text": "Sewage ejector pump not working",
            "description": "Ejector pump failure",
            "expected_primary": "sewage_ejector",
            "expected_secondary_count": 0,
            "expected_secondary": []
        },
        {
            "text": "New bathtub installation needed",
            "description": "Bathtub installation",
            "expected_primary": "bathtub_install",
            "expected_secondary_count": 0,
            "expected_secondary": []
        },
        {
            "text": "Well pump making strange noises",
            "description": "Well system issues",
            "expected_primary": "well_pump",
            "expected_secondary_count": 0,
            "expected_secondary": []
        },
        {
            "text": "Commercial restroom needs new fixtures",
            "description": "Commercial restroom work",
            "expected_primary": "commercial_restroom",
            "expected_secondary_count": 0,
            "expected_secondary": []
        },
        {
            "text": "Hydrostatic pressure test needed",
            "description": "Construction pressure testing",
            "expected_primary": "hydrostatic_test",
            "expected_secondary_count": 0,
            "expected_secondary": []
        },
        {
            "text": "Main water line needs replacement",
            "description": "Main water line work",
            "expected_primary": "water_line",
            "expected_secondary_count": 0,
            "expected_secondary": []
        }
    ]

    # Run Multi-Intent Tests
    print("\n🧪 MULTI-INTENT TESTS (15 RANDOM scenarios)")
    print("-" * 50)
    
    multi_passed = 0
    for i, test in enumerate(multi_intent_tests, 1):
        result = infer_multiple_job_types_from_text(test["text"])
        
        primary_match = result['primary'] == test['expected_primary']
        secondary_count_match = len(result['secondary']) == test['expected_secondary_count']
        
        # Check if any expected secondary services are present
        secondary_match = True
        if test['expected_secondary_count'] > 0:
            if not result['secondary']:
                secondary_match = False
            else:
                # Check if any expected secondary is in actual secondary
                found_expected = False
                for expected_sec in test['expected_secondary']:
                    if expected_sec in result['secondary']:
                        found_expected = True
                        break
                secondary_match = found_expected
        
        test_passed = primary_match and secondary_count_match and secondary_match
        
        if test_passed:
            multi_passed += 1
            status = "✅ PASS"
        else:
            status = "❌ FAIL"
        
        print(f"Test {i}: {test['description']}")
        print(f"  Text: '{test['text']}'")
        print(f"  Expected Primary: {test['expected_primary']}")
        print(f"  Actual Primary: {result['primary']}")
        print(f"  Expected Secondary Count: {test['expected_secondary_count']}")
        print(f"  Actual Secondary Count: {len(result['secondary'])}")
        print(f"  Secondary Services: {result['secondary']}")
        print(f"  Description Suffix: '{result['description_suffix']}'")
        print(f"  {status}")
        
        if not test_passed:
            if not primary_match:
                print("    Primary mismatch")
            if not secondary_count_match:
                print("    Secondary count mismatch")
            if not secondary_match:
                print("    Secondary mismatch")
        print()

    # Run Single Intent Tests
    print("\n🧪 SINGLE INTENT TESTS (10 RANDOM scenarios)")
    print("-" * 50)
    
    single_passed = 0
    for i, test in enumerate(single_intent_tests, 1):
        result = infer_multiple_job_types_from_text(test["text"])
        
        primary_match = result['primary'] == test['expected_primary']
        no_secondary = len(result['secondary']) == 0
        no_description = result['description_suffix'] == ''
        
        test_passed = primary_match and no_secondary and no_description
        
        if test_passed:
            single_passed += 1
            status = "✅ PASS"
        else:
            status = "❌ FAIL"
        
        print(f"Test {i}: {test['description']}")
        print(f"  Text: '{test['text']}'")
        print(f"  Expected Primary: {test['expected_primary']}")
        print(f"  Actual Primary: {result['primary']}")
        print(f"  Secondary Services: {result['secondary']}")
        print(f"  Description Suffix: '{result['description_suffix']}'")
        print(f"  {status}")
        
        if not test_passed:
            if not primary_match:
                print("    Primary mismatch")
            if not no_secondary:
                print("    Unexpected secondary intents")
            if not no_description:
                print("    Unexpected description suffix")
        print()

    # Results Summary
    print("=" * 70)
    print("📊 RANDOM STRESS TEST RESULTS")
    print("=" * 70)
    print(f"Multi-Intent Tests: {multi_passed}/15 passed ({multi_passed/15*100:.1f}%)")
    print(f"Single Intent Tests: {single_passed}/10 passed ({single_passed/10*100:.1f}%)")
    print(f"Overall: {multi_passed + single_passed}/25 passed ({(multi_passed + single_passed)/25*100:.1f}%)")
    
    overall_percentage = (multi_passed + single_passed) / 25 * 100
    
    if overall_percentage >= 90:
        print("\n🌟 EXCELLENT! System performing at high accuracy.")
    elif overall_percentage >= 80:
        print("\n✅ GOOD! System performing well with room for improvement.")
    elif overall_percentage >= 70:
        print("\n⚠️  MODERATE! System needs some refinement.")
    else:
        print("\n❌ NEEDS WORK! System requires significant improvement.")
    
    return multi_passed + single_passed == 25

if __name__ == "__main__":
    success = run_random_stress_test()
    sys.exit(0 if success else 1) 