"""
Security headers middleware for Flask applications

This module provides comprehensive security headers implementation including:
- Content Security Policy (CSP)
- HTTP Strict Transport Security (HSTS)
- X-Frame-Options
- X-Content-Type-Options
- X-XSS-Protection
- Referrer Policy
- Permissions Policy
"""

from flask import Flask, request, make_response, session, Response, g
from datetime import datetime, timedelta
import re
import secrets
import logging
from typing import Optional, Dict, Any, Union

class SecurityHeaders:
    """Security headers configuration and implementation"""
    
    def __init__(self, app: Optional[Flask] = None):
        self.app = app
        if app is not None:
            self.init_app(app)
    
    def init_app(self, app: Flask):
        """Initialize security headers with Flask app"""
        app.after_request(self.set_security_headers)
        
        # Configure CSP based on environment
        app.config.setdefault('SECURITY_CSP_POLICY', self._get_csp_policy())
        app.config.setdefault('SECURITY_HSTS_MAX_AGE', 31536000)  # 1 year
        app.config.setdefault('SECURITY_HSTS_INCLUDE_SUBDOMAINS', True)
        app.config.setdefault('SECURITY_HSTS_PRELOAD', True)
    
    def _get_csp_policy(self) -> str:
        """
        Generate Content Security Policy based on environment
        """
        # Base CSP directives
        csp_directives = [
            "default-src 'self'",
            "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdnjs.cloudflare.com https://unpkg.com",
            "style-src 'self' 'unsafe-inline' https://cdnjs.cloudflare.com https://fonts.googleapis.com",
            "img-src 'self' data: https: blob:",
            "font-src 'self' https://fonts.gstatic.com https://cdnjs.cloudflare.com",
            "connect-src 'self'",
            "frame-ancestors 'none'",
            "base-uri 'self'",
            "form-action 'self'",
            "upgrade-insecure-requests"
        ]
        
        # In development, allow more permissive policies
        if self.app and self.app.config.get('ENV') == 'development':
            csp_directives.extend([
                "script-src 'self' 'unsafe-inline' 'unsafe-eval' http://localhost:* https://localhost:*",
                "connect-src 'self' ws: wss: http://localhost:* https://localhost:*"
            ])
        
        return '; '.join(csp_directives)
    
    def set_security_headers(self, response: Response) -> Response:
        """
        Set comprehensive security headers on response
        
        Args:
            response: Flask response object
            
        Returns:
            Response with security headers added
        """
        # Content Security Policy
        csp_policy = self.app.config.get('SECURITY_CSP_POLICY', self._get_csp_policy()) if self.app else self._get_csp_policy()
        response.headers['Content-Security-Policy'] = csp_policy
        
        # HTTP Strict Transport Security (only in production with HTTPS)
        if (request.is_secure and 
            self.app and self.app.config.get('ENV') == 'production'):
            
            hsts_max_age = self.app.config.get('SECURITY_HSTS_MAX_AGE', 31536000)
            hsts_directives = [f"max-age={hsts_max_age}"]
            
            if self.app.config.get('SECURITY_HSTS_INCLUDE_SUBDOMAINS', True):
                hsts_directives.append('includeSubDomains')
            
            if self.app.config.get('SECURITY_HSTS_PRELOAD', True):
                hsts_directives.append('preload')
            
            response.headers['Strict-Transport-Security'] = '; '.join(hsts_directives)
        
        # X-Frame-Options (prevent clickjacking)
        response.headers['X-Frame-Options'] = 'DENY'
        
        # X-Content-Type-Options (prevent MIME type sniffing)
        response.headers['X-Content-Type-Options'] = 'nosniff'
        
        # X-XSS-Protection (legacy XSS protection)
        response.headers['X-XSS-Protection'] = '1; mode=block'
        
        # Referrer Policy
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        
        # Permissions Policy (restrict feature usage)
        permissions_policy = [
            'geolocation=()',
            'microphone=()',
            'camera=()',
            'payment=()',
            'usb=()',
            'magnetometer=()',
            'gyroscope=()',
            'accelerometer=()',
            'ambient-light-sensor=()',
            'autoplay=(self)',
            'encrypted-media=(self)',
            'fullscreen=(self)',
            'picture-in-picture=(self)'
        ]
        response.headers['Permissions-Policy'] = ', '.join(permissions_policy)
        
        # Additional security headers
        response.headers['X-Permitted-Cross-Domain-Policies'] = 'none'
        response.headers['X-Download-Options'] = 'noopen'
        
        # Remove server information
        response.headers.pop('Server', None)
        
        # Cache control for sensitive endpoints
        if self._is_sensitive_endpoint(request.endpoint or ""):
            response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, private'
            response.headers['Pragma'] = 'no-cache'
            response.headers['Expires'] = '0'
        
        return response
    
    def _is_sensitive_endpoint(self, endpoint: str) -> bool:
        """
        Determine if endpoint is sensitive and should not be cached
        
        Args:
            endpoint: Flask endpoint name
            
        Returns:
            True if endpoint is sensitive
        """
        if not endpoint:
            return False
        
        sensitive_patterns = [
            'admin',
            'api',
            'login',
            'logout',
            'create_api_key',
            'revoke_api_key'
        ]
        
        return any(pattern in endpoint.lower() for pattern in sensitive_patterns)

