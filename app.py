"""
CSC Polling Place API
Main application file

Provides centralized polling place location data in VIP (Voting Information Project) format
compatible with Google Civic Data API.
"""

import os
import json
import secrets
import bcrypt
import logging
import time
import threading
from datetime import datetime
from functools import wraps
from flask import Flask, jsonify, request, render_template, redirect, url_for, flash, session
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from dotenv import load_dotenv
from apscheduler.schedulers.background import BackgroundScheduler
from plugins.plugin_manager import PluginManager

# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__)

# Configure logging
log_file = os.path.join(os.path.dirname(__file__), 'app.log')
logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(levelname)s in %(name)s: %(message)s')
file_handler = logging.FileHandler(log_file)
file_handler.setLevel(logging.INFO)
file_handler.setFormatter(logging.Formatter('[%(asctime)s] %(levelname)s in %(name)s: %(message)s'))
logging.getLogger().addHandler(file_handler)
app.logger.setLevel(logging.INFO)

# Configuration
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

# Initialize extensions
from database import db
from models import PollingPlace, APIKey, Precinct, PrecinctAssignment, Election, AdminUser, AuditTrail
db.init_app(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'admin_login'

# Rate limiting
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"]
)

# Add timezone filter for templates
@app.template_filter('timezone_filter')
def timezone_filter(timestamp):
    """Convert UTC timestamp to local time for display"""
    if timestamp is None:
        return None
    from datetime import datetime, timedelta
    
    # Parse the timestamp if it's a string
    if isinstance(timestamp, str):
        try:
            timestamp = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        except:
            return timestamp
    
    # Convert UTC to Eastern Time (UTC-4 or UTC-5 depending on DST)
    # For simplicity, we'll use UTC-4 (EDT) - adjust as needed
    eastern_time = timestamp - timedelta(hours=4)
    return eastern_time.strftime('%Y-%m-%d %H:%M:%S')

# Initialize plugin manager (will be done after models are defined)
plugin_manager = None

# Initialize scheduler
scheduler = BackgroundScheduler()
scheduler.start()

# Import UserMixin for AdminUser
from flask_login import UserMixin

# Create tables
with app.app_context():
    db.create_all()

# Rate limiting helper functions
def get_api_key_identifier():
    """Get the API key from request for rate limiting"""
    return request.headers.get('X-API-Key', 'anonymous')

def get_api_key_limits():
    """
    Get dynamic rate limits for the current API key.
    Returns None (infinite) if no limits are set on the API key.
    """
    # Check if we have an API key object in the request context
    if hasattr(request, 'api_key') and request.api_key:
        key_obj = request.api_key
        limits = []

        # Add per-day limit if set
        if key_obj.rate_limit_per_day:
            limits.append(f"{key_obj.rate_limit_per_day} per day")

        # Add per-hour limit if set
        if key_obj.rate_limit_per_hour:
            limits.append(f"{key_obj.rate_limit_per_hour} per hour")

        # If no limits are set, return None (infinite)
        if not limits:
            return None

        return ";".join(limits)

    # No API key in request context, no limits
    return None

# Initialize rate limiter with no default limits (infinite by default)
limiter = Limiter(
    app=app,
    key_func=get_api_key_identifier,
    default_limits=[],
    storage_uri="memory://"
)

# Initialize scheduler
scheduler = BackgroundScheduler()
scheduler.start()

# Models are imported from models.py


@login_manager.user_loader
def load_user(user_id):
    """Load user for Flask-Login"""
    return AdminUser.query.get(int(user_id))


