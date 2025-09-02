# Square API Integration for Salon Booking System

This module provides a comprehensive integration with Square's Commerce APIs for managing salon bookings, customers, and services.

## Features

- **Location Management**: List and manage Square locations
- **Catalog Management**: Handle bookable services and variations
- **Customer Management**: Create, search, and manage customers
- **Booking Management**: Search availability, create, update, and cancel bookings
- **Error Handling**: Comprehensive error handling with custom exceptions
- **Rate Limiting**: Built-in rate limiting and retry logic

## Quick Start

### 1. Install Dependencies

```bash
pip install requests python-dotenv
```

### 2. Configuration

Copy the configuration template and set your Square API credentials:

```bash
cp config_template.env .env
```

Edit `.env` with your Square API credentials:

```env
SQUARE_ACCESS_TOKEN=your_access_token_here
SQUARE_ENVIRONMENT=sandbox  # or 'production'
SQUARE_LOCATION_ID=your_location_id_here
```

### 3. Basic Usage

```python
from ops_integrations.square import SquareClient, SquareConfig
from ops_integrations.square.services import LocationsService, BookingsService

# Initialize client
config = SquareConfig.from_env()
client = SquareClient(config)

# Get location ID
locations_service = LocationsService(client)
location_id = locations_service.get_main_location_id()

# Create a booking
bookings_service = BookingsService(client)
# ... (see examples below)
```

## Services Overview

### LocationsService

Manages Square locations:

```python
locations_service = LocationsService(client)

# List all locations
locations = locations_service.list_locations()

# Get main location ID
location_id = locations_service.get_main_location_id()

# Check if bookings are enabled
is_enabled = locations_service.is_bookings_enabled(location_id)
```

### CatalogService

Manages catalog items and services:

```python
catalog_service = CatalogService(client)

# Get bookable services
services = catalog_service.get_bookable_services(location_id)

# Find service by name
service = catalog_service.find_service_by_name("Haircut")

# Get service variation ID
variation_id = catalog_service.get_service_variation_id(service_id)
```

### CustomersService

Manages customers:

```python
customers_service = CustomersService(client)

# Find or create customer
customer = customers_service.find_or_create_customer(
    first_name="John",
    last_name="Doe",
    phone_number="+1234567890",
    email="john@example.com"
)

# Get customer ID
customer_id = customers_service.get_customer_id(
    first_name="John",
    last_name="Doe",
    phone_number="+1234567890"
)
```

### BookingsService

Manages bookings and availability:

```python
from datetime import datetime, timedelta

bookings_service = BookingsService(client)

# Search availability
start_time = datetime.utcnow() + timedelta(days=1)
end_time = start_time + timedelta(days=7)

availability = bookings_service.search_availability(
    location_id=location_id,
    service_variation_id=variation_id,
    start_at=start_time,
    end_at=end_time
)

# Create booking
appointment_time = datetime.utcnow() + timedelta(days=2)
booking = bookings_service.create_booking(
    location_id=location_id,
    customer_id=customer_id,
    service_variation_id=variation_id,
    start_at=appointment_time
)

# Cancel booking
cancelled_booking = bookings_service.cancel_booking(
    booking_id=booking["id"],
    cancellation_reason="Customer request"
)
```

## Complete Booking Flow Example

