"""
Comprehensive security tests for CSC Polling Place API

This module tests all security features including:
- Input validation and sanitization
- SQL injection detection
- XSS protection
- API key security
- Rate limiting
- Security headers
- CSRF protection
"""

import pytest
import json
import re
from unittest.mock import patch, MagicMock
from flask import Flask
from security import SecurityValidator, APIKeySecurity, RateLimitSecurity
from security_middleware import SecurityHeaders, CSRFProtection, SecurityMiddleware


class TestSecurityValidator:
    """Test SecurityValidator class methods"""
    
    def test_validate_string_valid_input(self):
        """Test valid string validation"""
        result = SecurityValidator.validate_string("test", "test_field", max_length=10)
        assert result == "test"
    
    def test_validate_string_too_long(self):
        """Test string length validation"""
        with pytest.raises(ValueError, match="exceeds maximum length"):
            SecurityValidator.validate_string("this_is_too_long", "test_field", max_length=5)
    
    def test_validate_string_required_missing(self):
        """Test required field validation"""
        with pytest.raises(ValueError, match="is required"):
            SecurityValidator.validate_string(None, "test_field", required=True)
    
    def test_validate_string_pattern_mismatch(self):
        """Test pattern validation"""
        pattern = re.compile(r'^[a-z]+$')
        with pytest.raises(ValueError, match="invalid characters"):
            SecurityValidator.validate_string("Test123", "test_field", pattern=pattern)
    
    def test_validate_string_sql_injection(self):
        """Test SQL injection detection"""
        with pytest.raises(ValueError, match="malicious content"):
            SecurityValidator.validate_string("'; DROP TABLE users; --", "test_field")
    
    def test_validate_integer_valid(self):
        """Test valid integer validation"""
        result = SecurityValidator.validate_integer("42", "test_field")
        assert result == 42
    
    def test_validate_integer_invalid(self):
        """Test invalid integer validation"""
        with pytest.raises(ValueError, match="valid integer"):
            SecurityValidator.validate_integer("not_a_number", "test_field")
    
    def test_validate_integer_out_of_range(self):
        """Test integer range validation"""
        with pytest.raises(ValueError, match="out of range"):
            SecurityValidator.validate_integer("999", "test_field", max_val=100)
    
    def test_validate_float_valid(self):
        """Test valid float validation"""
        result = SecurityValidator.validate_float("3.14", "test_field")
        assert result == 3.14
    
    def test_validate_float_invalid(self):
        """Test invalid float validation"""
        with pytest.raises(ValueError, match="valid number"):
            SecurityValidator.validate_float("not_a_number", "test_field")
    
    def test_validate_email_valid(self):
        """Test valid email validation"""
        result = SecurityValidator.validate_email("test@example.com")
        assert result == "test@example.com"
    
    def test_validate_email_invalid(self):
        """Test invalid email validation"""
        with pytest.raises(ValueError, match="invalid characters"):
            SecurityValidator.validate_email("invalid_email")
    
    def test_validate_state_code_valid(self):
        """Test valid state code validation"""
        result = SecurityValidator.validate_state_code("ca")
        assert result == "CA"
    
    def test_validate_state_code_invalid(self):
        """Test invalid state code validation"""
        with pytest.raises(ValueError, match="invalid characters"):
            SecurityValidator.validate_state_code("CAL")
    
    def test_validate_zip_code_valid(self):
        """Test valid ZIP code validation"""
        result = SecurityValidator.validate_zip_code("12345")
        assert result == "12345"
    
    def test_validate_zip_code_invalid(self):
        """Test invalid ZIP code validation"""
        with pytest.raises(ValueError, match="invalid characters"):
            SecurityValidator.validate_zip_code("ABCDE")
    
    def test_validate_coordinates_valid(self):
        """Test valid coordinates validation"""
        lat, lon = SecurityValidator.validate_coordinates("40.7128", "-74.0060")
        assert lat == 40.7128
        assert lon == -74.0060
    
    def test_validate_coordinates_invalid(self):
        """Test invalid coordinates validation"""
        with pytest.raises(ValueError, match="must be between"):
            SecurityValidator.validate_coordinates("91.0", "181.0")
    
    def test_sanitize_html_safe(self):
        """Test HTML sanitization of safe content"""
        content = "<p>Safe content</p>"
        result = SecurityValidator.sanitize_html(content)
        assert "<p>Safe content</p>" in result
    
    def test_sanitize_html_dangerous(self):
        """Test HTML sanitization of dangerous content"""
        content = "<script>alert('xss')</script>"
        result = SecurityValidator.sanitize_html(content)
        assert "<script>" not in result
    
    def test_detect_sql_injection_true(self):
        """Test SQL injection detection - positive case"""
        malicious = "'; DROP TABLE users; --"
        assert SecurityValidator.detect_sql_injection(malicious) is True
    
    def test_detect_sql_injection_false(self):
        """Test SQL injection detection - negative case"""
        safe = "John Doe"
        assert SecurityValidator.detect_sql_injection(safe) is False
    
    def test_validate_api_request_data_valid(self):
        """Test API request data validation - valid"""
        data = {"name": "test", "value": "123"}
        result = SecurityValidator.validate_api_request_data(
            data, 
            required_fields=["name"], 
            optional_fields={"value": "default"}
        )
        assert result["name"] == "test"
        assert result["value"] == "123"
    
    def test_validate_api_request_data_missing_required(self):
        """Test API request data validation - missing required"""
        data = {"value": "123"}
        with pytest.raises(ValueError, match="Missing required field"):
            SecurityValidator.validate_api_request_data(data, required_fields=["name"])
    
    def test_validate_api_request_data_invalid_type(self):
        """Test API request data validation - invalid type"""
        with pytest.raises(ValueError, match="must be a JSON object"):
            SecurityValidator.validate_api_request_data("not_a_dict")


