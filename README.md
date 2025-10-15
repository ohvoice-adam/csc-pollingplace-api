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

## Deployment to Google Cloud Run

### Prerequisites

- Google Cloud SDK installed
- Google Cloud project created
- Docker installed

### Deploy

1. Build the container:
```bash
gcloud builds submit --tag gcr.io/PROJECT-ID/csc-pollingplace-api
```

2. Deploy to Cloud Run:

   a. With SQLite and volume for persistent storage:
   ```bash
   gcloud run deploy csc-pollingplace-api \
     --image gcr.io/PROJECT-ID/csc-pollingplace-api \
     --platform managed \
     --region us-central1 \
     --allow-unauthenticated \
     --set-env-vars DB_TYPE=sqlite,DEFAULT_ADMIN_PASSWORD=your-secure-password,AUTO_SYNC_ENABLED=True \
     --execution-environment gen2
   ```

   b. With Cloud SQL (recommended for production):
   ```bash
   gcloud run deploy csc-pollingplace-api \
     --image gcr.io/PROJECT-ID/csc-pollingplace-api \
     --platform managed \
     --region us-central1 \
     --allow-unauthenticated \
     --set-env-vars DB_TYPE=postgresql,DB_USER=postgres,DB_PASSWORD=your-password,DB_NAME=pollingplaces,DB_HOST=/cloudsql/PROJECT-ID:REGION:INSTANCE-NAME,DEFAULT_ADMIN_PASSWORD=your-secure-password,AUTO_SYNC_ENABLED=True \
     --add-cloudsql-instances PROJECT-ID:REGION:INSTANCE-NAME \
     --execution-environment gen2
   ```

3. After deployment, access the admin interface:
- Navigate to `https://your-cloud-run-url/admin`
- Login with username `admin` and the password you set
- Change the default password immediately
- Create API keys for your applications

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
- Tracks registered voter counts per precinct

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
- Get all polling places
- Headers: `X-API-Key: <your-key>`
- Query parameters:
  - `state`: Filter by state code (e.g., `?state=CA`)
  - `format`: Response format - `vip` or `standard` (default: `standard`)
- Rate limit: 100/hour

**GET /api/polling-places/:id**
- Get a specific polling place by ID
- Headers: `X-API-Key: <your-key>`
- Query parameters:
  - `format`: Response format - `vip` or `standard` (default: `standard`)
- Rate limit: 100/hour

### Precincts

All endpoints require authentication.

**GET /api/precincts**
- Get all precincts with optional filtering
- Headers: `X-API-Key: <your-key>`
- Query parameters:
  - `state`: Filter by state code (e.g., `?state=CA`)
  - `county`: Filter by county name (e.g., `?county=Alameda`)
  - `changed_recently`: Filter by precincts changed in last 6 months (e.g., `?changed_recently=true`)
- Rate limit: 100/hour

**GET /api/precincts/:id**
- Get a specific precinct with full assignment history
- Headers: `X-API-Key: <your-key>`
- Returns:
  - Precinct details (name, county, registered voters, etc.)
  - Current polling place assignment with full details
  - Complete assignment history showing all polling place changes
  - `changed_recently` flag (true if changed within 6 months)
- Rate limit: 100/hour

**GET /api/polling-places/:id/precincts**
- Get all precincts assigned to a specific polling place
- Headers: `X-API-Key: <your-key>`
- Returns:
  - Polling place details
  - List of all assigned precincts
  - Total count of precincts
  - Total registered voters across all precincts
- Rate limit: 100/hour

### Plugins

All endpoints require authentication.

**GET /api/plugins**
- List all loaded plugins and their status
- Headers: `X-API-Key: <your-key>`
- Rate limit: 50/hour

**POST /api/plugins/:name/sync**
- Trigger a data sync for a specific plugin
- Headers: `X-API-Key: <your-key>`
- Example: `POST /api/plugins/california/sync`
- Rate limit: 10/hour

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

## Data Sources

State-specific plugins can pull data from various sources:
- State Secretary of State websites
- County election board APIs
- State open data portals
- Official CSV/Excel files
- Third-party election data providers

## Contributing

Contributions are welcome! Please feel free to:
- Add new state-specific plugins
- Improve the plugin architecture
- Enhance documentation
- Report issues

Please submit a Pull Request with your changes.

## License

MIT License
