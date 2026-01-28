#!/usr/bin/env python3
"""
Safe Gemini contact extraction with proper database handling.
Commits after each lead to avoid locks.
"""

import sqlite3
import sys
import time
from datetime import datetime
from enrichment.gemini_client import enrich_lead_with_gemini

DB_PATH = 'data/leads.db'

def extract_contacts(limit=50):
    """Extract contacts from rescraped leads with safe database handling."""
    
    print("=" * 70)
    print("GEMINI CONTACT EXTRACTION (SAFE MODE)")
    print("=" * 70)
    print()
    
    # Get leads to process (close connection immediately)
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    query = """
        SELECT id, business_name, website, website_text, tier, score, city, state
        FROM leads
        WHERE tier IN ('A', 'B')
          AND scrape_status = 'rescraped'
          AND website_text IS NOT NULL
          AND LENGTH(website_text) > 1000
          AND (gemini_status IS NULL OR gemini_status != 'complete')
        ORDER BY 
          CASE tier WHEN 'A' THEN 1 WHEN 'B' THEN 2 END,
          score DESC
        LIMIT ?
    """
    
    cursor.execute(query, (limit,))
    leads = [dict(row) for row in cursor.fetchall()]
    conn.close()  # Close immediately
    
    if not leads:
        print("❌ No leads found to process!")
        return False
    
    print(f"✅ Found {len(leads)} leads to process")
    print()
    
    stats = {
        'total': len(leads),
        'success': 0,
        'errors': 0,
        'contact_found': 0,
        'contacts': []
    }
    
    # Process each lead with individual connections
    for idx, lead in enumerate(leads, 1):
        lead_id = lead['id']
        business_name = lead['business_name']
        tier = lead['tier']
        text_len = len(lead['website_text'])
        
        print(f"[{idx}/{len(leads)}] {business_name} (Tier {tier}, {text_len:,} chars)")
        
        try:
            # Call Gemini
            result = enrich_lead_with_gemini(
                website_text=lead['website_text'],
                business_name=business_name,
                city=lead['city'],
                state=lead['state']
            )
            
            # Open NEW connection for this update only
            conn = sqlite3.connect(DB_PATH, timeout=30.0)
            cursor = conn.cursor()
            
            cursor.execute("""
                UPDATE leads
                SET contact_name = ?,
                    contact_title = ?,
                    contact_priority = ?,
                    owner_email = ?,
                    gemini_status = 'complete',
                    gemini_enriched_at = ?,
                    gemini_confidence = ?
                WHERE id = ?
            """, (
                result.get('contact_name'),
                result.get('contact_title'),
                result.get('contact_priority'),
                result.get('email'),
                datetime.now().isoformat(),
                result.get('confidence'),
                lead_id
            ))
            
            conn.commit()
            conn.close()  # Close immediately after commit
            
            stats['success'] += 1
            
            if result.get('contact_name'):
                stats['contact_found'] += 1
                contact_info = f"{result['contact_name']}"
                if result.get('contact_title'):
                    contact_info += f" ({result['contact_title']})"
                stats['contacts'].append(contact_info)
                print(f"   ✅ Contact: {contact_info}")
            else:
                print(f"   ⚠️  No contact found")
            
            if result.get('email'):
                print(f"   📧 Email: {result['email']}")
            
            # Small delay to avoid rate limits
            time.sleep(1)
            
        except Exception as e:
            stats['errors'] += 1
            error_msg = str(e)[:100]
            print(f"   ❌ Error: {error_msg}")
            time.sleep(2)  # Longer delay after error
    
    # Print summary
    print()
    print("=" * 70)
    print("EXTRACTION COMPLETE")
    print("=" * 70)
    print(f"Total processed: {stats['total']}")
    print(f"Successful: {stats['success']} ({stats['success']/stats['total']*100:.1f}%)")
    print(f"Errors: {stats['errors']}")
    print()
    print(f"Contacts found: {stats['contact_found']} ({stats['contact_found']/stats['total']*100:.1f}%)")
    print()
    
    if stats['contacts']:
        print("Sample contacts:")
        for contact in stats['contacts'][:10]:
            print(f"  - {contact}")
        if len(stats['contacts']) > 10:
            print(f"  ... and {len(stats['contacts']) - 10} more")
    
    print()
    extraction_rate = stats['contact_found'] / stats['total'] * 100
    
    if extraction_rate >= 30:
        print(f"✅ EXCELLENT: {extraction_rate:.1f}% extraction rate - Proceed to full batch!")
        return True
    elif extraction_rate >= 20:
        print(f"✅ GOOD: {extraction_rate:.1f}% extraction rate - Acceptable")
        return True
    else:
        print(f"⚠️  LOW: {extraction_rate:.1f}% extraction rate - Review needed")
        return False

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--limit', type=int, default=50, help='Number of leads to process')
    args = parser.parse_args()
    
    success = extract_contacts(args.limit)
    sys.exit(0 if success else 1)
