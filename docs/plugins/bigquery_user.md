# BigQuery Plugin - User Documentation

## What It Does
The BigQuery plugin queries voter registration data from Google BigQuery to provide precinct-level voter counts for any state. It's designed for analysis and planning rather than locating polling places.

## Key Features
- **Voter Count Data**: Provides number of registered voters per precinct
- **State-Specific Queries**: Can query data for any US state
- **Real-Time Data**: Pulls current voter registration numbers from BigQuery
- **Precinct Mapping**: Links voter counts to precinct names and codes

## How to Use
1. **Configure Query**: Set the `BIGQUERY_QUERY_TEMPLATE` environment variable with your SQL query
2. **Set Credentials**: Ensure Google Cloud authentication is configured
3. **Query Data**: Use the plugin to fetch voter counts for a specific state
4. **Analyze Results**: Use the data for voter turnout analysis or resource planning

## Data Provided
- Precinct names and codes
- Number of registered voters per precinct
- State-specific breakdowns

## Benefits
- Access to accurate, up-to-date voter registration data
- Supports election planning and resource allocation
- Enables analysis of voting patterns by precinct
- Integrates with Google Cloud infrastructure

## Requirements
- Google Cloud Project with BigQuery access
- Appropriate credentials (Application Default Credentials or service account)
- Custom SQL query template for your data source
- Access to voter registration datasets

## Supported States
- Configurable for any state with available BigQuery data
- Default template is for Ohio (Catalist data)
- Requires custom query for other states

## Troubleshooting
- Ensure BigQuery API is enabled in your Google Cloud project
- Check that credentials have read access to the datasets
- Verify the query template is correctly formatted
- Monitor BigQuery usage costs for large queries