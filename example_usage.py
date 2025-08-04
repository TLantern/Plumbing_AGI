#!/usr/bin/env python3
"""
Example: How to use the Contact Capture System for Plumbing AGI
"""

from ops_integrations.contact_capture import (
    phone_rang, 
    sms_received, 
    email_received, 
    website_form_submitted, 
    got_referral
)

# Example 1: Phone rings
print("📞 Phone rings from 555-999-1234...")
result = phone_rang("555-999-1234", "Sarah Johnson", "Sounds urgent, water leak")
print(f"Result: {result['message']}")
print(f"Contact ID: {result['contact_id']}")
print(f"Customer: {result['name']}")
print()

# Example 2: SMS received  
print("💬 SMS received...")
result = sms_received("555-888-7777", "Help! Toilet overflowing!", "Mike Wilson")
print(f"Result: {result['message']}")
print(f"Contact ID: {result['contact_id']}")
print()

# Example 3: Email received
print("📧 Email received...")
result = email_received("homeowner@house.com", "Emergency Plumbing", "Lisa Davis", "Basement flooding!")
print(f"Result: {result['message']}")
print()

# Example 4: Website form submitted
print("🌐 Website form submitted...")
result = website_form_submitted("Tom Rodriguez", "tom@email.com", "555-444-3333", "Need drain cleaning")
print(f"Result: {result['message']}")
print()

# Example 5: Got a referral
print("👥 Referral received...")
result = got_referral("Jennifer Smith", "555-222-1111", "jen@email.com", "Mary Johnson")
print(f"Result: {result['message']}")
print()

print("✅ All contacts captured successfully!")
print("Check customer_inquiries_backup.json for saved data") 