"""
Error Handling Decorators and Middleware

Provides decorators and middleware for consistent error handling across the application.
Integrates with structured logging, error tracking, graceful degradation, and alerting.
"""

import time
import traceback
import logging
from typing import Dict, Any, Optional, Callable, Union
from functools import wraps
from datetime import datetime

try:
    from flask import Flask, request, g, jsonify, Response
    from werkzeug.exceptions import HTTPException
    FLASK_AVAILABLE = True
except ImportError:
    FLASK_AVAILABLE = False
    Flask = None
    request = None
    g = None
    jsonify = None
    Response = None
    HTTPException = None

# Standard logger for fallback
logger = logging.getLogger(__name__)


def handle_errors(
    exceptions: Union[type, tuple] = Exception,
    fallback_value: Any = None,
    alert_on_error: bool = False,
    alert_severity: str = "medium",
    log_level: str = "error",
    reraise: bool = False,
    service_name: Optional[str] = None
):
    """Decorator for consistent error handling"""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            operation_name = f"{func.__module__}.{func.__name__}"
            
            try:
                return func(*args, **kwargs)
                    
            except exceptions as e:
                # Calculate execution time
                execution_time = time.time() - start_time
                
                # Log the error
                log_method = getattr(logger, log_level, logger.error)
                log_method(
                    f"Function execution failed - Operation: {operation_name}, "
                    f"Error: {str(e)}, Type: {type(e).__name__}, "
                    f"Execution Time: {execution_time:.4f}s"
                )
                
                # Return fallback value or reraise
                if reraise:
                    raise
                return fallback_value
                
        return wrapper
    return decorator


def retry_on_failure(
    max_retries: int = 3,
    initial_delay: float = 1.0,
    backoff_factor: float = 2.0,
    exceptions: Union[type, tuple] = Exception
):
    """Decorator for retrying failed operations"""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            operation_name = f"{func.__module__}.{func.__name__}"
            last_exception = None
            current_delay = initial_delay
            
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    
                    if attempt == max_retries:
                        logger.error(
                            f"Operation failed after {max_retries} retries - "
                            f"Operation: {operation_name}, Error: {str(e)}"
                        )
                        raise
                    
                    logger.warning(
                        f"Operation failed, retrying - Attempt: {attempt + 1}/{max_retries + 1}, "
                        f"Delay: {current_delay:.2f}s, Error: {str(e)}"
                    )
                    
                    time.sleep(current_delay)
                    current_delay *= backoff_factor
                    
        return wrapper
    return decorator


def performance_monitor(threshold_ms: float = 100.0):
    """Decorator for monitoring function performance"""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            operation_name = f"{func.__module__}.{func.__name__}"
            
            try:
                result = func(*args, **kwargs)
                return result
            finally:
                execution_time_ms = (time.time() - start_time) * 1000
                
                if execution_time_ms > threshold_ms:
                    logger.warning(
                        f"Performance threshold exceeded - Operation: {operation_name}, "
                        f"Execution Time: {execution_time_ms:.2f}ms, Threshold: {threshold_ms}ms"
                    )
                else:
                    logger.info(
                        f"Performance monitor - Operation: {operation_name}, "
                        f"Execution Time: {execution_time_ms:.2f}ms"
                    )
                    
        return wrapper
    return decorator


def validate_input(validation_schema: Optional[Dict[str, Dict[str, Any]]] = None):
    """Decorator for input validation"""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            operation_name = f"{func.__module__}.{func.__name__}"
            
            try:
                # Basic validation if schema provided
                if validation_schema:
                    for field, rules in validation_schema.items():
                        if field in kwargs:
                            value = kwargs[field]
                            
                            # Type validation
                            if 'type' in rules and not isinstance(value, rules['type']):
                                raise ValueError(f"Field {field} must be of type {rules['type'].__name__}")
                            
                            # Required validation
                            if rules.get('required', False) and value is None:
                                raise ValueError(f"Field {field} is required")
                            
                            # Length validation for strings
                            if isinstance(value, str):
                                if 'min_length' in rules and len(value) < rules['min_length']:
                                    raise ValueError(f"Field {field} must be at least {rules['min_length']} characters")
                                if 'max_length' in rules and len(value) > rules['max_length']:
                                    raise ValueError(f"Field {field} must be at most {rules['max_length']} characters")
                
                return func(*args, **kwargs)
                
            except ValueError as e:
                logger.warning(
                    f"Input validation failed - Operation: {operation_name}, Error: {str(e)}"
                )
                raise
                
        return wrapper
    return decorator