class CSRFProtection:
    """Enhanced CSRF protection for Flask applications"""
    
    def __init__(self, app: Optional[Flask] = None):
        self.app = app
        if app is not None:
            self.init_app(app)
    
    def init_app(self, app: Flask):
        """Initialize CSRF protection with Flask app"""
        app.before_request(self._validate_csrf_token)
        app.after_request(self._set_csrf_token)
        
        # Configure CSRF settings
        app.config.setdefault('WTF_CSRF_TIME_LIMIT', 3600)  # 1 hour
        app.config.setdefault('WTF_CSRF_SSL_STRICT', True)
    
    def _validate_csrf_token(self):
        """
        Validate CSRF token for state-changing requests
        
        Raises:
            ValueError: If CSRF token is invalid
        """
        # Skip CSRF validation for safe methods
        if request.method in ('GET', 'HEAD', 'OPTIONS', 'TRACE'):
            return
        
        # Skip for API endpoints (they use API key authentication)
        if request.path and request.path.startswith('/api/'):
            return
        
        # Skip for static files
        if request.endpoint and request.endpoint == 'static':
            return
        
        # Get CSRF token from request
        token = self._get_csrf_token()
        
        if not token:
            raise ValueError("CSRF token is missing")
        
        # Validate token against session
        session_token = session.get('_csrf_token')
        if not session_token or not secrets.compare_digest(token, session_token):
            raise ValueError("CSRF token is invalid")
    
    def _get_csrf_token(self) -> Optional[str]:
        """
        Extract CSRF token from request
        
        Returns:
            CSRF token string or None
        """
        # Check header first (preferred for AJAX)
        token = request.headers.get('X-CSRF-Token')
        if token:
            return token
        
        # Check form data
        token = request.form.get('csrf_token')
        if token:
            return token
        
        # Check JSON data
        if request.is_json:
            try:
                data = request.get_json(silent=True) or {}
                if isinstance(data, dict):
                    token = data.get('csrf_token')
                    if isinstance(token, str):
                        return token
            except Exception:
                pass
        
        return None
    
    def _set_csrf_token(self, response: Response) -> Response:
        """
        Set CSRF token in response and cookie
        
        Args:
            response: Flask response object
            
        Returns:
            Response with CSRF token
        """
        # Generate new CSRF token if not in session
        if '_csrf_token' not in session:
            session['_csrf_token'] = secrets.token_urlsafe(32)
        
        # Set CSRF token in response header for JavaScript access
        response.headers['X-CSRF-Token'] = session['_csrf_token']
        
        return response
    
    def generate_token(self) -> str:
        """Generate a new CSRF token"""
        return secrets.token_urlsafe(32)

