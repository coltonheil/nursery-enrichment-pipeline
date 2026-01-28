#!/usr/bin/env python3
"""Scrape all leads with websites but no content."""

import sqlite3
import sys
import time
from datetime import datetime

sys.stdout.reconfigure(line_buffering=True)

from enrichment.web_scraper import scrape_and_extract

DB_PATH = 'data/leads.db'

def scrape_pending():
    print("=" * 80)
    print("SCRAPING PENDING LEADS")
    print("=" * 80)
    
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Get leads with websites but no/little content
    query = """
        SELECT id, business_name, website, tier
        FROM leads
        WHERE website IS NOT NULL AND website != ''
        AND website NOT LIKE '%facebook%'
        AND (website_text IS NULL OR LENGTH(website_text) < 500)
        AND tier IN ('U', 'C')
        ORDER BY tier, id
    """
    
    cursor.execute(query)
    leads = cursor.fetchall()
    
    print(f"\n✅ Found {len(leads)} leads to scrape")
    print("Starting scraping...")
    print("=" * 80 + "\n")
    
    stats = {'total': len(leads), 'processed': 0, 'success': 0, 'failed': 0, 'start': time.time()}
    
    for idx, lead in enumerate(leads, 1):
        lead_id, name, website, tier = lead['id'], lead['business_name'], lead['website'], lead['tier']
        
        try:
            import signal
            def timeout_handler(signum, frame):
                raise TimeoutError("Timeout")
            
            old_handler = signal.signal(signal.SIGALRM, timeout_handler)
            signal.alarm(30)
            
            try:
                text, status = scrape_and_extract(website)
            finally:
                signal.alarm(0)
                signal.signal(signal.SIGALRM, old_handler)
            
            if text and len(text) > 100:
                cursor.execute("""
                    UPDATE leads SET website_text = ?, scrape_status = 'scraped', scraped_at = ?
                    WHERE id = ?
                """, (text, datetime.now().isoformat(), lead_id))
                conn.commit()
                stats['success'] += 1
                status_icon = "✅"
            else:
                cursor.execute("UPDATE leads SET scrape_status = 'failed' WHERE id = ?", (lead_id,))
                conn.commit()
                stats['failed'] += 1
                status_icon = "❌"
                
        except Exception as e:
            cursor.execute("UPDATE leads SET scrape_status = 'failed' WHERE id = ?", (lead_id,))
            conn.commit()
            stats['failed'] += 1
            status_icon = "❌"
        
        stats['processed'] += 1
        
        if idx % 50 == 0 or idx <= 10:
            elapsed = time.time() - stats['start']
            rate = stats['processed'] / elapsed * 60 if elapsed > 0 else 0
            remaining = stats['total'] - stats['processed']
            eta = remaining / rate if rate > 0 else 0
            pct = stats['success'] / stats['processed'] * 100
            print(f"[{idx}/{stats['total']}] {tier} | Success: {stats['success']} ({pct:.0f}%) | {rate:.1f}/min | ETA: {eta:.0f}min")
    
    conn.close()
    
    elapsed = time.time() - stats['start']
    print("\n" + "=" * 80)
    print("SCRAPING COMPLETE")
    print("=" * 80)
    print(f"Total: {stats['processed']}")
    print(f"Success: {stats['success']} ({stats['success']/stats['processed']*100:.1f}%)")
    print(f"Failed: {stats['failed']}")
    print(f"Time: {elapsed/60:.1f} minutes")

if __name__ == '__main__':
    scrape_pending()
