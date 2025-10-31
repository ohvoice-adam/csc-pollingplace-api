"""
Comprehensive test suite for Virginia plugin sync functionality.

Includes unit tests, integration tests, and data validation tests for:
- File discovery methods with mock HTTP responses
- Complete sync workflow from file selection through database updates
- Election record creation and precinct assignment linking
- Error scenarios for invalid URLs, malformed files, and database violations
"""

import pytest
import unittest
from unittest.mock import Mock, patch, MagicMock, call
from datetime import datetime, date
from io import BytesIO
import pandas as pd
import requests
from bs4 import BeautifulSoup

# Import the plugin and models
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from plugins.virginia import VirginiaPlugin
from models import PollingPlace, Precinct, PrecinctAssignment, Election


class TestVirginiaFileDiscovery(unittest.TestCase):
    """Unit tests for Virginia plugin's file discovery methods using mock HTTP responses."""

    def setUp(self):
        """Set up test fixtures with mock app and database."""
        self.mock_app = Mock()
        self.mock_app.logger = Mock()
        self.mock_db = Mock()
        self.plugin = VirginiaPlugin(self.mock_app, self.mock_db)

    @patch('plugins.virginia.requests.get')
    def test_discover_available_files_success(self, mock_get):
        """Test successful file discovery with valid HTML response."""
        # Mock HTML response with Excel file links
        mock_html = """
        <html>
            <body>
                <a href="/media/registration-statistics/2024-November-General-Election-Day-Polling-Locations-(10-9-24).xlsx">November General</a>
                <a href="/media/registration-statistics/2024-June-Democratic-and-Republican-Primary-Polling-Locations-(6-5-24).xlsx">June Primary</a>
                <a href="/media/registration-statistics/2024-March-Presidential-Primary-Polling-Locations-(2-27-24).xlsx">March Primary</a>
                <a href="/some/other/file.pdf">PDF File</a>
                <a href="/media/registration-statistics/not-polling-data.xlsx">Non-polling Excel</a>
            </body>
        </html>
        """
        
        mock_response = Mock()
        mock_response.text = mock_html
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        result = self.plugin._discover_available_files()

        # Verify results
        self.assertEqual(len(result), 3)
        
        # Check first file (November General)
        first_file = result[0]
        self.assertEqual(first_file['election_date'], '2024-11-05')
        self.assertEqual(first_file['election_name'], '2024 General Election')
        self.assertEqual(first_file['election_type'], 'general')
        self.assertIn('2024-November-General-Election-Day-Polling-Locations-(10-9-24).xlsx', first_file['filename'])
        
        # Verify files are sorted by date (most recent first)
        dates = [f['election_date'] for f in result]
        self.assertEqual(dates, ['2024-11-05', '2024-06-18', '2024-03-05'])

    @patch('plugins.virginia.requests.get')
    def test_discover_available_files_request_failure(self, mock_get):
        """Test file discovery with HTTP request failure."""
        mock_get.side_effect = requests.RequestException("Connection error")

        result = self.plugin._discover_available_files()

        self.assertEqual(result, [])
        self.mock_app.logger.error.assert_called()

    @patch('plugins.virginia.requests.get')
    def test_discover_available_files_empty_response(self, mock_get):
        """Test file discovery with empty HTML response."""
        mock_response = Mock()
        mock_response.text = "<html><body></body></html>"
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        result = self.plugin._discover_available_files()

        self.assertEqual(result, [])

    def test_parse_filename_metadata_general_election(self):
        """Test parsing metadata from general election filename."""
        filename = "2024-November-General-Election-Day-Polling-Locations-(10-9-24).xlsx"
        
        result = self.plugin._parse_filename_metadata(filename)
        
        self.assertIsNotNone(result)
        if result:  # Guard against None for type checking
            self.assertEqual(result['election_date'], '2024-11-05')
            self.assertEqual(result['election_name'], '2024 General Election')
            self.assertEqual(result['election_type'], 'general')
            self.assertEqual(result['file_date'], '2024-10-09')
            self.assertEqual(result['year'], '2024')

    def test_parse_filename_metadata_presidential_primary(self):
        """Test parsing metadata from presidential primary filename."""
        filename = "2024-March-Presidential-Primary-Polling-Locations-(2-27-24).xlsx"
        
        result = self.plugin._parse_filename_metadata(filename)
        
        self.assertIsNotNone(result)
        if result:  # Guard against None for type checking
            self.assertEqual(result['election_date'], '2024-03-05')
            self.assertEqual(result['election_name'], '2024 Presidential Primary')
            self.assertEqual(result['election_type'], 'presidential_primary')
            self.assertEqual(result['file_date'], '2024-02-27')

    def test_parse_filename_metadata_party_primary(self):
        """Test parsing metadata from party primary filename."""
        filename = "2024-June-Democratic-and-Republican-Primary-Polling-Locations-(6-5-24).xlsx"
        
        result = self.plugin._parse_filename_metadata(filename)
        
        self.assertIsNotNone(result)
        if result:  # Guard against None for type checking
            self.assertEqual(result['election_date'], '2024-06-18')
            self.assertEqual(result['election_name'], '2024 Primary Election')
            self.assertEqual(result['election_type'], 'party_primary')

    def test_parse_filename_metadata_special_election(self):
        """Test parsing metadata from special election filename."""
        filename = "2023-September-Special-Election-Polling-Locations.xlsx"
        
        result = self.plugin._parse_filename_metadata(filename)
        
        self.assertIsNotNone(result)
        if result:  # Guard against None for type checking
            self.assertEqual(result['election_date'], '2023-11-05')  # Default fallback
            self.assertEqual(result['election_name'], '2023 Special Election')
            self.assertEqual(result['election_type'], 'special')

    def test_parse_filename_metadata_invalid_format(self):
        """Test parsing metadata from invalid filename format."""
        filename = "invalid-file-name.xlsx"
        
        result = self.plugin._parse_filename_metadata(filename)
        
        self.assertIsNone(result)

    def test_generate_election_name_from_metadata(self):
        """Test election name generation from metadata."""
        # Test general election
        name = self.plugin._generate_election_name_from_metadata('2024-11-05', 'general')
        self.assertEqual(name, '2024 General Election')
        
        # Test presidential primary
        name = self.plugin._generate_election_name_from_metadata('2024-03-05', 'presidential_primary')
        self.assertEqual(name, '2024 Presidential Primary')
        
        # Test unknown type
        name = self.plugin._generate_election_name_from_metadata('2024-07-15', 'unknown')
        self.assertEqual(name, '2024 July Election')

    def test_get_available_elections(self):
        """Test getting structured election data from discovered files."""
        mock_files = [
            {
                'election_date': '2024-11-05',
                'election_name': '2024 General Election',
                'election_type': 'general',
                'url': 'http://example.com/file1.xlsx',
                'filename': 'file1.xlsx',
                'file_date': '2024-10-09'
            },
            {
                'election_date': '2022-11-08',
                'election_name': '2022 General Election',
                'election_type': 'general',
                'url': 'http://example.com/file2.xlsx',
                'filename': 'file2.xlsx',
                'file_date': '2022-11-01'
            }
        ]
        
        with patch.object(self.plugin, '_discover_available_files', return_value=mock_files):
            result = self.plugin.get_available_elections()
        
        self.assertEqual(len(result), 2)
        
        # Check recent election (within 2 years)
        recent_election = next(e for e in result if e['election_date'] == '2024-11-05')
        self.assertTrue(recent_election['is_recent'])
        
        # Check old election (more than 2 years)
        old_election = next(e for e in result if e['election_date'] == '2022-11-08')
        self.assertFalse(old_election['is_recent'])


