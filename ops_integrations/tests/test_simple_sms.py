#!/usr/bin/env python3
"""
Simple SMS test
"""
from dotenv import load_dotenv
load_dotenv('../.env')

from adapters.sms import SMSAdapter

def test_simple_sms():
    sms = SMSAdapter()
    print(f"From number: {sms.from_number}")
    print(f"SMS enabled: {sms.enabled}")
    
    # Test phone number
    test_phone = input("Enter phone number to test (+1234567890): ").strip()
    
    if not test_phone:
        print("No phone number provided")
        return
    
    # Send test message
    message = "🚰 Plumbing AGI Test: This is a real SMS from ClickSend! Reply to test the intent classification system."
    print(f"Sending: '{message}' to {test_phone}")
    
    result = sms.send_sms(test_phone, message)
    print(f"Result: {result}")
    
    if result.get('success'):
        print("✅ SMS sent! Check your phone.")
        print(f"Raw Response: {result.get('raw_response')}")
    else:
        print(f"❌ Failed: {result.get('error')}")

if __name__ == "__main__":
    test_simple_sms() 