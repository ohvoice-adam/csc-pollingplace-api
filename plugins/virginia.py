"""
Virginia Plugin - Fetches polling place and precinct data from Virginia Department of Elections

Data source: https://www.elections.virginia.gov/resultsreports/registration-statistics/
Format: Excel (.xlsx) files with polling locations and precinct assignments
"""

import re
import requests
import pandas as pd
from typing import List, Dict, Any
from io import BytesIO
from plugins.base_plugin import BasePlugin


class VirginiaPlugin(BasePlugin):
    """
    Virginia plugin that fetches polling place and precinct data from
    Virginia Department of Elections Excel files.
    """

    # Election data URLs (most recent first)
    ELECTIONS = {
        '2025-11-04': 'https://www.elections.virginia.gov/media/registration-statistics/2025-November-General-Election-Day-Polling-Locations-20250912.xlsx',
        '2025-06-10': 'https://www.elections.virginia.gov/media/registration-statistics/2025-June-Democratic-Primary-Election-Day-Polling-Locations-(5-28-25).xlsx',
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
                address1 = str(row['Address Line 1']).strip()
                address2 = str(row['Address Line 2']).strip() if pd.notna(row['Address Line 2']) else None
                city = str(row['City']).strip()
                zip_code = str(row['Zip Code']).strip()

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

    def import_historical_data(self) -> Dict[str, Any]:
        """
        Import data from all elections in chronological order.
        This builds up a complete assignment history.

        Returns:
            Dictionary with import results for each election
        """
        results = {}

        # Sort elections chronologically (oldest first)
        sorted_elections = sorted(self.ELECTIONS.items())

        self.app.logger.info(f"Starting historical import for {len(sorted_elections)} elections")

        for election_date, url in sorted_elections:
            self.app.logger.info(f"Importing election: {election_date}")

            try:
                # Download and parse this election's data
                df = self._download_excel(url)
                polling_places, precincts = self._parse_excel_data(df)

                # Use the parent sync() method but temporarily override fetch methods
                old_fetch_pp = self.fetch_polling_places
                old_fetch_pr = self.fetch_precincts

                # Override to return this election's data
                self.fetch_polling_places = lambda: polling_places
                self.fetch_precincts = lambda: precincts

                # Run sync for this election
                sync_result = self.sync()

                # Restore original methods
                self.fetch_polling_places = old_fetch_pp
                self.fetch_precincts = old_fetch_pr

                results[election_date] = {
                    'success': sync_result['success'],
                    'polling_places': sync_result['polling_places'],
                    'precincts': sync_result['precincts']
                }

                self.app.logger.info(
                    f"Election {election_date}: "
                    f"PP added={sync_result['polling_places']['added']}, "
                    f"PP updated={sync_result['polling_places']['updated']}, "
                    f"Precincts added={sync_result['precincts']['added']}, "
                    f"Precincts updated={sync_result['precincts']['updated']}"
                )

            except Exception as e:
                self.app.logger.error(f"Error importing election {election_date}: {e}")
                results[election_date] = {
                    'success': False,
                    'error': str(e)
                }

        return results
