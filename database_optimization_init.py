"""
Database optimization initialization

This module initializes all database performance optimizations including:
- Connection pooling
- Indexes
- Query optimization
- Migration system
"""

import logging
from datetime import datetime
from flask import current_app, jsonify

from database import db, health_check, get_database_stats
from query_optimization import query_optimizer, performance_monitor
from migrations import init_migrations, run_migrations, get_migration_status

logger = logging.getLogger(__name__)

def init_database_optimization(app):
    """
    Initialize all database optimizations
    
    Args:
        app: Flask application instance
    """
    logger.info("Initializing database optimizations...")
    
    try:
        # Initialize migration system
        with app.app_context():
            init_migrations()
            
            # Run pending migrations
            migration_result = run_migrations()
            if migration_result:
                logger.info(f"Database migrations completed: {migration_result}")
            else:
                logger.warning("Database migrations failed")
        
        # Log database health status
        with app.app_context():
            is_healthy, health_message = health_check()
            if is_healthy:
                logger.info(f"Database health check passed: {health_message}")
            else:
                logger.error(f"Database health check failed: {health_message}")
        
        # Log database statistics
        with app.app_context():
            stats = get_database_stats()
            if 'error' not in stats:
                logger.info(f"Database stats: {stats['polling_places']} polling places, "
                           f"{stats['precincts']} precincts, {stats['elections']} elections")
            else:
                logger.warning(f"Could not get database stats: {stats['error']}")
        
        # Initialize query performance monitoring
        if app.config.get('SQLALCHEMY_RECORD_QUERIES', False):
            performance_monitor.log_slow_queries()
            logger.info("Query performance monitoring enabled")
        
        logger.info("Database optimizations initialized successfully")
        
    except Exception as e:
        logger.error(f"Failed to initialize database optimizations: {e}")
        raise

def get_optimization_status():
    """
    Get comprehensive optimization status
    
    Returns:
        dict: Optimization status information
    """
    try:
        status = {
            'database_health': False,
            'connection_pool': {},
            'migrations': {},
            'query_monitoring': False,
            'indexes_applied': False
        }
        
        # Database health
        is_healthy, health_message = health_check()
        status['database_health'] = is_healthy
        status['health_message'] = health_message
        
        # Connection pool stats
        pool_stats = get_database_stats()
        status['connection_pool'] = pool_stats
        
        # Migration status
        migration_status = get_migration_status()
        status['migrations'] = migration_status
        
        # Query monitoring
        status['query_monitoring'] = current_app.config.get('SQLALCHEMY_RECORD_QUERIES', False)
        
        # Check if indexes are applied (basic check)
        try:
            # This is a simplified check - in production you'd want more sophisticated checking
            if migration_status.get('applied_migrations', 0) > 0:
                status['indexes_applied'] = True
        except:
            status['indexes_applied'] = False
        
        return status
        
    except Exception as e:
        logger.error(f"Failed to get optimization status: {e}")
        return {
            'error': str(e),
            'database_health': False,
            'connection_pool': {},
            'migrations': {},
            'query_monitoring': False,
            'indexes_applied': False
        }

def run_database_optimization():
    """
    Run database optimization routines
    
    Returns:
        dict: Optimization results
    """
    try:
        results = {
            'success': True,
            'optimizations_run': [],
            'errors': []
        }
        
        # Run query optimizer
        try:
            optimization_result = query_optimizer.optimize_database()
            if optimization_result.get('success', False):
                results['optimizations_run'].extend(
                    optimization_result.get('optimizations', [])
                )
                logger.info("Database optimization completed successfully")
            else:
                results['errors'].append(
                    optimization_result.get('error', 'Unknown optimization error')
                )
        except Exception as e:
            results['errors'].append(f"Optimization failed: {str(e)}")
        
        # Update statistics
        try:
            db_type = None
            if hasattr(db.engine.dialect, 'name'):
                db_type = db.engine.dialect.name
            
            if db_type == 'postgresql':
                db.session.execute(db.text("ANALYZE;"))
                db.session.commit()
                results['optimizations_run'].append("Updated PostgreSQL statistics")
            elif db_type == 'sqlite':
                db.session.execute(db.text("ANALYZE;"))
                db.session.commit()
                results['optimizations_run'].append("Updated SQLite statistics")
                
        except Exception as e:
            results['errors'].append(f"Statistics update failed: {str(e)}")
        
        results['success'] = len(results['errors']) == 0
        
        return results
        
    except Exception as e:
        logger.error(f"Database optimization failed: {e}")
        return {
            'success': False,
            'optimizations_run': [],
            'errors': [str(e)]
        }

def create_performance_monitoring_endpoint(app):
    """
    Create endpoint for monitoring database performance
    
    Args:
        app: Flask application instance
    """
    @app.route('/admin/api/database-performance')
    def admin_api_database_performance():
        """API endpoint for database performance metrics"""
        try:
            # Get optimization status
            status = get_optimization_status()
            
            # Get database statistics
            db_stats = query_optimizer.get_database_stats()
            
            # Get query performance stats
            query_stats = performance_monitor.get_query_stats()
            
            return jsonify({
                'optimization_status': status,
                'database_stats': db_stats,
                'query_performance': query_stats,
                'timestamp': datetime.utcnow().isoformat()
            })
            
        except Exception as e:
            return jsonify({
                'error': str(e),
                'timestamp': datetime.utcnow().isoformat()
            }), 500
    
    @app.route('/admin/api/database-optimize', methods=['POST'])
    def admin_api_database_optimize():
        """API endpoint to run database optimization"""
        try:
            results = run_database_optimization()
            
            if results['success']:
                return jsonify({
                    'success': True,
                    'message': 'Database optimization completed successfully',
                    'optimizations_run': results['optimizations_run'],
                    'timestamp': datetime.utcnow().isoformat()
                })
            else:
                return jsonify({
                    'success': False,
                    'message': 'Database optimization failed',
                    'errors': results['errors'],
                    'timestamp': datetime.utcnow().isoformat()
                }), 500
                
        except Exception as e:
            return jsonify({
                'success': False,
                'message': 'Database optimization failed',
                'error': str(e),
                'timestamp': datetime.utcnow().isoformat()
            }), 500

# Export main functions
__all__ = [
    'init_database_optimization',
    'get_optimization_status', 
    'run_database_optimization',
    'create_performance_monitoring_endpoint'
]