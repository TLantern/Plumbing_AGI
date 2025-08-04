# Baserow CRM Setup Guide for Plumbing AGI

## 🚀 Quick Setup

### 1. Create Baserow Account
- Go to [baserow.io](https://baserow.io)
- Sign up for a free account
- Create a new workspace

### 2. Create Database
- Create a new database called "Plumbing AGI CRM"
- This will give you a `DATABASE_ID`

### 3. Create Tables

#### Customers Table
Create a table with these fields:
- **Name** (Text, Required)
- **Email** (Email, Optional, Unique)
- **Phone** (Phone Number, Optional, Unique)
- **Address** (Long Text, Optional)
- **Last_Contact** (Date, Optional)
- **Status** (Single Select, Required)
  - Options: New Contact, Active Customer, Inactive Customer, Do Not Contact, Converted to Job
- **Created_At** (Date, Required)
- **Contact_Method** (Single Select, Optional)
  - Options: Phone, SMS, Email, Website Form, Referral, Walk-in, Other
- **Source** (Text, Optional)

#### Inquiries Table
Create a table with these fields:
- **Customer** (Link to Customers table, Required)
- **Inquiry_Date** (Date, Required)
- **Service_Type** (Single Select, Required)
  - Options: Initial Contact, Emergency Plumbing, Drain Cleaning, Water Heater, Pipe Repair, Fixture Installation, Leak Detection, Sewer Line, Gas Line, Bathroom Remodel, Kitchen Plumbing, Commercial Plumbing, Maintenance, Inspection, Other
- **Description** (Long Text, Optional)
- **Urgency** (Single Select, Required)
  - Options: Low, Normal, High, Emergency
- **Status** (Single Select, Required)
  - Options: New Contact, Service Request, Scheduled, In Progress, Completed, Cancelled, Follow Up Needed, Converted to Job
- **Contact_Method** (Single Select, Optional)
  - Options: Phone, SMS, Email, Website Form, Referral, Walk-in, Other
- **Estimated_Value** (Number, Optional)
- **Follow_Up_Date** (Date, Optional)
- **Notes** (Long Text, Optional)

### 4. Get Your Credentials

#### API Token
1. Go to your Baserow workspace settings
2. Navigate to "API tokens"
3. Create a new token
4. Copy the token value

#### Database and Table IDs
1. **Database ID**: Found in the URL when viewing your database
   - URL format: `https://baserow.io/database/[DATABASE_ID]`
   - Copy the `[DATABASE_ID]` part

2. **Table IDs**: Found in the URL when viewing each table
   - URL format: `https://baserow.io/database/[DATABASE_ID]/table/[TABLE_ID]`
   - Copy the `[TABLE_ID]` part for both Customers and Inquiries tables

### 5. Update Your .env File

Copy the template and fill in your values:

```bash
# Copy the template
cp env_template.txt .env

# Edit with your real values
nano .env
```

Update these values in your `.env` file:

```ini
# Baserow CRM Configuration
BASEROW_API_URL=https://api.baserow.io
BASEROW_API_TOKEN=your_actual_api_token_here
BASEROW_DATABASE_ID=your_actual_database_id_here
BASEROW_CUSTOMERS_TABLE_ID=your_actual_customers_table_id_here
BASEROW_INQUIRIES_TABLE_ID=your_actual_inquiries_table_id_here
```

### 6. Test the Integration

Run the contact capture test:

```bash
python3 ops_integrations/contact_capture.py
```

Or test with the example usage:

```bash
python3 example_usage.py
```

## ✅ What's Already Implemented

The Baserow CRM integration is **fully implemented** and includes:

### 🔧 **CRMAdapter Class** (`ops_integrations/adapters/crm.py`)
- **save_customer_inquiry()**: Saves customer inquiries to Baserow
- **Duplicate Prevention**: Checks for existing customers by email/phone
- **Automatic Customer Creation**: Creates new customers when needed
- **Robust Error Handling**: Falls back to local storage if Baserow is down

### 📞 **Contact Capture System** (`ops_integrations/contact_capture.py`)
- **phone_rang()**: Capture phone contacts
- **sms_received()**: Capture SMS contacts  
- **email_received()**: Capture email contacts
- **website_form_submitted()**: Capture website form submissions
- **got_referral()**: Capture referral contacts

### 🛡️ **Fallback System**
- If Baserow is unavailable, contacts are saved locally to `customer_inquiries_backup.json`
- No data is ever lost
- Automatic retry when Baserow comes back online

## 🎯 **Usage Examples**

### When Phone Rings:
```python
from ops_integrations.contact_capture import phone_rang
result = phone_rang("555-123-4567", "John Smith", "Sounds urgent")
```

### When SMS Received:
```python
from ops_integrations.contact_capture import sms_received
result = sms_received("555-987-6543", "Help! Emergency!", "Jane Doe")
```

### When Email Received:
```python
from ops_integrations.contact_capture import email_received
result = email_received("customer@email.com", "Plumbing Issue", "Bob Wilson", "Need help")
```

## 🔍 **Troubleshooting**

### Common Issues:

1. **404 Errors**: Check that your table IDs are correct
2. **401 Unauthorized**: Verify your API token is valid
3. **Missing Fields**: Ensure all required fields are created in Baserow
4. **Link Row Issues**: Make sure the Customer field in Inquiries table links to Customers table

### Test Your Setup:
```bash
# Test the CRM adapter directly
python3 -c "
from ops_integrations.adapters.crm import CRMAdapter
crm = CRMAdapter()
print(f'CRM Enabled: {crm.enabled}')
print(f'API URL: {crm.base_url}')
print(f'Database ID: {crm.database_id}')
"
```

## 📊 **Data Flow**

1. **Contact Received** → Phone/SMS/Email/Website/Referral
2. **Immediate Capture** → Contact data saved to Baserow CRM
3. **Customer Record** → Created or updated in Customers table
4. **Inquiry Record** → Created in Inquiries table, linked to customer
5. **Fallback** → If Baserow down, saved locally with automatic sync later

Your system is ready to capture every customer contact immediately! 🎉 