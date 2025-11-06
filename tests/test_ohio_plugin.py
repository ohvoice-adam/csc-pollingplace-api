"""
Comprehensive test suite for Ohio plugin functionality.

Includes unit tests, integration tests, and data validation tests for:
- CSV data parsing and validation
- Polling place and precinct data generation
- File upload functionality
- Geocoding integration
- Error scenarios and edge cases
"""

import pytest
import unittest
from unittest.mock import Mock, patch, MagicMock, call, mock_open
import os
import csv
import tempfile
import shutil
import pandas as pd
import requests

# Import the plugin and models
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from plugins.ohio import OhioPlugin
from models import PollingPlace, Precinct


class TestOhioCSVParsing(unittest.TestCase):
    """Unit tests for Ohio plugin's CSV parsing functionality."""

    def setUp(self):
        """Set up test fixtures with mock app and database."""
        self.mock_app = Mock()
        self.mock_app.logger = Mock()
        self.mock_db = Mock()
        self.mock_db.session = Mock()
        self.plugin = OhioPlugin(self.mock_app, self.mock_db)

    def test_read_csv_success(self):
        """Test successful CSV file reading."""
        # Create mock CSV data
        mock_csv_data = [
            {
                'COUNTY NAME': 'Franklin County',
                'NAME': 'Main Library',
                'ADDRESS': '96 S Grant Ave',
                'CITY': 'Columbus',
                'ZIP CODE': '43215',
                'Precinct Name': 'Precinct 1-A',
                'STATE PRECINCT CODE': '001A',
                'COUNTY PRECINCT CODE': '001'
            },
            {
                'COUNTY NAME': 'Franklin County',
                'NAME': 'Community Center',
                'ADDRESS': '123 Main St',
                'CITY': 'Columbus',
                'ZIP CODE': '43215',
                'Precinct Name': 'Precinct 2-B',
                'STATE PRECINCT CODE': '002B',
                'COUNTY PRECINCT CODE': '002'
            }
        ]

        with patch('builtins.open', mock_open(read_data='COUNTY NAME,NAME,ADDRESS,CITY,ZIP CODE,Precinct Name,STATE PRECINCT CODE,COUNTY PRECINCT CODE\nFranklin County,Main Library,96 S Grant Ave,Columbus,43215,Precinct 1-A,001A,001\nFranklin County,Community Center,123 Main St,Columbus,43215,Precinct 2-B,002B,002\n')), \
             patch('csv.DictReader', return_value=mock_csv_data):
            
            result = self.plugin._read_csv()

        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]['COUNTY NAME'], 'Franklin County')
        self.assertEqual(result[0]['NAME'], 'Main Library')

    def test_read_csv_file_not_found(self):
        """Test CSV reading when file doesn't exist."""
        with patch('builtins.open', side_effect=FileNotFoundError("File not found")):
            with self.assertRaises(FileNotFoundError):
                self.plugin._read_csv()

    def test_infer_location_type_drop_box(self):
        """Test location type inference for drop boxes."""
        test_cases = [
            ("Main Library Drop Box", "drop box"),
            ("Ballot Drop Location", "drop box"),
            ("Dropbox Center", "drop box"),
            ("Ballot Box Site", "drop box")
        ]

        for name, expected_type in test_cases:
            with self.subTest(name=name):
                result = self.plugin._infer_location_type(name)
                self.assertEqual(result, expected_type)

    def test_infer_location_type_early_voting(self):
        """Test location type inference for early voting."""
        test_cases = [
            ("Early Voting Center", "early voting"),
            ("Early Vote Location", "early voting"),
            ("Advance Voting Site", "early voting"),
            ("Early In-Person Voting", "early voting")
        ]

        for name, expected_type in test_cases:
            with self.subTest(name=name):
                result = self.plugin._infer_location_type(name)
                self.assertEqual(result, expected_type)

    def test_infer_location_type_election_day(self):
        """Test location type inference for election day locations."""
        test_cases = [
            ("Main Library", "election day"),
            ("Community Center", "election day"),
            ("Fire Station", "election day"),
            ("School Gymnasium", "election day")
        ]

        for name, expected_type in test_cases:
            with self.subTest(name=name):
                result = self.plugin._infer_location_type(name)
                self.assertEqual(result, expected_type)


