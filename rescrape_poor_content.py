#!/usr/bin/env python3
"""
Re-scrape only leads with genuinely poor content (<2000 chars).
Excludes leads that just have missing owner_name (AI enrichment issue, not scraping).
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

import sqlite3
from enrichment.web_scraper import scrape_and_extract
import time
from datetime import datetime

def rescrape_poor_content_leads(limit=650):
    """Re-scrape leads with poor content only."""
    
    conn = sqlite3.connect('data/leads.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Get leads with actually poor content (not just missing owner_name)
    cursor.execute("""
        SELECT 
            id, business_name, website, tier, score,
            LENGTH(website_text) as old_text_len
        FROM leads
        WHERE tier IN ('A', 'B')
            AND website IS NOT NULL
            AND (
                website_text IS NULL 
                OR LENGTH(website_text) < 2000
            )
        ORDER BY tier ASC, score DESC
        LIMIT ?
    """, (limit,))
    
    leads = [dict(row) for row in cursor.fetchall()]
    cursor.close()
    
    if not leads:
        print("✅ No leads with poor content need re-scraping")
        return {'processed': 0, 'reason': 'no_leads'}
    
    print("╔" + "="*68 + "╗")
    print("║" + " "*10 + "RE-SCRAPING POOR CONTENT LEADS" + " "*28 + "║")
    print("╚" + "="*68 + "╝")
    print()
    print(f"Re-scraping {len(leads)} Tier A+B leads with <2000 chars content")
    print(f"Will report every 25 leads")
    print("="*70)
    
    stats = {
        'processed': 0,
        'improved': 0,
        'team_pages_found': 0,
        'failed': 0,
        'total_pages_before': 0,
        'total_pages_after': 0,
        'total_chars_before': 0,
        'total_chars_after': 0
    }
    
    start_time = time.time()
    
    for i, lead in enumerate(leads, 1):
        old_len = lead.get('old_text_len', 0) or 0
        stats['total_chars_before'] += old_len
        
        try:
            # Scrape with enhanced scraper
            new_text, status_info = scrape_and_extract(lead['website'])
            
            new_len = len(new_text)
            new_pages = status_info.get('pages_scraped', 0)
            
            stats['total_chars_after'] += new_len
            stats['total_pages_after'] += new_pages
            
            # Check if team page was found
            has_team = any(kw in new_text.lower() for kw in ['[team', '[our-team', '[staff', '[people'])
            if has_team:
                stats['team_pages_found'] += 1
            
            # Update database
            conn = sqlite3.connect('data/leads.db')
            cursor = conn.cursor()
            
            cursor.execute('''
                UPDATE leads
                SET website_text = ?,
                    scrape_status = 'rescraped',
                    scraped_at = ?
                WHERE id = ?
            ''', (new_text, datetime.now().isoformat(), lead['id']))
            
            conn.commit()
            conn.close()
            
            # Track improvement
            if new_len > old_len * 1.3:  # 30% more content
                stats['improved'] += 1
            
            stats['processed'] += 1
            
            # Report every 25 leads
            if i % 25 == 0:
                elapsed = time.time() - start_time
                speed = i / elapsed * 60  # leads per minute
                eta = (len(leads) - i) / speed if speed > 0 else 0
                
                avg_pages = stats['total_pages_after'] / i if i > 0 else 0
                improvement_rate = stats['improved'] / i * 100 if i > 0 else 0
                
                print(f"\n[{i}/{len(leads)}] Progress Report", flush=True)
                print(f"  Processed: {stats['processed']}", flush=True)
                print(f"  Improved: {stats['improved']} ({improvement_rate:.0f}%)", flush=True)
                print(f"  Team pages: {stats['team_pages_found']}", flush=True)
                print(f"  Avg pages/lead: {avg_pages:.1f}", flush=True)
                print(f"  Speed: {speed:.1f} leads/min", flush=True)
                print(f"  ETA: {int(eta)}m", flush=True)
            
            # Small delay to avoid overwhelming servers
            time.sleep(0.5)
            
        except Exception as e:
            stats['failed'] += 1
            print(f"[{i}/{len(leads)}] ❌ {lead['business_name'][:40]}: {str(e)[:50]}", flush=True)
            time.sleep(1)
    
    # Final summary
    elapsed = time.time() - start_time
    
    print()
    print("="*70)
    print("RE-SCRAPING COMPLETE")
    print("="*70)
    print(f"Total processed: {stats['processed']}/{len(leads)}")
    print(f"Improved: {stats['improved']} ({stats['improved']/stats['processed']*100:.0f}%)")
    print(f"Failed: {stats['failed']}")
    print()
    print(f"Team pages found: {stats['team_pages_found']} ({stats['team_pages_found']/stats['processed']*100:.0f}%)")
    print()
    print(f"Average pages per lead: {stats['total_pages_after']/stats['processed']:.1f}")
    print()
    print(f"Average content per lead:")
    print(f"  Before: {stats['total_chars_before']/stats['processed']:,.0f} chars")
    print(f"  After: {stats['total_chars_after']/stats['processed']:,.0f} chars")
    improvement = ((stats['total_chars_after'] - stats['total_chars_before']) / stats['total_chars_before'] * 100) if stats['total_chars_before'] > 0 else 100
    print(f"  Improvement: +{improvement:.0f}%")
    print()
    print(f"Time: {int(elapsed/60)}m {int(elapsed%60)}s")
    print(f"Speed: {stats['processed']/(elapsed/60):.1f} leads/min")
    print("="*70)
    
    return stats

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--limit', type=int, default=650, help='Max leads to process')
    args = parser.parse_args()
    
    stats = rescrape_poor_content_leads(args.limit)
    print(f"\n✅ Rescrape completed: {stats['processed']} leads processed", flush=True)
