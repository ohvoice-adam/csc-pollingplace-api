"""
Shared database instance to avoid multiple SQLAlchemy instances
Includes connection pooling configuration for performance optimization
"""

import os
from flask_sqlalchemy import SQLAlchemy

# Create SQLAlchemy instance with optimized configuration
db = SQLAlchemy()

def configure_database(app):
    """
    Configure database with connection pooling and performance optimizations
    """
    # Get database type from environment
    db_type = os.getenv('DB_TYPE', 'sqlite').lower()
    
    if db_type in ['postgresql', 'postgres']:
        # PostgreSQL connection pooling configuration
        pool_size = int(os.getenv('DB_POOL_SIZE', '10'))
        max_overflow = int(os.getenv('DB_MAX_OVERFLOW', '20'))
        pool_timeout = int(os.getenv('DB_POOL_TIMEOUT', '30'))
        pool_recycle = int(os.getenv('DB_POOL_RECYCLE', '3600'))
        
        # Configure SQLAlchemy engine options for PostgreSQL
        app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
            'pool_size': pool_size,
            'max_overflow': max_overflow,
            'pool_timeout': pool_timeout,
            'pool_recycle': pool_recycle,
            'pool_pre_ping': True,  # Validate connections before use
            'pool_reset_on_return': 'commit',  # Reset connection state
            'echo': os.getenv('DB_ECHO', 'False').lower() == 'true',  # SQL logging
        }
        
        # Additional PostgreSQL-specific optimizations
        app.config['SQLALCHEMY_RECORD_QUERIES'] = True
        app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
        
    elif db_type == 'mysql':
        # MySQL connection pooling configuration
        pool_size = int(os.getenv('DB_POOL_SIZE', '5'))
        max_overflow = int(os.getenv('DB_MAX_OVERFLOW', '10'))
        pool_timeout = int(os.getenv('DB_POOL_TIMEOUT', '30'))
        pool_recycle = int(os.getenv('DB_POOL_RECYCLE', '3600'))
        
        # Configure SQLAlchemy engine options for MySQL
        app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
            'pool_size': pool_size,
            'max_overflow': max_overflow,
            'pool_timeout': pool_timeout,
            'pool_recycle': pool_recycle,
            'pool_pre_ping': True,
            'pool_reset_on_return': 'commit',
            'echo': os.getenv('DB_ECHO', 'False').lower() == 'true',
            # MySQL-specific options
            'mysql_charset': 'utf8mb4',
            'mysql_use_unicode': True,
        }
        
        app.config['SQLALCHEMY_RECORD_QUERIES'] = True
        app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
        
    else:
        # SQLite configuration (limited pooling support)
        app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
            'pool_pre_ping': True,
            'echo': os.getenv('DB_ECHO', 'False').lower() == 'true',
            # SQLite-specific options
            'connect_args': {
                'check_same_thread': False,
                'timeout': 20,  # Connection timeout in seconds
            }
        }
        
        # For SQLite, we don't want connection pooling in the traditional sense
        # but we can still enable query recording
        app.config['SQLALCHEMY_RECORD_QUERIES'] = os.getenv('DB_RECORD_QUERIES', 'False').lower() == 'true'
        app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    return app

def get_database_stats():
    """
    Get database connection pool statistics
    """
    try:
        engine = db.get_engine()
        
        if hasattr(engine.pool, 'status'):
            # PostgreSQL/MySQL pool stats
            pool_status = engine.pool.status()
            return {
                'pool_size': engine.pool.size(),
                'checked_in': pool_status.get('pool_checked_in', 0),
                'checked_out': pool_status.get('pool_checked_out', 0),
                'overflow': pool_status.get('pool_overflow', 0),
                'invalid': pool_status.get('pool_invalid', 0),
            }
        else:
            # SQLite or other database without pooling
            return {
                'pool_size': 1,
                'checked_in': 1,
                'checked_out': 0,
                'overflow': 0,
                'invalid': 0,
                'note': 'SQLite does not use connection pooling'
            }
    except Exception as e:
        return {
            'error': str(e),
            'note': 'Could not retrieve pool statistics'
        }

def health_check():
    """
    Perform database health check
    """
    try:
        # Test basic connectivity
        result = db.session.execute(db.text('SELECT 1')).scalar()
        if result != 1:
            return False, "Basic query failed"
        
        # Test connection pool
        stats = get_database_stats()
        if 'error' in stats:
            return False, f"Pool error: {stats['error']}"
        
        return True, "Database connection healthy"
    except Exception as e:
        return False, f"Database health check failed: {str(e)}"