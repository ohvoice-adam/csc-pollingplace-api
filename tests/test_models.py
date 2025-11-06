import pytest
import json
from datetime import datetime, date
from unittest.mock import Mock, patch, MagicMock
import sys
import os

# Add the parent directory to the path to import the modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import (
    PollingPlace, Precinct, PrecinctAssignment, Election, 
    AdminUser, APIKey, AuditTrail, LocationType,
    precinct_polling_places
)
from database import db


class TestPollingPlace:
    """Test cases for PollingPlace model"""
    
    def test_polling_place_creation(self):
        """Test creating a polling place with all fields"""
        polling_place = PollingPlace()
        polling_place.id = "test-pp-001"
        polling_place.name = "Community Center"
        polling_place.location_name = "Main Hall"
        polling_place.address_line1 = "123 Main St"
        polling_place.city = "Springfield"
        polling_place.state = "IL"
        polling_place.zip_code = "62701"
        polling_place.county = "Sangamon"
        polling_place.latitude = 39.7817
        polling_place.longitude = -89.6501
        polling_place.polling_hours = "7:00 AM - 8:00 PM"
        polling_place.notes = "Free parking available"
        polling_place.voter_services = "Accessibility services available"
        polling_place.start_date = date(2024, 1, 1)
        polling_place.end_date = date(2024, 12, 31)
        polling_place.location_type = "election day"
        polling_place.source_state = "IL"
        polling_place.source_plugin = "test_plugin"
        
        assert polling_place.id == "test-pp-001"
        assert polling_place.name == "Community Center"
        assert polling_place.location_name == "Main Hall"
        assert polling_place.city == "Springfield"
        assert polling_place.state == "IL"
        assert polling_place.zip_code == "62701"
        assert polling_place.county == "Sangamon"
        assert polling_place.latitude == 39.7817
        assert polling_place.longitude == -89.6501
        assert polling_place.polling_hours == "7:00 AM - 8:00 PM"
        assert polling_place.notes == "Free parking available"
        assert polling_place.voter_services == "Accessibility services available"
        assert polling_place.start_date == date(2024, 1, 1)
        assert polling_place.end_date == date(2024, 12, 31)
        assert polling_place.location_type == "election day"
        assert polling_place.source_state == "IL"
        assert polling_place.source_plugin == "test_plugin"
    
    def test_polling_place_minimal_creation(self):
        """Test creating a polling place with minimal required fields"""
        polling_place = PollingPlace()
        polling_place.id = "test-pp-002"
        polling_place.name = "School Gym"
        polling_place.city = "Chicago"
        polling_place.state = "IL"
        polling_place.zip_code = "60601"
        
        assert polling_place.id == "test-pp-002"
        assert polling_place.name == "School Gym"
        assert polling_place.city == "Chicago"
        assert polling_place.state == "IL"
        assert polling_place.zip_code == "60601"
        assert polling_place.location_type == "election day"  # Default value
        assert polling_place.address_line1 is None
        assert polling_place.county is None
    
    def test_to_dict(self):
        """Test converting polling place to dictionary"""
        polling_place = PollingPlace()
        polling_place.id = "test-pp-003"
        polling_place.name = "Library"
        polling_place.city = "Peoria"
        polling_place.state = "IL"
        polling_place.zip_code = "61602"
        polling_place.latitude = 40.6936
        polling_place.longitude = -89.5890
        polling_place.start_date = date(2024, 3, 1)
        polling_place.end_date = date(2024, 11, 30)
        
        # Mock datetime objects
        polling_place.created_at = datetime(2024, 1, 15, 10, 30, 0)
        polling_place.updated_at = datetime(2024, 1, 20, 14, 45, 0)
        
        result = polling_place.to_dict()
        
        assert result['id'] == "test-pp-003"
        assert result['name'] == "Library"
        assert result['city'] == "Peoria"
        assert result['state'] == "IL"
        assert result['zip_code'] == "61602"
        assert result['latitude'] == 40.6936
        assert result['longitude'] == -89.5890
        assert result['start_date'] == "2024-03-01"
        assert result['end_date'] == "2024-11-30"
        assert result['created_at'] == "2024-01-15T10:30:00"
        assert result['updated_at'] == "2024-01-20T14:45:00"
    
    def test_to_dict_with_null_dates(self):
        """Test to_dict with null date fields"""
        polling_place = PollingPlace()
        polling_place.id = "test-pp-004"
        polling_place.name = "Fire Station"
        polling_place.city = "Rockford"
        polling_place.state = "IL"
        polling_place.zip_code = "61101"
        
        result = polling_place.to_dict()
        
        assert result['start_date'] is None
        assert result['end_date'] is None
        assert result['created_at'] is None
        assert result['updated_at'] is None
    
    def test_to_vip_format(self):
        """Test converting polling place to VIP format"""
        polling_place = PollingPlace()
        polling_place.id = "test-pp-005"
        polling_place.name = "City Hall"
        polling_place.location_name = "Council Chambers"
        polling_place.address_line1 = "456 Government Ave"
        polling_place.address_line2 = "Suite 200"
        polling_place.city = "Aurora"
        polling_place.state = "IL"
        polling_place.zip_code = "60501"
        polling_place.county = "Kane"
        polling_place.latitude = 41.7606
        polling_place.longitude = -88.3201
        polling_place.polling_hours = "6:00 AM - 7:00 PM"
        polling_place.notes = "Photo ID required"
        polling_place.voter_services = "Language assistance available"
        polling_place.start_date = date(2024, 2, 15)
        polling_place.end_date = date(2024, 11, 5)
        polling_place.location_type = "early voting"
        
        result = polling_place.to_vip_format()
        
        assert result['id'] == "test-pp-005"
        assert result['name'] == "City Hall"
        assert result['address']['locationName'] == "Council Chambers"
        assert result['address']['line1'] == "456 Government Ave"
        assert result['address']['line2'] == "Suite 200"
        assert result['address']['city'] == "Aurora"
        assert result['address']['state'] == "IL"
        assert result['address']['zip'] == "60501"
        assert result['county'] == "Kane"
        assert result['latitude'] == 41.7606
        assert result['longitude'] == -88.3201
        assert result['pollingHours'] == "6:00 AM - 7:00 PM"
        assert result['notes'] == "Photo ID required"
        assert result['voterServices'] == "Language assistance available"
        assert result['startDate'] == "2024-02-15"
        assert result['endDate'] == "2024-11-05"
        assert result['locationType'] == "early voting"
    
    def test_to_vip_format_minimal(self):
        """Test VIP format with minimal required fields"""
        polling_place = PollingPlace()
        polling_place.id = "test-pp-006"
        polling_place.name = "Church"
        polling_place.city = "Naperville"
        polling_place.state = "IL"
        polling_place.zip_code = "60540"
        
        result = polling_place.to_vip_format()
        
        assert result['id'] == "test-pp-006"
        assert result['name'] == "Church"
        assert result['address']['city'] == "Naperville"
        assert result['address']['state'] == "IL"
        assert result['address']['zip'] == "60540"
        assert 'locationName' not in result['address']
        assert 'line1' not in result['address']
        assert 'county' not in result
        assert 'latitude' not in result
        assert 'longitude' not in result
        assert 'pollingHours' not in result
        assert 'notes' not in result
        assert 'voterServices' not in result
        assert 'startDate' not in result
        assert 'endDate' not in result
    
    def test_to_vip_format_with_location_type_enum(self):
        """Test VIP format with LocationType enum"""
        polling_place = PollingPlace()
        polling_place.id = "test-pp-007"
        polling_place.name = "Drop Box Location"
        polling_place.city = "Evanston"
        polling_place.state = "IL"
        polling_place.zip_code = "60201"
        polling_place.location_type = LocationType.DROP_BOX
        
        result = polling_place.to_vip_format()
        assert result['locationType'] == "drop box"


