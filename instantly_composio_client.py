"""
Instantly.ai Integration via Composio REST API
Uses REST API directly instead of Python SDK due to SDK bugs
"""
import os
import requests
from typing import List, Dict, Any, Optional


class InstantlyComposioClient:
    """
    Wrapper around Composio's Instantly.ai integration using REST API
    
    Usage:
        client = InstantlyComposioClient()
        campaigns = client.list_campaigns()
        client.create_lead(campaign_id='...', email='test@example.com', ...)
    """
    
    def __init__(self, api_key: str = None, account_id: str = None):
        """
        Initialize the client
        
        Args:
            api_key: Composio API key (or from COMPOSIO_API_KEY env var)
            account_id: Connected account ID (or from COMPOSIO_INSTANTLY_ACCOUNT_ID)
        """
        self.api_key = api_key or os.getenv("COMPOSIO_API_KEY")
        self.account_id = account_id or os.getenv("COMPOSIO_INSTANTLY_ACCOUNT_ID")
        self.base_url = "https://backend.composio.dev/api/v2"
        
        if not self.api_key:
            raise ValueError("COMPOSIO_API_KEY not found in environment or parameters")
        if not self.account_id:
            raise ValueError("COMPOSIO_INSTANTLY_ACCOUNT_ID not found in environment or parameters")
    
    def _execute_action(self, action_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a Composio action via REST API
        
        Args:
            action_name: Name of the action (e.g., 'INSTANTLY_LIST_CAMPAIGNS')
            params: Parameters for the action
        
        Returns:
            Response data from the action
        
        Raises:
            Exception: If the API call fails
        """
        url = f"{self.base_url}/actions/{action_name}/execute"
        headers = {
            "X-API-Key": self.api_key,
            "Content-Type": "application/json"
        }
        data = {
            "connectedAccountId": self.account_id,
            "input": params
        }
        
        response = requests.post(url, json=data, headers=headers, timeout=30)
        
        if response.status_code != 200:
            raise Exception(f"Composio API error ({response.status_code}): {response.text}")
        
        result = response.json()
        
        # Check if the action was successful
        if not result.get('successful', False):
            error = result.get('error', 'Unknown error')
            raise Exception(f"Action failed: {error}")
        
        return result.get('data', {})
    
    # ===== Campaign Methods =====
    
    def list_campaigns(
        self,
        limit: Optional[int] = None,
        search: Optional[str] = None,
        starting_after: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        List all campaigns
        
        Args:
            limit: Number of campaigns to return (1-100)
            search: Search text to filter campaign names
            starting_after: Cursor for pagination
        
        Returns:
            List of campaign dicts
        """
        params = {}
        if limit is not None:
            params['limit'] = limit
        if search:
            params['search'] = search
        if starting_after:
            params['starting_after'] = starting_after
        
        result = self._execute_action('INSTANTLY_LIST_CAMPAIGNS', params)
        return result.get('items', [])
    
    def get_campaign(self, campaign_id: str) -> Dict[str, Any]:
        """
        Get campaign details
        
        Args:
            campaign_id: Instantly campaign ID
        
        Returns:
            Campaign dict
        """
        result = self._execute_action('INSTANTLY_GET_CAMPAIGN', {
            'campaign_id': campaign_id
        })
        return result
    
    def get_campaign_analytics(self, campaign_id: str) -> Dict[str, Any]:
        """
        Get campaign analytics (opens, clicks, replies)
        
        Args:
            campaign_id: Instantly campaign ID
        
        Returns:
            Analytics dict
        """
        result = self._execute_action('INSTANTLY_GET_CAMPAIGN_ANALYTICS', {
            'campaign_id': campaign_id
        })
        return result
    
    # ===== Lead Methods =====
    
    def create_lead(
        self,
        campaign_id: str,
        email: str,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        company_name: Optional[str] = None,
        custom_variables: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Add a single lead to a campaign
        
        Args:
            campaign_id: Instantly campaign ID
            email: Lead email address
            first_name: First name (optional)
            last_name: Last name (optional)
            company_name: Company name (optional)
            custom_variables: Additional fields for personalization
                Example: {
                    'business_type': 'Garden Center',
                    'city': 'Austin',
                    'tier': 'A'
                }
        
        Returns:
            Result dict with success/failure
        """
        params = {
            'campaign_id': campaign_id,
            'email': email
        }
        
        if first_name:
            params['first_name'] = first_name
        if last_name:
            params['last_name'] = last_name
        if company_name:
            params['company_name'] = company_name
        if custom_variables:
            params['variables'] = custom_variables
        
        result = self._execute_action('INSTANTLY_CREATE_LEAD', params)
        return result
    
    def list_leads(
        self,
        campaign_id: Optional[str] = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        List leads (optionally filtered by campaign)
        
        Args:
            campaign_id: Filter by campaign ID (optional)
            skip: Number of leads to skip
            limit: Maximum leads to return
        
        Returns:
            List of lead dicts
        """
        params = {
            'skip': skip,
            'limit': limit
        }
        if campaign_id:
            params['campaign_id'] = campaign_id
        
        result = self._execute_action('INSTANTLY_LIST_LEADS', params)
        return result.get('items', [])
    
    def create_leads_batch(
        self,
        campaign_id: str,
        leads: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Add multiple leads to a campaign
        
        Args:
            campaign_id: Instantly campaign ID
            leads: List of lead dicts, each with:
                - email (required)
                - first_name, last_name, company_name (optional)
                - custom_variables (optional dict)
        
        Returns:
            List of results for each lead (success/failure)
        """
        results = []
        
        for lead in leads:
            try:
                result = self.create_lead(
                    campaign_id=campaign_id,
                    email=lead['email'],
                    first_name=lead.get('first_name'),
                    last_name=lead.get('last_name'),
                    company_name=lead.get('company_name'),
                    custom_variables=lead.get('custom_variables')
                )
                results.append({
                    'email': lead['email'],
                    'success': True,
                    'data': result
                })
            except Exception as e:
                results.append({
                    'email': lead['email'],
                    'success': False,
                    'error': str(e)
                })
        
        return results


if __name__ == "__main__":
    # Example usage / testing
    import sys
    from pathlib import Path
    
    # Load .env file
    env_file = Path(__file__).parent / '.env'
    if env_file.exists():
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key] = value
    
    print("=" * 60)
    print("Instantly Composio Client Test")
    print("=" * 60)
    print()
    
    try:
        # Initialize client
        client = InstantlyComposioClient()
        print("✓ Client initialized")
        print(f"  API Key: {client.api_key[:10]}...")
        print(f"  Account ID: {client.account_id}")
        print()
        
        # List campaigns
        print("Testing: List campaigns...")
        campaigns = client.list_campaigns()
        print(f"✅ Found {len(campaigns)} campaigns")
        
        if campaigns:
            for i, campaign in enumerate(campaigns[:3], 1):
                name = campaign.get('name', 'Unnamed')
                campaign_id = campaign.get('id', 'N/A')
                status = campaign.get('status', 'unknown')
                print(f"  {i}. {name} (ID: {campaign_id}, Status: {status})")
        else:
            print("  (No campaigns found - create one in Instantly first)")
        
        print()
        print("=" * 60)
        print("✅ ALL TESTS PASSED!")
        print("=" * 60)
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        sys.exit(1)
