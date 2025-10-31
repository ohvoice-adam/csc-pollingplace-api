# CSC Polling Place API - UI Documentation

## Overview

The CSC Polling Place API includes a comprehensive web-based admin interface that provides full control over polling place data, precinct management, plugin configuration, and system administration. The interface is built with Flask and custom HTML templates, featuring a modern, responsive design with a purple/blue color scheme (#667eea).

## Admin Interface Structure

### Main Navigation

The admin interface is organized into several key sections accessible from the main dashboard:

- **Dashboard** - Overview with statistics and quick actions
- **Edit Records** - Full CRUD operations via Flask-Admin integration
- **View Map** - Interactive map visualization of polling places
- **Manage Plugins** - Plugin synchronization and configuration
- **View Logs** - Application log monitoring
- **Geocoding Configuration** - API key management and service priority
- **Bulk Operations** - Mass data management tools
- **User Management** - Password and API key management

## 1. Dashboard (`/admin`)

### Features Overview

The main dashboard provides a comprehensive overview of the system status and quick access to common tasks.

#### Statistics Cards
- **Record Statistics**: Live counts of polling places, precincts, elections, and assignments
- **System Statistics**: Active API keys, precincts with polling places, upcoming elections
- **Data Distribution**: Top states and counties by polling place count

#### Quick Actions Section
- Edit Records
- Manage Plugins  
- View Logs
- Geocoding Priority Configuration
- Geocoding API Keys
- Bulk Delete Operations
- Change Password

#### Recent Activity Monitoring
- **Audit Trail**: Shows recent CREATE, UPDATE, DELETE operations
- **Recently Edited Records**: Quick access to recently modified polling places and precincts
- **Data Distribution Analytics**: Visual breakdown of data by state and county

#### API Key Management
- **Create New Keys**: Form with name, daily/hourly rate limits
- **Key Listing**: All keys with status, usage statistics, last used timestamps
- **Key Actions**: Activate/revoke functionality with confirmation dialogs

### Visual Design
- Grid-based responsive layout
- Color-coded statistics cards
- Interactive data tables with hover effects
- Real-time activity monitoring

## 2. Login Interface (`/admin/login`)

### Security Features
- Clean, centered login form with gradient background
- Session-based authentication with bcrypt password hashing
- Flash message system for login feedback
- Responsive design for mobile devices

### Default Credentials
- Username: `admin`
- Password: `admin123` (or `DEFAULT_ADMIN_PASSWORD` environment variable)
- **Security**: Immediate password change required on first login

## 3. Interactive Map (`/admin/map`)

### Map Functionality
- **Leaflet.js Integration**: OpenStreetMap tiles with custom styling
- **Real-time Data Loading**: Dynamic polling place markers from API
- **Advanced Filtering**: State, county, and dataset filtering
- **Interactive Popups**: Detailed polling place information on click

### Filter Controls
- **State Filter**: Dropdown with all 50 US states
- **County Filter**: Dynamic population based on selected state
- **Dataset Filter**: Toggle between real data and dummy/test data
- **Apply/Reset**: Instant filter application with loading indicators

### Statistics Bar
- Total places count
- Visible places after filtering
- Unique counties represented
- Unique states represented

### Popup Information
- Polling place name and address
- County and city information
- Polling hours
- Notes and voter services
- Direct edit links

### Technical Features
- GeoJSON format for efficient data loading
- Automatic map bounds fitting
- Loading overlays and error handling
- Responsive design for mobile devices

## 4. Plugin Management (`/admin/plugins`)

### Plugin Overview
- **Plugin Discovery**: Automatic loading of all available plugins
- **Status Monitoring**: Last sync timestamps and plugin health
- **Documentation Links**: Direct access to user and technical documentation

### Sync Operations
- **Sync All Real Plugins**: Batch synchronization excluding dummy plugins
- **Individual Plugin Sync**: Per-plugin manual synchronization
- **Virginia Advanced Sync**: Specialized interface for Virginia plugin with file discovery

### Plugin Information Display
- Plugin name and state code
- Description and functionality overview
- Last sync timestamp with timezone handling
- Documentation links (user guide + technical docs)
- Upload capability for supported plugins

### Interactive Features
- Loading indicators for sync operations
- Real-time status updates
- File upload interfaces for compatible plugins
- Error handling and user feedback

## 4.1. Plugin Documentation Viewer (`/admin/plugin-docs`)

### Documentation Access
- **In-App Viewing**: Browse plugin documentation without leaving the admin interface
- **Multiple Formats**: Support for both user guides and technical documentation
- **Plugin-Specific Docs**: Each plugin can have its own documentation files

### Features
- **Markdown Rendering**: Clean display of documentation content
- **Navigation**: Easy switching between different plugin documentation
- **Search**: Quick finding of relevant information within documentation
- **Print Support**: Printable documentation for offline reference

## 4.2. Plugin Upload Interface (`/admin/plugin-upload`)

### File Upload Capabilities
- **Plugin File Upload**: Upload compatible plugin files directly through the web interface
- **Validation**: Automatic validation of uploaded plugin files
- **Installation**: Automatic installation and registration of uploaded plugins

### Supported Features
- **Drag & Drop**: Modern file upload interface with drag-and-drop support
- **Progress Indicators**: Real-time upload progress tracking
- **Error Handling**: Clear error messages for invalid uploads
- **Security**: File type validation and security scanning

## 4.3. Plugin Configuration (`/admin/plugins-config`)

### Configuration Management
- **Plugin Settings**: Configure plugin-specific parameters
- **Environment Variables**: Manage plugin environment variables
- **Service Integration**: Configure external service connections

### Advanced Features
- **Validation**: Real-time validation of configuration values
- **Testing**: Test plugin connections and configurations
- **Backup/Restore**: Save and restore plugin configurations

## 4.4. Virginia Plugin Specialized Interface (`/admin/virginia-sync`)

### Virginia-Specific Features
- **Election Selection**: Choose specific election cycles for data import
- **Historical Data**: Import data from multiple past elections
- **File Discovery**: Automatic discovery of available election files
- **Progress Tracking**: Detailed progress indication for large imports

### Election Management
- **Multi-Election Support**: Handle General, Presidential Primary, and Primary elections
- **Chronological Import**: Import historical data in correct order
- **Data Validation**: Ensure data integrity across election cycles
- **Change Detection**: Identify and highlight changes between elections

## 5. Record Management (Flask-Admin Integration)

### Custom Styling Theme
- **Consistent Branding**: Purple/blue color scheme matching main interface
- **Enhanced UX**: Improved buttons, forms, and table styling
- **Responsive Design**: Mobile-friendly layout adaptations
- **Custom Components**: Styled modals, tooltips, and progress indicators

### Model Views
- **Polling Places**: Full CRUD with geocoding support
- **Precincts**: Management with assignment tracking
- **Elections**: Election data and scheduling
- **API Keys**: Authentication key management
- **Assignments**: Precinct-to-polling-place relationships

### Advanced Features
- **Search Functionality**: Global search across all fields
- **Advanced Filtering**: Multi-criteria filtering with date ranges
- **Bulk Operations**: Mass edit and delete capabilities
- **Export Options**: Multiple format exports (CSV, Excel, JSON)
- **Pagination**: Efficient handling of large datasets
- **Sorting**: Multi-column sorting with visual indicators

### Enhanced UI Elements
- **Tooltips**: Contextual help for complex fields
- **Status Badges**: Visual indicators for record states
- **Action Buttons**: Consistent icon-based actions
- **Breadcrumb Navigation**: Clear navigation hierarchy
- **Recent Activity Sidebar**: Live audit trail display

## 6. Bulk Operations

### 6.1. Bulk Delete Operations (`/admin/bulk-delete`)

#### Safety Features
- **Danger Zone Design**: Red-themed warning interface
- **Multi-step Confirmation**: Dry run → Preview → Confirmation → Execution
- **Large Deletion Protection**: Enhanced confirmation for >1000 records
- **Filter Validation**: Comprehensive filter review before deletion

#### Filter Options
- **Record Types**: Polling places, precincts, assignments, elections
- **Geographic Filters**: State and county filtering
- **Date Range Filters**: Election date ranges and creation date ranges
- **Source Plugin Filter**: Filter by data source plugin

#### Deletion Process
1. **Dry Run**: Preview what will be deleted without execution
2. **Results Review**: Detailed breakdown of records to be deleted
3. **Confirmation**: Type "DELETE" (or "DELETE_LARGE_[count]" for bulk) to confirm
4. **Execution**: Permanent deletion with success/error feedback

#### User Interface
- **Progress Indicators**: Loading spinners during operations
- **Error Handling**: Clear error messages and recovery options
- **Filter Persistence**: Maintain filters during the process
- **Responsive Design**: Mobile-friendly interface

### 6.2. Bulk Edit Operations

#### Bulk Polling Place Editing (`/admin/bulk-edit-pollingplace`)
- **Mass Updates**: Edit multiple polling places simultaneously
- **Field Selection**: Choose which fields to update across selected records
- **Preview Changes**: Review changes before applying them
- **Validation**: Ensure data integrity during bulk updates

#### Bulk Precinct Editing (`/admin/bulk-edit-precinct`)
- **Precinct Management**: Edit multiple precinct records at once
- **Assignment Updates**: Update polling place assignments for multiple precincts
- **Data Validation**: Maintain data consistency across bulk operations
- **Change Tracking**: Track all bulk changes in audit log

### 6.3. Records Management Index (`/admin/records-index`)

#### Centralized Record Access
- **Quick Navigation**: Fast access to all record management interfaces
- **Record Statistics**: Overview of all record types and counts
- **Recent Activity**: Display of recent changes across all record types
- **Quick Actions**: Direct links to common management tasks

#### Features
- **Search Integration**: Global search across all record types
- **Filter Options**: Advanced filtering capabilities
- **Export Tools**: Bulk export functionality for all record types
- **Import Support**: Import interfaces for compatible data formats

## 7. Geocoding Configuration

### Geocoding Priority (`/admin/geocoding-config`)
- **Service Order**: Configure priority of Census, Google, Mapbox services
- **Validation**: Ensures proper service name formatting
- **Real-time Updates**: Immediate configuration changes

### API Key Management (`/admin/geocoding-api-config`)
- **Multiple Services**: Support for various geocoding providers
- **Secure Storage**: Encrypted API key storage
- **Validation**: Key format validation and testing
- **Service Status**: Visual indicators of API key validity

## 8. Application Logs (`/admin/logs`)

### Log Viewing
- **Real-time Logs**: Live application log streaming
- **Syntax Highlighting**: Color-coded log levels (INFO, WARNING, ERROR, DEBUG)
- **Searchable Interface**: Easy log scanning and filtering
- **Responsive Design**: Mobile-friendly log viewing

### Log Features
- **Auto-refresh**: Optional automatic log updates
- **Level Filtering**: Filter by log severity
- **Time-based Navigation**: Jump to specific time periods
- **Export Options**: Download logs for analysis

## 9. Password Management (`/admin/change-password`)

### Security Features
- **Current Password Verification**: Confirm existing password
- **Strength Validation**: Password complexity requirements
- **Confirmation Field**: Prevent typo-related issues
- **Session Update**: Automatic session refresh on change

### User Experience
- **Clear Validation**: Real-time password strength feedback
- **Error Handling**: Descriptive error messages
- **Success Confirmation**: Clear success notification
- **Security Focus**: Emphasis on password security

## 10. Custom CSS Framework

### Design System
- **Color Palette**: Primary (#667eea), secondary (#e0e0e0), success (#28a745), danger (#dc3545)
- **Typography**: System font stack for optimal readability
- **Spacing**: Consistent margin/padding scale
- **Border Radius**: 8px for cards, 4px for form elements

### Component Library
- **Buttons**: Multiple variants with hover states and transitions
- **Cards**: Consistent shadow and border styling
- **Forms**: Enhanced input styling with focus states
- **Tables**: Striped rows with hover effects
- **Alerts**: Color-coded notification system
- **Modals**: Custom styled dialog boxes

### Responsive Design
- **Mobile-first Approach**: Optimized for mobile devices
- **Breakpoints**: 768px for tablet/desktop transitions
- **Grid System**: CSS Grid for complex layouts
- **Touch Targets**: Appropriate sizing for touch interfaces

## 11. JavaScript Enhancements

### Interactive Features
- **Loading States**: Dynamic loading indicators
- **Form Validation**: Real-time client-side validation
- **AJAX Operations**: Asynchronous data loading
- **Error Handling**: Graceful error recovery
- **Tooltips**: Bootstrap tooltip integration

### Performance Optimizations
- **Lazy Loading**: On-demand data loading
- **Caching**: Browser caching for static assets
- **Minification**: Optimized JavaScript delivery
- **Debouncing**: Efficient event handling

## 12. Accessibility Features

### WCAG Compliance
- **Semantic HTML**: Proper heading structure and landmarks
- **Keyboard Navigation**: Full keyboard accessibility
- **Screen Reader Support**: ARIA labels and descriptions
- **Color Contrast**: AA compliance for text readability
- **Focus Indicators**: Clear focus states for navigation

### Usability Features
- **Error Prevention**: Confirmation dialogs for destructive actions
- **Clear Feedback**: Success/error message system
- **Consistent Navigation**: Predictable menu structure
- **Help Text**: Contextual assistance and tooltips

## 13. Security Considerations

### Authentication & Authorization
- **Session Management**: Secure session handling
- **CSRF Protection**: Cross-site request forgery prevention
- **Input Validation**: Server-side validation for all inputs
- **Rate Limiting**: API endpoint protection

### Data Protection
- **Secure Headers**: Proper security headers implementation
- **XSS Prevention**: Output encoding and CSP headers
- **Password Security**: Bcrypt hashing with salt
- **API Key Protection**: Secure key storage and transmission

## 14. Browser Compatibility

### Supported Browsers
- **Modern Browsers**: Chrome 90+, Firefox 88+, Safari 14+, Edge 90+
- **Mobile Support**: iOS Safari 14+, Chrome Mobile 90+
- **Graceful Degradation**: Functional fallbacks for older browsers

### Feature Detection
- **JavaScript**: Progressive enhancement approach
- **CSS**: Feature queries for modern CSS
- **API**: Fallbacks for unsupported browser APIs

## 15. Performance Metrics

### Loading Performance
- **Page Load**: <2 seconds for dashboard
- **Map Loading**: <3 seconds for initial map render
- **Search Response**: <500ms for search results
- **Filter Application**: <1 second for filter updates

### Optimization Techniques
- **Image Optimization**: Compressed images and icons
- **CSS Minification**: Optimized stylesheet delivery
- **JavaScript Bundling**: Efficient script loading
- **Caching Strategy**: Browser and server caching

## 16. Future Enhancements

### Planned Features
- **Dark Mode**: Theme switching capability
- **Advanced Analytics**: Enhanced data visualization
- **Real-time Updates**: WebSocket integration
- **Mobile App**: Native mobile administration app
- **API Documentation**: Integrated API explorer

### Continuous Improvement
- **User Feedback**: Regular user experience surveys
- **Performance Monitoring**: Real-time performance tracking
- **Security Audits**: Regular security assessments
- **Accessibility Testing**: Ongoing accessibility improvements

---

## Technical Implementation Details

### Template Structure
```
templates/admin/
├── dashboard.html              # Main dashboard
├── login.html                  # Login interface
├── map.html                    # Interactive map
├── plugins.html                # Plugin management
├── plugin_docs.html            # Plugin documentation viewer
├── plugin_upload.html          # Plugin file upload interface
├── plugins_config.html         # Plugin configuration management
├── virginia_sync.html          # Virginia plugin specialized sync
├── bulk_delete_pollingplaces.html  # Bulk operations
├── bulk_edit_pollingplace.html # Bulk polling place editing
├── bulk_edit_precinct.html     # Bulk precinct editing
├── geocoding_config.html       # Geocoding settings
├── geocoding_api_config.html   # Geocoding API key management
├── logs.html                   # Log viewing
├── change_password.html        # Password management
├── records_index.html          # Records management index
└── flask_admin/               # Flask-Admin templates
    ├── base.html              # Base template with custom styling
    ├── model/
    │   ├── list.html          # Record listing with enhancements
    │   ├── edit.html          # Record editing forms
    │   └── create.html        # Record creation forms
    └── index.html             # Flask-Admin index
```

### Static Assets
```
static/
└── css/
    └── flask_admin_custom.css  # Custom styling for Flask-Admin
```

### Key Technologies
- **Frontend**: HTML5, CSS3, JavaScript (ES6+)
- **Frameworks**: Flask, Flask-Admin, Bootstrap 5
- **Maps**: Leaflet.js, OpenStreetMap
- **Icons**: Font Awesome 6
- **Fonts**: System font stack
- **Validation**: Client-side and server-side validation

This documentation provides a comprehensive overview of the UI features and capabilities of the CSC Polling Place API admin interface. The interface is designed to be intuitive, efficient, and accessible while providing powerful tools for managing polling place data and system administration.