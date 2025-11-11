"""
Structured logging system for CSC Polling Place API

This module provides comprehensive structured logging with JSON formatting,
correlation IDs, request tracking, and performance monitoring.
"""

import json
import logging
import time
import uuid
import traceback
from datetime import datetime
from typing import Any, Dict, Optional, Union
from functools import wraps
from flask import Flask, request, g
from pythonjsonlogger import jsonlogger


class StructuredLogger:
    """Structured logger with JSON formatting and correlation tracking"""
    
    def __init__(self, name: str, app: Optional[Flask] = None):
        self.name = name
        self.logger = logging.getLogger(name)
        self.app = app
        self._setup_logger()
    
    def _setup_logger(self):
        """Setup structured logger with JSON formatter"""
        # Remove existing handlers
        for handler in self.logger.handlers[:]:
            self.logger.removeHandler(handler)
        
        # Create JSON formatter
        formatter = jsonlogger.JsonFormatter(
            fmt='%(asctime)s %(name)s %(levelname)s %(message)s %(filename)s %(lineno)d',
            datefmt='%Y-%m-%dT%H:%M:%S'
        )
        
        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        self.logger.addHandler(console_handler)
        
        # File handler for errors
        error_handler = logging.FileHandler('logs/error.log')
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(formatter)
        self.logger.addHandler(error_handler)
        
        # File handler for all logs
        file_handler = logging.FileHandler('logs/app.log')
        file_handler.setFormatter(formatter)
        self.logger.addHandler(file_handler)
        
        self.logger.setLevel(logging.INFO)
        self.logger.propagate = False
    
    def _get_context(self) -> Dict[str, Any]:
        """Get request context for logging"""
        context = {
            'timestamp': datetime.utcnow().isoformat(),
            'service': 'csc-pollingplace-api',
            'version': getattr(self.app, 'version', '1.0.0') if self.app else '1.0.0'
        }
        
        # Add request context if available (safely check for request context)
        try:
            if request and hasattr(request, 'method'):
                context.update({
                    'request_id': getattr(g, 'request_id', None),
                    'method': request.method,
                    'url': request.url,
                    'user_agent': getattr(request, 'user_agent', {}).get('string', 'unknown'),
                    'remote_addr': getattr(request, 'remote_addr', 'unknown'),
                    'api_key': getattr(request, 'api_key', None)
                })
        except (RuntimeError, AttributeError):
            # Working outside of request context - skip request-specific fields
            pass
        
        # Add user context if available (safely check for application context)
        try:
            if hasattr(g, 'user_id'):
                context['user_id'] = g.user_id
        except (RuntimeError, AttributeError):
            # Working outside of application context - skip user-specific fields
            pass
        
        return context
    
    def _log(self, level: int, message: str, **kwargs):
        """Log with structured context"""
        context = self._get_context()
        context.update(kwargs)
        
        # Add exception info if available
        if 'exc_info' in kwargs:
            context['exception'] = traceback.format_exception(*kwargs['exc_info'])
        
        log_entry = {
            'level': logging.getLevelName(level),
            'message': message,
            **context
        }
        
        self.logger.log(level, json.dumps(log_entry, default=str))
    
    def debug(self, message: str, **kwargs):
        """Log debug message"""
        self._log(logging.DEBUG, message, **kwargs)
    
    def info(self, message: str, **kwargs):
        """Log info message"""
        self._log(logging.INFO, message, **kwargs)
    
    def warning(self, message: str, **kwargs):
        """Log warning message"""
        self._log(logging.WARNING, message, **kwargs)
    
    def error(self, message: str, **kwargs):
        """Log error message"""
        self._log(logging.ERROR, message, **kwargs)
    
    def critical(self, message: str, **kwargs):
        """Log critical message"""
        self._log(logging.CRITICAL, message, **kwargs)
    
    def exception(self, message: str, **kwargs):
        """Log exception with traceback"""
        kwargs['exc_info'] = True
        self._log(logging.ERROR, message, **kwargs)
    
    def log_request(self, duration: Optional[float] = None, status_code: Optional[int] = None, **kwargs):
        """Log HTTP request"""
        context = {
            'event_type': 'http_request',
            'duration_ms': duration * 1000 if duration else None,
            'status_code': status_code
        }
        context.update(kwargs)
        
        message = f"{request.method} {request.path}"
        if status_code:
            message += f" - {status_code}"
        
        if status_code and status_code >= 400:
            self.error(message, **context)
        else:
            self.info(message, **context)
    
    def log_performance(self, operation: str, duration: float, **kwargs):
        """Log performance metrics"""
        context = {
            'event_type': 'performance',
            'operation': operation,
            'duration_ms': duration * 1000
        }
        context.update(kwargs)
        
        self.info(f"Performance: {operation}", **context)
    
    def log_business_event(self, event_type: str, **kwargs):
        """Log business events"""
        context = {
            'event_type': 'business',
            'business_event': event_type
        }
        context.update(kwargs)
        
        self.info(f"Business Event: {event_type}", **context)
    
    def log_security_event(self, event_type: str, severity: str = 'medium', **kwargs):
        """Log security events"""
        context = {
            'event_type': 'security',
            'security_event': event_type,
            'severity': severity
        }
        context.update(kwargs)
        
        if severity in ['high', 'critical']:
            self.warning(f"Security Event: {event_type}", **context)
        else:
            self.info(f"Security Event: {event_type}", **context)