```python
from datetime import datetime, timedelta
from ops_integrations.square import SquareClient, SquareConfig
from ops_integrations.square.services import (
    LocationsService, CatalogService, CustomersService, BookingsService
)

def create_salon_booking(customer_info, service_name, appointment_time):
    \"\"\"Complete booking flow for salon\"\"\"
    
    # Initialize services
    config = SquareConfig.from_env()
    client = SquareClient(config)
    
    locations_service = LocationsService(client)
    catalog_service = CatalogService(client)
    customers_service = CustomersService(client)
    bookings_service = BookingsService(client)
    
    try:
        # 1. Get location ID
        location_id = locations_service.get_main_location_id()
        print(f"Using location: {location_id}")
        
        # 2. Find service and get variation ID
        service = catalog_service.find_service_by_name(service_name)
        if not service:
            raise ValueError(f"Service '{service_name}' not found")
        
        service_id = service["id"]
        variation_id = catalog_service.get_service_variation_id(service_id)
        print(f"Service variation ID: {variation_id}")
        
        # 3. Get or create customer
        customer_id = customers_service.get_customer_id(
            first_name=customer_info["first_name"],
            last_name=customer_info["last_name"],
            phone_number=customer_info.get("phone_number"),
            email=customer_info.get("email")
        )
        print(f"Customer ID: {customer_id}")
        
        # 4. Check availability
        is_available = bookings_service.check_availability_for_time(
            location_id=location_id,
            service_variation_id=variation_id,
            desired_time=appointment_time
        )
        
        if not is_available:
            raise ValueError("Requested time slot is not available")
        
        # 5. Create booking
        booking = bookings_service.create_booking(
            location_id=location_id,
            customer_id=customer_id,
            service_variation_id=variation_id,
            start_at=appointment_time,
            note=f"Booking for {service_name}"
        )
        
        print(f"Booking created successfully: {booking['id']}")
        return booking
        
    except Exception as e:
        print(f"Booking failed: {e}")
        raise

# Example usage
customer_info = {
    "first_name": "Jane",
    "last_name": "Smith", 
    "phone_number": "+1234567890",
    "email": "jane@example.com"
}

appointment_time = datetime.utcnow() + timedelta(days=3)
booking = create_salon_booking(customer_info, "Haircut", appointment_time)
```

## Phone Integration

For phone-based booking systems, integrate with your existing phone handlers:

```python
def handle_booking_request(caller_info, service_request, preferred_time):
    \"\"\"Handle booking request from phone call\"\"\"
    
    try:
        # Extract customer info from caller
        customer_info = {
            "first_name": caller_info.get("first_name"),
            "last_name": caller_info.get("last_name"),
            "phone_number": caller_info.get("phone_number")
        }
        
        # Create booking
        booking = create_salon_booking(
            customer_info=customer_info,
            service_name=service_request,
            appointment_time=preferred_time
        )
        
        return {
            "success": True,
            "booking_id": booking["id"],
            "message": f"Booking confirmed for {preferred_time.strftime('%Y-%m-%d %H:%M')}"
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": "Unable to create booking. Please try again."
        }
```

## Error Handling

The integration includes comprehensive error handling:

```python
from ops_integrations.square.exceptions import (
    SquareAPIError, SquareBookingError, SquareValidationError
)

try:
    booking = bookings_service.create_booking(...)
except SquareValidationError as e:
    print(f"Validation error: {e}")
except SquareBookingError as e:
    print(f"Booking error: {e}")
except SquareAPIError as e:
    print(f"API error: {e}")
```

## Important Notes

### Availability Search Rules

- **Time Range**: Must be ≥24 hours and ≤32 days for normal availability searches
- **Team Members**: Optional - if not specified, searches across all available team members
- **Location**: Must be specified and have bookings enabled

### Rate Limiting

The client includes built-in rate limiting:
- Minimum 100ms between requests
- Automatic retry for rate limit errors
- Exponential backoff for server errors

### Environment Setup

For production use:
1. Set `SQUARE_ENVIRONMENT=production`
2. Use production access token
3. Test thoroughly in sandbox first

## Getting Square API Credentials

1. Go to [Square Developer Console](https://developer.squareup.com/apps)
2. Create a new application
3. Get your access token from the application dashboard
4. For webhooks, get the webhook signature key
5. Note your application ID for OAuth flows

## Troubleshooting

### Common Issues

1. **Authentication Errors**: Check your access token and environment setting
2. **Location Not Found**: Ensure location has bookings enabled
3. **Service Not Found**: Verify service exists and is bookable
4. **Time Range Errors**: Ensure availability search window is 24+ hours

### Logging

Enable debug logging:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## API Documentation

For detailed Square API documentation, visit:
- [Square Commerce APIs](https://developer.squareup.com/docs/commerce)
- [Bookings API](https://developer.squareup.com/reference/square/bookings-api)
- [Customers API](https://developer.squareup.com/reference/square/customers-api)
- [Catalog API](https://developer.squareup.com/reference/square/catalog-api)
