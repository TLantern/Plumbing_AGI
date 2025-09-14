# Unified Backend Integration

This document describes the unified Supabase backend integration between the main webpage and salon phone service.

## Overview

The salon phone service now uses the same Supabase database as the main webpage, ensuring seamless data synchronization and admin oversight capabilities.

## Architecture

```
┌─────────────────────┐    ┌─────────────────────┐
│   Main Webpage      │    │  Salon Phone Service │
│   (React/TypeScript)│    │   (Python/FastAPI)   │
└─────────┬───────────┘    └─────────┬───────────┘
          │                          │
          └──────────┬─────────────────┘
                     │
          ┌──────────▼───────────┐
          │   Supabase Database  │
          │   (Unified Schema)   │
          └──────────────────────┘
```

## Database Schema

### Core Tables

- **`profiles`** - Shop profiles and basic information
- **`salon_info`** - Detailed salon information and settings  
- **`calls`** - Call logs and analytics
- **`appointments`** - Appointment bookings
- **`services`** - Service catalog
- **`scraped_services`** - Detailed service information from website scraping
- **`scraped_professionals`** - Staff information from website scraping
- **`salon_static_data`** - Cached knowledge and static data

### Analytics Functions

- **`get_salon_kpis`** - Get key performance indicators for a salon
- **`get_calls_timeseries`** - Get call volume over time
- **`get_platform_metrics`** - Get platform-wide metrics
- **`get_all_salons_overview`** - Get overview of all salons

## Integration Points

### 1. Shop Management

**Main Webpage:**
- Shop registration and profile management
- Service catalog management
- Staff information management

**Phone Service:**
- Automatic shop creation during setup
- Service data synchronization
- Real-time shop status updates

### 2. Call Logging

**Phone Service:**
- Logs all incoming calls to `calls` table
- Tracks call outcomes (booked, inquiry, missed)
- Records intent and sentiment analysis

**Main Webpage:**
- Displays call analytics in admin dashboard
- Shows real-time call metrics
- Provides call history and trends

### 3. Appointment Management

**Phone Service:**
- Creates appointments when bookings are confirmed
- Links appointments to originating calls
- Estimates revenue based on services

**Main Webpage:**
- Displays appointment calendar
- Manages appointment status
- Tracks revenue and conversion metrics

## API Endpoints

### Shop Management

```bash
# Setup new shop
POST /shop/setup
{
  "location_id": 1,
  "phone_number": "+1234567890",
  "website_url": "https://example.com",
  "business_name": "Example Salon"
}

# List all shops
GET /shops

# Get shop configuration
GET /shop/{location_id}/config
```

### Admin Analytics

```bash
# Platform-wide metrics
GET /admin/platform-metrics

# Shop-specific metrics
GET /admin/shop/{shop_id}/metrics?days=30

# Shop services
GET /admin/shop/{shop_id}/services

# Create appointment
POST /admin/shop/{shop_id}/appointment
{
  "call_id": "CA123...",
  "service_id": "svc_123",
  "appointment_date": "2024-01-15T10:00:00Z",
  "estimated_revenue_cents": 8000
}
```

### Real-time Updates

```bash
# WebSocket for real-time dashboard updates
WS /ops
```

## Data Flow

### 1. Shop Setup Flow

1. Phone service receives shop setup request
2. Scrapes website for services and staff information
3. Creates shop profile in `profiles` table
4. Stores detailed info in `salon_info` table
5. Saves services to `services` and `scraped_services` tables
6. Updates phone number mapping
7. Broadcasts update to connected dashboards

### 2. Call Processing Flow

1. Incoming call triggers voice webhook
2. Call logged to `calls` table with "in_progress" status
3. Conversation processed via ConversationRelay
4. Intent analysis determines call outcome
5. Call outcome updated in database
6. If booking confirmed, appointment created
7. Real-time updates sent to dashboards

### 3. Analytics Flow

1. Main webpage requests metrics via API functions
2. Supabase functions aggregate data from multiple tables
3. Results returned with proper formatting
4. Dashboard displays real-time analytics

## Configuration

### Environment Variables

```bash
# Supabase Configuration
SUPABASE_URL=https://yzoalegdsogecfiqzfbp.supabase.co
SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...

# Phone Number Mapping (JSON)
PHONE_TO_LOCATION_MAP='{"+18084826296": 1, "+1234567890": 2}'

# Default Location
DEFAULT_LOCATION_ID=1
```

### Phone Number Mapping

The system maps incoming phone numbers to shop locations:

```json
{
  "+18084826296": 1,
  "+1234567890": 2,
  "+1987654321": 3
}
```

## Benefits

### 1. Unified Data Model
- Single source of truth for all shop data
- Consistent data structure across platforms
- Eliminates data synchronization issues

### 2. Real-time Analytics
- Live call monitoring
- Instant appointment tracking
- Real-time revenue metrics

### 3. Admin Oversight
- Platform-wide metrics
- Individual shop performance
- Call quality and conversion tracking

### 4. Scalability
- Easy addition of new shops
- Automatic data synchronization
- Centralized configuration management

## Monitoring and Maintenance

### Health Checks

```bash
# Service health
GET /health

# Current metrics
GET /metrics
```

### Logging

All operations are logged with structured data:
- Call start/completion
- Shop setup/updates
- Appointment creation
- Error conditions

### Error Handling

- Graceful fallbacks for database issues
- Retry logic for failed operations
- Comprehensive error logging

## Future Enhancements

1. **Multi-tenant Support** - Enhanced shop isolation
2. **Advanced Analytics** - Machine learning insights
3. **Integration APIs** - Third-party system connections
4. **Automated Reporting** - Scheduled analytics reports
5. **Performance Optimization** - Caching and indexing improvements
