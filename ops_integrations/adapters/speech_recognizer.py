import asyncio
import logging
import base64
import io
import wave
from typing import Optional, Dict, Any, Tuple
import httpx
from openai import OpenAI
import os

logger = logging.getLogger(__name__)

class SpeechRecognizer:
    """Handles speech-to-text transcription and text-to-speech generation"""
    
    def __init__(self, openai_api_key: str, whisper_url: Optional[str] = None):
        self.openai_client = OpenAI(api_key=openai_api_key)
        self.whisper_url = whisper_url
        self.http_client = httpx.AsyncClient(timeout=30.0)
        
        # TTS Configuration
        self.tts_speed = 1.25
        self.tts_voice = "alloy"
        self.tts_model = "tts-1"
        
        # Transcription Configuration
        self.transcription_confidence_threshold = -0.7  # Optimized based on 99.75% accuracy test
        self.remote_whisper_enabled = whisper_url is not None
        
    async def transcribe_audio(self, audio_data: bytes, call_sid: str) -> Tuple[Optional[str], float, Optional[float]]:
        """Transcribe audio data to text using Whisper"""
        try:
            if self.remote_whisper_enabled:
                return await self._transcribe_remote(audio_data, call_sid)
            else:
                return await self._transcribe_openai(audio_data, call_sid)
        except Exception as e:
            logger.error(f"Transcription failed for {call_sid}: {e}")
            return None, 0.0, None
    
    async def _transcribe_remote(self, audio_data: bytes, call_sid: str) -> Tuple[Optional[str], float, Optional[float]]:
        """Transcribe using remote Whisper service"""
        try:
            start_time = asyncio.get_event_loop().time()
            
            # Convert mu-law to WAV format
            wav_data = self._convert_mulaw_to_wav(audio_data)
            
            # Send to remote Whisper service
            files = {"file": ("audio.wav", wav_data, "audio/wav")}
            url = f"{self.whisper_url.rstrip('/')}/transcribe"
            response = await self.http_client.post(url, files=files)
            
            if response.status_code == 200:
                result = response.json()
                text = result.get("text", "").strip()
                avg_logprob = result.get("avg_logprob")
                
                transcription_time = asyncio.get_event_loop().time() - start_time
                logger.info(f"Remote Whisper transcription completed for {call_sid} in {transcription_time:.2f}s")
                
                return text, transcription_time, avg_logprob
            else:
                reason = getattr(response, "reason_phrase", "")
                elapsed = getattr(response, "elapsed", None)
                elapsed_s = f"{elapsed.total_seconds():.2f}s" if elapsed else "N/A"
                content_type = response.headers.get("content-type", "")
                body_text = None
                error_json = None
                try:
                    # Prefer JSON error details if present
                    error_json = response.json()
                except Exception:
                    try:
                        body = response.text or ""
                        body_text = body if len(body) <= 1000 else body[:1000] + "...(truncated)"
                    except Exception:
                        body_text = "<unreadable body>"

                logger.error(
                    f"Remote Whisper failed for {call_sid}: status={response.status_code} reason='{reason}' "
                    f"url={url} elapsed={elapsed_s} content_type='{content_type}'"
                )
                if error_json is not None:
                    logger.error(f"Remote Whisper error body (json) for {call_sid}: {error_json}")
                elif body_text:
                    logger.error(f"Remote Whisper error body (text) for {call_sid}: {body_text}")
                return None, 0.0, None
                
        except Exception as e:
            request_url = None
            try:
                if isinstance(e, httpx.RequestError) and getattr(e, "request", None) is not None:
                    request_url = str(e.request.url)
            except Exception:
                request_url = None
            error_type = type(e).__name__
            detail = str(e)
            logger.error(
                f"Remote Whisper exception for {call_sid}: type={error_type} url={request_url or (self.whisper_url and self.whisper_url.rstrip('/') + '/transcribe')} detail={detail}"
            )
            return None, 0.0, None
    
    async def _transcribe_openai(self, audio_data: bytes, call_sid: str) -> Tuple[Optional[str], float, Optional[float]]:
        """Transcribe using OpenAI Whisper"""
        try:
            start_time = asyncio.get_event_loop().time()
            
            # Convert mu-law to WAV format
            wav_data = self._convert_mulaw_to_wav(audio_data)
            
            # Send to OpenAI Whisper
            response = await asyncio.to_thread(
                self.openai_client.audio.transcriptions.create,
                model="whisper-1",
                file=("audio.wav", wav_data, "audio/wav"),
                response_format="verbose_json"
            )
            
            text = response.text.strip()
            avg_logprob = getattr(response, 'avg_logprob', None)
            
            transcription_time = asyncio.get_event_loop().time() - start_time
            logger.info(f"OpenAI Whisper transcription completed for {call_sid} in {transcription_time:.2f}s")
            
            return text, transcription_time, avg_logprob
            
        except Exception as e:
            logger.error(f"OpenAI Whisper failed for {call_sid}: {e}")
            return None, 0.0, None
    
    def _convert_mulaw_to_wav(self, mulaw_data: bytes) -> bytes:
        """Convert mu-law encoded audio to WAV format"""
        try:
            # Convert mu-law to PCM
            pcm_data = self._mulaw_to_pcm(mulaw_data)
            
            # Create WAV file
            wav_buffer = io.BytesIO()
            with wave.open(wav_buffer, 'wb') as wav_file:
                wav_file.setnchannels(1)  # Mono
                wav_file.setsampwidth(2)  # 16-bit
                wav_file.setframerate(8000)  # 8kHz
                wav_file.writeframes(pcm_data)
            
            return wav_buffer.getvalue()
            
        except Exception as e:
            logger.error(f"Audio conversion failed: {e}")
            return mulaw_data
    
    def _mulaw_to_pcm(self, mulaw_data: bytes) -> bytes:
        """Convert mu-law encoded bytes to PCM"""
        # Mu-law to PCM conversion table
        MULAW_DECODE_TABLE = [
            -32124, -31100, -30076, -29052, -28028, -27004, -25980, -24956,
            -23932, -22908, -21884, -20860, -19836, -18812, -17788, -16764,
            -15996, -15484, -14972, -14460, -13948, -13436, -12924, -12412,
            -11900, -11388, -10876, -10364, -9852, -9340, -8828, -8316,
            -7932, -7676, -7420, -7164, -6908, -6652, -6396, -6140,
            -5884, -5628, -5372, -5116, -4860, -4604, -4348, -4092,
            -3900, -3772, -3644, -3516, -3388, -3260, -3132, -3004,
            -2876, -2748, -2620, -2492, -2364, -2236, -2108, -1980,
            -1884, -1820, -1756, -1692, -1628, -1564, -1500, -1436,
            -1372, -1308, -1244, -1180, -1116, -1052, -988, -924,
            -876, -844, -812, -780, -748, -716, -684, -652,
            -620, -588, -556, -524, -492, -460, -428, -396,
            -372, -356, -340, -324, -308, -292, -276, -260,
            -244, -228, -212, -196, -180, -164, -148, -132,
            -120, -112, -104, -96, -88, -80, -72, -64,
            -56, -48, -40, -32, -24, -16, -8, 0,
            32124, 31100, 30076, 29052, 28028, 27004, 25980, 24956,
            23932, 22908, 21884, 20860, 19836, 18812, 17788, 16764,
            15996, 15484, 14972, 14460, 13948, 13436, 12924, 12412,
            11900, 11388, 10876, 10364, 9852, 9340, 8828, 8316,
            7932, 7676, 7420, 7164, 6908, 6652, 6396, 6140,
            5884, 5628, 5372, 5116, 4860, 4604, 4348, 4092,
            3900, 3772, 3644, 3516, 3388, 3260, 3132, 3004,
            2876, 2748, 2620, 2492, 2364, 2236, 2108, 1980,
            1884, 1820, 1756, 1692, 1628, 1564, 1500, 1436,
            1372, 1308, 1244, 1180, 1116, 1052, 988, 924,
            876, 844, 812, 780, 748, 716, 684, 652,
            620, 588, 556, 524, 492, 460, 428, 396,
            372, 356, 340, 324, 308, 292, 276, 260,
            244, 228, 212, 196, 180, 164, 148, 132,
            120, 112, 104, 96, 88, 80, 72, 64,
            56, 48, 40, 32, 24, 16, 8, 0
        ]
        
        pcm_data = bytearray()
        for byte in mulaw_data:
            pcm_value = MULAW_DECODE_TABLE[byte]
            pcm_data.extend(pcm_value.to_bytes(2, byteorder='little', signed=True))
        
        return bytes(pcm_data)
    
    async def synthesize_tts(self, text: str, call_sid: str) -> Optional[bytes]:
        """Generate speech from text using OpenAI TTS"""
        try:
            if not text.strip():
                return None
            
            logger.info(f"🗣️ TTS SAY ({text[:20]}...) for CallSid={call_sid}: {text}")
            
            # Generate speech using OpenAI TTS
            response = await asyncio.to_thread(
                self.openai_client.audio.speech.create,
                model=self.tts_model,
                voice=self.tts_voice,
                input=text,
                speed=self.tts_speed
            )
            
            audio_data = response.content
            
            logger.info(f"🗣️ OpenAI TTS PLAY for CallSid={call_sid}: bytes={len(audio_data)} text={text}")
            
            return audio_data
            
        except Exception as e:
            logger.error(f"TTS generation failed for {call_sid}: {e}")
            return None
    
    def should_suppress_transcript(self, text: str, avg_logprob: Optional[float]) -> bool:
        """Determine if transcript should be suppressed based on confidence"""
        if not text.strip():
            return True
        
        # Check confidence threshold
        if avg_logprob is not None and avg_logprob < self.transcription_confidence_threshold:
            return True
        
        # Suppress very short transcripts
        if len(text.strip()) < 2:
            return True
        
        return False
    
    async def close(self):
        """Close HTTP client"""
        await self.http_client.aclose() 