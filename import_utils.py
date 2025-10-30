"""
Import utilities for bulk data updates
Supports CSV and Excel file imports with validation
"""

import pandas as pd
import io
import json
from datetime import datetime
from flask import current_app
from sqlalchemy.exc import SQLAlchemyError
from app import PollingPlace, Precinct
from models import AuditTrail
from flask_login import current_user


class DataImporter:
    """Base class for data importers"""
    
    def __init__(self, db_session):
        self.db = db_session
        self.errors = []
        self.warnings = []
        self.imported_count = 0
        self.updated_count = 0
    
    def validate_coordinates(self, lat, lon):
        """Validate geographic coordinates"""
        try:
            lat = float(lat) if lat is not None else None
            lon = float(lon) if lon is not None else None
            
            if lat is not None:
                if not (-90 <= lat <= 90):
                    return False, "Latitude must be between -90 and 90"
            
            if lon is not None:
                if not (-180 <= lon <= 180):
                    return False, "Longitude must be between -180 and 180"
            
            return True, None
        except (ValueError, TypeError):
            return False, "Invalid coordinate format"
    
    def validate_required_fields(self, data, required_fields):
        """Validate required fields are present"""
        missing_fields = []
        for field in required_fields:
            if field not in data or pd.isna(data[field]) or str(data[field]).strip() == '':
                missing_fields.append(field)
        
        if missing_fields:
            return False, f"Missing required fields: {', '.join(missing_fields)}"
        return True, None
    
    def create_audit_entry(self, table_name, record_id, action, old_values=None, new_values=None, changed_fields=None):
        """Create audit trail entry"""
        try:
            audit = AuditTrail()
            audit.table_name = table_name
            audit.record_id = str(record_id)
            audit.action = action
            audit.old_values = json.dumps(old_values) if old_values else None
            audit.new_values = json.dumps(new_values) if new_values else None
            audit.changed_fields = json.dumps(changed_fields) if changed_fields else None
            audit.user_id = current_user.id if current_user.is_authenticated else None
            audit.timestamp = datetime.utcnow()
            self.db.add(audit)
        except Exception as e:
            current_app.logger.error(f"Error creating audit entry: {str(e)}")


class PollingPlaceImporter(DataImporter):
    """Importer for PollingPlace data"""
    
    REQUIRED_FIELDS = ['id', 'name', 'city', 'state', 'zip_code']
    OPTIONAL_FIELDS = ['address_line1', 'address_line2', 'address_line3', 'county', 
                      'latitude', 'longitude', 'polling_hours', 'notes', 'source_plugin']
    
    def import_from_file(self, file_content, file_type='csv'):
        """Import polling places from file content"""
        try:
            if file_type == 'csv':
                df = pd.read_csv(io.StringIO(file_content))
            elif file_type in ['xlsx', 'xls']:
                df = pd.read_excel(io.BytesIO(file_content))
            else:
                return False, "Unsupported file format"
            
            return self.process_dataframe(df)
            
        except Exception as e:
            return False, f"Error reading file: {str(e)}"
    
    def process_dataframe(self, df):
        """Process DataFrame and import records"""
        try:
            for index, row in df.iterrows():
                try:
                    # Convert row to dict, handling NaN values
                    data = {}
                    for col in df.columns:
                        value = row[col]
                        if pd.isna(value):
                            data[col] = None
                        else:
                            data[col] = str(value).strip() if isinstance(value, str) else value
                    
                    # Validate required fields
                    is_valid, error_msg = self.validate_required_fields(data, self.REQUIRED_FIELDS)
                    if not is_valid:
                        self.errors.append(f"Row {index + 1}: {error_msg}")
                        continue
                    
                    # Validate coordinates
                    if 'latitude' in data or 'longitude' in data:
                        coord_valid, coord_error = self.validate_coordinates(
                            data.get('latitude'), data.get('longitude')
                        )
                        if not coord_valid:
                            self.errors.append(f"Row {index + 1}: {coord_error}")
                            continue
                    
                    # Check if record exists
                    existing = PollingPlace.query.get(data['id'])
                    
                    if existing:
                        # Update existing record
                        old_values = existing.to_dict()
                        
                        # Update fields
                        for field in self.OPTIONAL_FIELDS:
                            if field in data and data[field] is not None:
                                setattr(existing, field, data[field])
                        
                        new_values = existing.to_dict()
                        changed_fields = [k for k, v in old_values.items() 
                                        if old_values.get(k) != new_values.get(k)]
                        
                        if changed_fields:
                            self.create_audit_entry(
                                'polling_places', data['id'], 'UPDATE',
                                old_values, new_values, changed_fields
                            )
                            self.updated_count += 1
                    
                    else:
                        # Create new record
                        polling_place = PollingPlace()
                        polling_place.id = data['id']
                        polling_place.name = data['name']
                        polling_place.city = data['city']
                        polling_place.state = data['state']
                        polling_place.zip_code = data['zip_code']
                        
                        # Set optional fields
                        for field in self.OPTIONAL_FIELDS:
                            if field in data and data[field] is not None:
                                setattr(polling_place, field, data[field])
                        
                        self.db.add(polling_place)
                        self.create_audit_entry(
                            'polling_places', data['id'], 'CREATE',
                            None, polling_place.to_dict()
                        )
                        self.imported_count += 1
                
                except Exception as e:
                    self.errors.append(f"Row {index + 1}: {str(e)}")
                    continue
            
            # Commit changes
            self.db.commit()
            
            return True, self.get_summary()
            
        except Exception as e:
            self.db.rollback()
            return False, f"Error processing data: {str(e)}"
    
    def get_summary(self):
        """Get import summary"""
        summary = {
            'imported': self.imported_count,
            'updated': self.updated_count,
            'errors': len(self.errors),
            'warnings': len(self.warnings)
        }
        
        if self.errors:
            summary['error_details'] = self.errors[:10]  # First 10 errors
        
        if self.warnings:
            summary['warning_details'] = self.warnings[:10]  # First 10 warnings
        
        return summary


