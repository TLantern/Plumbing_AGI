import asyncio
import logging
import os
import wave
import io
from pathlib import Path
import difflib
from typing import Tuple

# Try to import audio processing libraries
try:
    import pydub
    from pydub import AudioSegment
except ImportError:
    print("pydub not installed. Install with: pip install pydub")
    exit(1)

try:
    import librosa
    import soundfile as sf
except ImportError:
    print("librosa not installed. Install with: pip install librosa soundfile")
    exit(1)

# Import our test audio processor
import sys
import os
sys.path.append(os.path.dirname(__file__))
from test_audio_processing import TestAudioProcessor

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class AudioAccuracyTester:
    """Test audio processing accuracy against target transcription"""
    
    def __init__(self, openai_api_key: str, whisper_url: str = None):
        self.processor = TestAudioProcessor(openai_api_key, whisper_url)
        self.target_transcription = ""
        self.current_transcription = ""
        
    def load_target_transcription(self, file_path: str) -> str:
        """Load the target transcription from file"""
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Extract just the speech content, skip the "Transcription" header
        lines = content.strip().split('\n')
        speech_lines = [line.strip() for line in lines if line.strip() and line.strip() != "Transcription"]
        self.target_transcription = ' '.join(speech_lines)
        
        logger.info(f"Target transcription loaded: {len(self.target_transcription)} characters")
        logger.info(f"Target text: {self.target_transcription[:100]}...")
        return self.target_transcription
    
    def convert_mp3_to_wav(self, mp3_path: str, output_path: str = None) -> str:
        """Convert MP3 to WAV format for processing"""
        if output_path is None:
            output_path = mp3_path.replace('.mp3', '_converted.wav')
        
        # Load MP3 and convert to WAV
        audio = AudioSegment.from_mp3(mp3_path)
        
        # Convert to mono 16kHz for better Whisper compatibility
        audio = audio.set_channels(1)  # Mono
        audio = audio.set_frame_rate(16000)  # 16kHz sample rate
        audio = audio.set_sample_width(2)  # 16-bit
        
        # Export as WAV
        audio.export(output_path, format="wav")
        
        logger.info(f"Converted MP3 to WAV: {output_path}")
        logger.info(f"Audio details: {len(audio)}ms, {audio.frame_rate}Hz, {audio.channels} channel(s)")
        
        return output_path
    
    def load_wav_as_pcm(self, wav_path: str) -> Tuple[bytes, int]:
        """Load WAV file and return PCM data and sample rate"""
        with wave.open(wav_path, 'rb') as wav_file:
            sample_rate = wav_file.getframerate()
            n_frames = wav_file.getnframes()
            pcm_data = wav_file.readframes(n_frames)
            
            logger.info(f"Loaded WAV: {n_frames} frames, {sample_rate}Hz, {len(pcm_data)} bytes")
            
            return pcm_data, sample_rate
    
    def chunk_audio_data(self, pcm_data: bytes, sample_rate: int, chunk_duration_ms: int = 100) -> list:
        """Split audio data into chunks for processing"""
        bytes_per_sample = 2  # 16-bit
        bytes_per_chunk = int(sample_rate * bytes_per_sample * chunk_duration_ms / 1000)
        
        chunks = []
        for i in range(0, len(pcm_data), bytes_per_chunk):
            chunk = pcm_data[i:i + bytes_per_chunk]
            if len(chunk) > 0:
                chunks.append(chunk)
        
        logger.info(f"Split audio into {len(chunks)} chunks of ~{chunk_duration_ms}ms each")
        return chunks
    
    async def process_audio_file(self, audio_file_path: str, call_sid: str = "test_call") -> str:
        """Process entire audio file through our pipeline"""
        # Convert MP3 to WAV if needed
        if audio_file_path.endswith('.mp3'):
            wav_path = self.convert_mp3_to_wav(audio_file_path)
        else:
            wav_path = audio_file_path
        
        # Load PCM data
        pcm_data, sample_rate = self.load_wav_as_pcm(wav_path)
        
        # Update processor configuration for this sample rate
        self.processor.audio_config_store[call_sid]['sample_rate'] = sample_rate
        
        # Initialize VAD state
        self.processor.vad_states[call_sid]['stream_start_time'] = 0
        
        # Process audio in chunks to simulate real-time streaming
        chunks = self.chunk_audio_data(pcm_data, sample_rate, chunk_duration_ms=100)
        
        all_transcriptions = []
        
        # Process each chunk
        for i, chunk in enumerate(chunks):
            logger.debug(f"Processing chunk {i+1}/{len(chunks)}")
            
            # Process the chunk through our pipeline
            await self.processor.process_audio(call_sid, chunk)
        
        # Force process any remaining buffered audio
        vad_state = self.processor.vad_states[call_sid]
        if len(vad_state['fallback_buffer']) > 0:
            logger.info("Processing remaining buffered audio...")
            await self.processor.process_speech_segment(call_sid, vad_state['fallback_buffer'])
        
        # Get all transcriptions from the processor
        all_transcriptions = self.processor.transcriptions[call_sid]
        
        # Combine all transcriptions
        full_transcription = ' '.join(all_transcriptions).strip()
        self.current_transcription = full_transcription
        
        logger.info(f"Full transcription: {full_transcription}")
        return full_transcription
    
    def calculate_accuracy(self, target: str, current: str) -> float:
        """Calculate accuracy percentage between target and current transcription"""
        if not target or not current:
            return 0.0
        
        # Normalize both texts for comparison
        target_normalized = self.normalize_text(target)
        current_normalized = self.normalize_text(current)
        
        # Use difflib to calculate similarity
        similarity = difflib.SequenceMatcher(None, target_normalized, current_normalized).ratio()
        accuracy = similarity * 100
        
        logger.info(f"Accuracy: {accuracy:.2f}%")
        logger.info(f"Target (normalized): {target_normalized}")
        logger.info(f"Current (normalized): {current_normalized}")
        
        return accuracy
    
    def normalize_text(self, text: str) -> str:
        """Normalize text for comparison"""
        import re
        
        # Convert to lowercase
        text = text.lower()
        
        # Remove extra whitespace
        text = ' '.join(text.split())
        
        # Remove punctuation except apostrophes
        text = re.sub(r"[^\w\s']", ' ', text)
        
        # Remove extra spaces again
        text = ' '.join(text.split())
        
        return text.strip()
    
    def show_diff(self, target: str, current: str):
        """Show detailed diff between target and current transcription"""
        target_normalized = self.normalize_text(target)
        current_normalized = self.normalize_text(current)
        
        target_words = target_normalized.split()
        current_words = current_normalized.split()
        
        print("\n" + "="*80)
        print("DETAILED COMPARISON")
        print("="*80)
        
        # Show word-by-word diff
        differ = difflib.unified_diff(
            target_words, 
            current_words, 
            fromfile='target', 
            tofile='current', 
            lineterm='',
            n=3
        )
        
        for line in differ:
            print(line)
        
        print("\n" + "="*80)
    
    async def run_accuracy_test(self, mp3_path: str, transcription_path: str) -> float:
        """Run the complete accuracy test"""
        try:
            # Load target transcription
            self.load_target_transcription(transcription_path)
            
            # Process audio file
            logger.info("Starting audio processing...")
            transcription = await self.process_audio_file(mp3_path)
            
            # Calculate accuracy
            accuracy = self.calculate_accuracy(self.target_transcription, transcription)
            
            # Show detailed comparison
            self.show_diff(self.target_transcription, transcription)
            
            return accuracy
            
        finally:
            await self.processor.close()

