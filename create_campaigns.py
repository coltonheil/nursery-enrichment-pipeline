#!/usr/bin/env python3
"""
Create Instantly campaigns via Composio
"""
import os
from pathlib import Path
from instantly_composio_client import InstantlyComposioClient

# Load .env
env_file = Path(__file__).parent / '.env'
if env_file.exists():
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                os.environ[key] = value

# Initialize client
client = InstantlyComposioClient()

print("=" * 60)
print("Creating Instantly Campaigns")
print("=" * 60)
print()

# Campaign 1: Premium Nurseries (Tier A)
print("Creating Campaign 1: Premium Nurseries (Tier A)...")
try:
    campaign_a = client._execute_action('INSTANTLY_CREATE_CAMPAIGN', {
        'name': 'Premium Nurseries - Worm Casting Samples (Tier A)',
        'campaign_schedule': {
            'days': ['mon', 'tue', 'wed', 'thu', 'fri'],  # Weekdays only
            'start_hour': '09:00',
            'end_hour': '17:00',
            'timezone': 'America/Chicago',
            'min_time_btw_emails': 60,  # 1 hour between emails
            'max_new_leads_per_day': 0  # Paused - don't send yet
        },
        'stop_on_reply': True,  # Stop when they reply
        'open_tracking': True,
        'link_tracking': True
    })
    print(f"✅ Created: {campaign_a.get('name', 'Premium Nurseries')}")
    print(f"   ID: {campaign_a.get('id', 'N/A')}")
    print(f"   Status: PAUSED (max_new_leads_per_day = 0)")
    print()
except Exception as e:
    print(f"❌ Error: {str(e)}")
    print()

# Campaign 2: Standard Nurseries (Tier B)
print("Creating Campaign 2: Standard Nurseries (Tier B)...")
try:
    campaign_b = client._execute_action('INSTANTLY_CREATE_CAMPAIGN', {
        'name': 'Standard Nurseries - Worm Casting Samples (Tier B)',
        'campaign_schedule': {
            'days': ['mon', 'tue', 'wed', 'thu', 'fri'],  # Weekdays only
            'start_hour': '09:00',
            'end_hour': '17:00',
            'timezone': 'America/Chicago',
            'min_time_btw_emails': 60,  # 1 hour between emails
            'max_new_leads_per_day': 0  # Paused - don't send yet
        },
        'stop_on_reply': True,  # Stop when they reply
        'open_tracking': True,
        'link_tracking': True
    })
    print(f"✅ Created: {campaign_b.get('name', 'Standard Nurseries')}")
    print(f"   ID: {campaign_b.get('id', 'N/A')}")
    print(f"   Status: PAUSED (max_new_leads_per_day = 0)")
    print()
except Exception as e:
    print(f"❌ Error: {str(e)}")
    print()

# List all campaigns to verify
print("=" * 60)
print("Verifying campaigns...")
campaigns = client.list_campaigns()
print(f"✅ Total campaigns: {len(campaigns)}")
print()

for i, campaign in enumerate(campaigns, 1):
    print(f"{i}. {campaign.get('name', 'Unnamed')}")
    print(f"   ID: {campaign.get('id', 'N/A')}")
    print(f"   Status: {campaign.get('status', 'unknown')}")
    print()

print("=" * 60)
print("✅ Campaigns created and ready!")
print("=" * 60)
print()
print("Next: Add campaign IDs to .env file for Phase 1")