class PrecinctImporter(DataImporter):
    """Importer for Precinct data"""
    
    REQUIRED_FIELDS = ['id', 'name', 'state']
    OPTIONAL_FIELDS = ['county', 'registered_voters', 'current_polling_place_id',
                      'last_change_date', 'changed_recently', 'source_plugin']
    
    def import_from_file(self, file_content, file_type='csv'):
        """Import precincts from file content"""
        try:
            if file_type == 'csv':
                df = pd.read_csv(io.StringIO(file_content))
            elif file_type in ['xlsx', 'xls']:
                df = pd.read_excel(io.BytesIO(file_content))
            else:
                return False, "Unsupported file format"
            
            return self.process_dataframe(df)
            
        except Exception as e:
            return False, f"Error reading file: {str(e)}"
    
    def process_dataframe(self, df):
        """Process DataFrame and import records"""
        try:
            for index, row in df.iterrows():
                try:
                    # Convert row to dict, handling NaN values
                    data = {}
                    for col in df.columns:
                        value = row[col]
                        if pd.isna(value):
                            data[col] = None
                        else:
                            data[col] = str(value).strip() if isinstance(value, str) else value
                    
                    # Validate required fields
                    is_valid, error_msg = self.validate_required_fields(data, self.REQUIRED_FIELDS)
                    if not is_valid:
                        self.errors.append(f"Row {index + 1}: {error_msg}")
                        continue
                    
                    # Check if record exists
                    existing = Precinct.query.get(data['id'])
                    
                    if existing:
                        # Update existing record
                        old_values = existing.to_dict()
                        
                        # Update fields
                        for field in self.OPTIONAL_FIELDS:
                            if field in data and data[field] is not None:
                                if field == 'registered_voters':
                                    try:
                                        setattr(existing, field, int(data[field]))
                                    except (ValueError, TypeError):
                                        self.warnings.append(f"Row {index + 1}: Invalid registered_voters value")
                                elif field == 'changed_recently':
                                    setattr(existing, field, str(data[field]).lower() in ['true', '1', 'yes'])
                                else:
                                    setattr(existing, field, data[field])
                        
                        new_values = existing.to_dict()
                        changed_fields = [k for k, v in old_values.items() 
                                        if old_values.get(k) != new_values.get(k)]
                        
                        if changed_fields:
                            self.create_audit_entry(
                                'precincts', data['id'], 'UPDATE',
                                old_values, new_values, changed_fields
                            )
                            self.updated_count += 1
                    
                    else:
                        # Create new record
                        precinct = Precinct()
                        precinct.id = data['id']
                        precinct.name = data['name']
                        precinct.state = data['state']
                        
                        # Set optional fields
                        for field in self.OPTIONAL_FIELDS:
                            if field in data and data[field] is not None:
                                if field == 'registered_voters':
                                    try:
                                        setattr(precinct, field, int(data[field]))
                                    except (ValueError, TypeError):
                                        self.warnings.append(f"Row {index + 1}: Invalid registered_voters value")
                                elif field == 'changed_recently':
                                    setattr(precinct, field, str(data[field]).lower() in ['true', '1', 'yes'])
                                else:
                                    setattr(precinct, field, data[field])
                        
                        self.db.add(precinct)
                        self.create_audit_entry(
                            'precincts', data['id'], 'CREATE',
                            None, precinct.to_dict()
                        )
                        self.imported_count += 1
                
                except Exception as e:
                    self.errors.append(f"Row {index + 1}: {str(e)}")
                    continue
            
            # Commit changes
            self.db.commit()
            
            return True, self.get_summary()
            
        except Exception as e:
            self.db.rollback()
            return False, f"Error processing data: {str(e)}"
    
    def get_summary(self):
        """Get import summary"""
        summary = {
            'imported': self.imported_count,
            'updated': self.updated_count,
            'errors': len(self.errors),
            'warnings': len(self.warnings)
        }
        
        if self.errors:
            summary['error_details'] = self.errors[:10]  # First 10 errors
        
        if self.warnings:
            summary['warning_details'] = self.warnings[:10]  # First 10 warnings
        
        return summary


def get_importer(model_type, db_session):
    """Factory function to get appropriate importer"""
    if model_type == 'polling_places':
        return PollingPlaceImporter(db_session)
    elif model_type == 'precincts':
        return PrecinctImporter(db_session)
    else:
        raise ValueError(f"Unknown model type: {model_type}")