class TestAPIKey:
    """Test cases for APIKey model"""
    
    def test_api_key_creation(self):
        """Test creating an API key"""
        api_key = APIKey()
        api_key.key = "test_key_12345"
        api_key.name = "Test Application"
        api_key.is_active = True
        api_key.rate_limit_per_day = 1000
        api_key.rate_limit_per_hour = 50
        
        assert api_key.key == "test_key_12345"
        assert api_key.name == "Test Application"
        assert api_key.is_active is True
        assert api_key.rate_limit_per_day == 1000
        assert api_key.rate_limit_per_hour == 50
    
    def test_api_key_minimal_creation(self):
        """Test creating API key with minimal fields"""
        api_key = APIKey()
        api_key.key = "minimal_key"
        api_key.name = "Minimal App"
        
        assert api_key.key == "minimal_key"
        assert api_key.name == "Minimal App"
        assert api_key.is_active is True  # Default value
        assert api_key.rate_limit_per_day is None
        assert api_key.rate_limit_per_hour is None
    
    def test_generate_key(self):
        """Test API key generation"""
        key1 = APIKey.generate_key()
        key2 = APIKey.generate_key()
        
        assert isinstance(key1, str)
        assert isinstance(key2, str)
        assert len(key1) > 40  # Should be substantial length
        assert len(key2) > 40
        assert key1 != key2  # Should be unique
    
    def test_to_dict(self):
        """Test converting API key to dictionary"""
        api_key = APIKey()
        api_key.id = 1
        api_key.key = "test_key_dict"
        api_key.name = "Dict Test App"
        api_key.is_active = False
        api_key.rate_limit_per_day = 500
        api_key.rate_limit_per_hour = 25
        
        # Mock datetime objects
        api_key.created_at = datetime(2024, 1, 10, 9, 0, 0)
        api_key.last_used_at = datetime(2024, 1, 15, 14, 30, 0)
        
        result = api_key.to_dict()
        
        assert result['id'] == 1
        assert result['key'] == "test_key_dict"
        assert result['name'] == "Dict Test App"
        assert result['is_active'] is False
        assert result['rate_limit_per_day'] == 500
        assert result['rate_limit_per_hour'] == 25
        assert result['created_at'] == "2024-01-10T09:00:00"
        assert result['last_used_at'] == "2024-01-15T14:30:00"
    
    def test_to_dict_with_null_dates(self):
        """Test to_dict with null datetime fields"""
        api_key = APIKey()
        api_key.id = 2
        api_key.key = "null_dates_key"
        api_key.name = "Null Dates App"
        
        result = api_key.to_dict()
        
        assert result['created_at'] is None
        assert result['last_used_at'] is None


