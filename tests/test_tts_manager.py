import pytest
import asyncio
import time
from unittest.mock import Mock, patch, AsyncMock
from ops_integrations.adapters.tts_manager import TTSManager

class TestTTSManager:
    """Unit tests for TTSManager module"""
    
    @pytest.fixture
    def mock_speech_recognizer(self):
        """Create mock speech recognizer"""
        mock = Mock()
        mock.synthesize_tts = AsyncMock()
        return mock
    
    @pytest.fixture
    def tts_manager(self, mock_speech_recognizer):
        """Create TTSManager instance for testing"""
        return TTSManager(mock_speech_recognizer)
    
    def test_initialization(self, tts_manager):
        """Test TTSManager initialization"""
        assert tts_manager.speech_gate_buffer_sec == 1.0
        assert tts_manager.max_cache_size == 100
        assert len(tts_manager.speech_gates) == 0
        assert len(tts_manager.tts_cache) == 0
    
    @pytest.mark.asyncio
    async def test_synthesize_tts_cache_hit(self, tts_manager):
        """Test TTS synthesis with cache hit"""
        call_sid = "test_call_123"
        text = "Hello, this is a test message"
        cached_audio = b'cached_audio_data'
        
        # Add to cache
        cache_key = f"{text}_{call_sid}"
        tts_manager.tts_cache[cache_key] = cached_audio
        
        # Should return cached audio
        result = await tts_manager.synthesize_tts(text, call_sid)
        assert result == cached_audio
        
        # Should not call speech recognizer
        tts_manager.speech_recognizer.synthesize_tts.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_synthesize_tts_cache_miss(self, tts_manager):
        """Test TTS synthesis with cache miss"""
        call_sid = "test_call_123"
        text = "Hello, this is a test message"
        generated_audio = b'generated_audio_data'
        
        # Mock speech recognizer response
        tts_manager.speech_recognizer.synthesize_tts.return_value = generated_audio
        
        # Should generate new audio
        result = await tts_manager.synthesize_tts(text, call_sid)
        assert result == generated_audio
        
        # Should call speech recognizer
        tts_manager.speech_recognizer.synthesize_tts.assert_called_once_with(text, call_sid)
        
        # Should be cached
        cache_key = f"{text}_{call_sid}"
        assert tts_manager.tts_cache[cache_key] == generated_audio
    
    @pytest.mark.asyncio
    async def test_synthesize_tts_empty_text(self, tts_manager):
        """Test TTS synthesis with empty text"""
        call_sid = "test_call_123"
        
        # Empty text
        result = await tts_manager.synthesize_tts("", call_sid)
        assert result is None
        
        # Whitespace only
        result = await tts_manager.synthesize_tts("   ", call_sid)
        assert result is None
        
        # Should not call speech recognizer
        tts_manager.speech_recognizer.synthesize_tts.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_synthesize_tts_failure(self, tts_manager):
        """Test TTS synthesis failure"""
        call_sid = "test_call_123"
        text = "Hello, this is a test message"
        
        # Mock speech recognizer failure
        tts_manager.speech_recognizer.synthesize_tts.return_value = None
        
        result = await tts_manager.synthesize_tts(text, call_sid)
        assert result is None
        
        # Should not be cached
        cache_key = f"{text}_{call_sid}"
        assert cache_key not in tts_manager.tts_cache
    
    def test_add_to_cache(self, tts_manager):
        """Test adding to cache"""
        key = "test_key"
        audio_data = b'test_audio_data'
        
        tts_manager._add_to_cache(key, audio_data)
        
        assert tts_manager.tts_cache[key] == audio_data
        assert len(tts_manager.tts_cache) == 1
    
    def test_add_to_cache_overflow(self, tts_manager):
        """Test cache overflow handling"""
        # Fill cache to max size
        for i in range(100):
            tts_manager._add_to_cache(f"key_{i}", b'audio_data')
        
        assert len(tts_manager.tts_cache) == 100
        
        # Add one more - should remove oldest
        tts_manager._add_to_cache("new_key", b'new_audio_data')
        
        assert len(tts_manager.tts_cache) == 100
        assert "new_key" in tts_manager.tts_cache
        assert "key_0" not in tts_manager.tts_cache  # Oldest should be removed
    
    def test_activate_speech_gate(self, tts_manager):
        """Test speech gate activation"""
        call_sid = "test_call_123"
        text = "Hello, this is a test message"
        
        tts_manager.activate_speech_gate(call_sid, text)
        
        gate_state = tts_manager.get_speech_gate_state(call_sid)
        assert gate_state['active'] == True
        assert gate_state['text'] == text
        assert gate_state['start_time'] > 0
        assert gate_state['duration'] > 0
    
    def test_is_speech_gate_active(self, tts_manager):
        """Test speech gate active status"""
        call_sid = "test_call_123"
        
        # Initially not active
        assert tts_manager.is_speech_gate_active(call_sid) == False
        
        # Activate gate
        tts_manager.activate_speech_gate(call_sid, "Test message")
        assert tts_manager.is_speech_gate_active(call_sid) == True
    
    def test_get_speech_gate_state(self, tts_manager):
        """Test getting speech gate state"""
        call_sid = "test_call_123"
        text = "Test message"
        
        tts_manager.activate_speech_gate(call_sid, text)
        
        state = tts_manager.get_speech_gate_state(call_sid)
        assert state['active'] == True
        assert state['text'] == text
        assert 'start_time' in state
        assert 'duration' in state
    
    def test_deactivate_speech_gate(self, tts_manager):
        """Test manual speech gate deactivation"""
        call_sid = "test_call_123"
        text = "Test message"
        
        # Activate gate
        tts_manager.activate_speech_gate(call_sid, text)
        assert tts_manager.is_speech_gate_active(call_sid) == True
        
        # Deactivate gate
        tts_manager.deactivate_speech_gate(call_sid)
        assert tts_manager.is_speech_gate_active(call_sid) == False
    
    @pytest.mark.asyncio
    async def test_add_tts_to_twiml_success(self, tts_manager):
        """Test adding TTS to TwiML response"""
        call_sid = "test_call_123"
        text = "Hello, this is a test message"
        mock_twiml = Mock()
        
        # Mock TTS generation
        tts_manager.speech_recognizer.synthesize_tts.return_value = b'audio_data'
        
        await tts_manager.add_tts_to_twiml(mock_twiml, call_sid, text)
        
        # Should activate speech gate
        assert tts_manager.is_speech_gate_active(call_sid) == True
        
        # Should generate TTS
        tts_manager.speech_recognizer.synthesize_tts.assert_called_once_with(text, call_sid)
    
    @pytest.mark.asyncio
    async def test_add_tts_to_twiml_empty_text(self, tts_manager):
        """Test adding TTS to TwiML with empty text"""
        call_sid = "test_call_123"
        mock_twiml = Mock()
        
        await tts_manager.add_tts_to_twiml(mock_twiml, call_sid, "")
        
        # Should not activate speech gate
        assert tts_manager.is_speech_gate_active(call_sid) == False
        
        # Should not generate TTS
        tts_manager.speech_recognizer.synthesize_tts.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_add_tts_to_twiml_failure(self, tts_manager):
        """Test adding TTS to TwiML with generation failure"""
        call_sid = "test_call_123"
        text = "Hello, this is a test message"
        mock_twiml = Mock()
        
        # Mock TTS generation failure
        tts_manager.speech_recognizer.synthesize_tts.return_value = None
        
        await tts_manager.add_tts_to_twiml(mock_twiml, call_sid, text)
        
        # Should still activate speech gate
        assert tts_manager.is_speech_gate_active(call_sid) == True
    
    def test_estimate_tts_duration(self, tts_manager):
        """Test TTS duration estimation"""
        # Test with different text lengths
        assert tts_manager.estimate_tts_duration("Hello") == 0.3  # 5 chars * 0.06
        assert tts_manager.estimate_tts_duration("This is a longer message") == 1.44  # 24 chars * 0.06
        assert tts_manager.estimate_tts_duration("") == 0.0
    
    def test_get_tts_stats(self, tts_manager):
        """Test getting TTS statistics"""
        call_sid = "test_call_123"
        
        # Add some data
        tts_manager.activate_speech_gate(call_sid, "Test message")
        tts_manager.tts_cache[f"text1_{call_sid}"] = b'audio1'
        tts_manager.tts_cache[f"text2_{call_sid}"] = b'audio2'
        tts_manager.tts_cache["other_call_text"] = b'audio3'
        
        stats = tts_manager.get_tts_stats(call_sid)
        
        assert stats['speech_gate_active'] == True
        assert stats['speech_gate_duration'] > 0
        assert stats['cached_tts_count'] == 2  # Only for this call
        assert stats['total_cache_size'] == 3  # All cached items
    
    def test_cleanup_call(self, tts_manager):
        """Test cleaning up TTS resources for a call"""
        call_sid = "test_call_123"
        
        # Add data for the call
        tts_manager.activate_speech_gate(call_sid, "Test message")
        tts_manager.tts_cache[f"text1_{call_sid}"] = b'audio1'
        tts_manager.tts_cache[f"text2_{call_sid}"] = b'audio2'
        tts_manager.tts_cache["other_call_text"] = b'audio3'
        
        # Cleanup
        tts_manager.cleanup_call(call_sid)
        
        # Speech gate should be removed
        assert call_sid not in tts_manager.speech_gates
        
        # Only call-specific cache entries should be removed
        assert f"text1_{call_sid}" not in tts_manager.tts_cache
        assert f"text2_{call_sid}" not in tts_manager.tts_cache
        assert "other_call_text" in tts_manager.tts_cache  # Should remain
    
    def test_clear_cache(self, tts_manager):
        """Test clearing TTS cache"""
        # Add some data
        tts_manager.tts_cache["key1"] = b'audio1'
        tts_manager.tts_cache["key2"] = b'audio2'
        
        assert len(tts_manager.tts_cache) == 2
        
        # Clear cache
        tts_manager.clear_cache()
        
        assert len(tts_manager.tts_cache) == 0
    
    def test_get_cache_stats(self, tts_manager):
        """Test getting cache statistics"""
        # Empty cache
        stats = tts_manager.get_cache_stats()
        assert stats['cache_size'] == 0
        assert stats['max_cache_size'] == 100
        assert stats['cache_usage_percent'] == 0.0
        
        # Add some data
        for i in range(50):
            tts_manager.tts_cache[f"key_{i}"] = b'audio_data'
        
        stats = tts_manager.get_cache_stats()
        assert stats['cache_size'] == 50
        assert stats['max_cache_size'] == 100
        assert stats['cache_usage_percent'] == 50.0
    
    @pytest.mark.asyncio
    async def test_speech_gate_auto_deactivation(self, tts_manager):
        """Test automatic speech gate deactivation"""
        call_sid = "test_call_123"
        text = "Short"  # 5 chars * 0.06 = 0.3s + 1s buffer = 1.3s
        
        # Activate gate
        tts_manager.activate_speech_gate(call_sid, text)
        assert tts_manager.is_speech_gate_active(call_sid) == True
        
        # Wait for auto-deactivation
        await asyncio.sleep(1.5)  # Longer than estimated duration
        
        # Should be deactivated
        assert tts_manager.is_speech_gate_active(call_sid) == False
    
    def test_multiple_calls_isolation(self, tts_manager):
        """Test that multiple calls are isolated"""
        call_sid_1 = "call_1"
        call_sid_2 = "call_2"
        text = "Test message"
        
        # Activate gates for different calls
        tts_manager.activate_speech_gate(call_sid_1, text)
        tts_manager.activate_speech_gate(call_sid_2, text)
        
        # Both should be active
        assert tts_manager.is_speech_gate_active(call_sid_1) == True
        assert tts_manager.is_speech_gate_active(call_sid_2) == True
        
        # Deactivate one
        tts_manager.deactivate_speech_gate(call_sid_1)
        
        # Only one should be inactive
        assert tts_manager.is_speech_gate_active(call_sid_1) == False
        assert tts_manager.is_speech_gate_active(call_sid_2) == True
    
    def test_cache_key_uniqueness(self, tts_manager):
        """Test that cache keys are unique per call"""
        call_sid_1 = "call_1"
        call_sid_2 = "call_2"
        text = "Same text"
        
        # Add same text for different calls
        tts_manager.tts_cache[f"{text}_{call_sid_1}"] = b'audio1'
        tts_manager.tts_cache[f"{text}_{call_sid_2}"] = b'audio2'
        
        # Should be separate entries
        assert tts_manager.tts_cache[f"{text}_{call_sid_1}"] == b'audio1'
        assert tts_manager.tts_cache[f"{text}_{call_sid_2}"] == b'audio2'
        assert len(tts_manager.tts_cache) == 2
    
    def test_speech_gate_duration_calculation(self, tts_manager):
        """Test speech gate duration calculation"""
        call_sid = "test_call_123"
        
        # Test with different text lengths
        short_text = "Hi"
        long_text = "This is a much longer message that should have a longer duration"
        
        tts_manager.activate_speech_gate(call_sid, short_text)
        short_duration = tts_manager.get_speech_gate_state(call_sid)['duration']
        
        tts_manager.deactivate_speech_gate(call_sid)
        
        tts_manager.activate_speech_gate(call_sid, long_text)
        long_duration = tts_manager.get_speech_gate_state(call_sid)['duration']
        
        # Longer text should have longer duration
        assert long_duration > short_duration 