class TestOhioDataGeneration(unittest.TestCase):
    """Unit tests for Ohio plugin's data generation functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_app = Mock()
        self.mock_app.logger = Mock()
        self.mock_db = Mock()
        self.mock_db.session = Mock()
        self.plugin = OhioPlugin(self.mock_app, self.mock_db)

    def test_fetch_polling_places_unique_locations(self):
        """Test that duplicate polling places are properly deduplicated."""
        mock_csv_data = [
            {
                'COUNTY NAME': 'Franklin County',
                'NAME': 'Main Library',
                'ADDRESS': '96 S Grant Ave',
                'CITY': 'Columbus',
                'ZIP CODE': '43215',
                'Precinct Name': 'Precinct 1-A',
                'STATE PRECINCT CODE': '001A',
                'COUNTY PRECINCT CODE': '001'
            },
            {
                'COUNTY NAME': 'Franklin County',
                'NAME': 'Main Library',  # Same location
                'ADDRESS': '96 S Grant Ave',  # Same address
                'CITY': 'Columbus',  # Same city
                'ZIP CODE': '43215',
                'Precinct Name': 'Precinct 1-B',  # Different precinct
                'STATE PRECINCT CODE': '001B',
                'COUNTY PRECINCT CODE': '002'
            }
        ]

        with patch.object(self.plugin, '_read_csv', return_value=mock_csv_data), \
             patch.object(self.plugin, '_geocode_addresses') as mock_geocode:
            
            # Mock no existing polling places
            mock_polling_place = Mock()
            mock_polling_place.latitude = None
            mock_polling_place.longitude = None
            self.mock_db.session.get.return_value = None
            
            result = self.plugin.fetch_polling_places()

        # Should only create one unique polling place
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['name'], 'Main Library')
        self.assertEqual(result[0]['address_line1'], '96 S Grant Ave')

    def test_fetch_polling_places_id_generation(self):
        """Test polling place ID generation follows expected format."""
        mock_csv_data = [
            {
                'COUNTY NAME': 'Franklin County',
                'NAME': 'Main Library',
                'ADDRESS': '96 S Grant Ave',
                'CITY': 'Columbus',
                'ZIP CODE': '43215',
                'Precinct Name': 'Precinct 1-A',
                'STATE PRECINCT CODE': '001A',
                'COUNTY PRECINCT CODE': '001'
            }
        ]

        with patch.object(self.plugin, '_read_csv', return_value=mock_csv_data), \
             patch.object(self.plugin, '_geocode_addresses') as mock_geocode:
            
            # Mock no existing polling places
            self.mock_db.session.get.return_value = None
            
            result = self.plugin.fetch_polling_places()

        # Check ID format: OH-{COUNTY}-PP-{####}
        self.assertEqual(len(result), 1)
        polling_place_id = result[0]['id']
        self.assertTrue(polling_place_id.startswith('OH-FRANKLIN-PP-'))
        self.assertRegex(polling_place_id, r'OH-FRANKLIN-PP-\d{4}')

    def test_fetch_precincts_polling_place_linking(self):
        """Test that precincts are properly linked to polling places."""
        mock_csv_data = [
            {
                'COUNTY NAME': 'Franklin County',
                'NAME': 'Main Library',
                'ADDRESS': '96 S Grant Ave',
                'CITY': 'Columbus',
                'ZIP CODE': '43215',
                'Precinct Name': 'Precinct 1-A',
                'STATE PRECINCT CODE': '001A',
                'COUNTY PRECINCT CODE': '001'
            }
        ]

        with patch.object(self.plugin, '_read_csv', return_value=mock_csv_data):
            result = self.plugin.fetch_precincts()

        self.assertEqual(len(result), 1)
        precinct = result[0]
        self.assertEqual(precinct['name'], 'Precinct 1-A')
        self.assertEqual(precinct['state'], 'OH')
        self.assertEqual(precinct['county'], 'Franklin County')
        self.assertEqual(precinct['precinctcode'], '001A')
        self.assertIsNotNone(precinct['polling_place_id'])

    def test_fetch_precincts_id_generation(self):
        """Test precinct ID generation follows expected format."""
        mock_csv_data = [
            {
                'COUNTY NAME': 'Franklin County',
                'NAME': 'Main Library',
                'ADDRESS': '96 S Grant Ave',
                'CITY': 'Columbus',
                'ZIP CODE': '43215',
                'Precinct Name': 'Precinct 1-A',
                'STATE PRECINCT CODE': '001A',
                'COUNTY PRECINCT CODE': '001'
            }
        ]

        with patch.object(self.plugin, '_read_csv', return_value=mock_csv_data):
            result = self.plugin.fetch_precincts()

        # Check ID format: OH-{COUNTY}-{STATE_PRECINCT_CODE}
        self.assertEqual(len(result), 1)
        precinct_id = result[0]['id']
        self.assertEqual(precinct_id, 'OH-FRANKLIN-001A')

    def test_fetch_precincts_missing_polling_place(self):
        """Test handling when polling place reference is missing."""
        mock_csv_data = [
            {
                'COUNTY NAME': 'Franklin County',
                'NAME': 'Main Library',
                'ADDRESS': '96 S Grant Ave',
                'CITY': 'Columbus',
                'ZIP CODE': '43215',
                'Precinct Name': 'Precinct 1-A',
                'STATE PRECINCT CODE': '001A',
                'COUNTY PRECINCT CODE': '001'
            }
        ]

        with patch.object(self.plugin, '_read_csv', return_value=mock_csv_data):
            # Mock the polling_places lookup to return empty (simulating missing reference)
            with patch.object(self.plugin, '_read_csv') as mock_read:
                # First call for building lookup, second call for processing
                mock_read.side_effect = [mock_csv_data, []]  # Empty second call breaks lookup
                
                result = self.plugin.fetch_precincts()

        # Should handle missing polling place gracefully
        self.assertEqual(len(result), 0)
        self.mock_app.logger.warning.assert_called()


class TestOhioGeocoding(unittest.TestCase):
    """Tests for Ohio plugin geocoding functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_app = Mock()
        self.mock_app.logger = Mock()
        self.mock_app.config = {'geocoder_priority': ['Census', 'Google', 'Mapbox']}
        self.mock_db = Mock()
        self.plugin = OhioPlugin(self.mock_app, self.mock_db)

    @patch('plugins.ohio.os.getenv')
    @patch('plugins.ohio.requests.post')
    def test_census_geocoding_success(self, mock_post, mock_getenv):
        """Test successful Census geocoding."""
        mock_getenv.return_value = None  # No API keys needed for Census
        
        # Mock Census response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = "id,street,city,state,zip,match,match_type,tiger_line_id,tiger_side,longitude,latitude\nOH-TEST-PP-0001,123 Main St,Columbus,OH,43215,Match,Exact,123456,-83.0006,39.9612"
        mock_post.return_value = mock_response
        
        polling_places = [{
            'id': 'OH-TEST-PP-0001',
            'address_line1': '123 Main St',
            'city': 'Columbus',
            'zip_code': '43215'
        }]
        
        self.plugin._geocode_census(polling_places)
        
        self.assertEqual(polling_places[0]['latitude'], 39.9612)
        self.assertEqual(polling_places[0]['longitude'], -83.0006)

    @patch('plugins.ohio.os.getenv')
    @patch('plugins.ohio.requests.get')
    def test_google_geocoding_success(self, mock_get, mock_getenv):
        """Test successful Google geocoding."""
        mock_getenv.return_value = 'test-api-key'
        
        # Mock Google API response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'status': 'OK',
            'results': [{
                'geometry': {
                    'location': {'lat': 39.9612, 'lng': -83.0006}
                }
            }]
        }
        mock_get.return_value = mock_response
        
        polling_places = [{
            'id': 'OH-TEST-PP-0001',
            'address_line1': '123 Main St',
            'city': 'Columbus',
            'zip_code': '43215'
        }]
        
        self.plugin._geocode_google(polling_places)
        
        self.assertEqual(polling_places[0]['latitude'], 39.9612)
        self.assertEqual(polling_places[0]['longitude'], -83.0006)

    @patch('plugins.ohio.os.getenv')
    def test_google_geocoding_no_api_key(self, mock_getenv):
        """Test Google geocoding with no API key."""
        mock_getenv.return_value = None
        
        polling_places = [{
            'id': 'OH-TEST-PP-0001',
            'address_line1': '123 Main St',
            'city': 'Columbus',
            'zip_code': '43215'
        }]
        
        self.plugin._geocode_google(polling_places)
        
        # Should log warning and not attempt geocoding
        self.mock_app.logger.warning.assert_called_with("Google API key not set, skipping Google geocoding")

    def test_geocode_addresses_with_missing_data(self):
        """Test geocoding with incomplete address data."""
        polling_places = [
            {'id': 'OH-TEST-PP-001', 'address_line1': '', 'city': 'Columbus', 'zip_code': '43215'},  # Missing address
            {'id': 'OH-TEST-PP-002', 'address_line1': '123 Main St', 'city': '', 'zip_code': '43215'},  # Missing city
            {'id': 'OH-TEST-PP-003', 'address_line1': '123 Main St', 'city': 'Columbus', 'zip_code': ''},  # Missing zip
            {'id': 'OH-TEST-PP-004', 'address_line1': '123 Main St', 'city': 'Columbus', 'zip_code': '43215'},  # Complete
        ]
        
        with patch.object(self.plugin, '_geocode_census') as mock_geocode:
            self.plugin._geocode_addresses(polling_places)
        
        # Should only geocode the complete address
        mock_geocode.assert_called_once()
        geocoded_places = mock_geocode.call_args[0][0]
        self.assertEqual(len(geocoded_places), 1)
        self.assertEqual(geocoded_places[0]['id'], 'OH-TEST-PP-004')


