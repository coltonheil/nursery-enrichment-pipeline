# Composio + Instantly.ai OAuth Setup Guide
**Goal:** Seamless authentication for Instantly integration using Composio

---

## 🎯 Why Composio?

Instead of managing raw API keys and building OAuth flows ourselves, Composio provides:

✅ **OAuth 2.0 flow** - Secure token management  
✅ **47 pre-built actions** - No need to write API client code  
✅ **Automatic token refresh** - Never worry about expired tokens  
✅ **Webhook support** - Bi-directional sync built-in  
✅ **Unified API** - Same pattern for 800+ tools  

---

## 📋 Prerequisites

1. **Composio Account** - [composio.dev](https://composio.dev)
2. **Instantly.ai Account** with API access
3. **Composio API Key** (from Composio dashboard)

---

## 🔧 Step 1: Set Up Composio

### Install Composio SDK (if not already installed)
```bash
cd ~/clawd/projects/nursery-enrichment-pipeline
source venv/bin/activate
pip install composio-core
```

### Add Composio API Key to Environment
```bash
# Add to .env file
echo "COMPOSIO_API_KEY=your_composio_api_key_here" >> .env
```

---

## 🔑 Step 2: Connect Instantly.ai via Composio

### Option A: Via Composio Dashboard (Easiest)

1. **Go to:** https://app.composio.dev
2. **Navigate to:** Integrations → Search "Instantly"
3. **Click:** "Connect Account"
4. **Enter:** Your Instantly.ai API key
5. **Copy:** The "Connected Account ID" (e.g., `conn_abc123...`)

### Option B: Via Python Script

```python
# scripts/connect_instantly.py
from composio import Composio

client = Composio(api_key="your_composio_api_key")

# Create connection
connection = client.connections.create(
    integration_id="instantly",
    auth_config={
        "api_key": "your_instantly_api_key"
    }
)

print(f"Connected! Account ID: {connection.id}")
# Save this ID for later use
```

### Where to Find Instantly API Key

1. Log into Instantly.ai
2. Go to Settings → API
3. Generate API key (if you don't have one)
4. Copy the key

---

## 📝 Step 3: Store Connected Account ID

```bash
# Add to .env
echo "COMPOSIO_INSTANTLY_ACCOUNT_ID=conn_abc123..." >> .env
```

---

## 🧪 Step 4: Test the Connection

Create a test script to verify everything works:

```python
# scripts/test_instantly_connection.py
import os
from composio import Composio

# Initialize
client = Composio(api_key=os.getenv("COMPOSIO_API_KEY"))
account_id = os.getenv("COMPOSIO_INSTANTLY_ACCOUNT_ID")

# Test: List campaigns
response = client.tools.execute(
    action="INSTANTLY_LIST_CAMPAIGNS",
    connected_account_id=account_id,
    params={}
)

print("✅ Connection successful!")
print(f"Found {len(response['data'])} campaigns:")
for campaign in response['data'][:3]:  # Show first 3
    print(f"  - {campaign['name']} (ID: {campaign['id']})")
```

Run it:
```bash
python scripts/test_instantly_connection.py
```

Expected output:
```
✅ Connection successful!
Found 2 campaigns:
  - Premium Nurseries (ID: camp_abc123)
  - Standard Nurseries (ID: camp_def456)
```

---

## 🔧 Step 5: Create Composio Instantly Client Wrapper

Create a clean wrapper for our use:

```python
# instantly_composio_client.py
import os
from composio import Composio
from typing import List, Dict, Any

class InstantlyComposioClient:
    """
    Wrapper around Composio's Instantly.ai integration
    Provides simplified methods for our use case
    """
    
    def __init__(self, api_key: str = None, account_id: str = None):
        self.api_key = api_key or os.getenv("COMPOSIO_API_KEY")
        self.account_id = account_id or os.getenv("COMPOSIO_INSTANTLY_ACCOUNT_ID")
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
    
    # ===== Batch Methods =====
    
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
    
    # ===== Email Verification =====
    
    def verify_email(self, email: str) -> Dict[str, Any]:
        """Verify email deliverability"""
        response = self.execute("INSTANTLY_VERIFY_EMAIL", {
            "email": email
        })
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


# Example usage:
if __name__ == "__main__":
    # Initialize client
    client = InstantlyComposioClient()
    
    # List campaigns
    campaigns = client.list_campaigns()
    print(f"Found {len(campaigns)} campaigns")
    
    # Add a test lead
    result = client.create_lead(
        campaign_id="camp_abc123",
        email="test@nursery.com",
        first_name="John",
        company_name="ABC Nursery",
        custom_variables={
            'tier': 'A',
            'city': 'Austin',
            'business_type': 'Garden Center'
        }
    )
    print(f"✅ Lead created: {result}")
```

---

## 🎯 Step 6: Integration with Flask App

Update your Flask app to use Composio:

```python
# In app.py
from instantly_composio_client import InstantlyComposioClient

# Initialize at app startup
instantly_client = InstantlyComposioClient()

@app.route('/api/instantly/send', methods=['POST'])
def send_to_instantly():
    """Send leads to Instantly via Composio"""
    data = request.json
    lead_ids = data.get('lead_ids', [])
    campaign_id = data.get('campaign_id')
    
    # Get leads from database
    leads = get_leads_by_ids(lead_ids)
    
    # Format for Instantly
    instantly_leads = []
    for lead in leads:
        instantly_leads.append({
            'email': lead['contact_email'] or lead['owner_email'],
            'first_name': lead['contact_name'].split()[0] if lead['contact_name'] else '',
            'last_name': lead['contact_name'].split()[1] if len(lead['contact_name'].split()) > 1 else '',
            'company_name': lead['business_name'],
            'custom_variables': {
                'tier': lead['tier'],
                'city': lead['city'],
                'state': lead['state'],
                'business_type': lead.get('business_type', ''),
                'website': lead['website'],
                'phone': lead['phone']
            }
        })
    
    # Send via Composio
    results = instantly_client.create_leads_batch(
        campaign_id=campaign_id,
        leads=instantly_leads
    )
    
    # Log to database
    for i, result in enumerate(results):
        log_instantly_sync(
            lead_id=lead_ids[i],
            campaign_id=campaign_id,
            status='sent' if result['success'] else 'failed',
            error_message=result.get('error')
        )
    
    return jsonify({
        'success': True,
        'sent': sum(1 for r in results if r['success']),
        'failed': sum(1 for r in results if not r['success']),
        'results': results
    })
```

---

## ✅ Verification Checklist

Before moving to Phase 1 implementation:

- [ ] Composio SDK installed
- [ ] Composio API key added to `.env`
- [ ] Instantly.ai connected via Composio dashboard
- [ ] Connected Account ID saved to `.env`
- [ ] Test script runs successfully and lists campaigns
- [ ] `InstantlyComposioClient` class created
- [ ] Can create a test lead via Composio

---

## 🎯 Next Steps

Once setup is complete:

1. **Phase 1 Planning** - Use Opus to design best-in-class implementation
2. **Phase 1 Build** - Use Sonnet to implement with Composio
3. **Checkpoint** - Test with 5-10 real leads
4. **Phase 2 Planning** - Opus designs staging area
5. **Phase 2 Build** - Sonnet implements
6. **Checkpoint** - Test review workflow
7. **Phase 3 Planning** - Opus designs bi-directional sync
8. **Phase 3 Build** - Sonnet implements webhooks

---

## 📚 Composio Resources

- [Instantly Toolkit Docs](https://docs.composio.dev/toolkits/instantly)
- [Composio Python SDK](https://docs.composio.dev/docs/providers/openai)
- [All Available Actions](https://docs.composio.dev/toolkits/instantly#tools-47)

---

## 🔒 Security Notes

- **Never commit API keys** - Use `.env` files (already in `.gitignore`)
- **Composio handles OAuth** - No need to manage refresh tokens
- **Tokens are encrypted** - Stored securely on Composio servers
- **Revoke access** - Can disconnect from Composio dashboard anytime

---

Ready to proceed! 🚀
