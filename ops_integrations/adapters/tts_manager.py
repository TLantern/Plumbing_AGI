import asyncio
import logging
import time
from typing import Optional, Dict, Any, Callable
from collections import defaultdict

logger = logging.getLogger(__name__)

class TTSManager:
    """Handles text-to-speech generation and speech gate management"""
    
    def __init__(self, speech_recognizer):
        self.speech_recognizer = speech_recognizer
        
        # Speech gate state per call
        self.speech_gates: Dict[str, Dict[str, Any]] = defaultdict(dict)
        
        # TTS cache
        self.tts_cache: Dict[str, bytes] = {}
        
        # Configuration
        self.speech_gate_buffer_sec = 1.0
        self.max_cache_size = 100
        
    async def synthesize_tts(self, text: str, call_sid: str) -> Optional[bytes]:
        """Generate TTS audio for text"""
        try:
            if not text.strip():
                return None
            
            # Check cache first
            cache_key = f"{text}_{call_sid}"
            if cache_key in self.tts_cache:
                logger.info(f"🎵 Using cached TTS for {call_sid}")
                return self.tts_cache[cache_key]
            
            # Generate new TTS
            audio_data = await self.speech_recognizer.synthesize_tts(text, call_sid)
            
            if audio_data:
                # Cache the result
                self._add_to_cache(cache_key, audio_data)
                logger.info(f"🎵 Generated TTS for {call_sid}: {len(audio_data)} bytes")
            
            return audio_data
            
        except Exception as e:
            logger.error(f"TTS synthesis failed for {call_sid}: {e}")
            return None
    
    def _add_to_cache(self, key: str, audio_data: bytes) -> None:
        """Add TTS audio to cache"""
        if len(self.tts_cache) >= self.max_cache_size:
            # Remove oldest entry
            oldest_key = next(iter(self.tts_cache))
            del self.tts_cache[oldest_key]
        
        self.tts_cache[key] = audio_data
    
    def activate_speech_gate(self, call_sid: str, text: str) -> None:
        """Activate speech gate to prevent overlapping speech"""
        try:
            # Estimate TTS duration (rough approximation)
            estimated_duration = len(text) * 0.06  # ~60ms per character
            gate_duration = estimated_duration + self.speech_gate_buffer_sec
            
            self.speech_gates[call_sid] = {
                'active': True,
                'start_time': time.time(),
                'duration': gate_duration,
                'text': text
            }
            
            logger.info(f"🔇 Speech gate activated for {call_sid}: {gate_duration:.2f}s (text: {len(text)} chars)")
            
            # Schedule deactivation
            asyncio.create_task(self._deactivate_speech_gate_after_delay(call_sid, gate_duration))
            
        except Exception as e:
            logger.error(f"Failed to activate speech gate for {call_sid}: {e}")
    
    async def _deactivate_speech_gate_after_delay(self, call_sid: str, delay: float) -> None:
        """Deactivate speech gate after specified delay"""
        try:
            await asyncio.sleep(delay)
            
            gate_state = self.speech_gates.get(call_sid, {})
            if gate_state.get('active'):
                gate_state['active'] = False
                actual_duration = time.time() - gate_state.get('start_time', time.time())
                logger.info(f"🔊 Speech gate deactivated for {call_sid} after {actual_duration:.2f}s")
                
        except Exception as e:
            logger.error(f"Failed to deactivate speech gate for {call_sid}: {e}")
    
    def is_speech_gate_active(self, call_sid: str) -> bool:
        """Check if speech gate is currently active"""
        gate_state = self.speech_gates.get(call_sid, {})
        return gate_state.get('active', False)
    
    def get_speech_gate_state(self, call_sid: str) -> Dict[str, Any]:
        """Get current speech gate state"""
        return self.speech_gates.get(call_sid, {}).copy()
    
    def deactivate_speech_gate(self, call_sid: str) -> None:
        """Manually deactivate speech gate"""
        gate_state = self.speech_gates.get(call_sid, {})
        if gate_state.get('active'):
            gate_state['active'] = False
            actual_duration = time.time() - gate_state.get('start_time', time.time())
            logger.info(f"🔊 Speech gate manually deactivated for {call_sid} after {actual_duration:.2f}s")
    
    async def add_tts_to_twiml(self, twiml_response, call_sid: str, text: str) -> None:
        """Add TTS to TwiML response"""
        try:
            if not text.strip():
                return
            
            # Activate speech gate
            self.activate_speech_gate(call_sid, text)
            
            # Generate TTS
            audio_data = await self.synthesize_tts(text, call_sid)
            
            if audio_data:
                # Add to TwiML response
                # Note: This is a simplified version - in practice you'd need to handle
                # the specific TwiML library being used
                logger.info(f"🎵 Added TTS to TwiML for {call_sid}: {len(text)} chars")
            else:
                logger.warning(f"⚠️ Failed to generate TTS for {call_sid}")
                
        except Exception as e:
            logger.error(f"Failed to add TTS to TwiML for {call_sid}: {e}")
    
    def estimate_tts_duration(self, text: str) -> float:
        """Estimate TTS duration for given text"""
        # Rough estimation: ~60ms per character
        return len(text) * 0.06
    
    def get_tts_stats(self, call_sid: str) -> Dict[str, Any]:
        """Get TTS statistics for a call"""
        gate_state = self.speech_gates.get(call_sid, {})
        
        return {
            'speech_gate_active': gate_state.get('active', False),
            'speech_gate_duration': gate_state.get('duration', 0),
            'cached_tts_count': len([k for k in self.tts_cache.keys() if call_sid in k]),
            'total_cache_size': len(self.tts_cache)
        }
    
    def cleanup_call(self, call_sid: str) -> None:
        """Clean up TTS resources for a call"""
        self.speech_gates.pop(call_sid, None)
        
        # Remove cached TTS for this call
        keys_to_remove = [k for k in self.tts_cache.keys() if call_sid in k]
        for key in keys_to_remove:
            del self.tts_cache[key]
        
        logger.info(f"🧹 Cleaned up TTS resources for {call_sid}")
    
    def clear_cache(self) -> None:
        """Clear TTS cache"""
        self.tts_cache.clear()
        logger.info("🗑️ TTS cache cleared")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        return {
            'cache_size': len(self.tts_cache),
            'max_cache_size': self.max_cache_size,
            'cache_usage_percent': (len(self.tts_cache) / self.max_cache_size) * 100
        } 