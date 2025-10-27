# Virginia Plugin - User Documentation

## What It Does
The Virginia plugin automatically fetches and updates polling place and precinct data for Virginia from the official Department of Elections website. It supports multiple election cycles and provides comprehensive historical data.

## Key Features
- **Multi-Election Support**: Fetches data from General Elections, Presidential Primaries, and Primary Elections
- **Historical Data Import**: Imports data from all available elections chronologically
- **Automatic Geocoding**: Adds latitude and longitude coordinates for mapping
- **Precinct Mapping**: Links precincts to their assigned polling places
- **Change Detection**: Only updates records when data has changed

## How to Use
1. **Automatic Sync**: Sync the plugin through the admin interface to get the latest data
2. **Historical Import**: Use the import function to load data from past elections
3. **View Data**: Access the data through the main application interface

## Data Provided
- Polling place names, addresses, and locations
- Geographic coordinates (latitude/longitude)
- Precinct assignments and codes
- Locality (county/city) information
- Election-specific data with dates

## Supported Elections
- **General Elections**: November elections (e.g., 2024 General)
- **Presidential Primaries**: March elections (e.g., 2024 Presidential Primary)
- **Primary Elections**: June elections (e.g., 2024 Primary)

## Benefits
- Provides comprehensive Virginia voting location data
- Supports historical analysis of polling place changes
- Enables accurate mapping and navigation
- Maintains election-specific assignment records

## Requirements
- Internet connection to download Excel files from Virginia elections website
- Optional: Google Geocoding API key or Mapbox access token for geocoding

## Troubleshooting
- Ensure internet connectivity for downloading files
- Check admin logs for download or parsing errors
- Verify that election URLs are accessible and up-to-date