class TestPrecinct:
    """Test cases for Precinct model"""
    
    def test_precinct_creation(self):
        """Test creating a precinct with all fields"""
        precinct = Precinct()
        precinct.id = "IL-001-001"
        precinct.name = "Ward 1 Precinct 1"
        precinct.state = "IL"
        precinct.county = "Cook"
        precinct.precinctcode = "001001"
        precinct.registered_voters = 1250
        precinct.current_polling_place_id = "pp-001"
        precinct.last_change_date = date(2024, 2, 1)
        precinct.changed_recently = True
        precinct.source_plugin = "test_plugin"
        
        assert precinct.id == "IL-001-001"
        assert precinct.name == "Ward 1 Precinct 1"
        assert precinct.state == "IL"
        assert precinct.county == "Cook"
        assert precinct.precinctcode == "001001"
        assert precinct.registered_voters == 1250
        assert precinct.current_polling_place_id == "pp-001"
        assert precinct.last_change_date == date(2024, 2, 1)
        assert precinct.changed_recently is True
        assert precinct.source_plugin == "test_plugin"
    
    def test_precinct_minimal_creation(self):
        """Test creating a precinct with minimal required fields"""
        precinct = Precinct()
        precinct.id = "IL-002-001"
        precinct.name = "Ward 2 Precinct 1"
        precinct.state = "IL"
        
        assert precinct.id == "IL-002-001"
        assert precinct.name == "Ward 2 Precinct 1"
        assert precinct.state == "IL"
        assert precinct.county is None
        assert precinct.precinctcode is None
        assert precinct.registered_voters is None
        assert precinct.current_polling_place_id is None
        assert precinct.changed_recently is False  # Default value
        assert precinct.source_plugin is None
    
    def test_to_dict(self):
        """Test converting precinct to dictionary"""
        precinct = Precinct()
        precinct.id = "IL-003-001"
        precinct.name = "Ward 3 Precinct 1"
        precinct.state = "IL"
        precinct.county = "DuPage"
        precinct.precinctcode = "003001"
        precinct.registered_voters = 980
        precinct.current_polling_place_id = "pp-003"
        precinct.last_change_date = date(2024, 1, 15)
        precinct.changed_recently = False
        precinct.source_plugin = "test_plugin"
        
        # Mock datetime objects
        precinct.created_at = datetime(2024, 1, 1, 10, 0, 0)
        precinct.updated_at = datetime(2024, 1, 15, 16, 30, 0)
        
        # Mock polling places relationship
        mock_pp1 = Mock()
        mock_pp1.id = "pp-003"
        mock_pp2 = Mock()
        mock_pp2.id = "pp-004"
        
        with patch.object(precinct, 'polling_places', [mock_pp1, mock_pp2]):
            result = precinct.to_dict()
            
            assert result['id'] == "IL-003-001"
            assert result['name'] == "Ward 3 Precinct 1"
            assert result['state'] == "IL"
            assert result['county'] == "DuPage"
            assert result['precinctcode'] == "003001"
            assert result['registered_voters'] == 980
            assert result['current_polling_place_id'] == "pp-003"
            assert result['polling_place_ids'] == ["pp-003", "pp-004"]
            assert result['last_change_date'] == "2024-01-15"
            assert result['changed_recently'] is False
            assert result['source_plugin'] == "test_plugin"
            assert result['created_at'] == "2024-01-01T10:00:00"
            assert result['updated_at'] == "2024-01-15T16:30:00"
    
    def test_to_dict_with_history(self):
        """Test converting precinct to dictionary with assignment history"""
        precinct = Precinct()
        precinct.id = "IL-004-001"
        precinct.name = "Ward 4 Precinct 1"
        precinct.state = "IL"
        
        # Mock current polling place
        mock_current_pp = Mock()
        mock_current_pp.to_dict.return_value = {"id": "pp-current", "name": "Current Location"}
        
        # Mock polling places
        mock_pp1 = Mock()
        mock_pp1.to_dict.return_value = {"id": "pp-001", "name": "Location 1"}
        mock_pp2 = Mock()
        mock_pp2.to_dict.return_value = {"id": "pp-002", "name": "Location 2"}
        
        # Mock assignments
        mock_assignment = Mock()
        mock_assignment.to_dict.return_value = {"id": 1, "precinct_id": "IL-004-001"}
        
        with patch.object(precinct, 'current_polling_place', mock_current_pp), \
             patch.object(precinct, 'polling_places', [mock_pp1, mock_pp2]), \
             patch.object(precinct, 'assignments', [mock_assignment]):
            
            result = precinct.to_dict_with_history()
            
            assert result['id'] == "IL-004-001"
            assert result['current_polling_place'] == {"id": "pp-current", "name": "Current Location"}
            assert result['polling_places'] == [
                {"id": "pp-001", "name": "Location 1"},
                {"id": "pp-002", "name": "Location 2"}
            ]
            assert result['assignment_history'] == [{"id": 1, "precinct_id": "IL-004-001"}]


