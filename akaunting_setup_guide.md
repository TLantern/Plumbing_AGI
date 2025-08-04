# Local Akaunting Setup Guide

## Prerequisites Installation

### 1. Install PHP (8.1 or higher)
```bash
# Using Homebrew (recommended)
brew install php

# Or download from https://www.php.net/downloads
```

### 2. Install Composer
```bash
# Using Homebrew
brew install composer

# Or download from https://getcomposer.org/download/
```

### 3. Install MySQL/MariaDB
```bash
# Using Homebrew
brew install mysql

# Start MySQL service
brew services start mysql
```

## Akaunting Setup

### 1. Navigate to Akaunting Directory
```bash
cd akaunting
```

### 2. Install Dependencies
```bash
composer install
```

### 3. Copy Environment File
```bash
cp .env.example .env
```

### 4. Configure Database
Edit `.env` file and set your database credentials:
```env
DB_CONNECTION=mysql
DB_HOST=127.0.0.1
DB_PORT=3306
DB_DATABASE=akaunting
DB_USERNAME=root
DB_PASSWORD=your_password
```

### 5. Create Database
```bash
mysql -u root -p -e "CREATE DATABASE akaunting;"
```

### 6. Generate Application Key
```bash
php artisan key:generate
```

### 7. Run Migrations
```bash
php artisan migrate
```

### 8. Create Admin User
```bash
php artisan user:create
```

### 9. Start Development Server
```bash
php artisan serve
```

## Integration with Plumbing AGI

### 1. Update Environment Variables
Add to your `.env` file:
```env
AKAUNTING_BASE_URL=http://localhost:8000
AKAUNTING_API_TOKEN=your_api_token_here
AKAUNTING_COMPANY_ID=1
```

### 2. Generate API Token
1. Log into Akaunting at http://localhost:8000
2. Go to Admin > Settings > API
3. Create a new API token
4. Copy the token to your environment variables

### 3. Test Integration
```bash
python3 test_akaunting.py
```

## File Structure
```
Plumbing_AGI/
├── akaunting/           # Akaunting installation
│   ├── app/
│   ├── public/
│   ├── artisan
│   └── ...
├── ops_integrations/    # Your Python integration
├── test_akaunting.py
└── ...
```

## Troubleshooting

### Common Issues:
1. **PHP not found**: Install PHP via Homebrew
2. **Composer not found**: Install Composer via Homebrew
3. **Database connection failed**: Check MySQL is running and credentials are correct
4. **Permission errors**: Ensure proper file permissions on storage and bootstrap/cache directories

### Useful Commands:
```bash
# Check PHP version
php --version

# Check Composer
composer --version

# Check MySQL status
brew services list | grep mysql

# Clear Akaunting cache
cd akaunting && php artisan cache:clear
``` 