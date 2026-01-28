#!/usr/bin/env python3
"""
Extract contacts from Tier C leads.
These are already enriched, just need contact extraction.
"""

import sqlite3
import sys
import time
from datetime import datetime

sys.stdout.reconfigure(line_buffering=True)
sys.stderr.reconfigure(line_buffering=True)

from enrichment.gemini_client import enrich_lead_with_gemini
from enrichment.email_hunter import hunt_email

DB_PATH = 'data/leads.db'

def extract_tier_c():
    """Extract contacts from Tier C leads."""
    
    print("=" * 80)
    print("TIER C CONTACT EXTRACTION")
    print("=" * 80)
    print()
    
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Query Tier C leads with good content but no contacts
    query = """
        SELECT id, business_name, website, website_text, city, state, score
        FROM leads
        WHERE tier = 'C'
          AND gemini_status IN ('complete', 'enriched')
          AND website_text IS NOT NULL
          AND LENGTH(website_text) > 1000
          AND (contact_name IS NULL OR contact_name = '')
        ORDER BY score DESC, LENGTH(website_text) DESC
    """
    
    cursor.execute(query)
    leads = cursor.fetchall()
    
    print(f"✅ Found {len(leads)} Tier C leads ready for contact extraction")
    print()
    print(f"Starting extraction... (will report every 100 leads)")
    print("=" * 80)
    print()
    
    stats = {
        'total': len(leads),
        'processed': 0,
        'contacts_found': 0,
        'emails_found': 0,
        'errors': 0,
        'start_time': time.time()
    }
    
    for idx, lead in enumerate(leads, 1):
        lead_id = lead['id']
        business_name = lead['business_name']
        
        try:
            # Extract contact using Gemini
            result = enrich_lead_with_gemini(
                website_text=lead['website_text'],
                business_name=business_name,
                city=lead['city'],
                state=lead['state']
            )
            
            contact_name = result.get('contact_name')
            contact_email = None
            
            # If contact found, hunt email
            if contact_name:
                stats['contacts_found'] += 1
                
                try:
                    email_result = hunt_email(
                        owner_name=contact_name,
                        business_name=business_name,
                        website=lead['website']
                    )
                    
                    if email_result and email_result.email:
                        contact_email = email_result.email
                        stats['emails_found'] += 1
                except:
                    pass  # Email hunting is optional
            
            # Update database
            cursor.execute("""
                UPDATE leads
                SET contact_name = ?,
                    contact_title = ?,
                    contact_priority = ?,
                    contact_email = ?,
                    gemini_enriched_at = ?
                WHERE id = ?
            """, (
                contact_name,
                result.get('contact_title'),
                result.get('contact_priority'),
                contact_email,
                datetime.now().isoformat(),
                lead_id
            ))
            conn.commit()
            
            stats['processed'] += 1
            
            # Progress report every 100 leads
            if idx % 100 == 0:
                elapsed = time.time() - stats['start_time']
                rate = stats['processed'] / elapsed * 60
                remaining = stats['total'] - stats['processed']
                eta_min = remaining / rate if rate > 0 else 0
                
                print(f"[{idx}/{stats['total']}] Progress Report")
                print(f"  Processed: {stats['processed']}")
                print(f"  Contacts: {stats['contacts_found']} ({stats['contacts_found']/stats['processed']*100:.1f}%)")
                print(f"  Emails: {stats['emails_found']} ({stats['emails_found']/stats['processed']*100:.1f}%)")
                print(f"  Speed: {rate:.1f} leads/min")
                print(f"  ETA: {int(eta_min)}min")
                print()
                
        except Exception as e:
            stats['errors'] += 1
            stats['processed'] += 1
    
    conn.close()
    
    # Final summary
    print()
    print("=" * 80)
    print("TIER C EXTRACTION COMPLETE")
    print("=" * 80)
    print(f"Total processed: {stats['total']}")
    print(f"Contacts found: {stats['contacts_found']} ({stats['contacts_found']/stats['total']*100:.1f}%)")
    print(f"Emails found: {stats['emails_found']} ({stats['emails_found']/stats['total']*100:.1f}%)")
    print(f"Errors: {stats['errors']}")
    print()
    print(f"Time elapsed: {(time.time() - stats['start_time'])/60:.1f} minutes")
    print("=" * 80)
    
    return True

if __name__ == '__main__':
    try:
        extract_tier_c()
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
