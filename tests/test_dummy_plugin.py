"""
Comprehensive test suite for Dummy plugin functionality.

Includes unit tests, integration tests, and data validation tests for:
- Fake data generation for all US states
- Polling place and precinct data generation
- Coordinate generation within US bounds
- Location type and data distribution
- Error scenarios and edge cases
"""

import pytest
import unittest
from unittest.mock import Mock, patch, MagicMock, call
import random

# Import plugin and models
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from plugins.dummy import DummyPlugin
from models import PollingPlace, Precinct


class TestDummyDataGeneration(unittest.TestCase):
    """Unit tests for Dummy plugin's data generation functionality."""

    def setUp(self):
        """Set up test fixtures with mock app and database."""
        self.mock_app = Mock()
        self.mock_app.logger = Mock()
        self.mock_db = Mock()
        self.mock_db.session = Mock()
        self.plugin = DummyPlugin(self.mock_app, self.mock_db)

    def test_plugin_properties(self):
        """Test plugin property values."""
        self.assertEqual(self.plugin.name, 'dummy')
        self.assertEqual(self.plugin.state_code, 'ALL')
        self.assertEqual(self.plugin.description, 'Dummy plugin that generates fake polling place data for testing (all states)')

    def test_generate_fake_city(self):
        """Test fake city name generation."""
        city = self.plugin.generate_fake_city()
        
        # Should be a combination of prefix and suffix
        self.assertIsInstance(city, str)
        self.assertTrue(len(city) > 0)
        
        # Should contain one of the prefixes and suffixes
        prefixes = self.plugin.CITY_PREFIXES
        suffixes = self.plugin.CITY_SUFFIXES
        
        has_prefix = any(city.startswith(prefix) for prefix in prefixes)
        has_suffix = any(city.endswith(suffix) for suffix in suffixes)
        
        self.assertTrue(has_prefix or has_suffix)

    def test_generate_fake_address(self):
        """Test fake address generation."""
        address = self.plugin.generate_fake_address()
        
        # Should be in format "number street_name"
        self.assertIsInstance(address, str)
        parts = address.split(' ', 1)
        self.assertEqual(len(parts), 2)
        
        number, street = parts
        self.assertTrue(number.isdigit())
        self.assertIn(street, self.plugin.STREET_NAMES)

    def test_generate_fake_coordinates(self):
        """Test fake coordinate generation within US bounds."""
        lat, lng = self.plugin.generate_fake_coordinates()
        
        # Check types
        self.assertIsInstance(lat, float)
        self.assertIsInstance(lng, float)
        
        # Check US bounds (continental)
        self.assertGreaterEqual(lat, 24.5)
        self.assertLessEqual(lat, 49.4)
        self.assertGreaterEqual(lng, -125.0)
        self.assertLessEqual(lng, -66.0)

    def test_generate_fake_polling_hours(self):
        """Test fake polling hours generation."""
        hours = self.plugin.generate_fake_polling_hours()
        
        # Should be in expected format
        self.assertIsInstance(hours, str)
        self.assertRegex(hours, r'\d+:\d+ [AP]M - \d+:\d+ [AP]M')

    def test_generate_fake_location_type(self):
        """Test fake location type generation with distribution."""
        # Test multiple generations to check distribution
        types = []
        for _ in range(1000):
            types.append(self.plugin.generate_fake_location_type())
        
        # Should only return valid types
        valid_types = {'drop box', 'early voting', 'election day'}
        self.assertTrue(all(t in valid_types for t in types))
        
        # Check approximate distribution (80% election day, 15% early voting, 5% drop box)
        election_day_count = types.count('election day')
        early_voting_count = types.count('early voting')
        drop_box_count = types.count('drop box')
        
        self.assertGreater(election_day_count, 700)  # ~80%
        self.assertGreater(early_voting_count, 100)   # ~15%
        self.assertGreater(drop_box_count, 30)        # ~5%

    def test_generate_fake_location_complete(self):
        """Test complete fake location generation."""
        location = self.plugin.generate_fake_location('OH', 1)
        
        # Check required fields
        required_fields = ['id', 'name', 'address_line1', 'city', 'state', 'zip_code', 'latitude', 'longitude', 'location_type']
        for field in required_fields:
            self.assertIn(field, location)
        
        # Check field types and values
        self.assertEqual(location['id'], 'OH-00001')
        self.assertEqual(location['state'], 'OH')
        self.assertIsInstance(location['name'], str)
        self.assertIsInstance(location['address_line1'], str)
        self.assertIsInstance(location['city'], str)
        self.assertIsInstance(location['zip_code'], str)
        self.assertIsInstance(location['latitude'], float)
        self.assertIsInstance(location['longitude'], float)
        self.assertIn(location['location_type'], ['drop box', 'early voting', 'election day'])

    def test_generate_fake_location_optional_fields(self):
        """Test optional fields in fake location generation."""
        # Test multiple generations to check optional fields
        locations = [self.plugin.generate_fake_location('OH', i) for i in range(100)]
        
        # Check optional fields appear randomly
        has_location_name = any('location_name' in loc for loc in locations)
        has_notes = any('notes' in loc for loc in locations)
        has_services = any('voter_services' in loc for loc in locations)
        
        self.assertTrue(has_location_name)
        self.assertTrue(has_notes)
        self.assertTrue(has_services)

    def test_states_coverage(self):
        """Test that all US states are covered."""
        self.assertEqual(len(self.plugin.STATES), 50)
        
        # Check some known states
        known_states = ['CA', 'TX', 'NY', 'FL', 'OH', 'IL']
        for state in known_states:
            self.assertIn(state, self.plugin.STATES)
            self.assertIsInstance(self.plugin.STATES[state], str)


