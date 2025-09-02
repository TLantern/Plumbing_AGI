"""
Square API Client

Main client for interfacing with Square's Commerce APIs.
Handles authentication, rate limiting, and error handling.
"""

import json
import time
import logging
from typing import Dict, Any, Optional, Union
from urllib.parse import urljoin
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .config import SquareConfig
from .exceptions import SquareAPIError, SquareRateLimitError, SquareAuthError


logger = logging.getLogger(__name__)


class SquareClient:
    """Main Square API client with error handling and retry logic"""
    
    def __init__(self, config: SquareConfig):
        """
        Initialize Square API client
        
        Args:
            config: Square API configuration
        """
        self.config = config
        self.config.validate()
        
        # Setup session with retry strategy
        self.session = requests.Session()
        retry_strategy = Retry(
            total=3,
            status_forcelist=[429, 500, 502, 503, 504],
            backoff_factor=1,
            respect_retry_after_header=True
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        
        # Rate limiting tracking
        self.last_request_time = 0
        self.min_request_interval = 0.1  # 100ms between requests
    
    def _wait_for_rate_limit(self):
        """Implement basic rate limiting"""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        if time_since_last < self.min_request_interval:
            time.sleep(self.min_request_interval - time_since_last)
        self.last_request_time = time.time()
    
    def _make_request(self, method: str, endpoint: str, data: Optional[Dict[str, Any]] = None, 
                     params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Make HTTP request to Square API with error handling
        
        Args:
            method: HTTP method (GET, POST, PUT, PATCH, DELETE)
            endpoint: API endpoint (without base URL)
            data: Request body data
            params: Query parameters
            
        Returns:
            API response as dictionary
            
        Raises:
            SquareAPIError: For API-related errors
            SquareRateLimitError: For rate limit errors
            SquareAuthError: For authentication errors
        """
        self._wait_for_rate_limit()
        
        url = urljoin(self.config.base_url, endpoint)
        headers = self.config.headers.copy()
        
        try:
            logger.debug(f"Making {method} request to {endpoint}")
            
            response = self.session.request(
                method=method,
                url=url,
                headers=headers,
                json=data,
                params=params,
                timeout=30
            )
            
            # Handle rate limiting
            if response.status_code == 429:
                retry_after = int(response.headers.get('Retry-After', 60))
                raise SquareRateLimitError(f"Rate limit exceeded. Retry after {retry_after} seconds")
            
            # Handle authentication errors
            if response.status_code == 401:
                raise SquareAuthError("Authentication failed. Check access token")
            
            # Handle other client/server errors
            if response.status_code >= 400:
                try:
                    error_data = response.json()
                    error_msg = error_data.get('errors', [{}])[0].get('detail', 'Unknown error')
                except:
                    error_msg = response.text or f"HTTP {response.status_code} error"
                
                raise SquareAPIError(f"API request failed: {error_msg}", 
                                   status_code=response.status_code, 
                                   response=response.text)
            
            # Parse successful response
            if response.content:
                return response.json()
            return {}
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed: {e}")
            raise SquareAPIError(f"Request failed: {e}")
    
    def get(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Make GET request"""
        return self._make_request("GET", endpoint, params=params)
    
    def post(self, endpoint: str, data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Make POST request"""
        return self._make_request("POST", endpoint, data=data)
    
    def put(self, endpoint: str, data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Make PUT request"""
        return self._make_request("PUT", endpoint, data=data)
    
    def patch(self, endpoint: str, data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Make PATCH request"""
        return self._make_request("PATCH", endpoint, data=data)
    
    def delete(self, endpoint: str) -> Dict[str, Any]:
        """Make DELETE request"""
        return self._make_request("DELETE", endpoint)
    
    def health_check(self) -> bool:
        """
        Check if the API client can connect to Square
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            # Try to list locations as a simple health check
            response = self.get("/v2/locations")
            return "locations" in response
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False
