"""
Simplified Flask-Admin configuration for CSC Polling Place API
Provides database management interface for editing records
"""

from flask_admin import Admin, BaseView, expose
from flask_admin.contrib.sqla import ModelView
from flask_login import current_user
from flask import redirect, url_for, flash, request, jsonify, Response, session, current_app
from markupsafe import Markup
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import text, or_, and_
from datetime import datetime
import json
import csv
import io
import xlsxwriter
import json
import csv
import io
import xlsxwriter
from flask import current_app

class SecureModelView(ModelView):
    """Base model view with authentication"""
    
    # Pagination
    page_size = 50
    
    def is_accessible(self):
        """Check if current user is authenticated"""
        return current_user.is_authenticated
    
    def inaccessible_callback(self, name, **kwargs):
        """Redirect to login page if not authenticated"""
        flash('Please log in to access this page.', 'warning')
        return redirect(url_for('admin_login', next=request.url))

class PollingPlaceView(SecureModelView):
    """Admin view for PollingPlace model with bulk operations"""
    
    # Enable bulk operations
    action_disallowed_list = []
    
    column_list = ['id', 'name', 'city', 'state', 'county', 'latitude', 'longitude', 'polling_hours', 'source_plugin', 'created_at', 'updated_at']
    column_searchable_list = ['name', 'city', 'county', 'address_line1', 'address_line2']
    column_filters = ['state', 'county', 'source_plugin', 'created_at', 'updated_at']
    column_sortable_list = ['name', 'city', 'state', 'county', 'created_at', 'updated_at']
    form_columns = ['name', 'address_line1', 'address_line2', 'address_line3', 'city', 'state', 'zip_code', 'county', 'latitude', 'longitude', 'polling_hours', 'source_plugin']
    
    # Custom actions for bulk operations
    @expose('/action/', methods=['POST'])
    def action_view(self):
        """Handle bulk actions"""
        return self.handle_bulk_action()
    
    def handle_bulk_action(self):
        """Handle bulk delete and edit operations"""
        try:
            if request.form.get('action') == 'delete':
                return self.bulk_delete()
            elif request.form.get('action') == 'bulk_edit':
                return self.bulk_edit_form()
            elif request.form.get('action') == 'apply_bulk_edit':
                return self.apply_bulk_edit()
            elif request.form.get('action') == 'export_csv':
                return self.export_csv()
            elif request.form.get('action') == 'export_excel':
                return self.export_excel()
        except Exception as e:
            flash(f'Error performing bulk action: {str(e)}', 'error')
            return redirect(self.get_url('.index_view'))
    
    def bulk_delete(self):
        """Bulk delete selected records"""
        ids = request.form.getlist('rowid')
        if not ids:
            flash('No records selected for deletion', 'error')
            return redirect(self.get_url('.index_view'))
        
        try:
            # Get records for audit trail
            records = self.model.query.filter(self.model.id.in_(ids)).all()
            
            # Create audit trail entries
            for record in records:
                self.create_audit_entry('DELETE', record.id, None, record.to_dict())
            
            # Delete records
            self.model.query.filter(self.model.id.in_(ids)).delete(synchronize_session=False)
            self.session.commit()
            
            flash(f'Successfully deleted {len(ids)} records', 'success')
        except Exception as e:
            self.session.rollback()
            flash(f'Error deleting records: {str(e)}', 'error')
        
        return redirect(self.get_url('.index_view'))
    
    def bulk_edit_form(self):
        """Show bulk edit form"""
        ids = request.form.getlist('rowid')
        if not ids:
            flash('No records selected for editing', 'error')
            return redirect(self.get_url('.index_view'))
        
        # Store selected IDs in session
        session['bulk_edit_ids'] = ids
        
        return self.render('admin/bulk_edit_pollingplace.html', ids=ids)
    
    def apply_bulk_edit(self):
        """Apply bulk edit changes"""
        ids = session.pop('bulk_edit_ids', [])
        if not ids:
            flash('No records selected for editing', 'error')
            return redirect(self.get_url('.index_view'))
        
        try:
            records = self.model.query.filter(self.model.id.in_(ids)).all()
            updated_count = 0
            
            for record in records:
                old_values = record.to_dict()
                
                # Update fields if provided
                if request.form.get('state'):
                    record.state = request.form.get('state')
                if request.form.get('county'):
                    record.county = request.form.get('county')
                if request.form.get('source_plugin'):
                    record.source_plugin = request.form.get('source_plugin')
                if request.form.get('polling_hours'):
                    record.polling_hours = request.form.get('polling_hours')
                
                new_values = record.to_dict()
                
                # Create audit entry if changes were made
                if old_values != new_values:
                    changed_fields = [k for k, v in old_values.items() if old_values.get(k) != new_values.get(k)]
                    self.create_audit_entry('UPDATE', record.id, old_values, new_values, changed_fields)
                    updated_count += 1
            
            self.session.commit()
            flash(f'Successfully updated {updated_count} records', 'success')
        except Exception as e:
            self.session.rollback()
            flash(f'Error updating records: {str(e)}', 'error')
        
        return redirect(self.get_url('.index_view'))
    
    def export_csv(self):
        """Export selected records to CSV"""
        ids = request.form.getlist('rowid')
        query = self.model.query
        
        if ids:
            query = query.filter(self.model.id.in_(ids))
        
        records = query.all()
        
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write header
        if records:
            writer.writerow(records[0].to_dict().keys())
        
        # Write data
        for record in records:
            writer.writerow(record.to_dict().values())
        
        output.seek(0)
        return Response(
            output.getvalue(),
            mimetype='text/csv',
            headers={'Content-Disposition': 'attachment; filename=polling_places.csv'}
        )
    
    def export_excel(self):
        """Export selected records to Excel"""
        ids = request.form.getlist('rowid')
        query = self.model.query
        
        if ids:
            query = query.filter(self.model.id.in_(ids))
        
        records = query.all()
        
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        worksheet = workbook.add_worksheet('Polling Places')
        
        # Write header
        if records:
            headers = list(records[0].to_dict().keys())
            for col, header in enumerate(headers):
                worksheet.write(0, col, header)
            
            # Write data
            for row, record in enumerate(records, 1):
                data = record.to_dict()
                for col, value in enumerate(data.values()):
                    worksheet.write(row, col, value)
        
        workbook.close()
        output.seek(0)
        
        return Response(
            output.getvalue(),
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            headers={'Content-Disposition': 'attachment; filename=polling_places.xlsx'}
        )
    
    def create_audit_entry(self, action, record_id, old_values, new_values, changed_fields=None):
        """Create audit trail entry"""
        try:
            from models import AuditTrail
            audit = AuditTrail()
            audit.table_name = 'polling_places'
            audit.record_id = str(record_id)
            audit.action = action
            audit.old_values = json.dumps(old_values) if old_values else None
            audit.new_values = json.dumps(new_values) if new_values else None
            audit.changed_fields = json.dumps(changed_fields) if changed_fields else None
            audit.user_id = current_user.id if current_user.is_authenticated else None
            audit.ip_address = request.remote_addr
            audit.user_agent = request.headers.get('User-Agent')
            self.session.add(audit)
        except Exception as e:
            current_app.logger.error(f"Error creating audit entry: {str(e)}")
    
    def on_model_change(self, form, model, is_created):
        """Override to add audit trail"""
        try:
            if is_created:
                self.create_audit_entry('CREATE', model.id, None, model.to_dict())
            else:
                # Get old values from database
                old_record = self.model.query.get(model.id)
                if old_record:
                    old_values = old_record.to_dict()
                    new_values = model.to_dict()
                    changed_fields = [k for k, v in old_values.items() if old_values.get(k) != new_values.get(k)]
                    if changed_fields:
                        self.create_audit_entry('UPDATE', model.id, old_values, new_values, changed_fields)
        except Exception as e:
            current_app.logger.error(f"Error in audit trail: {str(e)}")
    
    def on_model_delete(self, model):
        """Override to add audit trail for deletions"""
        try:
            self.create_audit_entry('DELETE', model.id, model.to_dict(), None)
        except Exception as e:
            current_app.logger.error(f"Error in audit trail: {str(e)}")

