"""
Error tracking system for CSC Polling Place API

This module provides comprehensive error tracking, exception handling,
and integration with external monitoring services.
"""

import os
import sys
import traceback
import time
from datetime import datetime, timedelta
from typing import Any, Dict, Optional, List, Callable, Union
from functools import wraps
from flask import Flask, request, g, current_app, jsonify, Response
from werkzeug.exceptions import HTTPException

try:
    from structured_logging import get_logger
except ImportError:
    import logging
    def get_logger(name='app'):
        return logging.getLogger(name)


class ErrorTracker:
    """Error tracking and monitoring system"""
    
    def __init__(self, app: Optional[Flask] = None):
        self.app = app
        self.sentry_enabled = False
        self.error_callbacks: List[Callable] = []
        self.logger = get_logger('error_tracker')
        self.error_stats = {
            'total_errors': 0,
            'http_errors': 0,
            'system_errors': 0,
            'last_error': None
        }
        
        if app:
            self.init_app(app)
    
    def init_app(self, app: Flask):
        """Initialize error tracking with Flask app"""
        self.app = app
        
        # Setup error handlers
        app.errorhandler(Exception)(self._handle_exception)
        app.errorhandler(HTTPException)(self._handle_http_exception)
        
        # Log initialization
        self.logger.info(
            "Error tracking initialized",
            sentry_enabled=self.sentry_enabled,
            environment=getattr(app, 'config', {}).get('ENV', 'development')
        )
    
    def _handle_exception(self, exception: Exception) -> Response:
        """Handle uncaught exceptions"""
        # Update error stats
        self.error_stats['total_errors'] += 1
        self.error_stats['system_errors'] += 1
        self.error_stats['last_error'] = {
            'timestamp': datetime.utcnow().isoformat(),
            'type': type(exception).__name__,
            'message': str(exception)
        }
        
        # Log to structured logger
        self.logger.error(
            f"Unhandled exception: {str(exception)}",
            extra={
                'exception_type': type(exception).__name__,
                'exception_module': type(exception).__module__,
                'traceback': traceback.format_exc()
            }
        )
        
        # Call error callbacks
        for callback in self.error_callbacks:
            try:
                callback(exception)
            except Exception as e:
                self.logger.error(f"Error in error callback: {str(e)}")
        
        # Return JSON error response
        return jsonify({
            'error': 'Internal server error',
            'message': 'An unexpected error occurred',
            'request_id': getattr(g, 'request_id', None),
            'timestamp': datetime.utcnow().isoformat()
        }), 500
    
    def _handle_http_exception(self, exception: HTTPException) -> Response:
        """Handle HTTP exceptions"""
        # Update error stats
        self.error_stats['total_errors'] += 1
        self.error_stats['http_errors'] += 1
        
        # Log HTTP errors
        self.logger.warning(
            f"HTTP exception: {exception.name}",
            extra={
                'status_code': exception.code,
                'description': exception.description
            }
        )
        
        # Return JSON error response
        return jsonify({
            'error': exception.name,
            'message': exception.description,
            'status_code': exception.code,
            'request_id': getattr(g, 'request_id', None),
            'timestamp': datetime.utcnow().isoformat()
        }), exception.code
    
    def capture_message(self, message: str, level: str = 'info'):
        """Capture custom message for monitoring"""
        self.logger.info(f"Error tracking message: {message}")
    
    def set_user_context(self, user_data: Dict[str, Any]):
        """Set user context for error tracking"""
        if 'id' in user_data:
            g.user_id = user_data['id']
    
    def set_tag(self, key: str, value: str):
        """Set tag for error context"""
        self.logger.info(f"Error tag set: {key} = {value}")
    
    def set_context(self, name: str, data: Dict[str, Any]):
        """Set context for error tracking"""
        self.logger.info(f"Error context set: {name}")
    
    def add_error_callback(self, callback: Callable[[Exception], None]):
        """Add custom error callback"""
        self.error_callbacks.append(callback)
    
    def get_error_stats(self) -> Dict[str, Any]:
        """Get error statistics"""
        return {
            **self.error_stats,
            'sentry_enabled': self.sentry_enabled,
            'error_callbacks_count': len(self.error_callbacks),
            'timestamp': datetime.utcnow().isoformat()
        }


