"""
Salon Response Generator - Bold Wings Hair Salon
Pre-generated warm, culturally authentic responses for instant customer service
"""

import json
import random
import logging
from typing import Dict, List, Any
import os

# Import OpenAI only if available
try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    OpenAI = None

class SalonResponseGenerator:
    """Generate and manage warm, authentic responses for Bold Wings salon"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # Pre-generated responses for instant use (no API delays)
        self.confirmation_responses = [
            "Perfect, sis! I can absolutely help you with {service_name}. The price is CAD ${price}. When would work best for you, {customer_name}?",
            "Yes queen! {service_name} is one of my favorites to do. That'll be CAD ${price}. What day were you thinking, love?",
            "Oh honey, {service_name} is going to look stunning on you! It's CAD ${price}. When can we get you in the chair, {customer_name}?",
            "Absolutely, darling! I'd love to do your {service_name}. That's CAD ${price}. What's your schedule looking like, hun?",
            "Girl, yes! {service_name} is perfect for you. The investment is CAD ${price}. When would you like to come through, {customer_name}?",
            "Of course, love! {service_name} will have you looking like the queen you are. It's CAD ${price}. What day works for you?",
            "Beautiful choice, sis! {service_name} is CAD ${price}. When can we make some magic happen, {customer_name}?",
            "You know I got you covered with that {service_name}! That's CAD ${price}. What time frame are you working with, hun?",
            "Yasss! {service_name} is going to be gorgeous on you. The price is CAD ${price}. When should we book you in, darling?",
            "I'm so excited to do your {service_name}! It'll be CAD ${price}. What's the best day for you, {customer_name}?",
            "Honey, {service_name} is one of my specialties! That comes to CAD ${price}. When can we get you scheduled, love?",
            "Girl, you picked the perfect service! {service_name} for CAD ${price}. What day can we make you feel fabulous, {customer_name}?",
            "Oh I love doing {service_name}! The cost is CAD ${price}. When would you like to come in and get pampered, sis?",
            "That's a beautiful choice, queen! {service_name} is CAD ${price}. What works best in your schedule, hun?",
            "Absolutely, {customer_name}! {service_name} will look amazing. It's CAD ${price}. When can we get you booked, darling?",
            "Yes love! {service_name} is going to have you feeling like royalty. That's CAD ${price}. What day should we reserve for you?",
            "Perfect pick, sis! {service_name} for CAD ${price}. When would you like to come through and get gorgeous, {customer_name}?",
            "I can definitely hook you up with that {service_name}! It's CAD ${price}. What's your availability looking like, hun?",
            "Beautiful! {service_name} is one of my favorites to create. The price is CAD ${price}. When can we make this happen, love?",
            "Girl, {service_name} is going to be stunning! That'll be CAD ${price}. What day can we get you feeling fabulous, {customer_name}?"
        ]
        
        self.greeting_responses = [
            "Hey beautiful! Welcome to Bold Wings! I'm so happy you called, love. How can I help you today?",
            "Hello queen! Thank you for calling Bold Wings Hair Salon. What can I do for you today, sis?",
            "Hi darling! Bold Wings here, where we make magic happen! How can I serve you today, hun?",
            "Hey love! Welcome to Bold Wings! I'm excited to help you today. What are you looking for?",
            "Hello gorgeous! You've reached Bold Wings Hair Salon. What beautiful service can I help you with today?",
            "Hi sis! Bold Wings salon speaking. What can we do to make you feel fabulous today?",
            "Hey hun! Thank you for calling Bold Wings. I'm here to help - what's on your mind today?",
            "Hello beautiful! Welcome to Bold Wings where every queen gets royal treatment. How can I help you?",
            "Hi love! Bold Wings Hair Salon here. What amazing transformation are we planning today?",
            "Hey darling! You've reached Bold Wings. I'm so excited to help you today - what are you thinking?"
        ]
        
        self.scheduling_responses = [
            "Perfect! Let me check our availability. We're open Monday through Thursday 7 AM to 11 PM, and Friday-Saturday 7 PM to 11 PM. What works best for you, {customer_name}?",
            "Great! I can get you scheduled, love. Our hours are Mon-Thu 7 AM to 11 PM, Fri-Sat 7 PM to 11 PM. What day were you thinking?",
            "Wonderful! Let me see what we have available, sis. We're open Monday-Thursday 7 to 11, Friday-Saturday 7 PM to 11 PM. What's your preference?",
            "Excellent choice, hun! Our schedule is Mon-Thu 7 AM-11 PM, Fri-Sat 7 PM-11 PM. When would work for you?",
            "Beautiful! I'll get you set up, darling. We're available Monday through Thursday 7 to 11, weekends 7 PM to 11 PM. What suits you?",
            "Perfect timing! Our hours are Monday-Thursday 7 AM to 11 PM, Friday-Saturday evenings 7 to 11. What day works, love?",
            "Great! Let me book you in, queen. We're open Mon-Thu all day 7-11, Fri-Sat nights 7-11. What's your schedule like?",
            "Awesome! I can definitely fit you in, sis. Monday through Thursday we're 7 AM to 11 PM, weekends 7 PM to 11 PM. Your preference?",
            "Wonderful! Our availability is Mon-Thu 7 AM-11 PM, Fri-Sat 7 PM-11 PM. What day works best for you, {customer_name}?",
            "Perfect! Let me check the books, hun. We're here Monday-Thursday 7 to 11, Friday-Saturday evenings. When can you come through?"
        ]
        
        self.unclear_responses = [
            "I want to make sure I understand exactly what you need, love. Could you tell me a bit more about what service you're looking for?",
            "Help me help you better, sis. What kind of hair service were you thinking about today?",
            "I didn't catch that clearly, hun. Could you let me know what style you have in mind?",
            "Sorry darling, I want to make sure I get this right. What service can I help you with today?",
            "Let me make sure I understand, queen. What hair service are you interested in?",
            "I want to give you exactly what you need, love. Could you repeat what service you're looking for?",
            "Help me out, sis - what kind of hair magic are we talking about today?",
            "I didn't quite get that, hun. What service were you hoping to book?",
            "Let me make sure I heard you right, beautiful. What can we do for your hair today?",
            "Sorry love, could you say that again? I want to make sure I help you with the right service."
        ]
        
        self.goodbye_responses = [
            "Perfect! You're all set, {customer_name}. I'll see you soon, love. Have a beautiful day!",
            "Wonderful! Can't wait to see you, sis. Take care and I'll talk to you soon!",
            "All booked, queen! Looking forward to making you feel fabulous. Have a great day, hun!",
            "You're scheduled, darling! I'm excited to work with you. See you soon, beautiful!",
            "Perfect! Everything's confirmed, {customer_name}. Have a lovely day, love!",
            "All set, sis! Can't wait to create something beautiful for you. Take care!",
            "Booked and ready, hun! I'll see you soon. Have an amazing day, queen!",
            "You're all good to go, love! Looking forward to seeing you. Take care, beautiful!",
            "Perfect! We're all set, {customer_name}. Have a wonderful day, darling!",
            "All confirmed, sis! I'm excited to work on your hair. See you soon, hun!"
        ]
        
        # Initialize OpenAI client for dynamic generation if needed
        self.openai_client = None
        if OPENAI_AVAILABLE and os.getenv('OPENAI_API_KEY'):
            try:
                self.openai_client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
            except Exception as e:
                self.logger.warning(f"Could not initialize OpenAI client: {e}")
    
    def get_confirmation_response(self, service_name: str, price: float, customer_name: str = "love") -> str:
        """Get a warm confirmation response for a service booking"""
        response = random.choice(self.confirmation_responses)
        return response.format(
            service_name=service_name,
            price=int(price),
            customer_name=customer_name
        )
    
    def get_greeting_response(self) -> str:
        """Get a warm greeting response"""
        return random.choice(self.greeting_responses)
    
    def get_scheduling_response(self, customer_name: str = "love") -> str:
        """Get a scheduling response"""
        response = random.choice(self.scheduling_responses)
        return response.format(customer_name=customer_name)
    
    def get_unclear_response(self) -> str:
        """Get a response for unclear customer input"""
        return random.choice(self.unclear_responses)
    
    def get_goodbye_response(self, customer_name: str = "love") -> str:
        """Get a goodbye response"""
        response = random.choice(self.goodbye_responses)
        return response.format(customer_name=customer_name)
    
    def generate_custom_responses(self, count: int = 20) -> List[str]:
        """Generate custom responses using GPT if available"""
        if not self.openai_client:
            self.logger.warning("OpenAI client not available, returning pre-generated responses")
            return self.confirmation_responses[:count]
        
        prompt = """You are writing text responses for an African hair braiding shop. The tone should be warm, welcoming, and natural — like how an auntie, sister, or trusted stylist would speak with her clients. Avoid robotic or overly formal wording. Use casual greetings, terms of endearment (sis, love, queen, hun, darling, etc.), and a touch of cultural flair if natural.

