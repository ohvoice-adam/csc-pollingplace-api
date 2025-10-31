# Virginia Plugin Test Suite

This directory contains comprehensive tests for the Virginia plugin sync functionality.

## Test Coverage

### Unit Tests (`TestVirginiaFileDiscovery`, `TestVirginiaDataParsing`, `TestVirginiaGeocoding`)
- **File Discovery Methods**: Test web scraping functionality with mock HTTP responses
- **Data Parsing**: Test Excel file parsing and data extraction
- **Geocoding**: Test address geocoding using multiple APIs (Census, Google, Mapbox)

### Integration Tests (`TestVirginiaSyncWorkflow`)
- **Complete Sync Workflow**: End-to-end testing from file selection through database updates
- **Election Record Creation**: Verify proper election record creation and linking
- **Precinct Assignment Linking**: Test precinct-to-polling-place assignment workflow

### Data Validation Tests (`TestVirginiaDataValidation`)
- **Election Date Parsing**: Verify various date formats are correctly parsed
- **Election Name Format**: Ensure election names follow expected patterns
- **Assignment History**: Validate PrecinctAssignment records reference correct election IDs

### Error Scenario Tests (`TestVirginiaErrorScenarios`)
- **Invalid File URLs**: Test handling of 404s and network errors
- **Malformed Excel Files**: Test handling of corrupted or invalid Excel files
- **Database Constraint Violations**: Test handling of duplicate records and constraint errors
- **Missing Data**: Test handling of incomplete or missing required data

## Running Tests

### Using the Test Runner (Recommended)
```bash
# Run all tests
python run_tests.py

# Run only unit tests
python run_tests.py --unit

# Run only integration tests
python run_tests.py --integration

# Run only error scenario tests
python run_tests.py --error

# Run with verbose output
python run_tests.py --verbose
```

### Using unittest directly
```bash
# Run all tests
python -m unittest tests.test_virginia_sync

# Run specific test class
python -m unittest tests.test_virginia_sync.TestVirginiaFileDiscovery

# Run specific test method
python -m unittest tests.test_virginia_sync.TestVirginiaFileDiscovery.test_discover_available_files_success
```

### Using pytest (if installed)
```bash
# Install pytest first
pip install pytest

# Run all tests
pytest tests/

# Run with coverage
pip install pytest-cov
pytest tests/ --cov=plugins.virginia --cov-report=html
```

## Test Structure

### Mock Objects
The tests use Python's `unittest.mock` to create mock objects for:
- HTTP requests (`requests.get`, `requests.post`)
- Database sessions and queries
- External API responses (Census, Google, Mapbox)
- File system operations

### Test Data
Mock data includes:
- Sample HTML responses for web scraping
- Sample Excel data frames for parsing
- Sample API responses for geocoding
- Sample database records for integration testing

### Assertions
Each test includes comprehensive assertions to verify:
- Correct data parsing and transformation
- Proper error handling and logging
- Database operations and transactions
- API request parameters and responses

## Key Test Scenarios

### File Discovery Tests
- Valid HTML with multiple Excel file links
- Empty HTML responses
- Network timeouts and connection errors
- Invalid file formats and non-polling files

### Data Parsing Tests
- Complete Excel files with all required columns
- Files with missing or invalid data
- Different locality and precinct name formats
- Address normalization and validation

### Sync Workflow Tests
- New election creation
- Existing election retrieval
- Polling place and precinct synchronization
- Assignment history tracking

### Error Handling Tests
- Database constraint violations
- Network failures during downloads
- Malformed Excel files
- Invalid date formats in filenames

## Best Practices

### Test Isolation
Each test method is isolated with fresh mock objects to prevent test interference.

### Comprehensive Coverage
Tests cover both success and failure paths for all major functionality.

### Realistic Mock Data
Mock data closely resembles actual Virginia Department of Elections data formats.

### Error Verification
Tests verify that errors are properly logged and handled gracefully.

## Adding New Tests

When adding new functionality to the Virginia plugin:

1. Create corresponding test methods in appropriate test classes
2. Use descriptive test method names following the `test_` prefix
3. Include both positive and negative test cases
4. Mock all external dependencies (HTTP, database, APIs)
5. Add comprehensive assertions for expected behavior
6. Update this README with new test coverage

## Troubleshooting

### Import Errors
Ensure the project root is in the Python path when running tests directly.

### Mock Issues
Check that all external dependencies are properly mocked before running tests.

### Database Tests
Integration tests use mock database sessions - no actual database connection required.

### Network Tests
All network requests are mocked - no internet connection required for testing.