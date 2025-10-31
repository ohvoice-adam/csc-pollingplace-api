# CSC Polling Place API

A centralized API for collecting and distributing polling place location data in VIP (Voting Information Project) format, compatible with Google Civic Data API.

## Problem Statement

Organizations that work on predicting and triaging voting issues - such as ID rejections, voter roll purges, and last-minute polling place changes - lack easy, up-to-the-minute, centralized access to collect and distribute this critical information.

## Solution

This API provides a centralized platform to:
- Aggregate polling place location data from multiple states
- Track voting precincts and their polling place assignments
- Monitor and flag polling place changes for precincts (with 6-month change detection)
- Maintain complete historical records of precinct-to-polling-place assignments
- Store registered voter counts per precinct
- Serve data in VIP (Voting Information Project) format
- Provide compatibility with Google Civic Data API
- Enable state-specific data plugins for easy extensibility
- Offer real-time access to polling place and precinct information

## Technology Stack

- **Framework**: Flask (Python)
- **Database**: SQLite (embedded, persistent storage via Docker volume)
- **Authentication**: API Key-based with rate limiting
- **Scheduling**: APScheduler for automated plugin syncs
- **Deployment**: Google Cloud Run
- **Container**: Docker

## Local Development

### Prerequisites

- Python 3.11+
- Docker (optional, for containerized development)

### Setup

1. Clone the repository:
```bash
git clone <repository-url>
cd csc-pollingplace-api
```

2. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Create data directory for database:
```bash
mkdir -p /data
# Or use a local directory: mkdir -p ./data
```

5. Set up environment variables:
```bash
cp .env.example .env
# Edit .env with your configuration
```

6. Generate a master API key:
```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
# Copy the output and add it to .env as MASTER_API_KEY
```

7. Run the application:
```bash
python app.py
```

The API will be available at `http://localhost:8080`

8. Access the admin interface:
- Open your browser to `http://localhost:8080/admin`
- Login with username: `admin` and password: `admin123` (or your configured DEFAULT_ADMIN_PASSWORD)
- **IMPORTANT**: Change the default password immediately at `/admin/change-password`
- Create API keys through the web interface

## Deployment Guide

### Prerequisites

- Python 3.11+
- Docker (for containerized deployment)
- Google Cloud SDK (for Cloud Run deployment)
- Google Cloud project (for Cloud Run)

### Local Development Deployment

1. **Setup Environment:**
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

2. **Run with SQLite:**
   ```bash
   mkdir -p data
   python app.py
   ```
   Access at `http://localhost:8080`

3. **Run with Docker:**
   ```bash
   docker build -t csc-pollingplace-api .
   docker run -d -p 8080:8080 \
     -v $(pwd)/data:/data \
     -e DB_TYPE=sqlite \
     -e MASTER_API_KEY=your-secure-key \
     -e AUTO_SYNC_ENABLED=True \
     csc-pollingplace-api
   ```

### Google Cloud Run Deployment

1. **Build and Push Container:**
   ```bash
   gcloud builds submit --tag gcr.io/PROJECT-ID/csc-pollingplace-api
   ```

2. **Deploy with SQLite:**
   ```bash
   gcloud run deploy csc-pollingplace-api \
     --image gcr.io/PROJECT-ID/csc-pollingplace-api \
     --platform managed \
     --region us-central1 \
     --allow-unauthenticated \
     --set-env-vars DB_TYPE=sqlite,DEFAULT_ADMIN_PASSWORD=your-secure-password,AUTO_SYNC_ENABLED=True \
     --execution-environment gen2
   ```

3. **Deploy with Cloud SQL (Recommended for Production):**
   ```bash
   # First, create a Cloud SQL instance and database
   gcloud sql instances create pollingplace-db --tier=db-f1-micro --region=us-central1
   gcloud sql databases create pollingplaces --instance=pollingplace-db
   gcloud sql users set-password postgres --host=% --instance=pollingplace-db --password=your-password

   # Then deploy
   gcloud run deploy csc-pollingplace-api \
     --image gcr.io/PROJECT-ID/csc-pollingplace-api \
     --platform managed \
     --region us-central1 \
     --allow-unauthenticated \
     --set-env-vars DB_TYPE=postgresql,DB_USER=postgres,DB_PASSWORD=your-password,DB_NAME=pollingplaces,DB_HOST=/cloudsql/PROJECT-ID:us-central1:pollingplace-db,DEFAULT_ADMIN_PASSWORD=your-secure-password,AUTO_SYNC_ENABLED=True \
     --add-cloudsql-instances PROJECT-ID:us-central1:pollingplace-db \
     --execution-environment gen2
   ```

