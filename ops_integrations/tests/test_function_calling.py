#!/usr/bin/env python3
"""
Debug Function Calling Issue
"""
import asyncio
import json
import sys
import os
from dotenv import load_dotenv
from openai import OpenAI

# Add parent directory to path to import adapters
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

load_dotenv('../../.env')

# Simple function definition
SIMPLE_FUNCTIONS = [
    {
        "type": "function",
        "function": {
            "name": "extract_plumbing_info",
            "description": "Extract plumbing job information from text",
            "parameters": {
                "type": "object",
                "properties": {
                    "job_type": {
                        "type": "string",
                        "enum": ["leak", "water_heater", "clog", "gas_line", "sewer_cam"]
                    },
                    "urgency": {
                        "type": "string", 
                        "enum": ["emergency", "same_day", "flex"]
                    },
                    "customer_name": {"type": "string"},
                    "address": {"type": "string"}
                },
                "required": ["job_type", "urgency"]
            }
        }
    }
]

async def test_simple_function_calling():
    """Test simple function calling"""
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    
    test_text = "Hi, I have a leaky faucet in my kitchen. My name is John Smith and I'm at 123 Main Street. I need this fixed as soon as possible."
    
    print("🧪 Testing Simple Function Calling")
    print("=" * 50)
    print(f"Input: {test_text}")
    
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "user", "content": f"Extract plumbing information from: {test_text}"}
            ],
            tools=SIMPLE_FUNCTIONS,
            tool_choice="auto",
            temperature=0.1
        )
        
        print(f"Response: {response}")
        print(f"Choices: {response.choices}")
        
        if response.choices and response.choices[0].message.tool_calls:
            tool_call = response.choices[0].message.tool_calls[0]
            print(f"Tool call: {tool_call}")
            print(f"Function name: {tool_call.function.name}")
            print(f"Arguments: {tool_call.function.arguments}")
            
            args = json.loads(tool_call.function.arguments)
            print(f"Parsed args: {json.dumps(args, indent=2)}")
        else:
            print("No tool calls made")
            print(f"Message content: {response.choices[0].message.content}")
            
    except Exception as e:
        print(f"Error: {e}")

async def test_original_function():
    """Test the original function calling"""
    from adapters.phone import extract_intent_from_text
    
    test_text = "Hi, I have a leaky faucet in my kitchen. My name is John Smith and I'm at 123 Main Street. I need this fixed as soon as possible."
    
    print("\n🧪 Testing Original Function")
    print("=" * 50)
    print(f"Input: {test_text}")
    
    try:
        result = await extract_intent_from_text(test_text)
        print(f"Result: {json.dumps(result, indent=2)}")
    except Exception as e:
        print(f"Error: {e}")

async def main():
    """Run tests"""
    await test_simple_function_calling()
    await test_original_function()

if __name__ == "__main__":
    asyncio.run(main()) 