# Authentication decorator
def require_api_key(f):
    """
    Decorator to require API key authentication for endpoints
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Get API key from header
        api_key = request.headers.get('X-API-Key')

        if not api_key:
            return jsonify({'error': 'API key required. Provide via X-API-Key header.'}), 401

        # Validate API key
        key_obj = APIKey.query.filter_by(key=api_key, is_active=True).first()

        if not key_obj:
            return jsonify({'error': 'Invalid or inactive API key'}), 401

        # Update last used timestamp
        key_obj.last_used_at = datetime.utcnow()
        db.session.commit()

        # Store key object in request context for potential use
        request.api_key = key_obj

        return f(*args, **kwargs)

    return decorated_function


# Routes
@app.route('/')
def index():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'service': 'CSC Polling Place API',
        'version': '1.0.0'
    })


@app.route('/health')
def health():
    """Health check endpoint for Cloud Run"""
    try:
        # Test database connection
        db.session.execute(db.text('SELECT 1'))
        
        # Get database type and connection info
        db_uri = app.config['SQLALCHEMY_DATABASE_URI']
        if db_uri.startswith('sqlite'):
            db_type = 'SQLite'
            db_path = db_uri.replace('sqlite:///', '')
            db_info = f"SQLite at {db_path}"
        elif db_uri.startswith('postgresql'):
            db_type = 'PostgreSQL'
            if '?host=/cloudsql/' in db_uri:
                # Cloud SQL connection
                instance = db_uri.split('?host=')[1]
                db_info = f"Cloud SQL at {instance}"
            else:
                # Standard PostgreSQL connection
                db_info = "PostgreSQL database"
        else:
            db_type = "Unknown"
            db_info = db_uri.split('://')[0]
            
        return jsonify({
            'status': 'healthy', 
            'database': {
                'connected': True,
                'type': db_type,
                'info': db_info
            }
        }), 200
    except Exception as e:
        return jsonify({
            'status': 'unhealthy', 
            'database': {
                'connected': False,
                'error': str(e)
            }
        }), 500


@app.route('/api/keys', methods=['POST'])
def create_api_key():
    """
    Create a new API key
    Requires master API key or admin authentication
    Body: {"name": "Description of key"}
    """
    # Check for master key
    master_key = os.getenv('MASTER_API_KEY')
    provided_key = request.headers.get('X-API-Key')

    if not master_key or provided_key != master_key:
        return jsonify({'error': 'Master API key required to create new keys'}), 401

    data = request.get_json()
    if not data or 'name' not in data:
        return jsonify({'error': 'Name required in request body'}), 400

    # Generate new key
    new_key = APIKey(
        key=APIKey.generate_key(),
        name=data['name'],
        rate_limit_per_day=data.get('rate_limit_per_day'),
        rate_limit_per_hour=data.get('rate_limit_per_hour')
    )

    db.session.add(new_key)
    db.session.commit()

    return jsonify({
        'message': 'API key created successfully',
        'key': new_key.to_dict()
    }), 201


@app.route('/api/keys', methods=['GET'])
@require_api_key
def list_api_keys():
    """
    List all API keys (requires valid API key)
    """
    keys = APIKey.query.all()
    return jsonify({
        'count': len(keys),
        'keys': [key.to_dict() for key in keys]
    }), 200


@app.route('/api/keys/<int:key_id>', methods=['DELETE'])
@require_api_key
def revoke_api_key(key_id):
    """
    Revoke (deactivate) an API key
    """
    key = APIKey.query.get_or_404(key_id)
    key.is_active = False
    db.session.commit()

    return jsonify({
        'message': f'API key {key_id} revoked successfully'
    }), 200


@app.route('/api/polling-places', methods=['GET'])
@require_api_key
@limiter.limit(get_api_key_limits)
def get_polling_places():
    """
    Get polling places for a specific state
    Query parameters (REQUIRED):
    - state: State code (e.g., ?state=VA)
    Optional parameters:
    - dataset: Data source - 'dummy' for test data (default: real plugin data)
    - format: Response format - 'vip' or 'standard' (default: standard)
    """
    try:
        # State parameter is now required
        state_filter = request.args.get('state')
        if not state_filter:
            return jsonify({
                'error': 'State parameter is required. Use ?state=VA (or other state code). Add dataset=dummy for test data.'
            }), 400

        state_filter = state_filter.upper()

        # Check if user wants dummy data
        dataset = request.args.get('dataset', '').lower()

        if dataset == 'dummy':
            # Query dummy data for this state
            query = PollingPlace.query.filter_by(state=state_filter, source_plugin='dummy')
        else:
            # Query real plugin data for this state
            plugin = plugin_manager.get_plugin_by_state(state_filter)
            if not plugin:
                return jsonify({
                    'error': f'No data plugin available for state "{state_filter}". Available states: {", ".join([p["state_code"] for p in plugin_manager.list_plugins() if p["state_code"] != "ALL"])}. Add dataset=dummy for test data.'
                }), 404

            # Query by both state AND source_plugin to avoid mixing with dummy data
            query = PollingPlace.query.filter_by(state=state_filter, source_plugin=plugin.name)

        polling_places = query.all()

        # Check format parameter
        response_format = request.args.get('format', 'standard').lower()

        if response_format == 'vip':
            # Return in VIP format
            return jsonify({
                'pollingLocations': [pp.to_vip_format() for pp in polling_places]
            }), 200
        else:
            # Return in standard format
            return jsonify({
                'count': len(polling_places),
                'polling_places': [pp.to_dict() for pp in polling_places]
            }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/polling-places/<location_id>', methods=['GET'])
@require_api_key
@limiter.limit(get_api_key_limits)
def get_polling_place(location_id):
    """
    Get a specific polling place by ID
    Query parameters:
    - format: Response format - 'vip' or 'standard' (default: standard)
    """
    try:
        polling_place = PollingPlace.query.get_or_404(location_id)

        # Check format parameter
        response_format = request.args.get('format', 'standard').lower()

        if response_format == 'vip':
            return jsonify(polling_place.to_vip_format()), 200
        else:
            return jsonify(polling_place.to_dict()), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 404


@app.route('/api/precincts', methods=['GET'])
@require_api_key
@limiter.limit(get_api_key_limits)
def get_precincts():
    """
    Get precincts for a specific state
    Query parameters (REQUIRED):
    - state: State code (e.g., ?state=VA)
    Optional parameters:
    - dataset: Data source - 'dummy' for test data (default: real plugin data)
    - county: Filter by county
    - changed_recently: Filter by recent changes (true/false)
    """
    try:
        # State parameter is now required
        state_filter = request.args.get('state')
        if not state_filter:
            return jsonify({
                'error': 'State parameter is required. Use ?state=VA (or other state code). Add dataset=dummy for test data.'
            }), 400

        state_filter = state_filter.upper()

        # Check if user wants dummy data
        dataset = request.args.get('dataset', '').lower()

        if dataset == 'dummy':
            # Query dummy data for this state
            query = Precinct.query.filter_by(state=state_filter, source_plugin='dummy')
        else:
            # Query real plugin data for this state
            plugin = plugin_manager.get_plugin_by_state(state_filter)
            if not plugin:
                return jsonify({
                    'error': f'No data plugin available for state "{state_filter}". Available states: {", ".join([p["state_code"] for p in plugin_manager.list_plugins() if p["state_code"] != "ALL"])}. Add dataset=dummy for test data.'
                }), 404

            # Query by both state AND source_plugin to avoid mixing with dummy data
            query = Precinct.query.filter_by(state=state_filter, source_plugin=plugin.name)

        # Filter by county if provided
        county_filter = request.args.get('county')
        if county_filter:
            query = query.filter_by(county=county_filter)

        # Filter by changed_recently if provided
        changed_recently_filter = request.args.get('changed_recently')
        if changed_recently_filter:
            changed_recently = changed_recently_filter.lower() == 'true'
            query = query.filter_by(changed_recently=changed_recently)

        precincts = query.all()

        return jsonify({
            'count': len(precincts),
            'precincts': [p.to_dict() for p in precincts]
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/precincts/<precinct_id>', methods=['GET'])
@require_api_key
@limiter.limit(get_api_key_limits)
def get_precinct(precinct_id):
    """
    Get a specific precinct by ID with assignment history
    """
    try:
        precinct = Precinct.query.get_or_404(precinct_id)
        return jsonify(precinct.to_dict_with_history()), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 404


@app.route('/api/polling-places/<location_id>/precincts', methods=['GET'])
@require_api_key
@limiter.limit(get_api_key_limits)
def get_polling_place_precincts(location_id):
    """
    Get all precincts currently assigned to a polling place
    Includes total registered voters
    """
    try:
        polling_place = PollingPlace.query.get_or_404(location_id)

        # Get all precincts currently assigned to this polling place
        precincts = Precinct.query.filter_by(current_polling_place_id=location_id).all()

        # Calculate total registered voters
        total_voters = sum(p.registered_voters or 0 for p in precincts)

        return jsonify({
            'polling_place': polling_place.to_dict(),
            'precinct_count': len(precincts),
            'total_registered_voters': total_voters,
            'precincts': [p.to_dict() for p in precincts]
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 404


@app.route('/api/plugins', methods=['GET'])
@require_api_key
@limiter.limit(get_api_key_limits)
def list_plugins():
    """List all loaded plugins and their status"""
    return jsonify({
        'plugins': plugin_manager.list_plugins()
    }), 200


@app.route('/api/plugins/<plugin_name>/sync', methods=['POST'])
@require_api_key
@limiter.limit(get_api_key_limits)
def sync_plugin(plugin_name):
    """Trigger a data sync for a specific plugin"""
    try:
        # Get optional election_id from query params or body
        election_id_str = request.args.get('election_id') or (request.json.get('election_id') if request.json else None)
        election_id = int(election_id_str) if election_id_str else None

        result = plugin_manager.sync_plugin(plugin_name, election_id=election_id)
        return jsonify(result), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/plugins/<plugin_name>/import-historical', methods=['POST'])
@require_api_key
@limiter.limit(get_api_key_limits)
def import_historical_plugin_data(plugin_name):
    """
    Trigger a historical data import for a specific plugin.
    This imports data from all available elections in chronological order
    to build up a complete assignment history.
    """
    try:
        plugin = plugin_manager.get_plugin(plugin_name)
        if not plugin:
            return jsonify({'error': f'Plugin "{plugin_name}" not found'}), 404

        # Check if plugin has import_historical_data method
        if not hasattr(plugin, 'import_historical_data'):
            return jsonify({
                'error': f'Plugin "{plugin_name}" does not support historical imports'
            }), 400

        # Run historical import
        result = plugin.import_historical_data()

        return jsonify({
            'success': True,
            'message': f'Historical import completed for {plugin_name}',
            'results': result
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/elections', methods=['GET'])
@require_api_key
@limiter.limit(get_api_key_limits)
def get_elections():
    """
    Get list of elections
    Query parameters:
    - state: Filter by state code (e.g., ?state=VA)
    - year: Filter by year (e.g., ?year=2024)
    """
    try:
        query = Election.query

        # Filter by state if provided
        state_filter = request.args.get('state')
        if state_filter:
            query = query.filter_by(state=state_filter.upper())

        # Filter by year if provided
        year_filter = request.args.get('year')
        if year_filter:
            year = int(year_filter)
            from datetime import date
            start_date = date(year, 1, 1)
            end_date = date(year, 12, 31)
            query = query.filter(Election.date >= start_date, Election.date <= end_date)

        # Order by date descending (most recent first)
        elections = query.order_by(Election.date.desc()).all()

        return jsonify({
            'count': len(elections),
            'elections': [e.to_dict() for e in elections]
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/elections/<int:election_id>', methods=['GET'])
@require_api_key
@limiter.limit(get_api_key_limits)
def get_election(election_id):
    """
    Get a specific election by ID with statistics
    """
    try:
        election = Election.query.get_or_404(election_id)

        # Get statistics about this election
        assignment_count = PrecinctAssignment.query.filter_by(election_id=election_id).count()
        precinct_count = db.session.query(PrecinctAssignment.precinct_id).filter_by(election_id=election_id).distinct().count()

        result = election.to_dict()
        result['stats'] = {
            'total_assignments': assignment_count,
            'unique_precincts': precinct_count
        }

        return jsonify(result), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 404


@app.route('/api/elections/<int:election_id>/precincts', methods=['GET'])
@require_api_key
@limiter.limit(get_api_key_limits)
def get_election_precincts(election_id):
    """
    Get precincts as they were assigned in a specific election
    Query parameters:
    - county: Filter by county
    """
    try:
        election = Election.query.get_or_404(election_id)

        # Get all precinct assignments for this election
        query = db.session.query(
            Precinct,
            PrecinctAssignment
        ).join(
            PrecinctAssignment,
            Precinct.id == PrecinctAssignment.precinct_id
        ).filter(
            PrecinctAssignment.election_id == election_id
        )

        # Filter by county if provided
        county_filter = request.args.get('county')
        if county_filter:
            query = query.filter(Precinct.county == county_filter)

        results = query.all()

        # Build response with precinct data and election-specific assignment
        precincts = []
        for precinct, assignment in results:
            precinct_data = precinct.to_dict()
            # Add election-specific polling place assignment
            precinct_data['election_polling_place_id'] = assignment.polling_place_id
            precinct_data['election_assigned_date'] = assignment.assigned_date.isoformat() if assignment.assigned_date else None
            precinct_data['election_removed_date'] = assignment.removed_date.isoformat() if assignment.removed_date else None
            precinct_data['previous_polling_place_id'] = assignment.previous_polling_place_id
            precincts.append(precinct_data)

        return jsonify({
            'election': election.to_dict(),
            'count': len(precincts),
            'precincts': precincts
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/bulk-delete', methods=['POST'])
@require_api_key
@limiter.limit(get_api_key_limits)
def bulk_delete_records():
    """
    Bulk delete polling places, precincts, assignments, and/or elections with filtering options
    Requires confirmation for safety
    
    Request body:
    {
        "delete_types": ["polling_places", "precincts", "assignments", "elections"],  // required: what to delete
        "filters": {
            "state": "OH",           // optional: filter by state code
            "start_date": "2024-01-01",  // optional: filter by start_date (>=) - polling places only
            "end_date": "2024-12-31",    // optional: filter by end_date (<=) - polling places only
            "created_after": "2024-01-01", // optional: filter by created_at (>=)
            "created_before": "2024-12-31", // optional: filter by created_at (<=)
            "source_plugin": "ohio"   // optional: filter by source plugin
        },
        "dry_run": true,             // optional: if true, only return count without deleting
        "confirm": "DELETE"          // required: must be exactly "DELETE" to confirm
    }
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Request body required'}), 400
        
        delete_types = data.get('delete_types', [])
        filters = data.get('filters', {})
        dry_run = data.get('dry_run', False)
        confirm = data.get('confirm')
        
        # Validate delete_types
        if not delete_types:
            return jsonify({'error': 'delete_types is required and must be a non-empty list'}), 400
        
        valid_types = ['polling_places', 'precincts', 'assignments', 'elections']
        invalid_types = [t for t in delete_types if t not in valid_types]
        if invalid_types:
            return jsonify({'error': f'Invalid delete_types: {invalid_types}. Valid types are: {valid_types}'}), 400
        
        results = {}
        total_count = 0
        
        # Process each delete type
        for delete_type in delete_types:
            if delete_type == 'polling_places':
                # Build query for polling places
                query = PollingPlace.query
                
                # Apply filters
                if 'state' in filters and filters['state']:
                    query = query.filter(PollingPlace.state == filters['state'])
                
                if 'start_date' in filters and filters['start_date']:
                    try:
                        start_date = datetime.strptime(filters['start_date'], '%Y-%m-%d').date()
                        query = query.filter(PollingPlace.start_date >= start_date)
                    except ValueError:
                        return jsonify({'error': 'Invalid start_date format. Use YYYY-MM-DD'}), 400
                
                if 'end_date' in filters and filters['end_date']:
                    try:
                        end_date = datetime.strptime(filters['end_date'], '%Y-%m-%d').date()
                        query = query.filter(PollingPlace.end_date <= end_date)
                    except ValueError:
                        return jsonify({'error': 'Invalid end_date format. Use YYYY-MM-DD'}), 400
                
                if 'created_after' in filters and filters['created_after']:
                    try:
                        created_after = datetime.strptime(filters['created_after'], '%Y-%m-%d')
                        query = query.filter(PollingPlace.created_at >= created_after)
                    except ValueError:
                        return jsonify({'error': 'Invalid created_after format. Use YYYY-MM-DD'}), 400
                
                if 'created_before' in filters and filters['created_before']:
                    try:
                        created_before = datetime.strptime(filters['created_before'], '%Y-%m-%d')
                        query = query.filter(PollingPlace.created_at <= created_before)
                    except ValueError:
                        return jsonify({'error': 'Invalid created_before format. Use YYYY-MM-DD'}), 400
                
                if 'source_plugin' in filters and filters['source_plugin']:
                    query = query.filter(PollingPlace.source_plugin == filters['source_plugin'])
                
                # Get count
                count = query.count()
                results['polling_places'] = {'count': count, 'query': query}
                total_count += count
                
            elif delete_type == 'precincts':
                # Build query for precincts
                query = Precinct.query
                
                # Apply filters (precincts have fewer filterable fields)
                if 'state' in filters and filters['state']:
                    query = query.filter(Precinct.state == filters['state'])
                
                if 'created_after' in filters and filters['created_after']:
                    try:
                        created_after = datetime.strptime(filters['created_after'], '%Y-%m-%d')
                        query = query.filter(Precinct.created_at >= created_after)
                    except ValueError:
                        return jsonify({'error': 'Invalid created_after format. Use YYYY-MM-DD'}), 400
                
                if 'created_before' in filters and filters['created_before']:
                    try:
                        created_before = datetime.strptime(filters['created_before'], '%Y-%m-%d')
                        query = query.filter(Precinct.created_at <= created_before)
                    except ValueError:
                        return jsonify({'error': 'Invalid created_before format. Use YYYY-MM-DD'}), 400
                
                if 'source_plugin' in filters and filters['source_plugin']:
                    query = query.filter(Precinct.source_plugin == filters['source_plugin'])
                
                # Get count
                count = query.count()
                results['precincts'] = {'count': count, 'query': query}
                total_count += count
                
            elif delete_type == 'assignments':
                # Build query for precinct assignments
                query = PrecinctAssignment.query
                
                # Apply filters
                if 'state' in filters and filters['state']:
                    # Filter by state through precinct relationship
                    query = query.join(Precinct).filter(Precinct.state == filters['state'])
                
                if 'created_after' in filters and filters['created_after']:
                    try:
                        created_after = datetime.strptime(filters['created_after'], '%Y-%m-%d')
                        query = query.filter(PrecinctAssignment.created_at >= created_after)
                    except ValueError:
                        return jsonify({'error': 'Invalid created_after format. Use YYYY-MM-DD'}), 400
                
                if 'created_before' in filters and filters['created_before']:
                    try:
                        created_before = datetime.strptime(filters['created_before'], '%Y-%m-%d')
                        query = query.filter(PrecinctAssignment.created_at <= created_before)
                    except ValueError:
                        return jsonify({'error': 'Invalid created_before format. Use YYYY-MM-DD'}), 400
                
                # Get count
                count = query.count()
                results['assignments'] = {'count': count, 'query': query}
                total_count += count
                
            elif delete_type == 'elections':
                # Build query for elections
                query = Election.query
                
                # Apply filters
                if 'state' in filters and filters['state']:
                    query = query.filter(Election.state == filters['state'])
                
                if 'created_after' in filters and filters['created_after']:
                    try:
                        created_after = datetime.strptime(filters['created_after'], '%Y-%m-%d')
                        query = query.filter(Election.created_at >= created_after)
                    except ValueError:
                        return jsonify({'error': 'Invalid created_after format. Use YYYY-MM-DD'}), 400
                
                if 'created_before' in filters and filters['created_before']:
                    try:
                        created_before = datetime.strptime(filters['created_before'], '%Y-%m-%d')
                        query = query.filter(Election.created_at <= created_before)
                    except ValueError:
                        return jsonify({'error': 'Invalid created_before format. Use YYYY-MM-DD'}), 400
                
                # Get count
                count = query.count()
                results['elections'] = {'count': count, 'query': query}
                total_count += count
        
        if total_count == 0:
            return jsonify({
                'message': 'No records match the specified filters',
                'total_count': 0,
                'results': {k: {'count': v['count']} for k, v in results.items()},
                'dry_run': dry_run
            }), 200
        
        # Safety check: require explicit confirmation for actual deletion
        if not dry_run:
            if confirm != 'DELETE':
                return jsonify({
                    'error': 'Confirmation required. Set "confirm": "DELETE" to proceed with deletion',
                    'total_count': total_count,
                    'results': {k: {'count': v['count']} for k, v in results.items()},
                    'dry_run': False
                }), 400
        
        # Perform deletion or dry run
        if dry_run:
            return jsonify({
                'message': 'Dry run completed. No records were deleted.',
                'total_count': total_count,
                'results': {k: {'count': v['count']} for k, v in results.items()},
                'dry_run': True,
                'filters': filters,
                'delete_types': delete_types
            }), 200
        else:
            # Perform actual deletions
            deleted_counts = {}
            total_deleted = 0
            
            for delete_type, result in results.items():
                query = result['query']
                count = result['count']
                
                if count > 0:
                    # Get IDs for logging
                    if delete_type == 'polling_places':
                        record_ids = [pp.id for pp in query.all()]
                        entity_name = 'polling places'
                    elif delete_type == 'precincts':
                        record_ids = [p.id for p in query.all()]
                        entity_name = 'precincts'
                    elif delete_type == 'assignments':
                        record_ids = [a.id for a in query.all()]
                        entity_name = 'precinct assignments'
                    elif delete_type == 'elections':
                        record_ids = [e.id for e in query.all()]
                        entity_name = 'elections'
                    
                    # Perform deletion
                    deleted_count = query.delete()
                    deleted_counts[delete_type] = deleted_count
                    total_deleted += deleted_count
                    
                    # Log the deletion
                    app.logger.warning(f"Bulk delete performed by API key: {deleted_count} {entity_name} deleted. IDs: {record_ids[:10]}{'...' if len(record_ids) > 10 else ''}")
            
            db.session.commit()
            
            # Build success message
            messages = []
            if 'polling_places' in deleted_counts:
                messages.append(f"{deleted_counts['polling_places']} polling places")
            if 'precincts' in deleted_counts:
                messages.append(f"{deleted_counts['precincts']} precincts")
            if 'assignments' in deleted_counts:
                messages.append(f"{deleted_counts['assignments']} precinct assignments")
            if 'elections' in deleted_counts:
                messages.append(f"{deleted_counts['elections']} elections")
            
            message = f'Successfully deleted {", ".join(messages)}'
            
            return jsonify({
                'message': message,
                'total_count': total_deleted,
                'results': deleted_counts,
                'dry_run': False,
                'filters': filters,
                'delete_types': delete_types
            }), 200
    
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Error in bulk delete: {str(e)}")
        return jsonify({'error': str(e)}), 500


