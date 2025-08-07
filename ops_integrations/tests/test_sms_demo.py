#!/usr/bin/env python3
"""
Demo script for SMS intent classification system
"""
import os
import sys

# Mock environment variables for demo
os.environ['TWILIO_ACCOUNT_SID'] = 'test_sid'
os.environ['TWILIO_AUTH_TOKEN'] = 'test_token'
os.environ['TWILIO_FROM_NUMBER'] = '+1234567890'
os.environ['OPENAI_API_KEY'] = 'test_key'

def demo_conversation_flow():
    """Demo back-and-forth messaging with intent classification."""
    print("🚀 SMS Conversation Flow Demo\n")
    
    # Conversation scenarios
    conversations = [
        {
            "scenario": "Emergency Plumbing Issue",
            "messages": [
                "my pipe just burst and there's water everywhere!",
                "yes it's flooding my basement right now",
                "123 Main St, Anytown",
                "as soon as possible"
            ]
        },
        {
            "scenario": "Clogged Toilet",
            "messages": [
                "my toilet won't flush and it's backing up",
                "toilet",
                "it's overflowing",
                "kitchen bathroom",
                "today if possible"
            ]
        },
        {
            "scenario": "Leaking Faucet",
            "messages": [
                "I have a dripping faucet in my kitchen",
                "kitchen sink",
                "just dripping slowly",
                "456 Oak Ave, Somewhere",
                "tomorrow morning"
            ]
        },
        {
            "scenario": "Installation Request",
            "messages": [
                "I need to install a new water heater",
                "basement",
                "water heater",
                "789 Pine St, Elsewhere",
                "next week"
            ]
        }
    ]
    
    try:
        from adapters.sms import SMSAdapter
        from flows import intents
        from prompts.prompt_layer import FOLLOW_UP_PROMPTS
        
        sms = SMSAdapter()
        
        print("📋 Available Intent Tags:")
        tags = intents.get_intent_tags()
        for i, tag in enumerate(tags, 1):
            print(f"  {i}. {tag}")
        
        print(f"\n💬 Testing {len(conversations)} conversation scenarios:")
        print("=" * 80)
        
        for conv_idx, conversation in enumerate(conversations, 1):
            print(f"\n🔸 Scenario {conv_idx}: {conversation['scenario']}")
            print("-" * 60)
            
            # Track conversation state
            conversation_state = {
                "intent": None,
                "details_collected": [],
                "step": 0
            }
            
            for msg_idx, customer_message in enumerate(conversation['messages'], 1):
                print(f"\n📱 Message {msg_idx}:")
                print(f"   Customer: '{customer_message}'")
                
                # Simulate intent classification (first message only)
                if msg_idx == 1:
                    if "burst" in customer_message.lower() or "flooding" in customer_message.lower():
                        intent = "EMERGENCY_FIX"
                    elif "toilet" in customer_message.lower() and "flush" in customer_message.lower():
                        intent = "CLOG_BLOCKAGE"
                    elif "dripping" in customer_message.lower() or "leak" in customer_message.lower():
                        intent = "LEAKING_FIXTURE"
                    elif "install" in customer_message.lower() or "new" in customer_message.lower():
                        intent = "INSTALL_REQUEST"
                    else:
                        intent = "GENERAL_INQUIRY"
                    
                    conversation_state["intent"] = intent
                    print(f"   🎯 Classified Intent: {intent}")
                
                # Generate contextual response based on conversation flow
                response = generate_conversation_response(
                    customer_message, 
                    conversation_state, 
                    msg_idx,
                    FOLLOW_UP_PROMPTS
                )
                
                print(f"   🤖 Response: '{response}'")
                
                # Update conversation state
                conversation_state["step"] = msg_idx
                conversation_state["details_collected"].append(customer_message)
            
            # Show final booking summary
            print(f"\n   📋 Booking Summary:")
            print(f"      Intent: {conversation_state['intent']}")
            print(f"      Details: {len(conversation_state['details_collected'])} pieces collected")
            print(f"      Status: Ready for scheduling")
        
        print("\n" + "=" * 80)
        print("✅ Conversation flow demo completed!")
        print("\n📋 Key Features Demonstrated:")
        print("• Intent classification on first message")
        print("• Contextual follow-up questions")
        print("• Progressive detail collection")
        print("• Conversation state tracking")
        print("• Booking preparation")
        
    except Exception as e:
        print(f"❌ Error in demo: {e}")

def generate_conversation_response(message, state, step, follow_up_prompts):
    """Generate contextual responses based on conversation flow."""
    intent = state["intent"]
    
    if step == 1:
        # First message - use the follow-up prompt
        if intent == "EMERGENCY_FIX":
            return "This sounds urgent—are you experiencing flooding or major leaks right now? If it's a true emergency, please call our hotline at (555) 123-4567. Otherwise reply with 'OK' to continue via SMS."
        elif intent == "CLOG_BLOCKAGE":
            return "Which fixture is affected (toilet, sink, shower)? Is it overflowing, slow-draining, or fully backed up?"
        elif intent == "LEAKING_FIXTURE":
            return "Which fixture is leaking (toilet, sink, shower)? Is it dripping, running continuously, or actively leaking?"
        elif intent == "INSTALL_REQUEST":
            return "Where would you like to install the new fixture (kitchen, bathroom, laundry)? What type of fixture (toilet, sink, shower)?"
        else:
            return "What type of general inquiry do you have (plumbing, heating, cooling)?"
    
    elif step == 2:
        # Second message - ask for location
        if "emergency" in message.lower() or "flooding" in message.lower():
            return "What's your address? We'll dispatch someone immediately."
        else:
            return "What's your address? We'll need this to schedule the service."
    
    elif step == 3:
        # Third message - ask for timing preference
        return "When would you like us to come? (today, tomorrow, specific time)"
    
    elif step == 4:
        # Fourth message - confirm details and offer scheduling
        address = state['details_collected'][2] if len(state['details_collected']) > 2 else "your address"
        timing = state['details_collected'][3] if len(state['details_collected']) > 3 else "at your preferred time"
        return f"Perfect! I've got your {intent.replace('_', ' ').lower()} at {address}. We can arrive {timing}. Reply 'CONFIRM' to book or 'CHANGE' to adjust."
    
    else:
        # Additional messages - handle scheduling
        if "confirm" in message.lower():
            return "Great! Your appointment is confirmed. We'll send you a reminder 1 hour before arrival. Thank you for choosing our services!"
        else:
            return "I understand you'd like to make changes. What would you like to adjust?"

if __name__ == "__main__":
    demo_conversation_flow() 