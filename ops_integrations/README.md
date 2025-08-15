# Ops Integrations - Organized Structure

This directory contains a comprehensive system for managing plumbing service operations, now organized into logical modules for better maintainability and readability.

## 📁 Directory Structure

```
ops_integrations/
├── README.md                    # This file
├── __init__.py                  # Main package initialization
├── core/                        # Core business logic
│   ├── __init__.py
│   ├── job_booking.py          # Job scheduling and booking logic
│   ├── contact_capture.py      # Contact information handling
│   ├── inquiry_handler.py      # Customer inquiry processing
│   └── models.py               # Data models and structures
├── services/                    # Service layer implementations
│   ├── __init__.py
│   ├── phone_service.py        # Main phone call processing (renamed from phone.py)
│   ├── webhook_server.py       # Webhook handling server
│   ├── whisper_service.py      # Whisper transcription service
│   ├── plumbing_services.py    # Plumbing service management
│   └── local_whisper.py        # Local whisper processing
├── adapters/                    # Adapter layer for integrations
│   ├── __init__.py
│   ├── audio_processor.py      # Audio processing and VAD
│   ├── speech_recognizer.py    # Speech-to-text and TTS
│   ├── intent_extractor.py     # Intent classification
│   ├── conversation_manager.py # Conversation state management
│   ├── tts_manager.py          # Text-to-speech management
│   ├── external_services/      # Third-party service adapters
│   │   ├── __init__.py
│   │   ├── twilio_webhook.py   # Twilio webhook handling
│   │   ├── google_calendar.py  # Google Calendar integration
│   │   ├── sheets.py           # Google Sheets integration
│   │   └── sms.py              # SMS messaging services
│   └── integrations/           # Business system integrations
│       ├── __init__.py
│       ├── crm.py              # CRM system integration
│       ├── akaunting.py        # Akaunting accounting system
│       ├── inventory.py        # Inventory management
│       └── calender.py         # Calendar system integration
├── config/                      # Configuration files
│   ├── __init__.py
│   ├── env.example             # Environment configuration example
│   ├── requirements_*.txt      # Various requirements files
│   ├── setup_local_whisper.sh  # Local whisper setup script
│   └── min_triggers.json       # Minimum triggers configuration
├── utils/                       # Utility modules
│   ├── __init__.py
│   ├── __init_.py              # Legacy init file
│   └── =*.0                    # Version files
├── docs/                        # Documentation
│   └── LOCAL_WHISPER_SETUP.md  # Local whisper setup documentation
├── etl/                         # ETL processes
│   ├── __init__.py
│   └── ops_etl.py              # Operations ETL processing
├── flows/                       # Workflow definitions
│   ├── __init__.py
│   ├── intents.json            # Intent definitions
│   └── intents.py              # Intent processing
├── prompts/                     # Prompt templates
│   ├── __init__.py
│   ├── prompt_layer.py         # Prompt layer management
│   └── faq.md                  # FAQ documentation
├── scripts/                     # Utility scripts
│   ├── run_sync.py             # Synchronization script
│   └── sync_production.py      # Production sync script
├── tests/                       # Test suite
│   ├── __init__.py
│   ├── test_audio_processor.py
│   ├── test_speech_recognizer.py
│   ├── test_intent_extractor.py
│   ├── test_conversation_manager.py
│   ├── test_tts_manager.py
│   ├── run_tests.py
│   └── requirements-test.txt
├── Mock_crm/                    # Mock CRM for testing
├── calender.cred/               # Calendar credentials
└── __pycache__/                 # Python cache files
```

## 🏗️ Architecture Overview

### Core Layer (`core/`)
Contains the essential business logic for plumbing operations:
- **job_booking.py**: Handles job scheduling, booking, and management
- **contact_capture.py**: Manages customer contact information
- **inquiry_handler.py**: Processes customer inquiries and requests
- **models.py**: Defines data structures and models

### Service Layer (`services/`)
Implements core services and external integrations:
- **phone_service.py**: Main phone call processing system (renamed from phone.py)
- **webhook_server.py**: Handles incoming webhooks
- **whisper_service.py**: Manages speech transcription
- **plumbing_services.py**: Core plumbing service logic
- **local_whisper.py**: Local whisper processing capabilities