# Admin Web Interface Routes
@app.route('/admin')
@app.route('/admin/')
def admin_redirect():
    """Redirect /admin to /admin/login or /admin/dashboard"""
    if current_user.is_authenticated:
        return redirect(url_for('admin_dashboard'))
    return redirect(url_for('admin_login'))


@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    """Admin login page"""
    if current_user.is_authenticated:
        return redirect(url_for('admin_dashboard'))

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        user = AdminUser.query.filter_by(username=username).first()

        if user and user.check_password(password):
            login_user(user)
            user.last_login_at = datetime.utcnow()
            db.session.commit()
            flash('Login successful!', 'success')
            return redirect(url_for('admin_dashboard'))
        else:
            flash('Invalid username or password', 'error')

    return render_template('admin/login.html')


@app.route('/admin/logout')
@login_required
def admin_logout():
    """Admin logout"""
    logout_user()
    flash('You have been logged out', 'info')
    return redirect(url_for('admin_login'))


@app.route('/admin/dashboard')
@login_required
def admin_dashboard():
    """Admin dashboard - manage API keys and show record statistics"""
    # Get API keys
    api_keys = APIKey.query.order_by(APIKey.created_at.desc()).all()
    
    # Get record statistics
    from sqlalchemy import text
    
    try:
        # Get counts for each model (excluding dummy data)
        polling_places_count = PollingPlace.query.filter(PollingPlace.source_plugin != 'dummy').count()
        precincts_count = Precinct.query.filter(Precinct.source_plugin != 'dummy').count()
        elections_count = Election.query.count()
        assignments_count = PrecinctAssignment.query.count()
        
        # Get additional statistics
        active_api_keys = APIKey.query.filter_by(is_active=True).count()
        precincts_with_polling_places = Precinct.query.filter(
            Precinct.current_polling_place_id.isnot(None),
            Precinct.source_plugin != 'dummy'
        ).count()
        recent_elections = Election.query.filter(Election.date >= datetime.now().date()).count()
        
        # Get recent activity from audit trail
        recent_activity = []
        try:
            from models import AuditTrail
            recent_audit = AuditTrail.query.order_by(AuditTrail.timestamp.desc()).limit(10).all()
            for activity in recent_audit:
                recent_activity.append({
                    'table_name': activity.table_name,
                    'action': activity.action,
                    'record_id': activity.record_id,
                    'timestamp': activity.timestamp,
                    'username': activity.user.username if activity.user else 'System'
                })
        except:
            recent_activity = []
        
        # Get recently edited records (based on updated_at, excluding dummy data)
        recent_polling_places = PollingPlace.query.filter(
            PollingPlace.source_plugin != 'dummy'
        ).order_by(PollingPlace.updated_at.desc()).limit(5).all()
        recent_precincts = Precinct.query.filter(
            Precinct.source_plugin != 'dummy'
        ).order_by(Precinct.updated_at.desc()).limit(5).all()
        
        # Get state distribution (excluding dummy data)
        states_data = db.session.execute(text("""
            SELECT state, COUNT(*) as count 
            FROM polling_places 
            WHERE state IS NOT NULL AND source_plugin != 'dummy'
            GROUP BY state 
            ORDER BY count DESC 
            LIMIT 10
        """)).fetchall()
        
        # Get county distribution (top 10, excluding dummy data)
        counties_data = db.session.execute(text("""
            SELECT county, COUNT(*) as count 
            FROM polling_places 
            WHERE county IS NOT NULL AND source_plugin != 'dummy'
            GROUP BY county 
            ORDER BY count DESC 
            LIMIT 10
        """)).fetchall()
        
    except Exception as e:
        # Fallback values if database queries fail
        polling_places_count = 0
        precincts_count = 0
        elections_count = 0
        assignments_count = 0
        active_api_keys = 0
        precincts_with_polling_places = 0
        recent_elections = 0
        recent_activity = []
        recent_polling_places = []
        recent_precincts = []
        states_data = []
        counties_data = []
    
    return render_template('admin/dashboard.html', 
                         api_keys=api_keys,
                         polling_places_count=polling_places_count,
                         precincts_count=precincts_count,
                         elections_count=elections_count,
                         assignments_count=assignments_count,
                         active_api_keys=active_api_keys,
                         precincts_with_polling_places=precincts_with_polling_places,
                         recent_elections=recent_elections,
                         recent_activity=recent_activity,
                         recent_polling_places=recent_polling_places,
                         recent_precincts=recent_precincts,
                         states_data=states_data,
                         counties_data=counties_data)


