"""
Test script for Phase 4A-B: Gemini AI Enrichment
Tests Gemini enrichment on real scraped leads from database
"""

import json
from database.models import get_leads_by_scrape_status
from enrichment.gemini_client import enrich_lead_with_gemini

def test_gemini_on_real_leads():
    """Test Gemini enrichment on 3 scraped leads."""

    print("Testing Gemini AI Enrichment on Real Leads")
    print("=" * 80)
    print()

    # Get leads that have been scraped successfully
    scraped_leads = get_leads_by_scrape_status('scraped')

    if not scraped_leads:
        print("[ERROR] No scraped leads found in database")
        print("Run the scraper first to get website text")
        return False

    # Test on first 3 scraped leads
    test_leads = scraped_leads[:3]

    print(f"Found {len(scraped_leads)} scraped leads. Testing on first {len(test_leads)}.")
    print()

    results = {
        'success': 0,
        'failed': 0,
        'details': []
    }

    for i, lead in enumerate(test_leads, 1):
        print(f"Test {i}/{len(test_leads)}: {lead['business_name']}")
        print(f"Location: {lead['city']}, {lead['state']}")
        print(f"Website: {lead['website']}")
        print(f"Website Text Length: {len(lead['website_text'] or '')} chars")
        print("-" * 80)

        try:
            # Call Gemini enrichment
            enriched_data = enrich_lead_with_gemini(
                website_text=lead['website_text'],
                business_name=lead['business_name'],
                city=lead['city'],
                state=lead['state']
            )

            # Success
            print("[SUCCESS] Gemini enrichment completed")
            print()
            print("Extracted Data:")
            print(json.dumps(enriched_data, indent=2))
            print()

            results['success'] += 1

            # Store summary
            results['details'].append({
                'business_name': lead['business_name'],
                'status': 'success',
                'business_type': enriched_data.get('business_type'),
                'is_wholesale': enriched_data.get('is_wholesale'),
                'container_production': enriched_data.get('container_production'),
                'confidence': enriched_data.get('confidence')
            })

        except Exception as e:
            print(f"[ERROR] Enrichment failed: {str(e)[:200]}")
            print()
            results['failed'] += 1
            results['details'].append({
                'business_name': lead['business_name'],
                'status': 'failed',
                'error': str(e)[:200]
            })

        print("=" * 80)
        print()

    # Summary
    print("TEST SUMMARY")
    print("=" * 80)
    print(f"Total Tests: {len(test_leads)}")
    print(f"Success: {results['success']}")
    print(f"Failed: {results['failed']}")
    print(f"Success Rate: {results['success']/len(test_leads)*100:.1f}%")
    print()

    if results['success'] > 0:
        print("Successful Extractions:")
        for detail in results['details']:
            if detail['status'] == 'success':
                print(f"  - {detail['business_name']}")
                print(f"    Type: {detail['business_type']}")
                print(f"    Wholesale: {detail['is_wholesale']}")
                print(f"    Container Production: {detail['container_production']}")
                print(f"    Confidence: {detail['confidence']}")
                print()

    if results['failed'] > 0:
        print("Failed Extractions:")
        for detail in results['details']:
            if detail['status'] == 'failed':
                print(f"  - {detail['business_name']}: {detail['error']}")

    print()
    print("Phase 4A-B testing complete!")
    print()

    return results

if __name__ == '__main__':
    test_gemini_on_real_leads()
