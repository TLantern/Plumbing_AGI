#!/bin/bash

# Heroku Deployment Script for Plumbing AGI
# This script deploys both the phone service and salon dashboard to Heroku

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging function
log() {
    echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1"
}

error() {
    echo -e "${RED}ERROR:${NC} $1"
    exit 1
}

success() {
    echo -e "${GREEN}SUCCESS:${NC} $1"
}

warning() {
    echo -e "${YELLOW}WARNING:${NC} $1"
}

# Check if Heroku CLI is installed
check_heroku_cli() {
    if ! command -v heroku &> /dev/null; then
        error "Heroku CLI is not installed. Please install it first: https://devcenter.heroku.com/articles/heroku-cli"
    fi
    log "Heroku CLI found"
}

# Check if user is logged in to Heroku
check_heroku_login() {
    if ! heroku auth:whoami &> /dev/null; then
        error "Not logged in to Heroku. Please run: heroku login"
    fi
    log "Logged in to Heroku as $(heroku auth:whoami)"
}

# Get app names from user
get_app_names() {
    echo
    log "Please provide the Heroku app names for deployment:"
    echo
    
    read -p "Enter name for phone service app (or press Enter to auto-generate): " PHONE_APP_NAME
    if [ -z "$PHONE_APP_NAME" ]; then
        PHONE_APP_NAME="plumbing-phone-$(date +%s)"
        log "Auto-generated phone app name: $PHONE_APP_NAME"
    fi
    
    read -p "Enter name for salon dashboard app (or press Enter to auto-generate): " DASHBOARD_APP_NAME
    if [ -z "$DASHBOARD_APP_NAME" ]; then
        DASHBOARD_APP_NAME="salon-dashboard-$(date +%s)"
        log "Auto-generated dashboard app name: $DASHBOARD_APP_NAME"
    fi
    
    echo
    log "App names:"
    log "  Phone Service: $PHONE_APP_NAME"
    log "  Salon Dashboard: $DASHBOARD_APP_NAME"
    echo
}

# Create Heroku apps
create_heroku_apps() {
    log "Creating Heroku apps..."
    
    # Create phone service app
    if heroku apps:info --app "$PHONE_APP_NAME" &> /dev/null; then
        warning "Phone service app '$PHONE_APP_NAME' already exists"
    else
        heroku create "$PHONE_APP_NAME" --region us
        success "Created phone service app: $PHONE_APP_NAME"
    fi
    
    # Create salon dashboard app
    if heroku apps:info --app "$DASHBOARD_APP_NAME" &> /dev/null; then
        warning "Salon dashboard app '$DASHBOARD_APP_NAME' already exists"
    else
        heroku create "$DASHBOARD_APP_NAME" --region us
        success "Created salon dashboard app: $DASHBOARD_APP_NAME"
    fi
}

# Deploy phone service
deploy_phone_service() {
    log "Deploying phone service to $PHONE_APP_NAME..."
    
    # Add Heroku remote
    git remote remove heroku-phone 2>/dev/null || true
    heroku git:remote -a "$PHONE_APP_NAME" -r heroku-phone
    
    # Set environment variables
    log "Setting environment variables for phone service..."
    
    # Check if .env file exists and read values
    if [ -f ".env" ]; then
        log "Reading environment variables from .env file..."
        source .env
    fi
    
    # Set required environment variables
    if [ -n "$TWILIO_ACCOUNT_SID" ]; then
        heroku config:set TWILIO_ACCOUNT_SID="$TWILIO_ACCOUNT_SID" --app "$PHONE_APP_NAME"
    else
        warning "TWILIO_ACCOUNT_SID not found in .env. Please set it manually after deployment."
    fi
    
    if [ -n "$TWILIO_AUTH_TOKEN" ]; then
        heroku config:set TWILIO_AUTH_TOKEN="$TWILIO_AUTH_TOKEN" --app "$PHONE_APP_NAME"
    else
        warning "TWILIO_AUTH_TOKEN not found in .env. Please set it manually after deployment."
    fi
    
    if [ -n "$OPENAI_API_KEY" ]; then
        heroku config:set OPENAI_API_KEY="$OPENAI_API_KEY" --app "$PHONE_APP_NAME"
    else
        warning "OPENAI_API_KEY not found in .env. Please set it manually after deployment."
    fi
    
    if [ -n "$ELEVENLABS_API_KEY" ]; then
        heroku config:set ELEVENLABS_API_KEY="$ELEVENLABS_API_KEY" --app "$PHONE_APP_NAME"
    else
        warning "ELEVENLABS_API_KEY not found in .env. Please set it manually after deployment."
    fi
    
    # Set default values
    heroku config:set ELEVENLABS_VOICE_ID="kdmDKE6EkgrWrrykO9Qt" --app "$PHONE_APP_NAME"
    heroku config:set EXTERNAL_WEBHOOK_URL="https://$PHONE_APP_NAME.herokuapp.com" --app "$PHONE_APP_NAME"
    
    # Deploy
    git push heroku-phone main
    
    success "Phone service deployed to: https://$PHONE_APP_NAME.herokuapp.com"
}

