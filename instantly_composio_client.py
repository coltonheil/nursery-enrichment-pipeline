"""
Composio-based Instantly.ai Client Wrapper
Provides simplified methods for nursery enrichment pipeline
"""

import os
from composio import Composio
from typing import List, Dict, Any, Optional


class InstantlyComposioClient:
    """
    Wrapper around Composio's Instantly.ai integration
    Provides simplified methods for our use case
    """
    
    def __init__(self, api_key: str = None, account_id: str = None):
        self.api_key = api_key or os.getenv("COMPOSIO_API_KEY")
        self.account_id = account_id or os.getenv("COMPOSIO_INSTANTLY_ACCOUNT_ID")
        
        if not self.api_key:
            raise ValueError("COMPOSIO_API_KEY not found in environment")
        
        self.client = Composio(api_key=self.api_key)
    
    def execute(self, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a Composio action with error handling"""
        try:
            response = self.client.tools.execute(
                action=action,
                connected_account_id=self.account_id,
                params=params
            )
            return response
        except Exception as e:
            print(f"❌ Error executing {action}: {str(e)}")
            raise
    
    # ===== Campaign Methods =====
    
    def list_campaigns(self) -> List[Dict[str, Any]]:
        """List all campaigns"""
        response = self.execute("INSTANTLY_LIST_CAMPAIGNS", {})
        return response.get('data', [])
    
    def get_campaign(self, campaign_id: str) -> Dict[str, Any]:
        """Get campaign details"""
        response = self.execute("INSTANTLY_GET_CAMPAIGN", {
            "campaign_id": campaign_id
        })
        return response.get('data', {})
    
    def create_campaign(
        self,
        name: str,
        from_email: str,
        reply_to_email: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create a new campaign"""
        params = {
            "name": name,
            "from_email": from_email
        }
        if reply_to_email:
            params['reply_to_email'] = reply_to_email
        
        response = self.execute("INSTANTLY_CREATE_CAMPAIGN", params)
        return response.get('data', {})
    
    def get_campaign_analytics(self, campaign_id: str) -> Dict[str, Any]:
        """Get campaign analytics (opens, clicks, replies)"""
        response = self.execute("INSTANTLY_GET_CAMPAIGN_ANALYTICS", {
            "campaign_id": campaign_id
        })
        return response.get('data', {})
    
    # ===== Lead Methods =====
    
    def create_lead(
        self,
        campaign_id: str,
        email: str,
        first_name: str = None,
        last_name: str = None,
        company_name: str = None,
        custom_variables: Dict[str, str] = None
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
        """
        params = {
            "campaign_id": campaign_id,
            "email": email
        }
        
        if first_name:
            params['first_name'] = first_name
        if last_name:
            params['last_name'] = last_name
        if company_name:
            params['company_name'] = company_name
        if custom_variables:
            params['custom_variables'] = custom_variables
        
        response = self.execute("INSTANTLY_CREATE_LEAD", params)
        return response.get('data', {})
    
    def list_leads(
        self,
        campaign_id: str = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """List leads (optionally filtered by campaign)"""
        params = {
            "skip": skip,
            "limit": limit
        }
        if campaign_id:
            params['campaign_id'] = campaign_id
        
        response = self.execute("INSTANTLY_LIST_LEADS", params)
        return response.get('data', [])
    
    def get_lead(self, email: str) -> Dict[str, Any]:
        """Get lead details by email"""
        response = self.execute("INSTANTLY_GET_LEAD", {
            "email": email
        })
        return response.get('data', {})
    
    def update_lead(
        self,
        email: str,
        variables: Dict[str, str]
    ) -> Dict[str, Any]:
        """Update lead custom variables"""
        response = self.execute("INSTANTLY_UPDATE_LEAD", {
            "email": email,
            "variables": variables
        })
        return response.get('data', {})
    
    def delete_lead(self, email: str) -> Dict[str, Any]:
        """Remove lead from campaign"""
        response = self.execute("INSTANTLY_DELETE_LEAD", {
            "email": email
        })
        return response.get('data', {})
    
    # ===== Batch Methods =====
    
    def create_leads_batch(
        self,
        campaign_id: str,
        leads: List[Dict[str, Any]],
        show_progress: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Add multiple leads to a campaign
        
        Args:
            campaign_id: Instantly campaign ID
            leads: List of lead dicts, each with:
                - email (required)
                - first_name, last_name, company_name (optional)
                - custom_variables (optional dict)
            show_progress: Print progress during batch creation
        
        Returns:
            List of results for each lead (success/failure)
        """
        results = []
        total = len(leads)
        
        for i, lead in enumerate(leads, 1):
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
                
                if show_progress and i % 10 == 0:
                    print(f"✓ {i}/{total} leads created...")
                    
            except Exception as e:
                results.append({
                    'email': lead['email'],
                    'success': False,
                    'error': str(e)
                })
                if show_progress:
                    print(f"✗ Failed: {lead['email']} - {str(e)}")
        
        if show_progress:
            success_count = sum(1 for r in results if r['success'])
            print(f"\n✅ Batch complete: {success_count}/{total} successful")
        
        return results
    
    # ===== Email Verification =====
    
    def verify_email(self, email: str) -> Dict[str, Any]:
        """Verify email deliverability"""
        response = self.execute("INSTANTLY_VERIFY_EMAIL", {
            "email": email
        })
        return response.get('data', {})
    
    # ===== Account Info =====
    
    def get_account_info(self) -> Dict[str, Any]:
        """Get account details and limits"""
        response = self.execute("INSTANTLY_GET_ACCOUNT", {})
        return response.get('data', {})
    
    # ===== Webhooks (for Phase 3) =====
    
    def list_webhooks(self) -> List[Dict[str, Any]]:
        """List configured webhooks"""
        response = self.execute("INSTANTLY_LIST_WEBHOOKS", {})
        return response.get('data', [])
    
    def create_webhook(
        self,
        url: str,
        events: List[str]
    ) -> Dict[str, Any]:
        """
        Create a webhook for events
        
        Args:
            url: Your webhook endpoint URL
            events: List of events to subscribe to
                ['email.opened', 'email.replied', 'email.bounced', etc.]
        """
        response = self.execute("INSTANTLY_CREATE_WEBHOOK", {
            "url": url,
            "events": events
        })
        return response.get('data', {})
    
    def delete_webhook(self, webhook_id: str) -> Dict[str, Any]:
        """Delete a webhook"""
        response = self.execute("INSTANTLY_DELETE_WEBHOOK", {
            "webhook_id": webhook_id
        })
        return response.get('data', {})


# Example usage
if __name__ == "__main__":
    import sys
    
    # Initialize client
    try:
        client = InstantlyComposioClient()
        print("✅ Client initialized successfully")
    except ValueError as e:
        print(f"❌ {e}")
        print("Please set COMPOSIO_API_KEY in .env file")
        sys.exit(1)
    
    # Test: List campaigns
    try:
        campaigns = client.list_campaigns()
        print(f"\n📊 Found {len(campaigns)} campaigns:")
        for camp in campaigns[:5]:
            print(f"  - {camp.get('name', 'Unnamed')} (ID: {camp.get('id', 'N/A')})")
    except Exception as e:
        print(f"❌ Failed to list campaigns: {e}")