@app.route('/admin/bulk-delete-pollingplaces')
@login_required
def admin_bulk_delete_records():
    """Bulk delete records interface"""
    return render_template('admin/bulk_delete_pollingplaces.html')


@app.route('/admin/keys/create', methods=['POST'])
@login_required
def admin_create_key():
    """Create a new API key from admin interface"""
    name = request.form.get('name')
    rate_limit_per_day = request.form.get('rate_limit_per_day')
    rate_limit_per_hour = request.form.get('rate_limit_per_hour')

    if not name:
        flash('API key name is required', 'error')
        return redirect(url_for('admin_dashboard'))

    new_key = APIKey(
        key=APIKey.generate_key(),
        name=name,
        rate_limit_per_day=int(rate_limit_per_day) if rate_limit_per_day else None,
        rate_limit_per_hour=int(rate_limit_per_hour) if rate_limit_per_hour else None
    )

    db.session.add(new_key)
    db.session.commit()

    flash(f'API key created successfully: {new_key.key}', 'success')
    return redirect(url_for('admin_dashboard'))


@app.route('/admin/keys/<int:key_id>/revoke', methods=['POST'])
@login_required
def admin_revoke_key(key_id):
    """Revoke an API key from admin interface"""
    key = APIKey.query.get_or_404(key_id)
    key.is_active = False
    db.session.commit()

    flash(f'API key "{key.name}" has been revoked', 'success')
    return redirect(url_for('admin_dashboard'))


