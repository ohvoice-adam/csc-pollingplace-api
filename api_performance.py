"""
API Performance Optimization Utilities

Provides pagination, caching, compression, and monitoring utilities
for optimizing API performance in the CSC Polling Place API.
"""

import math
import time
import hashlib
import json
import gzip
from typing import Dict, Any, Optional, List, Tuple
from functools import wraps
from flask import request, jsonify, Response
from datetime import datetime, timedelta


class PaginationHelper:
    """Utility class for handling API response pagination"""
    
    @staticmethod
    def get_pagination_params() -> Tuple[int, int]:
        """
        Extract pagination parameters from request
        Returns: (page, per_page)
        """
        try:
            page = max(1, int(request.args.get('page', 1)))
            per_page = min(100, max(1, int(request.args.get('per_page', 20))))
            return page, per_page
        except (ValueError, TypeError):
            return 1, 20
    
    @staticmethod
    def paginate_query(query, page: int, per_page: int):
        """
        Apply pagination to a SQLAlchemy query
        Returns: (items, total_count, pagination_info)
        """
        total_count = query.count()
        total_pages = math.ceil(total_count / per_page)
        
        # Ensure page is within bounds
        page = max(1, min(page, total_pages)) if total_pages > 0 else 1
        
        # Get paginated items
        items = query.offset((page - 1) * per_page).limit(per_page).all()
        
        pagination_info = {
            'page': page,
            'per_page': per_page,
            'total': total_count,
            'total_pages': total_pages,
            'has_prev': page > 1,
            'has_next': page < total_pages,
            'prev_num': page - 1 if page > 1 else None,
            'next_num': page + 1 if page < total_pages else None
        }
        
        return items, total_count, pagination_info
    
    @staticmethod
    def create_paginated_response(items: List[Any], pagination_info: Dict[str, Any], 
                                 items_key: str = 'items') -> Dict[str, Any]:
        """
        Create a standardized paginated response
        """
        return {
            'pagination': pagination_info,
            items_key: items
        }


class CacheManager:
    """Simple in-memory cache manager (can be extended to Redis)"""
    
    def __init__(self):
        self.cache = {}
        self.cache_times = {}
        self.default_ttl = 300  # 5 minutes
    
    def _generate_cache_key(self, prefix: str, **kwargs) -> str:
        """Generate a unique cache key based on request parameters"""
        key_data = {
            'endpoint': request.endpoint,
            'args': dict(request.args),
            'json': request.get_json(silent=True) or {},
            **kwargs
        }
        key_str = json.dumps(key_data, sort_keys=True)
        return f"{prefix}:{hashlib.md5(key_str.encode()).hexdigest()}"
    
    def get(self, key: str) -> Optional[Any]:
        """Get cached value if not expired"""
        if key in self.cache and key in self.cache_times:
            if time.time() - self.cache_times[key] < self.default_ttl:
                return self.cache[key]
            else:
                # Expired, remove from cache
                del self.cache[key]
                del self.cache_times[key]
        return None
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Set value in cache with optional TTL"""
        self.cache[key] = value
        self.cache_times[key] = time.time()
        if ttl:
            # Store custom TTL by encoding it in the key
            self.cache_times[f"{key}_ttl"] = ttl
    
    def delete(self, key: str) -> None:
        """Delete specific cache entry"""
        if key in self.cache:
            del self.cache[key]
        if key in self.cache_times:
            del self.cache_times[key]
    
    def clear(self) -> None:
        """Clear all cache entries"""
        self.cache.clear()
        self.cache_times.clear()
    
    def cleanup_expired(self) -> int:
        """Remove expired entries and return count of removed items"""
        current_time = time.time()
        expired_keys = []
        
        for key, cache_time in self.cache_times.items():
            if not key.endswith('_ttl'):
                ttl = self.cache_times.get(f"{key}_ttl", self.default_ttl)
                if current_time - cache_time >= ttl:
                    expired_keys.append(key)
        
        for key in expired_keys:
            self.delete(key)
            # Also remove TTL entry if exists
            ttl_key = f"{key}_ttl"
            if ttl_key in self.cache_times:
                del self.cache_times[ttl_key]
        
        return len(expired_keys)


# Global cache instance
cache_manager = CacheManager()


def cache_response(ttl: int = 300, key_prefix: str = "api"):
    """
    Decorator to cache API responses
    Args:
        ttl: Time to live in seconds (default: 5 minutes)
        key_prefix: Prefix for cache key
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Skip caching for non-GET requests
            if request.method != 'GET':
                return f(*args, **kwargs)
            
            # Generate cache key
            cache_key = cache_manager._generate_cache_key(key_prefix, **kwargs)
            
            # Try to get from cache
            cached_response = cache_manager.get(cache_key)
            if cached_response is not None:
                return cached_response
            
            # Execute function and cache result
            response = f(*args, **kwargs)
            
            # Only cache successful responses
            if hasattr(response, 'status_code') and response.status_code == 200:
                cache_manager.set(cache_key, response, ttl)
            elif isinstance(response, tuple) and len(response) >= 2 and response[1] == 200:
                cache_manager.set(cache_key, response, ttl)
            
            return response
        
        return decorated_function
    return decorator


