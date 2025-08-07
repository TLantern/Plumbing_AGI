#!/usr/bin/env python3
"""
Test GPT-4 Intent Extraction Accuracy
"""
import asyncio
import json
import sys
import os
from dotenv import load_dotenv

# Add parent directory to path to import adapters
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

load_dotenv('../.env')

# Test cases with expected outputs
TEST_CASES = [
    {
        "input": "Hi, I have a leaky faucet in my kitchen that's been dripping for days. My name is John Smith and I'm at 123 Main Street. I need this fixed as soon as possible.",
        "expected": {
            "intent": "BOOK_JOB",
            "customer": {"name": "John Smith", "phone": None, "email": None},
            "job": {"type": "leak", "urgency": "same_day", "description": "leaky faucet in kitchen"},
            "location": {"raw_address": "123 Main Street", "validated": False, "address_id": None, "lat": None, "lng": None},
            "fsm_backend": "servicetitan",
            "confidence": {"overall": 0.8, "fields": {"address": 0.7, "type": 0.9, "urgency": 0.8}},
            "handoff_needed": False
        }
    },
    {
        "input": "Emergency! My water heater just burst and there's water everywhere. This is Sarah Johnson at 456 Oak Avenue. Please send someone immediately!",
        "expected": {
            "intent": "BOOK_JOB", 
            "customer": {"name": "Sarah Johnson", "phone": None, "email": None},
            "job": {"type": "water_heater", "urgency": "emergency", "description": "water heater burst, water everywhere"},
            "location": {"raw_address": "456 Oak Avenue", "validated": False, "address_id": None, "lat": None, "lng": None},
            "fsm_backend": "servicetitan",
            "confidence": {"overall": 0.9, "fields": {"address": 0.8, "type": 0.95, "urgency": 0.95}},
            "handoff_needed": False
        }
    },
    {
        "input": "My toilet is clogged and won't flush. I'm Mike Davis, 789 Pine Road. Can someone come by tomorrow?",
        "expected": {
            "intent": "BOOK_JOB",
            "customer": {"name": "Mike Davis", "phone": None, "email": None}, 
            "job": {"type": "clog", "urgency": "flex", "description": "toilet clogged, won't flush"},
            "location": {"raw_address": "789 Pine Road", "validated": False, "address_id": None, "lat": None, "lng": None},
            "fsm_backend": "servicetitan",
            "confidence": {"overall": 0.85, "fields": {"address": 0.8, "type": 0.9, "urgency": 0.8}},
            "handoff_needed": False
        }
    },
    {
        "input": "I need a gas line inspection. My name is Lisa Chen, 321 Elm Street. When can you schedule this?",
        "expected": {
            "intent": "BOOK_JOB",
            "customer": {"name": "Lisa Chen", "phone": None, "email": None},
            "job": {"type": "gas_line", "urgency": "flex", "description": "gas line inspection"},
            "location": {"raw_address": "321 Elm Street", "validated": False, "address_id": None, "lat": None, "lng": None},
            "fsm_backend": "servicetitan", 
            "confidence": {"overall": 0.8, "fields": {"address": 0.8, "type": 0.85, "urgency": 0.7}},
            "handoff_needed": False
        }
    },
    {
        "input": "There's a weird smell coming from my drains. I think I need a sewer camera inspection. I'm at 654 Maple Drive.",
        "expected": {
            "intent": "BOOK_JOB",
            "customer": {"name": None, "phone": None, "email": None},
            "job": {"type": "sewer_cam", "urgency": "same_day", "description": "weird smell from drains, sewer camera inspection"},
            "location": {"raw_address": "654 Maple Drive", "validated": False, "address_id": None, "lat": None, "lng": None},
            "fsm_backend": "servicetitan",
            "confidence": {"overall": 0.7, "fields": {"address": 0.8, "type": 0.9, "urgency": 0.6}},
            "handoff_needed": True
        }
    },
    {
        "input": "My garbage disposal is broken and making loud noises. This is Tom Wilson at 555 Cedar Lane. My phone is 555-123-4567. Can you come today?",
        "expected": {
            "intent": "BOOK_JOB",
            "customer": {"name": "Tom Wilson", "phone": "555-123-4567", "email": None},
            "job": {"type": "install", "urgency": "same_day", "description": "garbage disposal broken, loud noises"},
            "location": {"raw_address": "555 Cedar Lane", "validated": False, "address_id": None, "lat": None, "lng": None},
            "fsm_backend": "servicetitan",
            "confidence": {"overall": 0.85, "fields": {"address": 0.8, "type": 0.8, "urgency": 0.9}},
            "handoff_needed": False
        }
    },
    {
        "input": "I have a backflow test scheduled but need to reschedule. My name is Maria Rodriguez, 777 Birch Street. Call me at 555-987-6543.",
        "expected": {
            "intent": "BOOK_JOB",
            "customer": {"name": "Maria Rodriguez", "phone": "555-987-6543", "email": None},
            "job": {"type": "backflow_test", "urgency": "flex", "description": "backflow test reschedule"},
            "location": {"raw_address": "777 Birch Street", "validated": False, "address_id": None, "lat": None, "lng": None},
            "fsm_backend": "servicetitan",
            "confidence": {"overall": 0.9, "fields": {"address": 0.9, "type": 0.95, "urgency": 0.8}},
            "handoff_needed": False
        }
    },
    {
        "input": "There's water leaking under my kitchen sink. It's getting worse. I'm at 999 Spruce Avenue and need help right away!",
        "expected": {
            "intent": "BOOK_JOB",
            "customer": {"name": None, "phone": None, "email": None},
            "job": {"type": "leak", "urgency": "emergency", "description": "water leaking under kitchen sink, getting worse"},
            "location": {"raw_address": "999 Spruce Avenue", "validated": False, "address_id": None, "lat": None, "lng": None},
            "fsm_backend": "servicetitan",
            "confidence": {"overall": 0.7, "fields": {"address": 0.8, "type": 0.9, "urgency": 0.9}},
            "handoff_needed": True
        }
    },
    {
        "input": "Hi, I'm David Kim at 111 Willow Drive. My hot water heater is making strange noises and the water isn't getting hot. Can someone come out this week?",
        "expected": {
            "intent": "BOOK_JOB",
            "customer": {"name": "David Kim", "phone": None, "email": None},
            "job": {"type": "water_heater", "urgency": "flex", "description": "hot water heater making noises, water not getting hot"},
            "location": {"raw_address": "111 Willow Drive", "validated": False, "address_id": None, "lat": None, "lng": None},
            "fsm_backend": "servicetitan",
            "confidence": {"overall": 0.85, "fields": {"address": 0.8, "type": 0.9, "urgency": 0.8}},
            "handoff_needed": False
        }
    },
    {
        "input": "I need to install a new toilet in my bathroom. My name is Jennifer Lee, I live at 222 Aspen Court. Email me at jen@email.com with the estimate.",
        "expected": {
            "intent": "BOOK_JOB",
            "customer": {"name": "Jennifer Lee", "phone": None, "email": "jen@email.com"},
            "job": {"type": "install", "urgency": "flex", "description": "install new toilet in bathroom"},
            "location": {"raw_address": "222 Aspen Court", "validated": False, "address_id": None, "lat": None, "lng": None},
            "fsm_backend": "servicetitan",
            "confidence": {"overall": 0.9, "fields": {"address": 0.9, "type": 0.95, "urgency": 0.8}},
            "handoff_needed": False
        }
    }
]

