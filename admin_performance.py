"""
Admin Performance Optimization Utilities

Provides lazy loading, client-side caching, asset minification,
map clustering, and progressive loading for admin interface.
"""

import os
import json
import time
import hashlib
from typing import Dict, Any, List, Optional, Tuple
from functools import wraps
from flask import request, jsonify, Response, current_app
from datetime import datetime, timedelta


class LazyLoadManager:
    """Manages lazy loading for large datasets in admin interface"""
    
    def __init__(self, default_page_size: int = 50, max_page_size: int = 500):
        self.default_page_size = default_page_size
        self.max_page_size = max_page_size
        self.cache: Dict[str, Any] = {}
        self.cache_timeout = 300  # 5 minutes
    
    def get_pagination_params(self) -> Dict[str, int]:
        """Extract pagination parameters from request"""
        page_str = request.args.get('page', '1')
        per_page_str = request.args.get('per_page', str(self.default_page_size))
        
        page = max(1, int(page_str) if page_str else 1)
        per_page = min(
            self.max_page_size,
            max(1, int(per_page_str) if per_page_str else self.default_page_size)
        )
        offset = (page - 1) * per_page
        
        return {
            'page': page,
            'per_page': per_page,
            'offset': offset
        }
    
    def paginate_query(self, query, total_count: Optional[int] = None) -> Dict[str, Any]:
        """Paginate a database query with metadata"""
        params = self.get_pagination_params()
        
        if total_count is None:
            count_result = query.count()
            total_count = count_result if count_result is not None else 0
        
        items = query.offset(params['offset']).limit(params['per_page']).all()
        
        total_pages = (total_count + params['per_page'] - 1) // params['per_page'] if params['per_page'] > 0 else 1
        
        return {
            'items': items,
            'pagination': {
                'page': params['page'],
                'per_page': params['per_page'],
                'total': total_count,
                'total_pages': total_pages,
                'has_next': params['page'] < total_pages,
                'has_prev': params['page'] > 1,
                'next_page': params['page'] + 1 if params['page'] < total_pages else None,
                'prev_page': params['page'] - 1 if params['page'] > 1 else None
            }
        }


