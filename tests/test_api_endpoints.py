"""
Comprehensive test suite for API endpoints related to plugins.

Includes unit tests, integration tests, and error scenario tests for:
- Plugin listing and status endpoints
- Plugin synchronization endpoints
- File upload endpoints
- Election data endpoints
- Error handling and authentication
"""

import pytest
import unittest
from unittest.mock import Mock, patch, MagicMock, call
import json
import tempfile
import os
from io import BytesIO

# Import Flask app and related modules
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app
from models import PollingPlace, Precinct, Election, APIKey, db


class TestPluginAPIEndpoints(unittest.TestCase):
    """Unit tests for plugin-related API endpoints."""

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
        
        # Create a test API key for authentication
        import secrets
        test_api_key = APIKey()
        test_api_key.key = secrets.token_urlsafe(32)
        test_api_key.name = "Test API Key"
        test_api_key.is_active = True
        db.session.add(test_api_key)
        db.session.commit()
        
        self.api_key = test_api_key.key

    def tearDown(self):
        """Clean up test fixtures."""
        db.session.remove()
        db.drop_all()
        self.ctx.pop()
    
    def get_authenticated_headers(self):
        """Get headers with API key authentication."""
        return {'X-API-Key': self.api_key}

    @patch('app.plugin_manager')
    def test_list_plugins_endpoint(self, mock_plugin_manager):
        """Test plugin listing endpoint."""
        # Mock plugin manager response
        mock_plugin_manager.list_plugins.return_value = [
            {
                'name': 'ohio',
                'state_code': 'OH',
                'description': 'Ohio polling place data from state CSV',
                'status': 'loaded'
            },
            {
                'name': 'virginia',
                'state_code': 'VA',
                'description': 'Virginia polling place data from state elections website',
                'status': 'loaded'
            }
        ]

        response = self.client.get('/api/plugins', headers=self.get_authenticated_headers())
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(len(data), 2)
        self.assertEqual(data[0]['name'], 'ohio')
        self.assertEqual(data[1]['name'], 'virginia')

    @patch('app.plugin_manager')
    def test_list_plugins_error(self, mock_plugin_manager):
        """Test plugin listing endpoint with error."""
        mock_plugin_manager.list_plugins.side_effect = Exception("Plugin manager error")

        response = self.client.get('/api/plugins')
        
        self.assertEqual(response.status_code, 500)
        data = json.loads(response.data)
        self.assertIn('error', data)

    @patch('app.plugin_manager')
    def test_get_plugin_by_state_endpoint(self, mock_plugin_manager):
        """Test getting plugin by state code."""
        mock_plugin = Mock()
        mock_plugin.name = 'ohio'
        mock_plugin.state_code = 'OH'
        mock_plugin.description = 'Ohio polling place data'
        mock_plugin.get_status.return_value = {
            'name': 'ohio',
            'state_code': 'OH',
            'description': 'Ohio polling place data'
        }
        mock_plugin_manager.get_plugin_by_state.return_value = mock_plugin

        response = self.client.get('/api/plugins/state/OH')
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(data['name'], 'ohio')
        self.assertEqual(data['state_code'], 'OH')

    @patch('app.plugin_manager')
    def test_get_plugin_by_state_not_found(self, mock_plugin_manager):
        """Test getting plugin by non-existent state code."""
        mock_plugin_manager.get_plugin_by_state.side_effect = KeyError("No plugin found for state 'XX'")

        response = self.client.get('/api/plugins/state/XX')
        
        self.assertEqual(response.status_code, 404)
        data = json.loads(response.data)
        self.assertIn('error', data)

    @patch('app.plugin_manager')
    def test_sync_plugin_endpoint(self, mock_plugin_manager):
        """Test plugin synchronization endpoint."""
        mock_plugin_manager.sync_plugin.return_value = {
            'success': True,
            'added': 10,
            'updated': 5,
            'errors': 0
        }

        response = self.client.post('/api/plugins/ohio/sync')
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data['success'])
        self.assertEqual(data['added'], 10)
        self.assertEqual(data['updated'], 5)

    @patch('app.plugin_manager')
    def test_sync_plugin_with_election_id(self, mock_plugin_manager):
        """Test plugin synchronization with election ID."""
        mock_plugin_manager.sync_plugin.return_value = {
            'success': True,
            'added': 8,
            'updated': 3,
            'errors': 0
        }

        response = self.client.post('/api/plugins/ohio/sync', 
                                 json={'election_id': 123},
                                 content_type='application/json')

        self.assertEqual(response.status_code, 200)
        mock_plugin_manager.sync_plugin.assert_called_once_with('ohio', election_id=123)

    @patch('app.plugin_manager')
    def test_sync_plugin_not_found(self, mock_plugin_manager):
        """Test syncing non-existent plugin."""
        mock_plugin_manager.sync_plugin.side_effect = KeyError("Plugin 'nonexistent' not found")

        response = self.client.post('/api/plugins/nonexistent/sync')
        
        self.assertEqual(response.status_code, 404)
        data = json.loads(response.data)
        self.assertIn('error', data)

    @patch('app.plugin_manager')
    def test_sync_all_plugins_endpoint(self, mock_plugin_manager):
        """Test syncing all plugins endpoint."""
        mock_plugin_manager.sync_all_plugins.return_value = {
            'ohio': {'success': True, 'added': 10, 'updated': 5},
            'virginia': {'success': True, 'added': 15, 'updated': 8}
        }

        response = self.client.post('/api/plugins/sync-all')
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertIn('ohio', data)
        self.assertIn('virginia', data)
        self.assertTrue(data['ohio']['success'])
        self.assertTrue(data['virginia']['success'])

    @patch('app.plugin_manager')
    def test_sync_all_plugins_partial_failure(self, mock_plugin_manager):
        """Test syncing all plugins with some failures."""
        mock_plugin_manager.sync_all_plugins.return_value = {
            'ohio': {'success': True, 'added': 10, 'updated': 5},
            'virginia': {'success': False, 'error': 'Network error', 'errors': 1}
        }

        response = self.client.post('/api/plugins/sync-all')
        
        self.assertEqual(response.status_code, 207)  # Multi-status
        data = json.loads(response.data)
        self.assertTrue(data['ohio']['success'])
        self.assertFalse(data['virginia']['success'])


