# Dummy Plugin - Technical Documentation

## Overview
The Dummy plugin generates fake but realistic polling place and precinct data for testing and development purposes. It creates data for all 50 US states.

## Architecture
- **Base Class**: Inherits from `BasePlugin`
- **Data Generation**: Uses random generation with predefined lists
- **Output**: Realistic fake data matching VIP specification
- **Database Integration**: Can sync to database for testing

## Key Methods

### `fetch_polling_places()`
- Generates 100-120 polling places per state
- Uses predefined lists for names, streets, cities
- Creates fake coordinates within US bounds
- Validates data before returning

### `fetch_precincts()`
- Generates 3-8 precincts per polling place
- Simulates precinct reassignment (10% chance per sync)
- Tracks changes in database for realistic testing

### `generate_fake_location(state_code, location_id)`
- Creates individual polling place records
- Includes optional fields like notes and services
- Generates fake but plausible addresses and coordinates

### `generate_fake_coordinates()`
- Returns latitude/longitude within continental US bounds
- Uses random.uniform for realistic distribution

## Data Generation Rules
- **States**: All 50 US states with proper codes
- **Locations**: Random selection from predefined types (schools, centers, etc.)
- **Addresses**: Combines random numbers and street names
- **Cities**: Generated from prefix/suffix combinations
- **Coordinates**: Realistic US bounds (24.5°-49.4° N, 66°-125° W)
- **Polling Hours**: Random times between 6 AM and 9 PM

## Features
- **Change Simulation**: Randomly reassigns precincts on subsequent syncs
- **Validation**: Uses base class validation for data integrity
- **Variety**: Includes optional fields randomly for realism

## Configuration
- No external dependencies or configuration required
- Uses Python random module for generation

## Use Cases
- Testing application functionality
- Development without real data
- Demonstrations and prototypes
- Load testing the database

## Limitations
- Data is entirely fake and not suitable for production
- Coordinates are approximate and not geocoded
- No real-world accuracy or updates