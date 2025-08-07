#!/usr/bin/env python3
"""
Test suite for the new fixture-issue mapping system in plumbing_services.py
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from adapters.plumbing_services import (
    find_fixtures_in_text,
    find_issues_in_text,
    get_fixture_issue_pairs,
    infer_job_type_from_text,
    get_multiple_intents_from_text,
    map_pair_to_intent
)

def test_fixture_detection():
    """Test fixture detection with various synonyms."""
    print("=== FIXTURE DETECTION TESTS ===")
    
    test_cases = [
        ("My toilet is acting up", ["toilet"]),
        ("The commode won't stop running", ["toilet"]),
        ("Kitchen sink is clogged", ["kitchen_sink", "sink"]),
        ("Bathroom sink drain is slow", ["bathroom_sink", "sink"]),
        ("Shower head is dripping", ["showerhead", "shower"]),
        ("Water heater not working", ["water_heater"]),
        ("Main sewer line needs camera inspection", ["main_line"]),
        ("Dishwasher hookup needed", ["dishwasher"]),
        ("Hose bib outside is frozen", ["hose_bib"])
    ]
    
    for text, expected_fixtures in test_cases:
        fixtures = find_fixtures_in_text(text)
        found_fixtures = [f[1] for f in fixtures]
        print(f"Text: '{text}'")
        print(f"  Found: {found_fixtures}")
        print(f"  Expected: {expected_fixtures}")
        print(f"  Match: {all(f in found_fixtures for f in expected_fixtures)}")
        print()

def test_issue_detection():
    """Test issue detection with various synonyms."""
    print("=== ISSUE DETECTION TESTS ===")
    
    test_cases = [
        ("toilet is clogged", ["clog"]),
        ("faucet is dripping", ["leak"]),
        ("no hot water", ["no_hot_water"]),
        ("constantly running", ["running"]),
        ("need installation", ["install"]),
        ("emergency repair needed", ["emergency", "repair"]),
        ("camera inspection required", ["camera_inspection"]),
        ("hydro jet the line", ["hydro_jet"]),
        ("snake the drain", ["snaking"]),
        ("pipe burst in basement", ["burst"])
    ]
    
    for text, expected_issues in test_cases:
        issues = find_issues_in_text(text)
        found_issues = [i[1] for i in issues]
        print(f"Text: '{text}'")
        print(f"  Found: {found_issues}")
        print(f"  Expected: {expected_issues}")
        print(f"  Match: {any(i in found_issues for i in expected_issues)}")
        print()

def test_fixture_issue_pairs():
    """Test fixture-issue pair detection."""
    print("=== FIXTURE-ISSUE PAIR TESTS ===")
    
    test_cases = [
        "toilet is clogged",
        "kitchen sink leak",
        "water heater no hot water",
        "main sewer camera inspection",
        "bathroom faucet dripping",
        "shower head needs replacement",
        "commode running constantly",
        "dishwasher hookup installation"
    ]
    
    for text in test_cases:
        pairs = get_fixture_issue_pairs(text)
        print(f"Text: '{text}'")
        for pair in pairs:
            intent = map_pair_to_intent(pair['fixture'], pair['issue'])
            print(f"  Pair: {pair['fixture']} + {pair['issue']} → {intent}")
            print(f"  Specificity: {pair['specificity']}, Distance: {pair['distance']}")
            print(f"  Matched: '{pair['fixture_text']}' + '{pair['issue_text']}'")
        print()

def test_intent_inference():
    """Test the main intent inference function."""
    print("=== INTENT INFERENCE TESTS ===")
    
    test_cases = [
        "My toilet is clogged and won't flush",
        "Kitchen sink faucet is leaking badly", 
        "Need a new water heater installed",
        "Main sewer line needs camera inspection",
        "Bathroom sink drain is slow and smells",
        "Emergency - water heater burst in basement",
        "Shower head replacement needed",
        "Dishwasher hookup for new appliance",
        "Commode keeps running after flushing",
        "Hydro jet the main line please"
    ]
    
    for text in test_cases:
        intent = infer_job_type_from_text(text)
        print(f"Text: '{text}'")
        print(f"  Primary Intent: {intent}")
        print()

def test_multiple_intents():
    """Test detection of multiple intents in one message."""
    print("=== MULTIPLE INTENT DETECTION TESTS ===")
    
    test_cases = [
        "Toilet is clogged and the kitchen sink faucet is leaking",
        "Need water heater installation and bathroom sink repair",
        "Emergency leak in basement and main sewer backup",
        "Camera inspection of main line and hydro jet cleaning needed",
        "Shower head dripping and toilet running constantly"
    ]
    
    for text in test_cases:
        result = get_multiple_intents_from_text(text)
        print(f"Text: '{text}'")
        print(f"  Primary Intent: {result['primary_intent']}")
        print(f"  Additional Intents: {result['additional_intents']}")
        print(f"  Confidence: {result['confidence']:.2f}")
        print("  Detected Pairs:")
        for pair in result['detected_pairs']:
            print(f"    {pair['fixture']} + {pair['issue']} → {pair['intent']} (spec: {pair['specificity']})")
        print()

def test_specificity_prioritization():
    """Test that more specific fixtures/issues are prioritized."""
    print("=== SPECIFICITY PRIORITIZATION TESTS ===")
    
    test_cases = [
        "kitchen sink clogged",  # Should prefer kitchen_sink over sink
        "bathroom sink leaking",  # Should prefer bathroom_sink over sink
        "toilet flange replacement",  # Should detect specific flange issue
        "water heater expansion tank",  # Should detect specific expansion issue
        "main sewer hydro jet"  # Should detect specific hydro_jet issue
    ]
    
    for text in test_cases:
        pairs = get_fixture_issue_pairs(text)
        intent = infer_job_type_from_text(text)
        print(f"Text: '{text}'")
        print(f"  Intent: {intent}")
        if pairs:
            primary_pair = pairs[0]
            print(f"  Primary Pair: {primary_pair['fixture']} + {primary_pair['issue']}")
            print(f"  Specificity: {primary_pair['specificity']}")
        print()

def test_synonym_matching():
    """Test that synonyms are properly matched."""
    print("=== SYNONYM MATCHING TESTS ===")
    
    test_cases = [
        ("commode is backed up", "toilet", "clog"),
        ("tap is dripping", "faucet", "leak"),
        ("spigot outside is frozen", "hose_bib", "frozen"),
        ("water closet replacement", "toilet", "install"),
        ("garbage disposer installation", "garbage_disposal", "install"),
        ("no hot water from heater", "water_heater", "no_hot_water")
    ]
    
    for text, expected_fixture, expected_issue in test_cases:
        pairs = get_fixture_issue_pairs(text)
        print(f"Text: '{text}'")
        print(f"  Expected: {expected_fixture} + {expected_issue}")
        if pairs:
            found_pair = pairs[0]
            print(f"  Found: {found_pair['fixture']} + {found_pair['issue']}")
            print(f"  Match: {found_pair['fixture'] == expected_fixture and found_pair['issue'] == expected_issue}")
        else:
            print("  Found: No pairs detected")
        print()

if __name__ == "__main__":
    print("Testing New Fixture-Issue Mapping System")
    print("=" * 50)
    
    test_fixture_detection()
    test_issue_detection()
    test_fixture_issue_pairs()
    test_intent_inference()
    test_multiple_intents()
    test_specificity_prioritization()
    test_synonym_matching()
    
    print("Testing complete!") 