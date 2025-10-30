"""
Flask-Admin configuration for CSC Polling Place API
Provides database management interface for editing records
"""

from flask_admin import Admin, BaseView, expose
from flask_admin.contrib.sqla import ModelView
from flask_admin.actions import action
from flask_login import current_user
from flask import redirect, url_for, flash, request
from wtforms import TextAreaField, SelectField
from wtforms.widgets import TextArea
from markupsafe import Markup
from sqlalchemy.exc import SQLAlchemyError
from datetime import datetime

class CKTextAreaWidget(TextArea):
    """Custom widget for rich text editing"""
    def __call__(self, field, **kwargs):
        if kwargs.get('class'):
            kwargs['class'] = f"{kwargs['class']} rich-text"
        else:
            kwargs.setdefault('class', 'rich-text')
        return super(CKTextAreaWidget, self).__call__(field, **kwargs)

class CKTextAreaField(TextAreaField):
    """Custom field for rich text editing"""
    widget = CKTextAreaWidget()

class SecureModelView(ModelView):
    """Base model view with authentication"""
    
    # Disable CSRF protection for simplicity (enable in production)
    form_base_class = None
    
    # Pagination
    page_size = 50
    
    # Security settings
    can_create = True
    can_edit = True
    can_delete = True
    can_view_details = True
    
    def is_accessible(self):
        """Check if current user is authenticated"""
        return current_user.is_authenticated
    
    def inaccessible_callback(self, name, **kwargs):
        """Redirect to login page if not authenticated"""
        flash('Please log in to access this page.', 'warning')
        return redirect(url_for('admin_login', next=request.url))
    
    def on_model_change(self, form, model, is_created):
        """Log model changes"""
        try:
            action = "created" if is_created else "updated"
            model_name = model.__class__.__name__
            flash(f'{model_name} successfully {action}!', 'success')
        except Exception as e:
            flash(f'Error saving {model.__class__.__name__}: {str(e)}', 'error')
    
    def on_model_delete(self, model):
        """Log model deletions"""
        try:
            model_name = model.__class__.__name__
            flash(f'{model_name} successfully deleted!', 'success')
        except Exception as e:
            flash(f'Error deleting {model.__class__.__name__}: {str(e)}', 'error')

class PollingPlaceView(SecureModelView):
    """Admin view for PollingPlace model"""
    
    # Columns to display
    column_list = ('id', 'name', 'city', 'state', 'county', 'latitude', 'longitude', 
                   'polling_hours', 'source_plugin', 'created_at', 'updated_at')
    
    # Searchable columns
    column_searchable_list = ('name', 'city', 'county', 'address_line1', 'address_line2')
    
    # Filters
    column_filters = ('state', 'county', 'source_plugin', 'created_at', 'updated_at')
    
    # Sortable columns
    column_sortable_list = ('name', 'city', 'state', 'county', 'created_at', 'updated_at')
    
    # Form fields - temporarily disabled custom widgets to avoid metaclass conflicts
    # form_overrides = {
    #     'notes': CKTextAreaField,
    #     'voter_services': CKTextAreaField
    # }
    
    # Form columns - only include fields that exist in the model
    form_columns = ('id', 'name', 'address_line1', 'address_line2', 
                   'address_line3', 'city', 'state', 'zip_code', 'county', 
                   'latitude', 'longitude', 'polling_hours', 'notes', 'source_plugin')
    
    # Custom form fields with help text
    form_args = {
        'id': {
            'label': 'ID',
            'description': 'Unique identifier for this polling place'
        },
        'name': {
            'label': 'Name',
            'description': 'Name of the polling place'
        },
        'latitude': {
            'label': 'Latitude',
            'description': 'WGS 84 decimal degrees (-90 to 90)'
        },
        'longitude': {
            'label': 'Longitude', 
            'description': 'WGS 84 decimal degrees (-180 to 180)'
        },
        'polling_hours': {
            'label': 'Polling Hours',
            'description': 'e.g., "7:00 AM - 8:00 PM"'
        },
        'source_plugin': {
            'label': 'Source Plugin'
        }
    }
    
    # Custom formatters for display
    def _source_plugin_formatter(self, context, model, name):
        if model.source_plugin:
            return f'<span class="label label-info">{model.source_plugin}</span>'
        return ''
    
    column_formatters = {
        'source_plugin': _source_plugin_formatter
    }
    
    # Custom actions
    @action('geocode', 'Geocode Selected', 'Are you sure you want to geocode selected items?')
    def geocode_action(self, ids):
        try:
            # This would integrate with your geocoding service
            flash(f'Geocoding {len(ids)} polling places', 'success')
        except Exception as ex:
            flash(f'Failed to geocode: {str(ex)}', 'error')

