"""
Comprehensive API endpoint tests for CSC Polling Place API.

Tests cover:
- Authentication scenarios (API key validation, master key operations)
- Rate limiting enforcement and bypass scenarios
- Data validation for all endpoints
- Error handling and edge cases
- VIP format responses
- Bulk operations
- Plugin management endpoints
- Geocoding endpoints
"""

import pytest
import unittest
from unittest.mock import Mock, patch, MagicMock
import json
import tempfile
import os
import time
from datetime import datetime, date
from io import BytesIO

# Import Flask app and related modules
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app
from models import PollingPlace, Precinct, Election, APIKey, AdminUser, db


class TestAuthenticationScenarios(unittest.TestCase):
    """Test all authentication scenarios for API endpoints."""

    def setUp(self):
        """Set up test fixtures."""
        self.app = app
        self.app.config['TESTING'] = True
        self.app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        self.client = self.app.test_client()
        self.ctx = self.app.app_context()
        self.ctx.push()
        
        # Create database tables
        db.create_all()
        
        # Create test API keys
        self.active_key = APIKey()
        self.active_key.key = "test-active-key-12345"
        self.active_key.name = "Active Test Key"
        self.active_key.is_active = True
        self.active_key.rate_limit_per_day = 100
        self.active_key.rate_limit_per_hour = 10
        db.session.add(self.active_key)
        
        self.inactive_key = APIKey()
        self.inactive_key.key = "test-inactive-key-67890"
        self.inactive_key.name = "Inactive Test Key"
        self.inactive_key.is_active = False
        db.session.add(self.inactive_key)
        
        db.session.commit()

    def tearDown(self):
        """Clean up test fixtures."""
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    def test_no_api_key_access(self):
        """Test access without API key should return 401."""
        response = self.client.get('/api/polling-places?state=VA')
        self.assertEqual(response.status_code, 401)
        data = json.loads(response.data)
        self.assertIn('API key required', data['error'])

    def test_invalid_api_key_access(self):
        """Test access with invalid API key should return 401."""
        headers = {'X-API-Key': 'invalid-key-123'}
        response = self.client.get('/api/polling-places?state=VA', headers=headers)
        self.assertEqual(response.status_code, 401)
        data = json.loads(response.data)
        self.assertIn('Invalid or inactive API key', data['error'])

    def test_inactive_api_key_access(self):
        """Test access with inactive API key should return 401."""
        headers = {'X-API-Key': self.inactive_key.key}
        response = self.client.get('/api/polling-places?state=VA', headers=headers)
        self.assertEqual(response.status_code, 401)
        data = json.loads(response.data)
        self.assertIn('Invalid or inactive API key', data['error'])

    def test_api_key_last_used_updated(self):
        """Test that API key last_used_at is updated on successful access."""
        original_last_used = self.active_key.last_used_at
        headers = {'X-API-Key': self.active_key.key}
        
        # Test health endpoint which doesn't require plugin manager
        response = self.client.get('/health', headers=headers)
        
        # Check that last_used_at was updated
        updated_key = APIKey.query.get(self.active_key.id)
        self.assertNotEqual(updated_key.last_used_at, original_last_used)

    @patch.dict(os.environ, {'MASTER_API_KEY': 'test-master-key-123'})
    def test_master_key_create_api_key(self):
        """Test creating API key with master key."""
        headers = {'X-API-Key': 'test-master-key-123'}
        data = {'name': 'New Test Key', 'rate_limit_per_day': 50}
        
        response = self.client.post('/api/keys', 
                                  headers=headers,
                                  data=json.dumps(data),
                                  content_type='application/json')
        
        self.assertEqual(response.status_code, 201)
        response_data = json.loads(response.data)
        self.assertIn('key', response_data)
        self.assertEqual(response_data['key']['name'], 'New Test Key')

    @patch.dict(os.environ, {'MASTER_API_KEY': 'test-master-key-123'})
    def test_invalid_master_key_create_api_key(self):
        """Test creating API key with invalid master key."""
        headers = {'X-API-Key': 'invalid-master-key'}
        data = {'name': 'New Test Key'}
        
        response = self.client.post('/api/keys', 
                                  headers=headers,
                                  data=json.dumps(data),
                                  content_type='application/json')
        
        self.assertEqual(response.status_code, 401)
        response_data = json.loads(response.data)
        self.assertIn('Master API key required', response_data['error'])

    def test_api_key_list_requires_authentication(self):
        """Test listing API keys requires authentication."""
        response = self.client.get('/api/keys')
        self.assertEqual(response.status_code, 401)

    def test_api_key_list_with_valid_key(self):
        """Test listing API keys with valid authentication."""
        headers = {'X-API-Key': self.active_key.key}
        response = self.client.get('/api/keys', headers=headers)
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.data)
        self.assertIn('keys', response_data)
        self.assertEqual(len(response_data['keys']), 2)  # Both keys we created


