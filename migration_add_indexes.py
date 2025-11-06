"""
Add database indexes for performance optimization

This migration adds indexes to frequently queried columns:
- state indexes on PollingPlace and Precinct tables
- county indexes on PollingPlace and Precinct tables  
- source_plugin indexes on PollingPlace and Precinct tables
- Composite indexes for common query patterns
"""

from datetime import datetime
import logging

def run_migration(db):
    """
    Add performance indexes to the database
    """
    logger = logging.getLogger(__name__)
    
    try:
        # Get database type
        db_type = None
        if hasattr(db.engine.dialect, 'name'):
            db_type = db.engine.dialect.name
        
        logger.info(f"Running database optimization migration for {db_type}")
        
        # Index definitions for different database types
        if db_type == 'postgresql':
            # PostgreSQL-specific indexes
            indexes = [
                # PollingPlace table indexes
                "CREATE INDEX IF NOT EXISTS idx_polling_places_state ON polling_places (state);",
                "CREATE INDEX IF NOT EXISTS idx_polling_places_county ON polling_places (county);",
                "CREATE INDEX IF NOT EXISTS idx_polling_places_source_plugin ON polling_places (source_plugin);",
                "CREATE INDEX IF NOT EXISTS idx_polling_places_state_source ON polling_places (state, source_plugin);",
                "CREATE INDEX IF NOT EXISTS idx_polling_places_location ON polling_places (latitude, longitude);",
                "CREATE INDEX IF NOT EXISTS idx_polling_places_created_at ON polling_places (created_at);",
                "CREATE INDEX IF NOT EXISTS idx_polling_places_updated_at ON polling_places (updated_at);",
                
                # Precinct table indexes
                "CREATE INDEX IF NOT EXISTS idx_precincts_state ON precincts (state);",
                "CREATE INDEX IF NOT EXISTS idx_precincts_county ON precincts (county);",
                "CREATE INDEX IF NOT EXISTS idx_precincts_source_plugin ON precincts (source_plugin);",
                "CREATE INDEX IF NOT EXISTS idx_precincts_state_source ON precincts (state, source_plugin);",
                "CREATE INDEX IF NOT EXISTS idx_precincts_current_polling_place ON precincts (current_polling_place_id);",
                "CREATE INDEX IF NOT EXISTS idx_precincts_changed_recently ON precincts (changed_recently);",
                "CREATE INDEX IF NOT EXISTS idx_precincts_created_at ON precincts (created_at);",
                "CREATE INDEX IF NOT EXISTS idx_precincts_updated_at ON precincts (updated_at);",
                
                # Election table indexes
                "CREATE INDEX IF NOT EXISTS idx_elections_state ON elections (state);",
                "CREATE INDEX IF NOT EXISTS idx_elections_date ON elections (date);",
                "CREATE INDEX IF NOT EXISTS idx_elections_state_date ON elections (state, date);",
                
                # PrecinctAssignment table indexes
                "CREATE INDEX IF NOT EXISTS idx_precinct_assignments_precinct_id ON precinct_assignments (precinct_id);",
                "CREATE INDEX IF NOT EXISTS idx_precinct_assignments_polling_place_id ON precinct_assignments (polling_place_id);",
                "CREATE INDEX IF NOT EXISTS idx_precinct_assignments_election_id ON precinct_assignments (election_id);",
                "CREATE INDEX IF NOT EXISTS idx_precinct_assignments_assigned_date ON precinct_assignments (assigned_date);",
                "CREATE INDEX IF NOT EXISTS idx_precinct_assignments_precinct_election ON precinct_assignments (precinct_id, election_id);",
                
                # APIKey table indexes
                "CREATE INDEX IF NOT EXISTS idx_api_keys_is_active ON api_keys (is_active);",
                "CREATE INDEX IF NOT EXISTS idx_api_keys_last_used_at ON api_keys (last_used_at);",
                
                # AuditTrail table indexes
                "CREATE INDEX IF NOT EXISTS idx_audit_trail_table_name ON audit_trail (table_name);",
                "CREATE INDEX IF NOT EXISTS idx_audit_trail_record_id ON audit_trail (record_id);",
                "CREATE INDEX IF NOT EXISTS idx_audit_trail_timestamp ON audit_trail (timestamp);",
                "CREATE INDEX IF NOT EXISTS idx_audit_trail_table_timestamp ON audit_trail (table_name, timestamp);",
            ]
        elif db_type == 'sqlite':
            # SQLite-specific indexes (no IF NOT EXISTS support for some versions)
            indexes = [
                # PollingPlace table indexes
                "CREATE INDEX IF NOT EXISTS idx_polling_places_state ON polling_places (state);",
                "CREATE INDEX IF NOT EXISTS idx_polling_places_county ON polling_places (county);",
                "CREATE INDEX IF NOT EXISTS idx_polling_places_source_plugin ON polling_places (source_plugin);",
                "CREATE INDEX IF NOT EXISTS idx_polling_places_state_source ON polling_places (state, source_plugin);",
                "CREATE INDEX IF NOT EXISTS idx_polling_places_location ON polling_places (latitude, longitude);",
                "CREATE INDEX IF NOT EXISTS idx_polling_places_created_at ON polling_places (created_at);",
                "CREATE INDEX IF NOT EXISTS idx_polling_places_updated_at ON polling_places (updated_at);",
                
                # Precinct table indexes
                "CREATE INDEX IF NOT EXISTS idx_precincts_state ON precincts (state);",
                "CREATE INDEX IF NOT EXISTS idx_precincts_county ON precincts (county);",
                "CREATE INDEX IF NOT EXISTS idx_precincts_source_plugin ON precincts (source_plugin);",
                "CREATE INDEX IF NOT EXISTS idx_precincts_state_source ON precincts (state, source_plugin);",
                "CREATE INDEX IF NOT EXISTS idx_precincts_current_polling_place ON precincts (current_polling_place_id);",
                "CREATE INDEX IF NOT EXISTS idx_precincts_changed_recently ON precincts (changed_recently);",
                "CREATE INDEX IF NOT EXISTS idx_precincts_created_at ON precincts (created_at);",
                "CREATE INDEX IF NOT EXISTS idx_precincts_updated_at ON precincts (updated_at);",
                
                # Election table indexes
                "CREATE INDEX IF NOT EXISTS idx_elections_state ON elections (state);",
                "CREATE INDEX IF NOT EXISTS idx_elections_date ON elections (date);",
                "CREATE INDEX IF NOT EXISTS idx_elections_state_date ON elections (state, date);",
                
                # PrecinctAssignment table indexes
                "CREATE INDEX IF NOT EXISTS idx_precinct_assignments_precinct_id ON precinct_assignments (precinct_id);",
                "CREATE INDEX IF NOT EXISTS idx_precinct_assignments_polling_place_id ON precinct_assignments (polling_place_id);",
                "CREATE INDEX IF NOT EXISTS idx_precinct_assignments_election_id ON precinct_assignments (election_id);",
                "CREATE INDEX IF NOT EXISTS idx_precinct_assignments_assigned_date ON precinct_assignments (assigned_date);",
                "CREATE INDEX IF NOT EXISTS idx_precinct_assignments_precinct_election ON precinct_assignments (precinct_id, election_id);",
                
                # APIKey table indexes
                "CREATE INDEX IF NOT EXISTS idx_api_keys_is_active ON api_keys (is_active);",
                "CREATE INDEX IF NOT EXISTS idx_api_keys_last_used_at ON api_keys (last_used_at);",
                
                # AuditTrail table indexes
                "CREATE INDEX IF NOT EXISTS idx_audit_trail_table_name ON audit_trail (table_name);",
                "CREATE INDEX IF NOT EXISTS idx_audit_trail_record_id ON audit_trail (record_id);",
                "CREATE INDEX IF NOT EXISTS idx_audit_trail_timestamp ON audit_trail (timestamp);",
                "CREATE INDEX IF NOT EXISTS idx_audit_trail_table_timestamp ON audit_trail (table_name, timestamp);",
            ]
        else:
            # Generic SQL indexes
            indexes = [
                # PollingPlace table indexes
                "CREATE INDEX idx_polling_places_state ON polling_places (state);",
                "CREATE INDEX idx_polling_places_county ON polling_places (county);",
                "CREATE INDEX idx_polling_places_source_plugin ON polling_places (source_plugin);",
                "CREATE INDEX idx_polling_places_state_source ON polling_places (state, source_plugin);",
                "CREATE INDEX idx_polling_places_location ON polling_places (latitude, longitude);",
                "CREATE INDEX idx_polling_places_created_at ON polling_places (created_at);",
                "CREATE INDEX idx_polling_places_updated_at ON polling_places (updated_at);",
                
                # Precinct table indexes
                "CREATE INDEX idx_precincts_state ON precincts (state);",
                "CREATE INDEX idx_precincts_county ON precincts (county);",
                "CREATE INDEX idx_precincts_source_plugin ON precincts (source_plugin);",
                "CREATE INDEX idx_precincts_state_source ON precincts (state, source_plugin);",
                "CREATE INDEX idx_precincts_current_polling_place ON precincts (current_polling_place_id);",
                "CREATE INDEX idx_precincts_changed_recently ON precincts (changed_recently);",
                "CREATE INDEX idx_precincts_created_at ON precincts (created_at);",
                "CREATE INDEX idx_precincts_updated_at ON precincts (updated_at);",
                
                # Election table indexes
                "CREATE INDEX idx_elections_state ON elections (state);",
                "CREATE INDEX idx_elections_date ON elections (date);",
                "CREATE INDEX idx_elections_state_date ON elections (state, date);",
                
                # PrecinctAssignment table indexes
                "CREATE INDEX idx_precinct_assignments_precinct_id ON precinct_assignments (precinct_id);",
                "CREATE INDEX idx_precinct_assignments_polling_place_id ON precinct_assignments (polling_place_id);",
                "CREATE INDEX idx_precinct_assignments_election_id ON precinct_assignments (election_id);",
                "CREATE INDEX idx_precinct_assignments_assigned_date ON precinct_assignments (assigned_date);",
                "CREATE INDEX idx_precinct_assignments_precinct_election ON precinct_assignments (precinct_id, election_id);",
                
                # APIKey table indexes
                "CREATE INDEX idx_api_keys_is_active ON api_keys (is_active);",
                "CREATE INDEX idx_api_keys_last_used_at ON api_keys (last_used_at);",
                
                # AuditTrail table indexes
                "CREATE INDEX idx_audit_trail_table_name ON audit_trail (table_name);",
                "CREATE INDEX idx_audit_trail_record_id ON audit_trail (record_id);",
                "CREATE INDEX idx_audit_trail_timestamp ON audit_trail (timestamp);",
                "CREATE INDEX idx_audit_trail_table_timestamp ON audit_trail (table_name, timestamp);",
            ]
        
        # Execute index creation
        for index_sql in indexes:
            try:
                db.session.execute(db.text(index_sql))
                logger.info(f"Created index: {index_sql.split('idx_')[1].split(' ')[0] if 'idx_' in index_sql else 'custom index'}")
            except Exception as e:
                if "already exists" in str(e).lower() or "duplicate" in str(e).lower():
                    logger.info(f"Index already exists: {index_sql}")
                else:
                    logger.warning(f"Failed to create index: {index_sql}, Error: {e}")
        
        # Commit the changes
        db.session.commit()
        logger.info("Database indexes migration completed successfully")
        
        # Update statistics for PostgreSQL
        if db_type == 'postgresql':
            try:
                db.session.execute(db.text("ANALYZE;"))
                db.session.commit()
                logger.info("Updated PostgreSQL table statistics")
            except Exception as e:
                logger.warning(f"Failed to update PostgreSQL statistics: {e}")
        
        return True
        
    except Exception as e:
        logger.error(f"Database indexes migration failed: {e}")
        db.session.rollback()
        return False


