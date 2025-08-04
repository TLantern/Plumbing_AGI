#!/bin/bash

echo "🚀 Setting up Local Akaunting for Plumbing AGI"
echo "=============================================="

# Check if Homebrew is installed
if ! command -v brew &> /dev/null; then
    echo "❌ Homebrew is not installed. Please install it first:"
    echo "   /bin/bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\""
    exit 1
fi

echo "📦 Installing prerequisites..."

# Install PHP
if ! command -v php &> /dev/null; then
    echo "📥 Installing PHP..."
    brew install php
else
    echo "✅ PHP is already installed"
fi

# Install Composer
if ! command -v composer &> /dev/null; then
    echo "📥 Installing Composer..."
    brew install composer
else
    echo "✅ Composer is already installed"
fi

# Install MySQL
if ! command -v mysql &> /dev/null; then
    echo "📥 Installing MySQL..."
    brew install mysql
    echo "🚀 Starting MySQL service..."
    brew services start mysql
else
    echo "✅ MySQL is already installed"
fi

echo ""
echo "🔧 Setting up Akaunting..."

# Navigate to Akaunting directory
cd akaunting

# Check if .env exists
if [ ! -f .env ]; then
    echo "📝 Creating .env file..."
    cp .env.example .env
else
    echo "✅ .env file already exists"
fi

# Install Composer dependencies
echo "📦 Installing Composer dependencies..."
composer install

# Generate application key
echo "🔑 Generating application key..."
php artisan key:generate

# Create database
echo "🗄️ Creating database..."
mysql -u root -e "CREATE DATABASE IF NOT EXISTS akaunting;" 2>/dev/null || echo "⚠️ Could not create database. Please create it manually."

echo ""
echo "✅ Setup complete!"
echo ""
echo "📋 Next steps:"
echo "1. Edit akaunting/.env and set your database credentials"
echo "2. Run: cd akaunting && php artisan migrate"
echo "3. Run: cd akaunting && php artisan user:create"
echo "4. Start Akaunting: cd akaunting && php artisan serve"
echo "5. Generate API token in Akaunting Admin > Settings > API"
echo "6. Update your .env file with the API token"
echo "7. Test integration: python3 test_akaunting.py"
echo ""
echo "📖 See akaunting_setup_guide.md for detailed instructions" 