def circuit_breaker(
    failure_threshold: int = 5,
    recovery_timeout: float = 60.0,
    expected_exception: type = Exception
):
    """Circuit breaker decorator"""
    def decorator(func: Callable) -> Callable:
        # Circuit breaker state
        state = {
            'failure_count': 0,
            'last_failure_time': None,
            'state': 'CLOSED'  # CLOSED, OPEN, HALF_OPEN
        }
        
        @wraps(func)
        def wrapper(*args, **kwargs):
            operation_name = f"{func.__module__}.{func.__name__}"
            current_time = time.time()
            
            # Check if circuit should be half-open
            if (state['state'] == 'OPEN' and 
                state['last_failure_time'] and 
                current_time - state['last_failure_time'] > recovery_timeout):
                state['state'] = 'HALF_OPEN'
                logger.info(f"Circuit breaker half-open - Operation: {operation_name}")
            
            # Reject calls if circuit is open
            if state['state'] == 'OPEN':
                raise Exception(f"Circuit breaker is open for operation: {operation_name}")
            
            try:
                result = func(*args, **kwargs)
                
                # Reset on success
                if state['state'] == 'HALF_OPEN':
                    state['state'] = 'CLOSED'
                    state['failure_count'] = 0
                    logger.info(f"Circuit breaker closed - Operation: {operation_name}")
                
                return result
                
            except expected_exception as e:
                state['failure_count'] += 1
                state['last_failure_time'] = current_time
                
                if state['failure_count'] >= failure_threshold:
                    state['state'] = 'OPEN'
                    logger.error(
                        f"Circuit breaker opened - Operation: {operation_name}, "
                        f"Failure Count: {state['failure_count']}, Threshold: {failure_threshold}"
                    )
                
                raise
                
        return wrapper
    return decorator


# Flask middleware
if FLASK_AVAILABLE:
    def setup_error_handling_middleware(app: Flask):
        """Setup error handling middleware for Flask app"""
        
        @app.before_request
        def before_request():
            g.start_time = time.time()
            g.request_id = f"{int(time.time())}-{id(request)}"
            
            logger.info(
                f"Request started - Request ID: {g.request_id}, "
                f"Method: {request.method}, Path: {request.path}, "
                f"Remote Addr: {request.remote_addr}"
            )
        
        @app.after_request
        def after_request(response):
            if hasattr(g, 'start_time'):
                execution_time = time.time() - g.start_time
                request_id = getattr(g, 'request_id', 'unknown')
                
                logger.info(
                    f"Request completed - Request ID: {request_id}, "
                    f"Method: {request.method}, Path: {request.path}, "
                    f"Status: {response.status_code}, Time: {execution_time:.4f}s"
                )
            
            return response
        
        @app.errorhandler(Exception)
        def handle_exception(e):
            request_id = getattr(g, 'request_id', 'unknown')
            
            logger.error(
                f"Unhandled exception - Request ID: {request_id}, "
                f"Error: {str(e)}, Type: {type(e).__name__}, "
                f"Traceback: {traceback.format_exc()}"
            )
            
            if isinstance(e, HTTPException):
                return jsonify({
                    'error': e.name,
                    'message': e.description,
                    'request_id': request_id
                }), e.code
            
            return jsonify({
                'error': 'Internal Server Error',
                'message': 'An unexpected error occurred',
                'request_id': request_id
            }), 500
        
        @app.errorhandler(404)
        def handle_not_found(e):
            request_id = getattr(g, 'request_id', 'unknown')
            
            logger.warning(
                f"Route not found - Request ID: {request_id}, "
                f"Path: {request.path}, Method: {request.method}"
            )
            
            return jsonify({
                'error': 'Not Found',
                'message': 'The requested resource was not found',
                'request_id': request_id
            }), 404
        
        @app.errorhandler(500)
        def handle_internal_error(e):
            request_id = getattr(g, 'request_id', 'unknown')
            
            logger.error(
                f"Internal server error - Request ID: {request_id}, "
                f"Error: {str(e)}"
            )
            
            return jsonify({
                'error': 'Internal Server Error',
                'message': 'An internal server error occurred',
                'request_id': request_id
            }), 500


# Utility functions
def log_function_call(func: Callable) -> Callable:
    """Decorator to log function calls"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        operation_name = f"{func.__module__}.{func.__name__}"
        logger.info(f"Function called - Operation: {operation_name}")
        
        try:
            result = func(*args, **kwargs)
            logger.info(f"Function completed successfully - Operation: {operation_name}")
            return result
        except Exception as e:
            logger.error(f"Function failed - Operation: {operation_name}, Error: {str(e)}")
            raise
    
    return wrapper


def timeout_handler(timeout_seconds: float):
    """Decorator for function timeout handling"""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            operation_name = f"{func.__module__}.{func.__name__}"
            
            # Simple timeout implementation using time tracking
            start_time = time.time()
            
            try:
                result = func(*args, **kwargs)
                execution_time = time.time() - start_time
                
                if execution_time > timeout_seconds:
                    logger.warning(
                        f"Function exceeded timeout - Operation: {operation_name}, "
                        f"Execution Time: {execution_time:.2f}s, Timeout: {timeout_seconds}s"
                    )
                
                return result
                
            except Exception as e:
                execution_time = time.time() - start_time
                logger.error(
                    f"Function failed with exception - Operation: {operation_name}, "
                    f"Execution Time: {execution_time:.2f}s, Error: {str(e)}"
                )
                raise
                
        return wrapper
    return decorator


# Configuration
class ErrorHandlingConfig:
    """Configuration for error handling"""
    
    def __init__(self):
        self.default_retry_attempts = 3
        self.default_retry_delay = 1.0
        self.default_performance_threshold = 100.0  # ms
        self.default_circuit_breaker_threshold = 5
        self.default_circuit_breaker_timeout = 60.0  # seconds
        self.log_all_requests = True
        self.log_performance_warnings = True


# Global configuration instance
error_config = ErrorHandlingConfig()