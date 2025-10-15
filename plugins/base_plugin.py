"""
Base plugin class for state-specific polling place data scrapers

All state plugins should inherit from this class and implement the required methods.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any
from datetime import datetime


class BasePlugin(ABC):
    """
    Abstract base class for polling place data plugins.

    Each plugin is responsible for scraping/fetching polling place data
    from a specific state's official sources and providing it in a
    standardized format that matches the VIP specification.
    """

    def __init__(self, app, db):
        """
        Initialize the plugin with Flask app and database instances.

        Args:
            app: Flask application instance
            db: SQLAlchemy database instance
        """
        self.app = app
        self.db = db
        self.last_sync = None
        self.sync_count = 0
        self.error_count = 0

    @property
    @abstractmethod
    def name(self) -> str:
        """
        Unique name for this plugin (e.g., 'california', 'texas')
        Should be lowercase and match the module filename.
        """
        pass

    @property
    @abstractmethod
    def state_code(self) -> str:
        """
        Two-letter state code (e.g., 'CA', 'TX')
        """
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """
        Human-readable description of this plugin
        """
        pass

    @abstractmethod
    def fetch_polling_places(self) -> List[Dict[str, Any]]:
        """
        Fetch polling place data from the state's data source.

        This method should scrape, download, or fetch data from official sources
        and return it as a list of dictionaries matching the VIP specification.

        Returns:
            List of dictionaries with polling place data. Each dictionary should contain:
            - id: str - Unique identifier for the polling place
            - name: str - Name of the polling place
            - location_name: str (optional) - Specific location name
            - address_line1: str - Street address
            - address_line2: str (optional) - Apt/Suite/etc
            - address_line3: str (optional) - Additional address info
            - city: str - City name
            - state: str - Two-letter state code
            - zip_code: str - ZIP code
            - latitude: float (optional) - Latitude in WGS 84 decimal degrees
            - longitude: float (optional) - Longitude in WGS 84 decimal degrees
            - polling_hours: str (optional) - Hours of operation
            - notes: str (optional) - Additional information
            - voter_services: str (optional) - Services available
            - start_date: str (optional) - ISO format date (YYYY-MM-DD)
            - end_date: str (optional) - ISO format date (YYYY-MM-DD)

        Raises:
            Exception: If there's an error fetching data
        """
        pass

    def sync(self) -> Dict[str, Any]:
        """
        Sync polling place data from the source to the database.

        This method calls fetch_polling_places() and updates the database.

        Returns:
            Dictionary with sync results:
            - success: bool
            - message: str
            - added: int - Number of new records
            - updated: int - Number of updated records
            - errors: int - Number of errors
            - timestamp: str - ISO format timestamp
        """
        with self.app.app_context():
            try:
                self.app.logger.info(f"Starting sync for plugin: {self.name}")

                # Import here to avoid circular imports
                from app import PollingPlace

                # Fetch data from source
                polling_places_data = self.fetch_polling_places()

                added = 0
                updated = 0
                errors = 0

                for data in polling_places_data:
                    try:
                        # Add source tracking
                        data['source_state'] = self.state_code
                        data['source_plugin'] = self.name

                        # Check if record exists
                        existing = self.db.session.get(PollingPlace, data['id'])

                        if existing:
                            # Update existing record
                            for key, value in data.items():
                                if hasattr(existing, key):
                                    setattr(existing, key, value)
                            updated += 1
                        else:
                            # Create new record
                            new_location = PollingPlace(**data)
                            self.db.session.add(new_location)
                            added += 1

                    except Exception as e:
                        self.app.logger.error(f"Error processing record: {e}")
                        errors += 1
                        self.error_count += 1

                # Commit changes
                self.db.session.commit()

                # Update sync stats
                self.last_sync = datetime.utcnow()
                self.sync_count += 1

                result = {
                    'success': True,
                    'message': f'Successfully synced data for {self.state_code}',
                    'added': added,
                    'updated': updated,
                    'errors': errors,
                    'timestamp': self.last_sync.isoformat()
                }

                self.app.logger.info(f"Sync completed for {self.name}: {result}")
                return result

            except Exception as e:
                self.error_count += 1
                error_msg = f"Error syncing {self.name}: {str(e)}"
                self.app.logger.error(error_msg)
                return {
                    'success': False,
                    'message': error_msg,
                    'added': 0,
                    'updated': 0,
                    'errors': 1,
                    'timestamp': datetime.utcnow().isoformat()
                }

    def get_status(self) -> Dict[str, Any]:
        """
        Get the current status of this plugin.

        Returns:
            Dictionary with plugin status information
        """
        return {
            'name': self.name,
            'state_code': self.state_code,
            'description': self.description,
            'last_sync': self.last_sync.isoformat() if self.last_sync else None,
            'sync_count': self.sync_count,
            'error_count': self.error_count,
            'enabled': True
        }

    def validate_polling_place_data(self, data: Dict[str, Any]) -> bool:
        """
        Validate that polling place data contains required fields.

        Args:
            data: Dictionary with polling place data

        Returns:
            True if valid, False otherwise
        """
        required_fields = ['id', 'name', 'city', 'state', 'zip_code']

        for field in required_fields:
            if field not in data or not data[field]:
                self.app.logger.warning(
                    f"Missing required field '{field}' in polling place data"
                )
                return False

        return True
