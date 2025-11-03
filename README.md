# Plumbing AGI - AI-Powered Service Business Operations Platform

An intelligent, multi-service AI platform designed for automating customer interactions, bookings, and operations for service-based businesses including salons, plumbing, HVAC, and other service industries.

## 🎯 Overview

Plumbing AGI is a comprehensive AI-powered operations platform that handles:
- **Voice AI Phone System**: Real-time phone call handling with intelligent conversation management
- **Multi-Location Support**: Manage multiple business locations with individual settings
- **Smart Booking System**: AI-driven appointment scheduling and confirmation
- **CRM Integration**: Seamless integration with popular CRM systems (Baserow, Akaunting)
- **Website Knowledge Scraping**: Automated extraction of business information for AI responses
- **Analytics & Reporting**: Real-time call analytics and performance tracking
- **SMS & Communication**: Multi-channel customer communication

## 🚀 Key Features

### 1. AI Phone System
- Real-time voice conversations using ElevenLabs TTS and OpenAI GPT-4
- WebSocket-based audio streaming with Twilio
- Intent detection and automatic call routing
- Natural language understanding for booking requests
- Support for multiple languages and accents

### 2. Smart Booking Management
- Automatic appointment scheduling from phone conversations
- Service catalog management with pricing and duration
- Stylist/technician availability tracking
- Calendar integration (Google Calendar)
- SMS confirmations and reminders

### 3. Multi-Location Support
- Separate configurations per location
- Location-specific service catalogs
- Individual AI agents with custom prompts
- Timezone-aware scheduling
- Location-specific analytics

### 4. Integration Ecosystem
- **Twilio**: Voice and SMS communication
- **OpenAI GPT-4**: Conversational AI
- **ElevenLabs**: High-quality text-to-speech
- **Supabase**: Database and authentication
- **Google Sheets/Calendar**: Data sync and scheduling
- **Square**: Payment and booking integration
- **Akaunting**: Accounting and invoicing
- **Baserow**: CRM and customer management

### 5. Knowledge Management
- Automated website scraping for business information
- Static data caching for instant AI responses
- Service catalog extraction and categorization
- Staff information and specialties
- FAQ handling from website content

## 📁 Project Structure

```
plumbing_AGI/
├── ops_integrations/          # Core operations platform
│   ├── core/                  # Business logic
│   │   ├── job_booking.py
│   │   ├── contact_capture.py
│   │   ├── inquiry_handler.py
│   │   └── models.py
│   ├── services/              # Service implementations
│   │   ├── salon_phone_service.py
│   │   ├── phone_service.py
│   │   ├── booking_service.py
│   │   ├── website_scraper.py
│   │   └── whisper_service.py
│   ├── adapters/              # External integrations
│   │   ├── audio_processor.py
│   │   ├── speech_recognizer.py
│   │   ├── intent_extractor.py
│   │   ├── conversation_manager.py
│   │   └── external_services/
│   ├── square/                # Square API integration
│   └── tests/                 # Test suite
├── frontend/                  # Next.js frontend dashboard
├── Magiclink/                 # Authentication service
├── akaunting/                 # Accounting system integration
├── scripts/                   # Utility scripts
├── extras/                    # Setup guides and documentation
└── docs/                      # Documentation files
```

## 🛠 Installation

### Prerequisites
- Python 3.8+
- Node.js 16+ (for frontend)
- PostgreSQL database
- Twilio account
- OpenAI API key
- ElevenLabs API key

### Quick Start

1. **Clone the repository**
```bash
git clone <repository-url>
cd wiAec
```

2. **Install Python dependencies**
```bash
pip install -r requirements.txt
```

3. **Set up environment variables**
```bash
cp extras/env_template.txt .env
# Edit .env with your credentials
```

4. **Initialize the database**
```bash
python -m ops_integrations.services.init_db
```

5. **Install frontend dependencies**
```bash
cd frontend
npm install
cd ..
```

6. **Run the development environment**
```bash
npm run dev
```

This starts three services:
- Magic Link auth server (port 8000)
- Phone service API (port 5001)
- Frontend dashboard (port 3000)

## 🔧 Configuration

### Environment Variables

Create a `.env` file with the following variables:

```bash
# Database
DATABASE_URL=postgresql://user:pass@host:port/db

# Twilio
TWILIO_ACCOUNT_SID=your_account_sid
TWILIO_AUTH_TOKEN=your_auth_token
CI_SERVICE_SID=your_ci_service_sid

# OpenAI
OPENAI_API_KEY=your_openai_key

# ElevenLabs
ELEVENLABS_API_KEY=your_elevenlabs_key
ELEVENLABS_VOICE_ID=kdmDKE6EkgrWrrykO9Qt

# Supabase
SUPABASE_URL=your_supabase_url
SUPABASE_KEY=your_supabase_key

# Google Services (Optional)
GOOGLE_SHEETS_CREDENTIALS=path/to/credentials.json
GOOGLE_CALENDAR_CREDENTIALS=path/to/calendar_credentials.json

# Square (Optional)
SQUARE_ACCESS_TOKEN=your_square_token
SQUARE_ENVIRONMENT=sandbox

# URLs
PUBLIC_BASE_URL=http://localhost:5001
WSS_PUBLIC_URL=ws://localhost:5001
```