class TestAPIKeySecurity:
    """Test APIKeySecurity class methods"""
    
    def test_generate_secure_key(self):
        """Test secure key generation"""
        key = APIKeySecurity.generate_secure_key(32)
        assert len(key) >= 32
        assert isinstance(key, str)
    
    def test_hash_api_key(self):
        """Test API key hashing"""
        key = "test_key_123"
        hashed = APIKeySecurity.hash_api_key(key)
        assert hashed != key
        assert len(hashed) == 64  # SHA256 hex length
    
    def test_verify_api_key_strength_strong(self):
        """Test API key strength verification - strong key"""
        strong_key = APIKeySecurity.generate_secure_key(48)
        assert APIKeySecurity.verify_api_key_strength(strong_key) is True
    
    def test_verify_api_key_strength_weak(self):
        """Test API key strength verification - weak key"""
        weak_key = "weak_key"
        assert APIKeySecurity.verify_api_key_strength(weak_key) is False
    
    def test_should_rotate_key_old(self):
        """Test API key rotation check - old key"""
        from datetime import datetime, timedelta
        old_date = datetime.utcnow() - timedelta(days=100)
        assert APIKeySecurity.should_rotate_key(old_date) is True
    
    def test_should_rotate_key_recent(self):
        """Test API key rotation check - recent key"""
        from datetime import datetime, timedelta
        recent_date = datetime.utcnow() - timedelta(days=10)
        assert APIKeySecurity.should_rotate_key(recent_date) is False


