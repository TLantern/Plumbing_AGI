# Enhanced Salon Phone Service with Website Scraping & Job Confirmation

This enhanced salon phone service combines multi-location database support, intelligent job confirmation, and website scraping for comprehensive location knowledge.

## 🚀 Key Features

### 1. **Multi-Location Database Schema**
- **Locations**: Support multiple salon locations with individual settings
- **Agents**: AI agents per location with custom prompts and voice settings  
- **Services**: Dynamic service catalog with pricing and duration
- **Bookings**: Complete appointment lifecycle tracking
- **Calls**: Call history with booking attribution

### 2. **Intelligent Job Confirmation System**
- Detects booking intent from customer conversation
- Automatically suggests appointment confirmation when appropriate
- Tracks conversation context for better decision making
- Supports service-specific booking workflows

### 3. **Static Website Data & Zero-Delay Knowledge**
- One-time scraping of salon websites for services, pricing, and professional info
- Static storage in JSON files for instant access during calls
- Pre-loaded knowledge cache for zero-delay AI responses
- Auto-categorizes services and professionals

### 4. **Enhanced AI Responses**
- Uses location-specific knowledge for accurate responses
- Mentions specific services, pricing, and staff specialties
- Answers FAQs from scraped website content
- Intelligently suggests bookings based on conversation flow

## 📋 Database Schema

### Core Tables

```sql
-- Locations (multi-salon support)
locations: id, name, phone, timezone, owner_name, owner_email

-- AI Agents (per location)  
agents: id, location_id, twilio_number, voice_id, system_prompt, business_hours_json

-- Services (per location)
services: id, location_id, name, duration_min, price_cents, active_bool, notes

-- Bookings (appointments)
bookings: id, location_id, service_id, start_at, end_at, status, customer_name, 
         customer_phone, source, call_id, price_cents_snapshot

-- Calls (with booking attribution)
calls: id, location_id, call_sid, started_at, ended_at, duration_sec, status,
       transcript_url, recording_url, booking_id, customer_phone
```

## 🛠 Installation & Setup

### 1. **Install Dependencies**
```bash
pip install -r requirements-heroku.txt
```

### 2. **Environment Variables**
```bash
# Database (Heroku provides DATABASE_URL automatically)
DATABASE_URL=postgresql://user:pass@host:port/db

# Twilio
TWILIO_ACCOUNT_SID=your_account_sid
TWILIO_AUTH_TOKEN=your_auth_token
CI_SERVICE_SID=your_ci_service_sid

# OpenAI
OPENAI_API_KEY=your_openai_key

# ElevenLabs
ELEVENLABS_VOICE_ID=kdmDKE6EkgrWrrykO9Qt

# URLs (for Heroku deployment)
PUBLIC_BASE_URL=https://your-app.herokuapp.com
WSS_PUBLIC_URL=wss://your-app.herokuapp.com

# Location
DEFAULT_LOCATION_ID=1
```

### 3. **Database Initialization**
```bash
# Initialize database with default salon data
python -m ops_integrations.services.init_db
```

## 🌐 Heroku Deployment

### 1. **Create Heroku App**
```bash
heroku create your-salon-phone-app
heroku addons:create heroku-postgresql:mini
```

### 2. **Set Environment Variables**
```bash
# Core service variables
heroku config:set TWILIO_ACCOUNT_SID=your_sid
heroku config:set TWILIO_AUTH_TOKEN=your_token
heroku config:set OPENAI_API_KEY=your_key
heroku config:set CI_SERVICE_SID=your_ci_sid
heroku config:set ELEVENLABS_VOICE_ID=kdmDKE6EkgrWrrykO9Qt
heroku config:set PUBLIC_BASE_URL=https://your-salon-phone-app.herokuapp.com
heroku config:set WSS_PUBLIC_URL=wss://your-salon-phone-app.herokuapp.com

# Database storage (DATABASE_URL is automatically set by Heroku PostgreSQL addon)
```

### 3. **Deploy**
```bash
git add .
git commit -m "Deploy enhanced salon phone service"
git push heroku main
```

The `release` process will automatically initialize the database.

## 🔧 API Endpoints

