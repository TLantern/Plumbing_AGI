#!/usr/bin/env python3
"""
Simple test for phone server
"""
import asyncio
import websockets
import json
import base64

async def test_simple_websocket():
    """Test basic WebSocket connection and message sending"""
    uri = "ws://localhost:8000/stream?callSid=test_call_12345"
    
    try:
        async with websockets.connect(uri) as websocket:
            print("✅ WebSocket connection established")
            
            # Send a simple start event
            start_event = {
                "event": "start",
                "start": {
                    "accountSid": "AC1234567890abcdef",
                    "callSid": "test_call_12345",
                    "mediaFormat": {
                        "type": "audio",
                        "channels": 1,
                        "rate": 8000
                    }
                }
            }
            
            await websocket.send(json.dumps(start_event))
            print("📤 Sent start event")
            
            # Wait a moment
            await asyncio.sleep(1)
            
            # Send a media packet
            dummy_audio = b'\x00' * 160  # 20ms of silence
            media_event = {
                "event": "media",
                "media": {
                    "payload": base64.b64encode(dummy_audio).decode('utf-8'),
                    "track": "inbound_track",
                    "chunk": 1,
                    "timestamp": "0"
                }
            }
            
            await websocket.send(json.dumps(media_event))
            print("📤 Sent media packet")
            
            # Wait a moment
            await asyncio.sleep(1)
            
            # Send stop event
            stop_event = {
                "event": "stop",
                "stop": {
                    "accountSid": "AC1234567890abcdef",
                    "callSid": "test_call_12345"
                }
            }
            
            await websocket.send(json.dumps(stop_event))
            print("📤 Sent stop event")
            
            print("✅ All messages sent successfully")
            
    except Exception as e:
        print(f"❌ Test failed: {e}")
        raise

if __name__ == "__main__":
    print("🧪 Testing Simple WebSocket Connection")
    print("=" * 50)
    
    try:
        asyncio.run(test_simple_websocket())
        print("\n🎉 Test completed successfully!")
    except Exception as e:
        print(f"\n❌ Test failed: {e}") 