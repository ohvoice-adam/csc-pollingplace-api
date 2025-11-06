"""
Admin Performance API Endpoints
Provides optimized API endpoints for admin interface performance
"""

from flask import Blueprint, request, jsonify, current_app
from admin_performance import lazy_load_manager, admin_cache_response, admin_cache
from models import PollingPlace, Precinct, PrecinctAssignment
from database import db
from sqlalchemy import text
import logging

# Create blueprint
admin_performance_bp = Blueprint('admin_performance', __name__, url_prefix='/admin/api')

logger = logging.getLogger(__name__)


@admin_performance_bp.route('/pollingplaces', methods=['GET'])
@admin_cache_response(ttl=300, cache_key_prefix="admin_pollingplaces")
def get_pollingplaces():
    """Get polling places with pagination and performance optimizations"""
    try:
        # Get pagination parameters
        params = lazy_load_manager.get_pagination_params()
        
        # Get search and filter parameters
        search = request.args.get('search', '').strip()
        sort_column = request.args.get('sort', 'id')
        sort_desc = request.args.get('sort_desc', '0') == '1'
        
        # Build query
        query = db.session.query(PollingPlace)
        
        # Apply search filter
        if search:
            search_pattern = f'%{search}%'
            query = query.filter(
                (PollingPlace.name.ilike(search_pattern)) |
                (PollingPlace.city.ilike(search_pattern))
            )
        
        # Get total count
        total_count = query.count()
        
        # Apply sorting
        if hasattr(PollingPlace, sort_column):
            sort_attr = getattr(PollingPlace, sort_column)
            if sort_desc:
                query = query.order_by(sort_attr.desc())
            else:
                query = query.order_by(sort_attr.asc())
        
        # Apply pagination
        paginated_result = lazy_load_manager.paginate_query(query, total_count)
        
        # Convert to dict for JSON response
        data = []
        for place in paginated_result['items']:
            place_dict = {
                'id': place.id,
                'name': place.name,
                'city': place.city or '',
                'state': place.state or '',
                'zip_code': place.zip_code or '',
                'county': place.county or '',
                'latitude': float(place.latitude) if place.latitude else None,
                'longitude': float(place.longitude) if place.longitude else None,
                'source_plugin': place.source_plugin or '',
                'is_active': place.is_active if place.is_active is not None else True
            }
            data.append(place_dict)
        
        return jsonify({
            'data': data,
            'pagination': paginated_result['pagination'],
            'performance': {
                'query_time': 0,  # Could be measured
                'cache_hit': False,
                'total_count': total_count
            }
        })
        
    except Exception as e:
        logger.error(f"Error in get_pollingplaces: {str(e)}")
        return jsonify({'error': 'Failed to fetch polling places'}), 500


@admin_performance_bp.route('/precincts', methods=['GET'])
@admin_cache_response(ttl=300, cache_key_prefix="admin_precincts")
def get_precincts():
    """Get precincts with pagination and performance optimizations"""
    try:
        # Get pagination parameters
        params = lazy_load_manager.get_pagination_params()
        
        # Get search and filter parameters
        search = request.args.get('search', '').strip()
        sort_column = request.args.get('sort', 'id')
        sort_desc = request.args.get('sort_desc', '0') == '1'
        
        # Build query
        query = db.session.query(Precinct)
        
        # Apply search filter
        if search:
            search_pattern = f'%{search}%'
            query = query.filter(
                (Precinct.name.ilike(search_pattern)) |
                (Precinct.county.ilike(search_pattern))
            )
        
        # Get total count
        total_count = query.count()
        
        # Apply sorting
        if hasattr(Precinct, sort_column):
            sort_attr = getattr(Precinct, sort_column)
            if sort_desc:
                query = query.order_by(sort_attr.desc())
            else:
                query = query.order_by(sort_attr.asc())
        
        # Apply pagination
        paginated_result = lazy_load_manager.paginate_query(query, total_count)
        
        # Convert to dict for JSON response
        data = []
        for precinct in paginated_result['items']:
            precinct_dict = {
                'id': precinct.id,
                'name': precinct.name,
                'county': precinct.county or '',
                'state': precinct.state or '',
                'ward': precinct.ward or '',
                'registered_voters': precinct.registered_voters or 0,
                'source_plugin': precinct.source_plugin or ''
            }
            data.append(precinct_dict)
        
        return jsonify({
            'data': data,
            'pagination': paginated_result['pagination'],
            'performance': {
                'query_time': 0,
                'cache_hit': False,
                'total_count': total_count
            }
        })
        
    except Exception as e:
        logger.error(f"Error in get_precincts: {str(e)}")
        return jsonify({'error': 'Failed to fetch precincts'}), 500