### Core Service
- `POST /voice` - Twilio voice webhook
- `WS /cr` - ConversationRelay WebSocket
- `POST /intelligence/transcripts` - CI transcripts webhook

### Static Data Management
- `POST /setup-location/{location_id}?website_url=...` - One-time location setup
- `GET /location/{location_id}/status` - Get location data status
- `GET /location/{location_id}/knowledge` - Get location knowledge summary
- `GET /locations` - List all configured locations

### Health & Status
- `GET /health` - Service health with database and knowledge status

## 🌐 Static Data Setup

### 1. **One-Time Location Setup**
```bash
# Setup location data (scrape and store statically)
curl -X POST "https://your-app.herokuapp.com/setup-location/1?website_url=https://example-salon.com"
```

### 2. **Check Data Status**
```bash
# Check if location has data and its age
curl "https://your-app.herokuapp.com/location/1/status"
```

### 3. **CLI Management Tool**
```bash
# Setup location data locally
python ops_integrations/services/manage_static_data.py setup 1 https://example-salon.com

# List all locations
python ops_integrations/services/manage_static_data.py list

# Check location status
python ops_integrations/services/manage_static_data.py status 1

# Update existing location
python ops_integrations/services/manage_static_data.py update 1
```

### 4. **Response Example**
```json
{
  "status": "success",
  "business_name": "Example Salon",
  "stats": {
    "services_count": 12,
    "professionals_count": 4,
    "faq_count": 8
  },
  "data_file": "scraped_data_location_1.json",
  "ai_context_file": "ai_context_location_1.txt"
}
```

## 🤖 AI Enhancement Features

### **Service-Aware Responses**
The AI now has access to:
- Specific service names and prices
- Professional specialties and bios
- FAQ content from the website
- Business hours and contact info

### **Booking Intelligence**
- Detects when customers show booking intent
- Suggests specific services based on conversation
- Confirms appointments with accurate pricing
- Tracks conversation history for context

### **Example Enhanced Response**
Instead of: *"We offer various hair services"*

Now: *"We offer haircuts for $65 (1 hour), highlights for $120 (2 hours), and blowouts for $45 (45 min). Sarah specializes in color and highlights. Would you like me to check availability for any of these services?"*

## 📁 File Structure

```
ops_integrations/services/
├── salon_phone_service.py      # Main FastAPI service
├── models.py                   # Database models
├── database.py                 # Database connection management
├── booking_service.py          # Booking logic and job confirmation
├── website_scraper.py          # Website scraping service
├── knowledge_service.py        # Location knowledge management
├── init_db.py                  # Database initialization
└── example_scraper_usage.py    # Usage examples
```

## 🔍 Testing Website Scraping

```python
# Test scraping locally
from ops_integrations.services.website_scraper import update_location_from_website

result = await update_location_from_website(1, "https://example-salon.com")
print(f"Found {result['services_count']} services")
```

## 📊 Monitoring & Analytics

- Database health monitoring via `/health` endpoint
- Knowledge cache status tracking
- Call and booking analytics through database queries
- Scraped data versioning with timestamps

## 🔄 Regular Maintenance

### **Update Location Knowledge**
Run website scraping monthly or when salon updates their website:
```bash
curl -X POST "https://your-app.herokuapp.com/scrape-location/1?website_url=https://salon-website.com"
```

### **Database Backups**
Heroku PostgreSQL includes automatic backups. Manual backup:
```bash
heroku pg:backups:capture
```

## 🎯 Benefits

1. **Accurate Information**: AI responses use real pricing and service details
2. **Better Conversions**: Intelligent booking suggestions increase appointment rates  
3. **Reduced Training**: Staff info and FAQs reduce need for human intervention
4. **Scalable**: Support multiple locations with unique configurations
5. **Data-Driven**: Complete call and booking analytics for business insights

## 🚨 Next Steps

1. Set up regular website scraping (weekly/monthly)
2. Configure location-specific business hours and staff
3. Monitor booking conversion rates
4. Add more sophisticated service matching
5. Implement appointment reminder system

This enhanced system transforms your salon phone service into an intelligent, data-driven assistant that provides accurate information and drives more bookings!