4. **Post-Deployment Steps:**
   - Access the admin interface at `https://your-cloud-run-url/admin`
   - Login with username `admin` and the password you set
   - Immediately change the default password at `/admin/change-password`
   - Create API keys through the web interface
   - Test the API: `curl https://your-cloud-run-url/api/polling-places?state=CA&dataset=dummy`

### Environment Variables

Required environment variables:
- `DB_TYPE`: `sqlite` or `postgresql`
- `MASTER_API_KEY`: Secure key for creating API keys
- `DEFAULT_ADMIN_PASSWORD`: Admin interface password (change immediately)
- `AUTO_SYNC_ENABLED`: `True` to enable automated plugin syncing
- `SYNC_INTERVAL_HOURS`: Hours between syncs (default: 24)

For PostgreSQL/Cloud SQL:
- `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_NAME`, `DB_PORT`

### Monitoring and Maintenance

- Monitor application logs in Cloud Run console
- Set up alerts for sync failures
- Regularly update dependencies: `pip install -u -r requirements.txt`
- Backup database regularly (especially for SQLite)

### Database Configuration

The API supports both SQLite (default) and PostgreSQL/Cloud SQL databases:

#### SQLite (Default)
```bash
# In your .env file
DB_TYPE=sqlite
SQLITE_PATH=/data/pollingplaces.db
```

#### PostgreSQL or Cloud SQL
```bash
# In your .env file
DB_TYPE=postgresql
DB_USER=postgres
DB_PASSWORD=your_password_here
DB_HOST=localhost
DB_PORT=5432
DB_NAME=pollingplaces

# For Cloud SQL with Unix socket
DB_HOST=/cloudsql/PROJECT_ID:REGION:INSTANCE_NAME
```

**Note for Cloud Run**: While Cloud Run Gen2 supports volume mounting for SQLite, using Cloud SQL is recommended for production deployments for better scalability and reliability.

### Docker Deployment

Run locally with Docker:

1. With SQLite (default):
```bash
docker build -t csc-pollingplace-api .
docker run -d -p 8080:8080 \
  -v $(pwd)/data:/data \
  -e DB_TYPE=sqlite \
  -e MASTER_API_KEY=your-secure-key \
  -e AUTO_SYNC_ENABLED=True \
  csc-pollingplace-api
```

2. With PostgreSQL:
```bash
docker build -t csc-pollingplace-api .
docker run -d -p 8080:8080 \
  -e DB_TYPE=postgresql \
  -e DB_USER=postgres \
  -e DB_PASSWORD=your-password \
  -e DB_HOST=host.docker.internal \
  -e DB_PORT=5432 \
  -e DB_NAME=pollingplaces \
  -e MASTER_API_KEY=your-secure-key \
  -e AUTO_SYNC_ENABLED=True \
  csc-pollingplace-api
```

Note: When using PostgreSQL, make sure the database exists and is accessible from the container.

## Plugin Architecture

This API uses a plugin system to allow state-specific data sources to be easily added. Each plugin:

1. Inherits from the `BasePlugin` class
2. Implements a `fetch_polling_places()` method to scrape/fetch data from the state's source
3. Optionally implements a `fetch_precincts()` method to provide precinct data and assignments
4. Returns data in VIP-compatible format
5. Is automatically discovered and loaded by the PluginManager

### Precinct Tracking

When a plugin implements `fetch_precincts()`, the API automatically:
- Detects when a precinct's polling place assignment has changed
- Creates a historical record of the change
- Flags precincts that have changed within the last 6 months
- Maintains a complete audit trail of all assignment changes

### Creating a Plugin