class PrecinctView(SecureModelView):
    """Admin view for Precinct model"""
    
    # Columns to display
    column_list = ('id', 'name', 'state', 'county', 'registered_voters', 
                   'current_polling_place', 'changed_recently', 
                   'source_plugin', 'created_at', 'updated_at')
    
    # Searchable columns
    column_searchable_list = ('name', 'county')
    
    # Filters
    column_filters = ('state', 'county', 'changed_recently', 'source_plugin', 'created_at')
    
    # Sortable columns
    column_sortable_list = ('name', 'state', 'county', 'registered_voters', 'created_at')
    
    # Form columns - only include fields that exist in the model
    form_columns = ('id', 'name', 'state', 'county', 'registered_voters', 
                   'current_polling_place', 'last_change_date',
                   'changed_recently', 'source_plugin')
    
    # Custom form fields with help text
    form_args = {
        'id': {
            'label': 'ID',
            'description': 'Unique identifier for this precinct (e.g., "CA-ALAMEDA-0001")'
        },
        'name': {
            'label': 'Name',
            'description': 'Name of the precinct'
        },
        'state': {
            'label': 'State',
            'description': 'Two-letter state code'
        },
        'county': {
            'label': 'County'
        },
        'registered_voters': {
            'label': 'Registered Voters',
            'description': 'Number of registered voters in this precinct'
        },
        'changed_recently': {
            'label': 'Changed Recently',
            'description': 'Whether this precinct has recent changes'
        },
        'source_plugin': {
            'label': 'Source Plugin'
        }
    }
    
    # Custom display for current polling place
    def _current_polling_place_formatter(self, context, model, name):
        if model.current_polling_place:
            return Markup(f'<a href="/admin/pollingplace/edit/?id={model.current_polling_place.id}">{model.current_polling_place.name}</a>')
        return '<span class="text-muted">Not assigned</span>'
    
    # Custom display for changed recently status
    def _changed_recently_formatter(self, context, model, name):
        if model.changed_recently:
            return '<span class="label label-warning">Yes</span>'
        return '<span class="label label-default">No</span>'
    
    column_formatters = {
        'current_polling_place': _current_polling_place_formatter,
        'changed_recently': _changed_recently_formatter
    }

class ElectionView(SecureModelView):
    """Admin view for Election model"""
    
    # Columns to display
    column_list = ('id', 'date', 'name', 'state', 'created_at')
    
    # Searchable columns
    column_searchable_list = ('name', 'state')
    
    # Filters
    column_filters = ('state', 'date', 'created_at')
    
    # Sortable columns
    column_sortable_list = ('date', 'name', 'state', 'created_at')
    
    # Form columns
    form_columns = ('date', 'name', 'state')
    
    # Custom form fields with help text
    form_args = {
        'name': {
            'label': 'Election Name',
            'description': 'e.g., "2024 General Election"'
        },
        'date': {
            'label': 'Election Date',
            'description': 'Date of the election'
        },
        'state': {
            'label': 'State',
            'description': 'Two-letter state code'
        }
    }
    
    # No custom formatters needed for Election model