@app.route('/admin/keys/<int:key_id>/activate', methods=['POST'])
@login_required
def admin_activate_key(key_id):
    """Reactivate an API key from admin interface"""
    key = APIKey.query.get_or_404(key_id)
    key.is_active = True
    db.session.commit()

    flash(f'API key "{key.name}" has been activated', 'success')
    return redirect(url_for('admin_dashboard'))


@app.route('/admin/change-password', methods=['GET', 'POST'])
@login_required
def admin_change_password():
    """Change admin password"""
    if request.method == 'POST':
        current_password = request.form.get('current_password')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')

        if not current_user.check_password(current_password):
            flash('Current password is incorrect', 'error')
        elif new_password != confirm_password:
            flash('New passwords do not match', 'error')
        elif len(new_password) < 8:
            flash('New password must be at least 8 characters', 'error')
        else:
            current_user.set_password(new_password)
            db.session.commit()
            flash('Password changed successfully', 'success')
            return redirect(url_for('admin_dashboard'))

    return render_template('admin/change_password.html')


@app.route('/admin/plugins')
@login_required
def admin_plugins():
    """Admin page to manage plugins"""
    plugins = plugin_manager.list_plugins()
    uploadable_plugins = [p['name'] for p in plugins if hasattr(plugin_manager.get_plugin(p['name']), 'supports_file_upload') and plugin_manager.get_plugin(p['name']).supports_file_upload]
    return render_template('admin/plugins.html', plugins=plugins, uploadable_plugins=uploadable_plugins)


@app.route('/admin/plugins/<plugin_name>/sync', methods=['POST'])
@login_required
def admin_sync_plugin(plugin_name):
    """Trigger sync for a specific plugin"""
    try:
        result = plugin_manager.sync_plugin(plugin_name)
        flash(f'Sync completed for {plugin_name}: {result["message"]}', 'success')
    except Exception as e:
        flash(f'Error syncing {plugin_name}: {str(e)}', 'error')
    return redirect(url_for('admin_plugins'))


@app.route('/admin/plugins/sync-all', methods=['POST'])
@login_required
def admin_sync_all_plugins():
    """Trigger sync for all plugins"""
    try:
        results = plugin_manager.sync_all_plugins()
        flash(f'Sync completed for all non-dummy plugins: {len(results)} processed', 'success')
    except Exception as e:
        flash(f'Error syncing all plugins: {str(e)}', 'error')
    return redirect(url_for('admin_plugins'))


@app.route('/admin/plugins/config', methods=['GET', 'POST'])
@login_required
def admin_plugins_config():
    """Configure plugin sync settings"""
    if request.method == 'POST':
        auto_sync_enabled = request.form.get('auto_sync_enabled') == 'on'
        sync_interval_hours = request.form.get('sync_interval_hours', 24)

        # Update environment variables (note: this won't persist across restarts without .env update)
        os.environ['AUTO_SYNC_ENABLED'] = str(auto_sync_enabled)
        os.environ['SYNC_INTERVAL_HOURS'] = str(sync_interval_hours)

        # Restart scheduler if needed
        if auto_sync_enabled:
            scheduler.add_job(
                func=sync_all_plugins_job,
                trigger='interval',
                hours=int(sync_interval_hours),
                id='sync_all_plugins',
                name='Sync all state plugins',
                replace_existing=True
            )
        else:
            scheduler.remove_job('sync_all_plugins')

        flash('Plugin sync configuration updated', 'success')
        return redirect(url_for('admin_plugins_config'))

    # Get current settings
    auto_sync_enabled = os.getenv('AUTO_SYNC_ENABLED', 'False').lower() == 'true'
    sync_interval_hours = int(os.getenv('SYNC_INTERVAL_HOURS', '24'))

    return render_template('admin/plugins_config.html',
                         auto_sync_enabled=auto_sync_enabled,
                         sync_interval_hours=sync_interval_hours)




@app.route('/admin/plugins/<plugin_name>/upload', methods=['GET', 'POST'])
@login_required
def admin_upload_plugin_file(plugin_name):
    """Upload file for a plugin that supports it"""
    try:
        plugin = plugin_manager.get_plugin(plugin_name)
        if not hasattr(plugin, 'supports_file_upload') or not plugin.supports_file_upload:
            flash(f'Plugin {plugin_name} does not support file uploads', 'error')
            return redirect(url_for('admin_plugins'))

        if request.method == 'POST':
            if 'file' not in request.files:
                flash('No file part', 'error')
                return redirect(request.url)

            file = request.files['file']
            if file.filename == '':
                flash('No selected file', 'error')
                return redirect(request.url)

            if file and file.filename.endswith('.csv'):
                # Save file temporarily
                temp_path = os.path.join('/tmp', f'{plugin_name}_{file.filename}')
                file.save(temp_path)

                # Call plugin's upload method
                result = plugin.upload_file(temp_path)

                # Clean up temp file
                os.remove(temp_path)

                if result['success']:
                    flash(result['message'], 'success')
                else:
                    flash(result['message'], 'error')
            else:
                flash('Only CSV files are allowed', 'error')

            return redirect(url_for('admin_plugins'))

        return render_template('admin/plugin_upload.html', plugin=plugin)
    except Exception as e:
        flash(f'Error uploading file: {str(e)}', 'error')
        return redirect(url_for('admin_plugins'))


@app.route('/docs/plugins/<plugin_name>_<doc_type>.md')
@login_required
def plugin_docs(plugin_name, doc_type):
    """Serve plugin documentation files"""
    if doc_type not in ['user', 'technical']:
        flash('Invalid documentation type', 'error')
        return redirect(url_for('admin_plugins'))

    doc_path = os.path.join('docs', 'plugins', f'{plugin_name}_{doc_type}.md')
    if not os.path.exists(doc_path):
        flash(f'Documentation not found for {plugin_name}', 'error')
        return redirect(url_for('admin_plugins'))

    with open(doc_path, 'r') as f:
        content = f.read()

    return render_template('admin/plugin_docs.html', plugin_name=plugin_name, doc_type=doc_type, content=content)


@app.route('/admin/virginia-sync')
@login_required
def admin_virginia_sync():
    """Virginia plugin sync interface"""
    try:
        # Get Virginia plugin instance
        virginia_plugin = plugin_manager.get_plugin('virginia')
        if not virginia_plugin:
            flash('Virginia plugin not found', 'error')
            return redirect(url_for('admin_plugins'))
        
        # Get available elections
        elections = virginia_plugin.get_available_elections()
        
        return render_template('admin/virginia_sync.html', elections=elections)
        
    except Exception as e:
        flash(f'Error loading Virginia sync interface: {str(e)}', 'error')
        return redirect(url_for('admin_plugins'))


