#!/usr/bin/env python3
"""Test enrichment on 50 Tier U leads to validate quality before scaling."""

import sqlite3
import sys
import time
from datetime import datetime

sys.stdout.reconfigure(line_buffering=True)

from enrichment.gemini_client import enrich_lead_with_gemini

DB_PATH = 'data/leads.db'

def test_enrichment():
    print("=" * 80)
    print("TEST: Tier U Enrichment (50 leads)")
    print("=" * 80)
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Get 50 Tier U leads with content but no contacts
    cursor.execute('''
        SELECT id, business_name, website, website_text, city, state
        FROM leads
        WHERE tier = 'U'
          AND website_text IS NOT NULL
          AND LENGTH(website_text) > 1000
          AND contact_name IS NULL
          AND owner_name IS NULL
        ORDER BY id
        LIMIT 50
    ''')
    
    leads = cursor.fetchall()
    print(f"Found {len(leads)} leads to test\n")
    
    stats = {
        'total': len(leads),
        'processed': 0,
        'extracted': 0,
        'with_email': 0,
        'errors': 0,
        'start_time': time.time()
    }
    
    for idx, lead in enumerate(leads, 1):
        lead_id = lead['id']
        name = lead['business_name']
        text = lead['website_text']
        
        print(f"[{idx}/{stats['total']}] {name[:50]}")
        
        try:
            enrichment = enrich_lead_with_gemini(
                website_text=text,
                business_name=name,
                city=lead['city'] or '',
                state=lead['state'] or ''
            )
            
            stats['processed'] += 1
            
            if enrichment:
                owner_name = enrichment.get('owner_name') or enrichment.get('contact_name')
                contact_name = enrichment.get('contact_name')
                email = enrichment.get('email') or enrichment.get('owner_email')
                
                if owner_name or contact_name:
                    stats['extracted'] += 1
                    print(f"   ✅ Contact: {owner_name or contact_name}")
                    
                    if email:
                        stats['with_email'] += 1
                        print(f"   📧 Email: {email}")
                    
                    # Save to database
                    cursor.execute('''
                        UPDATE leads
                        SET owner_name = COALESCE(?, owner_name),
                            contact_name = COALESCE(?, contact_name),
                            owner_email = COALESCE(?, owner_email),
                            gemini_status = 'complete',
                            gemini_enriched_at = ?
                        WHERE id = ?
                    ''', (owner_name, contact_name, email, 
                          datetime.now().isoformat(), lead_id))
                    conn.commit()
                else:
                    print(f"   ⚠️  No contact found")
            else:
                print(f"   ⚠️  Enrichment returned None")
                
        except Exception as e:
            stats['errors'] += 1
            print(f"   ❌ Error: {str(e)[:60]}")
        
        # Rate limiting
        time.sleep(0.5)
        
        # Progress every 10
        if idx % 10 == 0:
            rate = stats['extracted'] / stats['processed'] if stats['processed'] > 0 else 0
            print(f"\n   Progress: {stats['extracted']}/{stats['processed']} ({rate:.1%})\n")
    
    conn.close()
    
    # Final report
    elapsed = time.time() - stats['start_time']
    extraction_rate = stats['extracted'] / stats['processed'] if stats['processed'] > 0 else 0
    email_rate = stats['with_email'] / stats['extracted'] if stats['extracted'] > 0 else 0
    
    print("\n" + "=" * 80)
    print("TEST RESULTS")
    print("=" * 80)
    print(f"Total leads: {stats['total']}")
    print(f"Processed: {stats['processed']}")
    print(f"Contacts extracted: {stats['extracted']} ({extraction_rate:.1%})")
    print(f"  └─ With email: {stats['with_email']} ({email_rate:.1%} of extracted)")
    print(f"Errors: {stats['errors']}")
    print(f"Time: {elapsed/60:.1f} minutes")
    print(f"Cost estimate: ~${stats['processed'] * 0.001:.3f}")
    print("=" * 80)
    
    # Quality check
    print("\nQUALITY CHECK:")
    if extraction_rate >= 0.30:
        print("✅ Extraction rate >= 30% - GOOD")
    else:
        print(f"⚠️  Extraction rate {extraction_rate:.1%} < 30% - BELOW TARGET")
    
    if stats['errors'] / stats['total'] < 0.05:
        print("✅ Error rate < 5% - GOOD")
    else:
        print(f"⚠️  Error rate {stats['errors']/stats['total']:.1%} >= 5% - HIGH")
    
    print("\n✅ Test complete. Safe to scale to full Tier U." if extraction_rate >= 0.25 else "\n⚠️  Review extraction quality before scaling.")
    
    return stats

if __name__ == '__main__':
    stats = test_enrichment()
    sys.exit(0 if stats['extracted'] >= 15 else 1)  # Exit 0 if >= 30% extraction
