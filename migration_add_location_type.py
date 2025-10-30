#!/usr/bin/env python3
"""
Migration script to add location_type field to polling_places table
and create precinct_polling_places association table for many-to-many relationship.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database import db
from models import PollingPlace, Precinct, LocationType, precinct_polling_places
import app

def migrate():
    """Apply database migration"""
    print("Starting migration...")
    
    with app.app.app_context():
        # Check if location_type column already exists
        inspector = db.inspect(db.engine)
        columns = [col['name'] for col in inspector.get_columns('polling_places')]
        
        if 'location_type' not in columns:
            print("Adding location_type column to polling_places table...")
            # Add location_type column with enum type
            with db.engine.connect() as conn:
                conn.execute(db.text("""
                    ALTER TABLE polling_places 
                    ADD COLUMN location_type VARCHAR(20) NOT NULL DEFAULT 'election day'
                """))
                conn.commit()
            print("✓ Added location_type column")
        else:
            print("✓ location_type column already exists")
        
        # Check if association table already exists
        tables = inspector.get_table_names()
        if 'precinct_polling_places' not in tables:
            print("Creating precinct_polling_places association table...")
            db.create_all()  # This will create the association table
            print("✓ Created precinct_polling_places table")
        else:
            print("✓ precinct_polling_places table already exists")
        
        print("Migration completed successfully!")

if __name__ == '__main__':
    migrate()