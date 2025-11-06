"""
Comprehensive test suite for BigQuery plugin functionality.

Includes unit tests, integration tests, and error scenario tests for:
- BigQuery client connection and authentication
- Query execution and result processing
- Voter data retrieval by state
- Error handling for authentication and query failures
- Configuration and environment variable handling
"""

import pytest
import unittest
from unittest.mock import Mock, patch, MagicMock, call
import os

# Try to import Google Cloud BigQuery, skip tests if not available
try:
    from google.cloud import bigquery
    BIGQUERY_AVAILABLE = True
except ImportError:
    BIGQUERY_AVAILABLE = False
    bigquery = None

# Import the plugin and models
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from plugins.bigquery_plugin import BigQueryPlugin


@pytest.mark.skipif(not BIGQUERY_AVAILABLE, reason="Google Cloud BigQuery not available")
@pytest.mark.skipif(not BIGQUERY_AVAILABLE, reason="Google Cloud BigQuery not available")
class TestBigQueryConnection(unittest.TestCase):
    """Unit tests for BigQuery plugin connection functionality."""

    def setUp(self):
        """Set up test fixtures with mock app and database."""
        self.mock_app = Mock()
        self.mock_app.logger = Mock()
        self.mock_db = Mock()
        self.plugin = BigQueryPlugin(self.mock_app, self.mock_db)

    @patch('plugins.bigquery_plugin.bigquery.Client')
    def test_connect_to_bigquery_success(self, mock_client):
        """Test successful BigQuery client connection."""
        mock_client_instance = Mock()
        mock_client.return_value = mock_client_instance

        result = self.plugin.connect_to_bigquery()

        self.assertEqual(result, mock_client_instance)
        mock_client.assert_called_once()
        self.assertEqual(self.plugin.client, mock_client_instance)

    @patch('plugins.bigquery_plugin.bigquery.Client')
    def test_connect_to_bigquery_cached(self, mock_client):
        """Test that BigQuery client is cached after first connection."""
        mock_client_instance = Mock()
        mock_client.return_value = mock_client_instance

        # First call should create client
        result1 = self.plugin.connect_to_bigquery()
        # Second call should return cached client
        result2 = self.plugin.connect_to_bigquery()

        self.assertEqual(result1, mock_client_instance)
        self.assertEqual(result2, mock_client_instance)
        # Should only call Client() once
        mock_client.assert_called_once()

    @patch('plugins.bigquery_plugin.bigquery.Client')
    def test_connect_to_bigquery_authentication_error(self, mock_client):
        """Test BigQuery connection with authentication error."""
        from google.auth.exceptions import DefaultCredentialsError
        mock_client.side_effect = DefaultCredentialsError("Could not automatically determine credentials")

        with self.assertRaises(DefaultCredentialsError):
            self.plugin.connect_to_bigquery()

    def test_plugin_properties(self):
        """Test plugin property values."""
        self.assertEqual(self.plugin.name, 'bigquery')
        self.assertEqual(self.plugin.state_code, 'ALL')
        self.assertEqual(self.plugin.description, 'BigQuery plugin for querying voter data by state')


