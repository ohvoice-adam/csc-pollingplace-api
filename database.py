"""
Shared database instance to avoid multiple SQLAlchemy instances
"""

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()