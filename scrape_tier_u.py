#!/usr/bin/env python3
"""
Scrape websites for Tier U leads that have no content.
This is the first step before enrichment.
"""

import sqlite3
import sys
import time
from datetime import datetime

sys.stdout.reconfigure(line_buffering=True)
sys.stderr.reconfigure(line_buffering=True)

from enrichment.web_scraper import scrape_and_extract

DB_PATH = 'data/leads.db'

def scrape_tier_u():
    """Scrape websites for Tier U leads."""
    
    print("=" * 80)
    print("TIER U WEB SCRAPING")
    print("=" * 80)
    print()
    
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Query Tier U leads with websites but no/little content
    # Skip already scraped ones (resume from where we left off)
    query = """
        SELECT id, business_name, website
        FROM leads
        WHERE tier = 'U'
          AND website IS NOT NULL
          AND website != ''
          AND (website_text IS NULL OR LENGTH(website_text) < 500)
          AND (scrape_status IS NULL OR scrape_status NOT IN ('scraped', 'failed'))
        ORDER BY id
    """
    
    cursor.execute(query)
    leads = cursor.fetchall()
    
    print(f"✅ Found {len(leads)} Tier U leads needing web scraping")
    print()
    print(f"Starting scraping... (will report every 100 leads)")
    print("=" * 80)
    print()
    
    stats = {
        'total': len(leads),
        'processed': 0,
        'success': 0,
        'failed': 0,
        'no_website': 0,
        'start_time': time.time()
    }
    
    for idx, lead in enumerate(leads, 1):
        lead_id = lead['id']
        business_name = lead['business_name']
        website = lead['website']
        
        if not website or len(website.strip()) < 5:
            stats['no_website'] += 1
            stats['processed'] += 1
            continue
        
        try:
            # Scrape website with timeout protection
            import signal
            
            def timeout_handler(signum, frame):
                raise TimeoutError("Scraping timeout")
            
            # Set 30 second timeout per website
            old_handler = signal.signal(signal.SIGALRM, timeout_handler)
            signal.alarm(30)
            
            try:
                text, status_info = scrape_and_extract(website)
            finally:
                signal.alarm(0)
                signal.signal(signal.SIGALRM, old_handler)
            
            if text and len(text) > 100:
                # Update database with scraped content
                cursor.execute("""
                    UPDATE leads
                    SET website_text = ?,
                        scrape_status = 'scraped',
                        scraped_at = ?
                    WHERE id = ?
                """, (
                    text,
                    datetime.now().isoformat(),
                    lead_id
                ))
                conn.commit()
                stats['success'] += 1
            else:
                # Mark as failed
                cursor.execute("""
                    UPDATE leads
                    SET scrape_status = 'failed',
                        scrape_error = ?
                    WHERE id = ?
                """, (
                    str(status_info.get('error', 'No content'))[:200],
                    lead_id
                ))
                conn.commit()
                stats['failed'] += 1
            
            stats['processed'] += 1
            
            # Progress report every 100 leads
            if idx % 100 == 0:
                elapsed = time.time() - stats['start_time']
                rate = stats['processed'] / elapsed * 60
                remaining = stats['total'] - stats['processed']
                eta_min = remaining / rate if rate > 0 else 0
                
                print(f"[{idx}/{stats['total']}] Progress Report")
                print(f"  Processed: {stats['processed']}")
                print(f"  Success: {stats['success']} ({stats['success']/stats['processed']*100:.1f}%)")
                print(f"  Failed: {stats['failed']} ({stats['failed']/stats['processed']*100:.1f}%)")
                print(f"  Speed: {rate:.1f} leads/min")
                print(f"  ETA: {int(eta_min)}min ({eta_min/60:.1f}h)")
                print()
                
        except TimeoutError:
            stats['failed'] += 1
            stats['processed'] += 1
            
            cursor.execute("""
                UPDATE leads
                SET scrape_status = 'failed',
                    scrape_error = 'Timeout after 30s'
                WHERE id = ?
            """, (lead_id,))
            conn.commit()
            print(f"  [{idx}] {business_name[:30]} - TIMEOUT (skipped)")
            
        except Exception as e:
            stats['failed'] += 1
            stats['processed'] += 1
            
            cursor.execute("""
                UPDATE leads
                SET scrape_status = 'failed',
                    scrape_error = ?
                WHERE id = ?
            """, (
                str(e)[:200],
                lead_id
            ))
            conn.commit()
    
    conn.close()
    
    # Final summary
    elapsed = time.time() - stats['start_time']
    print()
    print("=" * 80)
    print("TIER U SCRAPING COMPLETE")
    print("=" * 80)
    print(f"Total processed: {stats['total']}")
    print(f"Success: {stats['success']} ({stats['success']/max(stats['processed'],1)*100:.1f}%)")
    print(f"Failed: {stats['failed']} ({stats['failed']/max(stats['processed'],1)*100:.1f}%)")
    print(f"No website: {stats['no_website']}")
    print()
    print(f"Time elapsed: {elapsed/60:.1f} minutes ({elapsed/3600:.1f} hours)")
    print()
    print("✅ Ready for Tier U enrichment")
    print("=" * 80)
    
    return True

if __name__ == '__main__':
    try:
        scrape_tier_u()
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user. Progress saved.")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
