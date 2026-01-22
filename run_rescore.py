"""
Direct rescoring script for Phase 5.
Rescores all enriched leads with new ICP-based model.
"""

import json
from database.models import get_db_connection
from enrichment.scorer import calculate_score

print("=" * 80)
print("Phase 5: Re-Scoring Enriched Leads with ICP Model")
print("=" * 80)
print()

conn = get_db_connection()
cursor = conn.cursor()

# Get all enriched leads
cursor.execute("""
    SELECT * FROM leads
    WHERE gemini_status = 'enriched'
    ORDER BY imported_at DESC
""")

leads = cursor.fetchall()

print(f"Found {len(leads)} enriched leads to rescore")
print()

results = {
    'total': len(leads),
    'rescored': 0,
    'tier_distribution': {'A': 0, 'B': 0, 'C': 0, 'U': 0},
    'icp_distribution': {
        'primary': 0,
        'secondary': 0,
        'tertiary': 0,
        'disqualified': 0
    },
    'geo_scores': {}
}

print("Rescoring leads...")
for i, lead in enumerate(leads, 1):
    # Convert to dict for scorer
    lead_dict = dict(lead)

    # Calculate score with new ICP-based model (includes geo scoring)
    score_result = calculate_score(lead_dict)

    # Update database
    cursor.execute('''
        UPDATE leads
        SET score = ?,
            tier = ?,
            icp_qualified = ?,
            icp_type = ?,
            geo_score = ?,
            score_breakdown = ?,
            rescored_at = CURRENT_TIMESTAMP
        WHERE id = ?
    ''', (
        score_result['total'],
        score_result['tier'],
        score_result.get('icp_qualified'),
        score_result.get('icp_type'),
        score_result.get('geo_score', 0),
        json.dumps({
            'total': score_result['total'],
            'signals': score_result['signals'],
            'tier': score_result['tier'],
            'has_data': score_result['has_data']
        }),
        lead['id']
    ))

    results['rescored'] += 1
    results['tier_distribution'][score_result['tier']] += 1
    icp_type = score_result.get('icp_type', 'disqualified')
    results['icp_distribution'][icp_type] += 1

    # Track geo scores
    geo = score_result.get('geo_score', 0)
    results['geo_scores'][geo] = results['geo_scores'].get(geo, 0) + 1

    # Show progress every 10 leads
    if i % 10 == 0:
        print(f"  Processed {i}/{len(leads)} leads...")

conn.commit()
conn.close()

print()
print("=" * 80)
print("RESCORING COMPLETE")
print("=" * 80)
print()
print(f"Total leads rescored: {results['rescored']}")
print()
print("NEW Tier Distribution (After ICP-Based Rescoring):")
for tier in ['A', 'B', 'C', 'U']:
    count = results['tier_distribution'][tier]
    pct = (count / results['total'] * 100) if results['total'] > 0 else 0
    print(f"  Tier {tier}: {count:3d} ({pct:5.1f}%)")
print()

print("ICP Distribution:")
for icp_type, count in sorted(results['icp_distribution'].items()):
    pct = (count / results['total'] * 100) if results['total'] > 0 else 0
    print(f"  {icp_type:15s}: {count:3d} ({pct:5.1f}%)")
print()

print("Geographic Scores:")
for geo_score in sorted(results['geo_scores'].keys(), reverse=True):
    count = results['geo_scores'][geo_score]
    print(f"  {geo_score:+3d} points: {count:3d} leads")
print()

print("Phase 5 rescoring completed successfully!")