class PrecinctView(SecureModelView):
    """Admin view for Precinct model with bulk operations"""
    
    # Enable bulk operations
    action_disallowed_list = []
    
    column_list = ['id', 'name', 'state', 'county', 'registered_voters', 'current_polling_place', 'changed_recently', 'source_plugin', 'created_at', 'updated_at']
    column_searchable_list = ['name', 'county']
    column_filters = ['state', 'county', 'changed_recently', 'source_plugin', 'created_at']
    column_sortable_list = ['name', 'state', 'county', 'registered_voters', 'created_at']
    form_columns = ['name', 'state', 'county', 'registered_voters', 'current_polling_place', 'last_change_date', 'changed_recently', 'source_plugin']
    
    def _current_polling_place_formatter(self, context, model, name):
        if model.current_polling_place:
            return Markup(f'<a href="/admin/db/pollingplace/edit/?id={model.current_polling_place.id}">{model.current_polling_place.name}</a>')
        return '<span class="text-muted">Not assigned</span>'
    
    column_formatters = {
        'current_polling_place': _current_polling_place_formatter
    }
    
    # Custom actions for bulk operations
    @expose('/action/', methods=['POST'])
    def action_view(self):
        """Handle bulk actions"""
        return self.handle_bulk_action()
    
    def handle_bulk_action(self):
        """Handle bulk delete and edit operations"""
        try:
            if request.form.get('action') == 'delete':
                return self.bulk_delete()
            elif request.form.get('action') == 'bulk_edit':
                return self.bulk_edit_form()
            elif request.form.get('action') == 'apply_bulk_edit':
                return self.apply_bulk_edit()
            elif request.form.get('action') == 'export_csv':
                return self.export_csv()
            elif request.form.get('action') == 'export_excel':
                return self.export_excel()
        except Exception as e:
            flash(f'Error performing bulk action: {str(e)}', 'error')
            return redirect(self.get_url('.index_view'))
    
    def bulk_delete(self):
        """Bulk delete selected records"""
        ids = request.form.getlist('rowid')
        if not ids:
            flash('No records selected for deletion', 'error')
            return redirect(self.get_url('.index_view'))
        
        try:
            # Get records for audit trail
            records = self.model.query.filter(self.model.id.in_(ids)).all()
            
            # Create audit trail entries
            for record in records:
                self.create_audit_entry('DELETE', record.id, None, record.to_dict())
            
            # Delete records
            self.model.query.filter(self.model.id.in_(ids)).delete(synchronize_session=False)
            self.session.commit()
            
            flash(f'Successfully deleted {len(ids)} records', 'success')
        except Exception as e:
            self.session.rollback()
            flash(f'Error deleting records: {str(e)}', 'error')
        
        return redirect(self.get_url('.index_view'))
    
    def bulk_edit_form(self):
        """Show bulk edit form"""
        ids = request.form.getlist('rowid')
        if not ids:
            flash('No records selected for editing', 'error')
            return redirect(self.get_url('.index_view'))
        
        # Store selected IDs in session
        session['bulk_edit_ids'] = ids
        
        return self.render('admin/bulk_edit_precinct.html', ids=ids)
    
    def apply_bulk_edit(self):
        """Apply bulk edit changes"""
        ids = session.pop('bulk_edit_ids', [])
        if not ids:
            flash('No records selected for editing', 'error')
            return redirect(self.get_url('.index_view'))
        
        try:
            records = self.model.query.filter(self.model.id.in_(ids)).all()
            updated_count = 0
            
            for record in records:
                old_values = record.to_dict()
                
                # Update fields if provided
                if request.form.get('state'):
                    record.state = request.form.get('state')
                if request.form.get('county'):
                    record.county = request.form.get('county')
                if request.form.get('source_plugin'):
                    record.source_plugin = request.form.get('source_plugin')
                if request.form.get('changed_recently'):
                    record.changed_recently = request.form.get('changed_recently') == 'true'
                
                new_values = record.to_dict()
                
                # Create audit entry if changes were made
                if old_values != new_values:
                    changed_fields = [k for k, v in old_values.items() if old_values.get(k) != new_values.get(k)]
                    self.create_audit_entry('UPDATE', record.id, old_values, new_values, changed_fields)
                    updated_count += 1
            
            self.session.commit()
            flash(f'Successfully updated {updated_count} records', 'success')
        except Exception as e:
            self.session.rollback()
            flash(f'Error updating records: {str(e)}', 'error')
        
        return redirect(self.get_url('.index_view'))
    
    def export_csv(self):
        """Export selected records to CSV"""
        ids = request.form.getlist('rowid')
        query = self.model.query
        
        if ids:
            query = query.filter(self.model.id.in_(ids))
        
        records = query.all()
        
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write header
        if records:
            writer.writerow(records[0].to_dict().keys())
        
        # Write data
        for record in records:
            writer.writerow(record.to_dict().values())
        
        output.seek(0)
        return Response(
            output.getvalue(),
            mimetype='text/csv',
            headers={'Content-Disposition': 'attachment; filename=precincts.csv'}
        )
    
    def export_excel(self):
        """Export selected records to Excel"""
        ids = request.form.getlist('rowid')
        query = self.model.query
        
        if ids:
            query = query.filter(self.model.id.in_(ids))
        
        records = query.all()
        
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        worksheet = workbook.add_worksheet('Precincts')
        
        # Write header
        if records:
            headers = list(records[0].to_dict().keys())
            for col, header in enumerate(headers):
                worksheet.write(0, col, header)
            
            # Write data
            for row, record in enumerate(records, 1):
                data = record.to_dict()
                for col, value in enumerate(data.values()):
                    worksheet.write(row, col, value)
        
        workbook.close()
        output.seek(0)
        
        return Response(
            output.getvalue(),
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            headers={'Content-Disposition': 'attachment; filename=precincts.xlsx'}
        )
    
    def create_audit_entry(self, action, record_id, old_values, new_values, changed_fields=None):
        """Create audit trail entry"""
        try:
            from models import AuditTrail
            audit = AuditTrail()
            audit.table_name = 'precincts'
            audit.record_id = str(record_id)
            audit.action = action
            audit.old_values = json.dumps(old_values) if old_values else None
            audit.new_values = json.dumps(new_values) if new_values else None
            audit.changed_fields = json.dumps(changed_fields) if changed_fields else None
            audit.user_id = current_user.id if current_user.is_authenticated else None
            audit.ip_address = request.remote_addr
            audit.user_agent = request.headers.get('User-Agent')
            self.session.add(audit)
        except Exception as e:
            current_app.logger.error(f"Error creating audit entry: {str(e)}")
    
    def on_model_change(self, form, model, is_created):
        """Override to add audit trail"""
        try:
            if is_created:
                self.create_audit_entry('CREATE', model.id, None, model.to_dict())
            else:
                # Get old values from database
                old_record = self.model.query.get(model.id)
                if old_record:
                    old_values = old_record.to_dict()
                    new_values = model.to_dict()
                    changed_fields = [k for k, v in old_values.items() if old_values.get(k) != new_values.get(k)]
                    if changed_fields:
                        self.create_audit_entry('UPDATE', model.id, old_values, new_values, changed_fields)
        except Exception as e:
            current_app.logger.error(f"Error in audit trail: {str(e)}")
    
    def on_model_delete(self, model):
        """Override to add audit trail for deletions"""
        try:
            self.create_audit_entry('DELETE', model.id, model.to_dict(), None)
        except Exception as e:
            current_app.logger.error(f"Error in audit trail: {str(e)}")

