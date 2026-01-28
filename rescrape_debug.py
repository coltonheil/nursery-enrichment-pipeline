#!/usr/bin/env python3
"""Debug version - processes 10 leads with verbose output"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

import sqlite3
from enrichment.web_scraper import scrape_and_extract
from datetime import datetime

print("Starting debug rescrape script...", flush=True)

conn = sqlite3.connect('data/leads.db')
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

print("Querying for leads...", flush=True)
cursor.execute("""
    SELECT id, business_name, website, LENGTH(website_text) as old_len
    FROM leads
    WHERE tier IN ('A', 'B')
        AND website IS NOT NULL
        AND (website_text IS NULL OR LENGTH(website_text) < 2000)
    LIMIT 10
""")

leads = [dict(row) for row in cursor.fetchall()]
cursor.close()

print(f"Found {len(leads)} leads to process", flush=True)

for i, lead in enumerate(leads, 1):
    print(f"\n[{i}/10] Processing: {lead['business_name']}", flush=True)
    print(f"  Website: {lead['website']}", flush=True)
    
    try:
        text, info = scrape_and_extract(lead['website'])
        print(f"  ✅ Scraped: {len(text)} chars, {info['pages_scraped']} pages", flush=True)
        
        # Update database
        conn = sqlite3.connect('data/leads.db')
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE leads
            SET website_text = ?, scrape_status = 'rescraped', scraped_at = ?
            WHERE id = ?
        ''', (text, datetime.now().isoformat(), lead['id']))
        conn.commit()
        conn.close()
        print(f"  💾 Database updated", flush=True)
        
    except Exception as e:
        print(f"  ❌ Error: {str(e)[:80]}", flush=True)

print(f"\n✅ Complete!", flush=True)
