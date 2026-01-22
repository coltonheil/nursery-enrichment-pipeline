"""
Test script for Phase 5 rescoring endpoint.
Checks enriched leads and triggers rescoring.
"""

import requests
import json
from database.models import get_db_connection

# Check current state
print("=" * 80)
print("Phase 5: Re-Scoring Existing Leads")
print("=" * 80)
print()

conn = get_db_connection()
cursor = conn.cursor()

# Get counts
cursor.execute("SELECT COUNT(*) FROM leads WHERE gemini_status = 'enriched'")
enriched_count = cursor.fetchone()[0]

cursor.execute("SELECT COUNT(*) FROM leads")
total_count = cursor.fetchone()[0]

print(f"Total leads in database: {total_count}")
print(f"Enriched leads (ready for rescoring): {enriched_count}")
print()

if enriched_count == 0:
    print("No enriched leads found. Cannot test rescoring.")
    conn.close()
    exit(0)

# Get current tier distribution (before rescoring)
cursor.execute("""
    SELECT tier, COUNT(*) as count
    FROM leads
    WHERE tier IS NOT NULL
    GROUP BY tier
""")
current_tiers = cursor.fetchall()

print("Current Tier Distribution (Before Rescoring):")
tier_counts_before = {'A': 0, 'B': 0, 'C': 0, 'U': 0}
for row in current_tiers:
    tier = row['tier'] if row['tier'] else 'U'
    count = row['count']
    tier_counts_before[tier] = count
    print(f"  Tier {tier}: {count}")
print()

conn.close()

# Now trigger rescoring via API
print("Triggering rescoring via POST /rescore/all...")
print("(Note: This requires the Flask app to be running)")
print()

try:
    response = requests.post(
        'http://127.0.0.1:5000/rescore/all',
        json={'batch_size': enriched_count},  # Rescore all
        timeout=300  # 5 minutes timeout for large batches
    )

    if response.status_code == 200:
        result = response.json()
        print("✓ Rescoring completed successfully!")
        print()
        print(f"Total leads rescored: {result.get('total', 0)}")
        print()
        print("New Tier Distribution (After Rescoring):")
        for tier in ['A', 'B', 'C', 'U']:
            count = result['tier_distribution'].get(tier, 0)
            before = tier_counts_before.get(tier, 0)
            change = count - before
            change_str = f"(+{change})" if change > 0 else f"({change})" if change < 0 else "(no change)"
            print(f"  Tier {tier}: {count} {change_str}")
        print()
        print("ICP Distribution:")
        for icp_type, count in result.get('icp_distribution', {}).items():
            print(f"  {icp_type}: {count}")
    else:
        print(f"Error: HTTP {response.status_code}")
        print(response.text)

except requests.exceptions.ConnectionError:
    print("ERROR: Could not connect to Flask app at http://127.0.0.1:5000")
    print("Please ensure the Flask app is running:")
    print("  py app.py")
except Exception as e:
    print(f"ERROR: {str(e)}")
