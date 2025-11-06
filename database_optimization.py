"""
Database performance optimization module
Provides connection pooling, query optimization, and performance monitoring
"""

import time
import logging
from contextlib import contextmanager
from typing import Optional, Dict, Any, List
from flask import current_app
from sqlalchemy import text, event, Index
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.pool import QueuePool
from database import db

logger = logging.getLogger(__name__)

class DatabaseOptimizer:
    """Database performance optimization and monitoring"""
    
    def __init__(self):
        self.query_stats = {}
        self.slow_query_threshold = 1.0  # seconds
        
    def setup_connection_pooling(self, app):
        """Configure database connection pooling"""
        if app.config.get('DB_TYPE') == 'postgresql':
            # PostgreSQL connection pooling configuration
            app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
                'pool_size': 20,  # Number of connections to keep open
                'max_overflow': 30,  # Additional connections beyond pool_size
                'pool_timeout': 30,  # Timeout to get connection from pool
                'pool_recycle': 3600,  # Recycle connections every hour
                'pool_pre_ping': True,  # Validate connections before use
                'poolclass': QueuePool,
            }
        elif app.config.get('DB_TYPE') == 'sqlite':
            # SQLite optimization
            app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
                'pool_size': 1,
                'max_overflow': 0,
                'pool_pre_ping': True,
                'connect_args': {
                    'timeout': 20,
                    'check_same_thread': False,
                }
            }
    
    def setup_query_listeners(self):
        """Setup query performance monitoring listeners"""
        @event.listens_for(Engine, "before_cursor_execute")
        def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
            context._query_start_time = time.time()
            
        @event.listens_for(Engine, "after_cursor_execute")
        def after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
            total = time.time() - context._query_start_time
            
            # Log slow queries
            if total > self.slow_query_threshold:
                logger.warning(
                    f"Slow query ({total:.2f}s): {statement[:100]}..."
                    f" Parameters: {parameters}"
                )
            
            # Track query statistics
            query_type = statement.strip().split()[0].upper()
            if query_type not in self.query_stats:
                self.query_stats[query_type] = {
                    'count': 0,
                    'total_time': 0,
                    'avg_time': 0,
                    'max_time': 0
                }
            
            stats = self.query_stats[query_type]
            stats['count'] += 1
            stats['total_time'] += total
            stats['avg_time'] = stats['total_time'] / stats['count']
            stats['max_time'] = max(stats['max_time'], total)
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """Get database performance statistics"""
        return {
            'query_stats': self.query_stats,
            'slow_query_threshold': self.slow_query_threshold
        }
    
    def reset_stats(self):
        """Reset performance statistics"""
        self.query_stats = {}

class DatabaseIndexer:
    """Manages database indexes for optimal query performance"""
    
    @staticmethod
    def create_indexes():
        """Create optimized indexes for frequently queried columns"""
        indexes = [
            # PollingPlace indexes
            Index('idx_polling_places_state', 'polling_places.state'),
            Index('idx_polling_places_county', 'polling_places.county'),
            Index('idx_polling_places_source_plugin', 'polling_places.source_plugin'),
            Index('idx_polling_places_location_type', 'polling_places.location_type'),
            Index('idx_polling_places_coordinates', 'polling_places.latitude', 'polling_places.longitude'),
            Index('idx_polling_places_created_at', 'polling_places.created_at'),
            Index('idx_polling_places_state_county', 'polling_places.state', 'polling_places.county'),
            
            # Precinct indexes
            Index('idx_precincts_state', 'precincts.state'),
            Index('idx_precincts_county', 'precincts.county'),
            Index('idx_precincts_source_plugin', 'precincts.source_plugin'),
            Index('idx_precincts_current_polling_place', 'precincts.current_polling_place_id'),
            Index('idx_precincts_changed_recently', 'precincts.changed_recently'),
            Index('idx_precincts_state_county', 'precincts.state', 'precincts.county'),
            
            # PrecinctAssignment indexes
            Index('idx_precinct_assignments_precinct', 'precinct_assignments.precinct_id'),
            Index('idx_precinct_assignments_polling_place', 'precinct_assignments.polling_place_id'),
            Index('idx_precinct_assignments_election', 'precinct_assignments.election_id'),
            Index('idx_precinct_assignments_assigned_date', 'precinct_assignments.assigned_date'),
            Index('idx_precinct_assignments_current', 'precinct_assignments.removed_date'),  # NULL = current
            
            # Election indexes
            Index('idx_elections_date', 'elections.date'),
            Index('idx_elections_state', 'elections.state'),
            Index('idx_elections_date_state', 'elections.date', 'elections.state'),
            
            # APIKey indexes
            Index('idx_api_keys_active', 'api_keys.is_active'),
            Index('idx_api_keys_last_used', 'api_keys.last_used_at'),
            
            # AuditTrail indexes
            Index('idx_audit_trail_table_record', 'audit_trail.table_name', 'audit_trail.record_id'),
            Index('idx_audit_trail_timestamp', 'audit_trail.timestamp'),
            Index('idx_audit_trail_user', 'audit_trail.user_id'),
        ]
        
        for index in indexes:
            try:
                index.create(db.engine)
                logger.info(f"Created index: {index.name}")
            except Exception as e:
                logger.warning(f"Index {index.name} already exists or failed to create: {e}")
    
    @staticmethod
    def analyze_query_performance():
        """Analyze and suggest index optimizations"""
        suggestions = []
        
        # Check for missing indexes on frequently queried columns
        if db.engine.dialect.name == 'postgresql':
            # PostgreSQL-specific analysis
            with db.engine.connect() as conn:
                # Get most frequent queries from pg_stat_statements
                try:
                    result = conn.execute(text("""
                        SELECT query, calls, total_time, mean_time 
                        FROM pg_stat_statements 
                        WHERE calls > 10 
                        ORDER BY total_time DESC 
                        LIMIT 10
                    """))
                    
                    for row in result:
                        if 'WHERE' in row[0] and 'state' in row[0]:
                            suggestions.append(
                                f"High-traffic query on 'state' column: {row[0][:100]}..."
                            )
                except Exception:
                    pass  # pg_stat_statements might not be available
        
        return suggestions

