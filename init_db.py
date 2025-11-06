#!/usr/bin/env python3
"""
Database initialization script
Sets up database optimization and runs migrations
"""

import os
import sys
from flask import Flask
from database import db
from database_optimization import init_database_optimization
from migrations import init_migrations, run_migrations

def create_app():
    """Create Flask app for initialization"""
    app = Flask(__name__)
    
    # Load configuration
    if os.path.exists('config.json'):
        import json
        with open('config.json', 'r') as f:
            config = json.load(f)
    else:
        config = {}
    
    # Database configuration
    db_type = os.getenv('DB_TYPE', 'sqlite').lower()
    
    if db_type in ['postgresql', 'postgres']:
        db_user = os.getenv('DB_USER', 'postgres')
        db_password = os.getenv('DB_PASSWORD', '')
        db_host = os.getenv('DB_HOST', 'localhost')
        db_port = os.getenv('DB_PORT', '5432')
        db_name = os.getenv('DB_NAME', 'pollingplaces')
        
        if db_host.startswith('/cloudsql/'):
            app.config['SQLALCHEMY_DATABASE_URI'] = f'postgresql+psycopg2://{db_user}:{db_password}@/{db_name}?host={db_host}'
        else:
            app.config['SQLALCHEMY_DATABASE_URI'] = f'postgresql+psycopg2://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}'
    else:
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///pollingplaces.db'
    
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    # Initialize database
    db.init_app(app)
    
    return app

def main():
    """Main initialization function"""
    print("🚀 Initializing database...")
    
    app = create_app()
    
    with app.app_context():
        try:
            # Import models to ensure they're registered
            from models import PollingPlace, Precinct, Election, APIKey, AuditTrail, AdminUser, PrecinctAssignment
            
            # Create all tables
            print("📋 Creating database tables...")
            db.create_all()
            print("✅ Database tables created")
            
            # Initialize database optimization
            print("📊 Setting up database optimization...")
            init_database_optimization(app)
            print("✅ Database optimization initialized")
            
            # Initialize migration system
            print("🔄 Setting up migration system...")
            init_migrations()
            print("✅ Migration system initialized")
            
            # Run migrations
            print("🔄 Running database migrations...")
            if run_migrations():
                print("✅ All migrations completed successfully")
            else:
                print("❌ Migration failed")
                sys.exit(1)
            
            print("🎉 Database initialization completed successfully!")
            
        except Exception as e:
            print(f"❌ Initialization failed: {e}")
            sys.exit(1)

if __name__ == '__main__':
    main()