See [plugins/README.md](plugins/README.md) for detailed instructions on creating state-specific plugins.

Quick example:

```python
from plugins.base_plugin import BasePlugin

class CaliforniaPlugin(BasePlugin):
    @property
    def name(self) -> str:
        return 'california'

    @property
    def state_code(self) -> str:
        return 'CA'

    @property
    def description(self) -> str:
        return 'California polling place data scraper'

    def fetch_polling_places(self) -> List[Dict[str, Any]]:
        # Fetch and return polling place data
        pass
```

Save this as `plugins/california.py` and it will be automatically loaded.

## Admin Interface

The API includes a web-based admin interface for managing API keys without needing command-line access.

### First-Time Setup

On first run, a default admin account is automatically created:
- **Username**: `admin`
- **Password**: `admin123` (or value of `DEFAULT_ADMIN_PASSWORD` env var)

**🔒 IMPORTANT**: Change the default password immediately after first login at `/admin/change-password`

### Accessing the Admin Panel

1. Navigate to `http://your-domain/admin` in your browser
2. Login with admin credentials
3. From the dashboard you can:
   - Create new API keys with custom rate limits
   - View all API keys and their usage statistics
   - Revoke or reactivate API keys
   - Change your admin password

### Features

- **No Console Access Needed**: Perfect for Cloud Run deployments
- **User-Friendly Interface**: Simple web UI for key management
- **Secure**: Password hashing with bcrypt, session-based authentication
- **Audit Trail**: Track key creation, last used timestamps

## Authentication

All API endpoints (except health checks and admin interface) require authentication via API key.

### Getting Started

1. Login to the admin interface at `/admin`
2. Create API keys through the web dashboard
3. Include API key in requests via `X-API-Key` header
4. Rate limits apply per API key

### Example Request
```bash
curl -H "X-API-Key: your-api-key-here" \
  http://localhost:8080/api/polling-places?state=CA&format=vip
```

## Rate Limiting

**Default**: API keys have **unlimited (infinite) rate limits** unless specific limits are set.

When creating API keys, you can optionally set custom rate limits:
- **rate_limit_per_day**: Maximum requests per day (e.g., 1000)
- **rate_limit_per_hour**: Maximum requests per hour (e.g., 100)

If no limits are specified for an API key, it will have infinite access to all endpoints.

**Note**: API key management endpoints (create, list, revoke) have no rate limits and are not affected by per-key settings.

## Automated Scheduling

Enable automated syncing of all plugins by setting environment variables:
```bash
AUTO_SYNC_ENABLED=True
SYNC_INTERVAL_HOURS=24  # Default: sync every 24 hours
```

When enabled, all state plugins will automatically sync on the specified interval.

## API Endpoints

### Authentication & API Keys

All API endpoints (except health checks and admin interface) require authentication via API key provided in the `X-API-Key` header.

**POST /api/keys**
- Create a new API key (requires master API key)
- Headers: `X-API-Key: <master-key>`
- Body: `{"name": "Description", "rate_limit_per_day": 500, "rate_limit_per_hour": 100}`
- Returns: New API key details
- No rate limit

**GET /api/keys**
- List all API keys (requires valid API key)
- Headers: `X-API-Key: <your-key>`
- No rate limit

**DELETE /api/keys/:id**
- Revoke an API key (requires valid API key)
- Headers: `X-API-Key: <your-key>`
- No rate limit

### Polling Places

All endpoints require authentication.

**GET /api/polling-places**
- Get polling places for a specific state
- Headers: `X-API-Key: <your-key>`
- Query parameters:
  - `state` (required): Filter by state code (e.g., `?state=CA`)
  - `format`: Response format - `vip` or `standard` (default: `standard`)
  - `dataset`: Data source - `dummy` for test data (default: real plugin data)
- Rate limit: 100/hour
- Example: `curl -H "X-API-Key: your-key" "http://localhost:8080/api/polling-places?state=CA&format=vip"`

**GET /api/polling-places/:id**
- Get a specific polling place by ID
- Headers: `X-API-Key: <your-key>`
- Query parameters:
  - `format`: Response format - `vip` or `standard` (default: `standard`)
