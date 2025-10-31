# Development Guide

This document provides comprehensive information for developers working on the CSC Polling Place API.

## Development Setup

### Prerequisites

- Python 3.11+
- Git
- Docker (optional, for containerized development)
- Google Cloud SDK (for Cloud Run deployment)

### Initial Setup

1. **Clone the repository:**
   ```bash
   git clone <repository-url>
   cd csc-pollingplace-api
   ```

2. **Create virtual environment:**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment:**
   ```bash
   cp .env.example .env
   # Edit .env with your development configuration
   ```

5. **Initialize database:**
   ```bash
   mkdir -p data
   python app.py  # This will create the database and tables
   ```

### Development Workflow

#### Running the Application

```bash
# Development mode with debug enabled
export DEBUG=True
python app.py
```

The application will be available at `http://localhost:8080`

#### Running Tests

```bash
# Run all tests
python run_tests.py

# Run specific test file
pytest tests/test_virginia_sync.py

# Run with coverage
pytest --cov=plugins tests/
```

#### Code Quality

```bash
# Check code style (if flake8 is installed)
flake8 plugins/ app.py models.py

# Type checking (if mypy is installed)
mypy plugins/ app.py models.py
```

## Architecture Overview

### Core Components

1. **Flask Application** (`app.py`): Main application with API endpoints and admin interface
2. **Database Models** (`models.py`): SQLAlchemy models for data persistence
3. **Plugin System** (`plugins/`): Extensible architecture for state-specific data sources
4. **Admin Interface** (`templates/admin/`): Web-based management interface
5. **Configuration** (`.env`, `config.json`): Environment-based configuration

### Plugin Architecture

The plugin system allows for easy extension of state-specific data sources:

- **Base Plugin** (`plugins/base_plugin.py`): Abstract base class defining the plugin interface
- **Plugin Manager** (`plugins/plugin_manager.py`): Handles plugin discovery, loading, and execution
- **State Plugins**: Individual implementations for each state (e.g., `virginia.py`, `ohio.py`)

#### Creating a New Plugin

1. Create a new file in `plugins/` directory
2. Inherit from `BasePlugin`
3. Implement required methods:
   - `name`: Plugin identifier (must match filename)
   - `state_code`: Two-letter state code
   - `description`: Human-readable description
   - `fetch_polling_places()`: Main data fetching method
4. Optionally implement `fetch_precincts()` for precinct data

Example:
```python
from plugins.base_plugin import BasePlugin

class CaliforniaPlugin(BasePlugin):
    @property
    def name(self) -> str:
        return 'california'
    
    @property
    def state_code(self) -> str:
        return 'CA'
    
    @property
    def description(self) -> str:
        return 'California polling place data scraper'
    
    def fetch_polling_places(self) -> List[Dict[str, Any]]:
        # Implementation here
        pass
```

### Database Schema

The application uses SQLAlchemy with the following main models:

- **PollingPlace**: Physical voting locations
- **Precinct**: Voting districts/precincts
- **Assignment**: Historical precinct-to-polling-place assignments
- **Election**: Election information and dates
- **APIKey**: Authentication keys for API access

### API Structure

The REST API follows RESTful conventions:

- **Authentication**: API key via `X-API-Key` header
- **Rate Limiting**: Per-key configurable limits
- **Response Format**: JSON with optional VIP format support
- **Error Handling**: Standard HTTP status codes with JSON error messages

## Development Guidelines

### Code Standards

1. **Python Style**: Follow PEP 8
2. **Type Hints**: Use type hints for all function signatures
3. **Documentation**: Include docstrings for all public functions and classes
4. **Error Handling**: Use proper exception handling with logging
5. **Security**: Validate all inputs and use parameterized queries

### Testing

1. **Unit Tests**: Test individual functions and methods
2. **Integration Tests**: Test plugin functionality and API endpoints
3. **Test Coverage**: Aim for >80% code coverage
4. **Test Data**: Use fixtures and mock data for consistent testing

### Plugin Development

1. **Data Validation**: Use `validate_polling_place_data()` for data validation
2. **Error Handling**: Handle network errors, parsing errors gracefully
3. **Logging**: Use `self.app.logger` for plugin-specific logging
4. **Rate Limiting**: Respect rate limits of external APIs
5. **Caching**: Consider caching data when appropriate

