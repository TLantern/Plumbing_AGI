# Enhanced Baserow CRM Setup Guide for Plumbing AGI

This guide will help you set up the enhanced Baserow CRM integration that automatically manages customer interactions, status updates, and service workflows.

## Overview

The enhanced CRM system provides:
- **Automatic Customer Creation**: New customers are added when they call, text, or email
- **Interaction Tracking**: All customer communications are logged with timestamps
- **Status Management**: Customer status updates automatically based on service progress
- **Service Workflows**: Track customer journey from inquiry to completion
- **Fallback Storage**: Local backup when Baserow is unavailable

## Required Environment Variables

Add these to your `.env` file:

```bash
# Baserow CRM Configuration
BASEROW_API_URL=https://api.baserow.io
BASEROW_API_TOKEN=your_baserow_api_token_here
BASEROW_DATABASE_ID=your_database_id
BASEROW_CUSTOMERS_TABLE_ID=your_customers_table_id
BASEROW_INQUIRIES_TABLE_ID=your_inquiries_table_id
BASEROW_INTERACTIONS_TABLE_ID=your_interactions_table_id
```

## Step 1: Create Baserow Database

1. Log into your Baserow account
2. Create a new database called "Plumbing AGI CRM"
3. Note the database ID from the URL

## Step 2: Create Required Tables

### Customers Table

Create a table called "Customers" with these fields:

| Field Name | Field Type | Settings |
|------------|------------|----------|
| Name | Single line text | Required |
| Email | Email | Optional |
| Phone | Phone number | Optional |
| Address | Long text | Optional |
| Status | Single select | Options: New, Contacted, Quoted, Scheduled, In Progress, Completed, Follow Up Required, Inactive, Priority Customer |
| First_Contact | Date | Auto-filled |
| Last_Contact | Date | Auto-updated |
| Total_Interactions | Number | Default: 0 |
| Priority_Level | Single select | Options: Low, Normal, High |
| Source | Single select | Options: Direct Contact, Referral, Website, Social Media, Advertisement |
| Last_Service_Type | Single line text | Optional |
| Notes | Long text | Optional |

### Inquiries Table

Create a table called "Inquiries" with these fields:

| Field Name | Field Type | Settings |
|------------|------------|----------|
| Customer | Link to table | Link to Customers table |
| Service_Type | Single select | Options: Emergency Plumbing, Drain Cleaning, Installation, Repair, Maintenance, Quote Request, General Inquiry |
| Description | Long text | Optional |
| Urgency | Single select | Options: Low, Normal, High, Emergency |
| Status | Single select | Options: New, In Progress, Quoted, Scheduled, Completed, Cancelled |
| Inquiry_Date | Date | Auto-filled |
| Follow_Up_Required | Checkbox | Default: false |
| Estimated_Cost | Number | Optional |
| Actual_Cost | Number | Optional |
| Completion_Date | Date | Optional |

### Interactions Table

Create a table called "Interactions" with these fields:

| Field Name | Field Type | Settings |
|------------|------------|----------|
| Customer | Link to table | Link to Customers table |
| Type | Single select | Options: Phone (Inbound), Phone (Outbound), SMS (Inbound), SMS (Outbound), Email (Inbound), Email (Outbound), Website Form, Referral, Appointment, Service Completion |
| Content | Long text | Optional |
| Service_Type | Single line text | Optional |
| Urgency | Single select | Options: Low, Normal, High, Emergency |
| Timestamp | Date | Auto-filled |
| Direction | Single select | Options: Inbound, Outbound |
| Follow_Up_Required | Checkbox | Default: false |

## Step 3: Get Table IDs

1. Go to each table and note the table ID from the URL
2. Add these IDs to your `.env` file

## Step 4: Generate API Token

1. Go to Account Settings in Baserow
2. Generate a new API token
3. Add it to your `.env` file

## Step 5: Test the Integration

Run the test to verify everything is working:

```python
from ops_integrations.etl.ops_etl import OpsETLSync

# Initialize and test
sync = OpsETLSync()
sync.run()  # This will test all functionality including CRM
```

