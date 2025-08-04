# Plumbing Ops Integrations

A production-ready Python service to integrate plumbing company systems (Akaunting, Calendars, CRMs, Inventory) and provide a unified ETL pipeline.

## Features
- Sync customers, invoices, and payments from Akaunting accounting software
- Import and export job events to Google Calendar or Outlook
- Manage customer records in a generic CRM
- Track parts inventory and automate reorders
- Modular, testable adapters and ETL pipelines

## Quickstart

### Option 1: Local Development (Recommended)
1. Clone the repo
2. `pip install -r requirements.txt`
3. Run the Akaunting setup script: `./setup_local_akaunting.sh`
4. Follow the setup guide: `akaunting_setup_guide.md`
5. Copy `env_template.txt` to `.env` and fill in credentials
6. Run `python ops_integrations/scripts/run_sync.py`

### Option 2: Cloud Akaunting
1. Clone the repo
2. `pip install -r requirements.txt`
3. Set up Akaunting Cloud at https://akaunting.com
4. Copy `env_template.txt` to `.env` and fill in credentials
5. Run `python3 ops_integrations/scripts/run_sync.py`
6. Production `python3 ops_integrations/scripts/sync_production.py`

## Environment Configuration

### Required Environment Variables

#### Akaunting Accounting (Local Development)
- `AKAUNTING_BASE_URL`: http://localhost:8000
- `AKAUNTING_API_TOKEN`: API token from Akaunting Admin > Settings > API
- `AKAUNTING_COMPANY_ID`: 1 (default for local setup)

#### Akaunting Accounting (Cloud)
- `AKAUNTING_BASE_URL`: Your Akaunting Cloud URL
- `AKAUNTING_API_TOKEN`: API token from Akaunting Admin > Settings > API
- `AKAUNTING_COMPANY_ID`: Your company ID

#### Google Calendar
- `GOOGLE_CALENDAR_ID`: Calendar ID (default: 'primary')
- `GOOGLE_CREDENTIALS_PATH`: Path to Google OAuth credentials file
- `GOOGLE_TOKEN_PATH`: Path to store Google OAuth token

#### CRM & Inventory
- `CRM_API_URL`: Your CRM system API URL
- `CRM_API_KEY`: CRM API authentication key
- `SUPPLIER_API_URL`: Supplier inventory API URL
- `SUPPLIER_API_KEY`: Supplier API authentication key

## Project Structure
```
Plumbing_AGI/
├── akaunting/                    # Local Akaunting installation
│   ├── app/                     # Akaunting application files
│   ├── public/                  # Web server files
│   └── artisan                  # Laravel command line tool
├── ops_integrations/            # Python integration code
│   ├── adapters/               # API adapters
│   ├── etl/                    # ETL pipeline
│   └── scripts/                # Utility scripts
├── setup_local_akaunting.sh    # Local setup script
├── akaunting_setup_guide.md    # Detailed setup guide
└── test_akaunting.py           # Akaunting connection test
```

## Testing

The system includes comprehensive tests for each integration:
- Calendar: Read events and create appointments
- Accounting: Sync customers and invoices from Akaunting
- CRM: Customer data synchronization
- Inventory: Parts tracking and reorder automation

## Local Development

### Prerequisites
- PHP 8.1+
- Composer
- MySQL/MariaDB
- Python 3.8+

### Quick Setup
```bash
# Install dependencies
pip install -r requirements.txt

# Set up local Akaunting
./setup_local_akaunting.sh

# Follow the setup guide
cat akaunting_setup_guide.md

# Test the integration
python3 test_akaunting.py
```