### Database Schema

The platform uses a multi-location schema:

- **locations**: Business locations with settings
- **agents**: AI agents per location with custom prompts
- **services**: Service catalog with pricing
- **bookings**: Appointment tracking
- **calls**: Call history and analytics

Run migrations:
```bash
python setup_supabase_tables.py
```

## 🚀 Deployment

### Heroku Deployment

1. **Create Heroku app**
```bash
heroku create your-app-name
heroku addons:create heroku-postgresql:mini
```

2. **Set environment variables**
```bash
heroku config:set OPENAI_API_KEY=your_key
heroku config:set TWILIO_ACCOUNT_SID=your_sid
# ... set all required variables
```

3. **Deploy**
```bash
git push heroku main
```

4. **Initialize database**
```bash
heroku run python -m ops_integrations.services.init_db
```

See `deploy-to-heroku.md` for detailed deployment instructions.

## 📱 Usage Examples

### Phone Call Flow

1. Customer calls the Twilio number
2. AI agent answers with location-specific greeting
3. Conversation manager extracts intent (booking, inquiry, etc.)
4. AI provides information from scraped website data
5. If booking intent detected, initiates booking flow
6. Collects customer details and confirms appointment
7. Sends SMS confirmation
8. Logs call data and transcript to database

### Adding a New Location

```python
from ops_integrations.services.salon_phone_service import setup_location

location_data = {
    "name": "SoHo Salon Denton",
    "phone": "19405650880",
    "website": "https://sohosalondenton.glossgenius.com",
    "timezone": "America/Chicago"
}

setup_location(location_data)
```

### Scraping Website Data

```python
from ops_integrations.services.website_scraper import scrape_business_info

data = scrape_business_info("https://yourbusiness.com")
# Automatically extracts services, pricing, staff, and FAQs
```

## 🧪 Testing

Run the test suite:

```bash
# All tests
python -m pytest tests/ -v

# Specific module
python -m pytest ops_integrations/tests/test_phone_ws.py -v

# Phone system integration test
python test_phone_calls.py

# Complete integration test
python test_complete_integration.py
```

## 📊 Analytics & Monitoring

The platform includes comprehensive analytics:

- Real-time call monitoring
- Booking conversion rates
- Average call duration
- Intent classification accuracy
- Customer satisfaction metrics
- Revenue tracking per location

Access analytics:
```bash
python scripts/start_salon_analytics.py
```

## 🔐 Security

- Environment variables for sensitive credentials
- Twilio webhook signature verification
- Supabase row-level security
- Rate limiting on API endpoints
- Sanitized logging (no PII in logs)

## 📚 Documentation

Detailed documentation available in:

- `SALON_ENHANCED_SYSTEM.md` - Enhanced salon phone service
- `CONVERSATIONRELAY_SETUP.md` - Conversation relay configuration
- `DATABASE_STORAGE_SETUP.md` - Database setup guide
- `DEPLOYMENT_CHECKLIST.md` - Pre-deployment checklist
- `SHOP_CUSTOMIZATION_GUIDE.md` - Customization options
- `extras/` - Setup guides for various services

## 🤝 Contributing

Contributions welcome! Please follow these guidelines:

1. Follow existing code style
2. Add tests for new features
3. Update documentation
4. Use descriptive commit messages
5. Keep changes minimal and focused

## 📄 License

See LICENSE.txt for details.

## 🆘 Support

For issues and questions:

1. Check existing documentation in `extras/` and `docs/`
2. Review setup guides for specific integrations
3. Check test files for usage examples
4. Open an issue with detailed information

## 🎯 Use Cases

### Salon/Beauty Services
- Appointment scheduling
- Service inquiries
- Stylist recommendations
- Pricing information
- Hours and location

### Plumbing/HVAC
- Emergency service requests
- Job booking
- Service area coverage
- Pricing estimates
- Technician dispatch

### General Service Businesses
- Customer inquiries
- Appointment scheduling
- Service catalog management
- Multi-location support
- Payment processing

## 🔮 Roadmap

- [ ] Voice biometrics for customer identification
- [ ] Multi-language support expansion
- [ ] Advanced analytics dashboard
- [ ] Mobile app for business owners
- [ ] Integration with more payment processors
- [ ] Automated follow-up campaigns
- [ ] AI training on custom datasets
- [ ] Video call support

---

**Built with ❤️ for service businesses** | Powered by OpenAI GPT-4 & ElevenLabs

