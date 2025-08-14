# Environment File Management Guide

## Overview

This project uses multiple environment files for different purposes:

- **`.env`** - Main project environment (Python integration)
- **`akaunting/.env`** - Akaunting-specific environment (PHP/Laravel)
- **`env_local.txt`** - Template for local development
- **`env_production.txt`** - Template for production deployment

## Database Credentials

### Local Development Database
- **Host**: localhost
- **Port**: 3306
- **Database**: akaunting
- **Username**: akaunting
- **Password**: akaunting123

### How to Change Database Password

If you want to use a different password:

1. **Create new MySQL user:**
   ```bash
   mysql -u root -e "DROP USER IF EXISTS 'akaunting'@'localhost';"
   mysql -u root -e "CREATE USER 'akaunting'@'localhost' IDENTIFIED BY 'your_new_password';"
   mysql -u root -e "GRANT ALL PRIVILEGES ON akaunting.* TO 'akaunting'@'localhost';"
   mysql -u root -e "FLUSH PRIVILEGES;"
   ```

2. **Update Akaunting environment:**
   Edit `akaunting/.env` and change:
   ```env
   DB_PASSWORD=your_new_password
   ```

## Environment File Structure

### Main Project (.env)
```env
# Python integration environment
AKAUNTING_BASE_URL=http://localhost:8000
AKAUNTING_API_TOKEN=your_token
GOOGLE_CALENDAR_ID=primary
# ... other Python app settings
```

### Akaunting (.env)
```env
# PHP/Laravel environment
DB_CONNECTION=mysql
DB_HOST=127.0.0.1
DB_DATABASE=akaunting
DB_USERNAME=akaunting
DB_PASSWORD=akaunting123
# ... other Laravel settings
```

## Environment File Management

### Local Development
```bash
# Copy local template
cp env_local.txt .env

# Set up Akaunting environment
cp akaunting_env.txt akaunting/.env
```

### Production Deployment
```bash
# Copy production template
cp env_production.txt .env

# Edit with production values
nano .env
```

### Environment Switching
```bash
# Switch to local
cp env_local.txt .env

# Switch to production
cp env_production.txt .env

# Custom environment
cp env_custom.txt .env
```

## Security Best Practices

### 1. Never Commit .env Files
```bash
# Add to .gitignore
echo ".env" >> .gitignore
echo "akaunting/.env" >> .gitignore
```

### 2. Use Different Passwords for Different Environments
- Local: `akaunting123`
- Staging: `staging_password`
- Production: `strong_production_password`

### 3. Rotate API Tokens Regularly
- Generate new Akaunting API tokens monthly
- Update Google Calendar tokens when needed
- Use environment-specific tokens

## Troubleshooting

### Database Connection Issues
```bash
# Test database connection
mysql -u akaunting -pakaunting123 -e "SELECT 1;"

# Check MySQL status
brew services list | grep mysql

# Restart MySQL
brew services restart mysql
```

### Environment Variable Issues
```bash
# Check if variables are loaded
python3 -c "import os; print('AKAUNTING_BASE_URL:', os.getenv('AKAUNTING_BASE_URL'))"

# Load environment manually
source .env
```

### Akaunting Environment Issues
```bash
# Check Akaunting environment
cd akaunting && php artisan env

# Clear Akaunting cache
cd akaunting && php artisan cache:clear
```

## Quick Commands

### Setup Environment
```bash
./setup_env.sh
```

### Switch Environments
```bash
# Local
cp env_local.txt .env

# Production
cp env_production.txt .env
```

### Test Database
```bash
mysql -u akaunting -pakaunting123 -e "SHOW DATABASES;"
```

### Test Integration
```bash
python3 test_akaunting.py
``` 