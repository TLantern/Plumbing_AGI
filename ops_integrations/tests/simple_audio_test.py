import asyncio
import logging
import os
import wave
import io
from pathlib import Path
import difflib

# Try to import audio processing libraries
try:
    import pydub
    from pydub import AudioSegment
except ImportError:
    print("pydub not installed. Install with: pip install pydub")
    exit(1)

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class SimpleAudioTester:
    """Simple audio file processor to test loading and format conversion"""
    
    def __init__(self):
        self.target_transcription = ""
        
    def load_target_transcription(self, file_path: str) -> str:
        """Load the target transcription from file"""
        logger.info(f"Loading transcription from: {file_path}")
        logger.info(f"File exists: {os.path.exists(file_path)}")
        
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        logger.info(f"Raw content length: {len(content)}")
        logger.info(f"Raw content preview: {repr(content[:200])}")
        
        # Extract just the speech content, skip the "Transcription" header
        lines = content.strip().split('\n')
        speech_lines = [line.strip() for line in lines if line.strip() and line.strip() != "Transcription"]
        self.target_transcription = ' '.join(speech_lines)
        
        logger.info(f"Extracted {len(speech_lines)} speech lines")
        logger.info(f"Target transcription loaded: {len(self.target_transcription)} characters")
        logger.info(f"Target text: {self.target_transcription[:100]}...")
        return self.target_transcription
    
    def convert_mp3_to_wav(self, mp3_path: str, output_path: str = None) -> str:
        """Convert MP3 to WAV format for processing"""
        if output_path is None:
            output_path = mp3_path.replace('.mp3', '_converted.wav')
        
        # Load MP3 and convert to WAV
        audio = AudioSegment.from_mp3(mp3_path)
        
        logger.info(f"Original audio: {len(audio)}ms, {audio.frame_rate}Hz, {audio.channels} channel(s)")
        
        # Convert to mono 16kHz for better Whisper compatibility
        audio = audio.set_channels(1)  # Mono
        audio = audio.set_frame_rate(16000)  # 16kHz sample rate
        audio = audio.set_sample_width(2)  # 16-bit
        
        # Export as WAV
        audio.export(output_path, format="wav")
        
        logger.info(f"Converted MP3 to WAV: {output_path}")
        logger.info(f"Converted audio: {len(audio)}ms, {audio.frame_rate}Hz, {audio.channels} channel(s)")
        
        return output_path
    
    def analyze_wav_file(self, wav_path: str):
        """Analyze WAV file properties"""
        with wave.open(wav_path, 'rb') as wav_file:
            sample_rate = wav_file.getframerate()
            n_frames = wav_file.getnframes()
            n_channels = wav_file.getnchannels()
            sample_width = wav_file.getsampwidth()
            duration_sec = n_frames / sample_rate
            
            logger.info(f"WAV Analysis:")
            logger.info(f"  Sample rate: {sample_rate} Hz")
            logger.info(f"  Channels: {n_channels}")
            logger.info(f"  Sample width: {sample_width} bytes")
            logger.info(f"  Frames: {n_frames}")
            logger.info(f"  Duration: {duration_sec:.2f} seconds")
            
            # Read a small chunk to check audio data
            pcm_data = wav_file.readframes(min(1000, n_frames))
            logger.info(f"  PCM data sample: {len(pcm_data)} bytes")
            
            return {
                'sample_rate': sample_rate,
                'channels': n_channels,
                'sample_width': sample_width,
                'frames': n_frames,
                'duration': duration_sec,
                'pcm_sample': pcm_data
            }
    
    def estimate_chunks(self, duration_sec: float, chunk_duration_ms: int = 100) -> int:
        """Estimate how many chunks the audio would be split into"""
        chunks = int((duration_sec * 1000) / chunk_duration_ms)
        logger.info(f"Audio would be split into approximately {chunks} chunks of {chunk_duration_ms}ms each")
        return chunks
    
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
    
    def run_basic_test(self, mp3_path: str, transcription_path: str):
        """Run basic audio file analysis"""
        try:
            # Load target transcription
            self.load_target_transcription(transcription_path)
            
            # Convert MP3 to WAV
            logger.info("Converting MP3 to WAV...")
            wav_path = self.convert_mp3_to_wav(mp3_path)
            
            # Analyze WAV file
            logger.info("Analyzing WAV file...")
            wav_info = self.analyze_wav_file(wav_path)
            
            # Estimate processing chunks
            self.estimate_chunks(wav_info['duration'])
            
            # Show what we're aiming for
            normalized_target = self.normalize_text(self.target_transcription)
            logger.info(f"Target (normalized): {normalized_target}")
            logger.info(f"Target word count: {len(normalized_target.split())}")
            
            return wav_info
            
        except Exception as e:
            logger.error(f"Error in basic test: {e}")
            return None

def run_simple_test():
    """Run simple audio analysis without API calls"""
    
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
    
    # Run basic test
    print("Running basic audio analysis...")
    tester = SimpleAudioTester()
    wav_info = tester.run_basic_test(mp3_path, transcription_path)
    
    if wav_info:
        print(f"\n✅ Basic audio analysis completed successfully!")
        print(f"Audio duration: {wav_info['duration']:.2f} seconds")
        print(f"Ready for transcription testing with audio processing pipeline.")
    else:
        print("❌ Basic audio analysis failed")

if __name__ == "__main__":
    run_simple_test() 