- Rate limit: 100/hour
- Example: `curl -H "X-API-Key: your-key" "http://localhost:8080/api/polling-places/CA-12345"`

### Precincts

All endpoints require authentication.

**GET /api/precincts**
- Get precincts for a specific state with optional filtering
- Headers: `X-API-Key: <your-key>`
- Query parameters:
  - `state` (required): Filter by state code (e.g., `?state=CA`)
  - `county`: Filter by county name (e.g., `?county=Alameda`)
  - `changed_recently`: Filter by precincts changed in last 6 months (e.g., `?changed_recently=true`)
  - `dataset`: Data source - `dummy` for test data (default: real plugin data)
- Rate limit: 100/hour
- Example: `curl -H "X-API-Key: your-key" "http://localhost:8080/api/precincts?state=CA&changed_recently=true"`

**GET /api/precincts/:id**
- Get a specific precinct with full assignment history
- Headers: `X-API-Key: <your-key>`
- Returns:
  - Precinct details (name, county, registered voters, etc.)
  - Current polling place assignment with full details
  - Complete assignment history showing all polling place changes
  - `changed_recently` flag (true if changed within 6 months)
- Rate limit: 100/hour
- Example: `curl -H "X-API-Key: your-key" "http://localhost:8080/api/precincts/CA-ALAMEDA-0001"`

**GET /api/polling-places/:id/precincts**
- Get all precincts assigned to a specific polling place
- Headers: `X-API-Key: <your-key>`
- Returns:
  - Polling place details
  - List of all assigned precincts
  - Total count of precincts
  - Total registered voters across all precincts
- Rate limit: 100/hour
- Example: `curl -H "X-API-Key: your-key" "http://localhost:8080/api/polling-places/CA-12345/precincts"`

### Plugins

All endpoints require authentication.

**GET /api/plugins**
- List all loaded plugins and their status
- Headers: `X-API-Key: <your-key>`
- Rate limit: 50/hour
- Example: `curl -H "X-API-Key: your-key" "http://localhost:8080/api/plugins"`

**POST /api/plugins/:name/sync**
- Trigger a data sync for a specific plugin
- Headers: `X-API-Key: <your-key>`
- Rate limit: 10/hour
- Example: `curl -X POST -H "X-API-Key: your-key" "http://localhost:8080/api/plugins/california/sync"`

**POST /api/plugins/:name/import-historical**
- Trigger historical data import for a plugin (if supported)
- Headers: `X-API-Key: <your-key>`
- Rate limit: 10/hour
- Example: `curl -X POST -H "X-API-Key: your-key" "http://localhost:8080/api/plugins/california/import-historical"`

### Elections

All endpoints require authentication.

**GET /api/elections**
- Get list of elections with optional filtering
- Headers: `X-API-Key: <your-key>`
- Query parameters:
  - `state`: Filter by state code (e.g., `?state=CA`)
  - `year`: Filter by year (e.g., `?year=2024`)
- Rate limit: 100/hour
- Example: `curl -H "X-API-Key: your-key" "http://localhost:8080/api/elections?year=2024"`

**GET /api/elections/:id**
- Get a specific election with statistics
- Headers: `X-API-Key: <your-key>`
- Rate limit: 100/hour
- Example: `curl -H "X-API-Key: your-key" "http://localhost:8080/api/elections/1"`

**GET /api/elections/:id/precincts**
- Get precincts as assigned in a specific election
- Headers: `X-API-Key: <your-key>`
- Query parameters:
  - `county`: Filter by county
- Rate limit: 100/hour
- Example: `curl -H "X-API-Key: your-key" "http://localhost:8080/api/elections/1/precincts"`

### Bulk Operations

All endpoints require authentication.

**POST /api/bulk-delete**
- Bulk delete polling places, precincts, assignments, and/or elections with filtering options
- Headers: `X-API-Key: <your-key>`
- Body: 
  ```json
  {
    "delete_types": ["polling_places", "precincts", "assignments", "elections"],
    "filters": {
      "state": "OH",
      "start_date": "2024-01-01",
      "end_date": "2024-12-31",
      "created_after": "2024-01-01",
      "created_before": "2024-12-31",
      "source_plugin": "ohio"
    },
    "dry_run": true,
    "confirm": "DELETE"
  }
  ```