@app.route('/admin/virginia-sync', methods=['POST'])
@login_required
def admin_virginia_sync_post():
    """Handle Virginia plugin sync requests"""
    try:
        # Get Virginia plugin instance
        virginia_plugin = plugin_manager.get_plugin('virginia')
        if not virginia_plugin:
            return jsonify({'success': False, 'error': 'Virginia plugin not found'}), 404
        
        # Parse form data
        selected_files = request.form.getlist('selected_files')
        custom_dates = request.form.getlist('custom_dates')
        
        if not selected_files:
            return jsonify({'success': False, 'error': 'No files selected'}), 400
        
        # Validate custom dates
        date_mapping = {}
        for i, file_url in enumerate(selected_files):
            custom_date = custom_dates[i] if i < len(custom_dates) else ''
            if custom_date:
                try:
                    # Validate date format
                    datetime.strptime(custom_date, '%Y-%m-%d')
                    date_mapping[file_url] = custom_date
                except ValueError:
                    return jsonify({'success': False, 'error': f'Invalid date format for {file_url}: {custom_date}'}), 400
        
        # Record sync start time
        sync_start_time = datetime.utcnow()
        
        # Process each selected file
        results = []
        total_pp_added = total_pp_updated = total_p_added = total_p_updated = 0
        
        for file_url in selected_files:
            try:
                # Get election info for this file
                elections = virginia_plugin.get_available_elections()
                election_info = next((e for e in elections if e['url'] == file_url), None)
                
                if not election_info:
                    results.append({
                        'file_url': file_url,
                        'success': False,
                        'error': 'Election info not found'
                    })
                    continue
                
                # Use custom date if provided, otherwise use detected date
                election_date = date_mapping.get(file_url, election_info['election_date'])
                
                # Create election record if needed
                from models import Election
                election = Election.query.filter_by(
                    date=datetime.strptime(election_date, '%Y-%m-%d').date(),
                    state='VA'
                ).first()
                
                if not election:
                    election = Election(
                        date=datetime.strptime(election_date, '%Y-%m-%d').date(),
                        name=election_info['election_name'],
                        state='VA'
                    )
                    db.session.add(election)
                    db.session.commit()
                
                # Sync polling places for this file
                polling_places = virginia_plugin.fetch_polling_places(file_url)
                sync_result = virginia_plugin.sync()
                
                # Sync precincts with election date
                precincts = virginia_plugin.fetch_precincts(file_url)
                precinct_result = virginia_plugin.sync_precincts(
                    effective_date=datetime.strptime(election_date, '%Y-%m-%d').date(),
                    election_id=election.id
                )
                
                # Aggregate statistics
                total_pp_added += sync_result['polling_places']['added']
                total_pp_updated += sync_result['polling_places']['updated']
                total_p_added += precinct_result['added']
                total_p_updated += precinct_result['updated']
                
                results.append({
                    'file_url': file_url,
                    'election_name': election_info['election_name'],
                    'success': True,
                    'polling_places': sync_result['polling_places'],
                    'precincts': precinct_result
                })
                
            except Exception as e:
                results.append({
                    'file_url': file_url,
                    'success': False,
                    'error': str(e)
                })
        
        # Calculate duration
        sync_end_time = datetime.utcnow()
        duration = sync_end_time - sync_start_time
        duration_str = str(duration).split('.')[0]  # Remove microseconds
        
        # Store sync history
        try:
            from models import AuditTrail
            audit_entry = AuditTrail(
                table_name='virginia_sync',
                record_id=f"sync_{sync_start_time.strftime('%Y%m%d_%H%M%S')}",
                action='CREATE',
                new_values=json.dumps({
                    'files_processed': len(selected_files),
                    'files_successful': len([r for r in results if r['success']]),
                    'files_failed': len([r for r in results if not r['success']]),
                    'polling_places_added': total_pp_added,
                    'polling_places_updated': total_pp_updated,
                    'precincts_added': total_p_added,
                    'precincts_updated': total_p_updated,
                    'duration': duration_str,
                    'success': len([r for r in results if r['success']]) == len(selected_files)
                }),
                user_id=current_user.id if current_user.is_authenticated else None,
                ip_address=request.remote_addr,
                user_agent=request.headers.get('User-Agent', '')
            )
            db.session.add(audit_entry)
            db.session.commit()
        except Exception as e:
            app.logger.warning(f"Failed to store sync history: {e}")
        
        return jsonify({'success': True, 'results': results})
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/admin/api/virginia-sync-history')
@login_required
def admin_api_virginia_sync_history():
    """Get Virginia sync history from audit trail"""
    try:
        from models import AuditTrail
        
        # Get recent Virginia sync operations from audit trail
        history = db.session.query(AuditTrail).filter(
            AuditTrail.table_name == 'virginia_sync',
            AuditTrail.action == 'CREATE'
        ).order_by(AuditTrail.timestamp.desc()).limit(20).all()
        
        history_data = []
        for entry in history:
            try:
                if entry.new_values:
                    data = json.loads(entry.new_values)
                    history_data.append({
                        'timestamp': entry.timestamp.isoformat() if entry.timestamp else None,
                        'files_processed': data.get('files_processed', 0),
                        'files_successful': data.get('files_successful', 0),
                        'files_failed': data.get('files_failed', 0),
                        'polling_places_added': data.get('polling_places_added', 0),
                        'polling_places_updated': data.get('polling_places_updated', 0),
                        'precincts_added': data.get('precincts_added', 0),
                        'precincts_updated': data.get('precincts_updated', 0),
                        'duration': data.get('duration', 'N/A'),
                        'success': data.get('success', False),
                        'username': entry.get_username()
                    })
            except Exception as e:
                app.logger.warning(f"Error parsing audit entry: {e}")
                continue
        
        return jsonify({'history': history_data})
        
    except Exception as e:
        app.logger.error(f"Error fetching sync history: {e}")
        return jsonify({'error': str(e), 'history': []})


@app.route('/admin/logs')
@login_required
def admin_logs():
    """View application logs"""
    try:
        with open(log_file, 'r') as f:
            lines = f.readlines()
        # Show last 100 lines
        content = ''.join(lines[-100:])
    except Exception as e:
        content = f"Error reading log file: {str(e)}"

    return render_template('admin/logs.html', content=content)


@app.route('/admin/geocoding_config', methods=['GET', 'POST'])
@login_required
def admin_geocoding_config():
    """Configure geocoding priority"""
    global config
    if request.method == 'POST':
        priority = request.form.get('geocoder_priority', '').split(',')
        priority = [p.strip() for p in priority if p.strip()]
        config['geocoder_priority'] = priority
        app.config['geocoder_priority'] = priority
        # Save to file
        with open(config_file, 'w') as f:
            json.dump(config, f, indent=4)
        flash('Geocoding configuration updated', 'success')
        return redirect(url_for('admin_geocoding_config'))

    return render_template('admin/geocoding_config.html', priority=','.join(config['geocoder_priority']))


@app.route('/admin/api/recent-activity')
@login_required
def admin_api_recent_activity():
    """API endpoint for recent activity sidebar"""
    try:
        from models import AuditTrail
        recent_audit = AuditTrail.query.order_by(AuditTrail.timestamp.desc()).limit(8).all()
        
        activity = []
        for audit in recent_audit:
            activity.append({
                'table_name': audit.table_name,
                'action': audit.action,
                'record_id': audit.record_id,
                'timestamp': audit.timestamp.isoformat() if audit.timestamp else None,
                'username': audit.user.username if audit.user else 'System'
            })
        
        return jsonify({'activity': activity})
    except Exception as e:
        return jsonify({'error': str(e), 'activity': []})


@app.route('/admin/map')
@login_required
def admin_map():
    """Map page showing polling places filterable by county"""
    return render_template('admin/map_optimized.html')


