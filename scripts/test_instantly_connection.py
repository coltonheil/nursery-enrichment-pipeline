#!/usr/bin/env python3
"""
Test Composio + Instantly.ai connection
Verifies OAuth setup and lists campaigns
"""

import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
from instantly_composio_client import InstantlyComposioClient

# Load environment
load_dotenv()


def test_connection():
    """Test Composio connection to Instantly"""
    
    print("🧪 Testing Composio + Instantly.ai connection...\n")
    
    # Check environment variables
    composio_key = os.getenv("COMPOSIO_API_KEY")
    account_id = os.getenv("COMPOSIO_INSTANTLY_ACCOUNT_ID")
    
    if not composio_key:
        print("❌ COMPOSIO_API_KEY not found in .env")
        print("Run: python scripts/connect_instantly.py")
        return False
    
    if not account_id:
        print("❌ COMPOSIO_INSTANTLY_ACCOUNT_ID not found in .env")
        print("Run: python scripts/connect_instantly.py")
        return False
    
    print(f"✓ Composio API Key: {composio_key[:10]}...")
    print(f"✓ Account ID: {account_id[:20]}...\n")
    
    # Initialize client
    try:
        print("⏳ Initializing Composio client...")
        client = InstantlyComposioClient()
        print("✅ Client initialized\n")
    except Exception as e:
        print(f"❌ Failed to initialize: {e}")
        return False
    
    # Test: Get account info
    try:
        print("⏳ Fetching account info...")
        account = client.get_account_info()
        print(f"✅ Account: {account.get('email', 'N/A')}")
        print(f"   Plan: {account.get('plan', 'N/A')}")
        print()
    except Exception as e:
        print(f"⚠️  Could not fetch account info: {e}\n")
    
    # Test: List campaigns
    try:
        print("⏳ Listing campaigns...")
        campaigns = client.list_campaigns()
        print(f"✅ Found {len(campaigns)} campaigns:\n")
        
        if len(campaigns) == 0:
            print("   (No campaigns yet - you'll create one in Phase 1)")
        else:
            for i, camp in enumerate(campaigns[:5], 1):
                name = camp.get('name', 'Unnamed')
                camp_id = camp.get('id', 'N/A')
                status = camp.get('status', 'unknown')
                print(f"   {i}. {name}")
                print(f"      ID: {camp_id}")
                print(f"      Status: {status}")
                print()
        
        print("✅ Connection test PASSED!")
        print("\n🎯 Ready for Phase 1 implementation!")
        return True
        
    except Exception as e:
        print(f"❌ Failed to list campaigns: {e}")
        print("\nTroubleshooting:")
        print("  - Check your Instantly API key has correct permissions")
        print("  - Verify connection at: https://app.composio.dev/apps/instantly")
        return False


if __name__ == "__main__":
    success = test_connection()
    sys.exit(0 if success else 1)