class TestRateLimitSecurity:
    """Test RateLimitSecurity class methods"""
    
    @patch('security.request')
    def test_get_client_identifier_with_api_key(self, mock_request):
        """Test client identifier with API key"""
        mock_request.api_key = MagicMock()
        mock_request.api_key.id = 123
        mock_request.environ = {}
        mock_request.remote_addr = "127.0.0.1"
        
        result = RateLimitSecurity.get_client_identifier()
        assert result == "api_key:123"
    
    @patch('security.request')
    def test_get_client_identifier_with_ip(self, mock_request):
        """Test client identifier with IP address"""
        mock_request.api_key = None
        mock_request.environ = {}
        mock_request.remote_addr = "127.0.0.1"
        
        result = RateLimitSecurity.get_client_identifier()
        assert result == "ip:127.0.0.1"
    
    @patch('security.request')
    def test_get_client_identifier_with_proxy(self, mock_request):
        """Test client identifier with proxy headers"""
        mock_request.api_key = None
        mock_request.environ = {'HTTP_X_FORWARDED_FOR': '10.0.0.1, 127.0.0.1'}
        mock_request.remote_addr = "127.0.0.1"
        
        result = RateLimitSecurity.get_client_identifier()
        assert result == "ip:10.0.0.1"
    
    def test_is_suspicious_activity_high_rate(self):
        """Test suspicious activity detection - high rate"""
        assert RateLimitSecurity.is_suspicious_activity(100, 5) is True
    
    def test_is_suspicious_activity_normal_rate(self):
        """Test suspicious activity detection - normal rate"""
        assert RateLimitSecurity.is_suspicious_activity(10, 60) is False
    
    def test_is_suspicious_activity_high_volume(self):
        """Test suspicious activity detection - high volume"""
        assert RateLimitSecurity.is_suspicious_activity(1500, 3600) is True


class TestSecurityHeaders:
    """Test SecurityHeaders class methods"""
    
    def test_init_with_app(self):
        """Test SecurityHeaders initialization with Flask app"""
        app = Flask(__name__)
        headers = SecurityHeaders(app)
        assert headers.app == app
    
    def test_init_without_app(self):
        """Test SecurityHeaders initialization without app"""
        headers = SecurityHeaders()
        assert headers.app is None
    
    def test_get_csp_policy_development(self):
        """Test CSP policy generation for development"""
        app = Flask(__name__)
        app.config['ENV'] = 'development'
        headers = SecurityHeaders(app)
        
        csp = headers._get_csp_policy()
        assert "localhost" in csp
        assert "unsafe-eval" in csp
    
    def test_get_csp_policy_production(self):
        """Test CSP policy generation for production"""
        app = Flask(__name__)
        app.config['ENV'] = 'production'
        headers = SecurityHeaders(app)
        
        csp = headers._get_csp_policy()
        assert "localhost" not in csp
        assert "default-src 'self'" in csp
    
    def test_is_sensitive_endpoint_admin(self):
        """Test sensitive endpoint detection - admin"""
        headers = SecurityHeaders()
        assert headers._is_sensitive_endpoint("admin_dashboard") is True
    
    def test_is_sensitive_endpoint_api(self):
        """Test sensitive endpoint detection - API"""
        headers = SecurityHeaders()
        assert headers._is_sensitive_endpoint("api_polling_places") is True
    
    def test_is_sensitive_endpoint_public(self):
        """Test sensitive endpoint detection - public"""
        headers = SecurityHeaders()
        assert headers._is_sensitive_endpoint("home") is False


class TestCSRFProtection:
    """Test CSRFProtection class methods"""
    
    def test_init_with_app(self):
        """Test CSRFProtection initialization with Flask app"""
        app = Flask(__name__)
        csrf = CSRFProtection(app)
        assert csrf.app == app
    
    def test_init_without_app(self):
        """Test CSRFProtection initialization without app"""
        csrf = CSRFProtection()
        assert csrf.app is None
    
    def test_generate_token(self):
        """Test CSRF token generation"""
        csrf = CSRFProtection()
        token = csrf.generate_token()
        assert len(token) > 0
        assert isinstance(token, str)