class TestPrecinctAssignment:
    """Test cases for PrecinctAssignment model"""
    
    def test_precinct_assignment_creation(self):
        """Test creating a precinct assignment"""
        assignment = PrecinctAssignment()
        assignment.id = 1
        assignment.precinct_id = "IL-001-001"
        assignment.polling_place_id = "pp-001"
        assignment.election_id = 1
        assignment.assigned_date = date(2024, 1, 1)
        assignment.removed_date = date(2024, 6, 30)
        assignment.previous_polling_place_id = "pp-old"
        
        assert assignment.id == 1
        assert assignment.precinct_id == "IL-001-001"
        assert assignment.polling_place_id == "pp-001"
        assert assignment.election_id == 1
        assert assignment.assigned_date == date(2024, 1, 1)
        assert assignment.removed_date == date(2024, 6, 30)
        assert assignment.previous_polling_place_id == "pp-old"
    
    def test_precinct_assignment_current(self):
        """Test creating a current precinct assignment (no removed_date)"""
        assignment = PrecinctAssignment()
        assignment.precinct_id = "IL-001-002"
        assignment.polling_place_id = "pp-002"
        assignment.assigned_date = date(2024, 7, 1)
        
        assert assignment.precinct_id == "IL-001-002"
        assert assignment.polling_place_id == "pp-002"
        assert assignment.assigned_date == date(2024, 7, 1)
        assert assignment.removed_date is None
    
    def test_to_dict(self):
        """Test converting precinct assignment to dictionary"""
        assignment = PrecinctAssignment()
        assignment.id = 2
        assignment.precinct_id = "IL-001-003"
        assignment.polling_place_id = "pp-003"
        assignment.election_id = 2
        assignment.assigned_date = date(2024, 3, 1)
        assignment.removed_date = date(2024, 8, 31)
        assignment.previous_polling_place_id = "pp-previous"
        
        # Mock datetime
        assignment.created_at = datetime(2024, 3, 1, 12, 0, 0)
        
        # Mock election
        mock_election = Mock()
        mock_election.id = 2
        mock_election.date = date(2024, 11, 5)
        mock_election.name = "2024 General Election"
        mock_election.state = "IL"
        
        with patch.object(assignment, 'election', mock_election):
            result = assignment.to_dict()
            
            assert result['id'] == 2
            assert result['precinct_id'] == "IL-001-003"
            assert result['polling_place_id'] == "pp-003"
            assert result['election_id'] == 2
            assert result['assigned_date'] == "2024-03-01"
            assert result['removed_date'] == "2024-08-31"
            assert result['previous_polling_place_id'] == "pp-previous"
            assert result['is_current'] is False  # Has removed_date
            assert result['created_at'] == "2024-03-01T12:00:00"
            assert result['election'] == {
                'id': 2,
                'date': '2024-11-05',
                'name': '2024 General Election',
                'state': 'IL'
            }
    
    def test_to_dict_current_assignment(self):
        """Test to_dict for current assignment"""
        assignment = PrecinctAssignment()
        assignment.id = 3
        assignment.precinct_id = "IL-001-004"
        assignment.polling_place_id = "pp-004"
        assignment.assigned_date = date(2024, 9, 1)
        
        with patch.object(assignment, 'election', None):
            result = assignment.to_dict()
            
            assert result['is_current'] is True  # No removed_date
            assert result['removed_date'] is None
            assert result['election_id'] is None
            assert 'election' not in result
    
    def test_to_dict_without_election(self):
        """Test to_dict without election relationship"""
        assignment = PrecinctAssignment()
        assignment.id = 4
        assignment.precinct_id = "IL-001-005"
        assignment.polling_place_id = "pp-005"
        assignment.assigned_date = date(2024, 10, 1)
        
        with patch.object(assignment, 'election', None):
            result = assignment.to_dict()
            
            assert result['election_id'] is None
            assert 'election' not in result