class ElectionView(SecureModelView):
    """Admin view for Election model"""
    
    column_list = ['id', 'date', 'name', 'state', 'created_at']
    column_searchable_list = ['name', 'state']
    column_filters = ['state', 'date', 'created_at']
    column_sortable_list = ['date', 'name', 'state', 'created_at']
    form_columns = ['date', 'name', 'state']

class PrecinctAssignmentView(SecureModelView):
    """Admin view for PrecinctAssignment model"""
    
    column_list = ['id', 'precinct', 'polling_place', 'election', 'assigned_date', 'removed_date']
    column_searchable_list = ['precinct.name', 'polling_place.name', 'election.name']
    column_filters = ['assigned_date', 'removed_date', 'election']
    column_sortable_list = ['assigned_date', 'removed_date']
    form_columns = ['precinct', 'polling_place', 'election', 'assigned_date', 'removed_date']
    
    def _precinct_formatter(self, context, model, name):
        if model.precinct:
            return Markup(f'<a href="/admin/db/precinct/edit/?id={model.precinct.id}">{model.precinct.name}</a>')
        return '<span class="text-muted">Not specified</span>'
    
    def _polling_place_formatter(self, context, model, name):
        if model.polling_place:
            return Markup(f'<a href="/admin/db/pollingplace/edit/?id={model.polling_place.id}">{model.polling_place.name}</a>')
        return '<span class="text-muted">Not specified</span>'
    
    def _election_formatter(self, context, model, name):
        if model.election:
            return Markup(f'<a href="/admin/db/election/edit/?id={model.election.id}">{model.election.name}</a>')
        return '<span class="text-muted">Not specified</span>'
    
    column_formatters = {
        'precinct': _precinct_formatter,
        'polling_place': _polling_place_formatter,
        'election': _election_formatter
    }

