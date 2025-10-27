# Ohio Plugin - Technical Documentation

## Overview
The Ohio plugin fetches polling place and precinct data from Ohio's official CSV file. It supports geocoding using multiple APIs (Census, Google, Mapbox) and handles file uploads for data updates.

## Architecture
- **Base Class**: Inherits from `BasePlugin`
- **Data Source**: CSV file (`ohio.csv`) located in the project root
- **Geocoding**: Multi-API fallback (Census → Google → Mapbox)
- **Database Integration**: Uses SQLAlchemy models for PollingPlace and Precinct

## Key Methods

### `fetch_polling_places()`
- Reads CSV data from `ohio.csv`
- Generates unique polling place IDs using county and sequence numbers
- Checks for existing records and only geocodes new or changed addresses
- Returns list of polling place dictionaries

### `fetch_precincts()`
- Parses precinct data from the same CSV
- Assigns precincts to polling places based on matching keys
- Generates precinct IDs using state and county codes

### `_geocode_addresses(polling_places)`
- Coordinates geocoding process
- Filters valid addresses (requires address_line1, city, zip_code)
- Calls individual geocoding methods in sequence

### `_geocode_census(polling_places)`
- Uses US Census Geocoding API
- Submits batch requests in CSV format
- Parses response and updates latitude/longitude

### `_geocode_google(polling_places)`
- Uses Google Maps Geocoding API (requires API key)
- Processes addresses individually with rate limiting
- Updates coordinates on successful response

### `_geocode_mapbox(polling_places)`
- Uses Mapbox Geocoding API (requires access token)
- Similar to Google method with Mapbox-specific URL format

### `upload_file(file_path)`
- Handles CSV file uploads
- Creates backup of existing file
- Copies new file to `ohio.csv`

## Data Format
CSV columns expected:
- COUNTY NAME
- NAME (polling place name)
- ADDRESS
- CITY
- ZIP CODE
- Precinct Name
- STATE PRECINCT CODE
- COUNTY PRECINCT CODE

## Configuration
- **Environment Variables**:
  - `GOOGLE_GEOCODING_API_KEY`: For Google geocoding
  - `MAPBOX_ACCESS_TOKEN`: For Mapbox geocoding
- **File Path**: `ohio.csv` in project root

## Error Handling
- Logs warnings for missing address data
- Retries failed geocoding requests (up to 3 attempts)
- Continues processing even if some addresses fail to geocode

## Performance Considerations
- Geocoding only new or changed addresses to avoid unnecessary API calls
- Rate limiting (0.1s delay) for Google and Mapbox APIs
- Batch processing for Census API