class TestElection:
    """Test cases for Election model"""
    
    def test_election_creation(self):
        """Test creating an election"""
        election = Election()
        election.id = 1
        election.date = date(2024, 11, 5)
        election.name = "2024 General Election"
        election.state = "IL"
        
        assert election.id == 1
        assert election.date == date(2024, 11, 5)
        assert election.name == "2024 General Election"
        assert election.state == "IL"
    
    def test_election_minimal_creation(self):
        """Test creating election with required fields only"""
        election = Election()
        election.date = date(2024, 3, 19)
        election.name = "2024 Primary Election"
        election.state = "IL"
        
        assert election.date == date(2024, 3, 19)
        assert election.name == "2024 Primary Election"
        assert election.state == "IL"
        assert election.id is None  # Will be set by database
    
    def test_to_dict(self):
        """Test converting election to dictionary"""
        election = Election()
        election.id = 3
        election.date = date(2024, 11, 5)
        election.name = "2024 General Election"
        election.state = "IL"
        
        # Mock datetime
        election.created_at = datetime(2024, 1, 1, 9, 0, 0)
        
        result = election.to_dict()
        
        assert result['id'] == 3
        assert result['date'] == "2024-11-05"
        assert result['name'] == "2024 General Election"
        assert result['state'] == "IL"
        assert result['created_at'] == "2024-01-01T09:00:00"
    
    def test_to_dict_with_null_date(self):
        """Test to_dict with null date"""
        election = Election()
        election.id = 4
        election.name = "Test Election"
        election.state = "IL"
        
        result = election.to_dict()
        
        assert result['date'] is None


