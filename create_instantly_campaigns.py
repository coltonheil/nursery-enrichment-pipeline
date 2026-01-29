#!/usr/bin/env python3
"""
Create Instantly.ai Campaigns via API V2
Creates two campaigns for worm casting sample outreach
"""
import os
import sys
import requests
import json
from pathlib import Path

# Load environment
env_file = Path(__file__).parent / '.env'
if env_file.exists():
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                os.environ[key] = value

# Get Instantly API key
INSTANTLY_API_KEY = os.getenv('INSTANTLY_API_KEY')
if not INSTANTLY_API_KEY:
    print("❌ INSTANTLY_API_KEY not found in .env")
    print("Please add your Instantly.ai API key (not Composio key)")
    print("Get it from: https://app.instantly.ai/app/settings/integrations")
    sys.exit(1)

BASE_URL = "https://api.instantly.ai/api/v2/campaigns"
HEADERS = {
    "Authorization": f"Bearer {INSTANTLY_API_KEY}",
    "Content-Type": "application/json"
}

print("=" * 70)
print("Creating Instantly.ai Campaigns - Worm Casting Sample Outreach")
print("=" * 70)
print()

# Campaign configuration
CAMPAIGNS = [
    {
        "name": "Premium Nurseries - Worm Casting Samples (Tier A)",
        "tier": "A",
        "description": "Top-tier qualified nurseries - premium sample outreach"
    },
    {
        "name": "Standard Nurseries - Worm Casting Samples (Tier B)",
        "tier": "B",
        "description": "Quality nurseries - standard sample outreach"
    }
]

# Email sequence for sample request
EMAIL_SEQUENCES = {
    "steps": [
        {
            "step_number": 1,
            "type": "email",
            "delay": 0,
            "variants": [
                {
                    "subject": "Free Worm Casting Sample for {{company_name}}?",
                    "body": """Hi {{first_name}},

I noticed {{company_name}} in {{city}}, {{state}} and thought you might be interested in trying our premium worm castings.

We're offering free samples to select nurseries in your area. The worm castings are 100% organic and have shown excellent results for plant health and growth.

Would you be interested in receiving a free sample to test with your plants?

If yes, just reply with your mailing address and I'll get a sample package out to you this week. No purchase necessary - we're simply looking for feedback from quality nurseries like yours.

Best regards,
[Your Name]
[Your Company]"""
                }
            ]
        },
        {
            "step_number": 2,
            "type": "email",
            "delay": 3,
            "variants": [
                {
                    "subject": "Re: Free worm casting sample for {{company_name}}",
                    "body": """Hi {{first_name}},

Just wanted to follow up on my message from a few days ago about the free worm casting sample.

I know you're busy running {{company_name}}, but I didn't want you to miss out on this opportunity to try a product that's been getting great results for nurseries in {{state}}.

If you'd like a sample, just reply with your mailing address and I'll have it sent out immediately.

Thanks for your time!

[Your Name]"""
                }
            ]
        }
    ]
}

