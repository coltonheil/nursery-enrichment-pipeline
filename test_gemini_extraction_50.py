#!/usr/bin/env python3
"""
Test Gemini contact extraction on 50 re-scraped leads.
Validates extraction quality before scaling to full 459 leads.
"""

import sqlite3
import sys
from datetime import datetime

# Force unbuffered output
sys.stdout.reconfigure(line_buffering=True)
sys.stderr.reconfigure(line_buffering=True)

from enrichment.gemini_client import enrich_lead_with_gemini

# Database path
DB_PATH = 'data/leads.db'

def test_extraction():
    """Test Gemini extraction on 50 re-scraped leads."""
    
    print("=" * 70)
    print("TEST GEMINI CONTACT EXTRACTION - 50 LEADS")
    print("=" * 70)
    print()
    
    # Connect to database
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Query 50 re-scraped leads with substantial content
    # Prioritize Tier A, then B, with good content quality
    query = """
        SELECT id, business_name, website, website_text, tier, score, city, state
        FROM leads
        WHERE tier IN ('A', 'B')
          AND scraped_at >= '2026-01-27 17:00:00'
          AND website_text IS NOT NULL
          AND LENGTH(website_text) > 1000
        ORDER BY 
          CASE tier WHEN 'A' THEN 1 WHEN 'B' THEN 2 END,
          score DESC,
          LENGTH(website_text) DESC
        LIMIT 50
    """
    
    cursor.execute(query)
    leads = cursor.fetchall()
    
    if not leads:
        print("❌ No leads found matching criteria!")
        print("   Criteria: Tier A/B, rescraped after Jan 27, >1000 chars")
        conn.close()
        return False
    
    print(f"✅ Found {len(leads)} leads to test")
    print(f"   Tier A: {sum(1 for l in leads if l['tier'] == 'A')}")
    print(f"   Tier B: {sum(1 for l in leads if l['tier'] == 'B')}")
    print()
    
    # Track statistics
    stats = {
        'total': len(leads),
        'success': 0,
        'errors': 0,
        'contact_found': 0,
        'email_found': 0,
        'contact_names': [],
        'errors_list': []
    }
    
    # Process each lead
    for idx, lead in enumerate(leads, 1):
        lead_id = lead['id']
        business_name = lead['business_name']
        website = lead['website']
        tier = lead['tier']
        text_length = len(lead['website_text']) if lead['website_text'] else 0
        
        print(f"[{idx}/{len(leads)}] {business_name} (Tier {tier}, {text_length:,} chars)")
        
        try:
            # Call Gemini enrichment
            result = enrich_lead_with_gemini(
                website_text=lead['website_text'],
                business_name=business_name,
                city=lead['city'],
                state=lead['state']
            )
            
            # Update database with results
            update_query = """
                UPDATE leads
                SET contact_name = ?,
                    contact_title = ?,
                    contact_priority = ?,
                    owner_email = ?,
                    gemini_status = 'complete',
                    gemini_enriched_at = ?,
                    gemini_confidence = ?
                WHERE id = ?
            """
            
            cursor.execute(update_query, (
                result.get('contact_name'),
                result.get('contact_title'),
                result.get('contact_priority'),
                result.get('email'),
                datetime.now().isoformat(),
                result.get('confidence'),
                lead_id
            ))
            
            stats['success'] += 1
            
            # Track contact extraction
            if result.get('contact_name'):
                stats['contact_found'] += 1
                contact_info = f"{result['contact_name']}"
                if result.get('contact_title'):
                    contact_info += f" ({result['contact_title']})"
                stats['contact_names'].append(contact_info)
                print(f"   ✅ Contact: {contact_info}")
            else:
                print(f"   ⚠️  No contact found")
            
            if result.get('email'):
                stats['email_found'] += 1
                print(f"   📧 Email: {result['email']}")
            
        except Exception as e:
            stats['errors'] += 1
            error_msg = str(e)[:100]
            stats['errors_list'].append(f"{business_name}: {error_msg}")
            print(f"   ❌ Error: {error_msg}")
    
    # Commit all changes
    conn.commit()
    conn.close()
    
    # Print summary
    print()
    print("=" * 70)
    print("TEST RESULTS SUMMARY")
    print("=" * 70)
    print(f"Total leads processed: {stats['total']}")
    print(f"Successful extractions: {stats['success']} ({stats['success']/stats['total']*100:.1f}%)")
    print(f"Errors: {stats['errors']} ({stats['errors']/stats['total']*100:.1f}%)")
    print()
    print(f"Contact names found: {stats['contact_found']} ({stats['contact_found']/stats['total']*100:.1f}%)")
    print(f"Emails found: {stats['email_found']} ({stats['email_found']/stats['total']*100:.1f}%)")
    print()
    
    if stats['contact_names']:
        print("Sample contacts extracted:")
        for contact in stats['contact_names'][:10]:
            print(f"  - {contact}")
        if len(stats['contact_names']) > 10:
            print(f"  ... and {len(stats['contact_names']) - 10} more")
        print()
    
    if stats['errors_list']:
        print("Errors encountered:")
        for error in stats['errors_list'][:5]:
            print(f"  - {error}")
        if len(stats['errors_list']) > 5:
            print(f"  ... and {len(stats['errors_list']) - 5} more")
        print()
    
    # Determine success
    extraction_rate = stats['contact_found'] / stats['total'] * 100
    
    print("=" * 70)
    print("RECOMMENDATION")
    print("=" * 70)
    
    if extraction_rate >= 35:
        print(f"✅ EXCELLENT: {extraction_rate:.1f}% extraction rate")
        print("   Recommend: Proceed with full 459-lead extraction")
        return True
    elif extraction_rate >= 25:
        print(f"✅ GOOD: {extraction_rate:.1f}% extraction rate")
        print("   Recommend: Proceed with full extraction")
        print("   Note: Lower than expected 40-50%, but still valuable")
        return True
    elif extraction_rate >= 15:
        print(f"⚠️  MARGINAL: {extraction_rate:.1f}% extraction rate")
        print("   Recommend: Review prompt or consider manual review")
        return False
    else:
        print(f"❌ LOW: {extraction_rate:.1f}% extraction rate")
        print("   Recommend: Debug prompt or scraper before scaling")
        return False

if __name__ == '__main__':
    success = test_extraction()
    sys.exit(0 if success else 1)