class TestDummyPollingPlaces(unittest.TestCase):
    """Unit tests for Dummy plugin's polling place generation."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_app = Mock()
        self.mock_app.logger = Mock()
        self.mock_db = Mock()
        self.mock_db.session = Mock()
        self.plugin = DummyPlugin(self.mock_app, self.mock_db)

    @patch('plugins.dummy.random.randint')
    def test_fetch_polling_places_count(self, mock_randint):
        """Test polling place count generation."""
        mock_randint.return_value = 105  # Fixed number for testing
        
        with patch.object(self.plugin, 'generate_fake_location') as mock_generate:
            mock_generate.return_value = {'id': 'test'}
            
            result = self.plugin.fetch_polling_places()
            
            # Should generate for all 50 states
            self.assertEqual(mock_generate.call_count, 50)
            self.assertEqual(len(result), 50 * 105)  # 50 states * 105 locations each

    @patch('plugins.dummy.random.randint')
    def test_fetch_polling_places_validation(self, mock_randint):
        """Test that generated polling places pass validation."""
        mock_randint.return_value = 2  # Small number for testing
        
        with patch.object(self.plugin, 'validate_polling_place_data', return_value=True):
            result = self.plugin.fetch_polling_places()
            
            # Should generate 2 locations per state = 100 total
            self.assertEqual(len(result), 100)

    @patch('plugins.dummy.random.randint')
    def test_fetch_polling_places_invalid_data(self, mock_randint):
        """Test handling of invalid generated data."""
        mock_randint.return_value = 2
        
        # Mock validation to fail for some locations
        def mock_validate(location):
            return location['id'] != 'invalid-id'
        
        with patch.object(self.plugin, 'generate_fake_location') as mock_generate, \
             patch.object(self.plugin, 'validate_polling_place_data', side_effect=mock_validate):
            
            # First location valid, second invalid
            mock_generate.side_effect = [
                {'id': 'valid-id'},
                {'id': 'invalid-id'}
            ]
            
            result = self.plugin.fetch_polling_places()
            
            # Should only include valid locations
            valid_locations = [loc for loc in result if loc['id'] == 'valid-id']
            self.assertEqual(len(valid_locations), 50)  # One valid per state

    def test_fetch_polling_places_id_format(self):
        """Test polling place ID format across states."""
        with patch('plugins.dummy.random.randint', return_value=1):
            with patch.object(self.plugin, 'validate_polling_place_data', return_value=True):
                result = self.plugin.fetch_polling_places()
                
                # Check ID format for each state
                for state_code in self.plugin.STATES.keys():
                    state_locations = [loc for loc in result if loc['state'] == state_code]
                    self.assertEqual(len(state_locations), 1)
                    
                    location = state_locations[0]
                    expected_id = f"{state_code}-00001"
                    self.assertEqual(location['id'], expected_id)

    def test_fetch_polling_places_geographic_distribution(self):
        """Test geographic distribution of generated polling places."""
        with patch('plugins.dummy.random.randint', return_value=10):
            with patch.object(self.plugin, 'validate_polling_place_data', return_value=True):
                result = self.plugin.fetch_polling_places()
                
                # Should have locations for all states
                states_represented = set(loc['state'] for loc in result)
                self.assertEqual(len(states_represented), 50)
                
                # Check coordinates are within bounds
                for location in result:
                    lat = location['latitude']
                    lng = location['longitude']
                    self.assertGreaterEqual(lat, 24.5)
                    self.assertLessEqual(lat, 49.4)
                    self.assertGreaterEqual(lng, -125.0)
                    self.assertLessEqual(lng, -66.0)


class TestDummyPrecincts(unittest.TestCase):
    """Unit tests for Dummy plugin's precinct generation."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_app = Mock()
        self.mock_app.logger = Mock()
        self.mock_db = Mock()
        self.mock_db.session = Mock()
        self.plugin = DummyPlugin(self.mock_app, self.mock_db)

    @patch('plugins.dummy.random.randint')
    def test_fetch_precincts_count(self, mock_randint):
        """Test precinct count generation."""
        mock_randint.return_value = 5  # 5 precincts per polling place
        
        # Mock no existing precincts
        self.mock_db.session.query.return_value.all.return_value = []
        
        result = self.plugin.fetch_precincts()
        
        # Should generate 5 precincts per polling place per state
        # 50 states * 5 polling places * 5 precincts = 1250 total
        expected_count = 50 * 5 * 5
        self.assertEqual(len(result), expected_count)

    @patch('plugins.dummy.random.randint')
    def test_fetch_precincts_existing_data(self, mock_randint):
        """Test precinct generation with existing data."""
        mock_randint.return_value = 3
        
        # Mock existing precincts
        mock_existing_precinct = Mock()
        mock_existing_precinct.id = 'OH-P-000001'
        mock_existing_precinct.current_polling_place_id = 'OH-00001'
        
        self.mock_db.session.query.return_value.all.return_value = [mock_existing_precinct]
        
        with patch('plugins.dummy.random.random', return_value=0.05):  # Below 10% threshold
            result = self.plugin.fetch_precincts()
            
            # Should handle existing precincts
            self.assertGreater(len(result), 0)

    @patch('plugins.dummy.random.randint')
    @patch('plugins.dummy.random.random')
    def test_fetch_precincts_reassignment(self, mock_random, mock_randint):
        """Test precinct reassignment logic."""
        mock_randint.return_value = 2
        mock_random.return_value = 0.15  # Above 10% threshold, triggers reassignment
        
        # Mock existing precincts
        mock_existing_precinct = Mock()
        mock_existing_precinct.id = 'OH-P-000001'
        mock_existing_precinct.current_polling_place_id = 'OH-00001'
        
        self.mock_db.session.query.return_value.all.return_value = [mock_existing_precinct]
        
        result = self.plugin.fetch_precincts()
        
        # Should have reassigned some precincts
        self.assertGreater(len(result), 0)

    def test_fetch_precincts_id_format(self):
        """Test precinct ID format."""
        with patch('plugins.dummy.random.randint', return_value=1):
            self.mock_db.session.query.return_value.all.return_value = []
            
            result = self.plugin.fetch_precincts()
            
            # Check ID format: {state}-P-{######}
            for precinct in result[:10]:  # Check first 10
                precinct_id = precinct['id']
                state = precinct['state']
                self.assertRegex(precinct_id, rf'{state}-P-\d{{6}}')

    def test_fetch_precincts_polling_place_linking(self):
        """Test that precincts are properly linked to polling places."""
        with patch('plugins.dummy.random.randint', return_value=2):
            self.mock_db.session.query.return_value.all.return_value = []
            
            result = self.plugin.fetch_precincts()
            
            # All precincts should have polling_place_id
            for precinct in result:
                self.assertIn('polling_place_id', precinct)
                self.assertIsInstance(precinct['polling_place_id'], str)
                
                # Polling place ID should match state
                self.assertTrue(precinct['polling_place_id'].startswith(precinct['state']))

    def test_fetch_precincts_data_completeness(self):
        """Test completeness of generated precinct data."""
        with patch('plugins.dummy.random.randint', return_value=1):
            self.mock_db.session.query.return_value.all.return_value = []
            
            result = self.plugin.fetch_precincts()
            
            # Check required fields
            required_fields = ['id', 'name', 'state', 'county', 'polling_place_id']
            for precinct in result:
                for field in required_fields:
                    self.assertIn(field, precinct)
                    self.assertIsNotNone(precinct[field])


