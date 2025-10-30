"""
Dummy Plugin - Generates fake polling place data for testing

This plugin generates realistic-looking but fake polling place data for any state.
It's useful for testing, demonstrations, and development purposes.
"""

import random
from typing import List, Dict, Any
from plugins.base_plugin import BasePlugin


class DummyPlugin(BasePlugin):
    """
    Dummy plugin that generates fake polling place data for testing.
    Generates data for all 50 US states.
    """

    # Sample location names for generating fake data
    LOCATION_TYPES = [
        'Elementary School', 'Middle School', 'High School', 'Community Center',
        'Public Library', 'Fire Station', 'City Hall', 'Recreation Center',
        'Senior Center', 'Church', 'Civic Center', 'Town Hall'
    ]

    STREET_NAMES = [
        'Main St', 'Oak Ave', 'Maple Dr', 'Washington Blvd', 'Lincoln Way',
        'Park Ave', 'Cedar Ln', 'Elm St', 'Pine Rd', 'Valley View Dr',
        'Highland Ave', 'River Rd', 'Lake St', 'Hill Dr', 'Sunset Blvd'
    ]

    CITY_PREFIXES = [
        'Spring', 'River', 'Lake', 'Oak', 'Pine', 'Cedar', 'Maple',
        'Green', 'Fair', 'Pleasant', 'Sun', 'Silver', 'Golden'
    ]

    CITY_SUFFIXES = [
        'field', 'ville', 'town', 'dale', 'wood', 'haven', 'port',
        'view', 'side', 'ridge', 'valley', 'springs'
    ]

    # US State codes and names
    STATES = {
        'AL': 'Alabama', 'AK': 'Alaska', 'AZ': 'Arizona', 'AR': 'Arkansas',
        'CA': 'California', 'CO': 'Colorado', 'CT': 'Connecticut', 'DE': 'Delaware',
        'FL': 'Florida', 'GA': 'Georgia', 'HI': 'Hawaii', 'ID': 'Idaho',
        'IL': 'Illinois', 'IN': 'Indiana', 'IA': 'Iowa', 'KS': 'Kansas',
        'KY': 'Kentucky', 'LA': 'Louisiana', 'ME': 'Maine', 'MD': 'Maryland',
        'MA': 'Massachusetts', 'MI': 'Michigan', 'MN': 'Minnesota', 'MS': 'Mississippi',
        'MO': 'Missouri', 'MT': 'Montana', 'NE': 'Nebraska', 'NV': 'Nevada',
        'NH': 'New Hampshire', 'NJ': 'New Jersey', 'NM': 'New Mexico', 'NY': 'New York',
        'NC': 'North Carolina', 'ND': 'North Dakota', 'OH': 'Ohio', 'OK': 'Oklahoma',
        'OR': 'Oregon', 'PA': 'Pennsylvania', 'RI': 'Rhode Island', 'SC': 'South Carolina',
        'SD': 'South Dakota', 'TN': 'Tennessee', 'TX': 'Texas', 'UT': 'Utah',
        'VT': 'Vermont', 'VA': 'Virginia', 'WA': 'Washington', 'WV': 'West Virginia',
        'WI': 'Wisconsin', 'WY': 'Wyoming'
    }

    @property
    def name(self) -> str:
        return 'dummy'

    @property
    def state_code(self) -> str:
        return 'ALL'

    @property
    def description(self) -> str:
        return 'Dummy plugin that generates fake polling place data for testing (all states)'

    def generate_fake_city(self) -> str:
        """Generate a fake city name"""
        prefix = random.choice(self.CITY_PREFIXES)
        suffix = random.choice(self.CITY_SUFFIXES)
        return f"{prefix}{suffix}"

    def generate_fake_address(self) -> tuple:
        """Generate a fake address (street number + street name)"""
        number = random.randint(100, 9999)
        street = random.choice(self.STREET_NAMES)
        return f"{number} {street}"

    def generate_fake_coordinates(self) -> tuple:
        """
        Generate fake but realistic coordinates within US bounds
        Latitude: 24.5° to 49.4° (continental US)
        Longitude: -125° to -66° (continental US)
        """
        lat = round(random.uniform(24.5, 49.4), 6)
        lng = round(random.uniform(-125.0, -66.0), 6)
        return (lat, lng)

    def generate_fake_polling_hours(self) -> str:
        """Generate fake polling hours"""
        start_hour = random.choice([6, 7, 8])
        end_hour = random.choice([19, 20, 21])
        return f"{start_hour}:00 AM - {end_hour % 12 or 12}:00 PM"

    def generate_fake_location_type(self) -> str:
        """Generate a fake location type with realistic distribution"""
        # Most polling places are election day locations
        weights = [0.05, 0.15, 0.80]  # drop box, early voting, election day
        return random.choices(['drop box', 'early voting', 'election day'], weights=weights)[0]

    def generate_fake_location(self, state_code: str, location_id: int) -> Dict[str, Any]:
        """Generate a single fake polling location"""
        location_type_name = random.choice(self.LOCATION_TYPES)
        location_name = f"{random.choice(['North', 'South', 'East', 'West', 'Central'])} {location_type_name}"
        city = self.generate_fake_city()
        address = self.generate_fake_address()
        lat, lng = self.generate_fake_coordinates()
        zip_code = f"{random.randint(10000, 99999)}"

        # Add some variety to the data
        has_notes = random.choice([True, False])
        has_services = random.choice([True, False])
        has_location_name = random.choice([True, False])

        data = {
            'id': f"{state_code}-{location_id:05d}",
            'name': location_name,
            'address_line1': address,
            'city': city,
            'state': state_code,
            'zip_code': zip_code,
            'latitude': lat,
            'longitude': lng,
            'polling_hours': self.generate_fake_polling_hours(),
            'location_type': self.generate_fake_location_type(),
        }

        # Add optional fields randomly
        if has_location_name:
            data['location_name'] = random.choice(['Main Entrance', 'Gymnasium', 'Cafeteria', 'Auditorium'])

        if has_notes:
            notes_options = [
                'Wheelchair accessible',
                'Parking available in rear lot',
                'Enter through main entrance',
                'Use side entrance on election day',
                'ADA compliant facility'
            ]
            data['notes'] = random.choice(notes_options)

        if has_services:
            services = []
            if random.choice([True, False]):
                services.append('Early voting')
            if random.choice([True, False]):
                services.append('Ballot drop-off')
            if random.choice([True, False]):
                services.append('Voter registration')
            if services:
                data['voter_services'] = ', '.join(services)

        return data

    def fetch_polling_places(self) -> List[Dict[str, Any]]:
        """
        Generate fake polling place data for all US states.

        Generates 100-120 polling places per state.
        """
        polling_places = []

        for state_code in self.STATES.keys():
            # Generate between 100 and 120 locations per state
            num_locations = random.randint(100, 120)

            for i in range(num_locations):
                location = self.generate_fake_location(state_code, i + 1)

                # Validate the data
                if self.validate_polling_place_data(location):
                    polling_places.append(location)

        self.app.logger.info(
            f"Generated {len(polling_places)} fake polling places across {len(self.STATES)} states"
        )

        return polling_places

    def fetch_precincts(self) -> List[Dict[str, Any]]:
        """
        Generate fake precinct data for all US states.

        Generates 3-8 precincts per polling place.
        On subsequent syncs, randomly reassigns ~10% of precincts to simulate changes.
        """
        # Import here to avoid circular imports
        from models import Precinct, PollingPlace

        # Check if we have existing precincts (to simulate changes)
        existing_precincts = self.db.session.query(Precinct).all()
        existing_precinct_map = {p.id: p for p in existing_precincts}

        precincts = []
        precinct_counter = 1

        for state_code in self.STATES.keys():
            # Generate between 100 and 120 polling places per state (matching fetch_polling_places)
            num_polling_places = random.randint(100, 120)

            # Generate county names for this state
            counties = [
                f"{random.choice(self.CITY_PREFIXES)} County",
                f"{random.choice(['Lake', 'River', 'Mountain'])} County",
                f"{random.choice(['North', 'South', 'East', 'West'])} County"
            ]

            # Get all polling place IDs for this state to allow reassignment
            all_polling_place_ids = [f"{state_code}-{i:05d}" for i in range(1, num_polling_places + 1)]

            for polling_place_num in range(1, num_polling_places + 1):
                polling_place_id = f"{state_code}-{polling_place_num:05d}"

                # Generate 3-8 precincts per polling place
                num_precincts = random.randint(3, 8)

                for precinct_num in range(1, num_precincts + 1):
                    precinct_id = f"{state_code}-P-{precinct_counter:06d}"

                    # Check if this precinct already exists
                    if precinct_id in existing_precinct_map:
                        existing_precinct = existing_precinct_map[precinct_id]

                        # 10% chance to reassign to a different polling place (simulate change)
                        if random.random() < 0.10:
                            # Ensure we pick a different polling place
                            new_polling_place_id = random.choice(all_polling_place_ids)
                            while new_polling_place_id == existing_precinct.current_polling_place_id:
                                new_polling_place_id = random.choice(all_polling_place_ids)

                            polling_place_id = new_polling_place_id
                            self.app.logger.debug(
                                f"Reassigning {precinct_id} from "
                                f"{existing_precinct.current_polling_place_id} to {polling_place_id}"
                            )

                    precinct_data = {
                        'id': precinct_id,
                        'name': f"Precinct {precinct_num}",
                        'state': state_code,
                        'county': random.choice(counties),
                        'precinctcode': f"{precinct_num:03d}",  # Add synthetic precinct code
                        'registered_voters': random.randint(500, 5000),
                        'polling_place_id': polling_place_id
                    }

                    precincts.append(precinct_data)
                    precinct_counter += 1

        self.app.logger.info(
            f"Generated {len(precincts)} fake precincts across {len(self.STATES)} states"
        )

        return precincts