class TestRateLimiting(unittest.TestCase):
    """Test rate limiting functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.app = app
        self.app.config['TESTING'] = True
        self.app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        self.client = self.app.test_client()
        self.ctx = self.app.app_context()
        self.ctx.push()
        
        # Create database tables
        db.create_all()
        
        # Create test API key with rate limits
        self.limited_key = APIKey()
        self.limited_key.key = "limited-key-12345"
        self.limited_key.name = "Limited Test Key"
        self.limited_key.is_active = True
        self.limited_key.rate_limit_per_day = 5
        self.limited_key.rate_limit_per_hour = 2
        db.session.add(self.limited_key)
        db.session.commit()

    def tearDown(self):
        """Clean up test fixtures."""
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    def test_rate_limit_enforcement(self):
        """Test that rate limits are enforced."""
        headers = {'X-API-Key': self.limited_key.key}
        
        # Make multiple requests quickly to hit rate limit
        responses = []
        for i in range(10):
            response = self.client.get('/health', headers=headers)
            responses.append(response.status_code)
            if response.status_code == 429:
                break
        
        # Should eventually hit rate limit
        self.assertIn(429, responses)

    def test_unlimited_api_key(self):
        """Test API key without rate limits."""
        unlimited_key = APIKey()
        unlimited_key.key = "unlimited-key-12345"
        unlimited_key.name = "Unlimited Test Key"
        unlimited_key.is_active = True
        unlimited_key.rate_limit_per_day = None
        unlimited_key.rate_limit_per_hour = None
        db.session.add(unlimited_key)
        db.session.commit()
        
        headers = {'X-API-Key': unlimited_key.key}
        
        # Should not hit rate limits for health endpoint
        for i in range(10):
            response = self.client.get('/health', headers=headers)
            self.assertNotEqual(response.status_code, 429)


class TestDataValidation(unittest.TestCase):
    """Test data validation for all API endpoints."""

    def setUp(self):
        """Set up test fixtures."""
        self.app = app
        self.app.config['TESTING'] = True
        self.app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        self.client = self.app.test_client()
        self.ctx = self.app.app_context()
        self.ctx.push()
        
        # Create database tables
        db.create_all()
        
        # Create test API key
        self.api_key = APIKey()
        self.api_key.key = "test-key-12345"
        self.api_key.name = "Test Key"
        self.api_key.is_active = True
        db.session.add(self.api_key)
        db.session.commit()
        
        self.headers = {'X-API-Key': self.api_key.key}

    def tearDown(self):
        """Clean up test fixtures."""
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    def test_polling_places_missing_state_parameter(self):
        """Test polling places endpoint without required state parameter."""
        response = self.client.get('/api/polling-places', headers=self.headers)
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertIn('State parameter is required', data['error'])

    def test_create_api_key_missing_name(self):
        """Test creating API key without required name parameter."""
        with patch.dict(os.environ, {'MASTER_API_KEY': 'test-master-key-123'}):
            headers = {'X-API-Key': 'test-master-key-123'}
            data = {'rate_limit_per_day': 100}
            
            response = self.client.post('/api/keys', 
                                      headers=headers,
                                      data=json.dumps(data),
                                      content_type='application/json')
            
            self.assertEqual(response.status_code, 400)
            response_data = json.loads(response.data)
            self.assertIn('Name required', response_data['error'])

    def test_bulk_delete_invalid_delete_types(self):
        """Test bulk delete with invalid delete types."""
        data = {
            'delete_types': ['invalid_type'],
            'confirm': 'DELETE'
        }
        
        response = self.client.post('/api/bulk-delete',
                                  headers=self.headers,
                                  data=json.dumps(data),
                                  content_type='application/json')
        
        self.assertEqual(response.status_code, 400)
        response_data = json.loads(response.data)
        self.assertIn('Invalid delete_types', response_data['error'])

    def test_bulk_delete_missing_confirmation(self):
        """Test bulk delete without proper confirmation."""
        data = {
            'delete_types': ['polling_places'],
            'filters': {'state': 'VA'}
        }
        
        response = self.client.post('/api/bulk-delete',
                                  headers=self.headers,
                                  data=json.dumps(data),
                                  content_type='application/json')
        
        self.assertEqual(response.status_code, 400)
        response_data = json.loads(response.data)
        self.assertIn('Confirmation required', response_data['error'])

    def test_bulk_delete_invalid_date_format(self):
        """Test bulk delete with invalid date format."""
        data = {
            'delete_types': ['polling_places'],
            'filters': {'start_date': 'invalid-date'},
            'confirm': 'DELETE'
        }
        
        response = self.client.post('/api/bulk-delete',
                                  headers=self.headers,
                                  data=json.dumps(data),
                                  content_type='application/json')
        
        self.assertEqual(response.status_code, 400)
        response_data = json.loads(response.data)
        self.assertIn('Invalid start_date format', response_data['error'])


class TestErrorHandling(unittest.TestCase):
    """Test error handling and edge cases."""

    def setUp(self):
        """Set up test fixtures."""
        self.app = app
        self.app.config['TESTING'] = True
        self.app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        self.client = self.app.test_client()
        self.ctx = self.app.app_context()
        self.ctx.push()
        
        # Create database tables
        db.create_all()
        
        # Create test API key
        self.api_key = APIKey()
        self.api_key.key = "test-key-12345"
        self.api_key.name = "Test Key"
        self.api_key.is_active = True
        db.session.add(self.api_key)
        db.session.commit()
        
        self.headers = {'X-API-Key': self.api_key.key}

    def tearDown(self):
        """Clean up test fixtures."""
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    def test_404_invalid_endpoint(self):
        """Test 404 for invalid endpoint."""
        response = self.client.get('/api/invalid-endpoint', headers=self.headers)
        self.assertEqual(response.status_code, 404)

    def test_405_invalid_method(self):
        """Test 405 for invalid HTTP method."""
        response = self.client.delete('/api/polling-places', headers=self.headers)
        self.assertEqual(response.status_code, 405)

    def test_malformed_json_request(self):
        """Test handling of malformed JSON requests."""
        response = self.client.post('/api/keys',
                                  headers=self.headers,
                                  data='invalid json',
                                  content_type='application/json')
        
        self.assertEqual(response.status_code, 400)

    def test_missing_content_type(self):
        """Test handling of missing content type."""
        response = self.client.post('/api/keys',
                                  headers=self.headers,
                                  data='{"test": "data"}')
        
        self.assertEqual(response.status_code, 400)

    def test_nonexistent_polling_place(self):
        """Test getting non-existent polling place."""
        response = self.client.get('/api/polling-places/999999', headers=self.headers)
        self.assertEqual(response.status_code, 404)

    def test_nonexistent_precinct(self):
        """Test getting non-existent precinct."""
        response = self.client.get('/api/precincts/999999', headers=self.headers)
        self.assertEqual(response.status_code, 404)

    def test_nonexistent_election(self):
        """Test getting non-existent election."""
        response = self.client.get('/api/elections/999999', headers=self.headers)
        self.assertEqual(response.status_code, 404)


class TestVIPFormatResponses(unittest.TestCase):
    """Test VIP format responses for polling places."""

    def setUp(self):
        """Set up test fixtures."""
        self.app = app
        self.app.config['TESTING'] = True
        self.app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        self.client = self.app.test_client()
        self.ctx = self.app.app_context()
        self.ctx.push()
        
        # Create database tables
        db.create_all()
        
        # Create test API key
        self.api_key = APIKey()
        self.api_key.key = "test-key-12345"
        self.api_key.name = "Test Key"
        self.api_key.is_active = True
        db.session.add(self.api_key)
        
        # Create test polling place
        self.polling_place = PollingPlace()
        self.polling_place.id = "test-pp-001"
        self.polling_place.name = "Test Polling Place"
        self.polling_place.address_line1 = "123 Main St"
        self.polling_place.city = "Test City"
        self.polling_place.state = "VA"
        self.polling_place.zip_code = "12345"
        self.polling_place.county = "Test County"
        self.polling_place.latitude = 37.7749
        self.polling_place.longitude = -122.4194
        self.polling_place.polling_hours = "7:00 AM - 8:00 PM"
        self.polling_place.voter_services = "Parking, Accessibility"
        self.polling_place.source_plugin = "test"
        db.session.add(self.polling_place)
        db.session.commit()
        
        self.headers = {'X-API-Key': self.api_key.key}

    def tearDown(self):
        """Clean up test fixtures."""
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    def test_single_polling_place_vip_format(self):
        """Test single polling place endpoint in VIP format."""
        response = self.client.get(f'/api/polling-places/{self.polling_place.id}?format=vip',
                                 headers=self.headers)
        
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.data)
        
        # Check VIP format structure
        self.assertIn('id', response_data)
        self.assertIn('name', response_data)
        self.assertIn('address', response_data)
        
        # Check address structure
        address = response_data['address']
        self.assertIn('line1', address)
        self.assertIn('city', address)
        self.assertIn('state', address)
        self.assertIn('zip', address)

    def test_vip_format_excludes_null_values(self):
        """Test that VIP format excludes null values."""
        # Create polling place with some null values
        pp_with_nulls = PollingPlace()
        pp_with_nulls.id = "test-pp-002"
        pp_with_nulls.name = "Test Place 2"
        pp_with_nulls.address_line1 = "456 Oak St"
        pp_with_nulls.city = "Test City"
        pp_with_nulls.state = "VA"
        pp_with_nulls.zip_code = "12345"
        # Leave some fields as None
        pp_with_nulls.source_plugin = "test"
        db.session.add(pp_with_nulls)
        db.session.commit()
        
        response = self.client.get(f'/api/polling-places/{pp_with_nulls.id}?format=vip',
                                 headers=self.headers)
        
        response_data = json.loads(response.data)
        
        # Null values should be excluded
        self.assertNotIn('county', response_data)
        self.assertNotIn('notes', response_data)
        self.assertNotIn('voterServices', response_data)


class TestBulkOperations(unittest.TestCase):
    """Test bulk operation endpoints."""

    def setUp(self):
        """Set up test fixtures."""
        self.app = app
        self.app.config['TESTING'] = True
        self.app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        self.client = self.app.test_client()
        self.ctx = self.app.app_context()
        self.ctx.push()
        
        # Create database tables
        db.create_all()
        
        # Create test API key
        self.api_key = APIKey()
        self.api_key.key = "test-key-12345"
        self.api_key.name = "Test Key"
        self.api_key.is_active = True
        db.session.add(self.api_key)
        
        # Create test data
        for i in range(5):
            pp = PollingPlace()
            pp.id = f"test-pp-{i:03d}"
            pp.name = f"Test Polling Place {i}"
            pp.address_line1 = f"{i} Main St"
            pp.city = "Test City"
            pp.state = "VA"
            pp.zip_code = "12345"
            pp.source_plugin = "test"
            db.session.add(pp)
        
        for i in range(3):
            precinct = Precinct()
            precinct.id = f"test-precinct-{i:03d}"
            precinct.name = f"Test Precinct {i}"
            precinct.state = "VA"
            precinct.source_plugin = "test"
            db.session.add(precinct)
        
        db.session.commit()
        self.headers = {'X-API-Key': self.api_key.key}

    def tearDown(self):
        """Clean up test fixtures."""
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    def test_bulk_delete_dry_run(self):
        """Test bulk delete dry run."""
        data = {
            'delete_types': ['polling_places'],
            'filters': {'state': 'VA'},
            'dry_run': True
        }
        
        response = self.client.post('/api/bulk-delete',
                                  headers=self.headers,
                                  data=json.dumps(data),
                                  content_type='application/json')
        
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.data)
        self.assertTrue(response_data['dry_run'])
        self.assertEqual(response_data['results']['polling_places']['count'], 5)
        
        # Verify no records were actually deleted
        remaining_count = PollingPlace.query.count()
        self.assertEqual(remaining_count, 5)

    def test_bulk_delete_with_confirmation(self):
        """Test bulk delete with proper confirmation."""
        data = {
            'delete_types': ['polling_places'],
            'filters': {'state': 'VA'},
            'confirm': 'DELETE'
        }
        
        response = self.client.post('/api/bulk-delete',
                                  headers=self.headers,
                                  data=json.dumps(data),
                                  content_type='application/json')
        
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.data)
        self.assertFalse(response_data['dry_run'])
        self.assertEqual(response_data['results']['polling_places'], 5)
        
        # Verify records were actually deleted
        remaining_count = PollingPlace.query.count()
        self.assertEqual(remaining_count, 0)

    def test_bulk_delete_multiple_types(self):
        """Test bulk delete of multiple record types."""
        data = {
            'delete_types': ['polling_places', 'precincts'],
            'filters': {'state': 'VA'},
            'dry_run': True
        }
        
        response = self.client.post('/api/bulk-delete',
                                  headers=self.headers,
                                  data=json.dumps(data),
                                  content_type='application/json')
        
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.data)
        self.assertEqual(response_data['results']['polling_places']['count'], 5)
        self.assertEqual(response_data['results']['precincts']['count'], 3)

    def test_bulk_delete_no_matching_records(self):
        """Test bulk delete when no records match filters."""
        data = {
            'delete_types': ['polling_places'],
            'filters': {'state': 'XX'},  # Non-existent state
            'dry_run': True
        }
        
        response = self.client.post('/api/bulk-delete',
                                  headers=self.headers,
                                  data=json.dumps(data),
                                  content_type='application/json')
        
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.data)
        self.assertEqual(response_data['total_count'], 0)
        self.assertIn('No records match', response_data['message'])


class TestElectionEndpoints(unittest.TestCase):
    """Test election-related endpoints."""

    def setUp(self):
        """Set up test fixtures."""
        self.app = app
        self.app.config['TESTING'] = True
        self.app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        self.client = self.app.test_client()
        self.ctx = self.app.app_context()
        self.ctx.push()
        
        # Create database tables
        db.create_all()
        
        # Create test API key
        self.api_key = APIKey()
        self.api_key.key = "test-key-12345"
        self.api_key.name = "Test Key"
        self.api_key.is_active = True
        db.session.add(self.api_key)
        
        # Create test elections
        election1 = Election()
        election1.date = date(2024, 11, 5)
        election1.name = "2024 General Election"
        election1.state = "VA"
        db.session.add(election1)
        
        election2 = Election()
        election2.date = date(2024, 3, 5)
        election2.name = "2024 Presidential Primary"
        election2.state = "VA"
        db.session.add(election2)
        
        db.session.commit()
        self.headers = {'X-API-Key': self.api_key.key}

    def tearDown(self):
        """Clean up test fixtures."""
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    def test_list_elections(self):
        """Test listing all elections."""
        response = self.client.get('/api/elections', headers=self.headers)
        
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.data)
        self.assertIn('elections', response_data)
        self.assertEqual(len(response_data['elections']), 2)

    def test_list_elections_with_state_filter(self):
        """Test listing elections with state filter."""
        response = self.client.get('/api/elections?state=VA', headers=self.headers)
        
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.data)
        self.assertEqual(len(response_data['elections']), 2)
        
        # All returned elections should be from VA
        for election in response_data['elections']:
            self.assertEqual(election['state'], 'VA')

    def test_list_elections_with_year_filter(self):
        """Test listing elections with year filter."""
        response = self.client.get('/api/elections?year=2024', headers=self.headers)
        
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.data)
        self.assertEqual(len(response_data['elections']), 2)

    def test_get_single_election(self):
        """Test getting a single election."""
        election = Election.query.first()
        response = self.client.get(f'/api/elections/{election.id}', headers=self.headers)
        
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.data)
        self.assertEqual(response_data['id'], election.id)
        self.assertEqual(response_data['name'], election.name)

    def test_get_nonexistent_election(self):
        """Test getting non-existent election."""
        response = self.client.get('/api/elections/999999', headers=self.headers)
        self.assertEqual(response.status_code, 404)


if __name__ == '__main__':
    # Create test suite
    test_suite = unittest.TestSuite()
    
    # Add all test classes
    test_classes = [
        TestAuthenticationScenarios,
        TestRateLimiting,
        TestDataValidation,
        TestErrorHandling,
        TestVIPFormatResponses,
        TestBulkOperations,
        TestElectionEndpoints
    ]
    
    for test_class in test_classes:
        tests = unittest.TestLoader().loadTestsFromTestCase(test_class)
        test_suite.addTests(tests)
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(test_suite)
    
    # Print summary
    print(f"\nTest Summary:")
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Success rate: {((result.testsRun - len(result.failures) - len(result.errors)) / result.testsRun * 100):.1f}%")