def rollback_migration(db):
    """
    Rollback the database indexes (remove them)
    """
    logger = logging.getLogger(__name__)
    
    try:
        # Get database type
        db_type = None
        if hasattr(db.engine.dialect, 'name'):
            db_type = db.engine.dialect.name
        
        logger.info(f"Rolling back database indexes for {db_type}")
        
        # Index drop statements
        if db_type == 'postgresql':
            drop_statements = [
                "DROP INDEX IF EXISTS idx_polling_places_state;",
                "DROP INDEX IF EXISTS idx_polling_places_county;",
                "DROP INDEX IF EXISTS idx_polling_places_source_plugin;",
                "DROP INDEX IF EXISTS idx_polling_places_state_source;",
                "DROP INDEX IF EXISTS idx_polling_places_location;",
                "DROP INDEX IF EXISTS idx_polling_places_created_at;",
                "DROP INDEX IF EXISTS idx_polling_places_updated_at;",
                "DROP INDEX IF EXISTS idx_precincts_state;",
                "DROP INDEX IF EXISTS idx_precincts_county;",
                "DROP INDEX IF EXISTS idx_precincts_source_plugin;",
                "DROP INDEX IF EXISTS idx_precincts_state_source;",
                "DROP INDEX IF EXISTS idx_precincts_current_polling_place;",
                "DROP INDEX IF EXISTS idx_precincts_changed_recently;",
                "DROP INDEX IF EXISTS idx_precincts_created_at;",
                "DROP INDEX IF EXISTS idx_precincts_updated_at;",
                "DROP INDEX IF EXISTS idx_elections_state;",
                "DROP INDEX IF EXISTS idx_elections_date;",
                "DROP INDEX IF EXISTS idx_elections_state_date;",
                "DROP INDEX IF EXISTS idx_precinct_assignments_precinct_id;",
                "DROP INDEX IF EXISTS idx_precinct_assignments_polling_place_id;",
                "DROP INDEX IF EXISTS idx_precinct_assignments_election_id;",
                "DROP INDEX IF EXISTS idx_precinct_assignments_assigned_date;",
                "DROP INDEX IF EXISTS idx_precinct_assignments_precinct_election;",
                "DROP INDEX IF EXISTS idx_api_keys_is_active;",
                "DROP INDEX IF EXISTS idx_api_keys_last_used_at;",
                "DROP INDEX IF EXISTS idx_audit_trail_table_name;",
                "DROP INDEX IF EXISTS idx_audit_trail_record_id;",
                "DROP INDEX IF EXISTS idx_audit_trail_timestamp;",
                "DROP INDEX IF EXISTS idx_audit_trail_table_timestamp;",
            ]
        else:
            # SQLite and other databases
            drop_statements = [
                "DROP INDEX IF EXISTS idx_polling_places_state;",
                "DROP INDEX IF EXISTS idx_polling_places_county;",
                "DROP INDEX IF EXISTS idx_polling_places_source_plugin;",
                "DROP INDEX IF EXISTS idx_polling_places_state_source;",
                "DROP INDEX IF EXISTS idx_polling_places_location;",
                "DROP INDEX IF EXISTS idx_polling_places_created_at;",
                "DROP INDEX IF EXISTS idx_polling_places_updated_at;",
                "DROP INDEX IF EXISTS idx_precincts_state;",
                "DROP INDEX IF EXISTS idx_precincts_county;",
                "DROP INDEX IF EXISTS idx_precincts_source_plugin;",
                "DROP INDEX IF EXISTS idx_precincts_state_source;",
                "DROP INDEX IF EXISTS idx_precincts_current_polling_place;",
                "DROP INDEX IF EXISTS idx_precincts_changed_recently;",
                "DROP INDEX IF EXISTS idx_precincts_created_at;",
                "DROP INDEX IF EXISTS idx_precincts_updated_at;",
                "DROP INDEX IF EXISTS idx_elections_state;",
                "DROP INDEX IF EXISTS idx_elections_date;",
                "DROP INDEX IF EXISTS idx_elections_state_date;",
                "DROP INDEX IF EXISTS idx_precinct_assignments_precinct_id;",
                "DROP INDEX IF EXISTS idx_precinct_assignments_polling_place_id;",
                "DROP INDEX IF EXISTS idx_precinct_assignments_election_id;",
                "DROP INDEX IF EXISTS idx_precinct_assignments_assigned_date;",
                "DROP INDEX IF EXISTS idx_precinct_assignments_precinct_election;",
                "DROP INDEX IF EXISTS idx_api_keys_is_active;",
                "DROP INDEX IF EXISTS idx_api_keys_last_used_at;",
                "DROP INDEX IF EXISTS idx_audit_trail_table_name;",
                "DROP INDEX IF EXISTS idx_audit_trail_record_id;",
                "DROP INDEX IF EXISTS idx_audit_trail_timestamp;",
                "DROP INDEX IF EXISTS idx_audit_trail_table_timestamp;",
            ]
        
        # Execute index drops
        for drop_sql in drop_statements:
            try:
                db.session.execute(db.text(drop_sql))
                logger.info(f"Dropped index: {drop_sql.split('idx_')[1].split(' ')[0] if 'idx_' in drop_sql else 'custom index'}")
            except Exception as e:
                if "does not exist" in str(e).lower() or "no such index" in str(e).lower():
                    logger.info(f"Index does not exist: {drop_sql}")
                else:
                    logger.warning(f"Failed to drop index: {drop_sql}, Error: {e}")
        
        # Commit the changes
        db.session.commit()
        logger.info("Database indexes rollback completed successfully")
        
        return True
        
    except Exception as e:
        logger.error(f"Database indexes rollback failed: {e}")
        db.session.rollback()
        return False