@app.route('/admin/api/polling-places-map')
@login_required
def admin_api_polling_places_map():
    """API endpoint for polling places data for the map"""
    try:
        # Get query parameters
        state_filter = request.args.get('state')
        county_filter = request.args.get('county')
        dataset = request.args.get('dataset', '').lower()
        
        # Default to showing all states if none specified
        query = PollingPlace.query.filter(
            PollingPlace.latitude.isnot(None),
            PollingPlace.longitude.isnot(None)
        )
        
        # Filter by state if provided
        if state_filter:
            query = query.filter_by(state=state_filter.upper())
        
        # Filter by county if provided
        if county_filter:
            query = query.filter_by(county=county_filter)
        
        # Filter by dataset if provided
        if dataset == 'dummy':
            query = query.filter_by(source_plugin='dummy')
        else:
            # Exclude dummy data by default
            query = query.filter(PollingPlace.source_plugin != 'dummy')
        
        polling_places = query.all()
        
        # Convert to GeoJSON format
        features = []
        for pp in polling_places:
            if pp.latitude and pp.longitude:
                features.append({
                    "type": "Feature",
                    "geometry": {
                        "type": "Point",
                        "coordinates": [pp.longitude, pp.latitude]
                    },
                    "properties": {
                        "id": pp.id,
                        "name": pp.name,
                        "address": f"{pp.address_line1 or ''}, {pp.city or ''}, {pp.state or ''} {pp.zip_code or ''}".strip(', '),
                        "county": pp.county,
                        "city": pp.city,
                        "state": pp.state,
                        "zip_code": pp.zip_code,
                        "polling_hours": pp.polling_hours,
                        "notes": pp.notes,
                        "voter_services": pp.voter_services
                    }
                })
        
        return jsonify({
            "type": "FeatureCollection",
            "features": features
        })
    except Exception as e:
        return jsonify({'error': str(e), "type": "FeatureCollection", "features": []})


@app.route('/admin/api/counties')
@login_required
def admin_api_counties():
    """API endpoint to get list of counties for filtering"""
    try:
        state_filter = request.args.get('state')
        dataset = request.args.get('dataset', '').lower()
        
        query = db.session.query(PollingPlace.county).filter(
            PollingPlace.county.isnot(None),
            PollingPlace.county != ''
        )
        
        # Filter by state if provided
        if state_filter:
            query = query.filter_by(state=state_filter.upper())
        
        # Filter by dataset if provided
        if dataset == 'dummy':
            query = query.filter_by(source_plugin='dummy')
        else:
            # Exclude dummy data by default
            query = query.filter(PollingPlace.source_plugin != 'dummy')
        
        counties = query.distinct().order_by(PollingPlace.county).all()
        
        return jsonify({
            'counties': [county[0] for county in counties if county[0]]
        })
    except Exception as e:
        return jsonify({'error': str(e), 'counties': []})





@app.route('/admin/docs')
@app.route('/admin/docs/<path:doc_path>')
@login_required
def admin_docs(doc_path=None):
    """Documentation viewer for admin interface"""
    import os
    import markdown
    from flask import send_from_directory
    
    # Define available documentation
    docs = {
        'main': {
            'title': 'Main Documentation',
            'file': 'README.md',
            'description': 'Project overview and setup guide'
        },
        'development': {
            'title': 'Development Guide', 
            'file': 'DEVELOPMENT.md',
            'description': 'Development setup and guidelines'
        },
        'ui': {
            'title': 'UI Documentation',
            'file': 'docs/UI_DOCUMENTATION.md',
            'description': 'Admin interface documentation'
        },
        'plugins': {
            'title': 'Plugin Guide',
            'file': 'plugins/README.md',
            'description': 'Plugin development guide'
        },
        'virginia-user': {
            'title': 'Virginia Plugin - User Guide',
            'file': 'docs/plugins/virginia_user.md',
            'description': 'Virginia plugin user documentation'
        },
        'virginia-technical': {
            'title': 'Virginia Plugin - Technical',
            'file': 'docs/plugins/virginia_technical.md',
            'description': 'Virginia plugin technical details'
        },
        'ohio-user': {
            'title': 'Ohio Plugin - User Guide',
            'file': 'docs/plugins/ohio_user.md',
            'description': 'Ohio plugin user documentation'
        },
        'ohio-technical': {
            'title': 'Ohio Plugin - Technical',
            'file': 'docs/plugins/ohio_technical.md',
            'description': 'Ohio plugin technical details'
        },
        'bigquery-user': {
            'title': 'BigQuery Plugin - User Guide',
            'file': 'docs/plugins/bigquery_user.md',
            'description': 'BigQuery plugin user documentation'
        },
        'bigquery-technical': {
            'title': 'BigQuery Plugin - Technical',
            'file': 'docs/plugins/bigquery_technical.md',
            'description': 'BigQuery plugin technical details'
        },
        'dummy-user': {
            'title': 'Dummy Plugin - User Guide',
            'file': 'docs/plugins/dummy_user.md',
            'description': 'Dummy plugin user documentation'
        },
        'dummy-technical': {
            'title': 'Dummy Plugin - Technical',
            'file': 'docs/plugins/dummy_technical.md',
            'description': 'Dummy plugin technical details'
        }
    }
    
    # If no specific doc requested, show index
    if not doc_path:
        return render_template('admin/docs.html', docs=docs, current_doc=None)
    
    # Find the requested document
    doc_key = doc_path
    if doc_key not in docs:
        # Try to find by partial match
        for key in docs:
            if doc_path in key or key in doc_path:
                doc_key = key
                break
        else:
            return render_template('admin/docs.html', docs=docs, current_doc=None, 
                                 error=f"Documentation '{doc_path}' not found")
    
    doc_info = docs[doc_key]
    doc_file = doc_info['file']
    
    # Read the documentation file
    try:
        file_path = os.path.join(os.path.dirname(__file__), doc_file)
        if not os.path.exists(file_path):
            return render_template('admin/docs.html', docs=docs, current_doc=None,
                                 error=f"Documentation file '{doc_file}' not found")
        
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Convert markdown to HTML
        html_content = markdown.markdown(content, extensions=[
            'markdown.extensions.codehilite',
            'markdown.extensions.tables',
            'markdown.extensions.toc',
            'markdown.extensions.fenced_code'
        ])
        
        return render_template('admin/docs.html', 
                             docs=docs, 
                             current_doc=doc_key,
                             doc_title=doc_info['title'],
                             doc_description=doc_info['description'],
                             doc_content=html_content)
    
    except Exception as e:
        app.logger.error(f"Error loading documentation {doc_file}: {str(e)}")
        return render_template('admin/docs.html', docs=docs, current_doc=None,
                             error=f"Error loading documentation: {str(e)}")


@app.route('/admin/geocoding-api-config', methods=['GET', 'POST'])
@login_required
def admin_geocoding_api_config():
    """Configure geocoding API keys"""
    if request.method == 'POST':
        google_key = request.form.get('google_geocoding_api_key')
        mapbox_token = request.form.get('mapbox_access_token')

        # Update .env file
        env_path = os.path.join(os.path.dirname(__file__), '.env')
        with open(env_path, 'r') as f:
            lines = f.readlines()

        # Update or add lines
        updated_lines = []
        google_updated = False
        mapbox_updated = False
        for line in lines:
            if line.startswith('GOOGLE_GEOCODING_API_KEY='):
                updated_lines.append(f'GOOGLE_GEOCODING_API_KEY={google_key}\n')
                google_updated = True
            elif line.startswith('MAPBOX_ACCESS_TOKEN='):
                updated_lines.append(f'MAPBOX_ACCESS_TOKEN={mapbox_token}\n')
                mapbox_updated = True
            else:
                updated_lines.append(line)

        if not google_updated:
            updated_lines.append(f'GOOGLE_GEOCODING_API_KEY={google_key}\n')
        if not mapbox_updated:
            updated_lines.append(f'MAPBOX_ACCESS_TOKEN={mapbox_token}\n')

        with open(env_path, 'w') as f:
            f.writelines(updated_lines)

        # Update os.environ
        os.environ['GOOGLE_GEOCODING_API_KEY'] = google_key
        os.environ['MAPBOX_ACCESS_TOKEN'] = mapbox_token

        flash('Geocoding API keys updated', 'success')
        return redirect(url_for('admin_geocoding_api_config'))

    # Get current settings
    google_key = os.getenv('GOOGLE_GEOCODING_API_KEY', '')
    mapbox_token = os.getenv('MAPBOX_ACCESS_TOKEN', '')

    return render_template('admin/geocoding_api_config.html',
                          google_key=google_key,
                          mapbox_token=mapbox_token)

# Geocoding progress tracking
geocoding_jobs = {}