class TestVirginiaDataParsing(unittest.TestCase):
    """Unit tests for Virginia plugin's Excel data parsing functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_app = Mock()
        self.mock_app.logger = Mock()
        self.mock_db = Mock()
        self.plugin = VirginiaPlugin(self.mock_app, self.mock_db)

    def test_normalize_locality_name(self):
        """Test locality name normalization."""
        # Test county
        result = self.plugin._normalize_locality_name("ACCOMACK COUNTY")
        self.assertEqual(result, "ACCOMACK")
        
        # Test city
        result = self.plugin._normalize_locality_name("RICHMOND CITY")
        self.assertEqual(result, "RICHMOND")
        
        # Test with special characters
        result = self.plugin._normalize_locality_name("FAIRFAX COUNTY (TEST)")
        self.assertEqual(result, "FAIRFAX")

    def test_extract_precinct_number(self):
        """Test precinct number extraction."""
        # Test standard format
        result = self.plugin._extract_precinct_number("101 - CHINCOTEAGUE")
        self.assertEqual(result, "101")
        
        # Test fallback format
        result = self.plugin._extract_precinct_number("PRECINCT-A")
        self.assertEqual(result, "PRECINCTA")

    def test_infer_location_type(self):
        """Test location type inference."""
        # Test drop box
        result = self.plugin._infer_location_type("Main Library Drop Box")
        self.assertEqual(result, "drop box")
        
        # Test early voting
        result = self.plugin._infer_location_type("Early Voting Center")
        self.assertEqual(result, "early voting")
        
        # Test default (election day)
        result = self.plugin._infer_location_type("Main Library")
        self.assertEqual(result, "election day")

    def test_parse_excel_data(self):
        """Test Excel data parsing into polling places and precincts."""
        # Create mock DataFrame
        mock_data = {
            'Locality Name': ['ACCOMACK COUNTY', 'ACCOMACK COUNTY'],
            'Voting Precinct Name': ['101 - CHINCOTEAGUE', '102 - ATLANTIC'],
            'Location': ['Chincoteague Elementary School', 'Atlantic Elementary School'],
            'Address Line 1': ['123 School St', '456 School Ave'],
            'Address Line 2': [None, 'Room 101'],
            'City': ['Chincoteague', 'Atlantic'],
            'Zip Code': ['23336', '23337']
        }
        df = pd.DataFrame(mock_data)
        
        polling_places, precincts = self.plugin._parse_excel_data(df)
        
        # Verify polling places
        self.assertEqual(len(polling_places), 2)
        self.assertEqual(polling_places[0]['id'], 'VA-ACCOMACK-PP-0001')
        self.assertEqual(polling_places[0]['name'], 'Chincoteague Elementary School')
        self.assertEqual(polling_places[0]['city'], 'Chincoteague')
        
        # Verify precincts
        self.assertEqual(len(precincts), 2)
        self.assertEqual(precincts[0]['id'], 'VA-ACCOMACK-P-101')
        self.assertEqual(precincts[0]['name'], '101 - CHINCOTEAGUE')
        self.assertEqual(precincts[0]['polling_place_id'], 'VA-ACCOMACK-PP-0001')

    def test_parse_excel_data_with_missing_data(self):
        """Test Excel data parsing with missing/invalid data."""
        # Create mock DataFrame with missing data
        mock_data = {
            'Locality Name': ['ACCOMACK COUNTY', None, 'ACCOMACK COUNTY'],
            'Voting Precinct Name': ['101 - CHINCOTEAGUE', '102 - ATLANTIC', ''],
            'Location': ['Chincoteague Elementary School', 'Atlantic Elementary School', 'Test School'],
            'Address Line 1': ['123 School St', '456 School Ave', '789 School Rd'],
            'Address Line 2': [None, 'Room 101', None],
            'City': ['Chincoteague', 'Atlantic', 'Test City'],
            'Zip Code': ['23336', '23337', '23338']
        }
        df = pd.DataFrame(mock_data)
        
        polling_places, precincts = self.plugin._parse_excel_data(df)
        
        # Should skip rows with missing critical data
        self.assertEqual(len(polling_places), 2)  # Only valid rows
        self.assertEqual(len(precincts), 2)


class TestVirginiaSyncWorkflow(unittest.TestCase):
    """Integration tests for complete sync workflow."""

    def setUp(self):
        """Set up test fixtures with database mocking."""
        self.mock_app = Mock()
        self.mock_app.logger = Mock()
        self.mock_db = Mock()
        self.mock_db.session = Mock()
        self.plugin = VirginiaPlugin(self.mock_app, self.mock_db)

    @patch('plugins.virginia.requests.get')
    def test_download_excel_success(self, mock_get):
        """Test successful Excel file download and parsing."""
        # Create mock Excel data
        mock_data = pd.DataFrame({
            'Locality Name': ['ACCOMACK COUNTY'],
            'Voting Precinct Name': ['101 - CHINCOTEAGUE'],
            'Location': ['Test School'],
            'Address Line 1': ['123 Test St'],
            'Address Line 2': [None],
            'City': ['Test City'],
            'Zip Code': ['12345']
        })
        
        # Mock HTTP response
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        
        # Mock pandas read_excel
        with patch('pandas.read_excel', return_value=mock_data):
            result = self.plugin._download_excel('http://example.com/test.xlsx')
        
        self.assertIsInstance(result, pd.DataFrame)
        self.assertEqual(len(result), 1)

    @patch('plugins.virginia.requests.get')
    def test_download_excel_failure(self, mock_get):
        """Test Excel file download failure."""
        mock_get.side_effect = requests.RequestException("Download failed")
        
        with self.assertRaises(requests.RequestException):
            self.plugin._download_excel('http://example.com/test.xlsx')

    def test_get_or_create_election_new(self):
        """Test creating a new election record."""
        election_date = date(2024, 11, 5)
        election_name = "2024 General Election"
        
        # Mock database queries
        mock_election_query = Mock()
        mock_election_query.filter_by.return_value.first.return_value = None
        self.mock_db.session.query.return_value = mock_election_query
        
        # Mock Election class
        with patch('app.Election') as mock_election_class:
            mock_election = Mock()
            mock_election.id = 1
            mock_election_class.return_value = mock_election
            
            result = self.plugin._get_or_create_election(election_date, election_name)
        
        self.assertEqual(result, mock_election)
        self.mock_db.session.add.assert_called_once_with(mock_election)
        self.mock_db.session.commit.assert_called_once()

    def test_get_or_create_election_existing(self):
        """Test retrieving an existing election record."""
        election_date = date(2024, 11, 5)
        election_name = "2024 General Election"
        
        # Mock existing election
        mock_existing_election = Mock()
        mock_existing_election.id = 1
        
        mock_election_query = Mock()
        mock_election_query.filter_by.return_value.first.return_value = mock_existing_election
        self.mock_db.session.query.return_value = mock_election_query
        
        result = self.plugin._get_or_create_election(election_date, election_name)
        
        self.assertEqual(result, mock_existing_election)
        self.mock_db.session.add.assert_not_called()
        self.mock_db.session.commit.assert_not_called()

    def test_validate_election_data_valid(self):
        """Test validation of valid election data."""
        election_date = date(2024, 11, 5)
        election_name = "2024 General Election"
        
        result = self.plugin._validate_election_data(election_date, election_name)
        
        self.assertTrue(result)

    def test_validate_election_data_empty_name(self):
        """Test validation failure with empty election name."""
        election_date = date(2024, 11, 5)
        election_name = ""
        
        result = self.plugin._validate_election_data(election_date, election_name)
        
        self.assertFalse(result)

    def test_validate_election_data_none_date(self):
        """Test validation failure with None election date."""
        election_date = None
        election_name = "2024 General Election"
        
        result = self.plugin._validate_election_data(election_date, election_name)
        
        self.assertFalse(result)

    def test_sync_single_file_success(self):
        """Test successful single file sync workflow."""
        file_url = "http://example.com/test.xlsx"
        
        # Mock file metadata parsing
        mock_metadata = {
            'election_date': '2024-11-05',
            'election_name': '2024 General Election'
        }
        
        # Mock Excel data
        mock_polling_places = [{'id': 'test-pp-1', 'name': 'Test Place'}]
        mock_precincts = [{'id': 'test-p-1', 'polling_place_id': 'test-pp-1'}]
        
        # Mock election
        mock_election = Mock()
        mock_election.id = 1
        mock_election.date = date(2024, 11, 5)
        mock_election.name = '2024 General Election'
        mock_election.state = 'VA'
        
        # Mock sync results
        mock_sync_result = {
            'success': True,
            'polling_places': {'added': 1, 'updated': 0}
        }
        mock_precinct_result = {'added': 1, 'updated': 0}
        
        with patch.object(self.plugin, '_parse_filename_metadata', return_value=mock_metadata), \
             patch.object(self.plugin, '_get_or_create_election', return_value=mock_election), \
             patch.object(self.plugin, '_download_excel', return_value=pd.DataFrame()), \
             patch.object(self.plugin, '_parse_excel_data', return_value=(mock_polling_places, mock_precincts)), \
             patch.object(self.plugin, 'sync', return_value=mock_sync_result), \
             patch.object(self.plugin, 'sync_precincts', return_value=mock_precinct_result):
            
            result = self.plugin.sync_single_file(file_url)
        
        self.assertTrue(result['success'])
        self.assertEqual(result['election']['id'], 1)
        self.assertEqual(result['polling_places']['added'], 1)
        self.assertEqual(result['precincts']['added'], 1)

    def test_sync_single_file_failure(self):
        """Test single file sync failure scenario."""
        file_url = "http://example.com/invalid.xlsx"
        
        with patch.object(self.plugin, '_download_excel', side_effect=Exception("Download failed")):
            result = self.plugin.sync_single_file(file_url)
        
        self.assertFalse(result['success'])
        self.assertIn('error', result)

    def test_sync_multiple_files_success(self):
        """Test successful multiple files sync workflow."""
        file_urls = [
            "http://example.com/file1.xlsx",
            "http://example.com/file2.xlsx"
        ]
        
        # Mock single file sync results
        mock_single_result = {
            'success': True,
            'filename': 'test.xlsx',
            'polling_places': {'added': 1, 'updated': 0},
            'precincts': {'added': 1, 'updated': 0}
        }
        
        with patch.object(self.plugin, 'sync_single_file', return_value=mock_single_result):
            result = self.plugin.sync_multiple_files(file_urls)
        
        self.assertTrue(result['success'])
        self.assertEqual(result['files_processed'], 2)
        self.assertEqual(result['files_successful'], 2)
        self.assertEqual(result['total_polling_places']['added'], 2)
        self.assertEqual(result['total_precincts']['added'], 2)

    def test_sync_multiple_files_partial_failure(self):
        """Test multiple files sync with some failures."""
        file_urls = [
            "http://example.com/file1.xlsx",
            "http://example.com/file2.xlsx"
        ]
        
        # Mock alternating success/failure
        def mock_sync_single_file(url):
            if 'file1' in url:
                return {
                    'success': True,
                    'filename': 'file1.xlsx',
                    'polling_places': {'added': 1, 'updated': 0},
                    'precincts': {'added': 1, 'updated': 0}
                }
            else:
                return {
                    'success': False,
                    'error': 'Download failed',
                    'file_url': url
                }
        
        with patch.object(self.plugin, 'sync_single_file', side_effect=mock_sync_single_file):
            result = self.plugin.sync_multiple_files(file_urls)
        
        self.assertFalse(result['success'])
        self.assertEqual(result['files_processed'], 2)
        self.assertEqual(result['files_successful'], 1)
        self.assertEqual(result['files_failed'], 1)


class TestVirginiaDataValidation(unittest.TestCase):
    """Data validation tests for election parsing and precinct assignments."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_app = Mock()
        self.mock_app.logger = Mock()
        self.mock_db = Mock()
        self.plugin = VirginiaPlugin(self.mock_app, self.mock_db)

    def test_election_date_parsing_formats(self):
        """Test various election date parsing formats."""
        # Test MM-DD-YY format in parentheses
        filename = "2024-November-General-Election-Day-Polling-Locations-(10-9-24).xlsx"
        result = self.plugin._parse_filename_metadata(filename)
        self.assertIsNotNone(result)
        if result:
            self.assertEqual(result['file_date'], '2024-10-09')
        
        # Test YYYYMMDD format at end
        filename = "2024-November-General-Election-Day-Polling-Locations-20241009.xlsx"
        result = self.plugin._parse_filename_metadata(filename)
        self.assertIsNotNone(result)
        if result:
            self.assertEqual(result['file_date'], '2024-10-09')

    def test_election_name_format_validation(self):
        """Test election name follows expected format."""
        test_cases = [
            ('2024-11-05', 'general', '2024 General Election'),
            ('2024-03-05', 'presidential_primary', '2024 Presidential Primary'),
            ('2024-06-18', 'party_primary', '2024 Primary Election'),
            ('2024-09-01', 'special', '2024 Special Election'),
            ('2024-05-01', 'municipal', '2024 Municipal Election'),
            ('2024-07-15', 'unknown', '2024 July Election')
        ]
        
        for election_date, election_type, expected_name in test_cases:
            result = self.plugin._generate_election_name_from_metadata(election_date, election_type)
            self.assertEqual(result, expected_name, 
                           f"Failed for date={election_date}, type={election_type}")

    def test_precinct_assignment_election_linking(self):
        """Test PrecinctAssignment records properly reference correct election IDs."""
        # Mock database objects
        mock_precinct = Mock()
        mock_precinct.id = 'VA-TEST-P-101'
        mock_polling_place = Mock()
        mock_polling_place.id = 'VA-TEST-PP-001'
        mock_election = Mock()
        mock_election.id = 1
        
        # Create assignment
        assignment = PrecinctAssignment(
            precinct_id=mock_precinct.id,
            polling_place_id=mock_polling_place.id,
            assigned_date=date(2024, 11, 5),
            election_id=mock_election.id
        )
        
        # Verify linking
        self.assertEqual(assignment.precinct_id, 'VA-TEST-P-101')
        self.assertEqual(assignment.polling_place_id, 'VA-TEST-PP-001')
        self.assertEqual(assignment.election_id, 1)
        self.assertEqual(assignment.assigned_date, date(2024, 11, 5))

    def test_validate_assignment_history(self):
        """Test assignment history validation for data integrity."""
        # Mock assignments
        mock_assignments = [
            Mock(id=1, precinct_id='P1', election_id=1, removed_date=None, precinct=Mock(), polling_place=Mock()),
            Mock(id=2, precinct_id='P2', election_id=None, removed_date=None, precinct=Mock(), polling_place=Mock()),
            Mock(id=3, precinct_id='P1', election_id=2, removed_date=date(2024, 10, 1), precinct=Mock(), polling_place=Mock()),
            Mock(id=4, precinct_id='P3', election_id=1, removed_date=None, precinct=None, polling_place=Mock()),  # Orphaned
        ]
        
        mock_query = Mock()
        mock_query.all.return_value = mock_assignments
        self.mock_db.session.query.return_value = mock_query
        
        result = self.plugin.validate_assignment_history()
        
        self.assertEqual(result['total_assignments'], 4)
        self.assertEqual(result['current_assignments'], 3)  # removed_date is None
        self.assertEqual(result['assignments_without_election'], 1)  # assignment 2
        self.assertEqual(result['orphaned_assignments'], 1)  # assignment 4
        self.assertEqual(result['duplicate_current_assignments'], 1)  # P1 appears twice

    def test_repair_assignment_history(self):
        """Test assignment history repair functionality."""
        # Mock validation results
        mock_validation = {
            'duplicate_current_assignments': 2,
            'issues': ['Issue 1', 'Issue 2']
        }
        
        # Mock database queries for duplicates
        mock_duplicates = [('P1', 2), ('P2', 2)]
        mock_query = Mock()
        mock_query.filter_by.return_value.group_by.return_value.having.return_value.all.return_value = mock_duplicates
        self.mock_db.session.query.return_value = mock_query
        
        # Mock current assignments
        mock_assignment1 = Mock(id=1, created_at=datetime(2024, 1, 1))
        mock_assignment2 = Mock(id=2, created_at=datetime(2024, 1, 2))
        mock_query.filter_by.return_value.order_by.return_value.all.return_value = [mock_assignment1, mock_assignment2]
        
        with patch.object(self.plugin, 'validate_assignment_history', return_value=mock_validation):
            result = self.plugin.repair_assignment_history(dry_run=False)
        
        self.assertFalse(result['dry_run'])
        self.assertEqual(result['issues_found'], 2)
        self.assertEqual(result['repairs_made'], 2)  # One duplicate per precinct


