import asyncio
import base64
import json
import math
import os
import random
import sys

try:
    import websockets
except ImportError:
    print("Missing dependency: websockets. Install with: python3 -m pip install --user websockets", file=sys.stderr)
    sys.exit(1)

WS_URL = os.environ.get("WS_URL", "ws://127.0.0.1:5001/stream?callSid=TESTCALL")
CALL_SID = os.environ.get("CALL_SID", "TESTCALL")
SAMPLE_RATE = int(os.environ.get("SAMPLE_RATE", "8000"))
FRAME_MS = 20
SAMPLES_PER_FRAME = SAMPLE_RATE * FRAME_MS // 1000
BYTES_PER_SAMPLE = 2  # PCM16
FRAME_BYTES = SAMPLES_PER_FRAME * BYTES_PER_SAMPLE
TOTAL_SECONDS = float(os.environ.get("TOTAL_SECONDS", "4.0"))
NUM_FRAMES = int(TOTAL_SECONDS * 1000 // FRAME_MS)


def generate_pcm16_frame(t: int) -> bytes:
    """Generate a pseudo speech-like PCM16 frame.
    Mix a couple of low-frequency tones plus noise to help VAD trigger, at 8kHz.
    """
    data = bytearray()
    # Phase accumulators for a couple of tones
    # Fundamental ~180 Hz and ~220 Hz
    for n in range(SAMPLES_PER_FRAME):
        # Time index across frames
        idx = t * SAMPLES_PER_FRAME + n
        # Sine components
        s1 = math.sin(2 * math.pi * 180.0 * (idx / SAMPLE_RATE))
        s2 = math.sin(2 * math.pi * 220.0 * (idx / SAMPLE_RATE))
        # Add small random noise
        noise = (random.random() - 0.5) * 0.1
        sample = 0.4 * s1 + 0.4 * s2 + noise
        # Soft clipping
        if sample > 1.0:
            sample = 1.0
        if sample < -1.0:
            sample = -1.0
        # Convert to int16 little-endian
        val = int(sample * 32767)
        data.extend(val.to_bytes(2, byteorder="little", signed=True))
    return bytes(data)


async def send_stream():
    print(f"Connecting to {WS_URL}")
    async with websockets.connect(WS_URL, max_size=2**22) as ws:
        # Send 'connected' event
        connected_evt = {"event": "connected"}
        await ws.send(json.dumps(connected_evt))
        # Send 'start' event with L16 format so server treats payload as PCM16
        start_evt = {
            "event": "start",
            "start": {
                "accountSid": "ACXXXXXXXX",
                "streamSid": "MEXXXXXXXX",
                "callSid": CALL_SID,
                "mediaFormat": {
                    "encoding": "audio/l16;rate=8000",
                    "sampleRate": SAMPLE_RATE,
                    "channels": 1
                }
            }
        }
        await ws.send(json.dumps(start_evt))
        print("Sent start event")

        # Send NUM_FRAMES frames (~4s)
        for i in range(NUM_FRAMES):
            frame = generate_pcm16_frame(i)
            assert len(frame) == FRAME_BYTES
            payload_b64 = base64.b64encode(frame).decode("ascii")
            media_evt = {"event": "media", "media": {"payload": payload_b64}}
            await ws.send(json.dumps(media_evt))
            if (i + 1) % 25 == 0:
                print(f"Sent {(i + 1) * FRAME_MS / 1000:.1f}s of audio")
            # Optional: simulate real-time
            # await asyncio.sleep(FRAME_MS / 1000)

        # Stop event
        stop_evt = {"event": "stop"}
        await ws.send(json.dumps(stop_evt))
        print("Sent stop event; closing")


if __name__ == "__main__":
    asyncio.run(send_stream()) 