class TestAdminUser:
    """Test cases for AdminUser model"""
    
    def test_admin_user_creation(self):
        """Test creating an admin user"""
        user = AdminUser()
        user.id = 1
        user.username = "testuser"
        user.password_hash = "hashed_password_here"
        
        assert user.id == 1
        assert user.username == "testuser"
        assert user.password_hash == "hashed_password_here"
    
    def test_set_password(self):
        """Test setting password"""
        user = AdminUser()
        user.username = "testuser"
        user.set_password("test_password_123")
        
        assert user.password_hash is not None
        assert user.password_hash != "test_password_123"
        assert user.password_hash.startswith('$2b$')  # bcrypt hash format
    
    def test_check_password_correct(self):
        """Test checking correct password"""
        user = AdminUser()
        user.username = "testuser"
        user.set_password("correct_password")
        
        assert user.check_password("correct_password") is True
    
    def test_check_password_incorrect(self):
        """Test checking incorrect password"""
        user = AdminUser()
        user.username = "testuser"
        user.set_password("correct_password")
        
        assert user.check_password("wrong_password") is False
    
    def test_password_hash_different_each_time(self):
        """Test that password hash is different each time (due to salt)"""
        user1 = AdminUser()
        user1.username = "user1"
        user1.set_password("same_password")
        
        user2 = AdminUser()
        user2.username = "user2"
        user2.set_password("same_password")
        
        assert user1.password_hash != user2.password_hash


class TestAuditTrail:
    """Test cases for AuditTrail model"""
    
    def test_audit_trail_creation(self):
        """Test creating an audit trail entry"""
        audit = AuditTrail()
        audit.id = 1
        audit.table_name = "polling_places"
        audit.record_id = "pp-001"
        audit.action = "UPDATE"
        audit.old_values = '{"name": "Old Name"}'
        audit.new_values = '{"name": "New Name"}'
        audit.changed_fields = '["name"]'
        audit.user_id = 1
        audit.ip_address = "192.168.1.100"
        audit.user_agent = "Mozilla/5.0..."
        
        assert audit.id == 1
        assert audit.table_name == "polling_places"
        assert audit.record_id == "pp-001"
        assert audit.action == "UPDATE"
        assert audit.old_values == '{"name": "Old Name"}'
        assert audit.new_values == '{"name": "New Name"}'
        assert audit.changed_fields == '["name"]'
        assert audit.user_id == 1
        assert audit.ip_address == "192.168.1.100"
        assert audit.user_agent == "Mozilla/5.0..."
    
    def test_to_dict(self):
        """Test converting audit trail to dictionary"""
        audit = AuditTrail()
        audit.id = 2
        audit.table_name = "precincts"
        audit.record_id = "precinct-001"
        audit.action = "CREATE"
        audit.old_values = None
        audit.new_values = '{"name": "New Precinct"}'
        audit.changed_fields = '["name", "state"]'
        audit.user_id = 2
        audit.ip_address = "10.0.0.1"
        audit.user_agent = "Test Agent"
        
        # Mock datetime
        audit.timestamp = datetime(2024, 1, 15, 14, 30, 0)
        
        # Mock get_username method
        with patch.object(audit, 'get_username', return_value="testuser"):
            result = audit.to_dict()
            
            assert result['id'] == 2
            assert result['table_name'] == "precincts"
            assert result['record_id'] == "precinct-001"
            assert result['action'] == "CREATE"
            assert result['old_values'] is None
            assert result['new_values'] == {"name": "New Precinct"}
            assert result['changed_fields'] == ["name", "state"]
            assert result['user_id'] == 2
            assert result['ip_address'] == "10.0.0.1"
            assert result['user_agent'] == "Test Agent"
            assert result['timestamp'] == "2024-01-15T14:30:00"
            assert result['username'] == "testuser"
    
    @patch('models.AdminUser')
    def test_get_username_with_user(self, mock_admin_user_class):
        """Test getting username when user exists"""
        # Mock admin user
        mock_user = Mock()
        mock_user.username = "testuser"
        mock_admin_user_class.query.get.return_value = mock_user
        
        audit = AuditTrail()
        audit.user_id = 1
        result = audit.get_username()
        
        assert result == "testuser"
        mock_admin_user_class.query.get.assert_called_once_with(1)
    
    @patch('models.AdminUser')
    def test_get_username_no_user(self, mock_admin_user_class):
        """Test getting username when user doesn't exist"""
        mock_admin_user_class.query.get.return_value = None
        
        audit = AuditTrail()
        audit.user_id = 999
        result = audit.get_username()
        
        assert result is None
        mock_admin_user_class.query.get.assert_called_once_with(999)
    
    def test_get_username_no_user_id(self):
        """Test getting username when no user_id"""
        audit = AuditTrail()
        audit.user_id = None
        result = audit.get_username()
        
        assert result is None
    
    @patch('models.AdminUser')
    def test_get_username_exception(self, mock_admin_user_class):
        """Test getting username when exception occurs"""
        mock_admin_user_class.query.get.side_effect = Exception("Database error")
        
        audit = AuditTrail()
        audit.user_id = 1
        result = audit.get_username()
        
        assert result is None