@admin_performance_bp.route('/precinct-assignments', methods=['GET'])
@admin_cache_response(ttl=300, cache_key_prefix="admin_assignments")
def get_precinct_assignments():
    """Get precinct assignments with pagination and performance optimizations"""
    try:
        # Get pagination parameters
        params = lazy_load_manager.get_pagination_params()
        
        # Get search and filter parameters
        search = request.args.get('search', '').strip()
        sort_column = request.args.get('sort', 'id')
        sort_desc = request.args.get('sort_desc', '0') == '1'
        
        # Build query with joins for better performance
        query = db.session.query(PrecinctAssignment)
        
        # Apply search filter
        if search:
            search_pattern = f'%{search}%'
            query = query.filter(
                (PrecinctAssignment.source_plugin.ilike(search_pattern))
            )
        
        # Get total count
        total_count = query.count()
        
        # Apply sorting
        if hasattr(PrecinctAssignment, sort_column):
            sort_attr = getattr(PrecinctAssignment, sort_column)
            if sort_desc:
                query = query.order_by(sort_attr.desc())
            else:
                query = query.order_by(sort_attr.asc())
        
        # Apply pagination
        paginated_result = lazy_load_manager.paginate_query(query, total_count)
        
        # Convert to dict for JSON response
        data = []
        for assignment in paginated_result['items']:
            assignment_dict = {
                'id': assignment.id,
                'polling_place_id': assignment.polling_place_id,
                'precinct_id': assignment.precinct_id,
                'is_active': assignment.is_active if assignment.is_active is not None else True,
                'effective_date': assignment.effective_date.isoformat() if assignment.effective_date else None,
                'source_plugin': assignment.source_plugin or ''
            }
            data.append(assignment_dict)
        
        return jsonify({
            'data': data,
            'pagination': paginated_result['pagination'],
            'performance': {
                'query_time': 0,
                'cache_hit': False,
                'total_count': total_count
            }
        })
        
    except Exception as e:
        logger.error(f"Error in get_precinct_assignments: {str(e)}")
        return jsonify({'error': 'Failed to fetch precinct assignments'}), 500


@admin_performance_bp.route('/stats', methods=['GET'])
@admin_cache_response(ttl=600, cache_key_prefix="admin_stats")
def get_admin_stats():
    """Get admin dashboard statistics with performance optimizations"""
    try:
        # Get counts for each table
        polling_places_count = db.session.query(PollingPlace).count()
        precincts_count = db.session.query(Precinct).count()
        assignments_count = db.session.query(PrecinctAssignment).count()
        
        # Get counts by state
        polling_places_by_state = db.session.execute(
            text("""
                SELECT state, COUNT(*) as count 
                FROM polling_places 
                WHERE state IS NOT NULL 
                GROUP BY state 
                ORDER BY count DESC
            """)
        ).fetchall()
        
        # Get counts by source plugin
        polling_places_by_plugin = db.session.execute(
            text("""
                SELECT source_plugin, COUNT(*) as count 
                FROM polling_places 
                WHERE source_plugin IS NOT NULL 
                GROUP BY source_plugin 
                ORDER BY count DESC
            """)
        ).fetchall()
        
        stats = {
            'overview': {
                'polling_places': polling_places_count,
                'precincts': precincts_count,
                'assignments': assignments_count
            },
            'by_state': [
                {'state': row[0], 'count': row[1]} 
                for row in polling_places_by_state
            ],
            'by_plugin': [
                {'plugin': row[0], 'count': row[1]} 
                for row in polling_places_by_plugin
            ],
            'performance': {
                'cache_hit': False,
                'query_time': 0
            }
        }
        
        return jsonify(stats)
        
    except Exception as e:
        logger.error(f"Error in get_admin_stats: {str(e)}")
        return jsonify({'error': 'Failed to fetch admin statistics'}), 500


@admin_performance_bp.route('/performance/metrics', methods=['GET'])
def get_performance_metrics():
    """Get performance metrics for monitoring"""
    try:
        # Get basic performance metrics
        metrics = {
            'cache_stats': {
                'admin_cache_size': len(admin_cache),
                'lazy_load_cache_size': len(lazy_load_manager.cache)
            },
            'database_stats': {
                'connection_pool_size': 0,  # Would need to be implemented
                'active_connections': 0
            },
            'request_stats': {
                'endpoint': request.endpoint,
                'method': request.method,
                'args': dict(request.args)
            }
        }
        
        return jsonify(metrics)
        
    except Exception as e:
        logger.error(f"Error in get_performance_metrics: {str(e)}")
        return jsonify({'error': 'Failed to fetch performance metrics'}), 500


@admin_performance_bp.route('/cache/clear', methods=['POST'])
def clear_cache():
    """Clear admin performance cache"""
    try:
        # Clear caches
        lazy_load_manager.cache.clear()
        admin_cache.clear()
        
        return jsonify({
            'message': 'Cache cleared successfully',
            'timestamp': current_app.config.get('CACHE_CLEARED', 'unknown')
        })
        
    except Exception as e:
        logger.error(f"Error clearing cache: {str(e)}")
        return jsonify({'error': 'Failed to clear cache'}), 500


@admin_performance_bp.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint for admin performance"""
    try:
        # Simple database health check
        db.session.execute(text("SELECT 1"))
        
        return jsonify({
            'status': 'healthy',
            'timestamp': current_app.config.get('HEALTH_CHECK_TIMESTAMP', 'unknown'),
            'version': '1.0.0'
        })
        
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return jsonify({
            'status': 'unhealthy',
            'error': str(e)
        }), 500