class APIKeyView(SecureModelView):
    """Admin view for APIKey model"""
    
    column_list = ['id', 'name', 'key', 'is_active', 'rate_limit_per_day', 'rate_limit_per_hour', 'created_at', 'last_used_at']
    column_searchable_list = ['name', 'key']
    column_filters = ['is_active', 'created_at', 'last_used_at']
    column_sortable_list = ['name', 'created_at', 'last_used_at']
    form_columns = ['name', 'is_active', 'rate_limit_per_day', 'rate_limit_per_hour']
    
    def _key_formatter(self, context, model, name):
        if model.key:
            return Markup(f'<code style="background: #f4f4f4; padding: 2px 4px; border-radius: 3px; font-size: 11px;">{model.key[:20]}...</code>')
        return ''
    
    def _status_formatter(self, context, model, name):
        if model.is_active:
            return '<span class="label label-success">Active</span>'
        return '<span class="label label-danger">Inactive</span>'
    
    column_formatters = {
        'key': _key_formatter,
        'is_active': _status_formatter
    }

class RecordsView(BaseView):
    """Custom view for record management with advanced search"""
    
    @expose('/')
    def index(self):
        try:
            # Import models here to avoid circular imports
            from app import PollingPlace, Precinct, Election, APIKey, PrecinctAssignment
            
            # Get search parameters
            search_query = request.args.get('search', '').strip()
            state_filter = request.args.get('state', '').strip()
            county_filter = request.args.get('county', '').strip()
            date_from = request.args.get('date_from', '').strip()
            date_to = request.args.get('date_to', '').strip()
            
            # Base queries
            polling_places_query = PollingPlace.query
            precincts_query = Precinct.query
            
            # Apply advanced filters
            if search_query:
                search_pattern = f'%{search_query}%'
                polling_places_query = polling_places_query.filter(
                    or_(
                        PollingPlace.name.ilike(search_pattern),
                        PollingPlace.city.ilike(search_pattern),
                        PollingPlace.county.ilike(search_pattern),
                        PollingPlace.address_line1.ilike(search_pattern)
                    )
                )
                precincts_query = precincts_query.filter(
                    or_(
                        Precinct.name.ilike(search_pattern),
                        Precinct.county.ilike(search_pattern)
                    )
                )
            
            if state_filter:
                polling_places_query = polling_places_query.filter(PollingPlace.state == state_filter)
                precincts_query = precincts_query.filter(Precinct.state == state_filter)
            
            if county_filter:
                polling_places_query = polling_places_query.filter(PollingPlace.county == county_filter)
                precincts_query = precincts_query.filter(Precinct.county == county_filter)
            
            # Get counts
            polling_places_count = polling_places_query.count()
            precincts_count = precincts_query.count()
            elections_count = Election.query.count()
            api_keys_count = APIKey.query.count()
            assignments_count = PrecinctAssignment.query.count()
            
            # Additional statistics
            active_api_keys = APIKey.query.filter_by(is_active=True).count()
            precincts_with_polling_places = Precinct.query.filter(Precinct.current_polling_place_id.isnot(None)).count()
            recent_elections = Election.query.filter(Election.date >= datetime.now().date()).count()
            
            # Get unique states and counties for filter dropdowns
            from flask_sqlalchemy import SQLAlchemy
            states = current_app.extensions['sqlalchemy'].session.query(PollingPlace.state).distinct().all()
            states = [state[0] for state in states if state[0]]
            
            counties = current_app.extensions['sqlalchemy'].session.query(PollingPlace.county).distinct().all()
            counties = [county[0] for county in counties if county[0]]
            counties.sort()
            
            # Pass counts and filters to template
            return self.render('admin/records_index.html',
                             polling_places_count=polling_places_count,
                             precincts_count=precincts_count,
                             elections_count=elections_count,
                             api_keys_count=api_keys_count,
                             assignments_count=assignments_count,
                             active_api_keys=active_api_keys,
                             precincts_with_polling_places=precincts_with_polling_places,
                             recent_elections=recent_elections,
                             states=states,
                             counties=counties,
                             search_query=search_query,
                             state_filter=state_filter,
                             county_filter=county_filter,
                             date_from=date_from,
                             date_to=date_to)
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
                             states=[],
                             counties=[],
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
                             states=[],
                             counties=[],
                             error=f'Error: {str(e)}')

