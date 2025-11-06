# CI/CD Pipeline

This project includes a comprehensive GitHub Actions workflow for automated testing, security scanning, and deployment.

## 🚀 Features

### Testing & Quality Assurance
- **Multi-Python Testing**: Tests run on Python 3.11 and 3.12
- **PostgreSQL Integration**: Tests use PostgreSQL database service
- **Code Coverage**: Coverage reporting with pytest-cov and Codecov integration
- **Artifact Collection**: Test reports and coverage artifacts are saved

### Code Quality
- **Linting**: Python code linting with flake8
- **Type Checking**: Static type analysis with mypy
- **Security Scanning**: 
  - Bandit for Python security issues
  - Safety for dependency vulnerability scanning
  - Trivy for container and filesystem security scanning

### Deployment
- **Docker Build**: Automated Docker image building with caching
- **Environment-based Deployment**: 
  - Staging deployment for `develop` branch
  - Production deployment for `main` branch
- **Security Integration**: Security scan results uploaded to GitHub Security tab

## 📁 Workflow Files

### `.github/workflows/ci.yml`
Main CI/CD pipeline with the following jobs:

1. **test**: Runs all quality checks and tests
2. **security-scan**: Performs comprehensive security scanning
3. **build**: Builds Docker image and scans it
4. **deploy-staging**: Deploys to staging environment (develop branch)
5. **deploy-production**: Deploys to production (main branch)

## ⚙️ Configuration Files

### `.flake8`
Configures Python linting rules:
- Max line length: 127 characters
- Max complexity: 10
- Excludes common directories and files
- Per-file ignores for specific patterns

### `mypy.ini`
Configures static type checking:
- Python 3.11 target
- Strict type checking enabled
- Import ignore rules for external libraries
- Comprehensive type safety settings

### `.bandit`
Configures security scanning:
- Excludes test directories
- Skips certain test-related security checks

## 🧪 Running Tests Locally

### Install Dependencies
```bash
pip install -r requirements.txt
```

### Run All Checks
```bash
# Lint code
flake8 .

# Type check
mypy --install-types --non-interactive --ignore-missing-imports *.py plugins/ tests/

# Security scan
bandit -r .
safety check

# Run tests with coverage
pytest tests/ --cov=. --cov-report=html --cov-report=term-missing
```

### Individual Commands
```bash
# Run specific test file
pytest tests/test_api_endpoints.py

# Run with specific markers
pytest tests/ -m unit
pytest tests/ -m integration
pytest tests/ -m slow
```

## 📊 Coverage Reports

Coverage reports are generated in multiple formats:
- **HTML**: `htmlcov/index.html` - Interactive HTML report
- **XML**: `coverage.xml` - For CI/CD integration
- **Terminal**: Shows coverage summary in console

## 🔒 Security Scanning

### Bandit (Python Security)
Scans Python code for common security issues:
- Hardcoded passwords
- SQL injection risks
- Insecure deserialization
- Command injection vulnerabilities

### Safety (Dependency Security)
Checks Python dependencies for known vulnerabilities:
- PyPI Security Database
- CVE vulnerability database
- Automatic vulnerability reporting

### Trivy (Container & Filesystem)
Comprehensive security scanner:
- Filesystem vulnerability scanning
- Docker image security analysis
- SARIF format output for GitHub Security integration

## 🚢 Deployment

### Staging Environment
- Triggered on pushes to `develop` branch
- Requires manual approval via GitHub environments
- Deployed to staging infrastructure

### Production Environment
- Triggered on pushes to `main` branch
- Requires manual approval via GitHub environments
- Deployed to production infrastructure

### Environment Variables
The workflow uses environment variables for:
- Database configuration (PostgreSQL for tests)
- API keys and secrets
- Deployment credentials

## 📈 Monitoring & Notifications

### GitHub Security Tab
Security scan results are automatically uploaded to the GitHub Security tab:
- Code scanning results (Bandit, Trivy)
- Dependency scanning results (Safety)
- Container security analysis

### Artifacts
Test artifacts are preserved for 30 days:
- `test-reports-python-version`: Coverage reports, security scan results
- HTML coverage reports for detailed analysis
- JSON reports for programmatic access

## 🛠️ Customization

### Adding New Checks
To add new quality checks:
1. Update the `test` job in `.github/workflows/ci.yml`
2. Add configuration files as needed
3. Update requirements.txt with new tools

### Modifying Deployment
To customize deployment:
1. Update `deploy-staging` and `deploy-production` jobs
2. Configure environment variables in GitHub repository settings
3. Add deployment-specific secrets

### Security Configuration
To modify security scanning:
1. Update `.bandit` for Python security rules
2. Configure Trivy settings in workflow
3. Adjust Safety ignore rules as needed

## 📝 Best Practices

1. **Branch Protection**: Enable branch protection for main/develop branches
2. **Required Checks**: Make CI checks required for pull requests
3. **Secrets Management**: Store sensitive data in GitHub Secrets
4. **Regular Updates**: Keep dependencies and actions up to date
5. **Coverage Targets**: Set minimum coverage thresholds in pytest configuration

## 🔗 Integration with Development Tools

### Pre-commit Hooks
Consider adding pre-commit hooks for local quality checks:
```bash
pip install pre-commit
# Create .pre-commit-config.yaml with flake8, mypy, bandit hooks
pre-commit install
```

### IDE Integration
Most IDEs support these tools:
- **VS Code**: Python extension with flake8, mypy integration
- **PyCharm**: Built-in code inspection and type checking
- **Vim/Neovim**: ALE, coc-python for real-time feedback

## 📚 Additional Resources

- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [pytest Documentation](https://docs.pytest.org/)
- [flake8 Documentation](https://flake8.pycqa.org/)
- [mypy Documentation](https://mypy.readthedocs.io/)
- [Bandit Documentation](https://bandit.readthedocs.io/)
- [Safety Documentation](https://pyup.io/safety/)
- [Trivy Documentation](https://aquasecurity.github.io/trivy/)