async def test_intent_extraction():
    """Test GPT-4 intent extraction accuracy"""
    from adapters.phone import extract_intent_from_text
    
    print("🧪 Testing GPT-4 Intent Extraction Accuracy")
    print("=" * 60)
    
    total_tests = len(TEST_CASES)
    passed_tests = 0
    accuracy_scores = []
    
    for i, test_case in enumerate(TEST_CASES, 1):
        print(f"\n📝 Test {i}/{total_tests}")
        print(f"Input: '{test_case['input']}'")
        
        try:
            # Extract intent using GPT-4
            result = await extract_intent_from_text(test_case['input'])
            
            # Calculate accuracy for key fields
            accuracy = calculate_accuracy(result, test_case['expected'])
            accuracy_scores.append(accuracy)
            
            print(f"✅ Extracted: {json.dumps(result, indent=2)}")
            print(f"🎯 Accuracy: {accuracy:.2%}")
            
            if accuracy >= 0.8:
                passed_tests += 1
                print("✅ PASS")
            else:
                print("❌ FAIL")
                
        except Exception as e:
            print(f"❌ Error: {e}")
            accuracy_scores.append(0.0)
    
    # Summary
    print(f"\n📊 SUMMARY")
    print("=" * 60)
    print(f"Total Tests: {total_tests}")
    print(f"Passed: {passed_tests}")
    print(f"Failed: {total_tests - passed_tests}")
    print(f"Success Rate: {passed_tests/total_tests:.2%}")
    print(f"Average Accuracy: {sum(accuracy_scores)/len(accuracy_scores):.2%}")
    
    return passed_tests, accuracy_scores

