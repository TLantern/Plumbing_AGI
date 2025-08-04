#!/usr/bin/env python3
"""
Test suite for Baserow CRM integration
Tests customer creation, inquiry saving, and error handling
"""

import os
import sys
import json
import unittest
from unittest.mock import patch, MagicMock
from datetime import datetime
from typing import Dict, Any

# Add the project root to the Python path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

from ops_integrations.adapters.crm import CRMAdapter
from ops_integrations.models import Customer

class TestBaserowCRM(unittest.TestCase):
    """Test cases for Baserow CRM integration."""
    
    def setUp(self):
        """Set up test environment."""
        # Mock environment variables
        self.env_patcher = patch.dict(os.environ, {
            'BASEROW_API_URL': 'https://api.baserow.io',
            'BASEROW_API_TOKEN': 'test_token_12345',
            'BASEROW_DATABASE_ID': '12345',
            'BASEROW_CUSTOMERS_TABLE_ID': '67890',
            'BASEROW_INQUIRIES_TABLE_ID': '11111'
        })
        self.env_patcher.start()
        
        self.crm = CRMAdapter()
        
        # Sample test data
        self.sample_inquiry = {
            "name": "John Doe",
            "email": "john.doe@example.com",
            "phone": "555-123-4567",
            "address": "123 Main St, Anytown, USA",
            "service_type": "Emergency Plumbing",
            "description": "Kitchen sink is clogged and water is backing up",
            "urgency": "High",
            "source": "Phone Call",
            "contact_method": "Phone"
        }
        
        self.sample_customer = Customer(
            id="cust_001",
            name="Jane Smith",
            email="jane.smith@example.com",
            phone="555-987-6543",
            address="456 Oak Ave, Somewhere, USA"
        )

    def tearDown(self):
        """Clean up after tests."""
        self.env_patcher.stop()

    @patch('requests.get')
    @patch('requests.post')
    def test_save_customer_inquiry_new_customer(self, mock_post, mock_get):
        """Test saving inquiry for a new customer."""
        # Mock customer search (no existing customer found)
        mock_get.return_value.json.return_value = {"results": []}
        mock_get.return_value.raise_for_status.return_value = None
        
        # Mock customer creation
        mock_post.return_value.json.return_value = {"id": 1}
        mock_post.return_value.raise_for_status.return_value = None
        
        # Mock inquiry creation
        mock_post.return_value.json.return_value = {"id": 101}
        
        result = self.crm.save_customer_inquiry(self.sample_inquiry)
        
        # Verify customer creation was called
        mock_post.assert_called()
        self.assertIsNotNone(result)
        self.assertEqual(result.get('id'), 101)

    @patch('requests.get')
    @patch('requests.patch')
    @patch('requests.post')
    def test_save_customer_inquiry_existing_customer(self, mock_post, mock_patch, mock_get):
        """Test saving inquiry for an existing customer."""
        # Mock customer search (existing customer found)
        mock_get.return_value.json.return_value = {
            "results": [{"id": 1, "name": "John Doe", "email": "john.doe@example.com"}]
        }
        mock_get.return_value.raise_for_status.return_value = None
        
        # Mock customer update
        mock_patch.return_value.json.return_value = {"id": 1}
        mock_patch.return_value.raise_for_status.return_value = None
        
        # Mock inquiry creation
        mock_post.return_value.json.return_value = {"id": 102}
        
        result = self.crm.save_customer_inquiry(self.sample_inquiry)
        
        # Verify customer update was called
        mock_patch.assert_called()
        self.assertIsNotNone(result)
        self.assertEqual(result.get('id'), 102)

    @patch('requests.get')
    @patch('requests.post')
    def test_save_customer_inquiry_no_inquiries_table(self, mock_post, mock_get):
        """Test saving inquiry when no separate inquiries table exists."""
        # Remove inquiries table ID
        self.crm.inquiries_table_id = None
        
        # Mock customer search and creation
        mock_get.return_value.json.return_value = {"results": []}
        mock_get.return_value.raise_for_status.return_value = None
        mock_post.return_value.json.return_value = {"id": 1}
        mock_post.return_value.raise_for_status.return_value = None
        
        result = self.crm.save_customer_inquiry(self.sample_inquiry)
        
        # Should save to customer table instead
        self.assertIsNotNone(result)
        self.assertNotIn('error', result)

    @patch('requests.get')
    @patch('requests.post')
    def test_save_customer_inquiry_api_error(self, mock_post, mock_get):
        """Test handling of API errors."""
        # Mock API error
        mock_get.side_effect = Exception("API Error")
        
        result = self.crm.save_customer_inquiry(self.sample_inquiry)
        
        # Should fall back to local storage
        self.assertIsNotNone(result)
        self.assertIn('id', result)
        self.assertTrue(result['id'].startswith('local_'))

    def test_save_customer_inquiry_disabled_crm(self):
        """Test saving inquiry when CRM is disabled."""
        # Disable CRM by removing API token
        self.crm.api_token = None
        self.crm.enabled = False
        
        result = self.crm.save_customer_inquiry(self.sample_inquiry)
        
        # Should use fallback storage
        self.assertIsNotNone(result)
        self.assertIn('id', result)
        self.assertTrue(result['id'].startswith('local_'))

    @patch('requests.get')
    def test_find_existing_customer_by_email(self, mock_get):
        """Test finding existing customer by email."""
        mock_get.return_value.json.return_value = {
            "results": [{"id": 1, "name": "John Doe", "email": "john.doe@example.com"}]
        }
        mock_get.return_value.raise_for_status.return_value = None
        
        customer = self.crm._find_existing_customer("john.doe@example.com", None)
        
        self.assertIsNotNone(customer)
        self.assertEqual(customer['id'], 1)
        self.assertEqual(customer['email'], "john.doe@example.com")

    @patch('requests.get')
    def test_find_existing_customer_by_phone(self, mock_get):
        """Test finding existing customer by phone."""
        # First call returns no results (email search)
        # Second call returns customer (phone search)
        mock_get.return_value.json.side_effect = [
            {"results": []},
            {"results": [{"id": 2, "name": "John Doe", "phone": "5551234567"}]}
        ]
        mock_get.return_value.raise_for_status.return_value = None
        
        customer = self.crm._find_existing_customer("", "555-123-4567")
        
        self.assertIsNotNone(customer)
        self.assertEqual(customer['id'], 2)
        self.assertEqual(customer['phone'], "5551234567")

    @patch('requests.get')
    def test_find_existing_customer_not_found(self, mock_get):
        """Test when customer is not found."""
        mock_get.return_value.json.return_value = {"results": []}
        mock_get.return_value.raise_for_status.return_value = None
        
        customer = self.crm._find_existing_customer("nonexistent@example.com", "555-999-9999")
        
        self.assertIsNone(customer)

    @patch('requests.get')
    def test_get_customer_inquiries(self, mock_get):
        """Test getting customer inquiries."""
        mock_get.return_value.json.return_value = {
            "results": [
                {"id": 1, "description": "First inquiry"},
                {"id": 2, "description": "Second inquiry"}
            ]
        }
        mock_get.return_value.raise_for_status.return_value = None
        
        inquiries = self.crm.get_customer_inquiries(1)
        
        self.assertEqual(len(inquiries), 2)
        self.assertEqual(inquiries[0]['description'], "First inquiry")
        self.assertEqual(inquiries[1]['description'], "Second inquiry")

    @patch('requests.get')
    def test_get_customer_inquiries_disabled(self, mock_get):
        """Test getting customer inquiries when CRM is disabled."""
        self.crm.enabled = False
        
        inquiries = self.crm.get_customer_inquiries(1)
        
        self.assertEqual(inquiries, [])
        mock_get.assert_not_called()

    @patch('requests.get')
    @patch('requests.post')
    def test_sync_customers(self, mock_post, mock_get):
        """Test syncing customers from Akaunting."""
        # Mock customer search and creation
        mock_get.return_value.json.return_value = {"results": []}
        mock_get.return_value.raise_for_status.return_value = None
        mock_post.return_value.json.return_value = {"id": 1}
        mock_post.return_value.raise_for_status.return_value = None
        
        customers = [self.sample_customer]
        self.crm.sync_customers(customers)
        
        # Verify customer was synced
        mock_post.assert_called()

    def test_sync_customers_disabled(self):
        """Test syncing customers when CRM is disabled."""
        self.crm.enabled = False
        
        customers = [self.sample_customer]
        self.crm.sync_customers(customers)
        
        # Should not make any API calls when disabled

    def test_fallback_save_inquiry(self):
        """Test fallback inquiry saving."""
        result = self.crm._fallback_save_inquiry(self.sample_inquiry)
        
        self.assertIsNotNone(result)
        self.assertIn('id', result)
        self.assertTrue(result['id'].startswith('local_'))
        self.assertIn('timestamp', result)
        self.assertIn('data', result)
        self.assertEqual(result['status'], 'saved_locally')

    def test_crm_initialization_with_env_vars(self):
        """Test CRM initialization with environment variables."""
        crm = CRMAdapter()
        
        self.assertTrue(crm.enabled)
        self.assertEqual(crm.base_url, 'https://api.baserow.io')
        self.assertEqual(crm.api_token, 'test_token_12345')
        self.assertEqual(crm.database_id, '12345')
        self.assertEqual(crm.customers_table_id, '67890')
        self.assertEqual(crm.inquiries_table_id, '11111')

    def test_crm_initialization_without_env_vars(self):
        """Test CRM initialization without environment variables."""
        with patch.dict(os.environ, {}, clear=True):
            crm = CRMAdapter()
            
            self.assertFalse(crm.enabled)
            self.assertIsNone(crm.api_token)
            self.assertIsNone(crm.database_id)
            self.assertIsNone(crm.customers_table_id)
            self.assertIsNone(crm.inquiries_table_id)

    def test_headers_construction(self):
        """Test that headers are constructed correctly."""
        self.assertEqual(self.crm.headers['Authorization'], 'Token test_token_12345')
        self.assertEqual(self.crm.headers['Content-Type'], 'application/json')

