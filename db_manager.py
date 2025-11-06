#!/usr/bin/env python3
"""
Database performance management CLI tool
Provides commands for monitoring, optimizing, and managing database performance
"""

import click
import logging
import os
import json
from flask import Flask
from database import db
from sqlalchemy import text

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_app():
    """Create Flask app for CLI operations"""
    app = Flask(__name__)
    
    # Load environment variables
    from dotenv import load_dotenv
    load_dotenv()
    
    # Database setup - supports both SQLite and PostgreSQL/Cloud SQL
    db_type = os.getenv('DB_TYPE', 'sqlite').lower()
    
    if db_type == 'postgresql' or db_type == 'postgres':
        # PostgreSQL configuration
        db_user = os.getenv('DB_USER', 'postgres')
        db_password = os.getenv('DB_PASSWORD', '')
        db_host = os.getenv('DB_HOST', 'localhost')
        db_port = os.getenv('DB_PORT', '5432')
        db_name = os.getenv('DB_NAME', 'pollingplaces')
        
        # Check if using Cloud SQL Unix socket
        if db_host.startswith('/cloudsql/'):
            # Cloud SQL with Unix socket
            app.config['SQLALCHEMY_DATABASE_URI'] = f'postgresql+psycopg2://{db_user}:{db_password}@/{db_name}?host={db_host}'
        else:
            # Standard PostgreSQL
            app.config['SQLALCHEMY_DATABASE_URI'] = f'postgresql+psycopg2://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}'
    else:
        # SQLite configuration
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///pollingplaces.db'
    
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key')
    
    # Load configuration
    config_file = os.path.join(os.path.dirname(__file__), 'config.json')
    if os.path.exists(config_file):
        with open(config_file, 'r') as f:
            config = json.load(f)
    else:
        config = {
            'geocoder_priority': ['Mapbox', 'Census', 'Google']
        }
    
    app.config['geocoder_priority'] = config['geocoder_priority']
    
    # Initialize database
    db.init_app(app)
    
    # Initialize database optimization
    from database_optimization import init_database_optimization
    init_database_optimization(app)
    
    # Initialize migration system
    from migrations import init_migrations
    init_migrations()
    
    return app

@click.group()
def cli():
    """Database performance management CLI"""
    pass

@cli.command()
@click.option('--verbose', '-v', is_flag=True, help='Verbose output')
def status(verbose):
    """Show database performance status"""
    app = create_app()
    
    with app.app_context():
        # Import modules that need app context
        from database_optimization import db_optimizer, db_indexer, query_optimizer
        from migrations import get_migration_status
        from models import PollingPlace, Precinct, Election, APIKey, AuditTrail
        
        click.echo("=== Database Performance Status ===\n")
        
        # Migration status
        migration_status = get_migration_status()
        click.echo(f"Migrations:")
        click.echo(f"  Total: {migration_status['total_migrations']}")
        click.echo(f"  Applied: {migration_status['applied_count']}")
        click.echo(f"  Pending: {migration_status['pending_count']}")
        click.echo(f"  Current: {migration_status['current_version']}")
        click.echo(f"  Latest: {migration_status['latest_version']}")
        click.echo()
        
        # Performance stats
        stats = db_optimizer.get_performance_stats()
        click.echo("Query Performance:")
        for query_type, data in stats['query_stats'].items():
            click.echo(f"  {query_type}:")
            click.echo(f"    Count: {data['count']}")
            click.echo(f"    Avg Time: {data['avg_time']:.3f}s")
            click.echo(f"    Max Time: {data['max_time']:.3f}s")
        click.echo()
        
        # Database size and table counts
        if verbose:
            try:
                with db.engine.connect() as conn:
                    if db.engine.dialect.name == 'postgresql':
                        # PostgreSQL specific queries
                        result = conn.execute(text("""
                            SELECT 
                                schemaname,
                                tablename,
                                n_tup_ins as inserts,
                                n_tup_upd as updates,
                                n_tup_del as deletes,
                                n_live_tup as live_tuples,
                                n_dead_tup as dead_tuples
                            FROM pg_stat_user_tables
                            ORDER BY n_live_tup DESC
                        """))
                        
                        click.echo("Table Statistics:")
                        for row in result:
                            click.echo(f"  {row[1]}:")
                            click.echo(f"    Live: {row[5]}, Dead: {row[6]}")
                            click.echo(f"    Ins: {row[2]}, Upd: {row[3]}, Del: {row[4]}")
                    else:
                        # Generic table counts
                        tables = [
                            ('polling_places', PollingPlace),
                            ('precincts', Precinct),
                            ('elections', Election),
                            ('api_keys', APIKey),
                            ('audit_trail', AuditTrail)
                        ]
                        
                        click.echo("Table Counts:")
                        for table_name, model in tables:
                            count = model.query.count()
                            click.echo(f"  {table_name}: {count:,}")
                            
            except Exception as e:
                click.echo(f"Error getting detailed stats: {e}")

