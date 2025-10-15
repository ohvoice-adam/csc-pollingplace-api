"""
CSC Polling Place API
Main application file

Provides centralized polling place location data in VIP (Voting Information Project) format
compatible with Google Civic Data API.
"""

import os
import secrets
import bcrypt
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
        # Standard PostgreSQL connection
        app.config['SQLALCHEMY_DATABASE_URI'] = f'postgresql+psycopg2://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}'
else:
    # Default to SQLite
    sqlite_path = os.getenv('SQLITE_PATH', '/data/pollingplaces.db')
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{sqlite_path}'

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['JSON_SORT_KEYS'] = False
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', secrets.token_hex(32))

# Initialize extensions
CORS(app)
db = SQLAlchemy(app)

# Initialize login manager
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'admin_login'

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


class AdminUser(UserMixin, db.Model):
    """
    Admin user model for web interface authentication
    """
    __tablename__ = 'admin_users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    last_login_at = db.Column(db.DateTime)

    def set_password(self, password):
        """Hash and set password"""
        self.password_hash = bcrypt.hashpw(
            password.encode('utf-8'),
            bcrypt.gensalt()
        ).decode('utf-8')

    def check_password(self, password):
        """Check if password matches hash"""
        return bcrypt.checkpw(
            password.encode('utf-8'),
            self.password_hash.encode('utf-8')
        )


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
    """Admin dashboard - manage API keys"""
    api_keys = APIKey.query.order_by(APIKey.created_at.desc()).all()
    return render_template('admin/dashboard.html', api_keys=api_keys)


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
