# SMS Job Booking Setup Guide

This guide will help you set up SMS job booking functionality using Twilio, integrated with your existing CRM and calendar systems.

## Overview

The SMS job booking system provides:
- **📅 Automatic Job Booking**: Book jobs with one function call
- **📱 SMS Notifications**: Send booking confirmations, reminders, and updates
- **🔄 CRM Integration**: Automatically capture customers and update status
- **📅 Calendar Integration**: Create calendar events for appointments
- **⏰ Status Updates**: Send SMS when job status changes

## Step 1: Install Twilio

```bash
pip install twilio
```

## Step 2: Set Up Twilio Account

1. **Create Twilio Account**: Go to [twilio.com](https://twilio.com) and sign up
2. **Get Account Credentials**: 
   - Account SID (found in your Twilio Console)
   - Auth Token (found in your Twilio Console)
3. **Get Phone Number**: Purchase a Twilio phone number for sending SMS

## Step 3: Environment Variables

Add these to your `.env` file:

```bash
# Twilio SMS Configuration
TWILIO_ACCOUNT_SID=your_account_sid_here
TWILIO_AUTH_TOKEN=your_auth_token_here
TWILIO_FROM_NUMBER=+1234567890  # Your Twilio phone number
```

## Step 4: Test the Setup

```python
from ops_integrations.job_booking import book_emergency_job

# Test booking an emergency job
result = book_emergency_job(
    phone="+15551234567",
    name="John Smith",
    service="Emergency Plumbing",
    address="123 Main Street",
    notes="Kitchen sink is leaking badly"
)

print(f"Booking result: {result}")
```

## Usage Examples

### Book Emergency Job (Next Available Slot)

```python
from ops_integrations.job_booking import book_emergency_job

result = book_emergency_job(
    phone="+15551234567",
    name="Jane Doe",
    service="Emergency Plumbing",
    address="456 Oak Avenue",
    notes="Burst pipe in basement"
)
```

### Book Scheduled Job

```python
from ops_integrations.job_booking import book_scheduled_job
from datetime import datetime, timedelta

# Book for tomorrow at 2 PM
appointment_time = datetime.now() + timedelta(days=1)
appointment_time = appointment_time.replace(hour=14, minute=0, second=0, microsecond=0)

result = book_scheduled_job(
    phone="+15551234567",
    name="Bob Wilson",
    service="Drain Cleaning",
    appointment_time=appointment_time,
    address="789 Pine Street",
    notes="Kitchen drain is slow"
)
```

### Update Job Status

```python
from ops_integrations.job_booking import update_job_status

# Customer ID from CRM
customer_id = 123

# Update to "in progress" - sends ETA SMS
result = update_job_status(customer_id, "in_progress", "Technician arrived on site")

# Update to "completed" - sends completion SMS
result = update_job_status(customer_id, "completed", "Job completed successfully")
```

### Send Reminder

```python
from ops_integrations.job_booking import send_appointment_reminder

# Send reminder to customer
result = send_appointment_reminder(customer_id=123)
```

## SMS Message Types

### 1. Booking Confirmation
```
Hi John Smith! 

Your Emergency Plumbing appointment is confirmed for Monday, January 15 at 2:00 PM.

Address: 123 Main Street

We'll send a reminder 1 hour before. Call us if you need to reschedule.

Thank you for choosing our plumbing services!
```

### 2. Appointment Reminder
```
Hi John Smith!

Reminder: Your Emergency Plumbing appointment is today at 2:00 PM.

Please ensure someone is available to let us in. We'll call when we're on our way.

Thank you!
```

### 3. ETA Update
```
Hi John Smith!

We're on our way and will arrive in approximately 15 minutes.

Please ensure someone is available to let us in.

Thank you for your patience!
```

### 4. Job Completion
```
Hi John Smith!

Your Emergency Plumbing has been completed successfully.

Thank you for choosing our services! We appreciate your business.
```

## Integration Features

### Automatic CRM Updates
- ✅ Customer captured in Baserow CRM
- ✅ Status updated to "Scheduled"
- ✅ Interaction logged with booking details

### Calendar Integration
- ✅ Google Calendar event created
- ✅ 2-hour default time slot
- ✅ Customer details in event description

### SMS Workflow
- ✅ Booking confirmation sent immediately
- ✅ Reminder scheduled for 1 hour before
- ✅ Status update SMS (ETA, completion)
- ✅ Error handling and fallback

## Error Handling

The system gracefully handles:
- **Twilio not configured**: Falls back to CRM/Calendar only
- **SMS send failures**: Continues with other operations
- **CRM unavailable**: Still creates calendar events
- **Calendar unavailable**: Still captures customer and sends SMS

## Testing

Run the test to verify everything works:

```python
python ops_integrations/job_booking.py
```

## Production Usage

### Emergency Booking Flow
1. Customer calls with emergency
2. Use `book_emergency_job()` to schedule immediately
3. Customer receives confirmation SMS
4. Calendar event created for technician
5. CRM updated with customer and status

### Scheduled Booking Flow
1. Customer requests appointment
2. Use `book_scheduled_job()` with specific time
3. Customer receives confirmation SMS
4. Calendar event created
5. Reminder SMS scheduled automatically

### Job Progress Updates
1. Technician starts work → `update_job_status(customer_id, "in_progress")`
2. Customer receives ETA SMS
3. Job completed → `update_job_status(customer_id, "completed")`
4. Customer receives completion SMS

## Best Practices

1. **Phone Number Format**: Always use international format (+1 for US)
2. **Error Handling**: Check result dictionaries for success status
3. **Customer ID**: Store customer IDs from booking results for status updates
4. **Testing**: Test with your own phone number first
5. **Monitoring**: Check Twilio logs for delivery status

## Troubleshooting

### Common Issues

1. **"SMS not configured"**
   - Check environment variables are set correctly
   - Verify Twilio credentials are valid

2. **"SMS send failed"**
   - Check Twilio account has sufficient credits
   - Verify phone number format (+1XXXXXXXXXX)
   - Check Twilio console for error details

3. **"Customer not found"**
   - Ensure customer was captured in CRM first
   - Check customer ID is correct

### Testing Connection

```python
from ops_integrations.adapters.sms import SMSAdapter

sms = SMSAdapter()
if sms.enabled:
    print("✅ SMS is properly configured")
else:
    print("❌ SMS configuration missing")
```

The SMS job booking system is now ready to automate your customer communication and streamline your booking process! 🎉 