@cli.command()
def migrate():
    """Run pending database migrations"""
    app = create_app()
    
    with app.app_context():
        # Import modules that need app context
        from migrations import init_migrations, run_migrations
        
        click.echo("Running database migrations...")
        
        # Initialize migration system
        init_migrations()
        
        # Run migrations
        if run_migrations():
            click.echo("✅ All migrations completed successfully")
        else:
            click.echo("❌ Migration failed")
            exit(1)

@cli.command()
@click.option('--force', is_flag=True, help='Force reindexing')
def index(force):
    """Create or recreate database indexes"""
    app = create_app()
    
    with app.app_context():
        # Import modules that need app context
        from database_optimization import db_indexer
        
        click.echo("Creating database indexes...")
        
        try:
            if force:
                click.echo("Force recreating all indexes...")
                # Note: In production, you might want to drop indexes first
            
            db_indexer.create_indexes()
            click.echo("✅ Indexes created successfully")
            
        except Exception as e:
            click.echo(f"❌ Index creation failed: {e}")
            exit(1)

@cli.command()
@click.option('--table', '-t', help='Analyze specific table')
def analyze(table):
    """Analyze database performance and suggest optimizations"""
    app = create_app()
    
    with app.app_context():
        # Import modules that need app context
        from database_optimization import db_indexer, db_optimizer
        
        click.echo("Analyzing database performance...")
        
        # Get performance suggestions
        suggestions = db_indexer.analyze_query_performance()
        
        if suggestions:
            click.echo("\nPerformance Suggestions:")
            for i, suggestion in enumerate(suggestions, 1):
                click.echo(f"{i}. {suggestion}")
        else:
            click.echo("No specific performance suggestions found")
        
        # Analyze slow queries
        stats = db_optimizer.get_performance_stats()
        slow_queries = [
            (qt, data) for qt, data in stats['query_stats'].items()
            if data['avg_time'] > db_optimizer.slow_query_threshold
        ]
        
        if slow_queries:
            click.echo("\nSlow Query Types:")
            for query_type, data in slow_queries:
                click.echo(f"  {query_type}: {data['avg_time']:.3f}s average")
        
        # Table-specific analysis
        if table:
            click.echo(f"\nAnalyzing table: {table}")
            try:
                with db.engine.connect() as conn:
                    if db.engine.dialect.name == 'postgresql':
                        result = conn.execute(text(f"""
                            SELECT 
                                column_name,
                                data_type,
                                is_nullable,
                                column_default
                            FROM information_schema.columns
                            WHERE table_name = '{table}'
                            ORDER BY ordinal_position
                        """))
                        
                        click.echo("Columns:")
                        for row in result:
                            nullable = "NULL" if row[2] == "YES" else "NOT NULL"
                            default = f" DEFAULT {row[3]}" if row[3] else ""
                            click.echo(f"  {row[0]}: {row[1]} {nullable}{default}")
                            
            except Exception as e:
                click.echo(f"Error analyzing table {table}: {e}")

