"""
Database query optimization utilities for large datasets

Provides optimized query methods, pagination, and performance monitoring
for handling large datasets efficiently.
"""

import time
import logging
from typing import Dict, List, Optional, Tuple, Any
from sqlalchemy import text, func, and_, or_
from sqlalchemy.orm import joinedload, selectinload
from flask import current_app

from database import db
from models import PollingPlace, Precinct, PrecinctAssignment, Election, APIKey, AuditTrail

logger = logging.getLogger(__name__)

class QueryOptimizer:
    """
    Database query optimization utilities
    """
    
    @staticmethod
    def get_polling_places_optimized(
        state: Optional[str] = None,
        county: Optional[str] = None,
        source_plugin: Optional[str] = None,
        location_type: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
        include_coordinates: bool = True
    ) -> Tuple[List[PollingPlace], int]:
        """
        Get polling places with optimized queries and pagination
        """
        start_time = time.time()
        
        # Build base query with only necessary columns
        query = PollingPlace.query
        
        # Apply filters efficiently
        if state:
            query = query.filter(PollingPlace.state == state.upper())
        
        if county:
            query = query.filter(PollingPlace.county == county)
        
        if source_plugin:
            query = query.filter(PollingPlace.source_plugin == source_plugin)
        
        if location_type:
            query = query.filter(PollingPlace.location_type == location_type)
        
        if include_coordinates:
            # Only include records with coordinates when requested
            query = query.filter(
                and_(
                    PollingPlace.latitude.isnot(None),
                    PollingPlace.longitude.isnot(None)
                )
            )
        
        # Get total count efficiently
        count_query = query.statement.with_only_columns([func.count()])
        total_count = db.session.execute(count_query).scalar()
        
        # Apply pagination with ordering for consistent results
        results = query.order_by(PollingPlace.state, PollingPlace.county, PollingPlace.name)\
                       .offset(offset)\
                       .limit(limit)\
                       .all()
        
        query_time = time.time() - start_time
        logger.info(f"Optimized polling places query: {len(results)} results in {query_time:.3f}s")
        
        return results, total_count
    
    @staticmethod
    def get_precincts_optimized(
        state: Optional[str] = None,
        county: Optional[str] = None,
        source_plugin: Optional[str] = None,
        changed_recently: Optional[bool] = None,
        has_polling_place: Optional[bool] = None,
        limit: int = 100,
        offset: int = 0
    ) -> Tuple[List[Precinct], int]:
        """
        Get precincts with optimized queries and pagination
        """
        start_time = time.time()
        
        # Build base query
        query = Precinct.query
        
        # Apply filters
        if state:
            query = query.filter(Precinct.state == state.upper())
        
        if county:
            query = query.filter(Precinct.county == county)
        
        if source_plugin:
            query = query.filter(Precinct.source_plugin == source_plugin)
        
        if changed_recently is not None:
            query = query.filter(Precinct.changed_recently == changed_recently)
        
        if has_polling_place is not None:
            if has_polling_place:
                query = query.filter(Precinct.current_polling_place_id.isnot(None))
            else:
                query = query.filter(Precinct.current_polling_place_id.is_(None))
        
        # Get total count
        count_query = query.statement.with_only_columns([func.count()])
        total_count = db.session.execute(count_query).scalar()
        
        # Apply pagination
        results = query.order_by(Precinct.state, Precinct.county, Precinct.name)\
                       .offset(offset)\
                       .limit(limit)\
                       .all()
        
        query_time = time.time() - start_time
        logger.info(f"Optimized precincts query: {len(results)} results in {query_time:.3f}s")
        
        return results, total_count
    
    @staticmethod
    def get_elections_with_stats(
        state: Optional[str] = None,
        year: Optional[int] = None,
        limit: int = 50,
        offset: int = 0
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        Get elections with aggregated statistics using optimized SQL
        """
        start_time = time.time()
        
        # Build the main query with statistics
        query = db.session.query(
            Election.id,
            Election.date,
            Election.name,
            Election.state,
            func.count(PrecinctAssignment.id).label('assignment_count'),
            func.count(func.distinct(PrecinctAssignment.precinct_id)).label('precinct_count')
        ).outerjoin(
            PrecinctAssignment,
            Election.id == PrecinctAssignment.election_id
        )
        
        # Apply filters
        if state:
            query = query.filter(Election.state == state.upper())
        
        if year:
            query = query.filter(func.extract('year', Election.date) == year)
        
        # Group by election fields
        query = query.group_by(
            Election.id, Election.date, Election.name, Election.state
        )
        
        # Get total count
        count_query = query.statement.with_only_columns([func.count()])
        total_count = db.session.execute(count_query).scalar()
        
        # Apply pagination and ordering
        results = query.order_by(Election.date.desc())\
                       .offset(offset)\
                       .limit(limit)\
                       .all()
        
        # Convert to dictionaries
        elections_data = []
        for row in results:
            elections_data.append({
                'id': row.id,
                'date': row.date.isoformat() if row.date else None,
                'name': row.name,
                'state': row.state,
                'assignment_count': row.assignment_count or 0,
                'precinct_count': row.precinct_count or 0
            })
        
        query_time = time.time() - start_time
        logger.info(f"Optimized elections query: {len(elections_data)} results in {query_time:.3f}s")
        
        return elections_data, total_count
    
    @staticmethod
    def get_precinct_assignments_optimized(
        election_id: Optional[int] = None,
        precinct_id: Optional[str] = None,
        polling_place_id: Optional[str] = None,
        is_current: Optional[bool] = None,
        limit: int = 100,
        offset: int = 0
    ) -> Tuple[List[PrecinctAssignment], int]:
        """
        Get precinct assignments with optimized queries
        """
        start_time = time.time()
        
        # Build base query with joins
        query = PrecinctAssignment.query
        
        # Apply filters
        if election_id:
            query = query.filter(PrecinctAssignment.election_id == election_id)
        
        if precinct_id:
            query = query.filter(PrecinctAssignment.precinct_id == precinct_id)
        
        if polling_place_id:
            query = query.filter(PrecinctAssignment.polling_place_id == polling_place_id)
        
        if is_current is not None:
            if is_current:
                query = query.filter(PrecinctAssignment.removed_date.is_(None))
            else:
                query = query.filter(PrecinctAssignment.removed_date.isnot(None))
        
        # Get total count
        count_query = query.statement.with_only_columns([func.count()])
        total_count = db.session.execute(count_query).scalar()
        
        # Apply pagination with eager loading
        results = query.options(
            joinedload(PrecinctAssignment.precinct),
            joinedload(PrecinctAssignment.polling_place),
            joinedload(PrecinctAssignment.election)
        ).order_by(
            PrecinctAssignment.assigned_date.desc()
        ).offset(offset).limit(limit).all()
        
        query_time = time.time() - start_time
        logger.info(f"Optimized assignments query: {len(results)} results in {query_time:.3f}s")
        
        return results, total_count
    
    @staticmethod
    def bulk_update_polling_places_coordinates(updates: List[Dict[str, Any]]) -> int:
        """
        Bulk update polling place coordinates efficiently
        """
        if not updates:
            return 0
        
        start_time = time.time()
        
        try:
            # Use bulk_update_mappings for efficient bulk updates
            db.session.bulk_update_mappings(
                PollingPlace,
                updates
            )
            db.session.commit()
            
            update_time = time.time() - start_time
            logger.info(f"Bulk updated {len(updates)} polling place coordinates in {update_time:.3f}s")
            
            return len(updates)
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Bulk update failed: {e}")
            return 0
    
    @staticmethod
    def get_database_stats() -> Dict[str, Any]:
        """
        Get comprehensive database statistics for monitoring
        """
        try:
            stats = {}
            
            # Table counts
            stats['polling_places'] = db.session.query(func.count(PollingPlace.id)).scalar()
            stats['precincts'] = db.session.query(func.count(Precinct.id)).scalar()
            stats['elections'] = db.session.query(func.count(Election.id)).scalar()
            stats['assignments'] = db.session.query(func.count(PrecinctAssignment.id)).scalar()
            stats['api_keys'] = db.session.query(func.count(APIKey.id)).scalar()
            stats['audit_trail'] = db.session.query(func.count(AuditTrail.id)).scalar()
            
            # State distribution
            state_stats = db.session.query(
                PollingPlace.state,
                func.count(PollingPlace.id).label('count')
            ).filter(
                PollingPlace.state.isnot(None)
            ).group_by(PollingPlace.state).order_by(func.count(PollingPlace.id).desc()).all()
            
            stats['state_distribution'] = [
                {'state': state, 'count': count} for state, count in state_stats
            ]
            
            # Source plugin distribution
            plugin_stats = db.session.query(
                PollingPlace.source_plugin,
                func.count(PollingPlace.id).label('count')
            ).filter(
                PollingPlace.source_plugin.isnot(None)
            ).group_by(PollingPlace.source_plugin).order_by(func.count(PollingPlace.id).desc()).all()
            
            stats['plugin_distribution'] = [
                {'plugin': plugin, 'count': count} for plugin, count in plugin_stats
            ]
            
            # Coordinates coverage
            with_coords = db.session.query(func.count(PollingPlace.id)).filter(
                and_(
                    PollingPlace.latitude.isnot(None),
                    PollingPlace.longitude.isnot(None)
                )
            ).scalar()
            
            stats['coordinate_coverage'] = {
                'with_coordinates': with_coords,
                'without_coordinates': stats['polling_places'] - with_coords,
                'percentage': round((with_coords / stats['polling_places'] * 100) if stats['polling_places'] > 0 else 0, 2)
            }
            
            return stats
            
        except Exception as e:
            logger.error(f"Failed to get database stats: {e}")
            return {'error': str(e)}
    
    @staticmethod
    def optimize_database():
        """
        Run database optimization commands
        """
        try:
            db_type = None
            if hasattr(db.engine.dialect, 'name'):
                db_type = db.engine.dialect.name
            
            optimizations = []
            
            if db_type == 'postgresql':
                # PostgreSQL optimizations
                commands = [
                    "ANALYZE;",  # Update statistics
                    "VACUUM ANALYZE;",  # Clean up and update stats
                    "REINDEX DATABASE pollingplaces;",  # Rebuild indexes
                ]
                
                for command in commands:
                    try:
                        db.session.execute(text(command))
                        optimizations.append(command)
                        logger.info(f"Executed optimization: {command}")
                    except Exception as e:
                        logger.warning(f"Optimization failed: {command}, Error: {e}")
                
                db.session.commit()
                
            elif db_type == 'sqlite':
                # SQLite optimizations
                try:
                    db.session.execute(text("VACUUM;"))
                    db.session.execute(text("ANALYZE;"))
                    optimizations.extend(["VACUUM;", "ANALYZE;"])
                    db.session.commit()
                    logger.info("Executed SQLite optimizations")
                except Exception as e:
                    logger.warning(f"SQLite optimization failed: {e}")
            
            return {
                'success': True,
                'optimizations': optimizations,
                'database_type': db_type
            }
            
        except Exception as e:
            logger.error(f"Database optimization failed: {e}")
            return {
                'success': False,
                'error': str(e)
            }

class QueryPerformanceMonitor:
    """
    Monitor and log query performance
    """
    
    def __init__(self):
        self.slow_query_threshold = 1.0  # seconds
    
    def log_slow_queries(self):
        """
        Log slow queries from the current session
        """
        if not current_app.config.get('SQLALCHEMY_RECORD_QUERIES', False):
            return
        
        # This would need to be implemented with SQLAlchemy's query logging
        # For now, we'll just log that monitoring is enabled
        logger.info("Query performance monitoring is enabled")
    
    def get_query_stats(self) -> Dict[str, Any]:
        """
        Get query performance statistics
        """
        # This would typically integrate with SQLAlchemy's query logging
        # For now, return basic info
        return {
            'monitoring_enabled': current_app.config.get('SQLALCHEMY_RECORD_QUERIES', False),
            'slow_query_threshold': self.slow_query_threshold
        }

# Global instances
query_optimizer = QueryOptimizer()
performance_monitor = QueryPerformanceMonitor()