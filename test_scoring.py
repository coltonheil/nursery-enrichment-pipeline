"""
Test script for Phase 5: Scoring Engine
Tests scoring all leads and displays tier distribution
"""

from database.models import get_leads_for_scoring, update_lead_score, log_action, get_tier_distribution
from enrichment.scorer import calculate_score
import json

def test_scoring_engine():
    """Test the scoring engine on all leads."""

    print("Testing Scoring Engine - Scoring All Leads")
    print("=" * 80)
    print()

    # Get all leads
    all_leads = get_leads_for_scoring()

    if not all_leads:
        print("[ERROR] No leads found in database")
        return False

    print(f"Found {len(all_leads)} leads to score")
    print()

    results = {
        'total': len(all_leads),
        'scored': 0,
        'tier_distribution': {'A': 0, 'B': 0, 'C': 0, 'U': 0},
        'details': []
    }

    for lead in all_leads:
        print(f"Scoring: {lead['business_name']}")

        try:
            # Calculate score
            score_data = calculate_score(lead)

            # Save to database
            update_lead_score(lead['id'], score_data)
            log_action(lead['id'], 'scored', f"Scored {score_data['total']} points, Tier {score_data['tier']}")

            print(f"  Score: {score_data['total']} | Tier: {score_data['tier']} | Signals: {len(score_data['signals'])}")

            if score_data['signals']:
                print(f"  Top signals:")
                for signal in sorted(score_data['signals'], key=lambda x: abs(x['points']), reverse=True)[:3]:
                    print(f"    - {signal['signal']}: {signal['points']:+d} points")

            results['scored'] += 1
            results['tier_distribution'][score_data['tier']] += 1

            results['details'].append({
                'business_name': lead['business_name'],
                'score': score_data['total'],
                'tier': score_data['tier'],
                'signals_count': len(score_data['signals'])
            })

        except Exception as e:
            print(f"  [ERROR] {str(e)[:200]}")

        print()

    # Summary
    print()
    print("=" * 80)
    print("SCORING SUMMARY")
    print("=" * 80)
    print(f"Total Leads: {results['total']}")
    print(f"Successfully Scored: {results['scored']}")
    print()

    # Tier distribution from database
    distribution = get_tier_distribution()
    total = distribution['total']

    print("TIER DISTRIBUTION:")
    print(f"  Tier A: {distribution['A']} leads ({distribution['A']/total*100:.1f}%)")
    print(f"  Tier B: {distribution['B']} leads ({distribution['B']/total*100:.1f}%)")
    print(f"  Tier C: {distribution['C']} leads ({distribution['C']/total*100:.1f}%)")
    print(f"  Tier U: {distribution['U']} leads ({distribution['U']/total*100:.1f}%)")
    print()

    # Show top leads by tier
    print("TOP LEADS BY TIER:")
    print()

    tier_a_leads = [d for d in results['details'] if d['tier'] == 'A']
    if tier_a_leads:
        print("Tier A Leads (Highest Priority):")
        for lead in sorted(tier_a_leads, key=lambda x: x['score'], reverse=True):
            print(f"  - {lead['business_name']}: {lead['score']} points ({lead['signals_count']} signals)")
    else:
        print("Tier A Leads: None")
    print()

    tier_b_leads = [d for d in results['details'] if d['tier'] == 'B']
    if tier_b_leads:
        print("Tier B Leads (Medium Priority):")
        for lead in sorted(tier_b_leads, key=lambda x: x['score'], reverse=True)[:5]:
            print(f"  - {lead['business_name']}: {lead['score']} points ({lead['signals_count']} signals)")
    else:
        print("Tier B Leads: None")
    print()

    tier_u_leads = [d for d in results['details'] if d['tier'] == 'U']
    if tier_u_leads:
        print(f"Tier U Leads (Insufficient Data): {len(tier_u_leads)} leads")
        for lead in tier_u_leads[:3]:
            print(f"  - {lead['business_name']}")
    print()

    print("Phase 5 testing complete!")
    print()

    return results

if __name__ == '__main__':
    test_scoring_engine()