class CircuitBreaker:
    """Circuit breaker for external service failures"""
    
    def __init__(self, failure_threshold: int = 5, recovery_timeout: int = 60, expected_exception: type = Exception):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        self.failure_count = 0
        self.last_failure_time = None
        self.state = 'CLOSED'  # CLOSED, OPEN, HALF_OPEN
        self.logger = get_logger('circuit_breaker')
    
    def __call__(self, func):
        """Decorator for circuit breaker"""
        @wraps(func)
        def decorated_function(*args, **kwargs):
            if self.state == 'OPEN':
                if self._should_attempt_reset():
                    self.state = 'HALF_OPEN'
                    self.logger.info("Circuit breaker transitioning to HALF_OPEN")
                else:
                    self.logger.warning("Circuit breaker OPEN - call rejected")
                    raise Exception("Service temporarily unavailable")
            
            try:
                result = func(*args, **kwargs)
                self._on_success()
                return result
            except self.expected_exception as e:
                self._on_failure()
                raise e
        
        return decorated_function
    
    def _should_attempt_reset(self) -> bool:
        """Check if circuit breaker should attempt reset"""
        if self.last_failure_time is None:
            return False
        return time.time() - self.last_failure_time >= self.recovery_timeout
    
    def _on_success(self):
        """Handle successful call"""
        self.failure_count = 0
        if self.state == 'HALF_OPEN':
            self.state = 'CLOSED'
            self.logger.info("Circuit breaker CLOSED - service recovered")
    
    def _on_failure(self):
        """Handle failed call"""
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.failure_count >= self.failure_threshold:
            self.state = 'OPEN'
            self.logger.error(
                f"Circuit breaker OPEN - {self.failure_count} failures detected"
            )
    
    def get_state(self) -> Dict[str, Any]:
        """Get circuit breaker state"""
        return {
            'state': self.state,
            'failure_count': self.failure_count,
            'failure_threshold': self.failure_threshold,
            'recovery_timeout': self.recovery_timeout,
            'last_failure_time': self.last_failure_time
        }


class RetryHandler:
    """Retry handler for transient failures"""
    
    def __init__(self, max_retries: int = 3, backoff_factor: float = 1.0, 
                 retry_on: List[type] = None):
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor
        self.retry_on = retry_on or [Exception]
        self.logger = get_logger('retry_handler')
    
    def __call__(self, func):
        """Decorator for retry logic"""
        @wraps(func)
        def decorated_function(*args, **kwargs):
            last_exception = None
            
            for attempt in range(self.max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    
                    # Check if this exception type should be retried
                    if not any(isinstance(e, exc_type) for exc_type in self.retry_on):
                        raise e
                    
                    if attempt < self.max_retries:
                        delay = self.backoff_factor * (2 ** attempt)
                        self.logger.warning(
                            f"Attempt {attempt + 1} failed, retrying in {delay}s: {str(e)}",
                            extra={
                                'attempt': attempt + 1,
                                'max_retries': self.max_retries + 1,
                                'delay': delay,
                                'error_type': type(e).__name__
                            }
                        )
                        time.sleep(delay)
                    else:
                        self.logger.error(
                            f"All {self.max_retries + 1} attempts failed: {str(e)}",
                            extra={
                                'total_attempts': self.max_retries + 1,
                                'final_error_type': type(e).__name__
                            }
                        )
            
            raise last_exception
        
        return decorated_function


# Global error tracker instance
_error_tracker: Optional[ErrorTracker] = None


def get_error_tracker() -> ErrorTracker:
    """Get global error tracker instance"""
    global _error_tracker
    if _error_tracker is None:
        _error_tracker = ErrorTracker()
    return _error_tracker


def init_error_tracking(app: Flask) -> ErrorTracker:
    """Initialize error tracking with Flask app"""
    global _error_tracker
    _error_tracker = ErrorTracker(app)
    return _error_tracker


def track_errors(operation: str = None):
    """Decorator to track function errors"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            operation_name = operation or f"{f.__module__}.{f.__name__}"
            
            try:
                return f(*args, **kwargs)
            except Exception as e:
                error_tracker = get_error_tracker()
                
                # Add operation context
                error_tracker.set_context('operation', {
                    'name': operation_name,
                    'function': f.__name__,
                    'module': f.__module__,
                    'args_count': len(args),
                    'kwargs_keys': list(kwargs.keys())
                })
                
                # Log error
                logger = get_logger()
                logger.error(
                    f"Error in {operation_name}: {str(e)}",
                    extra={
                        'operation': operation_name,
                        'error_type': type(e).__name__,
                        'function': f.__name__
                    }
                )
                
                raise
        
        return decorated_function
    return decorator


def circuit_breaker(failure_threshold: int = 5, recovery_timeout: int = 60):
    """Circuit breaker decorator"""
    return CircuitBreaker(failure_threshold, recovery_timeout)


def retry(max_retries: int = 3, backoff_factor: float = 1.0):
    """Retry decorator"""
    return RetryHandler(max_retries, backoff_factor)


def capture_error_message(message: str, level: str = 'info'):
    """Capture error message in tracking system"""
    error_tracker = get_error_tracker()
    error_tracker.capture_message(message, level)


def set_error_user(user_data: Dict[str, Any]):
    """Set user context for error tracking"""
    error_tracker = get_error_tracker()
    error_tracker.set_user_context(user_data)


def set_error_tag(key: str, value: str):
    """Set tag for error context"""
    error_tracker = get_error_tracker()
    error_tracker.set_tag(key, value)


def set_error_context(name: str, data: Dict[str, Any]):
    """Set context for error tracking"""
    error_tracker = get_error_tracker()
    error_tracker.set_context(name, data)