## Usage Examples

### Capturing Customer Interactions

```python
from ops_integrations.contact_capture import (
    phone_rang, sms_received, email_received, 
    website_form_submitted, got_referral
)

# When a customer calls
result = phone_rang(
    phone_number="555-123-4567",
    caller_name="John Smith",
    notes="Kitchen sink is leaking",
    service_type="Emergency Plumbing",
    urgency="High"
)

# When customer texts
result = sms_received(
    phone_number="555-987-6543",
    message="Need quote for bathroom renovation",
    service_type="Quote Request",
    urgency="Normal"
)

# When customer emails
result = email_received(
    email_address="customer@email.com",
    subject="Plumbing Emergency",
    sender_name="Jane Doe",
    content="My pipes burst in the basement!",
    service_type="Emergency Plumbing",
    urgency="Emergency"
)
```

### Managing Service Status

```python
from ops_integrations.contact_capture import (
    schedule_service, start_service, 
    complete_service, needs_follow_up
)

# After scheduling an appointment
customer_id = 123
schedule_service(customer_id, "Scheduled for tomorrow 9 AM")

# When technician arrives
start_service(customer_id, "Technician on site")

# After completing the job
complete_service(customer_id, "Sink repaired, new faucet installed")

# If follow-up is needed
needs_follow_up(customer_id, "Customer wants quote for additional work")
```

### Using Direct CRM Functions

```python
from ops_integrations.adapters.crm import (
    customer_called, customer_texted, customer_emailed
)

# Quick functions for immediate use
result = customer_called("555-123-4567", "John Smith", "Emergency call")
result = customer_texted("555-987-6543", "Need help ASAP!")
result = customer_emailed("customer@email.com", "Urgent: Pipe burst", "Help needed")
```

## Customer Status Workflow

The system automatically manages customer status based on interactions:

1. **New** → Customer first contacts you
2. **Contacted** → After initial interaction
3. **Quoted** → When quote/estimate is provided
4. **Scheduled** → When appointment is booked
5. **In Progress** → When service is being performed
6. **Completed** → When service is finished
7. **Follow Up Required** → When additional contact is needed
8. **Priority Customer** → For VIP or emergency situations

## Features

### Automatic Customer Detection
- Finds existing customers by phone or email
- Creates new customers automatically if not found
- Updates last contact time on every interaction

### Interaction Logging
- Records all communications with timestamps
- Tracks interaction types and content
- Maintains interaction count per customer

### Status Intelligence
- Updates status based on service type and urgency
- Emergency contacts get priority status
- Workflow progression based on business logic

### Fallback Protection
- Saves data locally if Baserow is unavailable
- Continues operation even during outages
- Can sync backlog when connection restored

## Troubleshooting

### Common Issues

1. **"CRM not configured" warning**
   - Check environment variables are set correctly
   - Verify API token is valid
   - Ensure table IDs are correct

2. **"Failed to create customer" error**
   - Check Baserow permissions
   - Verify table field names match exactly
   - Ensure required fields are configured

3. **Interaction not recorded**
   - Check BASEROW_INTERACTIONS_TABLE_ID is set
   - Verify interactions table exists
   - Check API token has write permissions

### Testing Connection

```python
from ops_integrations.adapters.crm import CRMAdapter

crm = CRMAdapter()
if crm.enabled:
    print("✅ CRM is properly configured")
else:
    print("❌ CRM configuration missing")
```

## Best Practices

1. **Regular Backups**: Export Baserow data regularly
2. **Monitor Logs**: Check application logs for errors
3. **Test Connectivity**: Run tests after any configuration changes
4. **Status Updates**: Keep customer statuses current
5. **Data Quality**: Ensure phone/email formats are consistent

## Integration with Existing Systems

The enhanced CRM integrates with:
- **Akaunting**: Syncs existing customers
- **Google Calendar**: Links appointments to customers
- **Local Backups**: Maintains offline copies

## Support

For issues with this integration:
1. Check logs for specific error messages
2. Verify Baserow table structure matches requirements
3. Test API connectivity with provided test functions
4. Review environment variable configuration 