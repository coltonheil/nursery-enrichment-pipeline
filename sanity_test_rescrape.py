#!/usr/bin/env python3
"""
Sanity test: Re-scrape 5 high-value leads to validate scraper fixes.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

import sqlite3
from enrichment.web_scraper import scrape_and_extract
import time
from datetime import datetime

def sanity_test(num_leads=5):
    """Test the fixed scraper on a small sample."""
    
    conn = sqlite3.connect('data/leads.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Get a sample of Tier A+B leads
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
        ORDER BY RANDOM()
        LIMIT ?
    """, (num_leads,))
    
    leads = [dict(row) for row in cursor.fetchall()]
    cursor.close()
    
    if not leads:
        print("✅ No leads found for testing")
        return {'success': True, 'reason': 'no_leads_needed'}
    
    print("╔" + "="*78 + "╗")
    print("║" + " "*25 + "SANITY TEST - SCRAPER FIX" + " "*28 + "║")
    print("╚" + "="*78 + "╝")
    print()
    print(f"Testing {len(leads)} random Tier A+B leads with fixed scraper")
    print("="*80)
    
    results = []
    
    for i, lead in enumerate(leads, 1):
        old_len = lead.get('old_text_len', 0) or 0
        
        print(f"\n[{i}/{len(leads)}] {lead['business_name'][:50]}")
        print(f"  Website: {lead['website']}")
        print(f"  Old content: {old_len:,} chars")
        
        try:
            start = time.time()
            new_text, status_info = scrape_and_extract(lead['website'])
            elapsed = time.time() - start
            
            new_len = len(new_text)
            new_pages = status_info.get('pages_scraped', 0)
            
            # Check for team pages
            has_team = any(kw in new_text.lower() for kw in ['[team', '[our-team', '[staff', '[people'])
            
            result = {
                'id': lead['id'],
                'business_name': lead['business_name'],
                'website': lead['website'],
                'old_len': old_len,
                'new_len': new_len,
                'pages_scraped': new_pages,
                'has_team': has_team,
                'elapsed': elapsed,
                'success': new_len > 100,  # At least some content
                'improved': new_len > old_len * 1.3  # 30% improvement
            }
            results.append(result)
            
            print(f"  ✅ SUCCESS")
            print(f"  New content: {new_len:,} chars ({new_pages} pages)")
            if has_team:
                print(f"  🎯 Team page found!")
            print(f"  Time: {elapsed:.1f}s")
            
            if new_len > old_len * 1.3:
                improvement = ((new_len - old_len) / old_len * 100) if old_len > 0 else 100
                print(f"  📈 Improved by {improvement:.0f}%")
            
            time.sleep(1)  # Small delay between tests
            
        except Exception as e:
            print(f"  ❌ FAILED: {str(e)[:70]}")
            results.append({
                'id': lead['id'],
                'business_name': lead['business_name'],
                'website': lead['website'],
                'old_len': old_len,
                'new_len': 0,
                'pages_scraped': 0,
                'has_team': False,
                'elapsed': 0,
                'success': False,
                'improved': False,
                'error': str(e)[:100]
            })
    
    # Summary
    print("\n" + "="*80)
    print("SANITY TEST RESULTS")
    print("="*80)
    
    successes = sum(1 for r in results if r['success'])
    improvements = sum(1 for r in results if r.get('improved', False))
    team_pages = sum(1 for r in results if r.get('has_team', False))
    
    total_old = sum(r['old_len'] for r in results)
    total_new = sum(r['new_len'] for r in results)
    total_pages = sum(r['pages_scraped'] for r in results)
    
    avg_old = total_old / len(results) if results else 0
    avg_new = total_new / len(results) if results else 0
    avg_pages = total_pages / len(results) if results else 0
    
    print(f"\nSuccess rate: {successes}/{len(results)} ({successes/len(results)*100:.0f}%)")
    print(f"Improved: {improvements}/{len(results)} ({improvements/len(results)*100:.0f}%)")
    print(f"Team pages found: {team_pages}/{len(results)} ({team_pages/len(results)*100:.0f}%)")
    print()
    print(f"Average pages scraped: {avg_pages:.1f}")
    print(f"Average content:")
    print(f"  Before: {avg_old:,.0f} chars")
    print(f"  After: {avg_new:,.0f} chars")
    
    if avg_old > 0:
        improvement_pct = ((avg_new - avg_old) / avg_old * 100)
        print(f"  Improvement: {improvement_pct:+.0f}%")
    
    print("\n" + "="*80)
    
    # Determine if we should proceed with full rescrape
    success_rate = successes / len(results) if results else 0
    
    if success_rate >= 0.6:  # At least 60% success
        print("✅ SANITY TEST PASSED - Proceeding with full rescrape recommended")
        return {'success': True, 'success_rate': success_rate, 'results': results}
    else:
        print("❌ SANITY TEST FAILED - Fix issues before full rescrape")
        return {'success': False, 'success_rate': success_rate, 'results': results}

if __name__ == '__main__':
    result = sanity_test()
    sys.exit(0 if result['success'] else 1)