class TestVirginiaErrorScenarios(unittest.TestCase):
    """Error scenario tests for invalid URLs, malformed files, and database violations."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_app = Mock()
        self.mock_app.logger = Mock()
        self.mock_db = Mock()
        self.mock_db.session = Mock()
        self.plugin = VirginiaPlugin(self.mock_app, self.mock_db)

    @patch('plugins.virginia.requests.get')
    def test_invalid_file_url(self, mock_get):
        """Test handling of invalid file URLs."""
        # Mock 404 response
        mock_response = Mock()
        mock_response.raise_for_status.side_effect = requests.HTTPError("404 Not Found")
        mock_get.return_value = mock_response
        
        with self.assertRaises(requests.HTTPError):
            self.plugin._download_excel('http://example.com/nonexistent.xlsx')

    def test_malformed_excel_file(self):
        """Test handling of malformed Excel files."""
        # Mock corrupted Excel data
        with patch('pandas.read_excel', side_effect=Exception("Invalid Excel format")):
            with self.assertRaises(Exception):
                self.plugin._download_excel('http://example.com/corrupted.xlsx')

    def test_database_constraint_violation(self):
        """Test handling of database constraint violations."""
        election_date = date(2024, 11, 5)
        election_name = "2024 General Election"
        
        # Mock IntegrityError
        from sqlalchemy.exc import IntegrityError
        mock_integrity_error = Mock(spec=IntegrityError)
        
        # Mock existing election query
        mock_existing_election = Mock()
        mock_existing_election.id = 1
        
        mock_election_query = Mock()
        mock_election_query.filter_by.return_value.first.side_effect = [None, mock_existing_election]
        self.mock_db.session.query.return_value = mock_election_query
        
        # Mock session operations
        self.mock_db.session.commit.side_effect = mock_integrity_error
        self.mock_db.session.rollback = Mock()
        
        result = self.plugin._get_or_create_election(election_date, election_name)
        
        # Should handle the error and return the existing election
        self.assertEqual(result, mock_existing_election)
        self.mock_db.session.rollback.assert_called_once()

    def test_missing_required_excel_columns(self):
        """Test handling of Excel files missing required columns."""
        # Create DataFrame missing required columns
        incomplete_data = pd.DataFrame({
            'Locality Name': ['ACCOMACK COUNTY'],
            # Missing 'Voting Precinct Name', 'Location', etc.
        })
        
        with self.assertRaises(KeyError):
            self.plugin._parse_excel_data(incomplete_data)

    def test_network_timeout_during_discovery(self):
        """Test handling of network timeouts during file discovery."""
        with patch('plugins.virginia.requests.get', side_effect=requests.Timeout("Request timed out")):
            result = self.plugin._discover_available_files()
        
        self.assertEqual(result, [])
        self.mock_app.logger.error.assert_called()

    def test_empty_excel_file(self):
        """Test handling of empty Excel files."""
        empty_data = pd.DataFrame()
        
        polling_places, precincts = self.plugin._parse_excel_data(empty_data)
        
        self.assertEqual(len(polling_places), 0)
        self.assertEqual(len(precincts), 0)

    def test_invalid_date_formats_in_filename(self):
        """Test handling of invalid date formats in filenames."""
        invalid_filenames = [
            "Invalid-Date-Format-Polling-Locations.xlsx",
            "2024-13-45-General-Election.xlsx",  # Invalid month/day
            "No-Date-Information.xlsx"
        ]
        
        for filename in invalid_filenames:
            result = self.plugin._parse_filename_metadata(filename)
            # Should either return None or handle gracefully
            self.assertTrue(result is None or 'election_date' in result)

    def test_database_session_rollback_on_error(self):
        """Test database session rollback on sync errors."""
        # Mock sync method that raises an exception
        with patch.object(self.plugin, 'fetch_polling_places', side_effect=Exception("Sync error")):
            result = self.plugin.sync()
        
        self.assertFalse(result['success'])
        self.assertEqual(result['polling_places']['errors'], 1)


class TestVirginiaGeocoding(unittest.TestCase):
    """Tests for geocoding functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_app = Mock()
        self.mock_app.logger = Mock()
        self.mock_app.config = {'geocoder_priority': ['Census', 'Google', 'Mapbox']}
        self.mock_db = Mock()
        self.plugin = VirginiaPlugin(self.mock_app, self.mock_db)

    @patch('plugins.virginia.os.getenv')
    @patch('plugins.virginia.requests.post')
    def test_census_geocoding_success(self, mock_post, mock_getenv):
        """Test successful Census geocoding."""
        mock_getenv.return_value = None  # No API keys needed for Census
        
        # Mock Census response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = "id,street,city,state,zip,match,match_type,tiger_line_id,tiger_side,longitude,latitude\nVA-TEST-PP-001,123 Main St,Test City,VA,12345,Match,Exact,123456,L,-77.0365,38.8977"
        mock_post.return_value = mock_response
        
        polling_places = [{
            'id': 'VA-TEST-PP-001',
            'address_line1': '123 Main St',
            'city': 'Test City',
            'zip_code': '12345'
        }]
        
        self.plugin._geocode_census(polling_places)
        
        self.assertEqual(polling_places[0]['latitude'], 38.8977)
        self.assertEqual(polling_places[0]['longitude'], -77.0365)

    @patch('plugins.virginia.os.getenv')
    @patch('plugins.virginia.requests.get')
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
                    'location': {'lat': 38.8977, 'lng': -77.0365}
                }
            }]
        }
        mock_get.return_value = mock_response
        
        polling_places = [{
            'id': 'VA-TEST-PP-001',
            'address_line1': '123 Main St',
            'city': 'Test City',
            'zip_code': '12345'
        }]
        
        self.plugin._geocode_google(polling_places)
        
        self.assertEqual(polling_places[0]['latitude'], 38.8977)
        self.assertEqual(polling_places[0]['longitude'], -77.0365)

    @patch('plugins.virginia.os.getenv')
    def test_google_geocoding_no_api_key(self, mock_getenv):
        """Test Google geocoding with no API key."""
        mock_getenv.return_value = None
        
        polling_places = [{
            'id': 'VA-TEST-PP-001',
            'address_line1': '123 Main St',
            'city': 'Test City',
            'zip_code': '12345'
        }]
        
        self.plugin._geocode_google(polling_places)
        
        # Should log warning and not attempt geocoding
        self.mock_app.logger.warning.assert_called_with("Google API key not set, skipping Google geocoding")

    def test_geocode_addresses_with_missing_data(self):
        """Test geocoding with incomplete address data."""
        polling_places = [
            {'id': 'VA-TEST-PP-001', 'address_line1': '', 'city': 'Test City', 'zip_code': '12345'},  # Missing address
            {'id': 'VA-TEST-PP-002', 'address_line1': '123 Main St', 'city': '', 'zip_code': '12345'},  # Missing city
            {'id': 'VA-TEST-PP-003', 'address_line1': '123 Main St', 'city': 'Test City', 'zip_code': ''},  # Missing zip
            {'id': 'VA-TEST-PP-004', 'address_line1': '123 Main St', 'city': 'Test City', 'zip_code': '12345'},  # Complete
        ]
        
        with patch.object(self.plugin, '_geocode_census') as mock_geocode:
            self.plugin._geocode_addresses(polling_places)
        
        # Should only geocode the complete address
        mock_geocode.assert_called_once()
        geocoded_places = mock_geocode.call_args[0][0]
        self.assertEqual(len(geocoded_places), 1)
        self.assertEqual(geocoded_places[0]['id'], 'VA-TEST-PP-004')


if __name__ == '__main__':
    # Create test suite
    test_suite = unittest.TestSuite()
    
    # Add all test classes
    test_classes = [
        TestVirginiaFileDiscovery,
        TestVirginiaDataParsing,
        TestVirginiaSyncWorkflow,
        TestVirginiaDataValidation,
        TestVirginiaErrorScenarios,
        TestVirginiaGeocoding
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