class TestSecurityMiddleware:
    """Test SecurityMiddleware class methods"""
    
    @patch('security_middleware.request')
    def test_is_sql_injection_true(self, mock_request):
        """Test SQL injection detection in middleware"""
        middleware = SecurityMiddleware(Flask(__name__))
        
        # Test various SQL injection patterns
        sql_attempts = [
            "'; DROP TABLE users; --",
            "OR 1=1",
            "UNION SELECT * FROM passwords",
            "EXEC sp_configure"
        ]
        
        for attempt in sql_attempts:
            assert middleware._is_sql_injection(attempt) is True
    
    @patch('security_middleware.request')
    def test_is_sql_injection_false(self, mock_request):
        """Test SQL injection detection - safe content"""
        middleware = SecurityMiddleware(Flask(__name__))
        
        safe_content = [
            "John Doe",
            "123 Main Street",
            "test@example.com",
            "Normal search query"
        ]
        
        for content in safe_content:
            assert middleware._is_sql_injection(content) is False
    
    def test_is_suspicious_user_agent_true(self):
        """Test suspicious user agent detection - positive"""
        middleware = SecurityMiddleware(Flask(__name__))
        
        suspicious_agents = [
            "sqlmap/1.0",
            "nikto/2.1",
            "nmap scanning tool",
            "malicious bot"
        ]
        
        for agent in suspicious_agents:
            assert middleware._is_suspicious_user_agent(agent) is True
    
    def test_is_suspicious_user_agent_false(self):
        """Test suspicious user agent detection - negative"""
        middleware = SecurityMiddleware(Flask(__name__))
        
        safe_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Chrome/91.0.4472.124",
            "curl/7.68.0"
        ]
        
        for agent in safe_agents:
            assert middleware._is_suspicious_user_agent(agent) is False
    
    def test_is_suspicious_user_agent_empty(self):
        """Test suspicious user agent detection - empty"""
        middleware = SecurityMiddleware(Flask(__name__))
        assert middleware._is_suspicious_user_agent("") is True
        assert middleware._is_suspicious_user_agent(None) is True
    
    @patch('security_middleware.request')
    def test_is_unusual_request_long_url(self, mock_request):
        """Test unusual request detection - long URL"""
        mock_request.full_path = "/api/" + "a" * 2000
        middleware = SecurityMiddleware(Flask(__name__))
        
        assert middleware._is_unusual_request() is True
    
    @patch('security_middleware.request')
    def test_is_unusual_request_many_params(self, mock_request):
        """Test unusual request detection - many parameters"""
        mock_request.full_path = "/api/test"
        mock_request.args = {f"param{i}": "value" for i in range(60)}
        mock_request.form = {}
        mock_request.json = None
        middleware = SecurityMiddleware(Flask(__name__))
        
        assert middleware._is_unusual_request() is True
    
    @patch('security_middleware.request')
    def test_is_unusual_request_suspicious_params(self, mock_request):
        """Test unusual request detection - suspicious parameter names"""
        mock_request.full_path = "/api/test"
        mock_request.args = {"admin": "true", "debug": "1"}
        mock_request.form = {}
        mock_request.json = None
        middleware = SecurityMiddleware(Flask(__name__))
        
        assert middleware._is_unusual_request() is True


class TestSecurityIntegration:
    """Test security integration with Flask app"""
    
    def test_security_middleware_initialization(self):
        """Test complete security middleware initialization"""
        app = Flask(__name__)
        app.config['SECRET_KEY'] = 'test-secret'
        
        # Initialize security middleware
        middleware = SecurityMiddleware(app)
        
        assert middleware.app == app
        assert middleware.security_headers is not None
        assert middleware.csrf_protection is not None
    
    def test_security_headers_integration(self):
        """Test security headers integration"""
        app = Flask(__name__)
        app.config['ENV'] = 'production'
        
        with app.test_request_context('/'):
            response = app.test_client().get('/')
            
            # Check if security headers would be set
            headers = SecurityHeaders(app)
            test_response = MagicMock()
            headers.set_security_headers(test_response)
            
            # Verify headers are set
            assert test_response.headers.__setitem__.called
    
    def test_csrf_protection_integration(self):
        """Test CSRF protection integration"""
        app = Flask(__name__)
        app.config['SECRET_KEY'] = 'test-secret'
        
        with app.test_request_context('/'):
            csrf = CSRFProtection(app)
            token = csrf.generate_token()
            
            assert len(token) > 0
            assert isinstance(token, str)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])