### Adapter Layer (`adapters/`)
Provides interfaces to external systems and services:

#### Core Adapters
- **audio_processor.py**: Audio processing and Voice Activity Detection
- **speech_recognizer.py**: Speech-to-text and text-to-speech
- **intent_extractor.py**: Intent classification and extraction
- **conversation_manager.py**: Conversation state management
- **tts_manager.py**: Text-to-speech management

#### External Services (`adapters/external_services/`)
- **twilio_webhook.py**: Twilio webhook handling
- **google_calendar.py**: Google Calendar integration
- **sheets.py**: Google Sheets integration
- **sms.py**: SMS messaging services

#### Integrations (`adapters/integrations/`)
- **crm.py**: CRM system integration
- **akaunting.py**: Akaunting accounting system
- **inventory.py**: Inventory management
- **calender.py**: Calendar system integration

### Configuration (`config/`)
Contains configuration files and setup scripts:
- Environment configuration examples
- Requirements files for different setups
- Setup scripts for local development
- Configuration JSON files

### Utilities (`utils/`)
Contains utility modules and helper functions:
- Version files
- Common utilities
- Helper classes

## 🚀 Usage

### Importing Modules

```python
# Import core modules
from ops_integrations.core import job_booking, contact_capture, inquiry_handler, models

# Import services
from ops_integrations.services import phone_service, webhook_server, whisper_service

# Import adapters
from ops_integrations.adapters import (
    audio_processor,
    speech_recognizer,
    intent_extractor,
    conversation_manager,
    tts_manager
)

# Import external service adapters
from ops_integrations.adapters.external_services import (
    twilio_webhook,
    google_calendar,
    sheets,
    sms
)

# Import integration adapters
from ops_integrations.adapters.integrations import (
    crm,
    akaunting,
    inventory,
    calender
)
```

### Running Tests

```bash
# Run all tests
python3 -m pytest tests/ -v

# Run specific module tests
python3 -m pytest tests/test_audio_processor.py -v
python3 -m pytest tests/test_speech_recognizer.py -v
python3 -m pytest tests/test_intent_extractor.py -v
python3 -m pytest tests/test_conversation_manager.py -v
python3 -m pytest tests/test_tts_manager.py -v
```

### Configuration

1. Copy `config/env.example` to `config/.env`
2. Update the environment variables as needed
3. Install dependencies from appropriate requirements files

## 🔧 Key Improvements

### 1. **Logical Organization**
- Files are now grouped by functionality
- Clear separation between core logic, services, and adapters
- Easy to locate specific functionality

### 2. **Better Naming**
- `phone.py` renamed to `phone_service.py` for clarity
- Descriptive directory names
- Consistent naming conventions

### 3. **Modular Structure**
- Each module has its own `__init__.py`
- Clear import paths
- Reduced coupling between components

### 4. **Documentation**
- Comprehensive README
- Clear module descriptions
- Usage examples

### 5. **Test Organization**
- Tests are organized alongside the main code
- Easy to run specific module tests
- Clear test structure

## 📋 Migration Notes

### File Moves
- `phone.py` → `services/phone_service.py`
- `job_booking.py` → `core/job_booking.py`
- `contact_capture.py` → `core/contact_capture.py`
- `inquiry_handler.py` → `core/inquiry_handler.py`
- `models.py` → `core/models.py`
- `webhook_server.py` → `services/webhook_server.py`
- `whisper_service.py` → `services/whisper_service.py`
- `plumbing_services.py` → `services/plumbing_services.py`
- `local_whisper.py` → `services/local_whisper.py`

### Import Updates
Update any existing imports to use the new structure:

```python
# Old imports
from ops_integrations.adapters.phone import PhoneService
from ops_integrations.job_booking import JobBooking

# New imports
from ops_integrations.services.phone_service import PhoneService
from ops_integrations.core.job_booking import JobBooking
```

## 🎯 Benefits

1. **Improved Readability**: Clear file organization makes it easy to find specific functionality
2. **Better Maintainability**: Logical grouping reduces cognitive load
3. **Enhanced Testability**: Modular structure makes testing easier
4. **Scalability**: Easy to add new modules without cluttering the root directory
5. **Documentation**: Clear structure with comprehensive documentation

This organized structure makes the codebase much more maintainable and easier to navigate for developers working on the plumbing operations system. 