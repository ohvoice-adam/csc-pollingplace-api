"""
CSC Polling Place API
Main application file
"""

import os
from flask import Flask, jsonify
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from dotenv import load_dotenv

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


# Database models
class PollingPlace(db.Model):
    """Polling place model"""
    __tablename__ = 'polling_places'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    address = db.Column(db.String(500), nullable=False)
    city = db.Column(db.String(100), nullable=False)
    state = db.Column(db.String(2), nullable=False)
    zip_code = db.Column(db.String(10), nullable=False)
    status = db.Column(db.String(50), default='active')
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    updated_at = db.Column(db.DateTime, server_default=db.func.now(), onupdate=db.func.now())

    def to_dict(self):
        """Convert model to dictionary"""
        return {
            'id': self.id,
            'name': self.name,
            'address': self.address,
            'city': self.city,
            'state': self.state,
            'zip_code': self.zip_code,
            'status': self.status,
            'latitude': self.latitude,
            'longitude': self.longitude,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }


class Issue(db.Model):
    """Voting issue model"""
    __tablename__ = 'issues'

    id = db.Column(db.Integer, primary_key=True)
    polling_place_id = db.Column(db.Integer, db.ForeignKey('polling_places.id'))
    issue_type = db.Column(db.String(100), nullable=False)  # e.g., 'id_rejection', 'purge', 'location_change'
    description = db.Column(db.Text, nullable=False)
    severity = db.Column(db.String(20), default='medium')  # low, medium, high, critical
    status = db.Column(db.String(20), default='open')  # open, investigating, resolved, closed
    reported_at = db.Column(db.DateTime, server_default=db.func.now())
    resolved_at = db.Column(db.DateTime)

    polling_place = db.relationship('PollingPlace', backref='issues')

    def to_dict(self):
        """Convert model to dictionary"""
        return {
            'id': self.id,
            'polling_place_id': self.polling_place_id,
            'issue_type': self.issue_type,
            'description': self.description,
            'severity': self.severity,
            'status': self.status,
            'reported_at': self.reported_at.isoformat() if self.reported_at else None,
            'resolved_at': self.resolved_at.isoformat() if self.resolved_at else None,
        }


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
    """Get all polling places"""
    try:
        polling_places = PollingPlace.query.all()
        return jsonify({
            'count': len(polling_places),
            'polling_places': [pp.to_dict() for pp in polling_places]
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/issues', methods=['GET'])
def get_issues():
    """Get all issues"""
    try:
        issues = Issue.query.all()
        return jsonify({
            'count': len(issues),
            'issues': [issue.to_dict() for issue in issues]
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# Create tables
with app.app_context():
    db.create_all()


if __name__ == '__main__':
    port = int(os.getenv('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=os.getenv('DEBUG', 'False') == 'True')
