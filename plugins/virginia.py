"""
Virginia Plugin - Fetches polling place and precinct data from Virginia Department of Elections

Data source: https://www.elections.virginia.gov/resultsreports/registration-statistics/
Format: Excel (.xlsx) files with polling locations and precinct assignments
"""

import re
import csv
import os
import requests
import time
import pandas as pd
from typing import List, Dict, Any
from io import BytesIO
from datetime import datetime
from urllib.parse import quote
from plugins.base_plugin import BasePlugin


class VirginiaPlugin(BasePlugin):
    """
    Virginia plugin that fetches polling place and precinct data from
    Virginia Department of Elections Excel files.
    """

    # Election data URLs (most recent first)
    ELECTIONS = {
        '2024-11-05': 'https://www.elections.virginia.gov/media/registration-statistics/2024-November-General-Election-Day-Polling-Locations-(10-9-24).xlsx',
        '2024-06-18': 'https://www.elections.virginia.gov/media/registration-statistics/2024-June-Democratic-and-Republican-Primary-Polling-Locations-(6-5-24).xlsx',
        '2024-03-05': 'https://www.elections.virginia.gov/media/registration-statistics/2024-March-Presidential-Primary-Polling-Locations-(2-27-24).xlsx',
    }

    @property
    def name(self) -> str:
        return 'virginia'

    @property
    def state_code(self) -> str:
        return 'VA'

    @property
    def description(self) -> str:
        return 'Virginia polling place data from state elections website'

    def _normalize_locality_name(self, locality: str) -> str:
        """
        Normalize locality name for use in IDs.
        Example: "ACCOMACK COUNTY" -> "ACCOMACK"
        """
        # Remove common suffixes
        locality = str(locality).upper().strip()
        locality = locality.replace(' COUNTY', '').replace(' CITY', '')
        # Remove special characters, keep only letters and numbers
        locality = re.sub(r'[^A-Z0-9]', '', locality)
        return locality

    def _extract_precinct_number(self, precinct_name: str) -> str:
        """
        Extract precinct number from name.
        Example: "101 - CHINCOTEAGUE" -> "101"
        """
        match = re.match(r'^(\d+)', str(precinct_name).strip())
        if match:
            return match.group(1)
        # Fallback: use sanitized name
        return re.sub(r'[^A-Z0-9]', '', str(precinct_name).upper())[:10]

    def _download_excel(self, url: str) -> pd.DataFrame:
        """Download and parse Excel file from URL."""
        self.app.logger.info(f"Downloading Excel file from: {url}")
        response = requests.get(url, timeout=30)
        response.raise_for_status()

        # Parse Excel file
        df = pd.read_excel(BytesIO(response.content))
        self.app.logger.info(f"Downloaded {len(df)} rows from Excel file")
        return df

    def _parse_excel_data(self, df: pd.DataFrame) -> tuple:
        """
        Parse Excel data into polling places and precincts.

        Returns:
            Tuple of (polling_places_dict, precincts_list)
        """
        polling_places = {}  # Key: (locality, location, address) -> polling_place_data
        precincts = []
        polling_place_counter = {}  # Track sequence per locality

        for idx, row in df.iterrows():
            try:
                locality_name = str(row['Locality Name']).strip()
                locality_short = self._normalize_locality_name(locality_name)
                precinct_name = str(row['Voting Precinct Name']).strip()
                precinct_num = self._extract_precinct_number(precinct_name)

                location = str(row['Location']).strip()
                address1 = str(row['Address Line 1']).strip() if not pd.isna(row['Address Line 1']) else ''
                address2 = str(row['Address Line 2']).strip() if not pd.isna(row['Address Line 2']) else None
                city = str(row['City']).strip() if not pd.isna(row['City']) else ''
                zip_code = str(row['Zip Code']).strip() if not pd.isna(row['Zip Code']) else ''

                # Create unique key for polling place
                polling_place_key = (locality_short, location, address1, city)

                # Create or get polling place ID
                if polling_place_key not in polling_places:
                    # New polling place
                    if locality_short not in polling_place_counter:
                        polling_place_counter[locality_short] = 1

                    pp_id = f"VA-{locality_short}-PP-{polling_place_counter[locality_short]:04d}"
                    polling_place_counter[locality_short] += 1

                    polling_places[polling_place_key] = {
                        'id': pp_id,
                        'name': location,
                        'address_line1': address1,
                        'address_line2': address2,
                        'city': city,
                        'state': 'VA',
                        'zip_code': zip_code,
                    }

                polling_place_id = polling_places[polling_place_key]['id']

                # Create precinct record
                precinct_id = f"VA-{locality_short}-P-{precinct_num}"
                precinct_data = {
                    'id': precinct_id,
                    'name': precinct_name,
                    'state': 'VA',
                    'county': locality_name,
                    'polling_place_id': polling_place_id,
                }
                precincts.append(precinct_data)

            except Exception as e:
                self.app.logger.warning(f"Error processing row {idx}: {e}")
                continue

        return (list(polling_places.values()), precincts)

    def _geocode_addresses(self, polling_places: List[Dict[str, Any]]) -> None:
        """
        Geocode the polling places using multiple APIs: Census, Google, Mapbox.

        Args:
            polling_places: List of polling place dictionaries to update with lat/lng
        """
        if not polling_places:
            return

        # Normalize addresses for better geocoding
        def normalize_address(addr):
            if not addr:
                return ""
            # Remove extra spaces, standardize
            return ' '.join(addr.strip().split())

        # Filter valid addresses
        valid_places = []
        for pp in polling_places:
            if pp.get('address_line1') and pp.get('city') and pp.get('zip_code'):
                valid_places.append(pp)
            else:
                self.app.logger.warning(f"Skipping geocoding for {pp['id']}: missing address data")

        polling_places = valid_places

        self.app.logger.info(f"Starting geocoding for {len(polling_places)} polling places")

        # Try geocoders in priority order
        geocoder_priority = self.app.config.get('geocoder_priority', ['Mapbox', 'Census', 'Google'])
        for geocoder in geocoder_priority:
            failed_places = [pp for pp in polling_places if 'latitude' not in pp]
            if not failed_places:
                break

            self.app.logger.info(f"Attempting {geocoder} geocoding for {len(failed_places)} addresses")
            if geocoder == 'Census':
                self._geocode_census(failed_places)
            elif geocoder == 'Google':
                self._geocode_google(failed_places)
            elif geocoder == 'Mapbox':
                self._geocode_mapbox(failed_places)
            else:
                self.app.logger.warning(f"Unknown geocoder: {geocoder}")

        # Final status
        geocoded = [pp for pp in polling_places if 'latitude' in pp]
        self.app.logger.info(f"Geocoding complete: {len(geocoded)}/{len(polling_places)} addresses geocoded")

    def _geocode_census(self, polling_places: List[Dict[str, Any]]) -> None:
        """Geocode using Census API"""
        # Prepare CSV data
        csv_data = "id,street,city,state,zip\n"
        for pp in polling_places:
            normalized_addr = ' '.join((pp['address_line1'] or '').strip().split())
            normalized_city = ' '.join((pp['city'] or '').strip().split())
            csv_data += f"{pp['id']},{normalized_addr},{normalized_city},VA,{pp['zip_code']}\n"
            self.app.logger.debug(f"Census input: {pp['id']} - {normalized_addr}, {normalized_city}, VA {pp['zip_code']}")

        url = "https://geocoding.geo.census.gov/geocoder/locations/addressbatch"
        files = {'addressFile': ('addresses.csv', csv_data, 'text/csv')}
        data = {
            'benchmark': 'Public_AR_Census2020',
            'vintage': 'Census2020_Census2020'
        }

        response = None
        max_retries = 3
        for attempt in range(max_retries):
            try:
                self.app.logger.info(f"Census geocoding {len(polling_places)} addresses (attempt {attempt + 1})")
                response = requests.post(url, files=files, data=data, timeout=60)

                if response.status_code == 200:
                    self.app.logger.info("Census geocoding request successful")
                    break
                elif response.status_code == 500 and attempt < max_retries - 1:
                    self.app.logger.warning(f"Census geocoding failed with 500, retrying in 5 seconds...")
                    time.sleep(5)
                    continue
                else:
                    self.app.logger.error(f"Census geocoding failed: {response.status_code} - {response.text}")
                    return

            except Exception as e:
                if attempt < max_retries - 1:
                    self.app.logger.warning(f"Census geocoding error, retrying: {e}")
                    time.sleep(5)
                else:
                    self.app.logger.error(f"Census geocoding error: {e}")
                    return

        if response and response.status_code == 200:
            lines = response.text.strip().split('\n')
            self.app.logger.info(f"Census response has {len(lines)} lines")
            for line in lines[1:]:
                if not line.strip():
                    continue
                parts = line.split(',')
                if len(parts) < 12:
                    self.app.logger.debug(f"Skipping line with {len(parts)} parts: {line}")
                    continue
                pp_id = parts[0]
                match = parts[6]
                lat = parts[11]
                lon = parts[10]

                if match == 'Match' and lat and lon:
                    for pp in polling_places:
                        if pp['id'] == pp_id:
                            pp['latitude'] = float(lat)
                            pp['longitude'] = float(lon)
                            self.app.logger.info(f"Census geocoded {pp_id}: {lat}, {lon}")
                            break
                else:
                    for pp in polling_places:
                        if pp['id'] == pp_id:
                            normalized_addr = ' '.join((pp['address_line1'] or '').strip().split())
                            normalized_city = ' '.join((pp['city'] or '').strip().split())
                            self.app.logger.warning(f"Census geocoding failed for {pp_id}: {normalized_addr}, {normalized_city}, VA {pp['zip_code']}")
                            break

    def _geocode_google(self, polling_places: List[Dict[str, Any]]) -> None:
        """Geocode using Google API"""
        api_key = os.getenv('GOOGLE_GEOCODING_API_KEY')
        if not api_key:
            self.app.logger.warning("Google API key not set, skipping Google geocoding")
            return

        self.app.logger.info(f"Starting Google geocoding for {len(polling_places)} addresses")
        for pp in polling_places:
            address = f"{pp['address_line1'] or ''}, {pp['city'] or ''}, VA {pp['zip_code'] or ''}"
            url = f"https://maps.googleapis.com/maps/api/geocode/json?address={quote(address)}&key={api_key}"

            try:
                self.app.logger.debug(f"Google request for {pp['id']}: {address}")
                response = requests.get(url, timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    if data['status'] == 'OK' and data['results']:
                        location = data['results'][0]['geometry']['location']
                        pp['latitude'] = location['lat']
                        pp['longitude'] = location['lng']
                        self.app.logger.info(f"Google geocoded {pp['id']}: {location['lat']}, {location['lng']}")
                    else:
                        self.app.logger.warning(f"Google geocoding failed for {pp['id']}: {address} - {data['status']}")
                else:
                    self.app.logger.warning(f"Google geocoding error for {pp['id']}: {response.status_code}")
            except Exception as e:
                self.app.logger.warning(f"Google geocoding exception for {pp['id']}: {e}")

            time.sleep(0.1)  # Rate limit

    def _geocode_mapbox(self, polling_places: List[Dict[str, Any]]) -> None:
        """Geocode using Mapbox API"""
        access_token = os.getenv('MAPBOX_ACCESS_TOKEN')
        if not access_token:
            self.app.logger.warning("Mapbox access token not set, skipping Mapbox geocoding")
            return

        self.app.logger.info(f"Starting Mapbox geocoding for {len(polling_places)} addresses")
        for pp in polling_places:
            address = f"{pp['address_line1'] or ''}, {pp['city'] or ''}, VA {pp['zip_code'] or ''}"
            url = f"https://api.mapbox.com/search/geocode/v6/forward?q={quote(address)}&permanent=false&access_token={access_token}"

            try:
                self.app.logger.debug(f"Mapbox request for {pp['id']}: {address}")
                response = requests.get(url, timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    if data['features']:
                        location = data['features'][0]['properties']['coordinates']
                        pp['longitude'] = location['longitude']
                        pp['latitude'] = location['latitude']
                        self.app.logger.info(f"Mapbox geocoded {pp['id']}: {location['latitude']}, {location['longitude']}")
                    else:
                        self.app.logger.warning(f"Mapbox geocoding failed for {pp['id']}: {address}")
                else:
                    self.app.logger.warning(f"Mapbox geocoding error for {pp['id']}: {response.status_code}")
            except Exception as e:
                self.app.logger.warning(f"Mapbox geocoding exception for {pp['id']}: {e}")

            time.sleep(0.1)  # Rate limit

    def fetch_polling_places(self) -> List[Dict[str, Any]]:
        """
        Fetch polling place data from the most recent election.

        Returns:
            List of polling place dictionaries
        """
        # Get most recent election
        most_recent_date = max(self.ELECTIONS.keys())
        url = self.ELECTIONS[most_recent_date]

        self.app.logger.info(f"Fetching Virginia polling places from {most_recent_date} election")

        # Download and parse
        df = self._download_excel(url)
        polling_places, _ = self._parse_excel_data(df)

        self.app.logger.info(f"Extracted {len(polling_places)} unique polling places")

        # Check which places need geocoding (new or address changed)
        from app import PollingPlace
        places_to_geocode = []
        new_places = 0
        changed_places = 0
        no_coords_places = 0

        for place in polling_places:
            existing = self.db.session.get(PollingPlace, place['id'])
            if not existing:
                # New place, needs geocoding
                places_to_geocode.append(place)
                new_places += 1
            else:
                # Check if address changed
                existing_data = {
                    'address_line1': existing.address_line1 or '',
                    'address_line2': existing.address_line2 or '',
                    'address_line3': existing.address_line3 or '',
                    'city': existing.city or '',
                    'state': existing.state or '',
                    'zip_code': existing.zip_code or ''
                }

                if self.has_address_changed(existing_data, place):
                    # Address changed, needs re-geocoding
                    places_to_geocode.append(place)
                    changed_places += 1
                    self.app.logger.info(f"Address changed for {place['name']}, will re-geocode")
                elif existing.latitude is None or existing.longitude is None:
                    # No coordinates, needs geocoding
                    places_to_geocode.append(place)
                    no_coords_places += 1
                    self.app.logger.info(f"No coordinates for {place['name']}, will geocode")
                else:
                    # Preserve existing coordinates
                    if existing.latitude is not None:
                        place['latitude'] = existing.latitude
                    if existing.longitude is not None:
                        place['longitude'] = existing.longitude

        self.app.logger.info(f"Places to geocode: {len(places_to_geocode)} (new: {new_places}, changed: {changed_places}, no coords: {no_coords_places})")

        # Geocode only the places that need it
        if places_to_geocode:
            self.app.logger.info(f"Geocoding {len(places_to_geocode)} places (new or address changed)")
            self._geocode_addresses(places_to_geocode)
        else:
            self.app.logger.info("No addresses changed, skipping geocoding")

        return polling_places

    def fetch_precincts(self) -> List[Dict[str, Any]]:
        """
        Fetch precinct data from the most recent election.

        Returns:
            List of precinct dictionaries with polling_place_id assignments
        """
        # Get most recent election
        most_recent_date = max(self.ELECTIONS.keys())
        url = self.ELECTIONS[most_recent_date]

        self.app.logger.info(f"Fetching Virginia precincts from {most_recent_date} election")

        # Download and parse
        df = self._download_excel(url)
        _, precincts = self._parse_excel_data(df)

        self.app.logger.info(f"Extracted {len(precincts)} precincts")
        return precincts

    def _get_or_create_election(self, election_date, election_name):
        """
        Get or create an Election record for the given date and name.

        Args:
            election_date: Date object for the election
            election_name: Name of the election (e.g., "2024 General Election")

        Returns:
            Election object
        """
        from app import Election

        # Check if election already exists
        election = Election.query.filter_by(date=election_date, state=self.state_code).first()

        if not election:
            # Create new election record
            election = Election(
                date=election_date,
                name=election_name,
                state=self.state_code
            )
            self.db.session.add(election)
            self.db.session.commit()
            self.app.logger.info(f"Created election record: {election_name} ({election_date})")
        else:
            self.app.logger.info(f"Using existing election record: {election_name} ({election_date})")

        return election

    def _generate_election_name(self, election_date_str):
        """
        Generate a human-readable election name from the date string.

        Args:
            election_date_str: Date string in YYYY-MM-DD format

        Returns:
            Human-readable election name
        """
        date_obj = datetime.strptime(election_date_str, '%Y-%m-%d')
        year = date_obj.year
        month = date_obj.strftime('%B')  # Full month name

        # Determine election type based on month
        if month == 'November' and date_obj.day <= 10:
            return f"{year} General Election"
        elif month == 'March':
            return f"{year} Presidential Primary"
        elif month == 'June':
            return f"{year} Primary Election"
        else:
            return f"{year} {month} Election"

    def import_historical_data(self) -> Dict[str, Any]:
        """
        Import data from all elections in chronological order.
        This builds up a complete assignment history and creates Election records.

        Returns:
            Dictionary with import results for each election
        """
        results = {}

        # Sort elections chronologically (oldest first)
        sorted_elections = sorted(self.ELECTIONS.items())

        self.app.logger.info(f"Starting historical import for {len(sorted_elections)} elections")

        for election_date_str, url in sorted_elections:
            self.app.logger.info(f"Importing election: {election_date_str}")

            try:
                # Parse election date
                election_date = datetime.strptime(election_date_str, '%Y-%m-%d').date()

                # Generate election name
                election_name = self._generate_election_name(election_date_str)

                # Get or create election record
                election = self._get_or_create_election(election_date, election_name)

                # Download and parse this election's data
                df = self._download_excel(url)
                polling_places, precincts = self._parse_excel_data(df)

                # Override fetch methods to return this election's data
                old_fetch_pp = self.fetch_polling_places
                old_fetch_pr = self.fetch_precincts

                self.fetch_polling_places = lambda: polling_places
                # Don't fetch precincts during sync() - we'll do that separately with the correct date
                self.fetch_precincts = lambda: []

                # Sync polling places
                sync_result = self.sync()

                # Restore fetch methods
                self.fetch_polling_places = old_fetch_pp
                self.fetch_precincts = old_fetch_pr

                # Now sync precincts separately with the actual election date (not today)
                # This ensures last_change_date reflects the actual election date
                # and links assignments to the election
                self.fetch_precincts = lambda: precincts
                precinct_result = self.sync_precincts(
                    effective_date=election_date,
                    election_id=election.id
                )
                self.fetch_precincts = old_fetch_pr

                results[election_date_str] = {
                    'success': sync_result['success'],
                    'election_id': election.id,
                    'election_name': election_name,
                    'polling_places': sync_result['polling_places'],
                    'precincts': precinct_result
                }

                self.app.logger.info(
                    f"Election {election_date_str} ({election_name}): "
                    f"PP added={sync_result['polling_places']['added']}, "
                    f"PP updated={sync_result['polling_places']['updated']}, "
                    f"Precincts added={precinct_result['added']}, "
                    f"Precincts updated={precinct_result['updated']}"
                )

            except Exception as e:
                self.app.logger.error(f"Error importing election {election_date_str}: {e}")
                results[election_date_str] = {
                    'success': False,
                    'error': str(e)
                }

        return results
