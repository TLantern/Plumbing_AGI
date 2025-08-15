# Audio Processing Accuracy Test

This test suite evaluates our audio processing pipeline against a target transcription to achieve 95% accuracy.

## Files Overview

- `test_audio_processing.py` - Core audio processing implementation (same as phone_service.py)
- `audio_accuracy_test.py` - Full accuracy testing framework  
- `simple_audio_test.py` - Basic audio loading test (no API required)
- `run_accuracy_test.py` - User-friendly test runner
- `../video/30 Second Elevator Speech.mp3` - Test audio file
- `../video/transcription.txt` - Target transcription

## Quick Start

1. **Basic Test (No API Key Required)**:
   ```bash
   cd ops_integrations/tests
   python3 simple_audio_test.py
   ```
   This verifies audio loading and conversion works correctly.

2. **Full Accuracy Test (Requires OpenAI API Key)**:
   ```bash
   cd ops_integrations/tests
   python3 run_accuracy_test.py
   ```
   This will prompt for your OpenAI API key and run the complete test.

## What the Test Does

1. **Audio Processing**:
   - Converts MP3 to WAV (16kHz, mono)
   - Splits audio into 100ms chunks
   - Processes through VAD (Voice Activity Detection)
   - Applies speech segmentation and filtering

2. **Transcription**:
   - Uses OpenAI Whisper for speech-to-text
   - Applies confidence filtering and noise suppression
   - Cleans and normalizes text output

3. **Accuracy Measurement**:
   - Compares result with target transcription
   - Uses text similarity algorithms
   - Reports percentage accuracy

## Tuning Parameters

If accuracy is below 95%, adjust these parameters in `test_audio_processing.py`:

### VAD Configuration
- `vad_aggressiveness` (1-3): Lower = more sensitive
- `silence_timeout_sec`: How long to wait before ending speech
- `min_speech_duration_sec`: Minimum speech length to process

### Confidence Thresholds  
- `transcription_confidence_threshold`: Lower = accept more transcriptions
- `energy_threshold_rms`: Lower = accept quieter audio

### Audio Quality Filters
- `min_duration_ms`: Minimum segment duration
- `preroll_ignore_sec`: Ignore audio at start

## Target Transcription

The test aims to transcribe this speech:

> "As a former basketball player, football player, and youth coach, I love all aspects of sports and have a genuine passion for discussing them and the impact that it has on our youth and society as a whole. I'm Nathan Monford. I work at the Limited Brands Warehouse. I'm also a student at the Ohio Center for Broadcasting, where I'm learning the art of radio and television production, as well as web design. I host a sports talk radio show called The Arena, which can be heard every Tuesday, 4 to 6 p.m. Eastern Standard Time, 10 a.m. in Hawaii, on scoreonair.com. Currently, I'm working on developing my website for networking and promoting my show, The Arena. So to sum it up in five words, I was born for this. Thanks for your time. I'll see you next Tuesday in The Arena. I'm Nathan Monford, hashtag living the dream."

## Expected Results

- **Audio Duration**: ~54.5 seconds
- **Target Word Count**: 152 words  
- **Processing Chunks**: ~545 chunks
- **Target Accuracy**: ≥95%

## Next Steps

Once 95% accuracy is achieved:

1. Copy the optimized parameters from `test_audio_processing.py`
2. Update the main `phone_service.py` with the same parameters
3. Deploy the updated audio processing pipeline

## Troubleshooting

- **Import errors**: Ensure all dependencies are installed (`pip install pydub librosa soundfile webrtcvad`)
- **ffmpeg errors**: Install ffmpeg (`brew install ffmpeg` on macOS)
- **API errors**: Verify your OpenAI API key is valid
- **Audio errors**: Check that the MP3 file exists and is readable 