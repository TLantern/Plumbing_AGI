# SoHo Salon Denton - Shop Customization Guide

Your salon phone system now supports multiple shops with automatic detection and customization per location. SoHo Salon Denton is fully configured as Location 1 with comprehensive service data.

## 🚀 Quick Start - SoHo Salon Denton

**Location 1 is ready to go!** SoHo Salon Denton has been configured with:

- **📞 Phone Number**: +18084826296  
- **🌐 Website**: [https://sohosalondenton.glossgenius.com/services](https://sohosalondenton.glossgenius.com/services)
- **🔧 Services**: 37 comprehensive services across 11 categories
- **💰 Price Range**: $0 (free consultations) to $310+ (premium treatments)
- **🎵 Voice**: kdmDKE6EkgrWrrykO9Qt (ElevenLabs)

### To Start Using:
1. Set environment: `source soho_salon_env.sh`
2. Start service: `cd ops_integrations && python3 -m services.salon_phone_service`
3. Test: Call +18084826296 or check `curl http://localhost:5001/shop/1/config`

## 🏪 How It Works

### 1. **Automatic Shop Detection**
- Each shop gets a unique phone number
- System automatically detects which shop based on incoming call number
- Each shop gets its own knowledge base, services, and configuration

### 2. **Shop-Specific Features**
- **Website Scraping**: Each shop's website is scraped for services, pricing, and staff info
- **Custom Voice**: Each shop can have its own ElevenLabs voice
- **Location Context**: AI responses are customized per shop's specific information
- **Booking System**: Shop-specific appointment booking and confirmation

## 🚀 Setting Up a New Shop

### Step 1: Add Phone Number Mapping
Update your environment variable `PHONE_TO_LOCATION_MAP`:

```bash
# SoHo Salon Denton + Additional Shops
PHONE_TO_LOCATION_MAP='{"+18084826296": 1, "+1234567890": 2, "+1987654321": 3}'

# Current Configuration (SoHo Salon Denton only)
PHONE_TO_LOCATION_MAP='{"'+"+18084826296"'": 1}'
```

### Step 2: Setup Shop Data

**SoHo Salon Denton is already configured!** For additional shops, use the API endpoint:

```bash
# SoHo Salon Denton (Location 1) - ALREADY CONFIGURED ✅
# Phone: +18084826296
# Services: 37 comprehensive services including cuts, color, braiding, natural hair care
# Website: https://sohosalondenton.glossgenius.com/services

# Setup additional shop with location ID 2
curl -X POST "https://your-app.herokuapp.com/shop/setup" \
  -H "Content-Type: application/json" \
  -d '{
    "location_id": 2,
    "phone_number": "+1234567890",
    "website_url": "https://anothersalon.com",
    "business_name": "Another Beauty Salon",
    "voice_id": "kdmDKE6EkgrWrrykO9Qt"
  }'
```

### Step 3: Verify Setup
Check that your shop is configured correctly:

```bash
# List all shops
curl "https://your-app.herokuapp.com/shops"

# Get SoHo Salon Denton config (Location 1)
curl "https://your-app.herokuapp.com/shop/1/config"

# Get other shop config  
curl "https://your-app.herokuapp.com/shop/2/config"
```

## 📞 Phone Number Configuration

### Twilio Setup
1. **Purchase phone numbers** for each shop location
2. **Configure webhooks** to point to your service:
   - Voice URL: `https://your-app.herokuapp.com/voice`
   - Status Callback: `https://your-app.herokuapp.com/voice/status`

### Environment Variables
```bash
# Phone number to location mapping (JSON format)
# SoHo Salon Denton Configuration
PHONE_TO_LOCATION_MAP='{"'+"+18084826296"'": 1}'

# With additional shops:
# PHONE_TO_LOCATION_MAP='{"+18084826296": 1, "+1234567890": 2}'

# Default location (SoHo Salon Denton)
DEFAULT_LOCATION_ID=1

# Voice settings (SoHo Salon uses this voice)
ELEVENLABS_VOICE_ID=kdmDKE6EkgrWrrykO9Qt
```

## 🎯 Shop-Specific Customization

### Voice Settings
Each shop can have different voice characteristics:
- **Voice ID**: Different ElevenLabs voices per shop
- **Sensitivity**: Customizable barge-in and speech timeout settings
- **Greeting**: Shop-specific welcome messages

### Knowledge Base
Each shop gets its own knowledge from:
- **Website scraping**: Services, pricing, staff info
- **FAQ extraction**: Common questions and answers  
- **Service catalog**: Available treatments and appointments

**SoHo Salon Denton Knowledge Base includes:**
- **37 Comprehensive Services** across 11 categories
- **Detailed Pricing**: From free consultations to $310+ premium treatments
- **Service Categories**: Hair Cuts, Color Services, Natural Hair, Braiding, Chemical Services, Treatments, Consultations, Kids Services
- **Special Features**: Buy Now Pay Later, Deposit system, Natural hair specialization
- **8 FAQ Items** covering consultations, deposits, financing, natural hair care, kids services, and signature offerings

### Booking System
- **Shop-specific services**: Each location's unique offerings
- **Availability**: Location-specific scheduling
- **Pricing**: Accurate pricing per shop

## 🔧 Management Endpoints

### List All Shops
```bash
GET /shops
```
Returns all configured shops with their status and data.

### Get Shop Configuration
```bash
GET /shop/{location_id}/config
```
Returns complete configuration for a specific shop.

### Setup New Shop
```bash
POST /shop/setup
{
  "location_id": 2,
  "phone_number": "+1234567890", 
  "website_url": "https://beautysalon2.com",
  "business_name": "Beauty Salon Downtown",
  "voice_id": "kdmDKE6EkgrWrrykO9Qt"
}
```

### Update Shop Data
```bash
POST /setup-location/{location_id}?website_url=https://beautysalon2.com
```
Re-scrape and update shop data from website.

## 📊 Monitoring

### Call Logs
Each call is tagged with:
- **Location ID**: Which shop received the call
- **Phone Number**: Which number was called
- **Caller Number**: Who called
- **Conversation Context**: Shop-specific conversation history

### Analytics
Track performance per shop:
- **Call Volume**: Calls per location
- **Booking Conversion**: Appointments booked per shop
- **Customer Satisfaction**: Shop-specific feedback

## 🎨 Customization Examples

### Example 1: SoHo Salon Denton + Chain Expansion
```json
{
  "PHONE_TO_LOCATION_MAP": {
    "+18084826296": 1,  // SoHo Salon Denton (CONFIGURED ✅)
    "+1234567890": 2,   // SoHo Salon Dallas (Future)
    "+1987654321": 3    // SoHo Salon Fort Worth (Future)
  }
}
```

**SoHo Salon Denton Services Summary:**
- **Hair Cuts**: Kids ($25), Men's ($45+), Women's ($55+), Signature ($70+)
- **Color Services**: Retouch ($90+), All Over ($110+), Blonding ($120-150+), Balayage ($160-215+)
- **Natural Hair**: Silk Press ($100+), Two Strand Twist ($75+), Hair Relaxer ($140+)
- **Braiding**: Corn Row ($85+), Stitch Braids ($120+), Knotless ($150+), Tribal ($200+)
- **Premium**: Keratin Treatment ($310+), Full Balayage ($215+)
- **Quick Services**: Bang Trim ($15), Consultations (Free)

### Example 2: Spa & Wellness Centers
```json
{
  "PHONE_TO_LOCATION_MAP": {
    "+1555123456": 1,   // Main spa
    "+1555987654": 2,   // Wellness center
    "+1555555555": 3    // Medical spa
  }
}
```

## 🔄 Updating Shop Information

### Refresh Website Data
```bash
# Update shop data from website
curl -X POST "https://your-app.herokuapp.com/setup-location/2?website_url=https://beautysalon2.com"
```

### Change Voice Settings
Update the `ELEVENLABS_VOICE_ID` environment variable or use different voices per shop in the setup.

### Modify Phone Mapping
Update the `PHONE_TO_LOCATION_MAP` environment variable and restart the service.

## 🚨 Troubleshooting

### Shop Not Detected
- Check `PHONE_TO_LOCATION_MAP` includes the phone number
- Verify phone number format (include country code: +1)
- Check logs for location detection messages

### No Shop Data
- Run `/shop/setup` endpoint to scrape website data
- Check website URL is accessible
- Verify location ID is correct

### Voice Issues
- Confirm ElevenLabs API key is set
- Check voice ID is valid
- Test voice with different ElevenLabs voices

## 📈 Scaling

The system is designed to handle:
- **Unlimited shops**: Add as many locations as needed
- **High call volume**: Each shop operates independently
- **Geographic distribution**: Shops can be anywhere
- **Different business types**: Hair salons, spas, barbershops, etc.

Each shop gets its own:
- Phone number
- Website data
- Voice settings
- Knowledge base
- Booking system
- Analytics tracking
