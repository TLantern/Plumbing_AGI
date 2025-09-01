# Salon Analytics System Setup Guide

This guide will help you set up a comprehensive data collection and analytics system for your mother's hairstyling business using your existing MVP infrastructure.

## 🏗️ System Overview

Your new salon analytics system includes:

- **Real-time call tracking** (total, missed, after-hours calls)
- **Appointment analytics** (no-shows, cancellations, revenue tracking)
- **Weekly growth metrics** and trend analysis
- **Customer relationship management** with service history
- **Live dashboard** with WebSocket real-time updates
- **Automated weekly reporting** with business insights

## 📊 Key Metrics Tracked

### Call Metrics
- Total calls received
- Answered vs missed calls
- After-hours call volume
- Average call duration
- Call-to-appointment conversion rate

### Appointment Metrics
- Total appointments scheduled
- Completed appointments
- No-show and cancellation rates
- Revenue per appointment
- Total weekly revenue

### Growth Analytics
- Week-over-week growth rates
- Customer retention metrics
- New vs returning customers
- Business insights and recommendations

## 🚀 Quick Start

### 1. Install Dependencies

```bash
# Install Python dependencies
pip install fastapi uvicorn websockets httpx sqlite3

# Install Node.js dependencies (if not already installed)
cd frontend
npm install
```

### 2. Start the Salon Analytics Service

```bash
# From the project root
python scripts/start_salon_analytics.py

# Or with custom options
python scripts/start_salon_analytics.py --host 0.0.0.0 --port 5002 --reload
```

### 3. Start the Frontend Dashboard

```bash
cd frontend
npm run dev
```

### 4. Access the Dashboard

- **Salon Dashboard**: http://localhost:3000/salon-dashboard
- **API Endpoint**: http://localhost:5002/salon/dashboard
- **WebSocket**: ws://localhost:5002/salon

## 🔧 Integration with Existing System

### Phone System Integration

Add these integration points to your existing phone service:

```python
# In your existing phone service file
from ops_integrations.adapters.integrations.salon_phone_integration import (
    on_call_started, on_call_ended, on_intent_extracted, on_appointment_scheduled
)

# In voice_webhook function:
asyncio.create_task(on_call_started({
    'CallSid': call_sid,
    'From': form.get("From"),
    'CallerName': form.get("CallerName")
}))

# In call end handling:
asyncio.create_task(on_call_ended({
    'call_sid': call_sid,
    'duration_sec': duration
}))

# In intent extraction:
asyncio.create_task(on_intent_extracted({
    'call_sid': call_sid,
    'intent': extracted_intent
}))

# In appointment scheduling:
asyncio.create_task(on_appointment_scheduled({
    'call_sid': call_sid,
    'job': job_data
}))
```

### Service Type Mapping

The system automatically maps your existing service types to hairstyling services:

- `EMERGENCY_FIX` → Haircut
- `CLOG_BLOCKAGE` → Hair Treatment
- `LEAKING_FIXTURE` → Hair Color
- `INSTALL_REQUEST` → Highlights
- `WATER_HEATER_ISSUE` → Perm
- `QUOTE_REQUEST` → Consultation
- And more...

## 📱 Dashboard Features

### Overview Tab
- Key metrics cards (calls, appointments, revenue, growth)
- Live call status
- Customer statistics

### Calls Tab
- Recent call history
- Call metrics (answer rate, after-hours calls, conversion rate)
- Real-time call tracking

### Appointments Tab
- Appointment overview with status breakdown
- Revenue metrics and averages
- No-show and cancellation tracking

### Growth & Insights Tab
- 4-week trend analysis
- Automated business insights
- Actionable recommendations

## 🗄️ Data Storage

### Database Schema
The system uses SQLite with the following tables:

- **customers**: Customer information and history
- **appointments**: Appointment details and status
- **calls**: Call records and metrics
- **weekly_metrics**: Historical performance data

