#!/usr/bin/env python3
"""
Phase 3: Email hunting on extracted contacts.
Uses pattern-based inference + MX verification.
"""

import sqlite3
import sys
import time
from datetime import datetime

sys.stdout.reconfigure(line_buffering=True)
sys.stderr.reconfigure(line_buffering=True)

from enrichment.email_hunter import hunt_email

DB_PATH = 'data/leads.db'

def hunt_emails():
    """Hunt emails for all newly extracted contacts."""
    
    print("=" * 70)
    print("PHASE 3: EMAIL HUNTING - EXTRACTED CONTACTS")
    print("=" * 70)
    print()
    
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Query contacts without personal emails
    query = """
        SELECT id, business_name, contact_name, contact_title, website, tier
        FROM leads
        WHERE tier IN ('A', 'B')
          AND contact_name IS NOT NULL
          AND contact_name != ''
          AND gemini_enriched_at >= '2026-01-28 05:00:00'
          AND (contact_email IS NULL OR contact_email = '')
        ORDER BY 
          CASE tier WHEN 'A' THEN 1 WHEN 'B' THEN 2 END,
          score DESC
    """
    
    cursor.execute(query)
    leads = cursor.fetchall()
    
    print(f"✅ Found {len(leads)} contacts to hunt emails for")
    print()
    
    stats = {
        'total': len(leads),
        'processed': 0,
        'emails_found': 0,
        'high_confidence': 0,
        'start_time': time.time()
    }
    
    for idx, lead in enumerate(leads, 1):
        lead_id = lead['id']
        business_name = lead['business_name']
        contact_name = lead['contact_name']
        website = lead['website']
        tier = lead['tier']
        
        print(f"[{idx}/{len(leads)}] {business_name} - {contact_name} (Tier {tier})")
        
        try:
            # Hunt email
            result = hunt_email(
                owner_name=contact_name,
                business_name=business_name,
                website=website
            )
            
            if result and result.email:
                # Update database
                update_query = """
                    UPDATE leads
                    SET contact_email = ?,
                        email_confidence = ?,
                        email_method = ?,
                        email_found_at = ?
                    WHERE id = ?
                """
                
                cursor.execute(update_query, (
                    result.email,
                    result.confidence,
                    result.method,
                    datetime.now().isoformat(),
                    lead_id
                ))
                conn.commit()
                
                stats['emails_found'] += 1
                if result.confidence >= 70:
                    stats['high_confidence'] += 1
                
                print(f"   ✅ {result.email} (confidence: {result.confidence}%, method: {result.method})")
            else:
                print(f"   ⚠️  No email found")
            
            stats['processed'] += 1
            
            # Progress report every 25 leads
            if idx % 25 == 0:
                elapsed = time.time() - stats['start_time']
                rate = stats['processed'] / elapsed * 60
                remaining = stats['total'] - stats['processed']
                eta_min = remaining / rate if rate > 0 else 0
                
                print()
                print(f"[Progress] {stats['processed']}/{stats['total']}")
                print(f"  Emails found: {stats['emails_found']} ({stats['emails_found']/stats['processed']*100:.1f}%)")
                print(f"  High confidence (≥70%): {stats['high_confidence']}")
                print(f"  Speed: {rate:.1f} leads/min, ETA: {int(eta_min)}min")
                print()
                
        except Exception as e:
            stats['processed'] += 1
            print(f"   ❌ Error: {str(e)[:80]}")
    
    conn.close()
    
    # Final summary
    print()
    print("=" * 70)
    print("PHASE 3 COMPLETE - FINAL RESULTS")
    print("=" * 70)
    print(f"Total contacts processed: {stats['total']}")
    print(f"Emails found: {stats['emails_found']} ({stats['emails_found']/stats['total']*100:.1f}%)")
    print(f"High confidence (≥70%): {stats['high_confidence']} ({stats['high_confidence']/stats['total']*100:.1f}%)")
    print()
    print(f"Time elapsed: {(time.time() - stats['start_time'])/60:.1f} minutes")
    print()
    print("✅ Ready for Phase 4: Re-scoring and final report")
    print("=" * 70)
    
    return True

if __name__ == '__main__':
    try:
        success = hunt_emails()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
