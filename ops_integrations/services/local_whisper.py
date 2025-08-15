import whisper
import torch
import logging
import io
import wave
import numpy as np
from typing import Optional, Dict, Any
import time

logger = logging.getLogger("local-whisper")

class LocalWhisperAdapter:
    """
    Self-hosted Whisper v3 adapter for high-quality transcription.
    """
    
    def __init__(self, model_name: str = "large-v3", device: Optional[str] = None):
        """
        Initialize local Whisper model.
        
        Args:
            model_name: Whisper model to use ("large-v3", "large-v2", "base", etc.)
            device: Device to use ("cuda", "cpu", or None for auto-detect)
        """
        self.model_name = model_name
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.model = None
        self._load_model()
    
    def _load_model(self):
        """Load the Whisper model."""
        try:
            logger.info(f"Loading Whisper model '{self.model_name}' on device '{self.device}'")
            start_time = time.time()
            self.model = whisper.load_model(self.model_name, device=self.device)
            load_time = time.time() - start_time
            logger.info(f"Whisper model loaded in {load_time:.2f}s")
        except Exception as e:
            logger.error(f"Failed to load Whisper model: {e}")
            raise
    
    def transcribe_audio(self, audio_data: bytes, sample_rate: int = 16000, 
                        language: str = "en", fp16: bool = None) -> Dict[str, Any]:
        """
        Transcribe audio data using local Whisper model.
        
        Args:
            audio_data: Raw audio bytes (PCM16)
            sample_rate: Audio sample rate
            language: Language code (e.g., "en")
            fp16: Use fp16 precision (True for GPU, False for CPU)
            
        Returns:
            Dict with transcription results including text, segments, etc.
        """
        if self.model is None:
            raise RuntimeError("Whisper model not loaded")
        
        try:
            # Convert PCM16 bytes to numpy array
            audio_array = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32) / 32768.0
            
            # Resample if needed (Whisper expects 16kHz)
            if sample_rate != 16000:
                audio_array = self._resample_audio(audio_array, sample_rate, 16000)
            
            # Set fp16 based on device if not specified
            if fp16 is None:
                fp16 = self.device == "cuda"
            
            start_time = time.time()
            
            # Transcribe using local model
            result = self.model.transcribe(
                audio_array,
                language=language,
                fp16=fp16,
                verbose=False
            )
            
            transcription_time = time.time() - start_time
            logger.info(f"Local Whisper transcription completed in {transcription_time:.2f}s")
            
            # Add metadata
            result["transcription_time"] = transcription_time
            result["model"] = self.model_name
            result["device"] = self.device
            
            return result
            
        except Exception as e:
            logger.error(f"Local Whisper transcription failed: {e}")
            raise
    
    def _resample_audio(self, audio_array: np.ndarray, src_rate: int, dst_rate: int) -> np.ndarray:
        """
        Simple resampling using scipy if available, otherwise basic interpolation.
        """
        try:
            from scipy import signal
            # Use scipy for high-quality resampling
            samples = len(audio_array)
            new_samples = int(samples * dst_rate / src_rate)
            resampled = signal.resample(audio_array, new_samples)
            return resampled.astype(np.float32)
        except ImportError:
            # Fallback to basic interpolation
            logger.warning("scipy not available, using basic resampling")
            samples = len(audio_array)
            new_samples = int(samples * dst_rate / src_rate)
            indices = np.linspace(0, samples - 1, new_samples)
            resampled = np.interp(indices, np.arange(samples), audio_array)
            return resampled.astype(np.float32)
    
    def get_model_info(self) -> Dict[str, Any]:
        """Get information about the loaded model."""
        return {
            "model_name": self.model_name,
            "device": self.device,
            "cuda_available": torch.cuda.is_available(),
            "model_loaded": self.model is not None
        }

# Global instance for reuse
_local_whisper_instance: Optional[LocalWhisperAdapter] = None

def get_local_whisper(model_name: str = "large-v3", device: Optional[str] = None) -> LocalWhisperAdapter:
    """
    Get or create a global LocalWhisperAdapter instance.
    
    Args:
        model_name: Whisper model to use
        device: Device to use
        
    Returns:
        LocalWhisperAdapter instance
    """
    global _local_whisper_instance
    
    if _local_whisper_instance is None:
        _local_whisper_instance = LocalWhisperAdapter(model_name, device)
    
    return _local_whisper_instance

def transcribe_with_local_whisper(audio_data: bytes, sample_rate: int = 16000, 
                                 language: str = "en", model_name: str = "large-v3") -> Dict[str, Any]:
    """
    Convenience function to transcribe audio using local Whisper.
    
    Args:
        audio_data: Raw audio bytes (PCM16)
        sample_rate: Audio sample rate
        language: Language code
        model_name: Whisper model name
        
    Returns:
        Transcription result dict
    """
    adapter = get_local_whisper(model_name)
    return adapter.transcribe_audio(audio_data, sample_rate, language) 