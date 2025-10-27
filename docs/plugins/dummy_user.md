# Dummy Plugin - User Documentation

## What It Does
The Dummy plugin generates fake but realistic polling place and precinct data for all 50 US states. It's perfect for testing, development, and demonstrations without using real voter data.

## Key Features
- **Complete US Coverage**: Generates data for all 50 states
- **Realistic Data**: Creates plausible addresses, coordinates, and details
- **Change Simulation**: Randomly reassigns precincts to simulate real-world changes
- **Testing Support**: Provides data for development and testing scenarios
- **No External Dependencies**: Works without internet or external APIs

## How to Use
1. **Enable Plugin**: The plugin is available in the admin interface
2. **Sync Data**: Run a sync to generate fake data for all states
3. **Test Features**: Use the generated data to test application functionality
4. **Repeat Syncs**: Run multiple syncs to see simulated precinct changes

## Data Provided
- Polling places with names, addresses, and coordinates
- Precinct assignments that change over time
- County and state information
- Optional fields like notes and voter services
- Realistic polling hours and accessibility features

## Generated Data Examples
- **Locations**: North Elementary School, Central Community Center
- **Addresses**: 1234 Main St, Springfield, CA 90210
- **Coordinates**: Realistic US latitude/longitude pairs
- **Precincts**: Automatically assigned with simulated changes

## Benefits
- Safe for development and testing environments
- No privacy concerns with fake data
- Helps test application scalability
- Simulates real-world data changes for robust testing

## Use Cases
- **Development**: Build and test features without real data
- **Demonstrations**: Show application capabilities to stakeholders
- **Load Testing**: Generate large datasets for performance testing
- **Training**: Use for user training and onboarding

## Limitations
- Data is entirely fictional and not accurate
- Not suitable for production or public use
- Coordinates are approximate, not precise
- No real-world updates or accuracy

## Best Practices
- Use only in development or testing environments
- Combine with real plugins for comprehensive testing
- Regularly sync to generate new change scenarios