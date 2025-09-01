# Phone System Modularization

This document describes the modularization of the `phone.py` system into 5 core modules for better testing, maintainability, and separation of concerns.

## Overview

The original `phone.py` file was a monolithic 4000+ line file handling all aspects of voice call processing. It has been broken down into 5 focused modules:

## Module 1: AudioProcessor (`audio_processor.py`)

**Purpose**: Handles audio processing, Voice Activity Detection (VAD), and speech segmentation.

**Key Responsibilities**:
- Audio buffer management per call
- Voice Activity Detection using webrtcvad
- Speech/silence state tracking
- Audio frame processing
- Buffer flushing decisions

**Key Methods**:
- `process_audio(call_sid, audio)` - Process incoming audio data
- `should_flush_buffer(call_sid)` - Determine when to process audio
- `get_and_clear_buffer(call_sid)` - Get and clear audio buffer
- `cleanup_call(call_sid)` - Clean up resources

**Dependencies**:
- webrtcvad (with fallback to dummy VAD)
- Standard library: asyncio, logging, time, collections

## Module 2: SpeechRecognizer (`speech_recognizer.py`)

**Purpose**: Handles speech-to-text transcription and text-to-speech generation.

**Key Responsibilities**:
- Audio transcription using OpenAI Whisper or remote service
- Text-to-speech generation using OpenAI TTS
- Audio format conversion (mu-law to WAV)
- Confidence scoring for transcripts

**Key Methods**:
- `transcribe_audio(audio_data, call_sid)` - Transcribe audio to text
- `synthesize_tts(text, call_sid)` - Generate speech from text
- `should_suppress_transcript(text, avg_logprob)` - Filter low-quality transcripts

**Dependencies**:
- OpenAI API
- httpx for HTTP requests
- wave, io for audio processing

## Module 3: IntentExtractor (`intent_extractor.py`)

**Purpose**: Extracts and classifies intents from customer text.

**Key Responsibilities**:
- Intent extraction using OpenAI function calling
- Plumbing service keyword matching
- Urgency detection
- Confidence scoring
- Handoff decision logic

**Key Methods**:
- `extract_intent_from_text(text, call_sid)` - Extract structured intent
- `should_handoff_to_human(args)` - Determine if human handoff needed
- `classify_transcript_intent(text)` - Simple intent classification

**Dependencies**:
- OpenAI API for function calling
- JSON processing for structured data

## Module 4: ConversationManager (`conversation_manager.py`)

**Purpose**: Manages conversation state and dialog flow.

**Key Responsibilities**:
- Dialog state management per call
- Duplicate transcript suppression
- Repeated utterance detection
- Clarification attempts tracking
- Call information storage

**Key Methods**:
- `get_dialog_state(call_sid)` / `set_dialog_state(call_sid, state)`
- `should_suppress_duplicate(call_sid, text)` - Prevent duplicate processing
- `should_suppress_repeated_utterance(call_sid, text)` - Detect stuck users
- `increment_clarification_attempts(call_sid)` - Track clarification attempts

**Dependencies**:
- Standard library only: time, collections, logging

## Module 5: TTSManager (`tts_manager.py`)

**Purpose**: Handles text-to-speech generation and speech gate management.

**Key Responsibilities**:
- TTS caching for performance
- Speech gate activation/deactivation
- TTS duration estimation
- Cache management

**Key Methods**:
- `synthesize_tts(text, call_sid)` - Generate TTS with caching
- `activate_speech_gate(call_sid, text)` - Prevent overlapping speech
- `is_speech_gate_active(call_sid)` - Check gate status
- `cleanup_call(call_sid)` - Clean up TTS resources

**Dependencies**:
- SpeechRecognizer (for TTS generation)
- asyncio for async operations

## Testing Strategy

### Unit Tests Created

Each module has comprehensive unit tests covering:

1. **AudioProcessor Tests** (`test_audio_processor.py`):
   - Initialization and configuration
   - Audio processing and buffer management
   - VAD state management
   - Buffer flushing logic
   - Multiple call isolation
   - Error handling and fallbacks

2. **SpeechRecognizer Tests** (`test_speech_recognizer.py`):
   - OpenAI and remote Whisper transcription
   - TTS generation
   - Audio format conversion
   - Confidence threshold filtering
   - Error handling

3. **IntentExtractor Tests** (`test_intent_extractor.py`):
   - Intent extraction with function calling
   - Keyword matching and job type inference
   - Urgency detection
   - Confidence scoring
   - Handoff decision logic
   - Fallback handling

4. **ConversationManager Tests** (`test_conversation_manager.py`):
   - Dialog state management
   - Duplicate suppression
   - Repeated utterance detection
   - Clarification attempts tracking
   - Call isolation
   - Cleanup operations

5. **TTSManager Tests** (`test_tts_manager.py`):
   - TTS caching and retrieval
   - Speech gate management
   - Cache overflow handling
   - Duration estimation
   - Resource cleanup

### Running Tests

```bash
# Install test dependencies
pip install -r tests/requirements-test.txt

# Run all tests
python tests/run_tests.py

# Run specific module tests
python tests/run_tests.py audio_processor
python tests/run_tests.py speech_recognizer
python tests/run_tests.py intent_extractor
python tests/run_tests.py conversation_manager
python tests/run_tests.py tts_manager

# Run with pytest directly
pytest tests/ -v
pytest tests/test_audio_processor.py -v
```

## Benefits of Modularization

### 1. **Testability**
- Each module can be tested in isolation
- Mock dependencies easily
- Focused test coverage
- Faster test execution

### 2. **Maintainability**
- Smaller, focused files
- Clear separation of concerns
- Easier to understand and modify
- Reduced cognitive load

### 3. **Reusability**
- Modules can be used independently
- Easy to swap implementations
- Clear interfaces between modules

### 4. **Debugging**
- Easier to isolate issues
- Better error messages
- Focused logging per module

### 5. **Performance**
- Parallel processing possible
- Better resource management
- Optimized caching strategies

## Integration with Original System

The modularized components can be integrated back into the original `phone.py` system by:

1. **Importing modules**:
```python
from ops_integrations.adapters.audio_processor import AudioProcessor
from ops_integrations.adapters.speech_recognizer import SpeechRecognizer
from ops_integrations.adapters.intent_extractor import IntentExtractor
from ops_integrations.adapters.conversation_manager import ConversationManager
from ops_integrations.adapters.tts_manager import TTSManager
```

2. **Initializing components**:
```python
# Initialize components
audio_processor = AudioProcessor()
speech_recognizer = SpeechRecognizer(openai_api_key=OPENAI_API_KEY)
intent_extractor = IntentExtractor(openai_api_key=OPENAI_API_KEY)
conversation_manager = ConversationManager()
tts_manager = TTSManager(speech_recognizer)
```

3. **Replacing monolithic functions** with calls to modular components.

## Future Enhancements

1. **Configuration Management**: Add configuration files for each module
2. **Metrics Collection**: Add performance metrics per module
3. **Plugin Architecture**: Allow swapping implementations
4. **Distributed Processing**: Run modules on different services
5. **A/B Testing**: Easy to test different implementations

## Migration Guide

To migrate from the monolithic `phone.py` to the modular system:

1. **Phase 1**: Run both systems in parallel
2. **Phase 2**: Gradually replace functions with module calls
3. **Phase 3**: Remove old monolithic code
4. **Phase 4**: Optimize and enhance modules

This modularization provides a solid foundation for future development while maintaining the existing functionality and improving the overall system architecture. 