- Rate limit: 10/hour
- Example: `curl -X POST -H "X-API-Key: your-key" -H "Content-Type: application/json" -d '{"delete_types":["assignments","elections"],"filters":{"state":"OH"},"dry_run":true}' "http://localhost:8080/api/bulk-delete"`
- Notes: 
  - Always perform a dry run first to review what will be deleted
  - Requires explicit "DELETE" confirmation for actual deletion
  - Supports deleting any combination of record types simultaneously
  - Polling places support date range filtering (start_date, end_date)
  - All types support creation date filtering and source plugin filtering
  - Assignments can be filtered by state through their precinct relationship
  - Large deletions (>1000 records) require enhanced confirmation: `DELETE_LARGE_[count]`

### VIP Format Example

When requesting data with `?format=vip`, the response follows the Voting Information Project specification:

```json
{
  "pollingLocations": [
    {
      "id": "CA-12345",
      "name": "City Hall",
      "address": {
        "locationName": "Main Entrance",
        "line1": "123 Main Street",
        "city": "Sacramento",
        "state": "CA",
        "zip": "95814"
      },
      "pollingHours": "7:00 AM - 8:00 PM",
      "latitude": 38.5816,
      "longitude": -121.4944,
      "notes": "Wheelchair accessible"
    }
  ]
}
```

### Error Responses

All endpoints return standard HTTP status codes and JSON error messages:

- `400 Bad Request`: Invalid request parameters
- `401 Unauthorized`: Missing or invalid API key
- `404 Not Found`: Resource not found
- `429 Too Many Requests`: Rate limit exceeded
- `500 Internal Server Error`: Server error

Example error response:
```json
{
  "error": "State parameter is required. Use ?state=VA (or other state code). Add dataset=dummy for test data."
}
```

## Data Sources

State-specific plugins can pull data from various sources:
- State Secretary of State websites
- County election board APIs
- State open data portals
- Official CSV/Excel files
- Third-party election data providers

### Supported States

Currently implemented plugins:
- **Dummy Plugin**: Generates test data for all 50 US states
- **Virginia Plugin**: Scrapes data from Virginia Department of Elections
- **BigQuery Plugin**: Queries voter data from Google BigQuery (configurable for any state)

To add support for a new state, create a plugin following the guide in `plugins/README.md`.

## Troubleshooting

### Common Issues

**Application won't start:**
- Ensure all dependencies are installed: `pip install -r requirements.txt`
- Check that environment variables are set (see `.env.example`)
- Verify database path exists and is writable for SQLite

**API key authentication fails:**
- Confirm API key is active and provided in `X-API-Key` header
- Check admin interface for key status
- Ensure key has not exceeded rate limits

**Plugin not loading:**
- Verify plugin file name matches the `name` property
- Check application logs for import errors
- Ensure plugin inherits from `BasePlugin`

**Sync failing:**
- Review application logs for specific errors
- Confirm data source is accessible
- Validate data format in plugin's `fetch_polling_places()` method

**Database connection issues:**
- For SQLite: Ensure `/data` directory exists and is writable
- For PostgreSQL: Verify connection string and credentials
- Check health endpoint: `GET /health`

**Rate limiting errors:**
- Check your API key's rate limits in the admin interface
- Wait before retrying or request higher limits

### Logs and Debugging

- Application logs are written to stdout/stderr
- Enable debug mode: Set `DEBUG=True` in environment variables
- Check database logs for SQL errors
- Use the health endpoint to verify database connectivity

## Contributing

Contributions are welcome! Please feel free to:
- Add new state-specific plugins
- Improve the plugin architecture
- Enhance documentation
- Report issues

### Development Setup

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/your-feature`
3. Make your changes
4. Run tests (if applicable)
5. Submit a Pull Request with a clear description

### Code Style

- Follow PEP 8 for Python code
- Use type hints where appropriate
- Add docstrings to new functions and classes
- Ensure all new code is covered by tests

## License

MIT License
