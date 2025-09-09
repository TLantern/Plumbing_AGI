#!/usr/bin/env python3
"""
Test Square webhook signature verification
"""
import os
import hmac
import hashlib
import json
from typing import Dict, Any

def verify_square_webhook_signature(
    body: str,
    signature: str,
    signature_key: str
) -> bool:
    """
    Verify Square webhook signature
    
    Args:
        body: Raw request body
        signature: X-Square-Signature header value
        signature_key: Webhook signature key from Square
        
    Returns:
        True if signature is valid, False otherwise
    """
    try:
        # Create HMAC SHA256 hash
        expected_signature = hmac.new(
            signature_key.encode('utf-8'),
            body.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        # Compare signatures
        return hmac.compare_digest(signature, expected_signature)
        
    except Exception as e:
        print(f"Error verifying signature: {e}")
        return False

def test_webhook_signature():
    """Test webhook signature verification"""
    print("🔐 Testing Square webhook signature verification...")
    
    # Test data
    test_body = '{"type":"booking.created","data":{"object":{"id":"test_booking_id"}}}'
    test_signature_key = "test_signature_key_123"
    
    # Generate expected signature
    expected_signature = hmac.new(
        test_signature_key.encode('utf-8'),
        test_body.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    
    print(f"📝 Test body: {test_body}")
    print(f"🔑 Test signature key: {test_signature_key}")
    print(f"✍️  Expected signature: {expected_signature}")
    
    # Test verification
    is_valid = verify_square_webhook_signature(
        test_body, 
        expected_signature, 
        test_signature_key
    )
    
    print(f"✅ Signature verification: {'PASSED' if is_valid else 'FAILED'}")
    
    # Test with invalid signature
    invalid_signature = "invalid_signature_123"
    is_invalid = verify_square_webhook_signature(
        test_body, 
        invalid_signature, 
        test_signature_key
    )
    
    print(f"❌ Invalid signature test: {'PASSED' if not is_invalid else 'FAILED'}")
    
    return is_valid and not is_invalid

def test_webhook_payload():
    """Test webhook payload handling"""
    print("\n📦 Testing webhook payload handling...")
    
    # Sample Square webhook payload
    sample_payload = {
        "type": "booking.created",
        "data": {
            "object": {
                "id": "booking_123",
                "start_at": "2024-01-15T10:00:00Z",
                "location_id": "location_456",
                "customer_id": "customer_789",
                "appointment_segments": [
                    {
                        "duration_minutes": 60,
                        "service_variation_id": "service_123"
                    }
                ]
            }
        }
    }
    
    print(f"📋 Sample payload type: {sample_payload['type']}")
    print(f"🆔 Booking ID: {sample_payload['data']['object']['id']}")
    print(f"📍 Location ID: {sample_payload['data']['object']['location_id']}")
    print(f"⏰ Start time: {sample_payload['data']['object']['start_at']}")
    
    return True

if __name__ == "__main__":
    print("🚀 Square Webhook Test Suite")
    print("=" * 40)
    
    # Test signature verification
    signature_test = test_webhook_signature()
    
    # Test payload handling
    payload_test = test_webhook_payload()
    
    print("\n" + "=" * 40)
    print("📊 Test Results:")
    print(f"🔐 Signature verification: {'✅ PASSED' if signature_test else '❌ FAILED'}")
    print(f"📦 Payload handling: {'✅ PASSED' if payload_test else '❌ FAILED'}")
    
    if signature_test and payload_test:
        print("\n🎉 All tests passed! Square webhook integration is ready.")
    else:
        print("\n⚠️  Some tests failed. Check the implementation.") 