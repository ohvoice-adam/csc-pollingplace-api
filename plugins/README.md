# Polling Place Data Plugins

This directory contains state-specific plugins for scraping and importing polling place data into the CSC Polling Place API.

## Overview

Each plugin is responsible for:
1. Fetching polling place data from a specific state's official sources
2. Converting the data to the VIP (Voting Information Project) format
3. Providing the data to the main application for storage and serving

## Creating a New Plugin

To create a new state-specific plugin:

1. Create a new Python file in this directory named after the state (e.g., `california.py`, `texas.py`)

2. Import the base plugin class:
```python
from plugins.base_plugin import BasePlugin
```

3. Create a class that inherits from `BasePlugin`:
```python
class CaliforniaPlugin(BasePlugin):
    @property
    def name(self) -> str:
        return 'california'  # Must match filename

    @property
    def state_code(self) -> str:
        return 'CA'

    @property
    def description(self) -> str:
        return 'California polling place data scraper'

    def fetch_polling_places(self) -> List[Dict[str, Any]]:
        # Your implementation here
        pass
```

4. Implement the `fetch_polling_places()` method to scrape/fetch data from the state's source

See `example_plugin.py` for a complete example.

## Data Format

The `fetch_polling_places()` method should return a list of dictionaries with the following structure:

### Required Fields
- `id` (str): Unique identifier for the polling place
- `name` (str): Name of the polling place
- `city` (str): City name
- `state` (str): Two-letter state code
- `zip_code` (str): ZIP code

### Optional Fields
- `location_name` (str): Specific location name within the address
- `address_line1` (str): Street address
- `address_line2` (str): Apartment, suite, etc.
- `address_line3` (str): Additional address information
- `latitude` (float): Latitude in WGS 84 decimal degrees
- `longitude` (float): Longitude in WGS 84 decimal degrees
- `polling_hours` (str): Hours of operation (e.g., "7:00 AM - 8:00 PM")
- `notes` (str): Additional information, directions, etc.
- `voter_services` (str): Services available at this location
- `start_date` (str): ISO format date (YYYY-MM-DD) when location becomes active
- `end_date` (str): ISO format date (YYYY-MM-DD) when location stops being active

### Example
```python
{
    'id': 'CA-12345',
    'name': 'City Hall',
    'location_name': 'Main Entrance',
    'address_line1': '123 Main Street',
    'city': 'Sacramento',
    'state': 'CA',
    'zip_code': '95814',
    'latitude': 38.5816,
    'longitude': -121.4944,
    'polling_hours': '7:00 AM - 8:00 PM',
    'notes': 'Wheelchair accessible',
    'voter_services': 'Early voting, ballot drop-off',
    'start_date': '2024-10-15',
    'end_date': '2024-11-05'
}
```

## Plugin Discovery

Plugins are automatically discovered and loaded when the application starts. The PluginManager:
1. Scans this directory for Python files
2. Imports each module
3. Instantiates any classes that inherit from `BasePlugin`
4. Verifies the module name matches the plugin's `name` property
5. Makes the plugin available through the API

## Testing Your Plugin

1. Create your plugin file in this directory
2. Restart the application
3. Check that your plugin was loaded:
   ```bash
   curl http://localhost:8080/api/plugins
   ```

4. Trigger a sync:
   ```bash
   curl -X POST http://localhost:8080/api/plugins/your_plugin_name/sync
   ```

5. Verify the data was imported:
   ```bash
   curl http://localhost:8080/api/polling-places?state=XX
   ```

## Best Practices

1. **Error Handling**: Always handle errors gracefully in your `fetch_polling_places()` method
2. **Rate Limiting**: Respect rate limits of the source data provider
3. **Caching**: Consider caching data when appropriate to reduce load on source systems
4. **Logging**: Use `self.app.logger` to log important events and errors
5. **Data Validation**: Use `self.validate_polling_place_data()` to validate data before returning
6. **Unique IDs**: Ensure polling place IDs are unique and stable across syncs

## Common Data Sources

State-specific data sources may include:
- State Secretary of State websites
- County election board websites
- State open data portals
- Official election APIs
- CSV/Excel files published by election authorities

## Troubleshooting

**Plugin not loading:**
- Check that the filename matches the plugin's `name` property
- Verify the class inherits from `BasePlugin`
- Check application logs for error messages

**Sync failing:**
- Check application logs for specific error messages
- Verify the data source is accessible
- Ensure data format matches the expected structure
- Use `validate_polling_place_data()` to check data validity

## Built-in Plugins

### Dummy Plugin

The **Dummy Plugin** (`dummy.py`) is included for testing and development purposes. It generates realistic-looking fake polling place data for all 50 US states.

**Features:**
- Generates 5-15 random polling locations per state
- Creates realistic fake data including:
  - Location names (schools, community centers, libraries, etc.)
  - Addresses with street numbers and names
  - Cities with random prefixes and suffixes
  - Valid US coordinates (latitude/longitude in WGS 84 format)
  - Polling hours with typical opening times
  - Optional notes and voter services
- Validates all generated data before returning
- Perfect for testing API endpoints and integrations

**Usage:**
```bash
# List plugins (should show dummy plugin with state_code='ALL')
curl -H "X-API-Key: your-key" http://localhost:8080/api/plugins

# Sync dummy plugin to generate test data
curl -X POST -H "X-API-Key: your-key" \
  http://localhost:8080/api/plugins/dummy/sync

# View generated data for a specific state
curl -H "X-API-Key: your-key" \
  http://localhost:8080/api/polling-places?state=CA
```

**Note:** The dummy plugin generates new random data each time it syncs. Data is not persistent between syncs unless stored in the database.

### Virginia Plugin

The **Virginia Plugin** (`virginia.py`) fetches comprehensive polling place and precinct data from the Virginia Department of Elections website.

**Features:**
- Multi-election support (General, Presidential Primary, Primary elections)
- Historical data import from all available elections
- Automatic geocoding of polling place addresses
- Precinct-to-polling-place assignment tracking
- Change detection to minimize unnecessary updates

**Documentation:**
- User Guide: [docs/plugins/virginia_user.md](docs/plugins/virginia_user.md)
- Technical Details: [docs/plugins/virginia_technical.md](docs/plugins/virginia_technical.md)

### Ohio Plugin

The **Ohio Plugin** (`ohio.py`) fetches polling place and precinct data from Ohio's official CSV files.

**Features:**
- Automatic data fetching from Ohio state sources
- Geocoding support for mapping functionality
- Precinct mapping and assignment tracking
- File upload support for manual CSV updates
- Change detection to optimize API usage

**Documentation:**
- User Guide: [docs/plugins/ohio_user.md](docs/plugins/ohio_user.md)
- Technical Details: [docs/plugins/ohio_technical.md](docs/plugins/ohio_technical.md)

### BigQuery Plugin

The **BigQuery Plugin** (`bigquery_plugin.py`) queries voter registration data from Google BigQuery for analysis and planning.

**Features:**
- Voter count data per precinct
- State-specific configurable queries
- Real-time data from BigQuery datasets
- Integration with Google Cloud infrastructure

**Documentation:**
- User Guide: [docs/plugins/bigquery_user.md](docs/plugins/bigquery_user.md)
- Technical Details: [docs/plugins/bigquery_technical.md](docs/plugins/bigquery_technical.md)

## Support

For questions or issues with plugins, please open an issue on the GitHub repository.
