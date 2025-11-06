"""
BigQuery Plugin for querying voter data by state

This plugin connects to BigQuery and returns a dictionary mapping precincts to number of voters.
"""
import os

from typing import Dict, Any

# Try to import Google Cloud BigQuery, handle gracefully if not available
try:
    from google.cloud import bigquery
    BIGQUERY_AVAILABLE = True
except ImportError:
    BIGQUERY_AVAILABLE = False
    bigquery = None

from plugins.base_plugin import BasePlugin

class BigQueryPlugin(BasePlugin):
    """
    Plugin for querying BigQuery to get voter data by state
    """
    
    def __init__(self, app, db):
        """
        Initialize the plugin with Flask app and database instances.
        
        Args:
            app: Flask application instance
            db: SQLAlchemy database instance
        """
        super().__init__(app, db)
        self.client = None
        
        # Check if BigQuery is available
        if not BIGQUERY_AVAILABLE:
            self.app.logger.warning("Google Cloud BigQuery not available. BigQuery plugin will be disabled.")
            return
        
    @property
    def name(self) -> str:
        """Unique name for this plugin"""
        return 'bigquery'
    
    @property
    def state_code(self) -> str:
        """Two-letter state code"""
        return 'ALL'  # This plugin can handle any state
    
    @property
    def description(self) -> str:
        """Human-readable description of this plugin"""
        return 'BigQuery plugin for querying voter data by state'
    
    def connect_to_bigquery(self):
        """
        Connect to BigQuery client.
        This assumes authentication is set up via environment variables or application default credentials.
        """
        if not BIGQUERY_AVAILABLE:
            raise RuntimeError("Google Cloud BigQuery not available. Install google-cloud-bigquery package.")
        
        if self.client is None:
            # Type: ignore because we've already checked BIGQUERY_AVAILABLE
            self.client = bigquery.Client()  # type: ignore
        return self.client
    
    def fetch_polling_places(self, state_code: str = 'OH') -> Any:
        """
        Query BigQuery for voter data by state.
        
        Args:
            state_code: Two-letter state code (default: 'OH')
            
        Returns:
            Dictionary mapping precinct names to number of voters
        """
        if not BIGQUERY_AVAILABLE:
            self.app.logger.warning("BigQuery not available, returning empty result")
            return {}
        
        try:
            # Connect to BigQuery
            client = self.connect_to_bigquery()
            
            # Get the query from environment variable
            # The query should contain {state_code} as a placeholder for the state code
            query_template = os.getenv('BIGQUERY_QUERY_TEMPLATE', """
            SELECT
                precinctname,
                precinctcode,
                COUNT(DISTINCT(p.dwid)) as registered
            FROM `prod-sv-oh-dd7a76f2.catalist_OH.Person` p
            LEFT JOIN `prod-sv-oh-dd7a76f2.catalist_OH.District` d
                ON p.dwid = d.dwid
                AND p.voterstatus = 'active'
                AND d.state = '{state_code}'
            GROUP BY 1,2
            """)
            
            # Format the query with the state code
            query = query_template.format(state_code=state_code)
            
            # Execute the query
            self.app.logger.info(f"Executing BigQuery query for state: {state_code}")
            query_job = client.query(query)
            
            # Process results
            results = {}
            for row in query_job:
                # Create a key combining precinct name and code
                precinct_key = f"{row.precinctname} ({row.precinctcode})"
                results[precinct_key] = int(row.registered)
            
            self.app.logger.info(f"Retrieved {len(results)} precincts for state {state_code}")
            return results
            
        except Exception as e:
            self.app.logger.error(f"Error querying BigQuery: {str(e)}")
            raise Exception(f"Failed to query BigQuery: {str(e)}")
    
    def get_voter_data_by_state(self, state_code: str = 'OH') -> Dict[str, int]:
        """
        Public method to get voter data by state.
        
        Args:
            state_code: Two-letter state code (default: 'OH')
            
        Returns:
            Dictionary mapping precinct names to number of voters
        """
        return self.fetch_polling_places(state_code)