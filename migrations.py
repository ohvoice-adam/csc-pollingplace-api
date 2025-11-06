"""
Database migration system for schema updates and version management
"""

import os
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional
from flask import current_app
from sqlalchemy import text, inspect
from database import db

logger = logging.getLogger(__name__)

class Migration:
    """Base class for database migrations"""
    
    def __init__(self, version: str, description: str):
        self.version = version
        self.description = description
        self.created_at = datetime.utcnow()
    
    def up(self):
        """Apply the migration"""
        raise NotImplementedError("Migration must implement up() method")
    
    def down(self):
        """Rollback the migration"""
        raise NotImplementedError("Migration must implement down() method")
    
    def __str__(self):
        return f"Migration {self.version}: {self.description}"

class MigrationManager:
    """Manages database migrations and version tracking"""
    
    def __init__(self):
        self.migrations: Dict[str, Migration] = {}
        self._table_initialized = False
    
    def _ensure_migration_table(self):
        """Create migrations table if it doesn't exist"""
        if self._table_initialized:
            return
            
        try:
            with db.engine.connect() as conn:
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS schema_migrations (
                        version VARCHAR(50) PRIMARY KEY,
                        description TEXT,
                        applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        rollback_script TEXT
                    )
                """))
                conn.commit()
            self._table_initialized = True
        except Exception as e:
            logger.error(f"Failed to create migration table: {e}")
            raise
    
    def register_migration(self, migration: Migration):
        """Register a migration"""
        self.migrations[migration.version] = migration
        logger.info(f"Registered migration: {migration}")
    
    def get_applied_migrations(self) -> List[str]:
        """Get list of applied migrations"""
        try:
            with db.engine.connect() as conn:
                result = conn.execute(text("SELECT version FROM schema_migrations ORDER BY version"))
                return [row[0] for row in result]
        except Exception as e:
            logger.error(f"Failed to get applied migrations: {e}")
            return []
    
    def get_pending_migrations(self) -> List[Migration]:
        """Get list of pending migrations"""
        applied = set(self.get_applied_migrations())
        pending = []
        
        for version in sorted(self.migrations.keys()):
            if version not in applied:
                pending.append(self.migrations[version])
        
        return pending
    
    def apply_migration(self, migration: Migration) -> bool:
        """Apply a single migration"""
        try:
            logger.info(f"Applying migration: {migration}")
            
            with db.engine.connect() as conn:
                # Start transaction
                trans = conn.begin()
                
                try:
                    # Apply migration
                    migration.up()
                    
                    # Record migration
                    conn.execute(text("""
                        INSERT INTO schema_migrations (version, description)
                        VALUES (:version, :description)
                    """), {
                        'version': migration.version,
                        'description': migration.description
                    })
                    
                    # Commit transaction
                    trans.commit()
                    logger.info(f"Successfully applied migration: {migration}")
                    return True
                    
                except Exception as e:
                    trans.rollback()
                    logger.error(f"Failed to apply migration {migration}: {e}")
                    raise
                    
        except Exception as e:
            logger.error(f"Migration failed: {e}")
            return False
    
    def rollback_migration(self, version: str) -> bool:
        """Rollback a migration"""
        if version not in self.migrations:
            logger.error(f"Migration {version} not found")
            return False
        
        migration = self.migrations[version]
        
        try:
            logger.info(f"Rolling back migration: {migration}")
            
            with db.engine.connect() as conn:
                # Start transaction
                trans = conn.begin()
                
                try:
                    # Rollback migration
                    migration.down()
                    
                    # Remove migration record
                    conn.execute(text("""
                        DELETE FROM schema_migrations WHERE version = :version
                    """), {'version': version})
                    
                    # Commit transaction
                    trans.commit()
                    logger.info(f"Successfully rolled back migration: {migration}")
                    return True
                    
                except Exception as e:
                    trans.rollback()
                    logger.error(f"Failed to rollback migration {migration}: {e}")
                    raise
                    
        except Exception as e:
            logger.error(f"Rollback failed: {e}")
            return False
    
    def migrate(self) -> bool:
        """Apply all pending migrations"""
        pending = self.get_pending_migrations()
        
        if not pending:
            logger.info("No pending migrations")
            return True
        
        logger.info(f"Found {len(pending)} pending migrations")
        
        for migration in pending:
            if not self.apply_migration(migration):
                logger.error(f"Migration failed at {migration.version}")
                return False
        
        logger.info("All migrations applied successfully")
        return True
    
    def get_migration_status(self) -> Dict[str, Any]:
        """Get migration status"""
        applied = self.get_applied_migrations()
        pending = self.get_pending_migrations()
        
        return {
            'total_migrations': len(self.migrations),
            'applied_count': len(applied),
            'pending_count': len(pending),
            'applied_migrations': applied,
            'pending_migrations': [m.version for m in pending],
            'current_version': applied[-1] if applied else None,
            'latest_version': max(self.migrations.keys()) if self.migrations else None
        }

# Individual migration classes
class Migration001AddPerformanceIndexes(Migration):
    """Add performance indexes for frequently queried columns"""
    
    def __init__(self):
        super().__init__("001", "Add performance indexes for frequently queried columns")
    
    def up(self):
        """Create performance indexes"""
        indexes = [
            # PollingPlace indexes
            "CREATE INDEX IF NOT EXISTS idx_polling_places_state ON polling_places(state)",
            "CREATE INDEX IF NOT EXISTS idx_polling_places_county ON polling_places(county)",
            "CREATE INDEX IF NOT EXISTS idx_polling_places_source_plugin ON polling_places(source_plugin)",
            "CREATE INDEX IF NOT EXISTS idx_polling_places_location_type ON polling_places(location_type)",
            "CREATE INDEX IF NOT EXISTS idx_polling_places_coordinates ON polling_places(latitude, longitude)",
            "CREATE INDEX IF NOT EXISTS idx_polling_places_created_at ON polling_places(created_at)",
            "CREATE INDEX IF NOT EXISTS idx_polling_places_state_county ON polling_places(state, county)",
            
            # Precinct indexes
            "CREATE INDEX IF NOT EXISTS idx_precincts_state ON precincts(state)",
            "CREATE INDEX IF NOT EXISTS idx_precincts_county ON precincts(county)",
            "CREATE INDEX IF NOT EXISTS idx_precincts_source_plugin ON precincts(source_plugin)",
            "CREATE INDEX IF NOT EXISTS idx_precincts_current_polling_place ON precincts(current_polling_place_id)",
            "CREATE INDEX IF NOT EXISTS idx_precincts_changed_recently ON precincts(changed_recently)",
            "CREATE INDEX IF NOT EXISTS idx_precincts_state_county ON precincts(state, county)",
            
            # PrecinctAssignment indexes
            "CREATE INDEX IF NOT EXISTS idx_precinct_assignments_precinct ON precinct_assignments(precinct_id)",
            "CREATE INDEX IF NOT EXISTS idx_precinct_assignments_polling_place ON precinct_assignments(polling_place_id)",
            "CREATE INDEX IF NOT EXISTS idx_precinct_assignments_election ON precinct_assignments(election_id)",
            "CREATE INDEX IF NOT EXISTS idx_precinct_assignments_assigned_date ON precinct_assignments(assigned_date)",
            "CREATE INDEX IF NOT EXISTS idx_precinct_assignments_current ON precinct_assignments(removed_date)",
            
            # Election indexes
            "CREATE INDEX IF NOT EXISTS idx_elections_date ON elections(date)",
            "CREATE INDEX IF NOT EXISTS idx_elections_state ON elections(state)",
            "CREATE INDEX IF NOT EXISTS idx_elections_date_state ON elections(date, state)",
            
            # APIKey indexes
            "CREATE INDEX IF NOT EXISTS idx_api_keys_active ON api_keys(is_active)",
            "CREATE INDEX IF NOT EXISTS idx_api_keys_last_used ON api_keys(last_used_at)",
            
            # AuditTrail indexes
            "CREATE INDEX IF NOT EXISTS idx_audit_trail_table_record ON audit_trail(table_name, record_id)",
            "CREATE INDEX IF NOT EXISTS idx_audit_trail_timestamp ON audit_trail(timestamp)",
            "CREATE INDEX IF NOT EXISTS idx_audit_trail_user ON audit_trail(user_id)",
        ]
        
        with db.engine.connect() as conn:
            for index_sql in indexes:
                try:
                    conn.execute(text(index_sql))
                    logger.info(f"Created index: {index_sql}")
                except Exception as e:
                    logger.warning(f"Index creation failed: {e}")
            conn.commit()
    
    def down(self):
        """Remove performance indexes"""
        indexes = [
            "DROP INDEX IF EXISTS idx_polling_places_state",
            "DROP INDEX IF EXISTS idx_polling_places_county",
            "DROP INDEX IF EXISTS idx_polling_places_source_plugin",
            "DROP INDEX IF EXISTS idx_polling_places_location_type",
            "DROP INDEX IF EXISTS idx_polling_places_coordinates",
            "DROP INDEX IF EXISTS idx_polling_places_created_at",
            "DROP INDEX IF EXISTS idx_polling_places_state_county",
            "DROP INDEX IF EXISTS idx_precincts_state",
            "DROP INDEX IF EXISTS idx_precincts_county",
            "DROP INDEX IF EXISTS idx_precincts_source_plugin",
            "DROP INDEX IF EXISTS idx_precincts_current_polling_place",
            "DROP INDEX IF EXISTS idx_precincts_changed_recently",
            "DROP INDEX IF EXISTS idx_precincts_state_county",
            "DROP INDEX IF EXISTS idx_precinct_assignments_precinct",
            "DROP INDEX IF EXISTS idx_precinct_assignments_polling_place",
            "DROP INDEX IF EXISTS idx_precinct_assignments_election",
            "DROP INDEX IF EXISTS idx_precinct_assignments_assigned_date",
            "DROP INDEX IF EXISTS idx_precinct_assignments_current",
            "DROP INDEX IF EXISTS idx_elections_date",
            "DROP INDEX IF EXISTS idx_elections_state",
            "DROP INDEX IF EXISTS idx_elections_date_state",
            "DROP INDEX IF EXISTS idx_api_keys_active",
            "DROP INDEX IF EXISTS idx_api_keys_last_used",
            "DROP INDEX IF EXISTS idx_audit_trail_table_record",
            "DROP INDEX IF EXISTS idx_audit_trail_timestamp",
            "DROP INDEX IF EXISTS idx_audit_trail_user",
        ]
        
        with db.engine.connect() as conn:
            for index_sql in indexes:
                try:
                    conn.execute(text(index_sql))
                    logger.info(f"Dropped index: {index_sql}")
                except Exception as e:
                    logger.warning(f"Index drop failed: {e}")
            conn.commit()

class Migration002AddLocationTypeEnum(Migration):
    """Add location_type enum constraint"""
    
    def __init__(self):
        super().__init__("002", "Add location_type enum constraint")
    
    def up(self):
        """Add location_type constraint"""
        with db.engine.connect() as conn:
            if db.engine.dialect.name == 'postgresql':
                conn.execute(text("""
                    ALTER TABLE polling_places 
                    ADD CONSTRAINT chk_location_type 
                    CHECK (location_type IN ('drop box', 'election day', 'early voting'))
                """))
            conn.commit()
    
    def down(self):
        """Remove location_type constraint"""
        with db.engine.connect() as conn:
            if db.engine.dialect.name == 'postgresql':
                conn.execute(text("""
                    ALTER TABLE polling_places DROP CONSTRAINT IF EXISTS chk_location_type
                """))
            conn.commit()

class Migration003AddFullTextSearchIndexes(Migration):
    """Add full-text search indexes for polling places"""
    
    def __init__(self):
        super().__init__("003", "Add full-text search indexes")
    
    def up(self):
        """Create full-text search indexes"""
        with db.engine.connect() as conn:
            if db.engine.dialect.name == 'postgresql':
                # PostgreSQL full-text search
                conn.execute(text("""
                    CREATE INDEX IF NOT EXISTS idx_polling_places_name_fts 
                    ON polling_places USING gin(to_tsvector('english', name))
                """))
                conn.execute(text("""
                    CREATE INDEX IF NOT EXISTS idx_polling_places_address_fts 
                    ON polling_places USING gin(to_tsvector('english', 
                        COALESCE(address_line1, '') || ' ' || 
                        COALESCE(address_line2, '') || ' ' || 
                        COALESCE(city, '') || ' ' || 
                        COALESCE(county, '')
                    ))
                """))
            elif db.engine.dialect.name == 'sqlite':
                # SQLite FTS5
                conn.execute(text("""
                    CREATE VIRTUAL TABLE IF NOT EXISTS polling_places_fts 
                    USING fts5(name, address_line1, city, county, content='polling_places')
                """))
                conn.execute(text("""
                    CREATE TRIGGER IF NOT EXISTS polling_places_fts_insert 
                    AFTER INSERT ON polling_places BEGIN
                        INSERT INTO polling_places_fts(rowid, name, address_line1, city, county)
                        VALUES (new.id, new.name, new.address_line1, new.city, new.county);
                    END
                """))
            conn.commit()
    
    def down(self):
        """Remove full-text search indexes"""
        with db.engine.connect() as conn:
            if db.engine.dialect.name == 'postgresql':
                conn.execute(text("DROP INDEX IF EXISTS idx_polling_places_name_fts"))
                conn.execute(text("DROP INDEX IF EXISTS idx_polling_places_address_fts"))
            elif db.engine.dialect.name == 'sqlite':
                conn.execute(text("DROP TRIGGER IF EXISTS polling_places_fts_insert"))
                conn.execute(text("DROP TABLE IF EXISTS polling_places_fts"))
            conn.commit()

# Global migration manager (lazy initialization)
migration_manager = None

def get_migration_manager():
    """Get or create migration manager"""
    global migration_manager
    if migration_manager is None:
        migration_manager = MigrationManager()
        register_migrations()
    return migration_manager

def register_migrations():
    """Register all migrations"""
    manager = get_migration_manager()
    manager.register_migration(Migration001AddPerformanceIndexes())
    manager.register_migration(Migration002AddLocationTypeEnum())
    manager.register_migration(Migration003AddFullTextSearchIndexes())

def init_migrations():
    """Initialize migration system"""
    # Just ensure migrations are registered
    get_migration_manager()
    logger.info("Migration system initialized")

def run_migrations():
    """Run all pending migrations"""
    return get_migration_manager().migrate()

def get_migration_status():
    """Get migration status"""
    return get_migration_manager().get_migration_status()