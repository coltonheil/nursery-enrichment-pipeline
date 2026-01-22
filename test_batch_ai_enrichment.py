"""
Test script for Phase 4C-D: Batch AI Enrichment
Tests the batch AI enrichment process end-to-end
"""

import time
from database.models import get_leads_for_gemini_enrichment, get_leads_by_gemini_status
from enrichment.gemini_client import enrich_lead_with_gemini
from database.models import update_gemini_data, update_gemini_error, log_action

def test_batch_ai_enrichment():
    """Test batch AI enrichment on all scraped leads."""

    print("Testing Batch AI Enrichment")
    print("=" * 80)
    print()

    # Get leads ready for enrichment
    leads_to_enrich = get_leads_for_gemini_enrichment()

    if not leads_to_enrich:
        print("[INFO] No leads ready for AI enrichment")
        print("Leads must have scrape_status='scraped' and gemini_status='pending'")
        return False

    print(f"Found {len(leads_to_enrich)} leads ready for AI enrichment")
    print()

    results = {
        'total': len(leads_to_enrich),
        'completed': 0,
        'failed': 0,
        'details': []
    }

    for i, lead in enumerate(leads_to_enrich, 1):
        print(f"Processing {i}/{results['total']}: {lead['business_name']}")
        print(f"  Location: {lead['city']}, {lead['state']}")

        try:
            # Enrich with Gemini
            start_time = time.time()
            enriched_data = enrich_lead_with_gemini(
                website_text=lead['website_text'],
                business_name=lead['business_name'],
                city=lead['city'],
                state=lead['state']
            )
            elapsed = time.time() - start_time

            # Save to database
            update_gemini_data(lead['id'], enriched_data, enriched_data)
            log_action(lead['id'], 'gemini_enriched', f"AI enrichment completed - {enriched_data.get('business_type')} ({enriched_data.get('confidence')} confidence)")

            print(f"  [SUCCESS] Enriched in {elapsed:.1f}s")
            print(f"  Type: {enriched_data.get('business_type')}")
            print(f"  Wholesale: {enriched_data.get('is_wholesale')}")
            print(f"  Container Production: {enriched_data.get('container_production')}")
            print(f"  Confidence: {enriched_data.get('confidence')}")
            print()

            results['completed'] += 1
            results['details'].append({
                'business_name': lead['business_name'],
                'status': 'success',
                'business_type': enriched_data.get('business_type'),
                'elapsed': elapsed
            })

            # Rate limit: 1 request per second
            if i < results['total']:
                print("  [Rate limit: waiting 1 second...]")
                time.sleep(1)
                print()

        except Exception as e:
            error_msg = str(e)[:200]
            update_gemini_error(lead['id'], error_msg)
            log_action(lead['id'], 'gemini_failed', error_msg)

            print(f"  [FAILED] {error_msg}")
            print()

            results['failed'] += 1
            results['details'].append({
                'business_name': lead['business_name'],
                'status': 'failed',
                'error': error_msg
            })

    # Summary
    print()
    print("=" * 80)
    print("BATCH AI ENRICHMENT SUMMARY")
    print("=" * 80)
    print(f"Total Leads: {results['total']}")
    print(f"Successfully Enriched: {results['completed']}")
    print(f"Failed: {results['failed']}")
    print(f"Success Rate: {results['completed']/results['total']*100:.1f}%")
    print()

    if results['completed'] > 0:
        # Show enriched leads
        enriched_leads = get_leads_by_gemini_status('enriched')
        print(f"Total Enriched Leads in Database: {len(enriched_leads)}")
        print()

        print("Sample Enriched Data:")
        for lead in enriched_leads[:3]:
            print(f"  - {lead['business_name']}")
            print(f"    Business Type: {lead['business_type']}")
            print(f"    Wholesale: {lead['is_wholesale']}, Retail: {lead['is_retail']}")
            print(f"    Container Production: {lead['container_production']}")
            if lead['owner_email']:
                print(f"    Email: {lead['owner_email']}")
            print()

    if results['failed'] > 0:
        print("Failed Leads:")
        for detail in results['details']:
            if detail['status'] == 'failed':
                print(f"  - {detail['business_name']}: {detail['error']}")
        print()

    print("Phase 4C-D testing complete!")
    print()

    return results

if __name__ == '__main__':
    test_batch_ai_enrichment()
