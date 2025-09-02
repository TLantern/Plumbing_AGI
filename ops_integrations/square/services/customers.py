"""
Square Customers Service

Handles customer-related operations for Square API.
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

from ..client import SquareClient
from ..exceptions import SquareCustomerError


logger = logging.getLogger(__name__)


class CustomersService:
    """Service for managing Square customers"""
    
    def __init__(self, client: SquareClient):
        """
        Initialize CustomersService
        
        Args:
            client: Square API client instance
        """
        self.client = client
    
    def create_customer(self, first_name: str, last_name: str, 
                       phone_number: Optional[str] = None,
                       email: Optional[str] = None,
                       note: Optional[str] = None) -> Dict[str, Any]:
        """
        Create a new customer
        
        Args:
            first_name: Customer's first name
            last_name: Customer's last name
            phone_number: Customer's phone number (optional)
            email: Customer's email address (optional)
            note: Additional notes about the customer (optional)
            
        Returns:
            Created customer object
            
        Raises:
            SquareCustomerError: If customer creation fails
        """
        try:
            logger.info(f"Creating customer: {first_name} {last_name}")
            
            customer_data = {
                "given_name": first_name,
                "family_name": last_name
            }
            
            if phone_number:
                customer_data["phone_number"] = phone_number
            
            if email:
                customer_data["email_address"] = email
                
            if note:
                customer_data["note"] = note
            
            data = customer_data
            
            response = self.client.post("/v2/customers", data=data)
            
            customer = response.get("customer")
            if not customer:
                raise SquareCustomerError("Failed to create customer - no customer data returned")
            
            customer_id = customer.get("id")
            logger.info(f"Created customer with ID: {customer_id}")
            
            return customer
            
        except Exception as e:
            logger.error(f"Failed to create customer: {e}")
            raise SquareCustomerError(f"Failed to create customer: {e}")
    
    def search_customers(self, phone_number: Optional[str] = None,
                        email: Optional[str] = None,
                        name: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Search for customers by phone, email, or name
        
        Args:
            phone_number: Phone number to search for
            email: Email address to search for
            name: Name to search for
            
        Returns:
            List of matching customers
            
        Raises:
            SquareCustomerError: If search fails
        """
        try:
            logger.info("Searching for customers")
            
            query_filters = []
            
            # Add phone number filter
            if phone_number:
                query_filters.append({
                    "phone_number": {
                        "exact": phone_number
                    }
                })
            
            # Add email filter
            if email:
                query_filters.append({
                    "email_address": {
                        "exact": email
                    }
                })
            
            # Add name filter
            if name:
                query_filters.append({
                    "text": {
                        "exact": name
                    }
                })
            
            if not query_filters:
                raise SquareCustomerError("At least one search criteria must be provided")
            
            data = {
                "query": {
                    "filter": {
                        "or": query_filters
                    }
                }
            }
            
            response = self.client.post("/v2/customers/search", data=data)
            
            customers = response.get("customers", [])
            logger.info(f"Found {len(customers)} matching customers")
            
            return customers
            
        except Exception as e:
            logger.error(f"Failed to search customers: {e}")
            raise SquareCustomerError(f"Failed to search customers: {e}")
    
    def get_customer(self, customer_id: str) -> Dict[str, Any]:
        """
        Get a specific customer by ID
        
        Args:
            customer_id: Square customer ID
            
        Returns:
            Customer object
            
        Raises:
            SquareCustomerError: If customer retrieval fails
        """
        try:
            logger.info(f"Fetching customer: {customer_id}")
            response = self.client.get(f"/v2/customers/{customer_id}")
            
            customer = response.get("customer")
            if not customer:
                raise SquareCustomerError(f"Customer {customer_id} not found")
            
            return customer
            
        except Exception as e:
            logger.error(f"Failed to get customer {customer_id}: {e}")
            raise SquareCustomerError(f"Failed to get customer {customer_id}: {e}")
    
    def find_or_create_customer(self, first_name: str, last_name: str,
                              phone_number: Optional[str] = None,
                              email: Optional[str] = None) -> Dict[str, Any]:
        """
        Find existing customer or create new one
        
        Args:
            first_name: Customer's first name
            last_name: Customer's last name
            phone_number: Customer's phone number (optional)
            email: Customer's email address (optional)
            
        Returns:
            Customer object (existing or newly created)
        """
        try:
            logger.info(f"Finding or creating customer: {first_name} {last_name}")
            
            # First try to find existing customer
            existing_customers = []
            
            # Search by phone if provided
            if phone_number:
                try:
                    phone_customers = self.search_customers(phone_number=phone_number)
                    existing_customers.extend(phone_customers)
                except:
                    pass  # Continue if phone search fails
            
            # Search by email if provided
            if email and not existing_customers:
                try:
                    email_customers = self.search_customers(email=email)
                    existing_customers.extend(email_customers)
                except:
                    pass  # Continue if email search fails
            
            # Search by name if no phone/email match
            if not existing_customers:
                try:
                    full_name = f"{first_name} {last_name}"
                    name_customers = self.search_customers(name=full_name)
                    existing_customers.extend(name_customers)
                except:
                    pass  # Continue if name search fails
            
            # If found existing customer, return first match
            if existing_customers:
                customer = existing_customers[0]
                customer_id = customer.get("id")
                logger.info(f"Found existing customer: {customer_id}")
                return customer
            
            # No existing customer found, create new one
            logger.info("No existing customer found, creating new one")
            return self.create_customer(
                first_name=first_name,
                last_name=last_name,
                phone_number=phone_number,
                email=email
            )
            
        except Exception as e:
            logger.error(f"Failed to find or create customer: {e}")
            raise SquareCustomerError(f"Failed to find or create customer: {e}")
    
    def update_customer(self, customer_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update customer information
        
        Args:
            customer_id: Square customer ID
            updates: Dictionary of fields to update
            
        Returns:
            Updated customer object
            
        Raises:
            SquareCustomerError: If update fails
        """
        try:
            logger.info(f"Updating customer: {customer_id}")
            
            data = updates
            
            response = self.client.put(f"/v2/customers/{customer_id}", data=data)
            
            customer = response.get("customer")
            if not customer:
                raise SquareCustomerError("Failed to update customer - no customer data returned")
            
            logger.info(f"Updated customer: {customer_id}")
            return customer
            
        except Exception as e:
            logger.error(f"Failed to update customer {customer_id}: {e}")
            raise SquareCustomerError(f"Failed to update customer {customer_id}: {e}")
    
    def delete_customer(self, customer_id: str) -> bool:
        """
        Delete a customer
        
        Args:
            customer_id: Square customer ID
            
        Returns:
            True if deletion successful
            
        Raises:
            SquareCustomerError: If deletion fails
        """
        try:
            logger.info(f"Deleting customer: {customer_id}")
            
            self.client.delete(f"/v2/customers/{customer_id}")
            
            logger.info(f"Deleted customer: {customer_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete customer {customer_id}: {e}")
            raise SquareCustomerError(f"Failed to delete customer {customer_id}: {e}")
    
    def get_customer_id(self, first_name: str, last_name: str,
                       phone_number: Optional[str] = None,
                       email: Optional[str] = None) -> str:
        """
        Get customer ID, creating customer if necessary
        
        Args:
            first_name: Customer's first name
            last_name: Customer's last name
            phone_number: Customer's phone number (optional)
            email: Customer's email address (optional)
            
        Returns:
            Customer ID
            
        Raises:
            SquareCustomerError: If unable to get customer ID
        """
        try:
            customer = self.find_or_create_customer(
                first_name=first_name,
                last_name=last_name,
                phone_number=phone_number,
                email=email
            )
            
            customer_id = customer.get("id")
            if not customer_id:
                raise SquareCustomerError("Customer object missing ID field")
            
            return customer_id
            
        except Exception as e:
            logger.error(f"Failed to get customer ID: {e}")
            raise SquareCustomerError(f"Failed to get customer ID: {e}")
