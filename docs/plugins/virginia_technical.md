# Virginia Plugin - Technical Documentation

## Overview
The Virginia plugin fetches polling place and precinct data from Virginia Department of Elections Excel files. It supports multiple election cycles, geocoding, and historical data import.

## Architecture
- **Base Class**: Inherits from `BasePlugin`
- **Data Source**: Excel (.xlsx) files from Virginia elections website
- **Geocoding**: Multi-API fallback (Census → Google → Mapbox)
- **Database Integration**: Uses SQLAlchemy models for PollingPlace, Precinct, and Election

## Key Methods

### `fetch_polling_places()`
- Downloads the most recent election Excel file
- Parses data using pandas
- Generates unique polling place IDs using locality codes
- Checks for existing records and only geocodes new or changed addresses
- Returns list of polling place dictionaries

### `fetch_precincts()`
- Parses precinct data from the same Excel file
- Assigns precincts to polling places
- Generates precinct IDs using locality and precinct numbers

### `_download_excel(url)`
- Downloads Excel file from provided URL
- Uses requests and pandas for parsing
- Handles timeouts and errors

### `_parse_excel_data(df)`
- Processes pandas DataFrame into polling places and precincts
- Normalizes locality names and extracts precinct numbers
- Creates unique keys for polling places

### `_geocode_addresses(polling_places)`
- Coordinates geocoding process (same as Ohio plugin)
- Filters valid addresses
- Calls individual geocoding methods

### `import_historical_data()`
- Imports data from all available elections chronologically
- Creates Election records for each election date
- Syncs polling places and precincts with proper dates

## Data Format
Excel columns expected:
- Locality Name
- Voting Precinct Name
- Location
- Address Line 1
- Address Line 2 (optional)
- City
- Zip Code

## Configuration
- **Election URLs**: Defined in ELECTIONS dictionary with dates as keys
- **Environment Variables**:
  - `GOOGLE_GEOCODING_API_KEY`: For Google geocoding
  - `MAPBOX_ACCESS_TOKEN`: For Mapbox geocoding

## Election Support
Supports multiple election types:
- General Elections (November)
- Presidential Primaries (March)
- Primary Elections (June)

## Error Handling
- Logs warnings for missing data in rows
- Continues processing even if some rows fail
- Handles network timeouts and parsing errors

## Performance Considerations
- Only geocodes new or changed addresses
- Rate limiting for geocoding APIs
- Batch processing for historical imports