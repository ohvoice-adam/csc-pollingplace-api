# Security Documentation

## Overview

The CSC Polling Place API implements comprehensive security measures to protect against common web vulnerabilities and ensure data integrity. This document outlines the security features, configuration options, and best practices for using the API securely.

## Security Features

### 🔒 **Input Validation & Sanitization**
- **SQL Injection Protection**: Detects and blocks SQL injection attempts using pattern matching
- **XSS Protection**: HTML sanitization using bleach library with configurable allowed tags
- **Input Validation**: Type checking, length limits, and pattern validation for all inputs
- **File Upload Security**: File type validation and security scanning

### 🛡️ **Security Headers**
- **Content Security Policy (CSP)**: Prevents XSS and code injection attacks
- **HTTP Strict Transport Security (HSTS)**: Enforces HTTPS connections
- **X-Frame-Options**: Prevents clickjacking attacks
- **X-Content-Type-Options**: Prevents MIME-type sniffing attacks
- **X-XSS-Protection**: Enables browser XSS protection
- **Referrer Policy**: Controls referrer information leakage
- **Permissions Policy**: Restricts browser feature access

### 🔑 **API Key Security**
- **Secure Key Generation**: Cryptographically secure API keys using `secrets.token_urlsafe()`
- **Key Hashing**: SHA-256 hashing for stored API keys (never stores raw keys)
- **Key Strength Validation**: Ensures API keys meet entropy requirements
- **Key Rotation**: Automatic rotation recommendations based on age
- **Rate Limiting**: Per-client rate limiting with suspicious activity detection

### 📊 **Security Monitoring & Logging**
- **Security Events Logging**: Comprehensive logging of security events
- **Suspicious Activity Detection**: Pattern-based detection of unusual behavior
- **IP Tracking**: Client IP logging for security analysis
- **User Agent Logging**: Browser/client identification for forensics

## Configuration

### Environment Variables

```bash
# Security Configuration
SECURITY_ENABLED=true                    # Enable/disable security features
SECURITY_LOG_LEVEL=WARNING               # Security logging level
SECURITY_RATE_LIMIT_ENABLED=true         # Enable rate limiting
SECURITY_HEADERS_ENABLED=true            # Enable security headers
SECURITY_CSP_ENABLED=true                # Enable Content Security Policy
SECURITY_API_KEY_ROTATION_DAYS=90        # API key rotation interval
SECURITY_MAX_REQUESTS_PER_MINUTE=60      # Rate limit per client
SECURITY_SUSPICIOUS_THRESHOLD=1000      # Suspicious activity threshold
```

### Security Headers Configuration

The security headers are automatically configured based on the environment:

```python
# Development CSP (more permissive)
csp_directives = [
    "default-src 'self'",
    "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdnjs.cloudflare.com",
    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
    "img-src 'self' data: https: blob:",
    "font-src 'self' https://fonts.gstatic.com",
    "connect-src 'self'"
]

# Production CSP (stricter)
csp_directives = [
    "default-src 'self'",
    "script-src 'self' https://cdnjs.cloudflare.com",
    "style-src 'self' https://fonts.googleapis.com",
    "img-src 'self' data:",
    "font-src 'self' https://fonts.gstatic.com",
    "connect-src 'self'",
    "frame-ancestors 'none'",
    "base-uri 'self'",
    "form-action 'self'"
]
```

## Usage Examples

### Input Validation

```python
from security import SecurityValidator

# Validate string input
state = SecurityValidator.validate_state_code(request.args.get('state'), required=True)

# Validate coordinates
lat, lon = SecurityValidator.validate_coordinates(
    request.args.get('lat'), 
    request.args.get('lon')
)

# Validate email
email = SecurityValidator.validate_email(request.json.get('email'))

# Sanitize HTML content
clean_html = SecurityValidator.sanitize_html(user_input)
```

### API Key Security

```python
from security import APIKeySecurity

# Generate secure API key
api_key = APIKeySecurity.generate_secure_key(48)

# Hash API key for storage
hashed_key = APIKeySecurity.hash_api_key(api_key)

# Check if key needs rotation
should_rotate = APIKeySecurity.should_rotate_key(
    created_at=key.created_at,
    last_rotated=key.last_rotated,
    max_age_days=90
)
```

### Security Decorators