class AssetManager:
    """Manages CSS/JS minification and client-side caching"""
    
    def __init__(self, cache_dir: str = 'static/cache'):
        self.cache_dir = cache_dir
        self.manifest: Dict[str, str] = {}
        self.ensure_cache_dir()
        self.load_manifest()
    
    def ensure_cache_dir(self):
        """Ensure cache directory exists"""
        if not os.path.exists(self.cache_dir):
            os.makedirs(self.cache_dir)
    
    def load_manifest(self):
        """Load asset manifest for cache busting"""
        manifest_path = os.path.join(self.cache_dir, 'manifest.json')
        if os.path.exists(manifest_path):
            with open(manifest_path, 'r') as f:
                self.manifest = json.load(f)
    
    def save_manifest(self):
        """Save asset manifest"""
        manifest_path = os.path.join(self.cache_dir, 'manifest.json')
        with open(manifest_path, 'w') as f:
            json.dump(self.manifest, f, indent=2)
    
    def get_asset_hash(self, file_path: str) -> str:
        """Generate hash for asset file"""
        try:
            with open(file_path, 'rb') as f:
                content = f.read()
            return hashlib.md5(content).hexdigest()[:8]
        except:
            return str(int(time.time()))
    
    def minify_css(self, css_content: str) -> str:
        """Simple CSS minification"""
        # Remove comments
        css_content = self._remove_css_comments(css_content)
        # Remove whitespace
        css_content = self._minify_whitespace(css_content)
        return css_content
    
    def _remove_css_comments(self, content: str) -> str:
        """Remove CSS comments"""
        import re
        return re.sub(r'/\*.*?\*/', '', content, flags=re.DOTALL)
    
    def _minify_whitespace(self, content: str) -> str:
        """Remove unnecessary whitespace"""
        import re
        # Remove newlines and tabs
        content = re.sub(r'[\n\t]', '', content)
        # Remove multiple spaces
        content = re.sub(r'\s+', ' ', content)
        # Remove spaces around special characters
        content = re.sub(r'\s*([{}:;,])\s*', r'\1', content)
        return content
    
    def get_cached_asset_url(self, original_path: str) -> str:
        """Get cached asset URL with cache busting"""
        if original_path in self.manifest:
            return f"/static/cache/{self.manifest[original_path]}"
        
        # Generate cached version
        file_path = original_path.lstrip('/static/')
        full_path = os.path.join('static', file_path)
        
        if os.path.exists(full_path):
            file_hash = self.get_asset_hash(full_path)
            filename, ext = os.path.splitext(file_path)
            cached_filename = f"{filename}.{file_hash}{ext}"
            cached_path = os.path.join(self.cache_dir, cached_filename)
            
            # Copy and minify if needed
            if not os.path.exists(cached_path):
                self._process_asset(full_path, cached_path)
            
            # Update manifest
            self.manifest[original_path] = cached_filename
            self.save_manifest()
            
            return f"/static/cache/{cached_filename}"
        
        return original_path
    
    def _process_asset(self, source_path: str, target_path: str):
        """Process and cache an asset"""
        with open(source_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        if source_path.endswith('.css'):
            content = self.minify_css(content)
        
        with open(target_path, 'w', encoding='utf-8') as f:
            f.write(content)


class MapClusterManager:
    """Manages map clustering for large datasets"""
    
    def __init__(self, cluster_radius: int = 50):
        self.cluster_radius = cluster_radius
    
    def cluster_markers(self, markers: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Cluster markers using simple grid-based clustering"""
        if not markers:
            return []
        
        # Create grid for clustering
        clusters = {}
        
        for marker in markers:
            lat = marker.get('lat', 0)
            lng = marker.get('lng', 0)
            
            # Calculate grid cell
            lat_cell = int(lat / (self.cluster_radius / 111000))  # Convert to degrees
            lng_cell = int(lng / (self.cluster_radius / (111000 * abs(lat) if lat else 111000)))
            
            cell_key = f"{lat_cell}_{lng_cell}"
            
            if cell_key not in clusters:
                clusters[cell_key] = {
                    'lat': lat,
                    'lng': lng,
                    'markers': [],
                    'count': 0
                }
            
            clusters[cell_key]['markers'].append(marker)
            clusters[cell_key]['count'] += 1
        
        # Convert clusters to markers
        result = []
        for cluster in clusters.values():
            if cluster['count'] == 1:
                result.append(cluster['markers'][0])
            else:
                # Calculate cluster center
                avg_lat = sum(m['lat'] for m in cluster['markers']) / len(cluster['markers'])
                avg_lng = sum(m['lng'] for m in cluster['markers']) / len(cluster['markers'])
                
                result.append({
                    'lat': avg_lat,
                    'lng': avg_lng,
                    'count': cluster['count'],
                    'markers': cluster['markers'],
                    'is_cluster': True
                })
        
        return result


class ProgressiveLoadManager:
    """Manages progressive loading for polling place data"""
    
    def __init__(self, chunk_size: int = 100):
        self.chunk_size = chunk_size
        self.active_sessions: Dict[str, Dict[str, Any]] = {}
    
    def start_progressive_load(self, session_id: str, total_count: int) -> Dict[str, Any]:
        """Start a progressive loading session"""
        self.active_sessions[session_id] = {
            'total_count': total_count,
            'loaded_count': 0,
            'chunks_loaded': 0,
            'total_chunks': (total_count + self.chunk_size - 1) // self.chunk_size,
            'started_at': datetime.now(),
            'last_activity': datetime.now()
        }
        
        status = self.get_session_status(session_id)
        return status if status is not None else {}
    
    def get_next_chunk(self, session_id: str, query_func) -> Optional[Dict[str, Any]]:
        """Get next chunk of data for progressive loading"""
        if session_id not in self.active_sessions:
            return None
        
        session = self.active_sessions[session_id]
        
        if session['loaded_count'] >= session['total_count']:
            return None
        
        # Get next chunk
        offset = session['loaded_count']
        chunk = query_func(offset=offset, limit=self.chunk_size)
        
        if not chunk:
            return None
        
        # Update session
        session['loaded_count'] += len(chunk)
        session['chunks_loaded'] += 1
        session['last_activity'] = datetime.now()
        
        return {
            'data': chunk,
            'session_id': session_id,
            'chunk_index': session['chunks_loaded'] - 1,
            'is_complete': session['loaded_count'] >= session['total_count'],
            'progress': {
                'loaded': session['loaded_count'],
                'total': session['total_count'],
                'percentage': (session['loaded_count'] / session['total_count']) * 100
            }
        }
    
    def get_session_status(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get status of progressive loading session"""
        if session_id not in self.active_sessions:
            return None
        
        session = self.active_sessions[session_id]
        
        return {
            'session_id': session_id,
            'total_count': session['total_count'],
            'loaded_count': session['loaded_count'],
            'chunks_loaded': session['chunks_loaded'],
            'total_chunks': session['total_chunks'],
            'is_complete': session['loaded_count'] >= session['total_count'],
            'progress_percentage': (session['loaded_count'] / session['total_count']) * 100,
            'started_at': session['started_at'].isoformat(),
            'last_activity': session['last_activity'].isoformat()
        }
    
    def cleanup_expired_sessions(self, max_age_hours: int = 2):
        """Clean up expired sessions"""
        cutoff_time = datetime.now() - timedelta(hours=max_age_hours)
        
        expired_sessions = [
            session_id for session_id, session in self.active_sessions.items()
            if session['last_activity'] < cutoff_time
        ]
        
        for session_id in expired_sessions:
            del self.active_sessions[session_id]
        
        return len(expired_sessions)


# Global instances
lazy_load_manager = LazyLoadManager()
asset_manager = AssetManager()
map_cluster_manager = MapClusterManager()
progressive_load_manager = ProgressiveLoadManager()

# Simple in-memory cache for admin responses
admin_cache: Dict[str, Dict[str, Any]] = {}


def admin_cache_response(ttl: int = 300, cache_key_prefix: str = "admin"):
    """Decorator for caching admin responses"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Generate cache key
            cache_key_data = {
                'endpoint': request.endpoint,
                'args': args,
                'kwargs': kwargs,
                'query_params': dict(request.args)
            }
            hash_digest = hashlib.md5(
                json.dumps(cache_key_data, sort_keys=True).encode()
            ).hexdigest()
            cache_key = f"{cache_key_prefix}:{hash_digest}"
            
            # Check cache
            cached = admin_cache.get(cache_key)
            if cached and (time.time() - cached['timestamp'] < ttl):
                return cached['response']
            
            # Generate response
            response = f(*args, **kwargs)
            
            # Cache response
            admin_cache[cache_key] = {
                'response': response,
                'timestamp': time.time()
            }
            
            return response
        return decorated_function
    return decorator


def optimize_admin_assets():
    """Initialize admin asset optimization"""
    # Pre-process common assets
    common_css = [
        '/static/css/flask_admin_custom.css'
    ]
    
    for css_path in common_css:
        asset_manager.get_cached_asset_url(css_path)
    
    return {
        'css_files': [asset_manager.get_cached_asset_url(path) for path in common_css],
        'js_files': [],  # Add JS files as needed
        'cache_buster': int(time.time())
    }