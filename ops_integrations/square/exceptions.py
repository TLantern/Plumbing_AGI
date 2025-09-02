"""
Square API Exceptions

Custom exception classes for Square API integration error handling.
"""

from typing import Optional


class SquareAPIError(Exception):
    """Base exception for Square API errors"""
    
    def __init__(self, message: str, status_code: Optional[int] = None, 
                 response: Optional[str] = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.response = response


class SquareAuthError(SquareAPIError):
    """Exception for authentication-related errors"""
    pass


class SquareRateLimitError(SquareAPIError):
    """Exception for rate limiting errors"""
    pass


class SquareValidationError(SquareAPIError):
    """Exception for data validation errors"""
    pass


class SquareBookingError(SquareAPIError):
    """Exception for booking-specific errors"""
    pass


class SquareLocationError(SquareAPIError):
    """Exception for location-related errors"""
    pass


class SquareCatalogError(SquareAPIError):
    """Exception for catalog-related errors"""
    pass


class SquareCustomerError(SquareAPIError):
    """Exception for customer-related errors"""
    pass
