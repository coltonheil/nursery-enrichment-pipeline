#!/usr/bin/env python3
"""
Phase 2: Extract contacts from all 459 re-scraped leads.
Based on successful 24% extraction test.
"""

import sqlite3
import sys
import time
from datetime import datetime

# Force unbuffered output
sys.stdout.reconfigure(line_buffering=True)
sys.stderr.reconfigure(line_buffering=True)

from enrichment.gemini_client import enrich_lead_with_gemini

# Database path
DB_PATH = 'data/leads.db'

def extract_all():
    """Extract contacts from all re-scraped Tier A+B leads."""
    
    print("=" * 70)
    print("PHASE 2: FULL CONTACT EXTRACTION - 459 LEADS")
    print("=" * 70)
    print()
    
    # Connect to database
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Query all re-scraped leads with substantial content
    # Skip already processed leads from this run
    query = """
        SELECT id, business_name, website, website_text, tier, score, city, state
        FROM leads
        WHERE tier IN ('A', 'B')
          AND scraped_at >= '2026-01-27 17:00:00'
          AND website_text IS NOT NULL
          AND LENGTH(website_text) > 1000
          AND (gemini_enriched_at IS NULL OR gemini_enriched_at < '2026-01-28 05:22:00')
        ORDER BY 
          CASE tier WHEN 'A' THEN 1 WHEN 'B' THEN 2 END,
          score DESC
    """
    
    cursor.execute(query)
    leads = cursor.fetchall()
    
    print(f"✅ Found {len(leads)} leads to process")
    print(f"   Tier A: {sum(1 for l in leads if l['tier'] == 'A')}")
    print(f"   Tier B: {sum(1 for l in leads if l['tier'] == 'B')}")
    print()
    print(f"Expected results (based on 24% test rate):")
    print(f"   Contacts: ~{int(len(leads) * 0.24)} ({24}%)")
    print(f"   Emails: ~{int(len(leads) * 0.24)} ({24}%)")
    print()
    print(f"Starting extraction... (will report every 50 leads)")
    print("=" * 70)
    print()
    
    # Track statistics
    stats = {
        'total': len(leads),
        'processed': 0,
        'success': 0,
        'errors': 0,
        'contact_found': 0,
        'email_found': 0,
        'start_time': time.time()
    }
    
    # Process each lead
    for idx, lead in enumerate(leads, 1):
        lead_id = lead['id']
        business_name = lead['business_name']
        tier = lead['tier']
        
        try:
            # Call Gemini enrichment
            result = enrich_lead_with_gemini(
                website_text=lead['website_text'],
                business_name=business_name,
                city=lead['city'],
                state=lead['state']
            )
            
            # Update database with results (with retry on lock)
            update_query = """
                UPDATE leads
                SET contact_name = ?,
                    contact_title = ?,
                    contact_priority = ?,
                    owner_email = COALESCE(?, owner_email),
                    gemini_status = 'complete',
                    gemini_enriched_at = ?,
                    gemini_confidence = ?
                WHERE id = ?
            """
            
            # Retry up to 3 times on database lock
            for retry in range(3):
                try:
                    cursor.execute(update_query, (
                        result.get('contact_name'),
                        result.get('contact_title'),
                        result.get('contact_priority'),
                        result.get('email'),
                        datetime.now().isoformat(),
                        result.get('confidence'),
                        lead_id
                    ))
                    conn.commit()  # Commit immediately to release lock
                    break
                except sqlite3.OperationalError as e:
                    if 'locked' in str(e) and retry < 2:
                        time.sleep(0.5)
                        continue
                    else:
                        raise
            
            stats['processed'] += 1
            stats['success'] += 1
            
            # Track contact extraction
            if result.get('contact_name'):
                stats['contact_found'] += 1
            
            if result.get('email'):
                stats['email_found'] += 1
            
            # Progress report every 50 leads
            if idx % 50 == 0:
                elapsed = time.time() - stats['start_time']
                rate = stats['processed'] / elapsed * 60  # leads per minute
                remaining = stats['total'] - stats['processed']
                eta_min = remaining / rate if rate > 0 else 0
                
                print(f"[{idx}/{stats['total']}] Progress Report")
                print(f"  Processed: {stats['processed']}")
                print(f"  Contacts found: {stats['contact_found']} ({stats['contact_found']/stats['processed']*100:.1f}%)")
                print(f"  Emails found: {stats['email_found']} ({stats['email_found']/stats['processed']*100:.1f}%)")
                print(f"  Speed: {rate:.1f} leads/min")
                print(f"  ETA: {int(eta_min)}min")
                print()
                
        except Exception as e:
            stats['errors'] += 1
            stats['processed'] += 1
            print(f"[{idx}/{stats['total']}] {business_name} - ERROR: {str(e)[:80]}")
    
    # Close connection
    conn.close()
    
    # Print final summary
    print()
    print("=" * 70)
    print("PHASE 2 COMPLETE - FINAL RESULTS")
    print("=" * 70)
    print(f"Total leads processed: {stats['total']}")
    print(f"Successful extractions: {stats['success']} ({stats['success']/stats['total']*100:.1f}%)")
    print(f"Errors: {stats['errors']} ({stats['errors']/stats['total']*100:.1f}%)")
    print()
    print(f"Contact names found: {stats['contact_found']} ({stats['contact_found']/stats['total']*100:.1f}%)")
    print(f"Emails found: {stats['email_found']} ({stats['email_found']/stats['total']*100:.1f}%)")
    print()
    print(f"Time elapsed: {(time.time() - stats['start_time'])/60:.1f} minutes")
    print()
    print("✅ Ready for Phase 3: Email hunting on extracted contacts")
    print("=" * 70)
    
    return True

if __name__ == '__main__':
    try:
        success = extract_all()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user. Progress has been saved.")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