def compress_response(f):
    """
    Decorator to compress API responses using gzip
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        response = f(*args, **kwargs)
        
        # Only compress successful JSON responses
        should_compress = (
            request.headers.get('Accept-Encoding', '').find('gzip') != -1 and
            (
                (hasattr(response, 'status_code') and response.status_code == 200) or
                (isinstance(response, tuple) and len(response) >= 2 and response[1] == 200)
            )
        )
        
        if not should_compress:
            return response
        
        # Extract response data and status
        if isinstance(response, tuple):
            data, status_code = response[0], response[1]
            headers = response[2] if len(response) > 2 else {}
        else:
            data, status_code, headers = response, 200, {}
        
        # Only compress if response is large enough (> 1KB)
        if isinstance(data, (dict, list)):
            json_str = json.dumps(data)
            if len(json_str) > 1024:  # Only compress if > 1KB
                compressed_data = gzip.compress(json_str.encode('utf-8'))
                
                # Create compressed response
                compressed_response = Response(
                    compressed_data,
                    status=status_code,
                    headers={
                        'Content-Encoding': 'gzip',
                        'Content-Type': 'application/json',
                        'Vary': 'Accept-Encoding',
                        **headers
                    }
                )
                return compressed_response
        
        return response
    
    return decorated_function


def monitor_response_time(f):
    """
    Decorator to monitor API response times
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        start_time = time.time()
        
        try:
            response = f(*args, **kwargs)
            success = True
            status_code = getattr(response, 'status_code', 200) if hasattr(response, 'status_code') else (response[1] if isinstance(response, tuple) and len(response) > 1 else 200)
        except Exception as e:
            response = jsonify({'error': str(e)}), 500
            success = False
            status_code = 500
        
        end_time = time.time()
        response_time = (end_time - start_time) * 1000  # Convert to milliseconds
        
        # Log response time
        app_logger = getattr(f, '__self__', None)
        if hasattr(app_logger, 'logger'):
            logger = app_logger.logger
        else:
            import logging
            logger = logging.getLogger(__name__)
        
        log_level = logging.WARNING if response_time > 1000 else logging.INFO
        logger.log(
            log_level,
            f"API Performance: {request.endpoint} - {response_time:.2f}ms - "
            f"Status: {status_code} - Success: {success}"
        )
        
        # Add response time to response headers for debugging
        if isinstance(response, tuple):
            if len(response) == 2:
                data, status = response
                headers = {}
            else:
                data, status, headers = response
            
            headers['X-Response-Time'] = f"{response_time:.2f}ms"
            return data, status, headers
        elif hasattr(response, 'headers'):
            response.headers['X-Response-Time'] = f"{response_time:.2f}ms"
        
        return response
    
    return decorated_function


class QueryOptimizer:
    """Utility class for optimizing database queries"""
    
    @staticmethod
    def apply_eager_loading(query, model, relationships: List[str] = None):
        """
        Apply eager loading to prevent N+1 queries
        Args:
            query: SQLAlchemy query
            model: SQLAlchemy model class
            relationships: List of relationship names to eager load
        """
        if not relationships:
            return query
        
        from sqlalchemy.orm import joinedload, selectinload
        
        eager_loads = []
        for rel in relationships:
            if hasattr(model, rel):
                eager_loads.append(joinedload(getattr(model, rel)))
        
        if eager_loads:
            return query.options(*eager_loads)
        return query
    
    @staticmethod
    def apply_filters(query, model, filters: Dict[str, Any]):
        """
        Apply common filters to a query
        Args:
            query: SQLAlchemy query
            model: SQLAlchemy model class
            filters: Dictionary of field_name -> value mappings
        """
        for field, value in filters.items():
            if value is not None and hasattr(model, field):
                field_attr = getattr(model, field)
                
                # Handle different filter types
                if isinstance(value, dict):
                    # Range filters
                    if 'min' in value:
                        query = query.filter(field_attr >= value['min'])
                    if 'max' in value:
                        query = query.filter(field_attr <= value['max'])
                    if 'like' in value:
                        query = query.filter(field_attr.ilike(f"%{value['like']}%"))
                    if 'in' in value:
                        query = query.filter(field_attr.in_(value['in']))
                else:
                    # Exact match
                    query = query.filter(field_attr == value)
        
        return query
    
    @staticmethod
    def get_optimized_count(query) -> int:
        """
        Get optimized count for large queries
        """
        try:
            # For simple queries, use count()
            return query.count()
        except Exception:
            # For complex queries, use subquery
            try:
                return query.statement.count()
            except Exception:
                # Fallback to len() for small result sets
                return len(query.all())


