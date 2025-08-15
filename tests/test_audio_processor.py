import pytest
import time
from unittest.mock import Mock, patch
from ops_integrations.adapters.audio_processor import AudioProcessor

class TestAudioProcessor:
    """Unit tests for AudioProcessor module"""
    
    @pytest.fixture
    def audio_processor(self):
        """Create AudioProcessor instance for testing"""
        return AudioProcessor(sample_rate=8000, frame_duration_ms=30)
    
    @pytest.fixture
    def sample_audio_data(self):
        """Create sample audio data for testing"""
        # Create 1 second of silent audio (8000 samples * 2 bytes per sample)
        return b'\x00\x00' * 8000
    
    def test_initialization(self, audio_processor):
        """Test AudioProcessor initialization"""
        assert audio_processor.sample_rate == 8000
        assert audio_processor.frame_duration_ms == 30
        assert audio_processor.frame_size == 240  # 8000 * 30 / 1000
        assert audio_processor.silence_threshold_ms == 1000
        assert audio_processor.min_speech_duration_ms == 500
        assert audio_processor.max_buffer_duration_ms == 10000
        assert audio_processor.time_based_flush_ms == 3000
    
    def test_process_audio_empty_buffer(self, audio_processor):
        """Test processing empty audio data"""
        call_sid = "test_call_123"
        audio_processor.process_audio(call_sid, b"")
        
        # Should not crash and should have empty buffer
        assert len(audio_processor.audio_buffers[call_sid]) == 0
    
    def test_process_audio_adds_to_buffer(self, audio_processor, sample_audio_data):
        """Test that audio data is added to buffer"""
        call_sid = "test_call_123"
        audio_processor.process_audio(call_sid, sample_audio_data)
        
        # Buffer should contain the remainder after frame processing
        buffer = audio_processor.audio_buffers[call_sid]
        frame_size_bytes = audio_processor.frame_size * 2
        expected_remainder = len(sample_audio_data) % frame_size_bytes
        
        assert len(buffer) == expected_remainder
        if expected_remainder > 0:
            assert bytes(buffer) == sample_audio_data[-expected_remainder:]
    
    def test_vad_state_initialization(self, audio_processor):
        """Test VAD state initialization for new calls"""
        call_sid = "test_call_123"
        vad_state = audio_processor.get_vad_state(call_sid)
        
        expected_state = {
            'speaking': False,
            'silence_start': None,
            'last_speech_time': 0,
            'has_received_media': False,
            'buffer_start_time': None
        }
        
        assert vad_state == expected_state
    
    def test_update_vad_state_speech(self, audio_processor):
        """Test VAD state update when speech is detected"""
        call_sid = "test_call_123"
        
        # Simulate speech detection
        audio_processor._update_vad_state(call_sid, True)
        
        vad_state = audio_processor.get_vad_state(call_sid)
        assert vad_state['speaking'] == True
        assert vad_state['silence_start'] == None
        assert vad_state['last_speech_time'] > 0
    
    def test_update_vad_state_silence(self, audio_processor):
        """Test VAD state update when silence is detected"""
        call_sid = "test_call_123"
        
        # First simulate speech
        audio_processor._update_vad_state(call_sid, True)
        
        # Then simulate silence
        audio_processor._update_vad_state(call_sid, False)
        
        vad_state = audio_processor.get_vad_state(call_sid)
        assert vad_state['speaking'] == True  # Still speaking, silence_start should be set
        assert vad_state['silence_start'] is not None
    
    def test_should_flush_buffer_empty(self, audio_processor):
        """Test should_flush_buffer with empty buffer"""
        call_sid = "test_call_123"
        assert audio_processor.should_flush_buffer(call_sid) == False
    
    def test_should_flush_buffer_min_duration(self, audio_processor):
        """Test should_flush_buffer with minimum duration"""
        call_sid = "test_call_123"
        
        # Add enough audio for minimum duration (500ms = 4000 bytes at 8kHz)
        min_audio = b'\x00\x00' * 4000
        audio_processor.audio_buffers[call_sid].extend(min_audio)
        
        # Should not flush if still speaking
        vad_state = audio_processor.vad_states[call_sid]
        vad_state['speaking'] = True
        vad_state['last_speech_time'] = time.time()
        
        assert audio_processor.should_flush_buffer(call_sid) == False
    
    def test_should_flush_buffer_speech_ended(self, audio_processor):
        """Test should_flush_buffer when speech has ended"""
        call_sid = "test_call_123"
        
        # Add enough audio for minimum duration
        min_audio = b'\x00\x00' * 4000
        audio_processor.audio_buffers[call_sid].extend(min_audio)
        
        # Simulate speech ended
        vad_state = audio_processor.vad_states[call_sid]
        vad_state['speaking'] = False
        vad_state['last_speech_time'] = time.time() - 2  # 2 seconds ago
        
        assert audio_processor.should_flush_buffer(call_sid) == True
    
    def test_should_flush_buffer_time_based(self, audio_processor):
        """Test time-based buffer flushing"""
        call_sid = "test_call_123"
        
        # Add enough audio for time-based flush (3000ms = 24000 bytes at 8kHz)
        time_audio = b'\x00\x00' * 24000
        audio_processor.audio_buffers[call_sid].extend(time_audio)
        
        assert audio_processor.should_flush_buffer(call_sid) == True
    
    def test_get_and_clear_buffer(self, audio_processor, sample_audio_data):
        """Test getting and clearing audio buffer"""
        call_sid = "test_call_123"
        
        # Add audio data
        audio_processor.audio_buffers[call_sid].extend(sample_audio_data)
        
        # Get and clear buffer
        result = audio_processor.get_and_clear_buffer(call_sid)
        
        assert result == sample_audio_data
        assert len(audio_processor.audio_buffers[call_sid]) == 0
        
        # VAD state should be reset
        vad_state = audio_processor.get_vad_state(call_sid)
        assert vad_state['speaking'] == False
        assert vad_state['silence_start'] == None
    
    def test_get_buffer_duration_ms(self, audio_processor):
        """Test buffer duration calculation"""
        call_sid = "test_call_123"
        
        # Add 1 second of audio (8000 samples * 2 bytes)
        audio_data = b'\x00\x00' * 8000
        audio_processor.audio_buffers[call_sid].extend(audio_data)
        
        duration_ms = audio_processor.get_buffer_duration_ms(call_sid)
        assert duration_ms == 1000  # 1000ms = 1 second
    
    def test_cleanup_call(self, audio_processor, sample_audio_data):
        """Test cleanup of call resources"""
        call_sid = "test_call_123"
        
        # Add some data
        audio_processor.audio_buffers[call_sid].extend(sample_audio_data)
        audio_processor._update_vad_state(call_sid, True)
        
        # Cleanup
        audio_processor.cleanup_call(call_sid)
        
        # Should be removed
        assert call_sid not in audio_processor.audio_buffers
        assert call_sid not in audio_processor.vad_states
    
    @patch('webrtcvad.Vad')
    def test_vad_fallback_on_import_error(self, mock_vad):
        """Test VAD fallback when webrtcvad is not available"""
        mock_vad.side_effect = ImportError("webrtcvad not available")
        
        # Should not crash
        processor = AudioProcessor()
        assert processor.vad is not None
        
        # Should return False for speech detection
        assert processor.vad.is_speech(b'\x00' * 480, 8000) == False
    
    def test_multiple_calls_isolation(self, audio_processor):
        """Test that multiple calls are isolated"""
        call_sid_1 = "call_1"
        call_sid_2 = "call_2"
        
        audio_data_1 = b'\x01\x01' * 1000
        audio_data_2 = b'\x02\x02' * 1000
        
        # Process audio for both calls
        audio_processor.process_audio(call_sid_1, audio_data_1)
        audio_processor.process_audio(call_sid_2, audio_data_2)
        
        # Buffers should be separate (accounting for frame processing)
        frame_size_bytes = audio_processor.frame_size * 2
        remainder_1 = len(audio_data_1) % frame_size_bytes
        remainder_2 = len(audio_data_2) % frame_size_bytes
        
        if remainder_1 > 0:
            assert bytes(audio_processor.audio_buffers[call_sid_1]) == audio_data_1[-remainder_1:]
        if remainder_2 > 0:
            assert bytes(audio_processor.audio_buffers[call_sid_2]) == audio_data_2[-remainder_2:]
        
        # VAD states should be separate
        vad_state_1 = audio_processor.get_vad_state(call_sid_1)
        vad_state_2 = audio_processor.get_vad_state(call_sid_2)
        assert vad_state_1 != vad_state_2 