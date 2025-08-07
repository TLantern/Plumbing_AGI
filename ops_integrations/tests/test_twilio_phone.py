#!/usr/bin/env python3
"""
Test Twilio Phone Adapter with simulated audio packets
"""
import asyncio
import json
import base64
import websockets
import logging
from dotenv import load_dotenv
import sys
import os

# Add parent directory to path to import adapters
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

load_dotenv('../.env')

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TwilioPhoneTester:
    def __init__(self, server_url="ws://localhost:8000/stream"):
        self.server_url = server_url
        self.call_sid = "test_call_12345"
        
    async def test_websocket_connection(self):
        """Test basic WebSocket connection"""
        try:
            uri = f"{self.server_url}?callSid={self.call_sid}"
            logger.info(f"Connecting to {uri}")
            
            async with websockets.connect(uri) as websocket:
                logger.info("✅ WebSocket connection established")
                
                # Test 1: Send start event
                await self.send_start_event(websocket)
                await asyncio.sleep(1)
                
                # Test 2: Send media packets with simulated audio
                await self.send_media_packets(websocket)
                await asyncio.sleep(1)
                
                # Test 3: Send stop event
                await self.send_stop_event(websocket)
                await asyncio.sleep(1)
                
                logger.info("✅ All test packets sent successfully")
                
        except Exception as e:
            logger.error(f"❌ WebSocket test failed: {e}")
            raise
    
    async def send_start_event(self, websocket):
        """Send stream start event"""
        start_event = {
            "event": "start",
            "start": {
                "accountSid": "AC1234567890abcdef",
                "callSid": self.call_sid,
                "mediaFormat": {
                    "type": "audio",
                    "channels": 1,
                    "rate": 8000
                }
            }
        }
        await websocket.send(json.dumps(start_event))
        logger.info("📤 Sent start event")
    
    async def send_media_packets(self, websocket):
        """Send simulated audio media packets"""
        # Create some dummy audio data (silence)
        dummy_audio = b'\x00' * 160  # 20ms of silence at 8kHz
        
        for i in range(5):  # Send 5 packets
            media_event = {
                "event": "media",
                "media": {
                    "payload": base64.b64encode(dummy_audio).decode('utf-8'),
                    "track": "inbound_track",
                    "chunk": i + 1,
                    "timestamp": str(i * 20)  # 20ms intervals
                }
            }
            await websocket.send(json.dumps(media_event))
            logger.info(f"📤 Sent media packet {i + 1}")
            await asyncio.sleep(0.1)  # Small delay between packets
    
    async def send_stop_event(self, websocket):
        """Send stream stop event"""
        stop_event = {
            "event": "stop",
            "stop": {
                "accountSid": "AC1234567890abcdef",
                "callSid": self.call_sid
            }
        }
        await websocket.send(json.dumps(stop_event))
        logger.info("📤 Sent stop event")
    
    async def test_voice_webhook(self):
        """Test the voice webhook endpoint"""
        import httpx
        
        webhook_url = "http://localhost:8000/voice"
        webhook_data = {
            "CallSid": self.call_sid,
            "From": "+1234567890",
            "To": "+0987654321",
            "Direction": "inbound"
        }
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(webhook_url, data=webhook_data)
                logger.info(f"📞 Voice webhook response status: {response.status_code}")
                logger.info(f"📞 Voice webhook response: {response.text[:200]}...")
                return response.status_code == 200
        except Exception as e:
            logger.error(f"❌ Voice webhook test failed: {e}")
            return False

async def main():
    """Run all tests"""
    tester = TwilioPhoneTester()
    
    print("🧪 Testing Twilio Phone Adapter")
    print("=" * 50)
    
    # Test 1: Voice webhook
    print("\n1. Testing Voice Webhook...")
    webhook_success = await tester.test_voice_webhook()
    if webhook_success:
        print("✅ Voice webhook test passed")
    else:
        print("❌ Voice webhook test failed")
    
    # Test 2: WebSocket connection and audio packets
    print("\n2. Testing WebSocket Connection and Audio Packets...")
    try:
        await tester.test_websocket_connection()
        print("✅ WebSocket and audio packet tests passed")
    except Exception as e:
        print(f"❌ WebSocket test failed: {e}")
    
    print("\n🎉 Test suite completed!")

if __name__ == "__main__":
    asyncio.run(main()) 