@pytest.mark.skipif(not BIGQUERY_AVAILABLE, reason="Google Cloud BigQuery not available")
class TestBigQueryQueryExecution(unittest.TestCase):
    """Unit tests for BigQuery query execution functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_app = Mock()
        self.mock_app.logger = Mock()
        self.mock_db = Mock()
        self.plugin = BigQueryPlugin(self.mock_app, self.mock_db)

    @patch('plugins.bigquery_plugin.os.getenv')
    def test_fetch_polling_places_default_query(self, mock_getenv):
        """Test query execution with default query template."""
        mock_getenv.return_value = None  # Use default query
        
        # Mock BigQuery client and query job
        mock_client = Mock()
        mock_query_job = Mock()
        mock_row = Mock()
        mock_row.precinctname = 'Test Precinct'
        mock_row.precinctcode = '001'
        mock_row.registered = 1500
        
        mock_query_job.__iter__ = Mock(return_value=iter([mock_row]))
        mock_client.query.return_value = mock_query_job
        
        with patch.object(self.plugin, 'connect_to_bigquery', return_value=mock_client):
            result = self.plugin.fetch_polling_places('OH')

        expected_key = 'Test Precinct (001)'
        self.assertEqual(result, {expected_key: 1500})
        mock_client.query.assert_called_once()
        
        # Verify the query contains the state code
        call_args = mock_client.query.call_args[0][0]
        self.assertIn('OH', call_args)

    @patch('plugins.bigquery_plugin.os.getenv')
    def test_fetch_polling_places_custom_query(self, mock_getenv):
        """Test query execution with custom query template."""
        custom_query = """
        SELECT
            custom_precinct_name as precinctname,
            custom_precinct_code as precinctcode,
            COUNT(*) as registered
        FROM custom_table
        WHERE state = '{state_code}'
        """
        mock_getenv.return_value = custom_query
        
        # Mock BigQuery client and query job
        mock_client = Mock()
        mock_query_job = Mock()
        mock_row = Mock()
        mock_row.precinctname = 'Custom Precinct'
        mock_row.precinctcode = 'XYZ'
        mock_row.registered = 2000
        
        mock_query_job.__iter__ = Mock(return_value=iter([mock_row]))
        mock_client.query.return_value = mock_query_job
        
        with patch.object(self.plugin, 'connect_to_bigquery', return_value=mock_client):
            result = self.plugin.fetch_polling_places('CA')

        expected_key = 'Custom Precinct (XYZ)'
        self.assertEqual(result, {expected_key: 2000})
        
        # Verify the custom query was used with state code substitution
        call_args = mock_client.query.call_args[0][0]
        self.assertIn('CA', call_args)
        self.assertIn('custom_table', call_args)

    @patch('plugins.bigquery_plugin.os.getenv')
    def test_fetch_polling_places_multiple_rows(self, mock_getenv):
        """Test query execution returning multiple rows."""
        mock_getenv.return_value = None  # Use default query
        
        # Mock multiple rows
        mock_rows = [
            Mock(precinctname='Precinct A', precinctcode='001', registered=1000),
            Mock(precinctname='Precinct B', precinctcode='002', registered=1500),
            Mock(precinctname='Precinct C', precinctcode='003', registered=2000)
        ]
        
        mock_client = Mock()
        mock_query_job = Mock()
        mock_query_job.__iter__ = Mock(return_value=iter(mock_rows))
        mock_client.query.return_value = mock_query_job
        
        with patch.object(self.plugin, 'connect_to_bigquery', return_value=mock_client):
            result = self.plugin.fetch_polling_places('OH')

        expected = {
            'Precinct A (001)': 1000,
            'Precinct B (002)': 1500,
            'Precinct C (003)': 2000
        }
        self.assertEqual(result, expected)

    @patch('plugins.bigquery_plugin.os.getenv')
    def test_fetch_polling_places_default_state(self, mock_getenv):
        """Test query execution with default state code."""
        mock_getenv.return_value = None  # Use default query
        
        mock_client = Mock()
        mock_query_job = Mock()
        mock_query_job.__iter__ = Mock(return_value=iter([]))
        mock_client.query.return_value = mock_query_job
        
        with patch.object(self.plugin, 'connect_to_bigquery', return_value=mock_client):
            self.plugin.fetch_polling_places()  # No state specified

        # Should use default state 'OH'
        call_args = mock_client.query.call_args[0][0]
        self.assertIn('OH', call_args)

    def test_get_voter_data_by_state(self):
        """Test public method for getting voter data by state."""
        mock_result = {'Test Precinct (001)': 1500}
        
        with patch.object(self.plugin, 'fetch_polling_places', return_value=mock_result) as mock_fetch:
            result = self.plugin.get_voter_data_by_state('OH')

        self.assertEqual(result, mock_result)
        mock_fetch.assert_called_once_with('OH')


@pytest.mark.skipif(not BIGQUERY_AVAILABLE, reason="Google Cloud BigQuery not available")
class TestBigQueryErrorScenarios(unittest.TestCase):
    """Error scenario tests for BigQuery plugin."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_app = Mock()
        self.mock_app.logger = Mock()
        self.mock_db = Mock()
        self.plugin = BigQueryPlugin(self.mock_app, self.mock_db)

    @patch('plugins.bigquery_plugin.os.getenv')
    def test_query_execution_error(self, mock_getenv):
        """Test handling of BigQuery query execution errors."""
        mock_getenv.return_value = None  # Use default query
        
        from google.cloud import exceptions
        mock_client = Mock()
        mock_client.query.side_effect = exceptions.GoogleCloudError("Query failed")
        
        with patch.object(self.plugin, 'connect_to_bigquery', return_value=mock_client):
            with self.assertRaises(Exception) as context:
                self.plugin.fetch_polling_places('OH')

        self.assertIn("Failed to query BigQuery", str(context.exception))
        self.mock_app.logger.error.assert_called()

    @patch('plugins.bigquery_plugin.os.getenv')
    def test_connection_error(self, mock_getenv):
        """Test handling of BigQuery connection errors."""
        mock_getenv.return_value = None  # Use default query
        
        from google.auth.exceptions import DefaultCredentialsError
        with patch.object(self.plugin, 'connect_to_bigquery', side_effect=DefaultCredentialsError("Auth failed")):
            with self.assertRaises(Exception) as context:
                self.plugin.fetch_polling_places('OH')

        self.assertIn("Failed to query BigQuery", str(context.exception))

    @patch('plugins.bigquery_plugin.os.getenv')
    def test_empty_query_results(self, mock_getenv):
        """Test handling of empty query results."""
        mock_getenv.return_value = None  # Use default query
        
        mock_client = Mock()
        mock_query_job = Mock()
        mock_query_job.__iter__ = Mock(return_value=iter([]))
        mock_client.query.return_value = mock_query_job
        
        with patch.object(self.plugin, 'connect_to_bigquery', return_value=mock_client):
            result = self.plugin.fetch_polling_places('OH')

        self.assertEqual(result, {})
        self.mock_app.logger.info.assert_called_with("Retrieved 0 precincts for state OH")

    @patch('plugins.bigquery_plugin.os.getenv')
    def test_malformed_query_results(self, mock_getenv):
        """Test handling of malformed query results."""
        mock_getenv.return_value = None  # Use default query
        
        # Mock row with missing attributes
        mock_row = Mock()
        del mock_row.precinctname  # Remove required attribute
        mock_row.precinctcode = '001'
        mock_row.registered = 1500
        
        mock_client = Mock()
        mock_query_job = Mock()
        mock_query_job.__iter__ = Mock(return_value=iter([mock_row]))
        mock_client.query.return_value = mock_query_job
        
        with patch.object(self.plugin, 'connect_to_bigquery', return_value=mock_client):
            with self.assertRaises(Exception) as context:
                self.plugin.fetch_polling_places('OH')
            self.assertIn("Failed to query BigQuery", str(context.exception))

    @patch('plugins.bigquery_plugin.os.getenv')
    def test_invalid_state_code(self, mock_getenv):
        """Test handling of invalid state codes."""
        mock_getenv.return_value = None  # Use default query
        
        mock_client = Mock()
        mock_query_job = Mock()
        mock_query_job.__iter__ = Mock(return_value=iter([]))
        mock_client.query.return_value = mock_query_job
        
        with patch.object(self.plugin, 'connect_to_bigquery', return_value=mock_client):
            # Should still attempt query with invalid state
            result = self.plugin.fetch_polling_places('XX')

        self.assertEqual(result, {})
        # Verify the invalid state was used in query
        call_args = mock_client.query.call_args[0][0]
        self.assertIn('XX', call_args)

    def test_large_result_set(self):
        """Test handling of large result sets."""
        # Mock many rows to test performance
        mock_rows = []
        for i in range(1000):
            mock_row = Mock()
            mock_row.precinctname = f'Precinct {i}'
            mock_row.precinctcode = f'{i:03d}'
            mock_row.registered = 1000 + i
            mock_rows.append(mock_row)

        mock_client = Mock()
        mock_query_job = Mock()
        mock_query_job.__iter__ = Mock(return_value=iter(mock_rows))
        mock_client.query.return_value = mock_query_job
        
        with patch.object(self.plugin, 'connect_to_bigquery', return_value=mock_client):
            result = self.plugin.fetch_polling_places('OH')

        self.assertEqual(len(result), 1000)
        self.assertEqual(result['Precinct 0 (000)'], 1000)
        self.assertEqual(result['Precinct 999 (999)'], 1999)


