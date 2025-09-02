"""
Square API Integration for Salon Booking System

This module provides a comprehensive integration with Square's Commerce APIs
for managing salon bookings, customers, and services.
"""

from .client import SquareClient
from .services.locations import LocationsService
from .services.catalog import CatalogService
from .services.customers import CustomersService
from .services.bookings import BookingsService
from .config import SquareConfig

__all__ = [
    'SquareClient',
    'LocationsService', 
    'CatalogService',
    'CustomersService',
    'BookingsService',
    'SquareConfig'
]

__version__ = '1.0.0'