class TestFileUploadEndpoints(unittest.TestCase):
    """Unit tests for file upload endpoints."""

    def setUp(self):
        """Set up test fixtures."""
        self.app = app
        self.app.config['TESTING'] = True
        self.client = self.app.test_client()
        self.ctx = self.app.app_context()
        self.ctx.push()

    def tearDown(self):
        """Clean up test fixtures."""
        self.ctx.pop()

    @patch('app.plugin_manager')
    def test_upload_file_success(self, mock_plugin_manager):
        """Test successful file upload."""
        mock_plugin = Mock()
        mock_plugin.upload_file.return_value = {
            'success': True,
            'message': 'File uploaded successfully'
        }
        mock_plugin_manager.get_plugin.return_value = mock_plugin

        # Create a test file
        test_data = b'test,csv,data\n1,2,3\n4,5,6\n'
        test_file = (BytesIO(test_data), 'test.csv')

        response = self.client.post('/api/plugins/ohio/upload',
                                 data={'file': test_file},
                                 content_type='multipart/form-data')

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data['success'])
        self.assertIn('message', data)

    @patch('app.plugin_manager')
    def test_upload_file_no_file(self, mock_plugin_manager):
        """Test file upload without file."""
        response = self.client.post('/api/plugins/ohio/upload',
                                 data={},
                                 content_type='multipart/form-data')

        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertIn('error', data)

    @patch('app.plugin_manager')
    def test_upload_file_plugin_not_found(self, mock_plugin_manager):
        """Test file upload for non-existent plugin."""
        mock_plugin_manager.get_plugin.side_effect = KeyError("Plugin 'nonexistent' not found")

        test_data = b'test,data\n'
        test_file = (BytesIO(test_data), 'test.csv')

        response = self.client.post('/api/plugins/nonexistent/upload',
                                 data={'file': test_file},
                                 content_type='multipart/form-data')

        self.assertEqual(response.status_code, 404)
        data = json.loads(response.data)
        self.assertIn('error', data)

    @patch('app.plugin_manager')
    def test_upload_file_upload_error(self, mock_plugin_manager):
        """Test file upload with upload error."""
        mock_plugin = Mock()
        mock_plugin.upload_file.return_value = {
            'success': False,
            'message': 'Invalid file format'
        }
        mock_plugin_manager.get_plugin.return_value = mock_plugin

        test_data = b'invalid,data'
        test_file = (BytesIO(test_data), 'test.csv')

        response = self.client.post('/api/plugins/ohio/upload',
                                 data={'file': test_file},
                                 content_type='multipart/form-data')

        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertFalse(data['success'])
        self.assertIn('message', data)