@pytest.mark.skipif(not BIGQUERY_AVAILABLE, reason="Google Cloud BigQuery not available")
class TestBigQueryConfiguration(unittest.TestCase):
    """Tests for BigQuery plugin configuration."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_app = Mock()
        self.mock_app.logger = Mock()
        self.mock_db = Mock()
        self.plugin = BigQueryPlugin(self.mock_app, self.mock_db)

    @patch('plugins.bigquery_plugin.os.getenv')
    def test_environment_variable_configuration(self, mock_getenv):
        """Test configuration via environment variables."""
        custom_query = """
        SELECT custom_fields FROM custom_table WHERE state = '{state_code}'
        """
        mock_getenv.return_value = custom_query
        
        mock_client = Mock()
        mock_query_job = Mock()
        mock_query_job.__iter__ = Mock(return_value=iter([]))
        mock_client.query.return_value = mock_query_job
        
        with patch.object(self.plugin, 'connect_to_bigquery', return_value=mock_client):
            self.plugin.fetch_polling_places('OH')

        # Verify custom query was used
        call_args = mock_client.query.call_args[0][0]
        self.assertIn('custom_fields', call_args)
        self.assertIn('custom_table', call_args)

    @patch('plugins.bigquery_plugin.os.getenv')
    def test_missing_environment_variable(self, mock_getenv):
        """Test behavior when environment variable is missing."""
        mock_getenv.return_value = None  # Environment variable not set
        
        mock_client = Mock()
        mock_query_job = Mock()
        mock_query_job.__iter__ = Mock(return_value=iter([]))
        mock_client.query.return_value = mock_query_job
        
        with patch.object(self.plugin, 'connect_to_bigquery', return_value=mock_client):
            self.plugin.fetch_polling_places('OH')

        # Should use default query
        call_args = mock_client.query.call_args[0][0]
        self.assertIn('prod-sv-oh-dd7a76f2.catalist_OH.Person', call_args)

    def test_query_template_substitution(self):
        """Test that state code is properly substituted in query template."""
        test_cases = [
            ('OH', 'OH'),
            ('CA', 'CA'),
            ('NY', 'NY'),
            ('TX', 'TX')
        ]

        for state_code, expected_substitution in test_cases:
            with self.subTest(state=state_code):
                mock_client = Mock()
                mock_query_job = Mock()
                mock_query_job.__iter__ = Mock(return_value=iter([]))
                mock_client.query.return_value = mock_query_job
                
                with patch.object(self.plugin, 'connect_to_bigquery', return_value=mock_client):
                    self.plugin.fetch_polling_places(state_code)

                # Verify state code was substituted
                call_args = mock_client.query.call_args[0][0]
                self.assertIn(expected_substitution, call_args)


@pytest.mark.skipif(not BIGQUERY_AVAILABLE, reason="Google Cloud BigQuery not available")
class TestBigQueryIntegration(unittest.TestCase):
    """Integration tests for BigQuery plugin workflow."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_app = Mock()
        self.mock_app.logger = Mock()
        self.mock_db = Mock()
        self.plugin = BigQueryPlugin(self.mock_app, self.mock_db)

    def test_complete_workflow(self):
        """Test complete workflow from connection to data retrieval."""
        # Mock realistic BigQuery response
        mock_rows = [
            Mock(precinctname='Franklin County Precinct 1A', precinctcode='001A', registered=1250),
            Mock(precinctname='Franklin County Precinct 2B', precinctcode='002B', registered=1450),
            Mock(precinctname='Cuyahoga County Precinct 10C', precinctcode='010C', registered=2100)
        ]

        mock_client = Mock()
        mock_query_job = Mock()
        mock_query_job.__iter__ = Mock(return_value=iter(mock_rows))
        mock_client.query.return_value = mock_query_job
        
        with patch.object(self.plugin, 'connect_to_bigquery', return_value=mock_client):
            result = self.plugin.fetch_polling_places('OH')

        expected = {
            'Franklin County Precinct 1A (001A)': 1250,
            'Franklin County Precinct 2B (002B)': 1450,
            'Cuyahoga County Precinct 10C (010C)': 2100
        }
        self.assertEqual(result, expected)
        
        # Verify logging
        self.mock_app.logger.info.assert_called_with("Retrieved 3 precincts for state OH")

    def test_multiple_state_queries(self):
        """Test querying multiple states."""
        states = ['OH', 'CA', 'TX']
        results = {}
        
        mock_client = Mock()
        
        for state in states:
            # Mock different results for each state
            mock_rows = [Mock(precinctname=f'{state} Precinct', precinctcode='001', registered=1000)]
            mock_query_job = Mock()
            mock_query_job.__iter__ = Mock(return_value=iter(mock_rows))
            mock_client.query.return_value = mock_query_job
            
            with patch.object(self.plugin, 'connect_to_bigquery', return_value=mock_client):
                results[state] = self.plugin.fetch_polling_places(state)

        # Verify each state was queried correctly
        self.assertEqual(len(results), 3)
        for state in states:
            self.assertIn(f'{state} Precinct (001)', results[state])
            self.assertEqual(results[state][f'{state} Precinct (001)'], 1000)

    def test_concurrent_queries(self):
        """Test handling of concurrent queries."""
        import threading
        import time

        results = {}
        errors = []

        def query_state(state):
            try:
                mock_rows = [Mock(precinctname=f'{state} Precinct', precinctcode='001', registered=1000)]
                mock_client = Mock()
                mock_query_job = Mock()
                mock_query_job.__iter__ = Mock(return_value=iter(mock_rows))
                mock_client.query.return_value = mock_query_job
                
                with patch.object(self.plugin, 'connect_to_bigquery', return_value=mock_client):
                    results[state] = self.plugin.fetch_polling_places(state)
            except Exception as e:
                errors.append(e)

        # Create multiple threads for concurrent queries
        threads = []
        states = ['OH', 'CA', 'TX', 'NY', 'FL']
        
        for state in states:
            thread = threading.Thread(target=query_state, args=(state,))
            threads.append(thread)
            thread.start()

        # Wait for all threads to complete
        for thread in threads:
            thread.join()

        # Verify all queries completed successfully
        self.assertEqual(len(errors), 0)
        self.assertEqual(len(results), len(states))
        for state in states:
            self.assertIn(state, results)


if __name__ == '__main__':
    # Create test suite
    test_suite = unittest.TestSuite()
    
    # Add all test classes
    test_classes = [
        TestBigQueryConnection,
        TestBigQueryQueryExecution,
        TestBigQueryErrorScenarios,
        TestBigQueryConfiguration,
        TestBigQueryIntegration
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