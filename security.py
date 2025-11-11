"""
Security utilities and validators for CSC Polling Place API

This module provides comprehensive security functions including:
- Input validation and sanitization
- XSS protection
- SQL injection prevention
- Rate limiting enhancements
- Security logging
- API key security
"""

import re
import html
import hashlib
import secrets
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union
from flask import request, g, current_app
from werkzeug.security import check_password_hash
import bleach

# Security logger
security_logger = logging.getLogger('security')

# XSS protection configuration
ALLOWED_TAGS = ['p', 'br', 'strong', 'em', 'u', 'ul', 'ol', 'li', 'a']
ALLOWED_ATTRIBUTES = {
    'a': ['href', 'title'],
    '*': ['class']
}

# Input validation patterns
PATTERNS = {
    'state_code': re.compile(r'^[A-Za-z]{2}$'),
    'zip_code': re.compile(r'^\d{5}(-\d{4})?$'),
    'latitude': re.compile(r'^-?90?\d*\.\d+$'),
    'longitude': re.compile(r'^-?180?\d*\.\d+$'),
    'email': re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'),
    'api_key_name': re.compile(r'^[a-zA-Z0-9\s\-_]{1,255}$'),
    'plugin_name': re.compile(r'^[a-zA-Z0-9_\-]{1,50}$'),
    'election_id': re.compile(r'^\d+$'),
    'filename': re.compile(r'^[a-zA-Z0-9._-]{1,255}$'),
    'sort_column': re.compile(r'^[a-zA-Z_][a-zA-Z0-9_]*$'),
    'search_query': re.compile(r'^[a-zA-Z0-9\s\-_.,@#%]{1,500}$')
}

# SQL injection detection patterns
SQL_INJECTION_PATTERNS = [
    re.compile(r"(\b(SELECT|INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|EXEC|UNION|SCRIPT)\b)", re.IGNORECASE),
    re.compile(r"(\-\-|\#|\/\*|\*\/)", re.IGNORECASE),
    re.compile(r"(\bOR\b.*\b1\s*=\s*1\b|\bAND\b.*\b1\s*=\s*1\b)", re.IGNORECASE),
    re.compile(r"(\bWHERE\b.*\bOR\b.*\bLIKE\b)", re.IGNORECASE),
    re.compile(r"(\;\s*(DROP|DELETE|UPDATE|INSERT)\b)", re.IGNORECASE),
    re.compile(r"(\bUNION\b.*\bSELECT\b)", re.IGNORECASE),
    re.compile(r"(\bEXEC\b\s*\(|\bEXECUTE\b\s*\()", re.IGNORECASE)
]

