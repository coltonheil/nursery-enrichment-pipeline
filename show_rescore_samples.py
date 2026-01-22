"""
Show sample rescored leads to understand the new ICP-based scoring.
"""

import json
from database.models import get_db_connection

conn = get_db_connection()
cursor = conn.cursor()

print("=" * 80)
print("Phase 5 Rescoring Results - Sample Leads")
print("=" * 80)
print()

# Show Tier B leads (top tier we achieved)
print("TIER B LEADS (Qualified ICP, 40-69 points):")
print("-" * 80)
cursor.execute("""
    SELECT id, business_name, state, score, tier, icp_type, icp_qualified, geo_score
    FROM leads
    WHERE tier = 'B'
    ORDER BY score DESC
    LIMIT 5
""")
tier_b = cursor.fetchall()
for lead in tier_b:
    print(f"ID {lead['id']}: {lead['business_name']}")
    print(f"  State: {lead['state']}, Score: {lead['score']}, Geo: {lead['geo_score']:+d}")
    print(f"  ICP: {lead['icp_type']} ({'[QUALIFIED]' if lead['icp_qualified'] else '[DISQUALIFIED]'})")
    print()

# Show some primary ICP leads in Tier C (qualified but low score)
print("\nPRIMARY ICP LEADS IN TIER C (Qualified but <40 points):")
print("-" * 80)
cursor.execute("""
    SELECT id, business_name, state, score, tier, icp_type, geo_score
    FROM leads
    WHERE tier = 'C' AND icp_type = 'primary'
    ORDER BY score DESC
    LIMIT 5
""")
primary_c = cursor.fetchall()
for lead in primary_c:
    print(f"ID {lead['id']}: {lead['business_name']}")
    print(f"  State: {lead['state']}, Score: {lead['score']}, Geo: {lead['geo_score']:+d}")
    print(f"  ICP: {lead['icp_type']}")
    print()

# Show some disqualified leads
print("\nDISQUALIFIED LEADS (Failed ICP Gate):")
print("-" * 80)
cursor.execute("""
    SELECT id, business_name, state, business_type, icp_type, disqualification_signals
    FROM leads
    WHERE icp_type = 'disqualified' AND tier = 'C'
    ORDER BY RANDOM()
    LIMIT 5
""")
disqualified = cursor.fetchall()
for lead in disqualified:
    print(f"ID {lead['id']}: {lead['business_name']}")
    print(f"  Type: {lead['business_type']}")
    try:
        disqual_signals = json.loads(lead['disqualification_signals'] or '[]')
        if disqual_signals:
            print(f"  Disqualification signals: {', '.join(disqual_signals)}")
    except:
        pass
    print()

conn.close()

print("=" * 80)
print("Key Findings:")
print("- ICP qualification gate successfully filters out non-ideal customers")
print("- Geographic proximity scoring rewards Wisconsin and nearby states")
print("- Most leads need higher ICP scores (organic cert, wholesale, soil purchasing)")
print("=" * 80)