def create_campaign(campaign_config):
    """Create a single campaign via Instantly API V2"""
    
    payload = {
        "name": campaign_config["name"],
        "campaign_schedule": {
            "schedules": [
                {
                    "name": "Weekday Business Hours",
                    "timing": {
                        "from": "09:00",
                        "to": "17:00"
                    },
                    "days": {
                        "0": False,  # Sunday
                        "1": True,   # Monday
                        "2": True,   # Tuesday
                        "3": True,   # Wednesday
                        "4": True,   # Thursday
                        "5": True,   # Friday
                        "6": False   # Saturday
                    },
                    "timezone": "America/Chicago"
                }
            ]
        },
        # Campaign behavior
        "daily_max_leads": 0,              # PAUSED - don't send yet (warmup)
        "stop_on_reply": True,             # Stop when they reply
        "stop_on_auto_reply": True,        # Stop on out-of-office
        "stop_for_company": False,         # Don't stop entire domain
        
        # Tracking
        "open_tracking": True,             # Track opens
        "link_tracking": True,             # Track clicks
        
        # Sending behavior
        "email_gap": 60,                   # 1 hour between emails
        "random_wait_max": 120,            # Up to 2 hours random delay
        "first_email_text_only": True,     # First email plain text (more personal)
        "prioritize_new_leads": True,      # New leads first
        
        # Compliance
        "insert_unsubscribe_header": True, # Add unsubscribe
        "allow_risky_contacts": False,     # Don't send to risky emails
        "disable_bounce_protect": False,   # Keep bounce protection
        
        # Email sequence
        "sequences": [EMAIL_SEQUENCES]
    }
    
    print(f"Creating: {campaign_config['name']}")
    print(f"  Description: {campaign_config['description']}")
    print(f"  Tier: {campaign_config['tier']}")
    print()
    
    try:
        response = requests.post(
            BASE_URL,
            headers=HEADERS,
            json=payload,
            timeout=30
        )
        
        if response.status_code in [200, 201]:
            result = response.json()
            campaign_id = result.get('id')
            status_code = result.get('status', 0)
            
            # Status mapping
            status_map = {
                0: 'Draft',
                1: 'Active',
                2: 'Paused',
                3: 'Completed'
            }
            status_name = status_map.get(status_code, f'Unknown ({status_code})')
            
            print("✅ Campaign Created Successfully!")
            print(f"   ID: {campaign_id}")
            print(f"   Status: {status_name}")
            print(f"   Daily Max Leads: 0 (PAUSED - warming up)")
            print(f"   Created: {result.get('timestamp_created')}")
            print()
            
            return {
                'success': True,
                'id': campaign_id,
                'name': campaign_config['name'],
                'tier': campaign_config['tier']
            }
            
        else:
            print(f"❌ Error: HTTP {response.status_code}")
            print(f"   Response: {response.text[:500]}")
            print()
            return {
                'success': False,
                'error': response.text,
                'name': campaign_config['name']
            }
            
    except Exception as e:
        print(f"❌ Exception: {str(e)}")
        print()
        return {
            'success': False,
            'error': str(e),
            'name': campaign_config['name']
        }

# Create both campaigns
results = []
for campaign_config in CAMPAIGNS:
    result = create_campaign(campaign_config)
    results.append(result)
    print("-" * 70)
    print()

# Summary
print("=" * 70)
print("SUMMARY")
print("=" * 70)
print()

successful = [r for r in results if r['success']]
failed = [r for r in results if not r['success']]

if successful:
    print(f"✅ {len(successful)} campaign(s) created successfully:")
    print()
    for r in successful:
        print(f"  • {r['name']}")
        print(f"    ID: {r['id']}")
        print(f"    Tier: {r['tier']}")
        print()

if failed:
    print(f"❌ {len(failed)} campaign(s) failed:")
    print()
    for r in failed:
        print(f"  • {r['name']}")
        print(f"    Error: {r['error'][:200]}")
        print()

# Save campaign IDs to .env if successful
if successful:
    print("=" * 70)
    print("NEXT STEPS")
    print("=" * 70)
    print()
    print("Campaign IDs to add to .env file:")
    print()
    
    tier_a = next((r for r in successful if r['tier'] == 'A'), None)
    tier_b = next((r for r in successful if r['tier'] == 'B'), None)
    
    if tier_a:
        print(f"INSTANTLY_CAMPAIGN_TIER_A={tier_a['id']}")
    if tier_b:
        print(f"INSTANTLY_CAMPAIGN_TIER_B={tier_b['id']}")
    
    print()
    print("To activate campaigns (after warmup complete):")
    print("1. Log into Instantly.ai")
    print("2. Go to each campaign")
    print("3. Set 'Daily Max Leads' to desired number (e.g., 50)")
    print("4. Campaign will start sending automatically")
    print()
    
    # Optionally auto-append to .env
    append = input("Append these to .env file now? (y/n): ").lower().strip()
    if append == 'y':
        with open(env_file, 'a') as f:
            f.write("\n# Instantly Campaign IDs\n")
            if tier_a:
                f.write(f"INSTANTLY_CAMPAIGN_TIER_A={tier_a['id']}\n")
            if tier_b:
                f.write(f"INSTANTLY_CAMPAIGN_TIER_B={tier_b['id']}\n")
        print("✅ Added to .env file!")
    
print()
print("=" * 70)
if successful:
    print("✅ CAMPAIGN SETUP COMPLETE!")
else:
    print("❌ CAMPAIGN SETUP FAILED")
print("=" * 70)
