# Ohio Plugin - User Documentation

## What It Does
The Ohio plugin automatically fetches and updates polling place and precinct data for Ohio from the official state CSV file. It provides accurate, up-to-date information about where Ohio residents can vote, including addresses, coordinates, and precinct assignments.

## Key Features
- **Automatic Data Fetching**: Pulls the latest polling place data from Ohio's official sources
- **Geocoding**: Automatically adds latitude and longitude coordinates for easy mapping
- **Precinct Mapping**: Links precincts to their assigned polling places
- **File Upload Support**: Allows manual upload of updated CSV files
- **Change Detection**: Only updates records when addresses have changed, saving time and API costs

## How to Use
1. **Automatic Sync**: The plugin can be synced automatically or manually through the admin interface
2. **File Upload**: If you have an updated Ohio CSV file, upload it via the admin panel
3. **View Data**: Access the fetched data through the main application interface

## Data Provided
- Polling place names and addresses
- Geographic coordinates (latitude/longitude)
- Precinct assignments and codes
- County information
- Polling hours (if available)

## Benefits
- Ensures Ohio voters have access to current polling locations
- Supports mapping and navigation features
- Maintains historical assignment data for analysis
- Reduces manual data entry through automation

## Requirements
- Ohio CSV file in the correct format
- Optional: Google Geocoding API key or Mapbox access token for enhanced geocoding

## Troubleshooting
- If geocoding fails, check API keys in environment variables
- Ensure CSV file has required columns (County Name, Name, Address, City, ZIP Code, etc.)
- Check admin logs for detailed error messages