class TestOhioFileUpload(unittest.TestCase):
    """Tests for Ohio plugin file upload functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_app = Mock()
        self.mock_app.logger = Mock()
        self.mock_db = Mock()
        self.plugin = OhioPlugin(self.mock_app, self.mock_db)
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        """Clean up temporary files."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_upload_file_success(self):
        """Test successful file upload."""
        # Create a temporary CSV file
        test_csv_path = os.path.join(self.temp_dir, 'test_ohio.csv')
        with open(test_csv_path, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['COUNTY NAME', 'NAME', 'ADDRESS', 'CITY', 'ZIP CODE', 'Precinct Name', 'STATE PRECINCT CODE', 'COUNTY PRECINCT CODE'])
            writer.writerow(['Franklin County', 'Test Location', '123 Test St', 'Columbus', '43215', 'Precinct 1', '001', '001'])

        # Mock the current CSV path
        with patch('plugins.ohio.os.path.join') as mock_join:
            mock_join.return_value = os.path.join(self.temp_dir, 'ohio.csv')
            
            result = self.plugin.upload_file(test_csv_path)

        self.assertTrue(result['success'])
        self.assertIn('Backup created', result['message'])

    def test_upload_file_with_backup(self):
        """Test file upload creates backup of existing file."""
        # Create existing CSV file
        existing_csv_path = os.path.join(self.temp_dir, 'ohio.csv')
        with open(existing_csv_path, 'w') as f:
            f.write('existing,data\n')

        # Create new CSV file
        new_csv_path = os.path.join(self.temp_dir, 'new_ohio.csv')
        with open(new_csv_path, 'w') as f:
            f.write('new,data\n')

        with patch('plugins.ohio.os.path.join') as mock_join:
            mock_join.side_effect = lambda *args: os.path.join(self.temp_dir, *args[1:])
            
            result = self.plugin.upload_file(new_csv_path)

        self.assertTrue(result['success'])
        # Check backup was created
        backup_path = existing_csv_path + '.backup'
        self.assertTrue(os.path.exists(backup_path))
        with open(backup_path, 'r') as f:
            self.assertEqual(f.read(), 'existing,data\n')

    def test_upload_file_failure(self):
        """Test file upload failure scenario."""
        invalid_path = '/nonexistent/path/file.csv'

        result = self.plugin.upload_file(invalid_path)

        self.assertFalse(result['success'])
        self.assertIn('error', result)