class QueryOptimizer:
    """Optimizes database queries for large datasets"""
    
    @staticmethod
    def get_polling_places_optimized(state: str = None, county: str = None, 
                                  source_plugin: str = None, limit: int = None,
                                  offset: int = None) -> List:
        """Optimized query for polling places with pagination"""
        query = PollingPlace.query
        
        # Apply filters efficiently
        if state:
            query = query.filter(PollingPlace.state == state)
        if county:
            query = query.filter(PollingPlace.county == county)
        if source_plugin:
            query = query.filter(PollingPlace.source_plugin == source_plugin)
        
        # Use pagination for large datasets
        if limit:
            query = query.limit(limit)
        if offset:
            query = query.offset(offset)
        
        # Use options for eager loading to avoid N+1 queries
        return query.options(
            db.joinedload(PollingPlace.precincts)
        ).all()
    
    @staticmethod
    def get_precincts_optimized(state: str = None, county: str = None,
                             changed_recently: bool = None, source_plugin: str = None,
                             limit: int = None, offset: int = None) -> List:
        """Optimized query for precincts with pagination"""
        query = Precinct.query
        
        # Apply filters efficiently
        if state:
            query = query.filter(Precinct.state == state)
        if county:
            query = query.filter(Precinct.county == county)
        if changed_recently is not None:
            query = query.filter(Precinct.changed_recently == changed_recently)
        if source_plugin:
            query = query.filter(Precinct.source_plugin == source_plugin)
        
        # Use pagination for large datasets
        if limit:
            query = query.limit(limit)
        if offset:
            query = query.offset(offset)
        
        # Use options for eager loading
        return query.options(
            db.joinedload(Precinct.current_polling_place),
            db.joinedload(Precinct.polling_places)
        ).all()
    
    @staticmethod
    def get_elections_optimized(state: str = None, year: int = None,
                             limit: int = None, offset: int = None) -> List:
        """Optimized query for elections with pagination"""
        query = Election.query
        
        # Apply filters efficiently
        if state:
            query = query.filter(Election.state == state)
        if year:
            query = query.filter(db.extract('year', Election.date) == year)
        
        # Use pagination for large datasets
        if limit:
            query = query.limit(limit)
        if offset:
            query = query.offset(offset)
        
        return query.order_by(Election.date.desc()).all()
    
    @staticmethod
    def bulk_insert_polling_places(polling_places_data: List[Dict[str, Any]]):
        """Bulk insert polling places for better performance"""
        try:
            # Use bulk_insert_mappings for better performance
            db.session.bulk_insert_mappings(PollingPlace, polling_places_data)
            db.session.commit()
            logger.info(f"Bulk inserted {len(polling_places_data)} polling places")
        except Exception as e:
            db.session.rollback()
            logger.error(f"Bulk insert failed: {e}")
            raise
    
    @staticmethod
    def bulk_update_precincts(precincts_data: List[Dict[str, Any]]):
        """Bulk update precincts for better performance"""
        try:
            # Use bulk_update_mappings for better performance
            db.session.bulk_update_mappings(Precinct, precincts_data)
            db.session.commit()
            logger.info(f"Bulk updated {len(precincts_data)} precincts")
        except Exception as e:
            db.session.rollback()
            logger.error(f"Bulk update failed: {e}")
            raise

@contextmanager
def database_transaction():
    """Context manager for database transactions with proper error handling"""
    try:
        yield db.session
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        logger.error(f"Database transaction failed: {e}")
        raise
    finally:
        db.session.close()

# Global instances
db_optimizer = DatabaseOptimizer()
db_indexer = DatabaseIndexer()
query_optimizer = QueryOptimizer()

def init_database_optimization(app):
    """Initialize all database optimizations"""
    # Setup connection pooling
    db_optimizer.setup_connection_pooling(app)
    
    # Setup query monitoring
    db_optimizer.setup_query_listeners()
    
    # Create indexes
    with app.app_context():
        db_indexer.create_indexes()
    
    logger.info("Database optimization initialized")

# Import models for index creation
from models import PollingPlace, Precinct, Election