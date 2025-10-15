# CSC Polling Place API

A centralized API for collecting and distributing polling place location data in VIP (Voting Information Project) format, compatible with Google Civic Data API.

## Problem Statement

Organizations that work on predicting and triaging voting issues - such as ID rejections, voter roll purges, and last-minute polling place changes - lack easy, up-to-the-minute, centralized access to collect and distribute this critical information.

## Solution

This API provides a centralized platform to:
- Aggregate polling place location data from multiple states
- Serve data in VIP (Voting Information Project) format
- Provide compatibility with Google Civic Data API
- Enable state-specific data plugins for easy extensibility
- Offer real-time access to polling place information

## Technology Stack

- **Framework**: Flask (Python)
- **Database**: PostgreSQL
- **Deployment**: Google Cloud Run
- **Container**: Docker

## Local Development

### Prerequisites

- Python 3.11+
- PostgreSQL (for local development)
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

4. Set up environment variables:
```bash
cp .env.example .env
# Edit .env with your configuration
```

5. Run the application:
```bash
python app.py
```

The API will be available at `http://localhost:8080`

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
```bash
gcloud run deploy csc-pollingplace-api \
  --image gcr.io/PROJECT-ID/csc-pollingplace-api \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated
```

## Plugin Architecture

This API uses a plugin system to allow state-specific data sources to be easily added. Each plugin:

1. Inherits from the `BasePlugin` class
2. Implements a `fetch_polling_places()` method to scrape/fetch data from the state's source
3. Returns data in VIP-compatible format
4. Is automatically discovered and loaded by the PluginManager

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

## API Endpoints

### Polling Places

**GET /api/polling-places**
- Get all polling places
- Query parameters:
  - `state`: Filter by state code (e.g., `?state=CA`)
  - `format`: Response format - `vip` or `standard` (default: `standard`)

**GET /api/polling-places/:id**
- Get a specific polling place by ID
- Query parameters:
  - `format`: Response format - `vip` or `standard` (default: `standard`)

### Plugins

**GET /api/plugins**
- List all loaded plugins and their status

**POST /api/plugins/:name/sync**
- Trigger a data sync for a specific plugin
- Example: `POST /api/plugins/california/sync`

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
