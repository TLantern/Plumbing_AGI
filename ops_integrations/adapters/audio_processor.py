import asyncio
import logging
import time
import struct
from typing import Optional, Dict, Any, Callable
from collections import defaultdict
import httpx

try:
    import webrtcvad
    WEBRTCVAD_AVAILABLE = True
except ImportError:
    WEBRTCVAD_AVAILABLE = False
    webrtcvad = None

logger = logging.getLogger(__name__)

class AudioProcessor:
    """Handles audio processing, Voice Activity Detection (VAD), and speech segmentation"""
    
    def __init__(self, sample_rate: int = 8000, frame_duration_ms: int = 30):
        self.sample_rate = sample_rate
        self.frame_duration_ms = frame_duration_ms
        self.frame_size = int(sample_rate * frame_duration_ms / 1000)
        
        # Initialize VAD
        if WEBRTCVAD_AVAILABLE:
            try:
                self.vad = webrtcvad.Vad(2)  # Aggressiveness level 2
            except Exception:
                self.vad = self._create_dummy_vad()
        else:
            self.vad = self._create_dummy_vad()
    
    def _create_dummy_vad(self):
        """Create a dummy VAD for when webrtcvad is not available"""
        class DummyVAD:
            def is_speech(self, frame_bytes: bytes, sample_rate: int) -> bool:
                return False
        return DummyVAD()
        
        # Audio buffers per call
        self.audio_buffers: Dict[str, bytearray] = defaultdict(bytearray)
        self.vad_states: Dict[str, Dict[str, Any]] = defaultdict(lambda: {
            'speaking': False,
            'silence_start': None,
            'last_speech_time': 0,
            'has_received_media': False,
            'buffer_start_time': None
        })
        
        # Configuration
        self.silence_threshold_ms = 1000  # 1 second of silence to end speech
        self.min_speech_duration_ms = 500  # Minimum speech duration
        self.max_buffer_duration_ms = 10000  # Maximum buffer duration (10 seconds)
        self.time_based_flush_ms = 3000  # Flush every 3 seconds regardless of VAD
        
    def process_audio(self, call_sid: str, audio: bytes) -> None:
        """Process incoming audio data and update VAD state"""
        try:
            # Update VAD state
            vad_state = self.vad_states[call_sid]
            vad_state['has_received_media'] = True
            
            # Add audio to buffer
            self.audio_buffers[call_sid].extend(audio)
            
            # Process audio in frames (but don't consume all data)
            buffer = self.audio_buffers[call_sid]
            frame_size_bytes = self.frame_size * 2  # 16-bit samples
            
            # Only process complete frames, leave remainder in buffer
            complete_frames = len(buffer) // frame_size_bytes
            if complete_frames > 0:
                for i in range(complete_frames):
                    start_idx = i * frame_size_bytes
                    end_idx = start_idx + frame_size_bytes
                    frame = buffer[start_idx:end_idx]
                    
                    # Check if frame contains speech
                    is_speech = self.vad.is_speech(frame, self.sample_rate)
                    self._update_vad_state(call_sid, is_speech)
                
                # Remove processed frames from buffer
                processed_bytes = complete_frames * frame_size_bytes
                buffer[:processed_bytes] = b''
            
            # Log VAD state periodically
            current_time = time.time()
            if current_time - vad_state.get('last_log_time', 0) > 1.0:
                vad_state['last_log_time'] = current_time
                buffer_ms = len(self.audio_buffers[call_sid]) * 1000 // (self.sample_rate * 2)
                logger.info(f"🎧 Listening ({call_sid}): buffer={buffer_ms}ms, speaking={vad_state['speaking']}, sample_rate={self.sample_rate}")
                
        except Exception as e:
            logger.error(f"Audio processing error for {call_sid}: {e}")
    
    def _update_vad_state(self, call_sid: str, is_speech: bool) -> None:
        """Update VAD state based on speech detection"""
        vad_state = self.vad_states[call_sid]
        current_time = time.time()
        
        if is_speech:
            vad_state['speaking'] = True
            vad_state['last_speech_time'] = current_time
            vad_state['silence_start'] = None
        else:
            # Check if we should transition to silence
            if vad_state['speaking']:
                if vad_state['silence_start'] is None:
                    vad_state['silence_start'] = current_time
                elif (current_time - vad_state['silence_start']) * 1000 >= self.silence_threshold_ms:
                    vad_state['speaking'] = False
                    vad_state['silence_start'] = None
    
    def should_flush_buffer(self, call_sid: str) -> bool:
        """Determine if audio buffer should be flushed for processing"""
        vad_state = self.vad_states[call_sid]
        buffer = self.audio_buffers[call_sid]
        
        if not buffer:
            return False
        
        current_time = time.time()
        buffer_duration_ms = len(buffer) * 1000 // (self.sample_rate * 2)
        
        # Flush if we have enough audio and speech has ended
        if (buffer_duration_ms >= self.min_speech_duration_ms and 
            not vad_state['speaking'] and 
            vad_state['last_speech_time'] > 0):
            return True
        
        # Time-based flush to prevent buffer overflow
        if buffer_duration_ms >= self.time_based_flush_ms:
            return True
        
        # Maximum buffer duration reached
        if buffer_duration_ms >= self.max_buffer_duration_ms:
            return True
        
        return False
    
    def get_and_clear_buffer(self, call_sid: str) -> Optional[bytes]:
        """Get current audio buffer and clear it"""
        buffer = self.audio_buffers[call_sid]
        if not buffer:
            return None
        
        audio_data = bytes(buffer)
        buffer.clear()
        
        # Reset VAD state
        vad_state = self.vad_states[call_sid]
        vad_state['speaking'] = False
        vad_state['silence_start'] = None
        
        return audio_data
    
    def get_buffer_duration_ms(self, call_sid: str) -> int:
        """Get current buffer duration in milliseconds"""
        buffer = self.audio_buffers[call_sid]
        return len(buffer) * 1000 // (self.sample_rate * 2)
    
    def cleanup_call(self, call_sid: str) -> None:
        """Clean up resources for a call"""
        self.audio_buffers.pop(call_sid, None)
        self.vad_states.pop(call_sid, None)
    
    def get_vad_state(self, call_sid: str) -> Dict[str, Any]:
        """Get current VAD state for a call"""
        return self.vad_states[call_sid].copy() 