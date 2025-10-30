"""
Ohio Plugin - Fetches polling place and precinct data from Ohio CSV

Data source: ohio.csv
Format: CSV file with polling locations and precinct assignments
"""

import csv
import os
import requests
import time
from urllib.parse import quote
from typing import List, Dict, Any
from plugins.base_plugin import BasePlugin


class OhioPlugin(BasePlugin):
    """
    Ohio plugin that fetches polling place and precinct data from
    Ohio CSV file.
    """

    @property
    def name(self) -> str:
        return 'ohio'

    @property
    def state_code(self) -> str:
        return 'OH'

    @property
    def description(self) -> str:
        return 'Ohio polling place data from state CSV'

    @property
    def supports_file_upload(self) -> bool:
        return True

    def _read_csv(self) -> List[Dict[str, str]]:
        """Read the Ohio CSV file."""
        csv_path = os.path.join(os.path.dirname(__file__), '..', 'ohio.csv')
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            return list(reader)

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
            normalized_addr = ' '.join(pp['address_line1'].strip().split())
            normalized_city = ' '.join(pp['city'].strip().split())
            csv_data += f"{pp['id']},{normalized_addr},{normalized_city},OH,{pp['zip_code']}\n"
            self.app.logger.debug(f"Census input: {pp['id']} - {normalized_addr}, {normalized_city}, OH {pp['zip_code']}")

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
                            normalized_addr = ' '.join(pp['address_line1'].strip().split())
                            normalized_city = ' '.join(pp['city'].strip().split())
                            self.app.logger.warning(f"Census geocoding failed for {pp_id}: {normalized_addr}, {normalized_city}, OH {pp['zip_code']}")
                            break

    def _geocode_google(self, polling_places: List[Dict[str, Any]]) -> None:
        """Geocode using Google API"""
        api_key = os.getenv('GOOGLE_GEOCODING_API_KEY')
        if not api_key:
            self.app.logger.warning("Google API key not set, skipping Google geocoding")
            return

        self.app.logger.info(f"Starting Google geocoding for {len(polling_places)} addresses")
        for pp in polling_places:
            address = f"{pp['address_line1']}, {pp['city']}, OH {pp['zip_code']}"
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
            address = f"{pp['address_line1']}, {pp['city']}, OH {pp['zip_code']}"
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
        Fetch polling place data from the CSV.

        Returns:
            List of polling place dictionaries
        """
        rows = self._read_csv()
        polling_places = {}
        polling_place_counter = {}

        for row in rows:
            county_name = row['COUNTY NAME'].strip()
            name = row['NAME'].strip()
            address = row['ADDRESS'].strip()
            city = row['CITY'].strip()
            zip_code = row['ZIP CODE'].strip()

            # Create unique key for polling place
            polling_place_key = (county_name, name, address, city)

            # Create or get polling place ID
            if polling_place_key not in polling_places:
                if county_name not in polling_place_counter:
                    polling_place_counter[county_name] = 1

                pp_id = f"OH-{county_name.replace(' ', '').upper()}-PP-{polling_place_counter[county_name]:04d}"
                polling_place_counter[county_name] += 1

                polling_places[polling_place_key] = {
                    'id': pp_id,
                    'name': name,
                    'address_line1': address,
                    'city': city,
                    'state': 'OH',
                    'zip_code': zip_code,
                    'county': county_name,
                }

        places = list(polling_places.values())
        self.app.logger.info(f"Extracted {len(places)} unique polling places")

        # Check which places need geocoding (new or address changed)
        from models import PollingPlace
        places_to_geocode = []
        
        for place in places:
            existing = self.db.session.get(PollingPlace, place['id'])
            if not existing:
                # New place, needs geocoding
                places_to_geocode.append(place)
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
                    self.app.logger.info(f"Address changed for {place['name']}, will re-geocode")
                else:
                    # Preserve existing coordinates
                    if existing.latitude is not None:
                        place['latitude'] = existing.latitude
                    if existing.longitude is not None:
                        place['longitude'] = existing.longitude

        # Geocode only the places that need it
        if places_to_geocode:
            self.app.logger.info(f"Geocoding {len(places_to_geocode)} places (new or address changed)")
            self._geocode_addresses(places_to_geocode)
        else:
            self.app.logger.info("No addresses changed, skipping geocoding")

        return places

    def fetch_precincts(self) -> List[Dict[str, Any]]:
        """
        Fetch precinct data from the CSV.

        Returns:
            List of precinct dictionaries with polling_place_id assignments
        """
        rows = self._read_csv()
        precincts = []

        # First, build a lookup dictionary of polling places without geocoding
        # We'll read the CSV directly to avoid the expensive geocoding in fetch_polling_places()
        polling_places = {}
        polling_place_counter = {}
        
        for row in rows:
            county_name = row['COUNTY NAME'].strip()
            name = row['NAME'].strip()
            address = row['ADDRESS'].strip()
            city = row['CITY'].strip()
            zip_code = row['ZIP CODE'].strip()

            # Create unique key for polling place
            polling_place_key = (county_name, name, address, city)

            # Create or get polling place ID
            if polling_place_key not in polling_places:
                if county_name not in polling_place_counter:
                    polling_place_counter[county_name] = 1

                pp_id = f"OH-{county_name.replace(' ', '').upper()}-PP-{polling_place_counter[county_name]:04d}"
                polling_place_counter[county_name] += 1

                polling_places[polling_place_key] = {
                    'id': pp_id,
                    'name': name,
                    'address_line1': address,
                    'city': city,
                    'state': 'OH',
                    'zip_code': zip_code,
                    'county': county_name,
                }

        # Now process precincts using the lookup dictionary
        for row in rows:
            county_name = row['COUNTY NAME'].strip()
            precinct_name = row['Precinct Name'].strip()
            state_precinct_code = row['STATE PRECINCT CODE'].strip()
            county_precinct_code = row['COUNTY PRECINCT CODE'].strip()
            name = row['NAME'].strip()
            address = row['ADDRESS'].strip()
            city = row['CITY'].strip()

            # Find the polling place ID using our lookup dictionary
            polling_place_key = (county_name, name, address, city)
            polling_place = polling_places.get(polling_place_key)
            
            if not polling_place:
                self.app.logger.warning(f"Could not find polling place for precinct {precinct_name}")
                continue

            # Create precinct ID
            precinct_id = f"OH-{county_name.replace(' ', '').upper()}-{state_precinct_code}"

            precinct_data = {
                'id': precinct_id,
                'name': precinct_name,
                'state': 'OH',
                'county': county_name,
                'precinctcode': state_precinct_code,  # Add state precinct code
                'polling_place_id': polling_place['id'],
            }
            precincts.append(precinct_data)

        self.app.logger.info(f"Extracted {len(precincts)} precincts")
        return precincts

    def upload_file(self, file_path: str) -> Dict[str, Any]:
        """
        Handle file upload for Ohio plugin.

        Args:
            file_path: Path to the uploaded CSV file

        Returns:
            Dictionary with upload result
        """
        try:
            # Backup current file
            current_csv = os.path.join(os.path.dirname(__file__), '..', 'ohio.csv')
            backup_path = current_csv + '.backup'
            if os.path.exists(current_csv):
                os.rename(current_csv, backup_path)

            # Copy uploaded file to ohio.csv
            import shutil
            shutil.copy(file_path, current_csv)

            self.app.logger.info(f"Uploaded new CSV file for Ohio plugin")
            return {
                'success': True,
                'message': 'File uploaded successfully. Backup created.'
            }
        except Exception as e:
            self.app.logger.error(f"Error uploading file for Ohio: {e}")
            return {
                'success': False,
                'message': str(e)
            }