class RequestTracker:
    """Request tracking middleware for correlation IDs and performance"""
    
    def __init__(self, app: Optional[Flask] = None):
        self.app = app
        if app:
            self.init_app(app)
    
    def init_app(self, app: Flask):
        """Initialize request tracking with Flask app"""
        app.before_request(self._before_request)
        app.after_request(self._after_request)
        app.teardown_appcontext(self._teardown_request)
    
    def _before_request(self):
        """Setup request context"""
        # Generate correlation ID
        g.request_id = request.headers.get('X-Request-ID') or str(uuid.uuid4())
        g.start_time = time.time()
        
        # Log request start
        logger = get_logger()
        logger.info(
            f"Request started: {request.method} {request.path}",
            event_type='request_start',
            request_id=g.request_id
        )
    
    def _after_request(self, response):
        """Log request completion"""
        if hasattr(g, 'start_time'):
            duration = time.time() - g.start_time
            
            logger = get_logger()
            logger.log_request(
                duration=duration,
                status_code=response.status_code,
                response_size=len(response.get_data()) if hasattr(response, 'get_data') else None
            )
            
            # Add correlation ID to response
            response.headers['X-Request-ID'] = g.request_id
        
        return response
    
    def _teardown_request(self, exception):
        """Handle request teardown"""
        if exception:
            logger = get_logger()
            logger.exception(
                f"Request failed: {request.method} {request.path}",
                event_type='request_error',
                exception_type=type(exception).__name__
            )


# Global logger instances
_loggers: Dict[str, StructuredLogger] = {}


def get_logger(name: str = 'app') -> StructuredLogger:
    """Get or create structured logger instance"""
    if name not in _loggers:
        _loggers[name] = StructuredLogger(name)
    return _loggers[name]


def init_logging(app: Flask) -> StructuredLogger:
    """Initialize logging system with Flask app"""
    # Create logs directory if it doesn't exist
    import os
    os.makedirs('logs', exist_ok=True)
    
    # Setup main logger
    logger = get_logger('app')
    logger.app = app
    logger._setup_logger()
    
    # Setup request tracking
    RequestTracker(app)
    
    # Log application startup
    logger.info(
        "Application started",
        event_type='application_start',
        environment=app.config.get('ENV', 'development'),
        debug=app.debug
    )
    
    return logger


def log_performance(operation: str):
    """Decorator to log function performance"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            start_time = time.time()
            try:
                result = f(*args, **kwargs)
                duration = time.time() - start_time
                
                logger = get_logger()
                logger.log_performance(
                    operation=operation,
                    duration=duration,
                    function=f.__name__,
                    success=True
                )
                
                return result
            except Exception as e:
                duration = time.time() - start_time
                
                logger = get_logger()
                logger.log_performance(
                    operation=operation,
                    duration=duration,
                    function=f.__name__,
                    success=False,
                    error=str(e)
                )
                
                raise
        
        return decorated_function
    return decorator


def log_business_event(event_type: str):
    """Decorator to log business events"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            logger = get_logger()
            
            try:
                result = f(*args, **kwargs)
                
                logger.log_business_event(
                    event_type=event_type,
                    function=f.__name__,
                    success=True
                )
                
                return result
            except Exception as e:
                logger.log_business_event(
                    event_type=event_type,
                    function=f.__name__,
                    success=False,
                    error=str(e)
                )
                
                raise
        
        return decorated_function
    return decorator


class ErrorContext:
    """Context manager for error logging"""
    
    def __init__(self, operation: str, **context):
        self.operation = operation
        self.context = context
        self.logger = get_logger()
        self.start_time = None
    
    def __enter__(self):
        self.start_time = time.time()
        self.logger.info(
            f"Starting operation: {self.operation}",
            event_type='operation_start',
            operation=self.operation,
            **self.context
        )
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        duration = time.time() - self.start_time if self.start_time else None
        
        if exc_type:
            self.logger.error(
                f"Operation failed: {self.operation}",
                event_type='operation_error',
                operation=self.operation,
                duration_ms=duration * 1000 if duration else None,
                error_type=exc_type.__name__ if exc_type else None,
                error_message=str(exc_val) if exc_val else None,
                **self.context
            )
        else:
            self.logger.info(
                f"Operation completed: {self.operation}",
                event_type='operation_complete',
                operation=self.operation,
                duration_ms=duration * 1000 if duration else None,
                **self.context
            )
        
        return False  # Don't suppress exceptions


# Convenience functions
def info(message: str, **kwargs):
    """Log info message"""
    get_logger().info(message, **kwargs)


def warning(message: str, **kwargs):
    """Log warning message"""
    get_logger().warning(message, **kwargs)


def error(message: str, **kwargs):
    """Log error message"""
    get_logger().error(message, **kwargs)


def critical(message: str, **kwargs):
    """Log critical message"""
    get_logger().critical(message, **kwargs)


def exception(message: str, **kwargs):
    """Log exception with traceback"""
    get_logger().exception(message, **kwargs)