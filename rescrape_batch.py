#!/usr/bin/env python3
"""Batch rescrape high-value leads with the fixed scraper."""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))
sys.stdout.reconfigure(line_buffering=True)

import sqlite3
from enrichment.web_scraper import scrape_and_extract
from datetime import datetime
import time

print(f"[{datetime.now().strftime('%H:%M:%S')}] Starting batch rescrape...")

conn = sqlite3.connect('data/leads.db')
conn.row_factory = sqlite3.Row

# Get high-value leads with bad/missing website text
cursor = conn.cursor()
cursor.execute("""
    SELECT id, business_name, website, LENGTH(website_text) as old_len
    FROM leads
    WHERE tier IN ('A', 'B')
        AND website IS NOT NULL
        AND (website_text IS NULL OR LENGTH(website_text) < 2000)
    ORDER BY tier, old_len ASC
""")
leads = [dict(row) for row in cursor.fetchall()]
cursor.close()

total = len(leads)
print(f"[{datetime.now().strftime('%H:%M:%S')}] Found {total} leads to rescrape")

success = 0
failed = 0
improved = 0

for i, lead in enumerate(leads, 1):
    if i % 25 == 1 or i == 1:
        print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Progress: {i-1}/{total} ({success} success, {failed} failed)")
    
    try:
        text, info = scrape_and_extract(lead['website'])
        
        if len(text) > 0:
            success += 1
            if lead['old_len'] is None or len(text) > lead['old_len']:
                improved += 1
            
            # Update database
            update_conn = sqlite3.connect('data/leads.db')
            update_cursor = update_conn.cursor()
            update_cursor.execute('''
                UPDATE leads
                SET website_text = ?, scrape_status = 'rescraped', scraped_at = ?
                WHERE id = ?
            ''', (text, datetime.now().isoformat(), lead['id']))
            update_conn.commit()
            update_conn.close()
        else:
            failed += 1
            
    except Exception as e:
        failed += 1
        print(f"  ❌ {lead['business_name'][:30]}: {str(e)[:50]}")
    
    # Rate limiting
    time.sleep(0.5)

print(f"\n{'='*60}")
print(f"[{datetime.now().strftime('%H:%M:%S')}] RESCRAPE COMPLETE")
print(f"  Total processed: {total}")
print(f"  Success: {success} ({100*success//total}%)")
print(f"  Failed: {failed} ({100*failed//total}%)")
print(f"  Improved: {improved}")
print(f"{'='*60}")