class TestOhioErrorScenarios(unittest.TestCase):
    """Error scenario tests for Ohio plugin."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_app = Mock()
        self.mock_app.logger = Mock()
        self.mock_db = Mock()
        self.mock_db.session = Mock()
        self.plugin = OhioPlugin(self.mock_app, self.mock_db)

    def test_csv_with_missing_columns(self):
        """Test handling of CSV with missing required columns."""
        mock_csv_data = [
            {
                'COUNTY NAME': 'Franklin County',
                'NAME': 'Main Library',
                # Missing ADDRESS, CITY, ZIP CODE
                'Precinct Name': 'Precinct 1-A',
                'STATE PRECINCT CODE': '001A',
                'COUNTY PRECINCT CODE': '001'
            }
        ]

        with patch.object(self.plugin, '_read_csv', return_value=mock_csv_data):
            with self.assertRaises(KeyError):
                self.plugin.fetch_polling_places()

    def test_csv_with_empty_data(self):
        """Test handling of empty CSV data."""
        with patch.object(self.plugin, '_read_csv', return_value=[]):
            result = self.plugin.fetch_polling_places()
            
            self.assertEqual(len(result), 0)

    def test_geocoding_network_error(self):
        """Test handling of network errors during geocoding."""
        polling_places = [{
            'id': 'OH-TEST-PP-0001',
            'address_line1': '123 Main St',
            'city': 'Columbus',
            'zip_code': '43215'
        }]

        with patch('plugins.ohio.requests.post', side_effect=requests.RequestException("Network error")):
            # Should handle network error gracefully
            self.plugin._geocode_census(polling_places)
            
            # Should log the error
            self.mock_app.logger.error.assert_called()

    def test_database_session_error(self):
        """Test handling of database session errors."""
        mock_csv_data = [
            {
                'COUNTY NAME': 'Franklin County',
                'NAME': 'Main Library',
                'ADDRESS': '96 S Grant Ave',
                'CITY': 'Columbus',
                'ZIP CODE': '43215',
                'Precinct Name': 'Precinct 1-A',
                'STATE PRECINCT CODE': '001A',
                'COUNTY PRECINCT CODE': '001'
            }
        ]

        # Mock database session to raise an exception
        self.mock_db.session.get.side_effect = Exception("Database error")

        with patch.object(self.plugin, '_read_csv', return_value=mock_csv_data), \
             patch.object(self.plugin, '_geocode_addresses'):
            
            with self.assertRaises(Exception):
                self.plugin.fetch_polling_places()


class TestOhioIntegration(unittest.TestCase):
    """Integration tests for complete Ohio plugin workflow."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_app = Mock()
        self.mock_app.logger = Mock()
        self.mock_app.config = {'geocoder_priority': ['Census']}
        self.mock_db = Mock()
        self.mock_db.session = Mock()
        self.plugin = OhioPlugin(self.mock_app, self.mock_db)

    def test_complete_workflow(self):
        """Test complete workflow from CSV reading to data generation."""
        mock_csv_data = [
            {
                'COUNTY NAME': 'Franklin County',
                'NAME': 'Main Library',
                'ADDRESS': '96 S Grant Ave',
                'CITY': 'Columbus',
                'ZIP CODE': '43215',
                'Precinct Name': 'Precinct 1-A',
                'STATE PRECINCT CODE': '001A',
                'COUNTY PRECINCT CODE': '001'
            },
            {
                'COUNTY NAME': 'Franklin County',
                'NAME': 'Community Center',
                'ADDRESS': '123 Main St',
                'CITY': 'Columbus',
                'ZIP CODE': '43215',
                'Precinct Name': 'Precinct 2-B',
                'STATE PRECINCT CODE': '002B',
                'COUNTY PRECINCT CODE': '002'
            }
        ]

        with patch.object(self.plugin, '_read_csv', return_value=mock_csv_data), \
             patch.object(self.plugin, '_geocode_addresses') as mock_geocode:
            
            # Mock no existing polling places
            self.mock_db.session.get.return_value = None
            
            # Test polling places
            polling_places = self.plugin.fetch_polling_places()
            self.assertEqual(len(polling_places), 2)
            
            # Test precincts
            precincts = self.plugin.fetch_precincts()
            self.assertEqual(len(precincts), 2)
            
            # Verify geocoding was called
            mock_geocode.assert_called()

    def test_address_change_detection(self):
        """Test that address changes trigger re-geocoding."""
        mock_csv_data = [
            {
                'COUNTY NAME': 'Franklin County',
                'NAME': 'Main Library',
                'ADDRESS': '96 S Grant Ave',
                'CITY': 'Columbus',
                'ZIP CODE': '43215',
                'Precinct Name': 'Precinct 1-A',
                'STATE PRECINCT CODE': '001A',
                'COUNTY PRECINCT CODE': '001'
            }
        ]

        # Mock existing polling place with different address
        mock_existing = Mock()
        mock_existing.address_line1 = '123 Different St'
        mock_existing.address_line2 = None
        mock_existing.address_line3 = None
        mock_existing.city = 'Columbus'
        mock_existing.state = 'OH'
        mock_existing.zip_code = '43215'
        mock_existing.latitude = 39.9612
        mock_existing.longitude = -83.0006

        with patch.object(self.plugin, '_read_csv', return_value=mock_csv_data), \
             patch.object(self.plugin, '_geocode_addresses') as mock_geocode, \
             patch.object(self.plugin, 'has_address_changed', return_value=True):
            
            self.mock_db.session.get.return_value = mock_existing
            
            polling_places = self.plugin.fetch_polling_places()

        # Should trigger re-geocoding due to address change
        mock_geocode.assert_called_once()
        geocoded_places = mock_geocode.call_args[0][0]
        self.assertEqual(len(geocoded_places), 1)


if __name__ == '__main__':
    # Create test suite
    test_suite = unittest.TestSuite()
    
    # Add all test classes
    test_classes = [
        TestOhioCSVParsing,
        TestOhioDataGeneration,
        TestOhioGeocoding,
        TestOhioFileUpload,
        TestOhioErrorScenarios,
        TestOhioIntegration
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