def calculate_accuracy(actual, expected):
    """Calculate accuracy score between actual and expected results"""
    score = 0.0
    total_fields = 0
    
    # Check intent
    if actual.get('intent') == expected.get('intent'):
        score += 1.0
    total_fields += 1
    
    # Check customer name
    actual_name = actual.get('customer', {}).get('name')
    expected_name = expected.get('customer', {}).get('name')
    if actual_name and expected_name and actual_name.lower() in expected_name.lower():
        score += 1.0
    elif not expected_name and not actual_name:
        score += 1.0
    total_fields += 1
    
    # Check job type
    if actual.get('job', {}).get('type') == expected.get('job', {}).get('type'):
        score += 1.0
    total_fields += 1
    
    # Check urgency
    if actual.get('job', {}).get('urgency') == expected.get('job', {}).get('urgency'):
        score += 1.0
    total_fields += 1
    
    # Check address (partial match)
    actual_addr = actual.get('location', {}).get('raw_address', '') or ''
    expected_addr = expected.get('location', {}).get('raw_address', '') or ''
    if actual_addr and expected_addr and any(word in actual_addr.lower() for word in expected_addr.lower().split()):
        score += 1.0
    total_fields += 1
    
    # Check description relevance
    actual_desc = actual.get('job', {}).get('description', '') or ''
    expected_desc = expected.get('job', {}).get('description', '') or ''
    if actual_desc and expected_desc:
        # Simple keyword matching
        keywords = expected_desc.lower().split()
        matches = sum(1 for keyword in keywords if keyword in actual_desc.lower())
        if matches > 0:
            score += min(1.0, matches / len(keywords))
    total_fields += 1
    
    return score / total_fields

async def test_edge_cases():
    """Test edge cases and error handling"""
    from adapters.phone import extract_intent_from_text
    
    print(f"\n🔍 Testing Edge Cases")
    print("=" * 60)
    
    edge_cases = [
        "Hello, how are you?",  # No job request
        "I need help with something",  # Vague request
        "My name is Bob and I'm at 123 Street",  # No job type
        "I have a plumbing emergency",  # No details
        "",  # Empty string
    ]
    
    for i, text in enumerate(edge_cases, 1):
        print(f"\nEdge Case {i}: '{text}'")
        try:
            result = await extract_intent_from_text(text)
            print(f"Result: {json.dumps(result, indent=2)}")
        except Exception as e:
            print(f"Error: {e}")

async def main():
    """Run all tests"""
    try:
        # Test main intent extraction
        passed, scores = await test_intent_extraction()
        
        # Test edge cases
        await test_edge_cases()
        
        print(f"\n🎉 Test suite completed!")
        print(f"Overall Performance: {passed}/{len(TEST_CASES)} tests passed")
        
    except Exception as e:
        print(f"❌ Test suite failed: {e}")

if __name__ == "__main__":
    asyncio.run(main()) 