# Deploy salon dashboard
deploy_salon_dashboard() {
    log "Deploying salon dashboard to $DASHBOARD_APP_NAME..."
    
    # Change to frontend directory
    cd frontend
    
    # Add Heroku remote
    git remote remove heroku-dashboard 2>/dev/null || true
    heroku git:remote -a "$DASHBOARD_APP_NAME" -r heroku-dashboard
    
    # Set environment variables
    log "Setting environment variables for salon dashboard..."
    heroku config:set NEXT_PUBLIC_PHONE_API_URL="https://$PHONE_APP_NAME.herokuapp.com" --app "$DASHBOARD_APP_NAME"
    heroku config:set NEXT_PUBLIC_SALON_API_URL="https://$PHONE_APP_NAME.herokuapp.com" --app "$DASHBOARD_APP_NAME"
    
    # Deploy
    git push heroku-dashboard main
    
    # Return to project root
    cd ..
    
    success "Salon dashboard deployed to: https://$DASHBOARD_APP_NAME.herokuapp.com"
}

# Verify deployment
verify_deployment() {
    log "Verifying deployment..."
    
    # Check phone service health
    log "Checking phone service health..."
    if curl -s "https://$PHONE_APP_NAME.herokuapp.com/health" | grep -q "healthy"; then
        success "Phone service is healthy"
    else
        warning "Phone service health check failed"
    fi
    
    # Check salon dashboard
    log "Checking salon dashboard..."
    if curl -s "https://$DASHBOARD_APP_NAME.herokuapp.com" | grep -q "html"; then
        success "Salon dashboard is accessible"
    else
        warning "Salon dashboard accessibility check failed"
    fi
}

# Display final information
display_final_info() {
    echo
    log "Deployment completed!"
    echo
    log "Your applications are now live at:"
    log "  Phone Service: https://$PHONE_APP_NAME.herokuapp.com"
    log "  Salon Dashboard: https://$DASHBOARD_APP_NAME.herokuapp.com"
    echo
    log "Next steps:"
    log "  1. Update your Twilio webhook URL to: https://$PHONE_APP_NAME.herokuapp.com/voice"
    log "  2. Set any missing environment variables in Heroku dashboard"
    log "  3. Test the phone service by calling your Twilio number"
    log "  4. Access the salon dashboard to view real-time analytics"
    echo
    log "Useful commands:"
    log "  View phone service logs: heroku logs --tail -a $PHONE_APP_NAME"
    log "  View dashboard logs: heroku logs --tail -a $DASHBOARD_APP_NAME"
    log "  Open phone service: heroku open -a $PHONE_APP_NAME"
    log "  Open dashboard: heroku open -a $DASHBOARD_APP_NAME"
    echo
}

# Main execution
main() {
    log "Starting Heroku deployment for Plumbing AGI..."
    
    check_heroku_cli
    check_heroku_login
    get_app_names
    create_heroku_apps
    deploy_phone_service
    deploy_salon_dashboard
    verify_deployment
    display_final_info
}

# Run main function
main "$@"
