"""
Test script for Phase 7: Email Personalization
Tests generating custom email opening lines for Tier A+B leads
"""

import json
from database.models import get_leads_for_personalization, update_personalization, update_personalization_error, log_action
from enrichment.gemini_client import generate_personalization

def test_personalization():
    """Test personalization on Tier A and B leads."""

    print("Testing Email Personalization")
    print("=" * 80)
    print()

    # Get leads ready for personalization
    leads_to_personalize = get_leads_for_personalization()

    if not leads_to_personalize:
        print("[INFO] No leads ready for personalization")
        print("Leads must be:")
        print("  - Tier A or B (including manual overrides)")
        print("  - Gemini enriched")
        print("  - Not yet personalized")
        return False

    print(f"Found {len(leads_to_personalize)} leads ready for personalization")
    print()

    results = {
        'total': len(leads_to_personalize),
        'completed': 0,
        'failed': 0,
        'details': []
    }

    for i, lead in enumerate(leads_to_personalize, 1):
        print(f"Processing {i}/{results['total']}: {lead['business_name']}")
        print(f"  Tier: {lead['tier_override'] or lead['tier']} | Score: {lead['score']}")
        print(f"  Type: {lead['business_type']}")

        try:
            # Parse JSON fields
            crops_grown = []
            size_signals = []

            if lead['crops_grown']:
                try:
                    crops_grown = json.loads(lead['crops_grown'])
                except:
                    pass

            if lead['size_signals']:
                try:
                    size_signals = json.loads(lead['size_signals'])
                except:
                    pass

            # Generate personalization
            result = generate_personalization(
                business_name=lead['business_name'],
                business_type=lead['business_type'],
                organic_focus=lead['organic_focus'],
                crops_grown=crops_grown,
                size_signals=size_signals,
                is_wholesale=lead['is_wholesale'],
                container_production=lead['container_production']
            )

            # Save to database
            update_personalization(lead['id'], result['custom_line'], result['email_angle'])
            log_action(lead['id'], 'personalized', f"Generated custom line: {result['custom_line'][:50]}...")

            print(f"  [SUCCESS]")
            print(f"  Angle: {result['email_angle']}")
            print(f"  Line: \"{result['custom_line']}\"")
            print()

            results['completed'] += 1
            results['details'].append({
                'business_name': lead['business_name'],
                'tier': lead['tier_override'] or lead['tier'],
                'status': 'success',
                'custom_line': result['custom_line'],
                'email_angle': result['email_angle']
            })

            # Rate limit: 1 request per second
            if i < results['total']:
                import time
                print("  [Rate limit: waiting 1 second...]")
                time.sleep(1)
                print()

        except Exception as e:
            error_msg = str(e)[:200]
            update_personalization_error(lead['id'], error_msg)
            log_action(lead['id'], 'personalization_failed', error_msg)

            print(f"  [FAILED] {error_msg}")
            print()

            results['failed'] += 1
            results['details'].append({
                'business_name': lead['business_name'],
                'tier': lead['tier_override'] or lead['tier'],
                'status': 'failed',
                'error': error_msg
            })

    # Summary
    print()
    print("=" * 80)
    print("PERSONALIZATION SUMMARY")
    print("=" * 80)
    print(f"Total Leads: {results['total']}")
    print(f"Successfully Generated: {results['completed']}")
    print(f"Failed: {results['failed']}")
    print(f"Success Rate: {results['completed']/results['total']*100:.1f}%")
    print()

    if results['completed'] > 0:
        # Show by tier
        tier_a = [d for d in results['details'] if d['tier'] == 'A' and d['status'] == 'success']
        tier_b = [d for d in results['details'] if d['tier'] == 'B' and d['status'] == 'success']

        if tier_a:
            print(f"TIER A PERSONALIZATION ({len(tier_a)} leads):")
            print()
            for lead in tier_a:
                print(f"  {lead['business_name']}")
                print(f"  Angle: {lead['email_angle']}")
                print(f"  Line: \"{lead['custom_line']}\"")
                print()

        if tier_b:
            print(f"TIER B PERSONALIZATION ({len(tier_b)} leads):")
            print()
            for lead in tier_b:
                print(f"  {lead['business_name']}")
                print(f"  Angle: {lead['email_angle']}")
                print(f"  Line: \"{lead['custom_line']}\"")
                print()

        # Show by angle
        angles = {}
        for detail in results['details']:
            if detail['status'] == 'success':
                angle = detail['email_angle']
                if angle not in angles:
                    angles[angle] = []
                angles[angle].append(detail)

        print("BY EMAIL ANGLE:")
        print()
        for angle, leads in angles.items():
            print(f"  {angle.upper()}: {len(leads)} leads")
        print()

    if results['failed'] > 0:
        print("Failed Personalization:")
        for detail in results['details']:
            if detail['status'] == 'failed':
                print(f"  - {detail['business_name']}: {detail['error']}")
        print()

    print("Phase 7 testing complete!")
    print()

    return results

if __name__ == '__main__':
    test_personalization()
