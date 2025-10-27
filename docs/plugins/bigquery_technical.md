# BigQuery Plugin - Technical Documentation

## Overview
The BigQuery plugin queries Google BigQuery for voter registration data by state. It returns precinct-level voter counts rather than polling place locations.

## Architecture
- **Base Class**: Inherits from `BasePlugin`
- **Data Source**: Google BigQuery datasets
- **Authentication**: Uses Google Cloud credentials (application default or environment)
- **Output**: Dictionary mapping precinct keys to voter counts

## Key Methods

### `fetch_polling_places(state_code='OH')`
- Note: Overrides base method but returns Dict instead of List
- Connects to BigQuery client
- Executes parameterized query for specified state
- Returns dictionary of precinct names to voter counts

### `connect_to_bigquery()`
- Initializes BigQuery client if not already connected
- Uses google-cloud-bigquery library

### `get_voter_data_by_state(state_code='OH')`
- Public interface method
- Calls fetch_polling_places internally

## Query Template
Uses environment variable `BIGQUERY_QUERY_TEMPLATE` with placeholder for state_code.

Default query:
```sql
SELECT
    precinctname,
    precinctcode,
    COUNT(DISTINCT(p.dwid)) as registered
FROM `prod-sv-oh-dd7a76f2.catalist_OH.Person` p
LEFT JOIN `prod-sv-oh-dd7a76f2.catalist_OH.District` d
    ON p.dwid = d.dwid
    AND p.voterstatus = 'active'
    AND d.state = '{state_code}'
GROUP BY 1,2
```

## Configuration
- **Environment Variables**:
  - `BIGQUERY_QUERY_TEMPLATE`: SQL query template with {state_code} placeholder
- **Authentication**: Google Cloud credentials (ADC or service account key)

## Limitations
- Does not provide polling place locations, only voter counts
- Requires access to specific BigQuery datasets
- State-specific query templates needed for non-Ohio states

## Error Handling
- Logs errors and raises exceptions on query failures
- Handles authentication and network issues

## Performance Considerations
- Queries can be expensive for large states
- Results are not cached; each call executes a new query