#!/usr/bin/env python3
"""
Test speech gate functionality to ensure faster listening after TTS.
"""

import sys
import os
import asyncio
import time
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Add the project root to the path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

from ops_integrations.adapters.phone import _activate_speech_gate, _deactivate_speech_gate_after_delay
from ops_integrations.adapters.phone import vad_states

def test_speech_gate_timing():
    """Test that speech gate timing is optimized for faster listening"""
    
    # Clear any existing state
    vad_states.clear()
    
    call_sid = "test_call_123"
    text = "Hello, this is a test message for speech gate timing."
    
    # Initialize VAD state
    vad_states[call_sid] = {
        'speech_gate_active': False,
        'bot_speaking': False,
        'bot_speech_start_time': 0
    }
    
    print("Testing speech gate timing...")
    print("=" * 50)
    
    # Test speech gate activation
    print(f"Activating speech gate for text: '{text}'")
    asyncio.run(_activate_speech_gate(call_sid, text))
    
    vad_state = vad_states[call_sid]
    print(f"Speech gate active: {vad_state['speech_gate_active']}")
    print(f"Bot speaking: {vad_state['bot_speaking']}")
    print(f"Bot speech start time: {vad_state['bot_speech_start_time']}")
    
    # Wait a bit to simulate TTS playing
    print("Waiting 1 second to simulate TTS...")
    time.sleep(1)
    
    # Check if gate is still active
    print(f"Speech gate still active after 1s: {vad_state['speech_gate_active']}")
    
    # Wait for gate to deactivate
    print("Waiting for speech gate to deactivate...")
    time.sleep(3)  # Should be enough time for the gate to deactivate
    
    print(f"Speech gate active after waiting: {vad_state['speech_gate_active']}")
    print(f"Bot speaking after waiting: {vad_state['bot_speaking']}")
    
    # Verify the improvements
    if not vad_state['speech_gate_active']:
        print("✅ Speech gate deactivated successfully")
        print("✅ Listening should resume immediately after TTS")
        return True
    else:
        print("❌ Speech gate still active - listening may be delayed")
        return False

if __name__ == "__main__":
    success = test_speech_gate_timing()
    sys.exit(0 if success else 1) 