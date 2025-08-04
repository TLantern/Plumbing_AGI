#!/bin/bash

echo "🔧 Environment Setup for Plumbing AGI"
echo "====================================="

# Function to copy environment file
copy_env_file() {
    local source=$1
    local target=$2
    local description=$3
    
    if [ ! -f "$target" ]; then
        echo "📝 Creating $description..."
        cp "$source" "$target"
        echo "✅ Created $target"
    else
        echo "⚠️ $target already exists (skipping)"
    fi
}

# Set up main project environment
echo ""
echo "🏠 Setting up main project environment..."
copy_env_file "env_local.txt" ".env" "local development environment"

# Set up Akaunting environment
echo ""
echo "📊 Setting up Akaunting environment..."
copy_env_file "akaunting_env.txt" "akaunting/.env" "Akaunting environment"

echo ""
echo "✅ Environment files created!"
echo ""
echo "📋 Database credentials created:"
echo "   Username: akaunting"
echo "   Password: akaunting123"
echo "   Database: akaunting"
echo ""
echo "🔧 Next steps:"
echo "1. Install PHP and Composer: ./setup_local_akaunting.sh"
echo "2. Set up Akaunting: cd akaunting && composer install"
echo "3. Generate Akaunting key: cd akaunting && php artisan key:generate"
echo "4. Run migrations: cd akaunting && php artisan migrate"
echo "5. Create admin user: cd akaunting && php artisan user:create"
echo "6. Start Akaunting: cd akaunting && php artisan serve"
echo "7. Test integration: python3 test_akaunting.py" 