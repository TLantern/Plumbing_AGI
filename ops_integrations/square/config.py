"""
Square API Configuration

Manages configuration settings for Square API integration including
authentication, environment settings, and API endpoints.
"""

import os
from typing import Optional
from dataclasses import dataclass
from enum import Enum


class SquareEnvironment(Enum):
    """Square API environment options"""
    SANDBOX = "sandbox"
    PRODUCTION = "production"


@dataclass
class SquareConfig:
    """Configuration settings for Square API"""
    
    access_token: str
    environment: SquareEnvironment = SquareEnvironment.SANDBOX
    application_id: Optional[str] = None
    webhook_signature_key: Optional[str] = None
    location_id: Optional[str] = None
    
    # API Base URLs
    SANDBOX_BASE_URL = "https://connect.squareupsandbox.com"
    PRODUCTION_BASE_URL = "https://connect.squareup.com"
    
    @property
    def base_url(self) -> str:
        """Get the base URL for the current environment"""
        if self.environment == SquareEnvironment.SANDBOX:
            return self.SANDBOX_BASE_URL
        return self.PRODUCTION_BASE_URL
    
    @property
    def headers(self) -> dict:
        """Get standard headers for Square API requests"""
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.access_token}",
            "Square-Version": "2024-12-18"  # Latest API version
        }
    
    @classmethod
    def from_env(cls) -> 'SquareConfig':
        """Create configuration from environment variables"""
        access_token = os.getenv('SQUARE_ACCESS_TOKEN')
        if not access_token:
            raise ValueError("SQUARE_ACCESS_TOKEN environment variable is required")
        
        env_str = os.getenv('SQUARE_ENVIRONMENT', 'sandbox').lower()
        environment = SquareEnvironment.SANDBOX if env_str == 'sandbox' else SquareEnvironment.PRODUCTION
        
        return cls(
            access_token=access_token,
            environment=environment,
            application_id=os.getenv('SQUARE_APPLICATION_ID'),
            webhook_signature_key=os.getenv('SQUARE_WEBHOOK_SIGNATURE_KEY'),
            location_id=os.getenv('SQUARE_LOCATION_ID')
        )
    
    def validate(self) -> bool:
        """Validate that required configuration is present"""
        if not self.access_token:
            raise ValueError("Access token is required")
        return True