```python
from security import validate_json_input, log_security_event

@app.route('/api/keys', methods=['POST'])
@validate_json_input(required_fields=['name'], optional_fields={'description': ''})
@log_security_event('api_key_creation', 'API key created')
def create_api_key():
    data = request.validated_data  # Access validated data
    # Your implementation here
```

## Security Event Types

The system logs various security events:

- **`validation_error`**: Input validation failures
- **`sql_injection_attempt`**: Detected SQL injection attempts
- **`xss_attempt`**: Detected XSS attempts
- **`rate_limit_exceeded`**: Rate limit violations
- **`suspicious_activity`**: Unusual activity patterns
- **`api_key_auth`**: API key authentication attempts
- **`admin_login`**: Administrative login attempts
- **`data_modification`**: Data modification operations

## Security Testing

The security implementation includes comprehensive tests:

```bash
# Run security tests
python -m pytest tests/test_security.py -v

# Run security scan
bandit -r . -f json -o temp_artifacts/bandit-report.json

# Run container security scan
trivy fs --format json -o temp_artifacts/trivy-report.json .
```

## Best Practices

### For Developers

1. **Always validate input**: Use `SecurityValidator` for all user inputs
2. **Sanitize HTML content**: Use `sanitize_html()` for any user-generated content
3. **Use security decorators**: Apply `@validate_json_input` and `@log_security_event`
4. **Never log sensitive data**: Avoid logging API keys, passwords, or PII
5. **Implement proper error handling**: Don't expose internal details in error messages

### For Administrators

1. **Monitor security logs**: Regularly review security event logs
2. **Rotate API keys**: Follow the 90-day rotation recommendation
3. **Update dependencies**: Keep security dependencies up to date
4. **Configure rate limits**: Adjust rate limits based on usage patterns
5. **Enable HTTPS**: Always use HTTPS in production

### For Users

1. **Protect API keys**: Never share or commit API keys to version control
2. **Use HTTPS**: Always communicate with the API over HTTPS
3. **Validate responses**: Validate API responses in your client code
4. **Report issues**: Report security vulnerabilities responsibly

## Security Headers Reference

### Content Security Policy (CSP)

```http
Content-Security-Policy: default-src 'self'; script-src 'self' https://cdnjs.cloudflare.com; style-src 'self' https://fonts.googleapis.com; img-src 'self' data:; font-src 'self' https://fonts.gstatic.com; connect-src 'self'
```

### HTTP Strict Transport Security (HSTS)

```http
Strict-Transport-Security: max-age=31536000; includeSubDomains; preload
```

### Other Security Headers

```http
X-Frame-Options: DENY
X-Content-Type-Options: nosniff
X-XSS-Protection: 1; mode=block
Referrer-Policy: strict-origin-when-cross-origin
Permissions-Policy: geolocation=(), microphone=(), camera=()
```

## Monitoring & Alerting

### Security Log Format

```json
{
  "timestamp": "2024-01-15T10:30:00.000Z",
  "client_ip": "192.168.1.100",
  "user_agent": "Mozilla/5.0...",
  "endpoint": "/api/keys",
  "method": "POST",
  "event_type": "api_key_creation",
  "severity": "low",
  "message": "API key created - SUCCESS"
}
```

### Setting Up Alerts

Configure monitoring systems to alert on:
- High-severity security events
- Rate limit violations
- SQL injection attempts
- Suspicious activity patterns
- Multiple failed authentication attempts

## Troubleshooting

### Common Issues

1. **False positives in SQL injection detection**
   - Review the detection patterns in `SQL_INJECTION_PATTERNS`
   - Adjust patterns based on your specific use cases

2. **CSP blocking legitimate resources**
   - Update CSP directives in `security_middleware.py`
   - Test CSP changes in development first

3. **Rate limiting too strict**
   - Adjust rate limits in environment configuration
   - Consider different limits for different user types

### Debug Mode

Enable debug logging for security events:

```python
import logging
logging.getLogger('security').setLevel(logging.DEBUG)
```

## Security Updates

Stay informed about security updates:

1. **Subscribe to security mailing lists** for Python and Flask
2. **Monitor dependency updates** using tools like `pip-audit`
3. **Review security scan results** regularly
4. **Update security patterns** as new threats emerge

## Contact & Reporting

For security issues or questions:

- **Security vulnerabilities**: Report privately to maintain security
- **General questions**: Use the project's issue tracker
- **Documentation updates**: Submit pull requests

---

**Last Updated**: January 2024  
**Version**: 1.0  
**Maintainer**: CSC Polling Place API Team