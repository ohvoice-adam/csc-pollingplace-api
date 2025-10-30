from datetime import datetime
import json
import secrets
import bcrypt

# Import db from the shared database module to avoid multiple instances
from database import db
from flask_login import UserMixin

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
    county = db.Column(db.String(100))  # County information

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
            'county': self.county,
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
        if self.county:
            vip_data['county'] = self.county

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


class Precinct(db.Model):
    """
    Voting precinct model.
    Represents a voting precinct and tracks its current polling place assignment.
    """
    __tablename__ = 'precincts'

    # Primary identifier
    id = db.Column(db.String(255), primary_key=True)  # e.g., "CA-ALAMEDA-0001"

    # Precinct information
    name = db.Column(db.String(255), nullable=False)
    state = db.Column(db.String(2), nullable=False, index=True)
    county = db.Column(db.String(100))
    precinctcode = db.Column(db.String(50))  # Official precinct code from state data
    registered_voters = db.Column(db.Integer)

    # Current assignment tracking
    current_polling_place_id = db.Column(db.String(255), db.ForeignKey('polling_places.id'))
    last_change_date = db.Column(db.Date)
    changed_recently = db.Column(db.Boolean, default=False)  # Changed in last 6 months

    # Source tracking
    source_plugin = db.Column(db.String(100))

    # Metadata
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    updated_at = db.Column(db.DateTime, server_default=db.func.now(), onupdate=db.func.now())

    # Relationships
    current_polling_place = db.relationship('PollingPlace', foreign_keys=[current_polling_place_id], backref='current_precincts')
    assignments = db.relationship('PrecinctAssignment', back_populates='precinct', order_by='PrecinctAssignment.assigned_date.desc()')

    def to_dict(self):
        """Convert model to dictionary"""
        return {
            'id': self.id,
            'name': self.name,
            'state': self.state,
            'county': self.county,
            'precinctcode': self.precinctcode,
            'registered_voters': self.registered_voters,
            'current_polling_place_id': self.current_polling_place_id,
            'last_change_date': self.last_change_date.isoformat() if self.last_change_date else None,
            'changed_recently': self.changed_recently,
            'source_plugin': self.source_plugin,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }

    def to_dict_with_history(self):
        """Convert model to dictionary with assignment history"""
        data = self.to_dict()
        data['assignment_history'] = [assignment.to_dict() for assignment in self.assignments]
        if self.current_polling_place:
            data['current_polling_place'] = self.current_polling_place.to_dict()
        return data


class PrecinctAssignment(db.Model):
    """
    Historical tracking of precinct-to-polling-place assignments.
    Each record represents a time period when a precinct was assigned to a specific polling place.
    """
    __tablename__ = 'precinct_assignments'

    id = db.Column(db.Integer, primary_key=True)

    # Assignment details
    precinct_id = db.Column(db.String(255), db.ForeignKey('precincts.id'), nullable=False, index=True)
    polling_place_id = db.Column(db.String(255), db.ForeignKey('polling_places.id'), nullable=False)
    election_id = db.Column(db.Integer, db.ForeignKey('elections.id'), index=True)  # Optional link to election

    # Time range
    assigned_date = db.Column(db.Date, nullable=False)
    removed_date = db.Column(db.Date)  # NULL means current assignment

    # Change tracking
    previous_polling_place_id = db.Column(db.String(255), db.ForeignKey('polling_places.id'))

    # Metadata
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    # Relationships
    precinct = db.relationship('Precinct', back_populates='assignments')
    polling_place = db.relationship('PollingPlace', foreign_keys=[polling_place_id])
    previous_polling_place = db.relationship('PollingPlace', foreign_keys=[previous_polling_place_id])
    election = db.relationship('Election', back_populates='assignments')

    def to_dict(self):
        """Convert model to dictionary"""
        result = {
            'id': self.id,
            'precinct_id': self.precinct_id,
            'polling_place_id': self.polling_place_id,
            'assigned_date': self.assigned_date.isoformat() if self.assigned_date else None,
            'removed_date': self.removed_date.isoformat() if self.removed_date else None,
            'previous_polling_place_id': self.previous_polling_place_id,
            'is_current': self.removed_date is None,
            'election_id': self.election_id,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }

        # Include election details if available
        if self.election:
            result['election'] = {
                'id': self.election.id,
                'date': self.election.date.isoformat() if self.election.date else None,
                'name': self.election.name,
                'state': self.election.state
            }

        return result


class Election(db.Model):
    """
    Election model for tracking elections and their polling place configurations.
    Each election represents a specific voting event with a date and name.
    """
    __tablename__ = 'elections'

    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False, index=True)
    name = db.Column(db.String(255), nullable=False)  # e.g., "2024 General Election"
    state = db.Column(db.String(2), nullable=False, index=True)

    # Metadata
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    # Relationships
    assignments = db.relationship('PrecinctAssignment', back_populates='election')

    # Unique constraint on date + state
    __table_args__ = (db.UniqueConstraint('date', 'state', name='unique_election_date_state'),)

    def to_dict(self):
        """Convert model to dictionary"""
        return {
            'id': self.id,
            'date': self.date.isoformat() if self.date else None,
            'name': self.name,
            'state': self.state,
            'created_at': self.created_at.isoformat() if self.created_at else None,
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


class AuditTrail(db.Model):
    """Audit trail to track all record changes"""
    __tablename__ = 'audit_trail'
    
    id = db.Column(db.Integer, primary_key=True)
    table_name = db.Column(db.String(50), nullable=False, index=True)
    record_id = db.Column(db.String(255), nullable=False, index=True)
    action = db.Column(db.String(20), nullable=False)  # 'CREATE', 'UPDATE', 'DELETE'
    old_values = db.Column(db.Text)  # JSON string of old values
    new_values = db.Column(db.Text)  # JSON string of new values
    changed_fields = db.Column(db.Text)  # JSON string of changed field names
    user_id = db.Column(db.Integer, db.ForeignKey('admin_users.id'))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    ip_address = db.Column(db.String(45))
    user_agent = db.Column(db.Text)
    
    # Relationship handled dynamically to avoid circular import issues
    
    def to_dict(self):
        """Convert audit trail entry to dictionary"""
        return {
            'id': self.id,
            'table_name': self.table_name,
            'record_id': self.record_id,
            'action': self.action,
            'old_values': json.loads(self.old_values) if self.old_values else None,
            'new_values': json.loads(self.new_values) if self.new_values else None,
            'changed_fields': json.loads(self.changed_fields) if self.changed_fields else [],
            'user_id': self.user_id,
            'username': self.get_username(),
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'ip_address': self.ip_address,
            'user_agent': self.user_agent
        }
    
    def get_username(self):
        """Get username for this audit trail entry"""
        if self.user_id:
            try:
                # Import here to avoid circular import
                from app import AdminUser
                admin_user = AdminUser.query.get(self.user_id)
                return admin_user.username if admin_user else None
            except:
                return None
        return None