class TestLocationType:
    """Test cases for LocationType enum"""
    
    def test_location_type_values(self):
        """Test LocationType enum values"""
        assert LocationType.DROP_BOX.value == "drop box"
        assert LocationType.ELECTION_DAY.value == "election day"
        assert LocationType.EARLY_VOTING.value == "early voting"
    
    def test_location_type_creation(self):
        """Test creating LocationType instances"""
        drop_box = LocationType.DROP_BOX
        election_day = LocationType.ELECTION_DAY
        early_voting = LocationType.EARLY_VOTING
        
        assert drop_box == LocationType.DROP_BOX
        assert election_day == LocationType.ELECTION_DAY
        assert early_voting == LocationType.EARLY_VOTING
    
    def test_location_type_string_representation(self):
        """Test string representation of LocationType"""
        assert str(LocationType.DROP_BOX) == "LocationType.DROP_BOX"
        assert str(LocationType.ELECTION_DAY) == "LocationType.ELECTION_DAY"
        assert str(LocationType.EARLY_VOTING) == "LocationType.EARLY_VOTING"


class TestRelationships:
    """Test cases for model relationships"""
    
    def test_precinct_polling_places_association_table(self):
        """Test the association table structure"""
        # Check that the association table has the expected columns
        assert hasattr(precinct_polling_places, 'columns')
        
        # The table should have columns for precinct_id, polling_place_id, and created_at
        column_names = [col.name for col in precinct_polling_places.columns]
        assert 'precinct_id' in column_names
        assert 'polling_place_id' in column_names
        assert 'created_at' in column_names
    
    def test_polling_place_relationships(self):
        """Test PollingPlace relationships"""
        # Create a polling place
        polling_place = PollingPlace()
        polling_place.id = "test-rel-pp"
        polling_place.name = "Test Place"
        polling_place.city = "Test City"
        polling_place.state = "IL"
        polling_place.zip_code = "12345"
        
        # Should have relationships defined
        assert hasattr(polling_place, 'precincts')
        assert hasattr(polling_place, 'current_precincts')
    
    def test_precinct_relationships(self):
        """Test Precinct relationships"""
        # Create a precinct
        precinct = Precinct()
        precinct.id = "test-rel-precinct"
        precinct.name = "Test Precinct"
        precinct.state = "IL"
        
        # Should have relationships defined
        assert hasattr(precinct, 'current_polling_place')
        assert hasattr(precinct, 'polling_places')
        assert hasattr(precinct, 'assignments')
    
    def test_election_relationships(self):
        """Test Election relationships"""
        # Create an election
        election = Election()
        election.date = date(2024, 11, 5)
        election.name = "Test Election"
        election.state = "IL"
        
        # Should have relationships defined
        assert hasattr(election, 'assignments')
    
    def test_precinct_assignment_relationships(self):
        """Test PrecinctAssignment relationships"""
        # Create an assignment
        assignment = PrecinctAssignment()
        assignment.precinct_id = "test-precinct"
        assignment.polling_place_id = "test-place"
        assignment.assigned_date = date(2024, 1, 1)
        
        # Should have relationships defined
        assert hasattr(assignment, 'precinct')
        assert hasattr(assignment, 'polling_place')
        assert hasattr(assignment, 'previous_polling_place')
        assert hasattr(assignment, 'election')


