# Enhanced Google Sheets Integration

## Overview
Added comprehensive metrics tracking to the Google Sheets integration for the Bold Wings Hair Salon phone service, including revenue per call, response speed, and call duration buckets.

## New Metrics Added

### 1. Call Duration Buckets
- **Short (<30s)**: Quick calls, likely hang-ups or simple inquiries
- **Medium (30s-2min)**: Standard appointment booking calls
- **Long (>2min)**: Complex calls with multiple questions or issues

### 2. Response Speed
- Measures time from first customer speech to first AI response
- Helps track AI performance and customer experience
- Measured in seconds with 2 decimal precision

### 3. Revenue per Call
- Calculates potential revenue based on service price and appointment scheduling
- Only counts revenue when an appointment is actually scheduled
- Helps track conversion rates and business value

## Technical Implementation

### GoogleSheetsCRM Class Updates (`ops_integrations/adapters/external_services/sheets.py`)

#### New Headers Added:
```python
"Call Duration Bucket",
"Response Speed (sec)", 
"Revenue per Call ($)"
```

#### New Utility Functions:
- `calculate_call_duration_bucket(duration_seconds)`: Classifies call duration
- `calculate_response_speed(first_speech_time, first_response_time)`: Calculates response time
- `calculate_revenue_per_call(service_price, appointment_scheduled)`: Calculates revenue
- `test_sheets_integration()`: Tests the integration with sample data

### Salon Phone Service Updates (`ops_integrations/services/salon_phone_service.py`)

#### New Tracking Variables:
```python
call_metrics_store = defaultdict(lambda: {
    'call_start_time': 0,
    'first_speech_time': 0,
    'first_response_time': 0,
    'call_end_time': 0,
    'service_price': 0.0,
    'appointment_scheduled': False,
    'response_speed': 0.0,
    'call_duration': 0.0,
    'call_duration_bucket': '',
    'revenue_per_call': 0.0
})
```

#### Enhanced Tracking Logic:
- **Call Start**: Initializes metrics tracking
- **First Speech**: Records when customer first speaks
- **First Response**: Records when AI first responds and calculates response speed
- **Service Detection**: Tracks service price from intent extraction
- **Appointment Scheduling**: Marks when appointments are scheduled
- **Call End**: Calculates final metrics and logs to Google Sheets

#### New Functions:
- `_finalize_call_metrics(call_sid)`: Calculates and logs final metrics
- Test endpoint: `POST /test/sheets-integration`

## Testing

### Test Script: `test_sheets_integration.py`
Comprehensive test script that:
1. Tests the GoogleSheetsCRM class directly
2. Tests the salon service endpoint
3. Verifies all new metrics calculations
4. Confirms Google Sheets integration

### Test Results:
```
✅ GoogleSheetsCRM is enabled and configured
📊 Test calculations:
   • Duration bucket for 45s: Medium (30s-2min)
   • Response speed (10s to 12.5s): 2.5s
   • Revenue for $85 service with appointment: $85.0
🧪 Test result: {'ok': True, 'mode': 'sheets'}
```

## Deployment

### For Heroku:
```bash
./deploy_enhanced_sheets.sh
```

### Manual Deployment:
```bash
git add .
git commit -m "Add enhanced Google Sheets tracking: revenue/call, response speed, call duration buckets"
git push heroku main
```

## Google Sheets Structure

The Google Sheets will now have these columns:

| Column | Description | Example |
|--------|-------------|---------|
| Timestamp | Call timestamp | 2024-01-15T14:30:00Z |
| Call SID | Unique call identifier | CA1234567890abcdef |
| Customer Name | Customer name | John Doe |
| Phone Number | Customer phone | +1234567890 |
| Call Status | Call status | completed |
| Call Duration (sec) | Total call duration | 45.2 |
| **Call Duration Bucket** | **Duration classification** | **Medium (30s-2min)** |
| **Response Speed (sec)** | **Time to first response** | **2.5** |
| **Revenue per Call ($)** | **Potential revenue** | **85.00** |
| After Hours | After hours call | false |
| Service Requested | Service type | Braids - Cornrow |
| Appointment Date | Scheduled date | 2024-01-20T15:00:00Z |
| Recording URL | Call recording | |
| Notes | Additional notes | Call completed - Duration: 45.2s, Response: 2.5s, Revenue: $85.00 |
| Source | Data source | salon_phone_system |
| Direction | Call direction | inbound |
| Error Code | Error code if any | |

## Benefits

1. **Performance Monitoring**: Track AI response times and call efficiency
2. **Business Intelligence**: Monitor revenue per call and conversion rates
3. **Call Classification**: Understand call patterns and durations
4. **Quality Assurance**: Identify calls that need attention (too long, too short, slow response)
5. **Revenue Tracking**: Monitor business value of phone system

## Usage

### Testing the Integration:
```bash
curl -X POST https://your-app.herokuapp.com/test/sheets-integration
```

### Viewing Metrics:
Check your Google Sheets for the new columns and real-time data as calls come in.

## Environment Variables Required

Make sure these are set in your Heroku app:
- `GOOGLE_SHEETS_SPREADSHEET_ID`
- `GOOGLE_SHEETS_CREDENTIALS_JSON` (or `GOOGLE_SHEETS_CREDENTIALS_PATH`)
- `SHEETS_BOOKINGS_TAB_NAME` (optional, defaults to "Bookings")

## Future Enhancements

Potential future improvements:
1. Customer name extraction and tracking
2. Service-specific revenue analysis
3. Time-of-day performance metrics
4. Call quality scoring
5. Automated reporting and alerts