class SecurityValidator:
    """Comprehensive input validation and security checking"""
    
    @staticmethod
    def validate_string(value: str, field_name: str, max_length: int = 255, 
                      pattern: Optional[re.Pattern] = None, required: bool = False) -> str:
        """
        Validate and sanitize string input
        
        Args:
            value: Input string to validate
            field_name: Name of the field for logging
            max_length: Maximum allowed length
            pattern: Regex pattern to match against
            required: Whether the field is required
            
        Returns:
            Sanitized string
            
        Raises:
            ValueError: If validation fails
        """
        if value is None:
            if required:
                SecurityValidator.log_security_event(f"Missing required field: {field_name}", "validation_error")
                raise ValueError(f"Field '{field_name}' is required")
            return ""
        
        if not isinstance(value, str):
            SecurityValidator.log_security_event(f"Invalid type for {field_name}: expected string, got {type(value)}", "validation_error")
            raise ValueError(f"Field '{field_name}' must be a string")
        
        # Trim whitespace
        value = value.strip()
        
        # Check length
        if len(value) > max_length:
            SecurityValidator.log_security_event(f"Field {field_name} exceeds maximum length: {len(value)} > {max_length}", "validation_error")
            raise ValueError(f"Field '{field_name}' exceeds maximum length of {max_length}")
        
        # Check pattern if provided
        if pattern and not pattern.match(value):
            SecurityValidator.log_security_event(f"Field {field_name} failed pattern validation: {value}", "validation_error")
            raise ValueError(f"Field '{field_name}' contains invalid characters")
        
        # Check for SQL injection attempts
        if SecurityValidator.detect_sql_injection(value):
            SecurityValidator.log_security_event(f"SQL injection attempt detected in {field_name}: {value}", "sql_injection_attempt")
            raise ValueError(f"Field '{field_name}' contains potentially malicious content")
        
        return value
    
    @staticmethod
    def validate_integer(value: str, field_name: str, min_val: int = 0, 
                      max_val: int = 2147483647, required: bool = False) -> int:
        """
        Validate integer input
        
        Args:
            value: Input string to convert to integer
            field_name: Name of the field for logging
            min_val: Minimum allowed value
            max_val: Maximum allowed value
            required: Whether the field is required
            
        Returns:
            Validated integer
            
        Raises:
            ValueError: If validation fails
        """
        if value is None:
            if required:
                SecurityValidator.log_security_event(f"Missing required field: {field_name}", "validation_error")
                raise ValueError(f"Field '{field_name}' is required")
            return min_val
        
        try:
            int_value = int(value)
        except (ValueError, TypeError):
            SecurityValidator.log_security_event(f"Invalid integer value for {field_name}: {value}", "validation_error")
            raise ValueError(f"Field '{field_name}' must be a valid integer")
        
        if int_value < min_val or int_value > max_val:
            SecurityValidator.log_security_event(f"Integer {field_name} out of range: {int_value}", "validation_error")
            raise ValueError(f"Field '{field_name}' must be between {min_val} and {max_val}")
        
        return int_value
    
    @staticmethod
    def validate_float(value: str, field_name: str, min_val: float = -180.0, 
                     max_val: float = 180.0, required: bool = False) -> Optional[float]:
        """
        Validate float input (for coordinates)
        
        Args:
            value: Input string to convert to float
            field_name: Name of the field for logging
            min_val: Minimum allowed value
            max_val: Maximum allowed value
            required: Whether the field is required
            
        Returns:
            Validated float or None
        """
        if value is None:
            if required:
                SecurityValidator.log_security_event(f"Missing required field: {field_name}", "validation_error")
                raise ValueError(f"Field '{field_name}' is required")
            return None
        
        try:
            float_value = float(value)
        except (ValueError, TypeError):
            SecurityValidator.log_security_event(f"Invalid float value for {field_name}: {value}", "validation_error")
            raise ValueError(f"Field '{field_name}' must be a valid number")
        
        if float_value < min_val or float_value > max_val:
            SecurityValidator.log_security_event(f"Float {field_name} out of range: {float_value}", "validation_error")
            raise ValueError(f"Field '{field_name}' must be between {min_val} and {max_val}")
        
        return float_value
    
    @staticmethod
    def validate_email(email: str, field_name: str = "email", required: bool = False) -> str:
        """Validate email address"""
        return SecurityValidator.validate_string(email, field_name, 254, PATTERNS['email'], required)
    
    @staticmethod
    def validate_state_code(state: str, required: bool = False) -> str:
        """Validate US state code (2 letters)"""
        return SecurityValidator.validate_string(state, "state", 2, PATTERNS['state_code'], required).upper()
    
    @staticmethod
    def validate_zip_code(zip_code: str, required: bool = False) -> str:
        """Validate US ZIP code"""
        return SecurityValidator.validate_string(zip_code, "zip_code", 10, PATTERNS['zip_code'], required)
    
    @staticmethod
    def validate_coordinates(lat: str, lon: str, required: bool = False) -> tuple:
        """Validate latitude and longitude coordinates"""
        latitude = SecurityValidator.validate_float(lat, "latitude", -90.0, 90.0, required)
        longitude = SecurityValidator.validate_float(lon, "longitude", -180.0, 180.0, required)
        return latitude, longitude
    
    @staticmethod
    def validate_sort_column(column: str, allowed_columns: List[str]) -> str:
        """Validate sort column against allowed list"""
        if not column:
            return "id"  # default
        
        column = SecurityValidator.validate_string(column, "sort_column", 50, PATTERNS['sort_column'])
        
        if column not in allowed_columns:
            SecurityValidator.log_security_event(f"Invalid sort column: {column}", "validation_error")
            raise ValueError(f"Invalid sort column: {column}")
        
        return column
    
    @staticmethod
    def validate_search_query(query: str) -> str:
        """Validate search query"""
        return SecurityValidator.validate_string(query, "search_query", 500, PATTERNS['search_query'])
    
    @staticmethod
    def sanitize_html(content: str) -> str:
        """
        Sanitize HTML content to prevent XSS
        
        Args:
            content: HTML content to sanitize
            
        Returns:
            Sanitized HTML content
        """
        if not content:
            return ""
        
        # Use bleach to remove dangerous HTML
        clean_content = bleach.clean(
            content,
            tags=ALLOWED_TAGS,
            attributes=ALLOWED_ATTRIBUTES,
            strip=True
        )
        
        # Additional HTML entity encoding
        clean_content = html.escape(clean_content)
        
        return clean_content
    
    @staticmethod
    def detect_sql_injection(value: str) -> bool:
        """
        Detect potential SQL injection attempts
        
        Args:
            value: String to check
            
        Returns:
            True if SQL injection pattern detected
        """
        if not value:
            return False
        
        for pattern in SQL_INJECTION_PATTERNS:
            if pattern.search(value):
                return True
        
        return False
    
    @staticmethod
    def log_security_event(message: str, event_type: str, severity: str = "medium"):
        """
        Log security events for monitoring
        
        Args:
            message: Description of the security event
            event_type: Type of security event
            severity: Severity level (low, medium, high, critical)
        """
        client_ip = getattr(request, 'remote_addr', 'unknown')
        user_agent = getattr(request, 'user_agent', {}).get('string', 'unknown')
        endpoint = getattr(request, 'endpoint', 'unknown')
        method = getattr(request, 'method', 'unknown')
        
        log_data = {
            'timestamp': datetime.utcnow().isoformat(),
            'client_ip': client_ip,
            'user_agent': user_agent,
            'endpoint': endpoint,
            'method': method,
            'event_type': event_type,
            'severity': severity,
            'message': message
        }
        
        # Log to security logger
        security_logger.warning(f"SECURITY_EVENT: {event_type} - {message} - IP: {client_ip} - Endpoint: {endpoint}")
        
        # Store in application context for potential response
        if not hasattr(g, 'security_events'):
            g.security_events = []
        g.security_events.append(log_data)
    
    @staticmethod
    def validate_api_request_data(data: Dict[str, Any], required_fields: List[str] = None, 
                                optional_fields: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Validate API request data
        
        Args:
            data: Request data dictionary
            required_fields: List of required field names
            optional_fields: Dictionary of optional fields with their default values
            
        Returns:
            Validated data dictionary
            
        Raises:
            ValueError: If validation fails
        """
        if not isinstance(data, dict):
            SecurityValidator.log_security_event("Invalid request data type", "validation_error")
            raise ValueError("Request data must be a JSON object")
        
        validated_data = {}
        
        # Check required fields
        if required_fields:
            for field in required_fields:
                if field not in data:
                    SecurityValidator.log_security_event(f"Missing required field: {field}", "validation_error")
                    raise ValueError(f"Required field '{field}' is missing")
                validated_data[field] = data[field]
        
        # Add optional fields with defaults
        if optional_fields:
            for field, default_value in optional_fields.items():
                validated_data[field] = data.get(field, default_value)
        
        return validated_data

class APIKeySecurity:
    """Enhanced API key security management"""
    
    @staticmethod
    def generate_secure_key(length: int = 48) -> str:
        """Generate cryptographically secure API key"""
        return secrets.token_urlsafe(length)
    
    @staticmethod
    def hash_api_key(api_key: str) -> str:
        """Hash API key for storage (never store raw keys)"""
        return hashlib.sha256(api_key.encode()).hexdigest()
    
    @staticmethod
    def verify_api_key_strength(api_key: str) -> bool:
        """Verify API key meets security requirements"""
        if len(api_key) < 32:
            return False
        
        # Check for sufficient entropy (basic check)
        unique_chars = len(set(api_key))
        if unique_chars < len(api_key) * 0.6:  # At least 60% unique characters
            return False
        
        return True
    
    @staticmethod
    def should_rotate_key(created_at: datetime, last_rotated: datetime = None, 
                       max_age_days: int = 90) -> bool:
        """
        Check if API key should be rotated
        
        Args:
            created_at: When the key was created
            last_rotated: When the key was last rotated
            max_age_days: Maximum age in days before rotation
            
        Returns:
            True if key should be rotated
        """
        now = datetime.utcnow()
        
        # Use last_rotated if available, otherwise use created_at
        reference_date = last_rotated or created_at
        
        return (now - reference_date).days > max_age_days

class RateLimitSecurity:
    """Enhanced rate limiting with security considerations"""
    
    @staticmethod
    def get_client_identifier() -> str:
        """Get secure client identifier for rate limiting"""
        # Use API key if available, otherwise IP address
        if hasattr(request, 'api_key') and request.api_key:
            return f"api_key:{request.api_key.id}"
        
        # Get IP address, considering proxy headers
        ip = request.environ.get('HTTP_X_FORWARDED_FOR', request.remote_addr)
        if ip and ',' in ip:
            ip = ip.split(',')[0].strip()  # Take first IP in chain
        
        return f"ip:{ip}"
    
    @staticmethod
    def is_suspicious_activity(request_count: int, time_window: int) -> bool:
        """
        Detect suspicious activity patterns
        
        Args:
            request_count: Number of requests in time window
            time_window: Time window in seconds
            
        Returns:
            True if activity appears suspicious
        """
        # Basic heuristics for suspicious activity
        requests_per_second = request_count / time_window
        
        # More than 10 requests per second is suspicious
        if requests_per_second > 10:
            return True
        
        # More than 1000 requests in an hour is suspicious
        if time_window >= 3600 and request_count > 1000:
            return True
        
        return False

# Security decorators
def validate_json_input(required_fields: List[str] = None, optional_fields: Dict[str, Any] = None):
    """
    Decorator to validate JSON input for API endpoints
    
    Args:
        required_fields: List of required field names
        optional_fields: Dictionary of optional fields with default values
    """
    def decorator(f):
        from functools import wraps
        
        @wraps(f)
        def decorated_function(*args, **kwargs):
            try:
                data = request.get_json()
                if data is None:
                    data = {}
                
                validated_data = SecurityValidator.validate_api_request_data(
                    data, required_fields, optional_fields
                )
                
                # Store validated data in request context
                request.validated_data = validated_data
                
                return f(*args, **kwargs)
                
            except ValueError as e:
                SecurityValidator.log_security_event(f"JSON validation failed: {str(e)}", "validation_error")
                return {'error': str(e)}, 400
            except Exception as e:
                SecurityValidator.log_security_event(f"Unexpected validation error: {str(e)}", "system_error")
                return {'error': 'Invalid request format'}, 400
        
        return decorated_function
    return decorator

def log_security_event(event_type: str, message: str, severity: str = "medium"):
    """
    Decorator to log security events for endpoints
    
    Args:
        event_type: Type of security event
        message: Message template
        severity: Severity level
    """
    def decorator(f):
        from functools import wraps
        
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Log before processing
            SecurityValidator.log_security_event(message, event_type, severity)
            
            try:
                result = f(*args, **kwargs)
                
                # Log successful completion for sensitive operations
                if event_type in ['api_key_auth', 'admin_login', 'data_modification']:
                    SecurityValidator.log_security_event(
                        f"{message} - SUCCESS", 
                        f"{event_type}_success", 
                        "low"
                    )
                
                return result
                
            except Exception as e:
                # Log failed operation
                SecurityValidator.log_security_event(
                    f"{message} - FAILED: {str(e)}", 
                    f"{event_type}_failure", 
                    "high"
                )
                raise
        
        return decorated_function
    return decorator