class AuditTrailView(SecureModelView):
    """Admin view for AuditTrail model"""
    
    column_list = ['id', 'table_name', 'record_id', 'action', 'username', 'timestamp', 'ip_address']
    column_searchable_list = ['table_name', 'record_id', 'action']
    column_filters = ['table_name', 'action', 'timestamp', 'user_id']
    column_sortable_list = ['timestamp', 'table_name', 'action']
    form_columns = ['table_name', 'record_id', 'action', 'old_values', 'new_values', 'changed_fields', 'user_id']
    
    def _username_formatter(self, context, model, name):
        # Handle missing relationship by querying AdminUser directly
        if model.user_id:
            try:
                from app import AdminUser
                admin_user = AdminUser.query.get(model.user_id)
                if admin_user:
                    return Markup(f'<a href="/admin/adminuser/edit/?id={admin_user.id}">{admin_user.username}</a>')
            except:
                pass
        return '<span class="text-muted">System</span>'
    
    def _changes_formatter(self, context, model, name):
        if model.changed_fields:
            try:
                changed_fields = json.loads(model.changed_fields)
                return ', '.join(changed_fields)
            except:
                return model.changed_fields
        return '<span class="text-muted">N/A</span>'
    
    column_formatters = {
        'username': _username_formatter,
        'changed_fields': _changes_formatter
    }
    
    # Read-only view for audit trail
    can_create = False
    can_edit = False
    can_delete = False

