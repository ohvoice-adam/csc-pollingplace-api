from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

db = SQLAlchemy()

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class PollingPlace(db.Model):
    id = db.Column(db.String(100), primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    address_line1 = db.Column(db.String(200))
    address_line2 = db.Column(db.String(200))
    address_line3 = db.Column(db.String(200))
    city = db.Column(db.String(100))
    state = db.Column(db.String(2))
    zip_code = db.Column(db.String(10))
    county = db.Column(db.String(100))
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)
    polling_hours = db.Column(db.String(200))
    notes = db.Column(db.Text)
    source_plugin = db.Column(db.String(100))
    last_updated = db.Column(db.DateTime, default=datetime.utcnow)

class Precinct(db.Model):
    id = db.Column(db.String(100), primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    state = db.Column(db.String(2))
    county = db.Column(db.String(100))
    registered_voters = db.Column(db.Integer)
    current_polling_place_id = db.Column(db.String(100), db.ForeignKey('polling_place.id'))
    last_change_date = db.Column(db.DateTime)
    changed_recently = db.Column(db.Boolean, default=False)
    source_plugin = db.Column(db.String(100))
    last_updated = db.Column(db.DateTime, default=datetime.utcnow)

class PrecinctAssignment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    precinct_id = db.Column(db.String(100), db.ForeignKey('precinct.id'))
    polling_place_id = db.Column(db.String(100), db.ForeignKey('polling_place.id'))
    assigned_date = db.Column(db.DateTime, default=datetime.utcnow)
    previous_polling_place_id = db.Column(db.String(100))
    election_id = db.Column(db.Integer, db.ForeignKey('election.id'))

class Election(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False)
    name = db.Column(db.String(200))
    state = db.Column(db.String(2))
    type = db.Column(db.String(50))  # e.g., 'general', 'primary'
    source_plugin = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)