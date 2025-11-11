"""
Graceful Degradation Module

Provides fallback mechanisms and graceful degradation for external service failures.
Implements circuit breakers, fallback responses, and service health monitoring.
"""

import time
import json
import asyncio
from typing import Dict, Any, Optional, Callable, Union, List
from dataclasses import dataclass, field
from enum import Enum
from functools import wraps
from datetime import datetime, timedelta
import logging

try:
    from redis import Redis as RedisType
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    RedisType = None

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

from structured_logging import get_logger, log_performance
from error_tracking import ErrorTracker, error_tracker

logger = get_logger(__name__)


class ServiceStatus(Enum):
    """Service health status"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    FAILED = "failed"
    UNKNOWN = "unknown"


@dataclass
class FallbackConfig:
    """Configuration for fallback behavior"""
    enabled: bool = True
    fallback_data: Optional[Dict[str, Any]] = None
    fallback_function: Optional[Callable] = None
    max_fallback_age: int = 300  # 5 minutes
    cache_fallback: bool = True


@dataclass
class ServiceHealth:
    """Service health tracking"""
    status: ServiceStatus = ServiceStatus.UNKNOWN
    last_check: Optional[datetime] = None
    failure_count: int = 0
    success_count: int = 0
    last_failure: Optional[datetime] = None
    last_success: Optional[datetime] = None
    response_time: Optional[float] = None
    error_message: Optional[str] = None


@dataclass
class DegradationLevel:
    """Degradation level configuration"""
    level: int
    name: str
    description: str
    max_failure_rate: float
    min_response_time: float
    actions: List[str] = field(default_factory=list)


class GracefulDegradationManager:
    """Manages graceful degradation for external services"""
    
    def __init__(self, redis_client: Optional[RedisType] = None):
        self.redis_client = redis_client
        self.services: Dict[str, ServiceHealth] = {}
        self.fallback_configs: Dict[str, FallbackConfig] = {}
        self.degradation_levels = self._init_degradation_levels()
        self.circuit_breakers: Dict[str, Dict[str, Any]] = {}
        
        # Default degradation settings
        self.default_settings = {
            'circuit_breaker_threshold': 5,
            'circuit_breaker_timeout': 60,
            'health_check_interval': 30,
            'max_response_time': 5.0,
            'failure_rate_threshold': 0.5
        }
    
    def _init_degradation_levels(self) -> List[DegradationLevel]:
        """Initialize degradation levels"""
        return [
            DegradationLevel(
                level=1,
                name="minimal",
                description="Service responding slowly",
                max_failure_rate=0.1,
                min_response_time=2.0,
                actions=["log_warning", "increase_timeout"]
            ),
            DegradationLevel(
                level=2,
                name="moderate",
                description="Service experiencing issues",
                max_failure_rate=0.3,
                min_response_time=5.0,
                actions=["use_cache", "reduce_requests", "log_error"]
            ),
            DegradationLevel(
                level=3,
                name="severe",
                description="Service mostly unavailable",
                max_failure_rate=0.7,
                min_response_time=10.0,
                actions=["use_fallback", "circuit_breaker", "alert_admin"]
            ),
            DegradationLevel(
                level=4,
                name="critical",
                description="Service completely unavailable",
                max_failure_rate=1.0,
                min_response_time=float('inf'),
                actions=["disable_service", "emergency_fallback", "critical_alert"]
            )
        ]
    
    def register_service(self, service_name: str, fallback_config: Optional[FallbackConfig] = None):
        """Register a service for degradation monitoring"""
        if service_name not in self.services:
            self.services[service_name] = ServiceHealth()
        
        if fallback_config:
            self.fallback_configs[service_name] = fallback_config
        
        # Initialize circuit breaker
        self.circuit_breakers[service_name] = {
            'state': 'closed',  # closed, open, half_open
            'failure_count': 0,
            'last_failure_time': None,
            'success_count': 0
        }
        
        logger.info("Registered service for degradation monitoring", 
                   service=service_name, has_fallback=fallback_config is not None)
    
    def check_service_health(self, service_name: str, health_check_func: Callable) -> ServiceHealth:
        """Check service health using provided function"""
        if service_name not in self.services:
            self.register_service(service_name)
        
        health = self.services[service_name]
        start_time = time.time()
        
        try:
            # Execute health check
            result = health_check_func()
            response_time = time.time() - start_time
            
            # Update health status
            health.status = ServiceStatus.HEALTHY
            health.last_check = datetime.utcnow()
            health.success_count += 1
            health.last_success = datetime.utcnow()
            health.response_time = response_time
            health.error_message = None
            
            # Update circuit breaker
            self._update_circuit_breaker(service_name, success=True)
            
            logger.info("Service health check passed", 
                       service=service_name, response_time=response_time)
            
            return health
            
        except Exception as e:
            response_time = time.time() - start_time
            
            # Update health status
            health.status = ServiceStatus.FAILED
            health.last_check = datetime.utcnow()
            health.failure_count += 1
            health.last_failure = datetime.utcnow()
            health.response_time = response_time
            health.error_message = str(e)
            
            # Update circuit breaker
            self._update_circuit_breaker(service_name, success=False)
            
            logger.error("Service health check failed", 
                        service=service_name, error=str(e), response_time=response_time)
            
            return health
    
    def _update_circuit_breaker(self, service_name: str, success: bool):
        """Update circuit breaker state"""
        if service_name not in self.circuit_breakers:
            return
        
        breaker = self.circuit_breakers[service_name]
        threshold = self.default_settings['circuit_breaker_threshold']
        timeout = self.default_settings['circuit_breaker_timeout']
        
        if success:
            breaker['success_count'] += 1
            if breaker['state'] == 'half_open':
                # Reset to closed after success in half-open state
                breaker['state'] = 'closed'
                breaker['failure_count'] = 0
                logger.info("Circuit breaker closed", service=service_name)
        else:
            breaker['failure_count'] += 1
            breaker['last_failure_time'] = datetime.utcnow()
            
            if breaker['state'] == 'closed' and breaker['failure_count'] >= threshold:
                breaker['state'] = 'open'
                logger.warning("Circuit breaker opened", service=service_name, 
                             failure_count=breaker['failure_count'])
            elif breaker['state'] == 'half_open':
                breaker['state'] = 'open'
                logger.warning("Circuit breaker re-opened", service=service_name)
        
        # Check if circuit breaker should transition to half-open
        if (breaker['state'] == 'open' and 
            breaker['last_failure_time'] and
            (datetime.utcnow() - breaker['last_failure_time']).seconds >= timeout):
            breaker['state'] = 'half_open'
            logger.info("Circuit breaker half-open", service=service_name)
    
    def get_degradation_level(self, service_name: str) -> Optional[DegradationLevel]:
        """Determine current degradation level for a service"""
        if service_name not in self.services:
            return None
        
        health = self.services[service_name]
        
        # Calculate failure rate
        total_requests = health.failure_count + health.success_count
        failure_rate = health.failure_count / total_requests if total_requests > 0 else 0
        
        # Find appropriate degradation level
        for level in reversed(self.degradation_levels):
            if (failure_rate >= level.max_failure_rate or
                (health.response_time and health.response_time >= level.min_response_time)):
                return level
        
        return None
    
    def execute_with_fallback(self, service_name: str, func: Callable, *args, **kwargs) -> Any:
        """Execute function with fallback support"""
        # Check circuit breaker
        if self._is_circuit_breaker_open(service_name):
            logger.warning("Circuit breaker open, using fallback", service=service_name)
            return self._get_fallback_response(service_name, *args, **kwargs)
        
        try:
            # Execute original function
            result = func(*args, **kwargs)
            
            # Record success
            if service_name in self.services:
                self.services[service_name].success_count += 1
                self.services[service_name].last_success = datetime.utcnow()
            
            return result
            
        except Exception as e:
            # Record failure
            if service_name in self.services:
                self.services[service_name].failure_count += 1
                self.services[service_name].last_failure = datetime.utcnow()
                self.services[service_name].error_message = str(e)
            
            # Update circuit breaker
            self._update_circuit_breaker(service_name, success=False)
            
            # Get fallback response
            logger.warning("Service call failed, using fallback", 
                         service=service_name, error=str(e))
            return self._get_fallback_response(service_name, *args, **kwargs)
    
    def _is_circuit_breaker_open(self, service_name: str) -> bool:
        """Check if circuit breaker is open for a service"""
        if service_name not in self.circuit_breakers:
            return False
        
        breaker = self.circuit_breakers[service_name]
        return breaker['state'] == 'open'
    
    def _get_fallback_response(self, service_name: str, *args, **kwargs) -> Any:
        """Get fallback response for a service"""
        fallback_config = self.fallback_configs.get(service_name)
        
        if not fallback_config or not fallback_config.enabled:
            raise Exception(f"Service {service_name} unavailable and no fallback configured")
        
        # Try fallback function first
        if fallback_config.fallback_function:
            try:
                return fallback_config.fallback_function(*args, **kwargs)
            except Exception as e:
                logger.error("Fallback function failed", service=service_name, error=str(e))
        
        # Try fallback data
        if fallback_config.fallback_data:
            return fallback_config.fallback_data
        
        # Default fallback
        return {"status": "degraded", "message": "Service temporarily unavailable"}
    
    def get_service_status(self, service_name: str) -> Dict[str, Any]:
        """Get comprehensive service status"""
        if service_name not in self.services:
            return {"status": "unknown", "message": "Service not registered"}
        
        health = self.services[service_name]
        degradation_level = self.get_degradation_level(service_name)
        breaker = self.circuit_breakers.get(service_name, {})
        
        return {
            "service": service_name,
            "status": health.status.value,
            "degradation_level": degradation_level.name if degradation_level else None,
            "circuit_breaker_state": breaker.get('state', 'unknown'),
            "failure_count": health.failure_count,
            "success_count": health.success_count,
            "last_check": health.last_check.isoformat() if health.last_check else None,
            "last_failure": health.last_failure.isoformat() if health.last_failure else None,
            "last_success": health.last_success.isoformat() if health.last_success else None,
            "response_time": health.response_time,
            "error_message": health.error_message,
            "has_fallback": service_name in self.fallback_configs
        }
    
    def get_all_services_status(self) -> Dict[str, Any]:
        """Get status of all registered services"""
        return {
            "services": {name: self.get_service_status(name) for name in self.services},
            "total_services": len(self.services),
            "healthy_services": len([s for s in self.services.values() if s.status == ServiceStatus.HEALTHY]),
            "failed_services": len([s for s in self.services.values() if s.status == ServiceStatus.FAILED]),
            "degraded_services": len([s for s in self.services.values() if s.status == ServiceStatus.DEGRADED])
        }


# Global instance
degradation_manager = GracefulDegradationManager()


def with_fallback(service_name: str, fallback_config: Optional[FallbackConfig] = None):
    """Decorator for adding fallback support to functions"""
    def decorator(func: Callable) -> Callable:
        # Register service if not already registered
        if service_name not in degradation_manager.services:
            degradation_manager.register_service(service_name, fallback_config)
        
        @wraps(func)
        def wrapper(*args, **kwargs):
            return degradation_manager.execute_with_fallback(service_name, func, *args, **kwargs)
        
        return wrapper
    return decorator


def with_circuit_breaker(service_name: str, threshold: int = 5, timeout: int = 60):
    """Decorator for adding circuit breaker support to functions"""
    def decorator(func: Callable) -> Callable:
        # Register service if not already registered
        if service_name not in degradation_manager.services:
            degradation_manager.register_service(service_name)
        
        # Update circuit breaker settings
        if service_name in degradation_manager.circuit_breakers:
            degradation_manager.default_settings['circuit_breaker_threshold'] = threshold
            degradation_manager.default_settings['circuit_breaker_timeout'] = timeout
        
        @wraps(func)
        def wrapper(*args, **kwargs):
            return degradation_manager.execute_with_fallback(service_name, func, *args, **kwargs)
        
        return wrapper
    return decorator


# Predefined fallback functions
def get_default_geocoding_fallback(address: str) -> Dict[str, Any]:
    """Default fallback for geocoding service"""
    return {
        "status": "fallback",
        "message": "Geocoding service unavailable",
        "address": address,
        "coordinates": {"lat": None, "lng": None},
        "accuracy": None
    }


def get_default_database_fallback(query: str) -> Dict[str, Any]:
    """Default fallback for database service"""
    return {
        "status": "fallback",
        "message": "Database service unavailable",
        "data": [],
        "query": query
    }


def get_default_cache_fallback(key: str) -> Any:
    """Default fallback for cache service"""
    return None


# Predefined fallback configurations
GEOCODING_FALLBACK = FallbackConfig(
    enabled=True,
    fallback_function=get_default_geocoding_fallback,
    cache_fallback=True
)

DATABASE_FALLBACK = FallbackConfig(
    enabled=True,
    fallback_function=get_default_database_fallback,
    cache_fallback=False
)

CACHE_FALLBACK = FallbackConfig(
    enabled=True,
    fallback_function=get_default_cache_fallback,
    cache_fallback=True
)