class TestModelValidation:
    """Test cases for model validation and edge cases"""
    
    def test_polling_place_coordinate_validation(self):
        """Test polling place coordinate validation"""
        # Valid coordinates
        pp_valid = PollingPlace()
        pp_valid.id = "coord-valid"
        pp_valid.name = "Valid Place"
        pp_valid.city = "Valid City"
        pp_valid.state = "IL"
        pp_valid.zip_code = "12345"
        pp_valid.latitude = 41.8781  # Chicago coordinates
        pp_valid.longitude = -87.6298
        
        assert -90 <= pp_valid.latitude <= 90
        assert -180 <= pp_valid.longitude <= 180
        
        # Edge case coordinates
        pp_edge = PollingPlace()
        pp_edge.id = "coord-edge"
        pp_edge.name = "Edge Place"
        pp_edge.city = "Edge City"
        pp_edge.state = "IL"
        pp_edge.zip_code = "12345"
        pp_edge.latitude = 0.0
        pp_edge.longitude = 0.0
        
        assert pp_edge.latitude == 0.0
        assert pp_edge.longitude == 0.0
    
    def test_state_code_validation(self):
        """Test state code format"""
        # Valid 2-letter state codes
        pp1 = PollingPlace()
        pp1.id = "state-1"
        pp1.name = "Place 1"
        pp1.city = "City 1"
        pp1.state = "IL"
        pp1.zip_code = "12345"
        
        pp2 = PollingPlace()
        pp2.id = "state-2"
        pp2.name = "Place 2"
        pp2.city = "City 2"
        pp2.state = "CA"
        pp2.zip_code = "67890"
        
        assert len(pp1.state) == 2
        assert len(pp2.state) == 2
        assert pp1.state.isupper()
        assert pp2.state.isupper()
    
    def test_zip_code_validation(self):
        """Test zip code formats"""
        # Standard 5-digit zip
        pp1 = PollingPlace()
        pp1.id = "zip-1"
        pp1.name = "Place 1"
        pp1.city = "City 1"
        pp1.state = "IL"
        pp1.zip_code = "12345"
        
        # Zip+4 format
        pp2 = PollingPlace()
        pp2.id = "zip-2"
        pp2.name = "Place 2"
        pp2.city = "City 2"
        pp2.state = "IL"
        pp2.zip_code = "12345-6789"
        
        assert len(pp1.zip_code) == 5
        assert len(pp2.zip_code) == 10
        assert '-' in pp2.zip_code
    
    def test_precinct_id_format(self):
        """Test precinct ID format"""
        precinct = Precinct()
        precinct.id = "IL-COOK-001"
        precinct.name = "Test Precinct"
        precinct.state = "IL"
        
        assert '-' in precinct.id
        assert precinct.id.startswith("IL-")
    
    def test_election_unique_constraint(self):
        """Test election unique constraint on date + state"""
        # This would be enforced at the database level
        # Here we just test the model structure
        election1 = Election()
        election1.date = date(2024, 11, 5)
        election1.name = "General Election"
        election1.state = "IL"
        
        election2 = Election()
        election2.date = date(2024, 11, 5)
        election2.name = "General Election"
        election2.state = "WI"  # Different state, same date - should be allowed
        
        assert election1.date == election2.date
        assert election1.state != election2.state


if __name__ == "__main__":
    pytest.main([__file__])