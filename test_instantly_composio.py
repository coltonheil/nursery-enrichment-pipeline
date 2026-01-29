#!/usr/bin/env python3
"""
Test Instantly connection via Composio
"""
import os
import sys
from pathlib import Path

print("=" * 60)
print("Testing Instantly.ai Connection via Composio")
print("=" * 60)
print()

# Load .env file if it exists
env_file = Path(__file__).parent / '.env'
if env_file.exists():
    print(f"✓ Loading environment from: {env_file}")
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                os.environ[key] = value
    print()

# Check for required environment variables
composio_api_key = os.getenv("COMPOSIO_API_KEY")
instantly_account_id = os.getenv("COMPOSIO_INSTANTLY_ACCOUNT_ID")

if not composio_api_key:
    print("❌ ERROR: COMPOSIO_API_KEY not found in environment")
    print()
    print("To fix:")
    print("1. Get your API key from: https://app.composio.dev/settings")
    print("2. Add to .env file:")
    print("   echo 'COMPOSIO_API_KEY=your_key_here' >> .env")
    print()
    sys.exit(1)

if not instantly_account_id:
    print("❌ ERROR: COMPOSIO_INSTANTLY_ACCOUNT_ID not found in environment")
    print()
    print("To fix:")
    print("1. Go to: https://app.composio.dev")
    print("2. Navigate to: Integrations → Instantly")
    print("3. If not connected, click 'Connect Account'")
    print("4. Copy the Connected Account ID (starts with 'conn_')")
    print("5. Add to .env file:")
    print("   echo 'COMPOSIO_INSTANTLY_ACCOUNT_ID=conn_...' >> .env")
    print()
    sys.exit(1)

# Try to import composio
try:
    from composio import Composio
except ImportError:
    print("❌ ERROR: composio-core package not installed")
    print()
    print("To fix:")
    print("  pip install composio-core")
    print()
    sys.exit(1)

# Initialize Composio client
print("✓ Environment variables found")
print(f"  - API Key: {composio_api_key[:10]}..." if len(composio_api_key) > 10 else composio_api_key)
print(f"  - Account ID: {instantly_account_id}")
print()

try:
    print("Initializing Composio client...")
    client = Composio(api_key=composio_api_key)
    print("✓ Client initialized")
    print()
    
    print("Testing connection: Listing campaigns...")
    # Get the action
    action = client.actions.get("INSTANTLY_LIST_CAMPAIGNS")
    print(f"✓ Action loaded: {action.name}")
    print()
    
    # Execute the action
    response = client.actions.execute(
        action=action,
        params={},
        connected_account=instantly_account_id
    )
    
    print()
    print("=" * 60)
    print("✅ CONNECTION SUCCESSFUL!")
    print("=" * 60)
    print()
    
    # Parse response
    if isinstance(response, dict):
        campaigns = response.get('data', [])
        if not campaigns:
            campaigns = response.get('campaigns', [])
    else:
        campaigns = []
    
    print(f"Found {len(campaigns)} Instantly campaigns:")
    print()
    
    if campaigns:
        for i, campaign in enumerate(campaigns[:5], 1):  # Show first 5
            name = campaign.get('name', 'Unnamed Campaign')
            campaign_id = campaign.get('id', 'N/A')
            status = campaign.get('status', 'unknown')
            print(f"  {i}. {name}")
            print(f"     ID: {campaign_id}")
            print(f"     Status: {status}")
            print()
        
        if len(campaigns) > 5:
            print(f"  ... and {len(campaigns) - 5} more campaigns")
            print()
    else:
        print("  (No campaigns found - you may need to create one in Instantly)")
        print()
    
    print("=" * 60)
    print("✅ Ready for Phase 1 implementation!")
    print("=" * 60)
    print()
    print("Next steps:")
    print("1. Tell Clawdbot: 'Ready for Phase 1 planning'")
    print("2. Opus will design the implementation")
    print("3. Sonnet will build it")
    print()
    
except Exception as e:
    print()
    print("=" * 60)
    print("❌ CONNECTION FAILED")
    print("=" * 60)
    print()
    print(f"Error: {str(e)}")
    print()
    print("Troubleshooting:")
    print("1. Verify your Composio API key is correct")
    print("2. Verify Instantly is connected in Composio dashboard")
    print("3. Verify the Connected Account ID is correct")
    print("4. Check if your Instantly API key is valid")
    print()
    sys.exit(1)