class SecurityMiddleware:
    """Combined security middleware for Flask applications"""
    
    def __init__(self, app: Flask):
        """Initialize all security middleware"""
        self.app = app
        
        # Initialize security headers
        self.security_headers = SecurityHeaders(app)
        
        # Initialize CSRF protection
        self.csrf_protection = CSRFProtection(app)
        
        # Add security logging
        app.before_request(self._log_security_info)
        app.after_request(self._log_response_info)
    
    def _log_security_info(self):
        """Log security-relevant request information"""
        # Skip logging for static files and health checks
        if (request.endpoint == 'static' or 
            request.path == '/health' or
            request.path == '/ping'):
            return
        
        # Log suspicious patterns
        self._check_suspicious_patterns()
    
    def _log_response_info(self, response: Response) -> Response:
        """Log security-relevant response information"""
        # Log authentication failures
        if response.status_code == 401:
            self._log_security_event(
                "Authentication failure",
                "auth_failure",
                "medium"
            )
        
        # Log authorization failures
        elif response.status_code == 403:
            self._log_security_event(
                "Authorization failure",
                "authz_failure", 
                "medium"
            )
        
        # Log potential attacks
        elif response.status_code == 400:
            user_agent = request.headers.get('User-Agent', '')
            if self._is_suspicious_user_agent(user_agent):
                self._log_security_event(
                    "Suspicious request blocked",
                    "suspicious_request",
                    "high"
                )
        
        return response
    
    def _check_suspicious_patterns(self):
        """Check request for suspicious patterns"""
        # Check for SQL injection attempts
        for param in [request.args, request.form, request.get_json(silent=True)]:
            if not param:
                continue
            
            for key, value in param.items():
                if isinstance(value, str) and self._is_sql_injection(value):
                    self._log_security_event(
                        f"SQL injection attempt detected in {key}: {value[:100]}",
                        "sql_injection_attempt",
                        "high"
                    )
        
        # Check for suspicious user agents
        user_agent = request.headers.get('User-Agent', '')
        if self._is_suspicious_user_agent(user_agent):
            self._log_security_event(
                f"Suspicious user agent: {user_agent}",
                "suspicious_user_agent",
                "medium"
            )
        
        # Check for unusual request patterns
        if self._is_unusual_request():
            self._log_security_event(
                f"Unusual request pattern: {request.method} {request.path}",
                "unusual_request",
                "low"
            )
    
    def _is_sql_injection(self, value: str) -> bool:
        """Check for SQL injection patterns"""
        if not value or not isinstance(value, str):
            return False
        
        sql_patterns = [
            r"(\b(SELECT|INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|EXEC|UNION|SCRIPT)\b)",
            r"(\-\-|\#|\/\*|\*\/)",
            r"(\bOR\b.*\b1\s*=\s*1\b|\bAND\b.*\b1\s*=\s*1\b)",
            r"(\;\s*(DROP|DELETE|UPDATE|INSERT)\b)",
            r"(\bUNION\b.*\bSELECT\b)",
            r"(\bEXEC\b\s*\(|\bEXECUTE\b\s*\()"
        ]
        
        for pattern in sql_patterns:
            if re.search(pattern, value, re.IGNORECASE):
                return True
        
        return False
    
    def _is_suspicious_user_agent(self, user_agent: str) -> bool:
        """Check for suspicious user agent patterns"""
        if not user_agent:
            return True  # No user agent is suspicious
        
        suspicious_patterns = [
            r"sqlmap",
            r"nikto",
            r"nmap",
            r"masscan",
            r"zap",
            r"burp",
            r"scanner",
            r"bot",
            r"crawler",
            r"spider"
        ]
        
        for pattern in suspicious_patterns:
            if re.search(pattern, user_agent, re.IGNORECASE):
                return True
        
        return False
    
    def _is_unusual_request(self) -> bool:
        """Check for unusual request patterns"""
        # Very long URLs
        if len(request.full_path) > 2048:
            return True
        
        # Too many parameters
        json_data = request.get_json(silent=True)
        total_params = len(request.args) + len(request.form) + (len(json_data) if json_data else 0)
        if total_params > 50:
            return True
        
        # Suspicious parameter names
        param_names = list(request.args.keys()) + list(request.form.keys())
        suspicious_param_patterns = [
            r"admin",
            r"root",
            r"test",
            r"debug",
            r"exec",
            r"cmd",
            r"system"
        ]
        
        for param_name in param_names:
            for pattern in suspicious_param_patterns:
                if re.search(pattern, param_name, re.IGNORECASE):
                    return True
        
        return False
    
    def _log_security_event(self, message: str, event_type: str, severity: str = "medium"):
        """Log security event"""
        import logging
        
        security_logger = logging.getLogger('security')
        client_ip = request.environ.get('HTTP_X_FORWARDED_FOR', request.remote_addr)
        if client_ip and ',' in client_ip:
            client_ip = client_ip.split(',')[0].strip()
        
        log_data = {
            'timestamp': datetime.utcnow().isoformat(),
            'client_ip': client_ip,
            'user_agent': request.headers.get('User-Agent', ''),
            'method': request.method,
            'path': request.path,
            'endpoint': request.endpoint,
            'event_type': event_type,
            'severity': severity,
            'message': message
        }
        
        security_logger.warning(f"SECURITY: {event_type} - {message} - IP: {client_ip} - Path: {request.path}")

# Flask extension factory
def init_security(app: Flask) -> SecurityMiddleware:
    """
    Initialize security middleware with Flask app
    
    Args:
        app: Flask application instance
    """
    return SecurityMiddleware(app)