class TestDummyErrorScenarios(unittest.TestCase):
    """Error scenario tests for Dummy plugin."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_app = Mock()
        self.mock_app.logger = Mock()
        self.mock_db = Mock()
        self.mock_db.session = Mock()
        self.plugin = DummyPlugin(self.mock_app, self.mock_db)

    def test_validation_failure_handling(self):
        """Test handling of validation failures."""
        with patch.object(self.plugin, 'validate_polling_place_data', return_value=False):
            result = self.plugin.fetch_polling_places()
            
            # Should return empty list if all validations fail
            self.assertEqual(len(result), 0)

    def test_database_error_handling(self):
        """Test handling of database errors."""
        # Mock database to raise an exception
        self.mock_db.session.query.side_effect = Exception("Database error")
        
        with self.assertRaises(Exception):
            self.plugin.fetch_precincts()

    def test_random_generation_edge_cases(self):
        """Test edge cases in random generation."""
        # Test with minimum values
        with patch('plugins.dummy.random.randint', return_value=100):
            with patch.object(self.plugin, 'validate_polling_place_data', return_value=True):
                result = self.plugin.fetch_polling_places()
                
                # Should still generate valid data
                self.assertEqual(len(result), 50 * 100)  # 50 states * 100 locations

    def test_coordinate_bounds_validation(self):
        """Test coordinate generation stays within bounds."""
        # Generate many coordinates to test bounds
        for _ in range(1000):
            lat, lng = self.plugin.generate_fake_coordinates()
            
            self.assertGreaterEqual(lat, 24.5)
            self.assertLessEqual(lat, 49.4)
            self.assertGreaterEqual(lng, -125.0)
            self.assertLessEqual(lng, -66.0)

    def test_empty_states_handling(self):
        """Test handling when states dictionary is empty."""
        original_states = self.plugin.STATES
        self.plugin.STATES = {}
        
        try:
            result = self.plugin.fetch_polling_places()
            self.assertEqual(len(result), 0)
        finally:
            self.plugin.STATES = original_states  # Restore


class TestDummyIntegration(unittest.TestCase):
    """Integration tests for Dummy plugin workflow."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_app = Mock()
        self.mock_app.logger = Mock()
        self.mock_db = Mock()
        self.mock_db.session = Mock()
        self.plugin = DummyPlugin(self.mock_app, self.mock_db)

    def test_complete_workflow(self):
        """Test complete workflow from data generation to validation."""
        with patch('plugins.dummy.random.randint', return_value=2):
            with patch.object(self.plugin, 'validate_polling_place_data', return_value=True):
                # Test polling places
                polling_places = self.plugin.fetch_polling_places()
                self.assertEqual(len(polling_places), 100)  # 50 states * 2 locations
                
                # Test precincts
                self.mock_db.session.query.return_value.all.return_value = []
                precincts = self.plugin.fetch_precincts()
                self.assertEqual(len(precincts), 200)  # 50 states * 2 locations * 2 precincts

    def test_data_consistency(self):
        """Test data consistency between polling places and precincts."""
        with patch('plugins.dummy.random.randint', return_value=1):
            with patch.object(self.plugin, 'validate_polling_place_data', return_value=True):
                polling_places = self.plugin.fetch_polling_places()
                self.mock_db.session.query.return_value.all.return_value = []
                precincts = self.plugin.fetch_precincts()
                
                # Check that all precinct polling place IDs exist in polling places
                polling_place_ids = {pp['id'] for pp in polling_places}
                for precinct in precincts:
                    self.assertIn(precinct['polling_place_id'], polling_place_ids)

    def test_state_distribution(self):
        """Test uniform distribution across states."""
        with patch('plugins.dummy.random.randint', return_value=1):
            with patch.object(self.plugin, 'validate_polling_place_data', return_value=True):
                result = self.plugin.fetch_polling_places()
                
                # Count locations per state
                state_counts = {}
                for location in result:
                    state = location['state']
                    state_counts[state] = state_counts.get(state, 0) + 1
                
                # Should have exactly 1 location per state
                self.assertEqual(len(state_counts), 50)
                for count in state_counts.values():
                    self.assertEqual(count, 1)

    def test_performance_with_large_dataset(self):
        """Test performance with large dataset generation."""
        import time
        
        start_time = time.time()
        
        with patch('plugins.dummy.random.randint', return_value=5):
            with patch.object(self.plugin, 'validate_polling_place_data', return_value=True):
                result = self.plugin.fetch_polling_places()
        
        end_time = time.time()
        generation_time = end_time - start_time
        
        # Should complete within reasonable time (5 seconds for 250 locations)
        self.assertLess(generation_time, 5.0)
        self.assertEqual(len(result), 250)  # 50 states * 5 locations

    def test_reproducible_generation(self):
        """Test that generation can be made reproducible."""
        # Set random seed for reproducible results
        with patch('plugins.dummy.random.randint', return_value=1):
            with patch.object(self.plugin, 'validate_polling_place_data', return_value=True):
                result1 = self.plugin.fetch_polling_places()
                result2 = self.plugin.fetch_polling_places()
                
                # Results should be identical with same parameters
                self.assertEqual(len(result1), len(result2))
                
                # Sort by ID for comparison
                result1_sorted = sorted(result1, key=lambda x: x['id'])
                result2_sorted = sorted(result2, key=lambda x: x['id'])
                
                for loc1, loc2 in zip(result1_sorted, result2_sorted):
                    self.assertEqual(loc1['id'], loc2['id'])
                    self.assertEqual(loc1['state'], loc2['state'])


if __name__ == '__main__':
    # Create test suite
    test_suite = unittest.TestSuite()
    
    # Add all test classes
    test_classes = [
        TestDummyDataGeneration,
        TestDummyPollingPlaces,
        TestDummyPrecincts,
        TestDummyErrorScenarios,
        TestDummyIntegration
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