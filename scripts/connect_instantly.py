#!/usr/bin/env python3
"""
Connect Instantly.ai to Composio
Establishes OAuth connection and saves account ID
"""

import os
import sys
from dotenv import load_dotenv

# Load environment
load_dotenv()

try:
    from composio import Composio
except ImportError:
    print("❌ Composio SDK not installed")
    print("Run: pip install composio-core")
    sys.exit(1)


def connect_instantly():
    """Connect Instantly.ai via Composio"""
    
    # Get API keys
    composio_key = os.getenv("COMPOSIO_API_KEY")
    instantly_key = os.getenv("INSTANTLY_API_KEY")
    
    if not composio_key:
        print("❌ COMPOSIO_API_KEY not found in .env")
        print("Get yours from: https://app.composio.dev/settings")
        return False
    
    if not instantly_key:
        print("❌ INSTANTLY_API_KEY not found in .env")
        print("Get yours from: Instantly.ai → Settings → API")
        return False
    
    print("🔌 Connecting Instantly.ai to Composio...")
    print(f"   Composio API Key: {composio_key[:10]}...")
    print(f"   Instantly API Key: {instantly_key[:10]}...")
    
    try:
        # Initialize Composio client
        client = Composio(api_key=composio_key)
        
        # Create connection
        print("\n⏳ Creating connection...")
        connection = client.connections.create(
            integration_id="instantly",
            auth_config={
                "api_key": instantly_key
            }
        )
        
        account_id = connection.id
        print(f"\n✅ Connected successfully!")
        print(f"   Account ID: {account_id}")
        
        # Save to .env
        env_path = ".env"
        with open(env_path, 'r') as f:
            lines = f.readlines()
        
        # Check if COMPOSIO_INSTANTLY_ACCOUNT_ID already exists
        found = False
        for i, line in enumerate(lines):
            if line.startswith("COMPOSIO_INSTANTLY_ACCOUNT_ID="):
                lines[i] = f"COMPOSIO_INSTANTLY_ACCOUNT_ID={account_id}\n"
                found = True
                break
        
        if not found:
            lines.append(f"\n# Composio Connected Account\nCOMPOSIO_INSTANTLY_ACCOUNT_ID={account_id}\n")
        
        with open(env_path, 'w') as f:
            f.writelines(lines)
        
        print(f"\n💾 Saved account ID to {env_path}")
        print("\n🎯 Next steps:")
        print("   1. Run: python scripts/test_instantly_connection.py")
        print("   2. Verify campaigns are listed")
        print("   3. Ready for Phase 1 implementation!")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Connection failed: {e}")
        print("\nTroubleshooting:")
        print("  - Check that your Composio API key is valid")
        print("  - Check that your Instantly API key has correct permissions")
        print("  - Visit: https://app.composio.dev/apps/instantly")
        return False


if __name__ == "__main__":
    success = connect_instantly()
    sys.exit(0 if success else 1)
