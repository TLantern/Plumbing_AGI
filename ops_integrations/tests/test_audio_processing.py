import asyncio
import logging
import base64
import io
import wave
import struct
import time
import array
from typing import Optional, Dict, Any, Tuple
from collections import defaultdict
import httpx
from openai import OpenAI
import os

# Try to import webrtcvad for Voice Activity Detection
try:
    import webrtcvad  # type: ignore
except Exception:
    class _DummyVAD:
        def __init__(self, aggressiveness: int):
            pass
        def is_speech(self, frame_bytes: bytes, sample_rate: int) -> bool:
            return False
    class _webrtcvad_module:  # minimal shim for interface
        Vad = _DummyVAD
    webrtcvad = _webrtcvad_module()  # type: ignore

# Try to import audioop for mu-law decoding and resampling; may be missing on some Python versions
try:
    import audioop as _audioop  # type: ignore
except Exception:
    _audioop = None

logger = logging.getLogger(__name__)

class TestAudioProcessor:
    """Test implementation of audio processing with same tuning/cleaning as phone_service.py"""
    
    def __init__(self, openai_api_key: str, whisper_url: Optional[str] = None):
        self.openai_client = OpenAI(api_key=openai_api_key)
        self.whisper_url = whisper_url
        self.http_client = httpx.AsyncClient(timeout=30.0)
        
        # Transcription configuration (same as phone_service.py)
        self.use_local_whisper = False
        self.use_remote_whisper = True
        self.remote_whisper_url = whisper_url or "https://cd1864cc8a91.ngrok-free.app"
        self.transcription_model = "whisper-1"
        self.fast_transcription_prompt = "Caller describing plumbing issue. Focus on clear human speech. Ignore background noise, dial tones, hangup signals, beeps, clicks, static, and other audio artifacts. Maintain natural speech patterns and context."
        
        # VAD Configuration (same as phone_service.py)
        self.vad_aggressiveness = 2  # Reduced from 3 - less aggressive filtering for better sensitivity
        self.vad_frame_duration_ms = 30  # Increased from 20ms - better accuracy for voice detection
        self.silence_timeout_sec = 2.0  # Increased from 1.5s - allow longer natural pauses
        self.min_speech_duration_sec = 0.5  # Increased from 0.3s - filter out brief noise
        self.chunk_duration_sec = 2.0  # Increased from 2.0s - more context for processing
        self.preroll_ignore_sec = 0.5  # Increased from 0.4s - better initial speech detection
        self.min_start_rms = 100  # Reduced from 130 - more sensitive to quiet speech
        self.fast_response_mode = False  # Disabled for better quality over speed
        
        # Audio format defaults for Twilio Media Streams (mu-law 8k)
        self.sample_rate_default = 8000
        self.sample_width = 2  # bytes (16-bit)
        
        # Confidence thresholds (same as phone_service.py)
        self.transcription_confidence_threshold = -0.7  # Relaxed from -0.6 - allow more transcriptions through
        self.confidence_debug_mode = True  # Enable detailed confidence logging
        
        # Buffer incoming PCM16 per call and track VAD state
        self.audio_buffers = defaultdict(bytearray)
        self.vad_states = defaultdict(lambda: {
            'is_speaking': False,
            'last_speech_time': 0,
            'speech_start_time': 0,
            'pending_audio': bytearray(),
            'vad': webrtcvad.Vad(self.vad_aggressiveness),
            'fallback_buffer': bytearray(),
            'last_chunk_time': 0,
            'has_received_media': False,
            'last_listen_log_time': 0.0,
            'bot_speaking': False,  # Track when bot is outputting TTS
            'bot_speech_start_time': 0,  # When bot started speaking
            'speech_gate_active': False,  # Gate to block user speech processing
        })
        
        # Per-call media format (encoding and sample rate)
        self.audio_config_store = defaultdict(lambda: {
            'encoding': 'mulaw',      # 'mulaw' or 'pcm16'
            'sample_rate': self.sample_rate_default
        })
        
        # Store call information when calls start
        self.call_info_store = {}
        
        # Store transcriptions per call
        self.transcriptions = defaultdict(list)
        
    def _mulaw_byte_to_linear16(self, mu: int) -> int:
        """Convert mu-law byte to linear 16-bit PCM (same as phone_service.py)"""
        mu = ~mu & 0xFF
        sign = mu & 0x80
        exponent = (mu >> 4) & 0x07
        mantissa = mu & 0x0F
        sample = ((mantissa << 3) + 132) << exponent
        sample = sample - 132
        if sign:
            sample = -sample
        # Clamp to int16
        if sample > 32767:
            sample = 32767
        if sample < -32768:
            sample = -32768
        return sample
    
    def mulaw_to_pcm16(self, mu_bytes: bytes) -> bytes:
        """Convert mu-law encoded bytes to PCM16 (same as phone_service.py)"""
        if _audioop is not None:
            return _audioop.ulaw2lin(mu_bytes, 2)
        # Pure Python fallback
        out = bytearray()
        for b in mu_bytes:
            s = self._mulaw_byte_to_linear16(b)
            out.extend(struct.pack('<h', s))
        return bytes(out)
    
    def convert_media_payload_to_pcm16(self, call_sid: str, payload_b64: str) -> bytes:
        """Convert Twilio media payload to PCM16 bytes (same as phone_service.py)"""
        raw_bytes = base64.b64decode(payload_b64)
        cfg = self.audio_config_store.get(call_sid, {"encoding": "mulaw", "sample_rate": self.sample_rate_default})
        encoding = cfg.get("encoding", "mulaw")
        if encoding == "mulaw":
            return self.mulaw_to_pcm16(raw_bytes)
        # Already PCM16 (audio/l16)
        return raw_bytes
    
    def pcm_to_wav_bytes(self, pcm: bytes, sample_rate: int) -> bytes:
        """Wrap raw PCM into a WAV container for Whisper (same as phone_service.py)"""
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(self.sample_width)
            wf.setframerate(sample_rate)
            wf.writeframes(pcm)
        return buf.getvalue()
    
    async def process_audio(self, call_sid: str, audio: bytes):
        """Enhanced audio processing with Voice Activity Detection (VAD) - same as phone_service.py"""
        vad_state = self.vad_states[call_sid]
        vad = vad_state['vad']
        current_time = time.time()
        sample_rate = self.audio_config_store.get(call_sid, {}).get('sample_rate', self.sample_rate_default)
        stream_start_time = vad_state.get('stream_start_time', current_time)
        
        # Check if bot is currently speaking (speech gate)
        if vad_state.get('speech_gate_active', False):
            # Bot is speaking - suppress user speech processing but still log
            gate_start_time = vad_state.get('bot_speech_start_time', current_time)
            gate_elapsed = current_time - gate_start_time
            logger.debug(f"🔇 Speech gate active for {call_sid} - suppressing user speech processing (elapsed: {gate_elapsed:.2f}s)")
            # Still add to buffer to maintain continuity when gate is lifted
            self.audio_buffers[call_sid].extend(audio)
            return
        
        # Log incoming audio
        logger.debug(f"📡 Received {len(audio)} bytes of PCM16 audio from {call_sid}")
        
        # Add audio to buffer
        self.audio_buffers[call_sid].extend(audio)
        # Also accumulate into time-based fallback buffer regardless of VAD state
        vad_state['fallback_buffer'].extend(audio)
        total_buffer_size = len(self.audio_buffers[call_sid])
        buffer_duration_ms = total_buffer_size / (sample_rate * self.sample_width) * 1000
        
        # Info-level listening heartbeat (throttled)
        try:
            if (current_time - vad_state.get('last_listen_log_time', 0)) >= 1.0:
                fb_ms = len(vad_state['fallback_buffer']) / (sample_rate * self.sample_width) * 1000
                logger.info(f"🎧 Listening ({call_sid}): buffer={fb_ms:.0f}ms, speaking={vad_state['is_speaking']}, sample_rate={sample_rate}")
                vad_state['last_listen_log_time'] = current_time
        except Exception:
            pass
        
        logger.debug(f"Audio buffer for {call_sid}: {total_buffer_size} bytes ({buffer_duration_ms:.0f}ms total)")
        
        # Process audio in frames for VAD
        frame_size_bytes = int(sample_rate * self.vad_frame_duration_ms / 1000) * self.sample_width
        buffer = self.audio_buffers[call_sid]
        
        while len(buffer) >= frame_size_bytes:
            # Extract frame for VAD analysis
            frame_bytes = bytes(buffer[:frame_size_bytes])
            buffer = buffer[frame_size_bytes:]
            
            try:
                # VAD requires PCM16 mono at specific sample rates
                is_speech = vad.is_speech(frame_bytes, sample_rate)

                # During preroll window, ignore low-energy detections
                if is_speech and not vad_state['is_speaking']:
                    if (current_time - stream_start_time) < self.preroll_ignore_sec:
                        try:
                            if _audioop is not None:
                                frame_rms = _audioop.rms(frame_bytes, 2)
                            else:
                                arr = array.array('h', frame_bytes)
                                frame_rms = int((sum(x*x for x in arr) / len(arr)) ** 0.5) if len(arr) else 0
                        except Exception:
                            frame_rms = 0
                        if frame_rms < self.min_start_rms:
                            # Treat as noise; continue without starting a segment
                            is_speech = False

                if is_speech:
                    # Speech detected
                    if not vad_state['is_speaking']:
                        # Start of speech
                        vad_state['is_speaking'] = True
                        vad_state['speech_start_time'] = current_time
                        vad_state['pending_audio'] = bytearray()
                        logger.info(f"🗣️  SPEECH STARTED for {call_sid}")
                    
                    vad_state['last_speech_time'] = current_time
                    vad_state['pending_audio'].extend(frame_bytes)
                    
                    # Log periodic speech detection
                    if len(vad_state['pending_audio']) % (frame_size_bytes * 25) == 0:  # Every ~500ms
                        speech_duration = current_time - vad_state['speech_start_time']
                        pending_duration_ms = len(vad_state['pending_audio']) / (sample_rate * self.sample_width) * 1000
                        logger.debug(f"Speech continuing for {call_sid}: {speech_duration:.1f}s elapsed, {pending_duration_ms:.0f}ms buffered")
                    
                else:
                    # No speech in this frame
                    if vad_state['is_speaking']:
                        # We were speaking, add this frame to pending audio (might be pause)
                        vad_state['pending_audio'].extend(frame_bytes)
                        
                        # Check if silence timeout exceeded
                        silence_duration = current_time - vad_state['last_speech_time']
                        if silence_duration >= self.silence_timeout_sec:
                            # End of speech detected
                            speech_duration = current_time - vad_state['speech_start_time']
                            pending_duration_ms = len(vad_state['pending_audio']) / (sample_rate * self.sample_width) * 1000
                            
                            logger.info(f"🔇 SPEECH ENDED for {call_sid}: {speech_duration:.2f}s total, {pending_duration_ms:.0f}ms buffered, {silence_duration:.2f}s silence")
                            
                            if speech_duration >= self.min_speech_duration_sec:
                                # Valid speech segment, process it
                                logger.info(f"✅ Processing valid speech segment for {call_sid}")
                                await self.process_speech_segment(call_sid, vad_state['pending_audio'])
                                # Clear fallback buffer too to avoid double-processing the same audio
                                vad_state['fallback_buffer'] = bytearray()
                                # Mark the time when we last processed via VAD to prevent immediate fallback
                                vad_state['last_vad_process_time'] = current_time
                            else:
                                logger.warning(f"❌ Speech too short for {call_sid} ({speech_duration:.2f}s < {self.min_speech_duration_sec}s), discarding")
                            
                            # Reset VAD state
                            vad_state['is_speaking'] = False
                            vad_state['pending_audio'] = bytearray()
                    
            except Exception as e:
                logger.warning(f"VAD processing error for {call_sid}: {e}")
                # Fall back to time-based chunking on VAD error
                continue
        
        # Update buffer
        self.audio_buffers[call_sid] = buffer
        
        # Fallback: if we've been collecting audio for too long, force processing (VAD path)
        if vad_state['is_speaking']:
            speech_duration = current_time - vad_state['speech_start_time']
            if speech_duration >= self.chunk_duration_sec:
                logger.debug(f"Forcing processing due to max duration for {call_sid}")
                await self.process_speech_segment(call_sid, vad_state['pending_audio'])
                # Clear fallback buffer too, since it contains the same recent audio
                vad_state['fallback_buffer'] = bytearray()
                # Mark the time when we processed via VAD to prevent immediate fallback
                vad_state['last_vad_process_time'] = current_time
                vad_state['is_speaking'] = False
                vad_state['pending_audio'] = bytearray()

        # Time-based fallback flush every CHUNK_DURATION_SEC even if VAD never triggered
        try:
            fallback_bytes = len(vad_state['fallback_buffer'])
            last_vad_process = vad_state.get('last_vad_process_time', 0)
            last_chunk_time = vad_state.get('last_chunk_time', 0)
            time_since_vad = current_time - last_vad_process
            time_since_chunk = current_time - last_chunk_time
            
            # Only trigger fallback if:
            # 1. Not currently speaking
            # 2. Have enough audio buffered
            # 3. Haven't processed via VAD recently (prevent double processing)
            # 4. Haven't processed via fallback recently (prevent excessive processing)
            if (not vad_state['is_speaking'] and 
                fallback_bytes >= int(sample_rate * self.sample_width * self.chunk_duration_sec) and
                time_since_vad > 3.0 and  # Increased from 2.0 - wait longer after VAD processing
                time_since_chunk > 5.0):  # Wait at least 5 seconds between fallback processes
                logger.info(f"⏱️ Time-based fallback flush for {call_sid}: {fallback_bytes} bytes (~{self.chunk_duration_sec}s)")
                await self.process_speech_segment(call_sid, vad_state['fallback_buffer'])
                vad_state['fallback_buffer'] = bytearray()
                vad_state['last_chunk_time'] = current_time
        except Exception as e:
            logger.debug(f"Time-based fallback flush error for {call_sid}: {e}")

    async def process_speech_segment(self, call_sid: str, audio_data: bytearray):
        """Process a detected speech segment (same as phone_service.py)"""
        sample_rate = self.audio_config_store.get(call_sid, {}).get('sample_rate', self.sample_rate_default)
        audio_duration_ms = len(audio_data) / (sample_rate * self.sample_width) * 1000
        logger.info(f"Processing speech segment for {call_sid}: {len(audio_data)} bytes, {audio_duration_ms:.0f}ms duration")
        
        # Audio fingerprinting to prevent processing the same audio multiple times
        try:
            import hashlib
            audio_hash = hashlib.md5(bytes(audio_data)).hexdigest()[:8]  # First 8 chars of hash
            info = self.call_info_store.get(call_sid, {})
            last_audio_hash = info.get('last_audio_hash')
            last_audio_ts = info.get('last_audio_ts', 0)
            now_ts = time.time()
            
            if last_audio_hash == audio_hash and (now_ts - last_audio_ts) < 30:
                logger.info(f"Suppressing duplicate audio segment for {call_sid} (hash: {audio_hash})")
                return
            
            info['last_audio_hash'] = audio_hash
            info['last_audio_ts'] = now_ts
            self.call_info_store[call_sid] = info
        except Exception as e:
            logger.debug(f"Audio fingerprinting failed for {call_sid}: {e}")
        
        # Quality-focused processing - require longer segments for better accuracy
        min_duration_ms = 500  # Increased from 400 - require longer segments for better quality
        min_bytes = sample_rate * self.sample_width * (min_duration_ms / 1000)
        
        if len(audio_data) < min_bytes:
            logger.warning(f"Speech segment too short for {call_sid} ({audio_duration_ms:.0f}ms < {min_duration_ms}ms), skipping Whisper processing")
            return

        # Energy gate to drop very low-energy segments (likely noise/line tones)
        try:
            if _audioop is not None:
                rms = _audioop.rms(bytes(audio_data), 2)
            else:
                # Fallback simple RMS
                arr = array.array('h', audio_data)
                if len(arr) == 0:
                    rms = 0
                else:
                    rms = int((sum(x*x for x in arr) / len(arr)) ** 0.5)
            if rms < 60:  # Reduced from 80 - more sensitive to quiet speech
                logger.info(f"Skipping low-energy segment for {call_sid} (RMS={rms})")
                return
        except Exception as e:
            logger.debug(f"RMS calc failed for {call_sid}: {e}")

        try:
            logger.debug(f"Converting PCM16 to WAV for {call_sid} ({len(audio_data)} bytes) @ {sample_rate} Hz")
            wav_bytes = self.pcm_to_wav_bytes(bytes(audio_data), sample_rate)
            logger.debug(f"WAV conversion complete for {call_sid}: {len(wav_bytes)} bytes")
            
            # Optionally resample to 16k for Whisper if available
            target_rate = 16000
            wav_for_whisper = wav_bytes
            if sample_rate != target_rate and _audioop is not None:
                pcm16 = bytes(audio_data)
                converted, _ = _audioop.ratecv(pcm16, 2, 1, sample_rate, target_rate, None)
                wav_for_whisper = self.pcm_to_wav_bytes(converted, target_rate)
                logger.debug(f"Resampled audio for Whisper from {sample_rate} Hz to {target_rate} Hz")
            
            logger.info(f"Sending audio to Whisper for {call_sid}")
            start_time = time.time()
            
            # Try remote Whisper service first
            resp = None
            if self.use_remote_whisper:
                try:
                    # Convert WAV to base64
                    wav_base64 = base64.b64encode(wav_for_whisper).decode('utf-8')
                    
                    # Send to remote service
                    response = await self.http_client.post(
                        f"{self.remote_whisper_url}/transcribe",
                        json={
                            "audio_base64": wav_base64,
                            "sample_rate": 16000,
                            "language": "en"
                        }
                    )
                    response.raise_for_status()
                    remote_result = response.json()
                
                    # Convert to OpenAI format
                    openai_resp = type('obj', (object,), {
                        'text': remote_result.get('text', ''),
                        'segments': []  # Remote service doesn't provide segments
                    })()
                    
                    resp = openai_resp
                    logger.info(f"Remote Whisper transcription completed for {call_sid} in {remote_result.get('transcription_time', 0):.2f}s")
                    
                except Exception as e:
                    logger.error(f"Remote Whisper failed for {call_sid}: {e}")
                    resp = None
            
            # Fallback to OpenAI Whisper
            if not self.use_remote_whisper or resp is None:
                logger.info(f"Using OpenAI Whisper {self.transcription_model} for {call_sid}")
                wav_file = io.BytesIO(wav_for_whisper)
                try:
                    wav_file.name = "speech.wav"  # Help the API infer format
                except Exception:
                    pass
                
                # Enhanced prompt for better transcription quality
                prompt = "Caller is describing a plumbing issue or asking a question. Focus on clear human speech and maintain natural conversation flow. Ignore background noise, dial tones, hangup signals, beeps, clicks, static, and other audio artifacts. Preserve context and intent."
                
                resp = await asyncio.to_thread(
                    self.openai_client.audio.transcriptions.create,
                    model=self.transcription_model,
                    file=wav_file,
                    response_format="verbose_json",
                    language="en",
                    prompt=prompt,
                    temperature=0.0  # Add temperature=0 for more consistent results
                )
            
            transcription_duration = time.time() - start_time
            logger.info(f"Whisper transcription completed for {call_sid} in {transcription_duration:.2f}s")
            
            text = (resp.text or "").strip()
            
            # Clean and filter transcription for unwanted content and repetitions
            cleaned_text, should_suppress_due_to_content = self.clean_and_filter_transcription(text)
            if should_suppress_due_to_content:
                return
            
            # Use cleaned text for further processing
            text = cleaned_text
            
            # Confidence/quality gating using segments avg_logprob
            avg_logprobs = []
            for seg in getattr(resp, 'segments', []) or []:
                lp = getattr(seg, 'avg_logprob', None)
                if isinstance(lp, (int, float)):
                    avg_logprobs.append(lp)
            mean_lp = sum(avg_logprobs) / len(avg_logprobs) if avg_logprobs else None
            
            normalized = text.lower().strip().strip(".,!? ")
            
            short_garbage = {"bye", "hi", "uh", "um", "hmm", "huh"}
            should_suppress = False
            if not text:
                should_suppress = True
            elif len(normalized) <= 3 and normalized in short_garbage:
                should_suppress = True
            elif mean_lp is not None and mean_lp < self.transcription_confidence_threshold:
                should_suppress = True
                if self.confidence_debug_mode:
                    logger.info(f"🔍 Low transcription confidence: {mean_lp:.3f} < {self.transcription_confidence_threshold}")
            
            if should_suppress:
                logger.info(f"Suppressed low-confidence/short transcription for {call_sid}: '{text}' (avg_logprob={mean_lp})")
                return
            
            logger.info(f'🎤 USER SPEECH ({call_sid}): "{text}" [duration: {audio_duration_ms:.0f}ms, transcription_time: {transcription_duration:.2f}s, avg_logprob: {mean_lp}]')
            
            # Additional filtering for very short or low-confidence transcriptions
            if len(text.strip()) <= 2 and mean_lp is not None and mean_lp < -0.8:
                logger.info(f"Suppressing very short low-confidence transcript for {call_sid}: '{text}' (length={len(text)}, confidence={mean_lp:.3f})")
                return
            
            # Suppress common noise patterns
            noise_patterns = [
                r'^\s*[.,!?;:]\s*$',  # Just punctuation
                r'^\s*[aeiou]\s*$',   # Just a single vowel
                r'^\s*[bcdfghjklmnpqrstvwxyz]\s*$',  # Just a single consonant
                r'^\s*[0-9]\s*$',     # Just a single digit
                r'^\s*[^\w\s]\s*$',   # Just a single special character
            ]
            import re
            for pattern in noise_patterns:
                if re.match(pattern, text, re.IGNORECASE):
                    logger.info(f"Suppressing noise pattern transcript for {call_sid}: '{text}'")
                    return
            
            # Enhanced duplicate suppression with fuzzy matching and audio fingerprinting
            try:
                normalized_text = " ".join(text.lower().split())
                info = self.call_info_store.get(call_sid, {})
                prev_text = info.get('asr_last_text')
                prev_ts = info.get('asr_last_ts', 0)
                now_ts = time.time()
                
                # Check for exact duplicates within 30 seconds
                if prev_text == normalized_text and (now_ts - prev_ts) < 30:
                    logger.info(f"Suppressing exact duplicate transcript for {call_sid}: '{text}'")
                    return
                
                # Check for very similar text (fuzzy matching) within 30 seconds
                if prev_text and (now_ts - prev_ts) < 30:
                    # Remove punctuation and extra spaces for comparison
                    clean_prev = ''.join(c for c in prev_text if c.isalnum() or c.isspace()).strip()
                    clean_current = ''.join(c for c in normalized_text if c.isalnum() or c.isspace()).strip()
                    
                    # Check if they're very similar (e.g., "thank you" vs "thank you.")
                    if clean_prev == clean_current:
                        logger.info(f"Suppressing similar transcript for {call_sid}: '{text}' (similar to '{prev_text}')")
                        return
                    
                    # Check for common variations of "thank you"
                    thank_you_variations = {
                        'thank you', 'thanks', 'thankyou', 'thank u', 'thx', 'ty',
                        'thank you.', 'thanks.', 'thankyou.', 'thank u.', 'thx.', 'ty.'
                    }
                    if (normalized_text in thank_you_variations and 
                        any(v in prev_text for v in thank_you_variations)):
                        logger.info(f"Suppressing thank you variation for {call_sid}: '{text}'")
                        return
                
                # Update tracking
                info['asr_last_text'] = normalized_text
                info['asr_last_ts'] = now_ts
                self.call_info_store[call_sid] = info
            except Exception as e:
                logger.debug(f"Duplicate transcript guard failed for {call_sid}: {e}")

            # Store the transcription
            self.transcriptions[call_sid].append(text)
            
            # Return the processed text for further handling
            return text
                
        except Exception as e:
            logger.error(f"Speech processing error for {call_sid}: {e}")
            logger.debug(f"Failed audio details for {call_sid}: {len(audio_data)} bytes, {audio_duration_ms:.0f}ms")
            return None

    def clean_and_filter_transcription(self, text: str) -> Tuple[str, bool]:
        """Clean and filter transcription for unwanted content (same as phone_service.py)"""
        if not text:
            return "", True
        
        # Remove excessive whitespace and normalize
        text = " ".join(text.split())
        
        # Filter out common noise patterns
        noise_patterns = [
            r'^\s*[.,!?;:]\s*$',  # Just punctuation
            r'^\s*[aeiou]\s*$',   # Just a single vowel
            r'^\s*[bcdfghjklmnpqrstvwxyz]\s*$',  # Just a single consonant
            r'^\s*[0-9]\s*$',     # Just a single digit
            r'^\s*[^\w\s]\s*$',   # Just a single special character
        ]
        
        import re
        for pattern in noise_patterns:
            if re.match(pattern, text, re.IGNORECASE):
                return text, True
        
        # Filter out very short garbage
        short_garbage = {"bye", "hi", "uh", "um", "hmm", "huh"}
        normalized = text.lower().strip().strip(".,!? ")
        if len(normalized) <= 3 and normalized in short_garbage:
            return text, True
        
        return text, False

    async def close(self):
        """Close HTTP client"""
        await self.http_client.aclose()

# Test function to demonstrate usage
async def test_audio_processing():
    """Test the audio processing functionality"""
    # Initialize with your OpenAI API key
    processor = TestAudioProcessor(openai_api_key="your-openai-api-key-here")
    
    try:
        # Example: Process some test audio data
        call_sid = "test_call_123"
        
        # Simulate receiving audio data (you would get this from Twilio)
        # This is just a placeholder - you'd need real audio data
        test_audio = b'\x00\x00' * 1000  # 1000 samples of silence
        
        # Process the audio
        await processor.process_audio(call_sid, test_audio)
        
        logger.info("Audio processing test completed")
        
    finally:
        await processor.close()

if __name__ == "__main__":
    # Set up logging
    logging.basicConfig(level=logging.INFO)
    
    # Run the test
    asyncio.run(test_audio_processing()) 