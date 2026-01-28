#!/usr/bin/env python3
"""
Enrich Tier U leads that have been scraped.
Extract business data and re-score to potentially upgrade to A/B/C.
"""

import sqlite3
import sys
import time
from datetime import datetime

sys.stdout.reconfigure(line_buffering=True)
sys.stderr.reconfigure(line_buffering=True)

from enrichment.gemini_client import enrich_lead_with_gemini
from enrichment.scorer import calculate_score

DB_PATH = 'data/leads.db'

def enrich_tier_u():
    """Enrich Tier U leads with scraped content."""
    
    print("=" * 80)
    print("TIER U ENRICHMENT + CONTACT EXTRACTION")
    print("=" * 80)
    print()
    
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Query Tier U leads with content but not enriched
    query = """
        SELECT id, business_name, website, website_text, city, state
        FROM leads
        WHERE tier = 'U'
          AND scrape_status = 'scraped'
          AND website_text IS NOT NULL
          AND LENGTH(website_text) > 500
          AND (gemini_status IS NULL OR gemini_status NOT IN ('complete', 'enriched'))
        ORDER BY LENGTH(website_text) DESC
    """
    
    cursor.execute(query)
    leads = cursor.fetchall()
    
    print(f"✅ Found {len(leads)} Tier U leads ready for enrichment")
    print()
    print(f"Starting enrichment... (will report every 50 leads)")
    print("=" * 80)
    print()
    
    stats = {
        'total': len(leads),
        'processed': 0,
        'contacts_found': 0,
        'upgraded_a': 0,
        'upgraded_b': 0,
        'upgraded_c': 0,
        'stayed_u': 0,
        'errors': 0,
        'start_time': time.time()
    }
    
    for idx, lead in enumerate(leads, 1):
        lead_id = lead['id']
        business_name = lead['business_name']
        
        try:
            # Enrich with Gemini
            result = enrich_lead_with_gemini(
                website_text=lead['website_text'],
                business_name=business_name,
                city=lead['city'],
                state=lead['state']
            )
            
            # Calculate new score
            score_result = calculate_score(result)
            new_score = score_result.get('total', 0) if score_result else 0
            
            # Determine new tier
            if new_score >= 40:
                new_tier = 'A'
                stats['upgraded_a'] += 1
            elif new_score >= 20:
                new_tier = 'B'
                stats['upgraded_b'] += 1
            elif new_score > -20:
                new_tier = 'C'
                stats['upgraded_c'] += 1
            else:
                new_tier = 'U'
                stats['stayed_u'] += 1
            
            contact_name = result.get('contact_name')
            if contact_name:
                stats['contacts_found'] += 1
            
            # Update database
            cursor.execute("""
                UPDATE leads
                SET gemini_status = 'complete',
                    gemini_enriched_at = ?,
                    business_type = ?,
                    is_wholesale = ?,
                    is_retail = ?,
                    container_production = ?,
                    soil_relevance = ?,
                    organic_focus = ?,
                    contact_name = ?,
                    contact_title = ?,
                    contact_priority = ?,
                    score = ?,
                    tier = ?,
                    gemini_confidence = ?
                WHERE id = ?
            """, (
                datetime.now().isoformat(),
                result.get('business_type'),
                result.get('is_wholesale'),
                result.get('is_retail'),
                result.get('container_production'),
                result.get('soil_relevance'),
                result.get('organic_focus'),
                contact_name,
                result.get('contact_title'),
                result.get('contact_priority'),
                new_score,
                new_tier,
                result.get('confidence'),
                lead_id
            ))
            conn.commit()
            
            stats['processed'] += 1
            
            # Progress report every 50 leads
            if idx % 50 == 0:
                elapsed = time.time() - stats['start_time']
                rate = stats['processed'] / elapsed * 60
                remaining = stats['total'] - stats['processed']
                eta_min = remaining / rate if rate > 0 else 0
                
                print(f"[{idx}/{stats['total']}] Progress Report")
                print(f"  Processed: {stats['processed']}")
                print(f"  Upgraded to A: {stats['upgraded_a']}")
                print(f"  Upgraded to B: {stats['upgraded_b']}")
                print(f"  Upgraded to C: {stats['upgraded_c']}")
                print(f"  Contacts: {stats['contacts_found']}")
                print(f"  Speed: {rate:.1f} leads/min")
                print(f"  ETA: {int(eta_min)}min")
                print()
                
        except Exception as e:
            stats['errors'] += 1
            stats['processed'] += 1
            print(f"  [{idx}] {business_name[:30]} - ERROR: {str(e)[:50]}")
    
    conn.close()
    
    # Final summary
    print()
    print("=" * 80)
    print("TIER U ENRICHMENT COMPLETE")
    print("=" * 80)
    print(f"Total processed: {stats['total']}")
    print(f"Upgraded to A: {stats['upgraded_a']} ({stats['upgraded_a']/max(stats['processed'],1)*100:.1f}%)")
    print(f"Upgraded to B: {stats['upgraded_b']} ({stats['upgraded_b']/max(stats['processed'],1)*100:.1f}%)")
    print(f"Upgraded to C: {stats['upgraded_c']} ({stats['upgraded_c']/max(stats['processed'],1)*100:.1f}%)")
    print(f"Stayed U: {stats['stayed_u']} ({stats['stayed_u']/max(stats['processed'],1)*100:.1f}%)")
    print(f"Contacts found: {stats['contacts_found']}")
    print(f"Errors: {stats['errors']}")
    print()
    print(f"Time elapsed: {(time.time() - stats['start_time'])/60:.1f} minutes")
    print("=" * 80)
    
    return True

if __name__ == '__main__':
    try:
        enrich_tier_u()
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