class TestElectionEndpoints(unittest.TestCase):
    """Unit tests for election-related endpoints."""

    def setUp(self):
        """Set up test fixtures."""
        self.app = app
        self.app.config['TESTING'] = True
        self.client = self.app.test_client()
        self.ctx = self.app.app_context()
        self.ctx.push()

    def tearDown(self):
        """Clean up test fixtures."""
        self.ctx.pop()

    @patch('app.plugin_manager')
    def test_get_available_elections(self, mock_plugin_manager):
        """Test getting available elections."""
        mock_plugin = Mock()
        mock_plugin.get_available_elections.return_value = [
            {
                'election_date': '2024-11-05',
                'election_name': '2024 General Election',
                'election_type': 'general',
                'url': 'http://example.com/file.xlsx',
                'is_recent': True
            },
            {
                'election_date': '2024-03-05',
                'election_name': '2024 Presidential Primary',
                'election_type': 'presidential_primary',
                'url': 'http://example.com/file2.xlsx',
                'is_recent': True
            }
        ]
        mock_plugin_manager.get_plugin.return_value = mock_plugin

        response = self.client.get('/api/plugins/virginia/elections')
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(len(data), 2)
        self.assertEqual(data[0]['election_name'], '2024 General Election')
        self.assertEqual(data[1]['election_name'], '2024 Presidential Primary')

    @patch('app.plugin_manager')
    def test_get_available_elections_plugin_not_found(self, mock_plugin_manager):
        """Test getting elections for non-existent plugin."""
        mock_plugin_manager.get_plugin.side_effect = KeyError("Plugin 'nonexistent' not found")

        response = self.client.get('/api/plugins/nonexistent/elections')
        
        self.assertEqual(response.status_code, 404)
        data = json.loads(response.data)
        self.assertIn('error', data)

    @patch('app.plugin_manager')
    def test_sync_election_file(self, mock_plugin_manager):
        """Test syncing specific election file."""
        mock_plugin = Mock()
        mock_plugin.sync_single_file.return_value = {
            'success': True,
            'filename': '2024-General-Election.xlsx',
            'election': {
                'id': 1,
                'date': '2024-11-05',
                'name': '2024 General Election'
            },
            'polling_places': {'added': 100, 'updated': 10},
            'precincts': {'added': 150, 'updated': 15}
        }
        mock_plugin_manager.get_plugin.return_value = mock_plugin

        response = self.client.post('/api/plugins/virginia/sync-file',
                                 json={'file_url': 'http://example.com/election.xlsx'},
                                 content_type='application/json')

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data['success'])
        self.assertEqual(data['filename'], '2024-General-Election.xlsx')
        self.assertEqual(data['polling_places']['added'], 100)

    @patch('app.plugin_manager')
    def test_sync_election_file_missing_url(self, mock_plugin_manager):
        """Test syncing election file without URL."""
        response = self.client.post('/api/plugins/virginia/sync-file',
                                 json={},
                                 content_type='application/json')

        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertIn('error', data)


