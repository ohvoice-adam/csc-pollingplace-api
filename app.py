"""
CSC Polling Place API
Main application file

Provides centralized polling place location data in VIP (Voting Information Project) format
compatible with Google Civic Data API.
"""

import os
import secrets
from datetime import datetime
from functools import wraps
from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from dotenv import load_dotenv
from apscheduler.schedulers.background import BackgroundScheduler
from plugins.plugin_manager import PluginManager

# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__)

# Configuration
# Use SQLite database stored in /data directory (persistent in Docker volume)
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv(
    'DATABASE_URL',
    'sqlite:////data/pollingplaces.db'
)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['JSON_SORT_KEYS'] = False

# Initialize extensions
CORS(app)
db = SQLAlchemy(app)

# Initialize rate limiter
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://"
)

# Initialize scheduler
scheduler = BackgroundScheduler()
scheduler.start()

# Initialize plugin manager (will be done after models are defined)
plugin_manager = None


# Database models
class PollingPlace(db.Model):
    """
    Polling place model based on VIP (Voting Information Project) specification.
    Compatible with Google Civic Data API format.
    """
    __tablename__ = 'polling_places'

    # Primary identifier
    id = db.Column(db.String(255), primary_key=True)  # VIP uses string IDs

    # Location name and address fields (VIP structured address)
    name = db.Column(db.String(255), nullable=False)
    location_name = db.Column(db.String(255))  # Specific location name within address
    address_line1 = db.Column(db.String(255))
    address_line2 = db.Column(db.String(255))
    address_line3 = db.Column(db.String(255))
    city = db.Column(db.String(100), nullable=False)
    state = db.Column(db.String(2), nullable=False)
    zip_code = db.Column(db.String(10), nullable=False)

    # Coordinates (WGS 84 decimal degrees)
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)

    # VIP-specific fields
    polling_hours = db.Column(db.String(255))  # e.g., "7:00 AM - 8:00 PM"
    notes = db.Column(db.Text)  # Additional information, directions, etc.
    voter_services = db.Column(db.String(500))  # Services available at this location
    start_date = db.Column(db.Date)  # When this location becomes active
    end_date = db.Column(db.Date)  # When this location stops being active

    # Source tracking
    source_state = db.Column(db.String(2))  # Which state plugin provided this data
    source_plugin = db.Column(db.String(100))  # Which plugin provided this data

    # Metadata
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    updated_at = db.Column(db.DateTime, server_default=db.func.now(), onupdate=db.func.now())

    def to_dict(self):
        """Convert model to standard dictionary format"""
        return {
            'id': self.id,
            'name': self.name,
            'location_name': self.location_name,
            'address_line1': self.address_line1,
            'address_line2': self.address_line2,
            'address_line3': self.address_line3,
            'city': self.city,
            'state': self.state,
            'zip_code': self.zip_code,
            'latitude': self.latitude,
            'longitude': self.longitude,
            'polling_hours': self.polling_hours,
            'notes': self.notes,
            'voter_services': self.voter_services,
            'start_date': self.start_date.isoformat() if self.start_date else None,
            'end_date': self.end_date.isoformat() if self.end_date else None,
            'source_state': self.source_state,
            'source_plugin': self.source_plugin,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }

    def to_vip_format(self):
        """
        Convert model to VIP (Voting Information Project) format
        Compatible with Google Civic Data API
        """
        address = {
            'locationName': self.location_name,
            'line1': self.address_line1,
            'line2': self.address_line2,
            'line3': self.address_line3,
            'city': self.city,
            'state': self.state,
            'zip': self.zip_code
        }

        # Remove None values from address
        address = {k: v for k, v in address.items() if v is not None}

        vip_data = {
            'id': self.id,
            'name': self.name,
            'address': address,
            'pollingHours': self.polling_hours,
            'notes': self.notes,
        }

        # Add optional fields if present
        if self.latitude is not None and self.longitude is not None:
            vip_data['latitude'] = self.latitude
            vip_data['longitude'] = self.longitude

        if self.voter_services:
            vip_data['voterServices'] = self.voter_services

        if self.start_date:
            vip_data['startDate'] = self.start_date.isoformat()

        if self.end_date:
            vip_data['endDate'] = self.end_date.isoformat()

        # Remove None values
        return {k: v for k, v in vip_data.items() if v is not None}


class APIKey(db.Model):
    """
    API Key model for authentication
    """
    __tablename__ = 'api_keys'

    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(64), unique=True, nullable=False, index=True)
    name = db.Column(db.String(255), nullable=False)  # Description/owner of the key
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    last_used_at = db.Column(db.DateTime)

    # Rate limit overrides (optional, uses defaults if None)
    rate_limit_per_day = db.Column(db.Integer)
    rate_limit_per_hour = db.Column(db.Integer)

    @staticmethod
    def generate_key():
        """Generate a new API key"""
        return secrets.token_urlsafe(48)

    def to_dict(self):
        """Convert model to dictionary"""
        return {
            'id': self.id,
            'key': self.key,
            'name': self.name,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_used_at': self.last_used_at.isoformat() if self.last_used_at else None,
            'rate_limit_per_day': self.rate_limit_per_day,
            'rate_limit_per_hour': self.rate_limit_per_hour,
        }


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
        return jsonify({'status': 'healthy', 'database': 'connected'}), 200
    except Exception as e:
        return jsonify({'status': 'unhealthy', 'error': str(e)}), 500


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
@limiter.limit("100 per hour")
def get_polling_places():
    """
    Get all polling places
    Query parameters:
    - state: Filter by state (e.g., ?state=CA)
    - format: Response format - 'vip' or 'standard' (default: standard)
    """
    try:
        query = PollingPlace.query

        # Filter by state if provided
        state_filter = request.args.get('state')
        if state_filter:
            query = query.filter_by(state=state_filter.upper())

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
@limiter.limit("100 per hour")
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


@app.route('/api/plugins', methods=['GET'])
@require_api_key
@limiter.limit("50 per hour")
def list_plugins():
    """List all loaded plugins and their status"""
    return jsonify({
        'plugins': plugin_manager.list_plugins()
    }), 200


@app.route('/api/plugins/<plugin_name>/sync', methods=['POST'])
@require_api_key
@limiter.limit("10 per hour")
def sync_plugin(plugin_name):
    """Trigger a data sync for a specific plugin"""
    try:
        result = plugin_manager.sync_plugin(plugin_name)
        return jsonify(result), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# Scheduling functions
def sync_all_plugins_job():
    """Background job to sync all plugins"""
    with app.app_context():
        app.logger.info("Running scheduled sync for all plugins")
        results = plugin_manager.sync_all_plugins()
        app.logger.info(f"Scheduled sync completed: {results}")


# Create tables and initialize
with app.app_context():
    db.create_all()

    # Initialize plugin manager after models are defined
    global plugin_manager
    plugin_manager = PluginManager(app, db)

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