# Configuration parameters that can be tuned
class AudioProcessingConfig:
    """Configuration for tuning audio processing parameters"""
    
    def __init__(self):
        # VAD Configuration
        self.vad_aggressiveness = 2
        self.vad_frame_duration_ms = 30
        self.silence_timeout_sec = 2.0
        self.problem_details_silence_timeout_sec = 3.0  # Longer timeout specifically for problem details phase
        self.min_speech_duration_sec = 0.5
        self.chunk_duration_sec = 4.0  # Regular chunk duration for normal conversations
        self.problem_details_chunk_duration_sec = 15.0  # Extended chunk duration specifically for problem details phase
        self.preroll_ignore_sec = 0.5
        self.min_start_rms = 100
        
        # Confidence thresholds
        self.transcription_confidence_threshold = -0.7
        
        # Audio quality filters
        self.min_duration_ms = 500
        self.energy_threshold_rms = 60

async def run_iterative_test():
    """Run iterative testing to optimize parameters"""
    
    # Get OpenAI API key from environment
    openai_api_key = os.getenv("OPENAI_API_KEY")
    if not openai_api_key:
        print("Please set OPENAI_API_KEY environment variable")
        return
    
    # Set up file paths
    current_dir = Path(__file__).parent
    video_dir = current_dir.parent / "video"
    mp3_path = str(video_dir / "30 Second Elevator Speech.mp3")
    transcription_path = str(video_dir / "transcription.txt")
    
    # Check if files exist
    if not os.path.exists(mp3_path):
        print(f"MP3 file not found: {mp3_path}")
        return
    
    if not os.path.exists(transcription_path):
        print(f"Transcription file not found: {transcription_path}")
        return
    
    # Initial test with default parameters
    print("Running initial accuracy test with default parameters...")
    tester = AudioAccuracyTester(openai_api_key)
    accuracy = await tester.run_accuracy_test(mp3_path, transcription_path)
    
    print(f"\nInitial accuracy: {accuracy:.2f}%")
    
    if accuracy >= 95.0:
        print("🎉 Target accuracy achieved!")
        return
    
    print("\nAccuracy below 95%. Consider tuning these parameters:")
    print("1. Reduce transcription_confidence_threshold (currently -0.7)")
    print("2. Adjust min_speech_duration_sec (currently 0.5)")
    print("3. Modify energy_threshold_rms (currently 60)")
    print("4. Tune VAD aggressiveness (currently 2)")
    print("5. Adjust silence_timeout_sec (currently 2.0)")

if __name__ == "__main__":
    asyncio.run(run_iterative_test()) 