Task: Generate 20 different short responses that confirm the [Service Name] & CAD $[Price], and ask when [Customer Name] would like to book.

Format output as a JSON array of strings. Use {service_name}, {price}, and {customer_name} as placeholders."""
        
        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are a helpful assistant that generates authentic, warm responses for an African hair salon."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.9,
                max_tokens=2000
            )
            
            content = response.choices[0].message.content.strip()
            
            # Try to parse JSON response
            try:
                responses = json.loads(content)
                if isinstance(responses, list) and len(responses) >= count:
                    self.logger.info(f"Generated {len(responses)} custom responses")
                    return responses[:count]
            except json.JSONDecodeError:
                self.logger.warning("Could not parse GPT response as JSON")
            
        except Exception as e:
            self.logger.error(f"Failed to generate custom responses: {e}")
        
        # Fallback to pre-generated responses
        return self.confirmation_responses[:count]
    
    def get_response_for_context(self, context: str, **kwargs) -> str:
        """Get appropriate response based on conversation context"""
        context_lower = context.lower()
        
        if any(word in context_lower for word in ['hello', 'hi', 'hey', 'greeting']):
            return self.get_greeting_response()
        elif any(word in context_lower for word in ['schedule', 'book', 'appointment', 'when']):
            return self.get_scheduling_response(kwargs.get('customer_name', 'love'))
        elif any(word in context_lower for word in ['goodbye', 'bye', 'thanks', 'thank you']):
            return self.get_goodbye_response(kwargs.get('customer_name', 'love'))
        elif any(word in context_lower for word in ['unclear', 'repeat', 'what', 'sorry']):
            return self.get_unclear_response()
        elif all(key in kwargs for key in ['service_name', 'price']):
            return self.get_confirmation_response(
                kwargs['service_name'], 
                kwargs['price'], 
                kwargs.get('customer_name', 'love')
            )
        else:
            return self.get_greeting_response()
    
    def get_all_responses(self) -> Dict[str, List[str]]:
        """Get all pre-generated responses for backup/export"""
        return {
            'confirmations': self.confirmation_responses,
            'greetings': self.greeting_responses,
            'scheduling': self.scheduling_responses,
            'unclear': self.unclear_responses,
            'goodbyes': self.goodbye_responses
        }

# Global instance for instant access
salon_response_generator = SalonResponseGenerator()

# Quick access functions
def get_salon_confirmation(service_name: str, price: float, customer_name: str = "love") -> str:
    """Quick function to get confirmation response"""
    return salon_response_generator.get_confirmation_response(service_name, price, customer_name)

def get_salon_greeting() -> str:
    """Quick function to get greeting response"""
    return salon_response_generator.get_greeting_response()

def get_salon_scheduling(customer_name: str = "love") -> str:
    """Quick function to get scheduling response"""
    return salon_response_generator.get_scheduling_response(customer_name)

def get_salon_unclear() -> str:
    """Quick function to get unclear response"""
    return salon_response_generator.get_unclear_response()

def get_salon_goodbye(customer_name: str = "love") -> str:
    """Quick function to get goodbye response"""
    return salon_response_generator.get_goodbye_response(customer_name)

if __name__ == "__main__":
    # Test the response generator
    generator = SalonResponseGenerator()
    
    print("=== Testing Salon Response Generator ===")
    print("\n1. Confirmation Response:")
    print(generator.get_confirmation_response("Knotless Braids", 250, "Sarah"))
    
    print("\n2. Greeting Response:")
    print(generator.get_greeting_response())
    
    print("\n3. Scheduling Response:")
    print(generator.get_scheduling_response("Maria"))
    
    print("\n4. Custom Generated Responses (first 3):")
    custom_responses = generator.generate_custom_responses(3)
    for i, response in enumerate(custom_responses[:3], 1):
        print(f"   {i}. {response}")
    
    print("\n=== Response Generator Ready! ===")