### Data Location
- Database: `hairstyling_analytics.db`
- Logs: `logs/salon_analytics.log`
- Backups: `customer_interactions_backup.json` (fallback)

## 📈 Growth Tracking Features

### Automatic Insights
The system automatically generates insights such as:
- Revenue growth trends
- Appointment booking patterns
- Customer retention analysis
- Peak call time identification

### Weekly Reports
Every Sunday at midnight, the system:
- Saves weekly metrics to the database
- Generates growth insights
- Broadcasts reports to connected dashboards

## 🔄 Real-time Updates

### WebSocket Integration
The dashboard receives real-time updates for:
- New incoming calls
- Appointment bookings
- Status changes
- Metric updates

### API Endpoints

#### Dashboard Data
```
GET /salon/dashboard
```

#### Weekly Metrics
```
GET /salon/metrics/weekly?weeks_back=12
```

#### Growth Insights
```
GET /salon/insights
```

#### Webhook Endpoints
```
POST /salon/call
POST /salon/appointment
```

## 🧪 Testing the System

### Test Call Event
```bash
curl -X POST http://localhost:5002/salon/test/call
```

### Test Appointment Event
```bash
curl -X POST http://localhost:5002/salon/test/appointment
```

### Health Check
```bash
curl http://localhost:5002/health
```

## 🔧 Configuration

### Environment Variables

Create a `.env` file in the project root:

```bash
# Salon Analytics Configuration
SALON_SERVICE_URL=http://localhost:5002
SALON_DB_PATH=./data/salon/hairstyling_analytics.db

# Business Hours (optional)
BUSINESS_START_HOUR=9
BUSINESS_END_HOUR=18
BUSINESS_DAYS=0,1,2,3,4,5  # Monday-Saturday

# Default Service Pricing
HAIRCUT_PRICE=45.00
COLOR_PRICE=120.00
HIGHLIGHTS_PRICE=150.00
PERM_PRICE=80.00
BLOWOUT_PRICE=35.00
TREATMENT_PRICE=65.00
```

### Service Customization

Edit `hairstyling_crm.py` to customize:
- Service types and pricing
- Business hours
- Metric calculations
- Database schema

## 📊 Weekly Growth Goals

To ensure all metrics grow over the next week, the system tracks:

1. **Call Volume Growth**: Track increase in total calls
2. **Conversion Improvement**: Monitor call-to-appointment rates
3. **Revenue Growth**: Track weekly revenue increases
4. **Customer Retention**: Monitor returning customer rates
5. **Efficiency Metrics**: Reduce no-show and cancellation rates

### Growth Strategies Implemented

- **After-hours call tracking** to identify expansion opportunities
- **Conversion rate monitoring** to improve booking processes
- **No-show rate analysis** to implement reminder systems
- **Customer segmentation** for targeted retention efforts

## 🚨 Troubleshooting

### Common Issues

1. **Service won't start**
   ```bash
   python scripts/start_salon_analytics.py --check-only
   ```

2. **Database connection issues**
   - Check file permissions in the data directory
   - Ensure SQLite is available

3. **WebSocket connection fails**
   - Verify port 5002 is available
   - Check firewall settings

4. **Dashboard shows no data**
   - Ensure salon analytics service is running
   - Check API endpoint: http://localhost:5002/salon/dashboard

### Logs
Check logs for debugging:
```bash
tail -f logs/salon_analytics.log
```

## 📚 Next Steps

1. **Integrate with existing phone system** using the provided integration functions
2. **Customize service types and pricing** for your specific business
3. **Set up automated backups** of the analytics database
4. **Configure business hours** to match salon operating schedule
5. **Train staff** on using the dashboard for daily operations

## 🎯 Expected Results

After one week of operation, you should see:
- Complete call tracking with missed call identification
- Appointment booking and completion tracking
- Revenue analytics with growth trends
- Customer insights and retention metrics
- Actionable recommendations for business growth

The system is designed to help identify opportunities for growth and optimize operations based on real data rather than assumptions.