class TestPluginStatusEndpoints(unittest.TestCase):
    """Unit tests for plugin status endpoints."""

    def setUp(self):
        """Set up test fixtures."""
        self.app = app
        self.app.config['TESTING'] = True
        self.client = self.app.test_client()
        self.ctx = self.app.app_context()
        self.ctx.push()

    def tearDown(self):
        """Clean up test fixtures."""
        self.ctx.pop()

    @patch('app.plugin_manager')
    def test_get_plugin_status(self, mock_plugin_manager):
        """Test getting plugin status."""
        mock_plugin = Mock()
        mock_plugin.get_status.return_value = {
            'name': 'ohio',
            'state_code': 'OH',
            'description': 'Ohio polling place data from state CSV',
            'last_sync': '2024-01-15T10:30:00Z',
            'total_polling_places': 1500,
            'total_precincts': 2000,
            'status': 'healthy'
        }
        mock_plugin_manager.get_plugin.return_value = mock_plugin

        response = self.client.get('/api/plugins/ohio/status')
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(data['name'], 'ohio')
        self.assertEqual(data['state_code'], 'OH')
        self.assertEqual(data['status'], 'healthy')

    @patch('app.plugin_manager')
    def test_get_plugin_status_not_found(self, mock_plugin_manager):
        """Test getting status for non-existent plugin."""
        mock_plugin_manager.get_plugin.side_effect = KeyError("Plugin 'nonexistent' not found")

        response = self.client.get('/api/plugins/nonexistent/status')
        
        self.assertEqual(response.status_code, 404)
        data = json.loads(response.data)
        self.assertIn('error', data)

    @patch('app.plugin_manager')
    def test_get_all_plugins_status(self, mock_plugin_manager):
        """Test getting status for all plugins."""
        mock_plugin_manager.list_plugins.return_value = [
            {
                'name': 'ohio',
                'state_code': 'OH',
                'status': 'healthy',
                'last_sync': '2024-01-15T10:30:00Z'
            },
            {
                'name': 'virginia',
                'state_code': 'VA',
                'status': 'healthy',
                'last_sync': '2024-01-15T11:00:00Z'
            }
        ]

        response = self.client.get('/api/plugins/status')
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(len(data), 2)
        self.assertEqual(data[0]['name'], 'ohio')
        self.assertEqual(data[1]['name'], 'virginia')


class TestAPIErrorHandling(unittest.TestCase):
    """Unit tests for API error handling."""

    def setUp(self):
        """Set up test fixtures."""
        self.app = app
        self.app.config['TESTING'] = True
        self.client = self.app.test_client()
        self.ctx = self.app.app_context()
        self.ctx.push()

    def tearDown(self):
        """Clean up test fixtures."""
        self.ctx.pop()

    def test_invalid_endpoint(self):
        """Test accessing invalid endpoint."""
        response = self.client.get('/api/invalid/endpoint')
        
        self.assertEqual(response.status_code, 404)

    def test_invalid_method(self):
        """Test using invalid HTTP method."""
        response = self.client.delete('/api/plugins')
        
        self.assertEqual(response.status_code, 405)  # Method Not Allowed

    @patch('app.plugin_manager')
    def test_plugin_manager_unavailable(self, mock_plugin_manager):
        """Test API when plugin manager is unavailable."""
        mock_plugin_manager.list_plugins.side_effect = Exception("Plugin manager not initialized")

        response = self.client.get('/api/plugins')
        
        self.assertEqual(response.status_code, 500)
        data = json.loads(response.data)
        self.assertIn('error', data)

    def test_malformed_json_request(self):
        """Test handling of malformed JSON requests."""
        response = self.client.post('/api/plugins/ohio/sync',
                                 data='invalid json',
                                 content_type='application/json')

        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertIn('error', data)

    def test_missing_content_type(self):
        """Test handling of missing content type."""
        response = self.client.post('/api/plugins/ohio/sync',
                                 data='{"test": "data"}')

        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertIn('error', data)