class PrecinctAssignmentView(SecureModelView):
    """Admin view for PrecinctAssignment model"""
    
    # Columns to display
    column_list = ('id', 'precinct', 'polling_place', 'election', 'assigned_date', 
                   'removed_date')
    
    # Searchable columns
    column_searchable_list = ('precinct.name', 'polling_place.name', 'election.name')
    
    # Filters
    column_filters = ('assigned_date', 'removed_date', 'election')
    
    # Sortable columns
    column_sortable_list = ('assigned_date', 'removed_date')
    
    # Form columns
    form_columns = ('precinct', 'polling_place', 'election', 'assigned_date', 
                   'removed_date', 'previous_polling_place')
    
    # Custom form fields with help text
    form_args = {
        'assigned_date': {
            'label': 'Assigned Date',
            'description': 'Date when this assignment was made'
        },
        'removed_date': {
            'label': 'Removed Date',
            'description': 'Date when this assignment was removed (leave empty if current)'
        }
    }
    
    # Custom display for related objects
    def _precinct_formatter(self, context, model, name):
        if model.precinct:
            return Markup(f'<a href="/admin/precinct/edit/?id={model.precinct.id}">{model.precinct.name}</a>')
        return '<span class="text-muted">Not specified</span>'
    
    def _polling_place_formatter(self, context, model, name):
        if model.polling_place:
            return Markup(f'<a href="/admin/pollingplace/edit/?id={model.polling_place.id}">{model.polling_place.name}</a>')
        return '<span class="text-muted">Not specified</span>'
    
    def _election_formatter(self, context, model, name):
        if model.election:
            return Markup(f'<a href="/admin/election/edit/?id={model.election.id}">{model.election.name}</a>')
        return '<span class="text-muted">Not specified</span>'
    
    def _status_formatter(self, context, model, name):
        if model.removed_date:
            return '<span class="label label-default">Inactive</span>'
        return '<span class="label label-success">Active</span>'
    
    column_formatters = {
        'precinct': _precinct_formatter,
        'polling_place': _polling_place_formatter,
        'election': _election_formatter,
        'removed_date': _status_formatter
    }

class APIKeyView(SecureModelView):
    """Admin view for APIKey model"""
    
    # Columns to display
    column_list = ('id', 'name', 'key', 'is_active', 'rate_limit_per_day', 
                   'rate_limit_per_hour', 'created_at', 'last_used_at')
    
    # Searchable columns
    column_searchable_list = ('name', 'key')
    
    # Filters
    column_filters = ('is_active', 'created_at', 'last_used_at')
    
    # Sortable columns
    column_sortable_list = ('name', 'created_at', 'last_used_at')
    
    # Form columns
    form_columns = ('name', 'key', 'is_active', 'rate_limit_per_day', 'rate_limit_per_hour')
    
    # Custom form fields with help text
    form_args = {
        'name': {
            'label': 'Key Name',
            'description': 'Description/owner of the key'
        },
        'key': {
            'label': 'API Key',
            'description': 'The actual API key string (64 characters)'
        },
        'is_active': {
            'label': 'Active',
            'description': 'Whether this API key is currently active'
        },
        'rate_limit_per_day': {
            'label': 'Daily Rate Limit',
            'description': 'Maximum requests per day (leave empty for unlimited)'
        },
        'rate_limit_per_hour': {
            'label': 'Hourly Rate Limit', 
            'description': 'Maximum requests per hour (leave empty for unlimited)'
        }
    }
    
    # Display API key in a more readable format
    def _key_formatter(self, context, model, name):
        if model.key:
            return Markup(f'<code style="background: #f4f4f4; padding: 2px 4px; border-radius: 3px; font-size: 11px;">{model.key[:20]}...</code>')
        return ''
    
    def _status_formatter(self, context, model, name):
        if model.is_active:
            return '<span class="label label-success">Active</span>'
        return '<span class="label label-danger">Inactive</span>'
    
    def _last_used_formatter(self, context, model, name):
        if model.last_used_at:
            return model.last_used_at.strftime('%Y-%m-%d %H:%M')
        return '<span class="text-muted">Never used</span>'
    
    column_formatters = {
        'key': _key_formatter,
        'is_active': _status_formatter,
        'last_used_at': _last_used_formatter
    }

