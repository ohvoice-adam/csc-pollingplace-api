"""
Base plugin class for state-specific polling place data scrapers

All state plugins should inherit from this class and implement the required methods.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, TYPE_CHECKING
from datetime import datetime, date, timedelta

if TYPE_CHECKING:
    from app import PollingPlace, Precinct, PrecinctAssignment


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

    def fetch_precincts(self) -> List[Dict[str, Any]]:
        """
        Fetch precinct data from the state's data source.

        Optional method - return empty list if precincts are not available.

        Returns:
            List of dictionaries with precinct data. Each dictionary should contain:
            - id: str - Unique identifier (e.g., "CA-ALAMEDA-0001")
            - name: str - Precinct name
            - state: str - Two-letter state code
            - county: str (optional) - County name
            - registered_voters: int (optional) - Number of registered voters
            - polling_place_id: str - ID of assigned polling place

        Raises:
            Exception: If there's an error fetching data
        """
        return []

    def normalize_text(self, text: str) -> str:
        """
        Normalize text for matching by standardizing abbreviations and formatting.

        Args:
            text: The text to normalize

        Returns:
            Normalized text string
        """
        if not text:
            return ""

        # Common abbreviation mappings
        abbreviations = {
            'office': 'ofc',
            'ofc': 'ofc',
            'building': 'bldg',
            'bldg': 'bldg',
            'street': 'st',
            'st': 'st',
            'avenue': 'ave',
            'ave': 'ave',
            'road': 'rd',
            'rd': 'rd',
            'drive': 'dr',
            'dr': 'dr',
            'lane': 'ln',
            'ln': 'ln',
            'boulevard': 'blvd',
            'blvd': 'blvd',
            'place': 'pl',
            'pl': 'pl',
            'court': 'ct',
            'ct': 'ct',
            'center': 'ctr',
            'ctr': 'ctr',
            'school': 'sch',
            'sch': 'sch',
            'library': 'lib',
            'lib': 'lib',
            'community': 'comm',
            'comm': 'comm',
            'hall': 'hl',
            'hl': 'hl',
            'park': 'pk',
            'pk': 'pk',
            'elementary': 'elem',
            'elem': 'elem',
            'middle': 'mid',
            'mid': 'mid',
            'high': 'hi',
            'hi': 'hi',
            'north': 'n',
            'n': 'n',
            'south': 's',
            's': 's',
            'east': 'e',
            'e': 'e',
            'west': 'w',
            'w': 'w'
        }

        # Convert to lowercase, remove extra spaces, and replace abbreviations
        normalized = text.lower().strip()
        for full, abbr in abbreviations.items():
            normalized = normalized.replace(full, abbr)

        # Remove punctuation and extra spaces
        import re
        normalized = re.sub(r'[^\w\s]', '', normalized)
        normalized = re.sub(r'\s+', ' ', normalized).strip()

        return normalized

    def generate_composite_key(self, name: str, address_line1: str, city: str, state: str, zip_code: str) -> str:
        """
        Generate a composite key from normalized name and address components.

        Args:
            name: Polling place name
            address_line1: Street address
            city: City name
            state: State code
            zip_code: ZIP code

        Returns:
            Composite key string
        """
        normalized_name = self.normalize_text(name)
        normalized_address = self.normalize_text(address_line1)
        normalized_city = self.normalize_text(city)

        # Create a hash-based key for uniqueness
        import hashlib
        key_string = f"{normalized_name}|{normalized_address}|{normalized_city}|{state}|{zip_code}"
        return hashlib.md5(key_string.encode()).hexdigest()



    def sync(self) -> Dict[str, Any]:
        """
        Sync polling place data from the source to the database.

        This method calls fetch_polling_places() and updates the database using
        name and address matching instead of relying on IDs.

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

                        # Generate composite key as ID if not provided
                        if 'id' not in data or not data['id']:
                            data['id'] = self.generate_composite_key(
                                data.get('name', ''),
                                data.get('address_line1', ''),
                                data.get('city', ''),
                                data.get('state', ''),
                                data.get('zip_code', '')
                            )

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

                # Sync precincts if available
                precinct_result = self.sync_precincts()

                # Update sync stats
                self.last_sync = datetime.utcnow()
                self.sync_count += 1

                result = {
                    'success': True,
                    'message': f'Successfully synced data for {self.state_code} using name/address matching',
                    'polling_places': {
                        'added': added,
                        'updated': updated,
                        'errors': errors
                    },
                    'precincts': precinct_result,
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
                    'polling_places': {
                        'added': 0,
                        'updated': 0,
                        'errors': 1
                    },
                    'precincts': {'added': 0, 'updated': 0, 'errors': 0},
                    'timestamp': datetime.utcnow().isoformat()
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
                    'polling_places': {
                        'added': 0,
                        'updated': 0,
                        'errors': 1
                    },
                    'precincts': {'added': 0, 'updated': 0, 'errors': 0},
                    'timestamp': datetime.utcnow().isoformat()
                }





    def sync_precincts(self, effective_date: date = None, election_id: int = None) -> Dict[str, int]:
        """
        Sync precinct data from the source to the database.

        This method tracks assignment changes and maintains historical records,
        using name and address matching for polling places.

        Args:
            effective_date: Date to use for assignments (default: today).
                             Used during historical imports to set accurate dates.
            election_id: Optional election ID to link assignments to.

        Returns:
            Dictionary with sync results:
            - added: int - Number of new precincts
            - updated: int - Number of updated precincts
            - errors: int - Number of errors
        """
        try:
            # Import here to avoid circular imports
            from app import Precinct, PrecinctAssignment, PollingPlace

            # Fetch precinct data from source
            precincts_data = self.fetch_precincts()

            if not precincts_data:
                return {'added': 0, 'updated': 0, 'errors': 0}

            added = 0
            updated = 0
            errors = 0
            # Use effective_date for historical imports, otherwise use today
            sync_date = effective_date if effective_date else date.today()
            today = date.today()  # For calculating changed_recently
            six_months_ago = today - timedelta(days=180)

            for data in precincts_data:
                try:
                    precinct_id = data.get('id')
                    polling_place_id = data.get('polling_place_id')

                    if not precinct_id:
                        self.app.logger.warning(f"Skipping precinct with missing id")
                        errors += 1
                        continue



                    if not polling_place_id:
                        self.app.logger.warning(f"Skipping precinct with missing polling_place_id")
                        errors += 1
                        continue

                    # Check if precinct exists
                    existing = self.db.session.get(Precinct, precinct_id)

                    if existing:
                        # Check if polling place assignment has changed
                        if existing.current_polling_place_id != polling_place_id:
                            # Mark the old assignment as ended
                            current_assignment = self.db.session.query(PrecinctAssignment).filter_by(
                                precinct_id=precinct_id,
                                removed_date=None
                            ).first()

                            if current_assignment:
                                current_assignment.removed_date = sync_date

                            # Create new assignment record
                            new_assignment = PrecinctAssignment(
                                precinct_id=precinct_id,
                                polling_place_id=polling_place_id,
                                assigned_date=sync_date,
                                previous_polling_place_id=existing.current_polling_place_id,
                                election_id=election_id
                            )
                            self.db.session.add(new_assignment)

                            # Update precinct with new assignment
                            existing.current_polling_place_id = polling_place_id
                            existing.last_change_date = sync_date
                            # Note: changed_recently will be set below based on last_change_date

                        # Update other fields (regardless of whether assignment changed)
                        if 'name' in data:
                            existing.name = data['name']
                        if 'county' in data:
                            existing.county = data['county']
                        if 'registered_voters' in data:
                            existing.registered_voters = data['registered_voters']
                        if 'state' in data:
                            existing.state = data['state']

                        existing.source_plugin = self.name

                        # Update changed_recently flag based on last_change_date
                        # This ensures it's only True if the assignment actually changed within 6 months
                        if existing.last_change_date:
                            existing.changed_recently = (existing.last_change_date >= six_months_ago)

                        updated += 1
                    else:
                        # Create new precinct
                        new_precinct = Precinct(
                            id=precinct_id,
                            name=data.get('name', ''),
                            state=data.get('state', self.state_code),
                            county=data.get('county'),
                            registered_voters=data.get('registered_voters'),
                            current_polling_place_id=polling_place_id,
                            last_change_date=sync_date,
                            changed_recently=False,
                            source_plugin=self.name
                        )
                        self.db.session.add(new_precinct)

                        # Create initial assignment record
                        initial_assignment = PrecinctAssignment(
                            precinct_id=precinct_id,
                            polling_place_id=polling_place_id,
                            assigned_date=sync_date,
                            previous_polling_place_id=None,
                            election_id=election_id
                        )
                        self.db.session.add(initial_assignment)

                        added += 1

                except Exception as e:
                    self.app.logger.error(f"Error processing precinct {data.get('id', 'unknown')}: {e}")
                    errors += 1

            # Commit all precinct changes
            self.db.session.commit()

            return {'added': added, 'updated': updated, 'errors': errors}

        except Exception as e:
            self.app.logger.error(f"Error syncing precincts for {self.name}: {str(e)}")
            return {'added': 0, 'updated': 0, 'errors': 1}



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