def init_admin(app, db):
    """Initialize Flask-Admin with custom views"""
    
    # Check if Flask-Admin is already initialized
    if hasattr(app, 'extensions') and 'admin' in app.extensions:
        app.logger.info("Flask-Admin already initialized, returning existing instance")
        return app.extensions['admin']
    
    try:
        # Import models here to avoid circular imports
        from app import PollingPlace, Precinct, Election, PrecinctAssignment, APIKey, AdminUser
        from models import AuditTrail
        
        # Note: AuditTrail relationship handled dynamically to avoid circular import
        
        admin = Admin(
            app, 
            name='CSC Polling Place Admin',
            template_mode='bootstrap3',
            url='/admin/db'
        )
        
        # Add custom index view
        admin.add_view(RecordsView(name='Records Dashboard', endpoint='db_dashboard'))
        
        # Add model views
        admin.add_view(PollingPlaceView(PollingPlace, db.session, name='Polling Places', endpoint='pollingplace'))
        admin.add_view(PrecinctView(Precinct, db.session, name='Precincts', endpoint='precinct'))
        admin.add_view(ElectionView(Election, db.session, name='Elections', endpoint='election'))
        admin.add_view(PrecinctAssignmentView(PrecinctAssignment, db.session, name='Precinct Assignments', endpoint='precinctassignment'))
        admin.add_view(APIKeyView(APIKey, db.session, name='API Keys', endpoint='apikey'))
        admin.add_view(AuditTrailView(AuditTrail, db.session, name='Audit Trail', endpoint='audittrail'))
        
        app.logger.info("Flask-Admin initialized successfully")
        return admin
        
    except Exception as e:
        app.logger.error(f"Failed to initialize Flask-Admin: {e}")
        return None