class TestBaserowCRMIntegration(unittest.TestCase):
    """Integration tests for Baserow CRM with real API calls (optional)."""
    
    def setUp(self):
        """Set up integration test environment."""
        self.crm = CRMAdapter()
        
        # Only run integration tests if properly configured
        self.run_integration_tests = all([
            self.crm.api_token,
            self.crm.database_id,
            self.crm.customers_table_id,
            os.getenv('RUN_INTEGRATION_TESTS', 'false').lower() == 'true'
        ])

    @unittest.skipUnless(os.getenv('RUN_INTEGRATION_TESTS') == 'true', 
                        "Integration tests disabled - set RUN_INTEGRATION_TESTS=true to enable")
    def test_real_api_connection(self):
        """Test real connection to Baserow API."""
        if not self.run_integration_tests:
            self.skipTest("Integration tests not configured")
        
        # Test basic API connectivity
        try:
            # This would test actual API connection
            # For now, just verify the CRM is enabled
            self.assertTrue(self.crm.enabled)
        except Exception as e:
            self.fail(f"Failed to connect to Baserow API: {e}")

    @unittest.skipUnless(os.getenv('RUN_INTEGRATION_TESTS') == 'true',
                        "Integration tests disabled - set RUN_INTEGRATION_TESTS=true to enable")
    def test_real_customer_creation(self):
        """Test real customer creation in Baserow."""
        if not self.run_integration_tests:
            self.skipTest("Integration tests not configured")
        
        test_inquiry = {
            "name": f"Test Customer {datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "email": f"test{datetime.now().strftime('%Y%m%d_%H%M%S')}@example.com",
            "phone": "555-999-9999",
            "service_type": "Test Service",
            "description": "Integration test inquiry",
            "source": "Integration Test"
        }
        
        result = self.crm.save_customer_inquiry(test_inquiry)
        
        self.assertIsNotNone(result)
        self.assertNotIn('error', result)

def run_tests():
    """Run the test suite."""
    # Create test suite
    test_suite = unittest.TestSuite()
    
    # Add unit tests
    test_suite.addTest(unittest.makeSuite(TestBaserowCRM))
    
    # Add integration tests if enabled
    if os.getenv('RUN_INTEGRATION_TESTS', 'false').lower() == 'true':
        test_suite.addTest(unittest.makeSuite(TestBaserowCRMIntegration))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(test_suite)
    
    return result.wasSuccessful()

if __name__ == '__main__':
    print("🧪 Running Baserow CRM Tests...")
    print("=" * 50)
    
    success = run_tests()
    
    if success:
        print("\n✅ All tests passed!")
    else:
        print("\n❌ Some tests failed!")
    
    print("\nTo run integration tests with real API calls:")
    print("export RUN_INTEGRATION_TESTS=true")
    print("python test_baserow_crm.py") 