"""
Data validation utilities for geographic coordinates and other critical fields
"""

import re
from datetime import datetime
from typing import Tuple, Optional, Dict, Any


class ValidationError(Exception):
    """Custom validation error"""
    pass


class DataValidator:
    """Validator for various data types"""
    
    @staticmethod
    def validate_coordinates(latitude: Any, longitude: Any) -> Tuple[bool, Optional[str]]:
        """
        Validate geographic coordinates
        
        Args:
            latitude: Latitude value
            longitude: Longitude value
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            # Convert to float if possible
            lat = float(latitude) if latitude is not None else None
            lon = float(longitude) if longitude is not None else None
            
            # Validate latitude
            if lat is not None:
                if not (-90 <= lat <= 90):
                    return False, "Latitude must be between -90 and 90 degrees"
                if abs(lat) > 85:  # Near poles warning
                    pass  # Could add warning system
            
            # Validate longitude
            if lon is not None:
                if not (-180 <= lon <= 180):
                    return False, "Longitude must be between -180 and 180 degrees"
            
            return True, None
            
        except (ValueError, TypeError):
            return False, "Coordinates must be valid numbers"
    
    @staticmethod
    def validate_zip_code(zip_code: str, country: str = 'US') -> Tuple[bool, Optional[str]]:
        """
        Validate ZIP/postal code format
        
        Args:
            zip_code: ZIP code to validate
            country: Country code for format rules
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        if not zip_code:
            return True, None  # Optional field
        
        zip_code = str(zip_code).strip()
        
        if country.upper() == 'US':
            # US ZIP code format: 5 digits or 5+4 format
            if not re.match(r'^\d{5}(-\d{4})?$', zip_code):
                return False, "US ZIP code must be 5 digits or 5+4 format (e.g., 12345 or 12345-6789)"
        
        return True, None
    
    @staticmethod
    def validate_state_code(state_code: str) -> Tuple[bool, Optional[str]]:
        """
        Validate US state code
        
        Args:
            state_code: State code to validate
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        if not state_code:
            return False, "State code is required"
        
        state_code = str(state_code).strip().upper()
        
        # List of valid US state and territory codes
        valid_states = {
            'AL', 'AK', 'AZ', 'AR', 'CA', 'CO', 'CT', 'DE', 'FL', 'GA',
            'HI', 'ID', 'IL', 'IN', 'IA', 'KS', 'KY', 'LA', 'ME', 'MD',
            'MA', 'MI', 'MN', 'MS', 'MO', 'MT', 'NE', 'NV', 'NH', 'NJ',
            'NM', 'NY', 'NC', 'ND', 'OH', 'OK', 'OR', 'PA', 'RI', 'SC',
            'SD', 'TN', 'TX', 'UT', 'VT', 'VA', 'WA', 'WV', 'WI', 'WY',
            'DC', 'PR', 'VI', 'GU', 'AS', 'MP'
        }
        
        if state_code not in valid_states:
            return False, f"Invalid state code: {state_code}. Must be a valid US state or territory code."
        
        return True, None
    
    @staticmethod
    def validate_phone_number(phone: str) -> Tuple[bool, Optional[str]]:
        """
        Validate phone number format
        
        Args:
            phone: Phone number to validate
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        if not phone:
            return True, None  # Optional field
        
        phone = str(phone).strip()
        
        # Remove common formatting characters
        clean_phone = re.sub(r'[^\d]', '', phone)
        
        # Check if it's 10 digits (US standard) or 11 digits (with country code)
        if len(clean_phone) == 10:
            return True, None
        elif len(clean_phone) == 11 and clean_phone.startswith('1'):
            return True, None
        else:
            return False, "Phone number must be 10 digits (US format) or 11 digits with country code"
    
    @staticmethod
    def validate_email(email: str) -> Tuple[bool, Optional[str]]:
        """
        Validate email format
        
        Args:
            email: Email address to validate
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        if not email:
            return True, None  # Optional field
        
        email = str(email).strip()
        
        # Basic email regex
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        
        if not re.match(email_pattern, email):
            return False, "Invalid email format"
        
        return True, None
    
    @staticmethod
    def validate_date(date_str: str, date_format: str = '%Y-%m-%d') -> Tuple[bool, Optional[str], Optional[datetime]]:
        """
        Validate date string
        
        Args:
            date_str: Date string to validate
            date_format: Expected date format
            
        Returns:
            Tuple of (is_valid, error_message, datetime_object)
        """
        if not date_str:
            return True, None, None  # Optional field
        
        try:
            date_obj = datetime.strptime(str(date_str).strip(), date_format)
            return True, None, date_obj
        except ValueError:
            return False, f"Date must be in format {date_format}", None
    
    @staticmethod
    def validate_positive_integer(value: Any, field_name: str = "Value") -> Tuple[bool, Optional[str], Optional[int]]:
        """
        Validate positive integer
        
        Args:
            value: Value to validate
            field_name: Name of the field for error messages
            
        Returns:
            Tuple of (is_valid, error_message, integer_value)
        """
        if value is None:
            return True, None, None  # Optional field
        
        try:
            int_value = int(value)
            if int_value < 0:
                return False, f"{field_name} must be a positive integer", None
            return True, None, int_value
        except (ValueError, TypeError):
            return False, f"{field_name} must be a valid integer", None
    
    @staticmethod
    def validate_string_length(value: str, min_length: int = 0, max_length: int = 255, 
                              field_name: str = "Field") -> Tuple[bool, Optional[str]]:
        """
        Validate string length
        
        Args:
            value: String to validate
            min_length: Minimum required length
            max_length: Maximum allowed length
            field_name: Name of the field for error messages
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        if value is None:
            if min_length > 0:
                return False, f"{field_name} is required"
            return True, None
        
        str_value = str(value).strip()
        length = len(str_value)
        
        if length < min_length:
            return False, f"{field_name} must be at least {min_length} characters long"
        
        if length > max_length:
            return False, f"{field_name} must be no more than {max_length} characters long"
        
        return True, None
    
    @staticmethod
    def validate_polling_place_data(data: Dict[str, Any]) -> Tuple[bool, Dict[str, str]]:
        """
        Validate complete polling place data
        
        Args:
            data: Dictionary containing polling place data
            
        Returns:
            Tuple of (is_valid, errors_dict)
        """
        errors = {}
        
        # Required fields
        required_fields = ['id', 'name', 'city', 'state', 'zip_code']
        for field in required_fields:
            if not data.get(field) or str(data[field]).strip() == '':
                errors[field] = f"{field.replace('_', ' ').title()} is required"
        
        # State code validation
        if 'state' in data:
            is_valid, error = DataValidator.validate_state_code(data['state'])
            if not is_valid:
                errors['state'] = error
        
        # ZIP code validation
        if 'zip_code' in data:
            is_valid, error = DataValidator.validate_zip_code(data['zip_code'])
            if not is_valid:
                errors['zip_code'] = error
        
        # Coordinates validation
        lat = data.get('latitude')
        lon = data.get('longitude')
        if lat is not None or lon is not None:
            is_valid, error = DataValidator.validate_coordinates(lat, lon)
            if not is_valid:
                errors['coordinates'] = error
        
        # String length validations
        string_fields = {
            'name': (1, 200),
            'city': (1, 100),
            'county': (0, 100),
            'address_line1': (0, 200),
            'address_line2': (0, 200),
            'address_line3': (0, 200),
            'polling_hours': (0, 200),
            'source_plugin': (0, 100)
        }
        
        for field, (min_len, max_len) in string_fields.items():
            if field in data:
                is_valid, error = DataValidator.validate_string_length(
                    data[field], min_len, max_len, field.replace('_', ' ').title()
                )
                if not is_valid:
                    errors[field] = error
        
        return len(errors) == 0, errors
    
    @staticmethod
    def validate_precinct_data(data: Dict[str, Any]) -> Tuple[bool, Dict[str, str]]:
        """
        Validate complete precinct data
        
        Args:
            data: Dictionary containing precinct data
            
        Returns:
            Tuple of (is_valid, errors_dict)
        """
        errors = {}
        
        # Required fields
        required_fields = ['id', 'name', 'state']
        for field in required_fields:
            if not data.get(field) or str(data[field]).strip() == '':
                errors[field] = f"{field.replace('_', ' ').title()} is required"
        
        # State code validation
        if 'state' in data:
            is_valid, error = DataValidator.validate_state_code(data['state'])
            if not is_valid:
                errors['state'] = error
        
        # Registered voters validation
        if 'registered_voters' in data:
            is_valid, error, int_val = DataValidator.validate_positive_integer(
                data['registered_voters'], 'Registered Voters'
            )
            if not is_valid:
                errors['registered_voters'] = error
        
        # String length validations
        string_fields = {
            'name': (1, 200),
            'county': (0, 100),
            'source_plugin': (0, 100)
        }
        
        for field, (min_len, max_len) in string_fields.items():
            if field in data:
                is_valid, error = DataValidator.validate_string_length(
                    data[field], min_len, max_len, field.replace('_', ' ').title()
                )
                if not is_valid:
                    errors[field] = error
        
        return len(errors) == 0, errors


def validate_model_data(model_type: str, data: Dict[str, Any]) -> Tuple[bool, Dict[str, str]]:
    """
    Factory function to validate data based on model type
    
    Args:
        model_type: Type of model ('polling_place' or 'precinct')
        data: Data to validate
        
    Returns:
        Tuple of (is_valid, errors_dict)
    """
    if model_type == 'polling_place':
        return DataValidator.validate_polling_place_data(data)
    elif model_type == 'precinct':
        return DataValidator.validate_precinct_data(data)
    else:
        raise ValueError(f"Unknown model type: {model_type}")