"""
CSC Polling Place API
Main application file

Provides centralized polling place location data in VIP (Voting Information Project) format
compatible with Google Civic Data API.
"""

import os
from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from dotenv import load_dotenv
from plugins.plugin_manager import PluginManager

# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__)

# Configuration
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv(
    'DATABASE_URL',
    'postgresql://localhost/csc_pollingplace'
)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['JSON_SORT_KEYS'] = False

# Initialize extensions
CORS(app)
db = SQLAlchemy(app)

# Initialize plugin manager
plugin_manager = PluginManager(app, db)


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


@app.route('/api/polling-places', methods=['GET'])
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
def list_plugins():
    """List all loaded plugins and their status"""
    return jsonify({
        'plugins': plugin_manager.list_plugins()
    }), 200


@app.route('/api/plugins/<plugin_name>/sync', methods=['POST'])
def sync_plugin(plugin_name):
    """Trigger a data sync for a specific plugin"""
    try:
        result = plugin_manager.sync_plugin(plugin_name)
        return jsonify(result), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# Create tables
with app.app_context():
    db.create_all()


if __name__ == '__main__':
    port = int(os.getenv('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=os.getenv('DEBUG', 'False') == 'True')
