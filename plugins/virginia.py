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
from typing import List, Dict, Any, Optional
from io import BytesIO
from datetime import datetime
from urllib.parse import quote, urljoin
from bs4 import BeautifulSoup
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

    def _infer_location_type(self, name: str) -> str:
        """
        Infer location type from polling place name.
        
        Args:
            name: The polling place name
            
        Returns:
            Location type: "drop box", "election day", or "early voting"
        """
        name_lower = name.lower()
        
        # Check for drop box indicators
        drop_box_keywords = ['drop box', 'ballot drop', 'dropbox', 'ballot box']
        if any(keyword in name_lower for keyword in drop_box_keywords):
            return 'drop box'
        
        # Check for early voting indicators
        early_voting_keywords = ['early voting', 'early vote', 'advance voting', 'early in-person']
        if any(keyword in name_lower for keyword in early_voting_keywords):
            return 'early voting'
        
        # Default to election day
        return 'election day'

    def _discover_available_files(self) -> List[Dict[str, Any]]:
        """
        Discover available polling place Excel files from Virginia Department of Elections website.
        
        Scrapes the registration statistics page to find Excel files containing polling location data.
        Extracts file metadata including URLs, dates from filenames, and election types.
        
        Returns:
            List of dictionaries with file metadata:
            - url: str - Direct URL to the Excel file
            - filename: str - Filename from the URL
            - election_date: str - Parsed election date (YYYY-MM-DD)
            - election_name: str - Generated election name
            - election_type: str - Type of election (general, primary, etc.)
            - file_date: str - Date from filename (YYYY-MM-DD)
        """
        base_url = "https://www.elections.virginia.gov/resultsreports/registration-statistics/"
        
        try:
            self.app.logger.info(f"Discovering files from: {base_url}")
            response = requests.get(base_url, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            files = []
            
            # Find all links to Excel files
            for link in soup.find_all('a', href=True):
                href = link.get('href', '')
                if href.endswith('.xlsx') and 'polling' in href.lower():
                    # Convert relative URL to absolute
                    if href.startswith('/'):
                        file_url = urljoin('https://www.elections.virginia.gov', href)
                    else:
                        file_url = href
                    
                    # Extract filename
                    filename = href.split('/')[-1]
                    
                    # Parse metadata from filename
                    metadata = self._parse_filename_metadata(filename)
                    if metadata:
                        metadata['url'] = file_url
                        metadata['filename'] = filename
                        files.append(metadata)
                        self.app.logger.debug(f"Found file: {filename} -> {metadata['election_name']}")
            
            # Sort by election date (most recent first)
            files.sort(key=lambda x: x.get('election_date', ''), reverse=True)
            
            self.app.logger.info(f"Discovered {len(files)} polling place files")
            return files
            
        except requests.RequestException as e:
            self.app.logger.error(f"Failed to fetch discovery page: {e}")
            return []
        except Exception as e:
            self.app.logger.error(f"Error discovering files: {e}")
            return []

    def _parse_filename_metadata(self, filename: str) -> Optional[Dict[str, Any]]:
        """
        Parse election metadata from Virginia Excel filename.
        
        Expected format patterns:
        - "YYYY-Month-ElectionType-Polling-Locations-(MM-DD-YY).xlsx"
        - "YYYY-Month-ElectionType-Polling-Locations.xlsx"
        
        Args:
            filename: The Excel filename to parse
            
        Returns:
            Dictionary with parsed metadata or None if parsing failed
        """
        try:
            # Remove .xlsx extension
            base_name = filename.replace('.xlsx', '')
            
            # Extract date in parentheses if present (MM-DD-YY format)
            file_date = None
            if '(' in base_name and ')' in base_name:
                date_str = base_name.split('(')[1].split(')')[0]
                try:
                    # Convert MM-DD-YY to YYYY-MM-DD
                    month, day, year = date_str.split('-')
                    year = '20' + year if len(year) == 2 else year
                    file_date = f"{year}-{month.zfill(2)}-{day.zfill(2)}"
                except:
                    pass
            # Also check for date pattern at end of filename (YYYYMMDD format)
            date_match = re.search(r'(\d{8})$', base_name)
            if date_match:
                date_str = date_match.group(1)
                try:
                    # Convert YYYYMMDD to YYYY-MM-DD
                    year = date_str[:4]
                    month = date_str[4:6]
                    day = date_str[6:8]
                    file_date = f"{year}-{month}-{day}"
                except:
                    pass
            
            # Extract year and election type
            year_match = re.search(r'(\d{4})', base_name)
            if not year_match:
                return None
            
            year = year_match.group(1)
            
            # Determine election type
            election_type = 'unknown'
            if 'general' in base_name.lower():
                election_type = 'general'
            elif 'primary' in base_name.lower():
                if 'presidential' in base_name.lower():
                    election_type = 'presidential_primary'
                elif 'democratic' in base_name.lower() or 'republican' in base_name.lower():
                    election_type = 'party_primary'
                else:
                    election_type = 'primary'
            elif 'special' in base_name.lower():
                election_type = 'special'
            elif 'municipal' in base_name.lower():
                election_type = 'municipal'
            
            # Extract month for date parsing
            month_match = re.search(r'(January|February|March|April|May|June|July|August|September|October|November|December)', base_name, re.IGNORECASE)
            month_name = month_match.group(1) if month_match else 'November'
            
            # Generate election date (use file_date if available, otherwise estimate)
            if file_date:
                election_date = file_date
            else:
                # Estimate based on election type and month
                if election_type == 'general':
                    election_date = f"{year}-11-05"  # First Tuesday after first Monday in November
                elif election_type == 'presidential_primary':
                    election_date = f"{year}-03-05"  # Super Tuesday
                elif election_type == 'party_primary':
                    election_date = f"{year}-06-18"  # Typical June primary
                else:
                    election_date = f"{year}-11-05"  # Default to November
            
            # Generate election name
            election_name = self._generate_election_name_from_metadata(election_date, election_type)
            
            return {
                'election_date': election_date,
                'election_name': election_name,
                'election_type': election_type,
                'file_date': file_date or election_date,
                'year': year,
                'month': month_name
            }
            
        except Exception as e:
            self.app.logger.warning(f"Failed to parse metadata from filename {filename}: {e}")
            return None

    def _generate_election_name_from_metadata(self, election_date: str, election_type: str) -> str:
        """
        Generate human-readable election name from date and type.
        
        Args:
            election_date: Date string in YYYY-MM-DD format
            election_type: Type of election
            
        Returns:
            Human-readable election name
        """
        try:
            date_obj = datetime.strptime(election_date, '%Y-%m-%d')
            year = date_obj.year
            
            if election_type == 'general':
                return f"{year} General Election"
            elif election_type == 'presidential_primary':
                return f"{year} Presidential Primary"
            elif election_type == 'party_primary':
                return f"{year} Primary Election"
            elif election_type == 'special':
                return f"{year} Special Election"
            elif election_type == 'municipal':
                return f"{year} Municipal Election"
            else:
                month = date_obj.strftime('%B')
                return f"{year} {month} Election"
                
        except Exception:
            return f"Election {election_date}"

    def get_available_elections(self) -> List[Dict[str, Any]]:
        """
        Get structured data about discovered elections.
        
        Returns:
            List of election dictionaries with metadata:
            - election_date: str - Election date (YYYY-MM-DD)
            - election_name: str - Human-readable election name
            - election_type: str - Type of election
            - url: str - Direct URL to Excel file
            - filename: str - Filename
            - file_date: str - Date from file
            - is_recent: bool - Whether election is within last 2 years
        """
        try:
            files = self._discover_available_files()
            
            # Determine recent elections (within 2 years)
            today = datetime.now().date()
            two_years_ago = today.replace(year=today.year - 2)
            
            elections = []
            for file_data in files:
                try:
                    election_date = datetime.strptime(file_data['election_date'], '%Y-%m-%d').date()
                    is_recent = election_date >= two_years_ago
                    
                    election_data = {
                        'election_date': file_data['election_date'],
                        'election_name': file_data['election_name'],
                        'election_type': file_data['election_type'],
                        'url': file_data['url'],
                        'filename': file_data['filename'],
                        'file_date': file_data['file_date'],
                        'is_recent': is_recent
                    }
                    elections.append(election_data)
                    
                except Exception as e:
                    self.app.logger.warning(f"Error processing election data: {e}")
                    continue
            
            self.app.logger.info(f"Processed {len(elections)} elections from discovered files")
            return elections
            
        except Exception as e:
            self.app.logger.error(f"Error getting available elections: {e}")
            return []

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
                address1 = str(row['Address Line 1']).strip() if str(row['Address Line 1']) != 'nan' else ''
                address2 = str(row['Address Line 2']).strip() if str(row['Address Line 2']) != 'nan' else None
                city = str(row['City']).strip() if str(row['City']) != 'nan' else ''
                zip_code = str(row['Zip Code']).strip() if str(row['Zip Code']) != 'nan' else ''

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
                        'location_type': self._infer_location_type(location),
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

    def fetch_polling_places(self, file_url: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Fetch polling place data from Virginia elections.

        Args:
            file_url: Optional URL to specific Excel file. If not provided, uses most recent election.

        Returns:
            List of polling place dictionaries
        """
        if file_url:
            url = file_url
            self.app.logger.info(f"Fetching Virginia polling places from provided URL: {url}")
        else:
            # Get most recent election from hardcoded list
            most_recent_date = max(self.ELECTIONS.keys())
            url = self.ELECTIONS[most_recent_date]
            self.app.logger.info(f"Fetching Virginia polling places from {most_recent_date} election")

        # Download and parse
        df = self._download_excel(url)
        polling_places, _ = self._parse_excel_data(df)

        self.app.logger.info(f"Extracted {len(polling_places)} unique polling places")

        # Check which places need geocoding (new or address changed)
        from models import PollingPlace
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

    def fetch_precincts(self, file_url: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Fetch precinct data from Virginia elections.

        Args:
            file_url: Optional URL to specific Excel file. If not provided, uses most recent election.

        Returns:
            List of precinct dictionaries with polling_place_id assignments
        """
        if file_url:
            url = file_url
            self.app.logger.info(f"Fetching Virginia precincts from provided URL: {url}")
        else:
            # Get most recent election from hardcoded list
            most_recent_date = max(self.ELECTIONS.keys())
            url = self.ELECTIONS[most_recent_date]
            self.app.logger.info(f"Fetching Virginia precincts from {most_recent_date} election")

        # Download and parse
        df = self._download_excel(url)
        _, precincts = self._parse_excel_data(df)

        self.app.logger.info(f"Extracted {len(precincts)} precincts")
        return precincts

    def _get_or_create_election(self, election_date, election_name, url=None, filename=None):
        """
        Get or create an Election record for the given date and name.
        Enhanced to better parse election metadata from file names and URLs.
        Includes validation to prevent duplicate election records.

        Args:
            election_date: Date object for the election
            election_name: Name of the election (e.g., "2024 General Election")
            url: Optional URL to the election file for metadata parsing
            filename: Optional filename for metadata parsing

        Returns:
            Election object
        """
        from app import Election
        from sqlalchemy.exc import IntegrityError

        # Check if election already exists
        election = Election.query.filter_by(date=election_date, state=self.state_code).first()

        if not election:
            # Enhanced election name generation if we have URL or filename
            if url or filename:
                enhanced_name = self._parse_election_metadata_from_source(url, filename, election_date)
                if enhanced_name:
                    election_name = enhanced_name

            # Validate election data before creation
            if not self._validate_election_data(election_date, election_name):
                raise ValueError(f"Invalid election data: date={election_date}, name={election_name}")

            # Create new election record with error handling for duplicates
            try:
                election = Election(
                    date=election_date,
                    name=election_name,
                    state=self.state_code
                )
                self.db.session.add(election)
                self.db.session.commit()
                self.app.logger.info(f"Created election record: {election_name} ({election_date})")
            except IntegrityError as e:
                self.db.session.rollback()
                # Handle race condition where another process created the same election
                self.app.logger.warning(f"Election already exists (race condition): {election_name} ({election_date})")
                election = Election.query.filter_by(date=election_date, state=self.state_code).first()
                if not election:
                    raise ValueError(f"Failed to create or retrieve election: {election_name} ({election_date})") from e
        else:
            self.app.logger.info(f"Using existing election record: {election_name} ({election_date})")

        return election

    def _validate_election_data(self, election_date, election_name):
        """
        Validate election data to prevent duplicates and ensure data integrity.
        
        Args:
            election_date: Date object for the election
            election_name: Name of the election
            
        Returns:
            True if valid, False otherwise
        """
        try:
            # Check if election with same date and state already exists
            from app import Election
            existing = Election.query.filter_by(date=election_date, state=self.state_code).first()
            if existing:
                self.app.logger.warning(f"Election already exists for {election_date} in {self.state_code}: {existing.name}")
                return False
            
            # Validate election name is not empty
            if not election_name or not election_name.strip():
                self.app.logger.error("Election name cannot be empty")
                return False
                
            # Validate election date is not None
            if not election_date:
                self.app.logger.error("Election date cannot be None")
                return False
                
            return True
            
        except Exception as e:
            self.app.logger.error(f"Error validating election data: {e}")
            return False

    def _parse_election_metadata_from_source(self, url, filename, fallback_date):
        """
        Parse election metadata from URL or filename to generate better election names.
        
        Args:
            url: URL to the election file
            filename: Filename of the election file
            fallback_date: Date to use if parsing fails
            
        Returns:
            Enhanced election name or None if parsing fails
        """
        source_name = None
        try:
            # Use filename if available, otherwise extract from URL
            source_name = filename
            if not source_name and url:
                source_name = url.split('/')[-1]
            
            if not source_name:
                return None
                
            # Parse metadata using existing method
            metadata = self._parse_filename_metadata(source_name)
            if metadata and metadata.get('election_name'):
                return metadata['election_name']
                
            return None
            
        except Exception as e:
            self.app.logger.warning(f"Failed to parse election metadata from {source_name or 'unknown source'}: {e}")
            return None

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

                self.fetch_polling_places = lambda file_url=None: polling_places
                # Don't fetch precincts during sync() - we'll do that separately with the correct date
                self.fetch_precincts = lambda file_url=None: []

                # Sync polling places
                sync_result = self.sync()

                # Restore fetch methods
                self.fetch_polling_places = old_fetch_pp
                self.fetch_precincts = old_fetch_pr

                # Now sync precincts separately with the actual election date (not today)
                # This ensures last_change_date reflects the actual election date
                # and links assignments to the election
                self.fetch_precincts = lambda file_url=None: precincts
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

    def sync_single_file(self, file_url, election_date=None, election_name=None):
        """
        Sync data from a single file with proper election tracking.
        
        Args:
            file_url: URL to the specific Excel file to sync
            election_date: Optional date for the election (parsed from file if not provided)
            election_name: Optional name for the election (generated if not provided)
            
        Returns:
            Dictionary with sync results including election information
        """
        try:
            self.app.logger.info(f"Starting single file sync from: {file_url}")
            
            # Extract filename from URL
            filename = file_url.split('/')[-1]
            
            # Parse election metadata from file if not provided
            if not election_date or not election_name:
                metadata = self._parse_filename_metadata(filename)
                if metadata:
                    if not election_date:
                        election_date = datetime.strptime(metadata['election_date'], '%Y-%m-%d').date()
                    if not election_name:
                        election_name = metadata['election_name']
            
            # Fallback to current date if still not available
            if not election_date:
                from datetime import date
                election_date = date.today()
                self.app.logger.warning(f"Could not parse election date from {filename}, using today's date")
            
            if not election_name:
                election_name = f"Election {election_date}"
                self.app.logger.warning(f"Could not parse election name from {filename}, using fallback")
            
            # Get or create election record
            election = self._get_or_create_election(election_date, election_name, file_url, filename)
            
            # Download and parse the file
            df = self._download_excel(file_url)
            polling_places, precincts = self._parse_excel_data(df)
            
            # Override fetch methods to return this file's data
            old_fetch_pp = self.fetch_polling_places
            old_fetch_pr = self.fetch_precincts
            
            self.fetch_polling_places = lambda file_url=None: polling_places
            self.fetch_precincts = lambda file_url=None: precincts
            
            try:
                # Sync polling places (without election_id for polling places)
                sync_result = self.sync()
                
                # Sync precincts with election_id
                precinct_result = self.sync_precincts(
                    effective_date=election_date,
                    election_id=election.id
                )
                
                return {
                    'success': True,
                    'file_url': file_url,
                    'filename': filename,
                    'election': {
                        'id': election.id,
                        'date': election.date.isoformat(),
                        'name': election.name,
                        'state': election.state
                    },
                    'polling_places': sync_result['polling_places'],
                    'precincts': precinct_result,
                    'message': f'Successfully synced {filename} for {election_name}'
                }
                
            finally:
                # Restore fetch methods
                self.fetch_polling_places = old_fetch_pp
                self.fetch_precincts = old_fetch_pr
                
        except Exception as e:
            self.app.logger.error(f"Error in single file sync: {e}")
            return {
                'success': False,
                'file_url': file_url,
                'error': str(e),
                'message': f'Failed to sync file: {str(e)}'
            }

    def sync_multiple_files(self, file_urls=None, election_dates=None):
        """
        Sync data from multiple files with proper election tracking.
        
        Args:
            file_urls: List of URLs to Excel files to sync (if None, uses discovered files)
            election_dates: Optional list of election dates corresponding to files
            
        Returns:
            Dictionary with combined sync results
        """
        try:
            # Discover files if not provided
            if not file_urls:
                discovered_files = self._discover_available_files()
                file_urls = [f['url'] for f in discovered_files]
                self.app.logger.info(f"Discovered {len(file_urls)} files for multi-file sync")
            
            results = {}
            total_pp_added = total_pp_updated = total_p_added = total_p_updated = 0
            errors = 0
            
            for i, file_url in enumerate(file_urls):
                try:
                    # Get corresponding election date if provided
                    election_date = election_dates[i] if election_dates and i < len(election_dates) else None
                    
                    # Sync individual file
                    result = self.sync_single_file(file_url, election_date)
                    
                    if result['success']:
                        filename = result['filename']
                        results[filename] = result
                        
                        # Aggregate statistics
                        total_pp_added += result['polling_places']['added']
                        total_pp_updated += result['polling_places']['updated']
                        total_p_added += result['precincts']['added']
                        total_p_updated += result['precincts']['updated']
                        
                        self.app.logger.info(f"Successfully synced {filename}")
                    else:
                        errors += 1
                        self.app.logger.error(f"Failed to sync {file_url}: {result['error']}")
                        
                except Exception as e:
                    errors += 1
                    filename = file_url.split('/')[-1] if file_url else f'file_{i}'
                    results[filename] = {
                        'success': False,
                        'error': str(e),
                        'file_url': file_url
                    }
                    self.app.logger.error(f"Error syncing file {i}: {e}")
            
            return {
                'success': errors == 0,
                'files_processed': len(file_urls),
                'files_successful': len(file_urls) - errors,
                'files_failed': errors,
                'total_polling_places': {
                    'added': total_pp_added,
                    'updated': total_pp_updated
                },
                'total_precincts': {
                    'added': total_p_added,
                    'updated': total_p_updated
                },
                'results': results,
                'message': f'Processed {len(file_urls)} files with {errors} errors'
            }
            
        except Exception as e:
            self.app.logger.error(f"Error in multiple file sync: {e}")
            return {
                'success': False,
                'error': str(e),
                'message': f'Multi-file sync failed: {str(e)}'
            }

    def validate_assignment_history(self, election_id=None):
        """
        Validate assignment history for data integrity.
        
        Args:
            election_id: Optional election ID to validate specific election assignments
            
        Returns:
            Dictionary with validation results
        """
        try:
            from models import PrecinctAssignment, Precinct, Election
            
            validation_results = {
                'total_assignments': 0,
                'current_assignments': 0,
                'assignments_without_election': 0,
                'orphaned_assignments': 0,
                'duplicate_current_assignments': 0,
                'issues': []
            }
            
            # Build query based on election_id
            query = self.db.session.query(PrecinctAssignment)
            if election_id:
                query = query.filter_by(election_id=election_id)
            
            assignments = query.all()
            validation_results['total_assignments'] = len(assignments)
            
            # Track current assignments per precinct
            current_assignments_by_precinct = {}
            
            for assignment in assignments:
                # Check for assignments without election
                if not assignment.election_id:
                    validation_results['assignments_without_election'] += 1
                    validation_results['issues'].append(
                        f"Assignment {assignment.id} for precinct {assignment.precinct_id} has no election_id"
                    )
                
                # Check for current assignments
                if assignment.removed_date is None:
                    validation_results['current_assignments'] += 1
                    
                    # Check for duplicate current assignments
                    precinct_id = assignment.precinct_id
                    if precinct_id in current_assignments_by_precinct:
                        validation_results['duplicate_current_assignments'] += 1
                        validation_results['issues'].append(
                            f"Multiple current assignments found for precinct {precinct_id}: "
                            f"assignments {current_assignments_by_precinct[precinct_id]} and {assignment.id}"
                        )
                    else:
                        current_assignments_by_precinct[precinct_id] = assignment.id
                
                # Check for orphaned assignments (precinct or polling place doesn't exist)
                if not assignment.precinct:
                    validation_results['orphaned_assignments'] += 1
                    validation_results['issues'].append(
                        f"Assignment {assignment.id} references non-existent precinct {assignment.precinct_id}"
                    )
                
                if not assignment.polling_place:
                    validation_results['orphaned_assignments'] += 1
                    validation_results['issues'].append(
                        f"Assignment {assignment.id} references non-existent polling place {assignment.polling_place_id}"
                    )
            
            # Log validation results
            if validation_results['issues']:
                self.app.logger.warning(
                    f"Assignment validation found {len(validation_results['issues'])} issues"
                )
                for issue in validation_results['issues'][:10]:  # Log first 10 issues
                    self.app.logger.warning(f"  {issue}")
                if len(validation_results['issues']) > 10:
                    self.app.logger.warning(f"  ... and {len(validation_results['issues']) - 10} more issues")
            else:
                self.app.logger.info("Assignment validation completed successfully with no issues found")
            
            return validation_results
            
        except Exception as e:
            self.app.logger.error(f"Error during assignment validation: {e}")
            return {
                'success': False,
                'error': str(e),
                'message': f'Validation failed: {str(e)}'
            }

    def repair_assignment_history(self, election_id=None, dry_run=True):
        """
        Repair assignment history issues.
        
        Args:
            election_id: Optional election ID to repair specific election assignments
            dry_run: If True, only report what would be repaired without making changes
            
        Returns:
            Dictionary with repair results
        """
        try:
            from models import PrecinctAssignment
            
            # First validate to identify issues
            validation = self.validate_assignment_history(election_id)
            
            repair_results = {
                'dry_run': dry_run,
                'issues_found': len(validation.get('issues', [])),
                'repairs_made': 0,
                'repairs_skipped': 0,
                'repair_details': []
            }
            
            if dry_run:
                repair_results['message'] = "Dry run completed - no changes made"
                return repair_results
            
            # Repair duplicate current assignments
            if validation['duplicate_current_assignments'] > 0:
                # Find and fix duplicate current assignments
                from models import Precinct
                from sqlalchemy import func
                
                # Find precincts with multiple current assignments
                duplicates = self.db.session.query(
                    PrecinctAssignment.precinct_id,
                    func.count(PrecinctAssignment.id).label('count')
                ).filter_by(removed_date=None).group_by(
                    PrecinctAssignment.precinct_id
                ).having(func.count(PrecinctAssignment.id) > 1).all()
                
                for precinct_id, count in duplicates:
                    # Get all current assignments for this precinct, ordered by creation date
                    current_assignments = self.db.session.query(PrecinctAssignment).filter_by(
                        precinct_id=precinct_id,
                        removed_date=None
                    ).order_by(PrecinctAssignment.created_at).all()
                    
                    # Keep the oldest one, mark others as removed
                    for assignment in current_assignments[1:]:
                        assignment.removed_date = datetime.now().date()
                        repair_results['repairs_made'] += 1
                        repair_results['repair_details'].append(
                            f"Marked duplicate assignment {assignment.id} for precinct {precinct_id} as removed"
                        )
            
            self.db.session.commit()
            repair_results['message'] = f"Repair completed - {repair_results['repairs_made']} repairs made"
            
            return repair_results
            
        except Exception as e:
            self.db.session.rollback()
            self.app.logger.error(f"Error during assignment repair: {e}")
            return {
                'success': False,
                'error': str(e),
                'message': f'Repair failed: {str(e)}'
            }