@cli.command()
@click.option('--threshold', '-t', default=1.0, help='Slow query threshold in seconds')
def monitor(threshold):
    """Monitor database queries in real-time"""
    app = create_app()
    
    with app.app_context():
        # Import modules that need app context
        from database_optimization import db_optimizer, database_transaction
        from models import PollingPlace, Precinct, Election
        
        click.echo(f"Monitoring database queries (threshold: {threshold}s)...")
        click.echo("Press Ctrl+C to stop\n")
        
        # Update threshold
        db_optimizer.slow_query_threshold = threshold
        
        try:
            # Reset stats
            db_optimizer.reset_stats()
            
            # Simulate some queries to show monitoring
            with database_transaction():
                # Test queries
                PollingPlace.query.limit(10).all()
                Precinct.query.filter(Precinct.state == 'CA').all()
                Election.query.order_by(Election.date.desc()).limit(5).all()
            
            # Show stats
            stats = db_optimizer.get_performance_stats()
            click.echo("Query Statistics:")
            for query_type, data in stats['query_stats'].items():
                if data['avg_time'] > threshold:
                    click.echo(f"🐌 {query_type}: {data['avg_time']:.3f}s (SLOW)")
                else:
                    click.echo(f"✅ {query_type}: {data['avg_time']:.3f}s")
                    
        except KeyboardInterrupt:
            click.echo("\nMonitoring stopped")

@cli.command()
@click.option('--vacuum', is_flag=True, help='Run VACUUM (PostgreSQL only)')
@click.option('--analyze', is_flag=True, help='Run ANALYZE')
def optimize(vacuum, analyze):
    """Optimize database performance"""
    app = create_app()
    
    with app.app_context():
        # Import modules that need app context
        from database_optimization import db_optimizer
        
        click.echo("Optimizing database...")
        
        try:
            with db.engine.connect() as conn:
                if db.engine.dialect.name == 'postgresql':
                    if vacuum:
                        click.echo("Running VACUUM...")
                        conn.execute(text("VACUUM ANALYZE"))
                        click.echo("✅ VACUUM completed")
                    
                    if analyze:
                        click.echo("Running ANALYZE...")
                        conn.execute(text("ANALYZE"))
                        click.echo("✅ ANALYZE completed")
                        
                elif db.engine.dialect.name == 'sqlite':
                    if vacuum:
                        click.echo("Running VACUUM...")
                        conn.execute(text("VACUUM"))
                        click.echo("✅ VACUUM completed")
                    
                    if analyze:
                        click.echo("Running ANALYZE...")
                        conn.execute(text("ANALYZE"))
                        click.echo("✅ ANALYZE completed")
                
                else:
                    click.echo("Optimization not supported for this database type")
                    
        except Exception as e:
            click.echo(f"❌ Optimization failed: {e}")
            exit(1)

@cli.command()
@click.option('--backup-path', '-p', help='Backup file path')
def backup(backup_path):
    """Create database backup"""
    app = create_app()
    
    with app.app_context():
        if not backup_path:
            import datetime
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = f"backup_{timestamp}.sql"
        
        click.echo(f"Creating database backup: {backup_path}")
        
        try:
            if db.engine.dialect.name == 'postgresql':
                import subprocess
                db_url = app.config.get('DATABASE_URL', '')
                
                # Extract connection info from DATABASE_URL
                # This is simplified - in production you'd want better parsing
                cmd = f"pg_dump {db_url} > {backup_path}"
                subprocess.run(cmd, shell=True, check=True)
                
            elif db.engine.dialect.name == 'sqlite':
                import shutil
                db_path = app.config.get('SQLITE_PATH', '/data/pollingplaces.db')
                shutil.copy2(db_path, backup_path)
                
            else:
                click.echo("Backup not supported for this database type")
                return
            
            click.echo(f"✅ Backup created: {backup_path}")
            
        except Exception as e:
            click.echo(f"❌ Backup failed: {e}")
            exit(1)

@cli.command()
def reset_stats():
    """Reset performance statistics"""
    app = create_app()
    
    with app.app_context():
        # Import modules that need app context
        from database_optimization import db_optimizer
        
        db_optimizer.reset_stats()
        click.echo("✅ Performance statistics reset")

if __name__ == '__main__':
    cli()