class RecordsView(BaseView):
    """Custom view for record management"""
    
    @expose('/')
    def index(self):
        try:
            # Import models here to avoid circular imports
            from app import PollingPlace, Precinct, Election, APIKey, PrecinctAssignment
            
            # Query counts for each model
            polling_places_count = PollingPlace.query.count()
            precincts_count = Precinct.query.count()
            elections_count = Election.query.count()
            api_keys_count = APIKey.query.count()
            assignments_count = PrecinctAssignment.query.count()
            
            # Additional statistics
            active_api_keys = APIKey.query.filter_by(is_active=True).count()
            precincts_with_polling_places = Precinct.query.filter(Precinct.current_polling_place_id.isnot(None)).count()
            recent_elections = Election.query.filter(Election.date >= datetime.now().date()).count()
            
            # Pass counts to template
            return self.render('admin/records_index.html',
                             polling_places_count=polling_places_count,
                             precincts_count=precincts_count,
                             elections_count=elections_count,
                             api_keys_count=api_keys_count,
                             assignments_count=assignments_count,
                             active_api_keys=active_api_keys,
                             precincts_with_polling_places=precincts_with_polling_places,
                             recent_elections=recent_elections)
        except SQLAlchemyError as e:
            # Handle database errors gracefully
            return self.render('admin/records_index.html',
                             polling_places_count=0,
                             precincts_count=0,
                             elections_count=0,
                             api_keys_count=0,
                             assignments_count=0,
                             active_api_keys=0,
                             precincts_with_polling_places=0,
                             recent_elections=0,
                             error=f'Database error: {str(e)}')
        except Exception as e:
            # Handle other errors
            return self.render('admin/records_index.html',
                             polling_places_count=0,
                             precincts_count=0,
                             elections_count=0,
                             api_keys_count=0,
                             assignments_count=0,
                             active_api_keys=0,
                             precincts_with_polling_places=0,
                             recent_elections=0,
                             error=f'Error: {str(e)}')

def init_admin(app, db):
    """Initialize Flask-Admin with custom views"""
    
    try:
        # Import models here to avoid circular imports
        from app import PollingPlace, Precinct, Election, PrecinctAssignment, APIKey
        
        admin = Admin(
            app, 
            name='CSC Polling Place Admin',
            template_mode='bootstrap3',
            index_view=RecordsView(name='Records Dashboard', url='/admin/records', endpoint='records_dashboard'),
            url='/admin'
        )
        
        # Add model views with proper error handling
        try:
            admin.add_view(PollingPlaceView(PollingPlace, db.session, name='Polling Places', endpoint='pollingplace'))
        except Exception as e:
            app.logger.error(f"Error adding PollingPlace view: {e}")
        
        try:
            admin.add_view(PrecinctView(Precinct, db.session, name='Precincts', endpoint='precinct'))
        except Exception as e:
            app.logger.error(f"Error adding Precinct view: {e}")
        
        try:
            admin.add_view(ElectionView(Election, db.session, name='Elections', endpoint='election'))
        except Exception as e:
            app.logger.error(f"Error adding Election view: {e}")
        
        try:
            admin.add_view(PrecinctAssignmentView(PrecinctAssignment, db.session, name='Precinct Assignments', endpoint='precinctassignment'))
        except Exception as e:
            app.logger.error(f"Error adding PrecinctAssignment view: {e}")
        
        try:
            admin.add_view(APIKeyView(APIKey, db.session, name='API Keys', endpoint='apikey'))
        except Exception as e:
            app.logger.error(f"Error adding APIKey view: {e}")
        
        app.logger.info("Flask-Admin initialized successfully")
        return admin
        
    except Exception as e:
        app.logger.error(f"Failed to initialize Flask-Admin: {e}")
        return None