class AsyncTaskManager:
    """Simple async task manager for background processing"""
    
    def __init__(self):
        self.tasks = {}
        self.task_results = {}
    
    def create_task(self, task_id: str, func, *args, **kwargs):
        """
        Create and start a background task
        """
        import threading
        
        def task_worker():
            try:
                result = func(*args, **kwargs)
                self.task_results[task_id] = {
                    'status': 'completed',
                    'result': result,
                    'completed_at': datetime.utcnow()
                }
            except Exception as e:
                self.task_results[task_id] = {
                    'status': 'failed',
                    'error': str(e),
                    'completed_at': datetime.utcnow()
                }
            finally:
                # Clean up task from active tasks
                if task_id in self.tasks:
                    del self.tasks[task_id]
        
        # Mark task as running
        self.tasks[task_id] = {
            'status': 'running',
            'started_at': datetime.utcnow()
        }
        
        # Start background thread
        thread = threading.Thread(target=task_worker)
        thread.daemon = True
        thread.start()
        
        return task_id
    
    def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """
        Get status of a background task
        """
        if task_id in self.tasks:
            return self.tasks[task_id]
        elif task_id in self.task_results:
            return self.task_results[task_id]
        else:
            return {'status': 'not_found'}
    
    def cancel_task(self, task_id: str) -> bool:
        """
        Cancel a running task (best effort)
        """
        if task_id in self.tasks:
            self.tasks[task_id]['status'] = 'cancelled'
            self.task_results[task_id] = {
                'status': 'cancelled',
                'completed_at': datetime.utcnow()
            }
            del self.tasks[task_id]
            return True
        return False


# Global async task manager
async_task_manager = AsyncTaskManager()


def paginate_api_response(items_key: str = 'items', default_per_page: int = 20):
    """
    Decorator to automatically paginate API responses
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Get pagination parameters
            page, per_page = PaginationHelper.get_pagination_params()
            per_page = min(per_page, 100)  # Max 100 items per page
            
            # Call original function
            result = f(*args, **kwargs)
            
            # Handle different response types
            if isinstance(result, tuple):
                data, status_code = result[0], result[1]
                headers = result[2] if len(result) > 2 else {}
            else:
                data, status_code, headers = result, 200, {}
            
            # If data is already paginated, return as-is
            if isinstance(data, dict) and 'pagination' in data:
                return data, status_code, headers
            
            # If data is a query, paginate it
            if hasattr(data, 'count') and hasattr(data, 'offset') and hasattr(data, 'limit'):
                items, total_count, pagination_info = PaginationHelper.paginate_query(
                    data, page, per_page
                )
                paginated_data = PaginationHelper.create_paginated_response(
                    items, pagination_info, items_key
                )
                return paginated_data, status_code, headers
            
            # If data is a list, paginate it
            elif isinstance(data, list):
                total_count = len(data)
                total_pages = math.ceil(total_count / per_page)
                
                # Ensure page is within bounds
                page = max(1, min(page, total_pages)) if total_pages > 0 else 1
                
                start_idx = (page - 1) * per_page
                end_idx = start_idx + per_page
                items = data[start_idx:end_idx]
                
                pagination_info = {
                    'page': page,
                    'per_page': per_page,
                    'total': total_count,
                    'total_pages': total_pages,
                    'has_prev': page > 1,
                    'has_next': page < total_pages,
                    'prev_num': page - 1 if page > 1 else None,
                    'next_num': page + 1 if page < total_pages else None
                }
                
                paginated_data = PaginationHelper.create_paginated_response(
                    items, pagination_info, items_key
                )
                return paginated_data, status_code, headers
            
            # Otherwise, return as-is
            return result
        
        return decorated_function
    return decorator