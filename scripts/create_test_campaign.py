#!/usr/bin/env python3
"""
Create a test campaign in Instantly.ai
For validation before Phase 1 implementation
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


def create_test_campaign():
    """Create a test campaign to validate setup"""
    
    print("🧪 Creating test campaign in Instantly.ai...\n")
    
    # Initialize client
    try:
        client = InstantlyComposioClient()
    except Exception as e:
        print(f"❌ Failed to initialize client: {e}")
        print("Run: python scripts/connect_instantly.py")
        return False
    
    # Campaign details
    campaign_name = "TEST - Nursery Pipeline Setup"
    from_email = input("\nEnter your sending email address: ").strip()
    
    if not from_email:
        print("❌ Email address required")
        return False
    
    # Create campaign
    try:
        print(f"\n⏳ Creating campaign: {campaign_name}")
        print(f"   From: {from_email}\n")
        
        campaign = client.create_campaign(
            name=campaign_name,
            from_email=from_email,
            reply_to_email=from_email
        )
        
        campaign_id = campaign.get('id')
        print(f"✅ Campaign created!")
        print(f"   ID: {campaign_id}")
        print(f"   Name: {campaign.get('name')}")
        print(f"   Status: {campaign.get('status')}")
        
        # Add a test lead
        print("\n⏳ Adding test lead...")
        test_lead = client.create_lead(
            campaign_id=campaign_id,
            email="test@example.com",
            first_name="Test",
            last_name="Lead",
            company_name="Test Nursery",
            custom_variables={
                'tier': 'A',
                'city': 'Madison',
                'state': 'WI',
                'business_type': 'Garden Center'
            }
        )
        
        print(f"✅ Test lead added!")
        print(f"   Email: {test_lead.get('email')}")
        print(f"   Status: {test_lead.get('status')}")
        
        print("\n✅ Test campaign setup COMPLETE!")
        print(f"\n🎯 Campaign ID for Phase 1: {campaign_id}")
        print("   (You can delete this test campaign after validation)")
        
        return True
        
    except Exception as e:
        print(f"❌ Failed to create campaign: {e}")
        print("\nNote: Check that:")
        print("  - Your email is verified in Instantly.ai")
        print("  - You have campaign creation permissions")
        return False


if __name__ == "__main__":
    success = create_test_campaign()
    sys.exit(0 if success else 1)