@app.route('/admin/api/geocode-start', methods=['POST'])
@login_required
def admin_api_geocode_start():
    """Start geocoding with progress tracking"""
    try:
        data = request.get_json()
        plugin_name = data.get('plugin', 'virginia')
        polling_place_ids = data.get('polling_place_ids', [])
        
        if not polling_place_ids:
            return jsonify({'success': False, 'error': 'No polling places specified'}), 400
        
        # Generate unique job ID
        job_id = secrets.token_hex(8)
        
        # Get plugin instance
        plugin = plugin_manager.get_plugin(plugin_name)
        if not plugin:
            return jsonify({'success': False, 'error': f'Plugin {plugin_name} not found'}), 404
        
        # Get polling places from database
        from models import PollingPlace
        polling_places = PollingPlace.query.filter(
            PollingPlace.id.in_(polling_place_ids)
        ).all()
        
        if not polling_places:
            return jsonify({'success': False, 'error': 'No polling places found'}), 404
        
        # Convert to list of dictionaries for geocoding
        polling_places_data = []
        for pp in polling_places:
            polling_places_data.append({
                'id': pp.id,
                'address_line1': pp.address_line1,
                'city': pp.city,
                'zip_code': pp.zip_code,
                'latitude': pp.latitude,
                'longitude': pp.longitude
            })
        
        # Initialize job state
        geocoding_jobs[job_id] = {
            'status': 'running',
            'progress': 0,
            'message': 'Starting geocoding...',
            'start_time': time.time(),
            'cancelled': False,
            'total_places': len(polling_places_data),
            'processed_places': 0,
            'current_phase': 'initializing',
            'results': {
                'geocoded': 0,
                'failed': 0,
                'skipped': 0
            }
        }
        
        # Start geocoding in background thread
        def geocode_worker():
            try:
                # Progress callback function
                def progress_callback(progress_data):
                    if job_id not in geocoding_jobs:
                        return
                    
                    job = geocoding_jobs[job_id]
                    if job['cancelled']:
                        return
                    
                    # Update job state with progress data
                    job['current_phase'] = progress_data.get('phase', 'unknown')
                    job['message'] = progress_data.get('message', 'Processing...')
                    
                    if 'geocoder_progress' in progress_data:
                        job['progress'] = progress_data['geocoder_progress']
                    
                    if 'current_address' in progress_data and 'total_addresses' in progress_data:
                        job['processed_places'] = progress_data['current_address']
                        job['total_places'] = progress_data['total_addresses']
                
                # Cancel check function
                def cancel_check():
                    return job_id not in geocoding_jobs or geocoding_jobs[job_id]['cancelled']
                
                # Perform geocoding with progress tracking
                plugin._geocode_addresses(
                    polling_places_data,
                    progress_callback=progress_callback,
                    cancel_check=cancel_check
                )
                
                # Update database with geocoded results
                geocoded_count = 0
                failed_count = 0
                skipped_count = 0
                
                for pp_data in polling_places_data:
                    pp = next((p for p in polling_places if p.id == pp_data['id']), None)
                    if pp:
                        if 'latitude' in pp_data and 'longitude' in pp_data:
                            pp.latitude = pp_data['latitude']
                            pp.longitude = pp_data['longitude']
                            geocoded_count += 1
                        elif pp.latitude and pp.longitude:
                            skipped_count += 1  # Already had coordinates
                        else:
                            failed_count += 1
                
                # Commit changes to database
                db.session.commit()
                
                # Update final job state
                if job_id in geocoding_jobs:
                    job = geocoding_jobs[job_id]
                    if not job['cancelled']:
                        job['status'] = 'completed'
                        job['progress'] = 100
                        job['message'] = f'Geocoding completed: {geocoded_count} geocoded, {skipped_count} skipped, {failed_count} failed'
                        job['results'] = {
                            'geocoded': geocoded_count,
                            'failed': failed_count,
                            'skipped': skipped_count
                        }
                
            except Exception as e:
                app.logger.error(f"Geocoding job {job_id} failed: {str(e)}")
                if job_id in geocoding_jobs:
                    geocoding_jobs[job_id]['status'] = 'error'
                    geocoding_jobs[job_id]['message'] = f'Error: {str(e)}'
        
        # Start background thread
        thread = threading.Thread(target=geocode_worker)
        thread.daemon = True
        thread.start()
        
        return jsonify({
            'success': True,
            'job_id': job_id,
            'total_places': len(polling_places_data)
        })
        
    except Exception as e:
        app.logger.error(f"Error starting geocoding: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/admin/api/geocode-status/<job_id>')
@login_required
def admin_api_geocode_status(job_id):
    """Get geocoding job status"""
    if job_id not in geocoding_jobs:
        return jsonify({'success': False, 'error': 'Job not found'}), 404
    
    job = geocoding_jobs[job_id]
    
    # Calculate time tracking
    current_time = time.time()
    elapsed_time = current_time - job['start_time']
    
    response_data = {
        'success': True,
        'job_id': job_id,
        'status': job['status'],
        'progress': job['progress'],
        'message': job['message'],
        'current_phase': job['current_phase'],
        'elapsed_time': elapsed_time,
        'processed_places': job['processed_places'],
        'total_places': job['total_places'],
        'results': job['results']
    }
    
    # Estimate time remaining
    if job['status'] == 'running' and job['progress'] > 0:
        estimated_total_time = elapsed_time / (job['progress'] / 100)
        remaining_time = estimated_total_time - elapsed_time
        response_data['estimated_remaining_time'] = max(0, remaining_time)
    
    return jsonify(response_data)

@app.route('/admin/api/geocode-cancel/<job_id>', methods=['POST'])
@login_required
def admin_api_geocode_cancel(job_id):
    """Cancel geocoding job"""
    if job_id not in geocoding_jobs:
        return jsonify({'success': False, 'error': 'Job not found'}), 404
    
    job = geocoding_jobs[job_id]
    if job['status'] in ['completed', 'error']:
        return jsonify({'success': False, 'error': 'Job already finished'}), 400
    
    job['cancelled'] = True
    job['status'] = 'cancelled'
    job['message'] = 'Geocoding cancelled by user'
    
    return jsonify({
        'success': True,
        'message': 'Geocoding job cancelled'
    })

# Scheduling functions
def sync_all_plugins_job():
    """Background job to sync all plugins"""
    with app.app_context():
        app.logger.info("Running scheduled sync for all plugins")
        results = plugin_manager.sync_all_plugins()
        app.logger.info(f"Scheduled sync completed: {results}")


# Initialize scheduler after function is defined
scheduler.add_job(func=sync_all_plugins_job, trigger="interval", hours=24)


# Create tables and initialize
with app.app_context():
    db.create_all()

    # Initialize default admin user if none exists
    if AdminUser.query.count() == 0:
        default_password = os.getenv('DEFAULT_ADMIN_PASSWORD', 'admin123')
        admin = AdminUser(username='admin')
        admin.set_password(default_password)
        db.session.add(admin)
        db.session.commit()
        app.logger.warning(
            f"Created default admin user with username 'admin' and password '{default_password}'. "
            "Please change the password immediately at /admin/change-password"
        )

    # Initialize plugin manager after models are defined
    plugin_manager = PluginManager(app, db)
    
    # Initialize Flask-Admin after models are defined
    try:
        from admin_config import init_admin
        admin = init_admin(app, db)
    except ImportError as e:
        app.logger.warning(f"Flask-Admin not available: {e}")
        admin = None

    # Set up automated scheduling if enabled
    auto_sync_enabled = os.getenv('AUTO_SYNC_ENABLED', 'False').lower() == 'true'
    sync_interval_hours = int(os.getenv('SYNC_INTERVAL_HOURS', '24'))

    if auto_sync_enabled:
        scheduler.add_job(
            func=sync_all_plugins_job,
            trigger='interval',
            hours=sync_interval_hours,
            id='sync_all_plugins',
            name='Sync all state plugins',
            replace_existing=True
        )
        app.logger.info(
            f"Automated sync enabled: running every {sync_interval_hours} hours"
        )
    else:
        app.logger.info("Automated sync disabled")


if __name__ == '__main__':
    port = int(os.getenv('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=os.getenv('DEBUG', 'False') == 'True')