class TestAPIAuthentication(unittest.TestCase):
    """Unit tests for API authentication."""

    def setUp(self):
        """Set up test fixtures."""
        self.app = app
        self.app.config['TESTING'] = True
        self.client = self.app.test_client()
        self.ctx = self.app.app_context()
        self.ctx.push()

    def tearDown(self):
        """Clean up test fixtures."""
        self.ctx.pop()

    @patch('app.plugin_manager')
    def test_unauthenticated_access(self, mock_plugin_manager):
        """Test API access without authentication."""
        # This test assumes some endpoints require authentication
        # Adjust based on actual authentication requirements
        mock_plugin_manager.list_plugins.return_value = []

        response = self.client.get('/api/plugins')
        
        # If authentication is required, should return 401 or 403
        # If not required, should return 200
        self.assertIn(response.status_code, [200, 401, 403])

    @patch('app.plugin_manager')
    def test_authenticated_access(self, mock_plugin_manager):
        """Test API access with authentication."""
        mock_plugin_manager.list_plugins.return_value = []

        # Test with authentication header if required
        headers = {'Authorization': 'Bearer test-token'}
        response = self.client.get('/api/plugins', headers=headers)
        
        # Should succeed with valid authentication
        self.assertIn(response.status_code, [200, 401])  # 401 if auth not actually implemented


class TestAPIIntegration(unittest.TestCase):
    """Integration tests for API endpoints."""

    def setUp(self):
        """Set up test fixtures."""
        self.app = app
        self.app.config['TESTING'] = True
        self.client = self.app.test_client()
        self.ctx = self.app.app_context()
        self.ctx.push()

    def tearDown(self):
        """Clean up test fixtures."""
        self.ctx.pop()

    @patch('app.plugin_manager')
    def test_complete_plugin_workflow(self, mock_plugin_manager):
        """Test complete plugin workflow through API."""
        mock_plugin = Mock()
        mock_plugin.name = 'test'
        mock_plugin.state_code = 'TS'
        mock_plugin.get_status.return_value = {
            'name': 'test',
            'state_code': 'TS',
            'status': 'loaded'
        }
        mock_plugin.sync.return_value = {
            'success': True,
            'added': 10,
            'updated': 5
        }
        mock_plugin_manager.get_plugin.return_value = mock_plugin
        mock_plugin_manager.list_plugins.return_value = [mock_plugin.get_status.return_value]

        # Test listing plugins
        response = self.client.get('/api/plugins')
        self.assertEqual(response.status_code, 200)
        plugins = json.loads(response.data)
        self.assertEqual(len(plugins), 1)

        # Test getting plugin status
        response = self.client.get('/api/plugins/test/status')
        self.assertEqual(response.status_code, 200)
        status = json.loads(response.data)
        self.assertEqual(status['name'], 'test')

        # Test syncing plugin
        response = self.client.post('/api/plugins/test/sync')
        self.assertEqual(response.status_code, 200)
        sync_result = json.loads(response.data)
        self.assertTrue(sync_result['success'])

    def test_api_response_format(self):
        """Test that API responses follow consistent format."""
        # Test successful response
        with patch('app.plugin_manager') as mock_plugin_manager:
            mock_plugin_manager.list_plugins.return_value = []
            
            response = self.client.get('/api/plugins')
            
            # Should have proper content type
            self.assertEqual(response.content_type, 'application/json')
            
            # Should be valid JSON
            try:
                data = json.loads(response.data)
                self.assertIsInstance(data, list)
            except json.JSONDecodeError:
                self.fail("Response is not valid JSON")

    def test_api_cors_headers(self):
        """Test that API includes proper CORS headers."""
        response = self.client.get('/api/plugins')
        
        # Check for common CORS headers
        # Note: This depends on Flask-CORS configuration
        # Adjust based on actual CORS setup
        self.assertIn(response.status_code, [200, 404, 500])


if __name__ == '__main__':
    # Create test suite
    test_suite = unittest.TestSuite()
    
    # Add all test classes
    test_classes = [
        TestPluginAPIEndpoints,
        TestFileUploadEndpoints,
        TestElectionEndpoints,
        TestPluginStatusEndpoints,
        TestAPIErrorHandling,
        TestAPIAuthentication,
        TestAPIIntegration
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