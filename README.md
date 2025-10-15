# CSC Polling Place API

A centralized API for collecting and distributing real-time information about voting access issues.

## Problem Statement

Organizations that work on predicting and triaging voting issues - such as ID rejections, voter roll purges, and last-minute polling place changes - lack easy, up-to-the-minute, centralized access to collect and distribute this critical information.

## Solution

This API provides a centralized platform to:
- Track polling place changes and closures
- Monitor voter roll updates and purges
- Document ID requirement issues
- Provide real-time access to voting access data

## Technology Stack

- **Framework**: Flask (Python)
- **Database**: PostgreSQL
- **Deployment**: Google Cloud Run
- **Container**: Docker

## Local Development

### Prerequisites

- Python 3.11+
- PostgreSQL (for local development)
- Docker (optional, for containerized development)

### Setup

1. Clone the repository:
```bash
git clone <repository-url>
cd csc-pollingplace-api
```

2. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Set up environment variables:
```bash
cp .env.example .env
# Edit .env with your configuration
```

5. Run the application:
```bash
python app.py
```

The API will be available at `http://localhost:8080`

## Deployment to Google Cloud Run

### Prerequisites

- Google Cloud SDK installed
- Google Cloud project created
- Docker installed

### Deploy

1. Build the container:
```bash
gcloud builds submit --tag gcr.io/PROJECT-ID/csc-pollingplace-api
```

2. Deploy to Cloud Run:
```bash
gcloud run deploy csc-pollingplace-api \
  --image gcr.io/PROJECT-ID/csc-pollingplace-api \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated
```

## API Documentation

API documentation will be available at `/docs` when the application is running.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

MIT License
