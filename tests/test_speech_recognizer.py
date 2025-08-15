import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from ops_integrations.adapters.speech_recognizer import SpeechRecognizer

class TestSpeechRecognizer:
    """Unit tests for SpeechRecognizer module"""
    
    @pytest.fixture
    def speech_recognizer(self):
        """Create SpeechRecognizer instance for testing"""
        return SpeechRecognizer(openai_api_key="test_key")
    
    @pytest.fixture
    def speech_recognizer_with_whisper(self):
        """Create SpeechRecognizer with remote Whisper for testing"""
        return SpeechRecognizer(openai_api_key="test_key", whisper_url="http://test-whisper.com")
    
    @pytest.fixture
    def sample_mulaw_audio(self):
        """Create sample mu-law encoded audio data"""
        # Simple mu-law encoded audio (silence)
        return b'\x7f' * 1000
    
    def test_initialization(self, speech_recognizer):
        """Test SpeechRecognizer initialization"""
        assert speech_recognizer.tts_speed == 1.25
        assert speech_recognizer.tts_voice == "alloy"
        assert speech_recognizer.tts_model == "tts-1"
        assert speech_recognizer.transcription_confidence_threshold == -0.6
        assert speech_recognizer.remote_whisper_enabled == False
    
    def test_initialization_with_whisper(self, speech_recognizer_with_whisper):
        """Test SpeechRecognizer initialization with remote Whisper"""
        assert speech_recognizer_with_whisper.remote_whisper_enabled == True
        assert speech_recognizer_with_whisper.whisper_url == "http://test-whisper.com"
    
    def test_mulaw_to_pcm_conversion(self, speech_recognizer):
        """Test mu-law to PCM conversion"""
        # Test with known mu-law values
        mulaw_data = b'\x7f\x00\xff'  # Silence, positive, negative
        pcm_data = speech_recognizer._mulaw_to_pcm(mulaw_data)
        
        # Should convert to 16-bit PCM
        assert len(pcm_data) == 6  # 3 samples * 2 bytes each
        assert isinstance(pcm_data, bytes)
    
    def test_convert_mulaw_to_wav(self, speech_recognizer, sample_mulaw_audio):
        """Test mu-law to WAV conversion"""
        wav_data = speech_recognizer._convert_mulaw_to_wav(sample_mulaw_audio)
        
        # Should be valid WAV format
        assert wav_data.startswith(b'RIFF')
        assert b'WAVE' in wav_data
        assert b'fmt ' in wav_data
        assert b'data' in wav_data
    
    @pytest.mark.asyncio
    async def test_transcribe_audio_openai(self, speech_recognizer, sample_mulaw_audio):
        """Test transcription using OpenAI Whisper"""
        call_sid = "test_call_123"
        
        with patch.object(speech_recognizer.openai_client.audio.transcriptions, 'create') as mock_create:
            # Mock OpenAI response
            mock_response = Mock()
            mock_response.text = "Hello, this is a test."
            mock_response.avg_logprob = -0.5
            
            mock_create.return_value = mock_response
            
            text, transcription_time, avg_logprob = await speech_recognizer.transcribe_audio(sample_mulaw_audio, call_sid)
            
            assert text == "Hello, this is a test."
            assert transcription_time > 0
            assert avg_logprob == -0.5
            mock_create.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_transcribe_audio_remote_whisper(self, speech_recognizer_with_whisper, sample_mulaw_audio):
        """Test transcription using remote Whisper service"""
        call_sid = "test_call_123"
        
        with patch.object(speech_recognizer_with_whisper.http_client, 'post') as mock_post:
            # Mock HTTP response
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "text": "Hello from remote Whisper",
                "avg_logprob": -0.3
            }
            mock_post.return_value = mock_response
            
            text, transcription_time, avg_logprob = await speech_recognizer_with_whisper.transcribe_audio(sample_mulaw_audio, call_sid)
            
            assert text == "Hello from remote Whisper"
            assert transcription_time > 0
            assert avg_logprob == -0.3
            mock_post.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_transcribe_audio_remote_whisper_failure(self, speech_recognizer_with_whisper, sample_mulaw_audio):
        """Test transcription failure with remote Whisper"""
        call_sid = "test_call_123"
        
        with patch.object(speech_recognizer_with_whisper.http_client, 'post') as mock_post:
            # Mock HTTP failure
            mock_response = Mock()
            mock_response.status_code = 500
            mock_post.return_value = mock_response
            
            text, transcription_time, avg_logprob = await speech_recognizer_with_whisper.transcribe_audio(sample_mulaw_audio, call_sid)
            
            assert text is None
            assert transcription_time == 0.0
            assert avg_logprob is None
    
    @pytest.mark.asyncio
    async def test_synthesize_tts_success(self, speech_recognizer):
        """Test successful TTS synthesis"""
        call_sid = "test_call_123"
        text = "Hello, this is a test message."
        
        with patch.object(speech_recognizer.openai_client.audio.speech, 'create') as mock_create:
            # Mock OpenAI TTS response
            mock_response = Mock()
            mock_response.content = b'fake_audio_data'
            mock_create.return_value = mock_response
            
            audio_data = await speech_recognizer.synthesize_tts(text, call_sid)
            
            assert audio_data == b'fake_audio_data'
            mock_create.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_synthesize_tts_empty_text(self, speech_recognizer):
        """Test TTS synthesis with empty text"""
        call_sid = "test_call_123"
        
        audio_data = await speech_recognizer.synthesize_tts("", call_sid)
        assert audio_data is None
        
        audio_data = await speech_recognizer.synthesize_tts("   ", call_sid)
        assert audio_data is None
    
    @pytest.mark.asyncio
    async def test_synthesize_tts_failure(self, speech_recognizer):
        """Test TTS synthesis failure"""
        call_sid = "test_call_123"
        text = "Hello, this is a test message."
        
        with patch.object(speech_recognizer.openai_client.audio.speech, 'create') as mock_create:
            mock_create.side_effect = Exception("OpenAI API error")
            
            audio_data = await speech_recognizer.synthesize_tts(text, call_sid)
            
            assert audio_data is None
    
    def test_should_suppress_transcript_empty(self, speech_recognizer):
        """Test transcript suppression with empty text"""
        assert speech_recognizer.should_suppress_transcript("", None) == True
        assert speech_recognizer.should_suppress_transcript("   ", None) == True
    
    def test_should_suppress_transcript_short(self, speech_recognizer):
        """Test transcript suppression with short text"""
        assert speech_recognizer.should_suppress_transcript("a", None) == True
        assert speech_recognizer.should_suppress_transcript("hi", None) == False  # 2 chars is not suppressed
    
    def test_should_suppress_transcript_low_confidence(self, speech_recognizer):
        """Test transcript suppression with low confidence"""
        # Low confidence (below threshold)
        assert speech_recognizer.should_suppress_transcript("Hello world", -0.8) == True
        
        # High confidence (above threshold)
        assert speech_recognizer.should_suppress_transcript("Hello world", -0.4) == False
    
    def test_should_suppress_transcript_normal(self, speech_recognizer):
        """Test transcript suppression with normal text"""
        assert speech_recognizer.should_suppress_transcript("Hello, this is a normal message.", None) == False
        assert speech_recognizer.should_suppress_transcript("Hello, this is a normal message.", -0.5) == False
    
    @pytest.mark.asyncio
    async def test_close(self, speech_recognizer):
        """Test closing HTTP client"""
        with patch.object(speech_recognizer.http_client, 'aclose') as mock_close:
            await speech_recognizer.close()
            mock_close.assert_called_once()
    
    def test_mulaw_decode_table_completeness(self, speech_recognizer):
        """Test that mu-law decode table is complete"""
        # Test a few known values
        mulaw_data = bytes([0x7f, 0x00, 0xff, 0x80])
        pcm_data = speech_recognizer._mulaw_to_pcm(mulaw_data)
        
        # Should convert all bytes without errors
        assert len(pcm_data) == 8  # 4 samples * 2 bytes each
        
        # Check that we get different values for different inputs
        assert pcm_data[0:2] != pcm_data[2:4]  # Different mu-law values should produce different PCM
    
    @pytest.mark.asyncio
    async def test_transcribe_audio_exception_handling(self, speech_recognizer, sample_mulaw_audio):
        """Test exception handling in transcription"""
        call_sid = "test_call_123"
        
        with patch.object(speech_recognizer.openai_client.audio.transcriptions, 'create') as mock_create:
            mock_create.side_effect = Exception("Network error")
            
            text, transcription_time, avg_logprob = await speech_recognizer.transcribe_audio(sample_mulaw_audio, call_sid)
            
            assert text is None
            assert transcription_time == 0.0
            assert avg_logprob is None
    
    def test_wav_format_validation(self, speech_recognizer, sample_mulaw_audio):
        """Test that generated WAV has correct format"""
        wav_data = speech_recognizer._convert_mulaw_to_wav(sample_mulaw_audio)
        
        # Check WAV header structure
        assert wav_data[0:4] == b'RIFF'  # RIFF header
        assert wav_data[8:12] == b'WAVE'  # WAVE identifier
        assert wav_data[12:16] == b'fmt '  # Format chunk
        assert b'data' in wav_data  # Data chunk
        
        # Check that file size is reasonable
        assert len(wav_data) > 44  # Minimum WAV header size 