### Security Considerations

1. **API Keys**: Never commit API keys to version control
2. **Input Validation**: Validate all user inputs
3. **SQL Injection**: Use SQLAlchemy ORM or parameterized queries
4. **XSS Prevention**: Escape user-generated content in templates
5. **CSRF Protection**: Use Flask's CSRF protection

## Debugging

### Debug Mode

Enable debug mode for development:
```bash
export DEBUG=True
python app.py
```

Debug mode provides:
- Detailed error pages with stack traces
- Automatic reloading on code changes
- Interactive debugger

### Logging

The application uses Python's logging module:

```python
import logging
logger = logging.getLogger(__name__)

logger.info("Information message")
logger.warning("Warning message")
logger.error("Error message")
```

Log levels:
- `DEBUG`: Detailed information for debugging
- `INFO`: General information about application execution
- `WARNING`: Something unexpected happened
- `ERROR`: Serious problem occurred
- `CRITICAL`: Very serious error

### Common Issues

#### Plugin Not Loading

1. Check that filename matches plugin `name` property
2. Verify the class inherits from `BasePlugin`
3. Check for syntax errors in the plugin file
4. Review application logs for import errors

#### Database Issues

1. Ensure database directory exists and is writable
2. Check database connection string in `.env`
3. Verify database schema is up to date
4. Use health endpoint: `GET /health`

#### API Issues

1. Verify API key is valid and active
2. Check rate limits in admin interface
3. Review request headers and parameters
4. Check application logs for errors

## Performance Optimization

### Database Optimization

1. **Indexing**: Add indexes for frequently queried columns
2. **Query Optimization**: Use SQLAlchemy's query optimization features
3. **Connection Pooling**: Configure connection pooling for PostgreSQL
4. **Caching**: Implement caching for frequently accessed data

### API Performance

1. **Pagination**: Use pagination for large result sets
2. **Caching**: Cache static data and API responses
3. **Compression**: Enable gzip compression for API responses
4. **Rate Limiting**: Implement appropriate rate limits

### Frontend Optimization

1. **Asset Minification**: Minify CSS and JavaScript
2. **Image Optimization**: Compress images and use appropriate formats
3. **Lazy Loading**: Implement lazy loading for large datasets
4. **CDN**: Use CDN for static assets in production

## Deployment

### Local Development

```bash
# Run with SQLite
python app.py

# Run with Docker
docker build -t csc-pollingplace-api .
docker run -p 8080:8080 -v $(pwd)/data:/data csc-pollingplace-api
```

### Production Deployment

See the main README.md for detailed production deployment instructions, including:
- Google Cloud Run deployment
- PostgreSQL/Cloud SQL configuration
- Environment variable setup
- Security considerations

## Contributing

### Pull Request Process

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/your-feature`
3. Make your changes
4. Add tests for new functionality
5. Run tests: `python run_tests.py`
6. Commit your changes with descriptive messages
7. Push to your fork
8. Create a pull request

### Code Review

All pull requests require code review. Reviewers should check:
- Code follows project standards
- Tests are adequate and passing
- Documentation is updated
- Security considerations are addressed
- Performance implications are considered

### Release Process

1. Update version numbers in relevant files
2. Update CHANGELOG.md with new features and fixes
3. Tag the release: `git tag v1.0.0`
4. Push tags: `git push origin --tags`
5. Create release in GitHub interface

## Resources

### Documentation

- [Main README.md](README.md): Project overview and setup
- [Plugin Documentation](plugins/README.md): Plugin development guide
- [UI Documentation](docs/UI_DOCUMENTATION.md): Admin interface guide
- [API Documentation](README.md#api-endpoints): API endpoint reference

### External Dependencies

- [Flask Documentation](https://flask.palletsprojects.com/)
- [SQLAlchemy Documentation](https://docs.sqlalchemy.org/)
- [Flask-Admin Documentation](https://flask-admin.readthedocs.io/)
- [Bootstrap Documentation](https://getbootstrap.com/docs/)
- [Leaflet.js Documentation](https://leafletjs.com/)

### Support

- **Issues**: Report bugs and feature requests on GitHub
- **Discussions**: Use GitHub Discussions for questions
- **Documentation**: Check existing documentation before asking questions
- **Code Review**: Participate in code reviews to improve code quality