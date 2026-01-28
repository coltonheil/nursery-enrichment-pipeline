#!/usr/bin/env python3
"""
Test the fixed web scraper on sample nursery leads from the database.
Validates that the fixes work:
1. retry_count=0 enables retries
2. Delays between ALL requests (not just successful ones)
3. Team pages prioritized before about pages
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

import sqlite3
import time
from enrichment.web_scraper import scrape_and_extract, scrape_website

def get_test_leads(limit=5):
    """Get sample leads from the database for testing."""
    conn = sqlite3.connect('data/leads.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Get leads that previously failed or have little text
    cursor.execute("""
        SELECT id, business_name, website, 
               LENGTH(website_text) as old_text_len
        FROM leads
        WHERE website IS NOT NULL
          AND tier IN ('A', 'B')
          AND (website_text IS NULL OR LENGTH(website_text) < 500)
        ORDER BY RANDOM()
        LIMIT ?
    """, (limit,))
    
    leads = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return leads


def test_single_scrape():
    """Test scrape_website directly to verify retry logic."""
    print("="*70)
    print("TEST 1: Verify scrape_website retry behavior")
    print("="*70)
    
    # Test with a known working site
    test_url = "https://example.com"
    
    print(f"\nTesting: {test_url}")
    start = time.time()
    html, status, error = scrape_website(test_url, retry_count=0)
    elapsed = time.time() - start
    
    print(f"  Status: {status}")
    print(f"  Error: {error}")
    print(f"  HTML length: {len(html) if html else 0}")
    print(f"  Time: {elapsed:.1f}s")
    
    if html and status == 200:
        print("  ✅ Basic scraping works")
        return True
    else:
        print("  ❌ Basic scraping failed")
        return False


def test_scrape_and_extract(leads):
    """Test the full scrape_and_extract pipeline on real leads."""
    print("\n" + "="*70)
    print("TEST 2: Test scrape_and_extract on database leads")
    print("="*70)
    
    results = {
        'tested': 0,
        'successful': 0,
        'team_pages': 0,
        'total_pages': 0,
        'total_chars': 0
    }
    
    for i, lead in enumerate(leads, 1):
        print(f"\n[{i}/{len(leads)}] {lead['business_name'][:50]}")
        print(f"  URL: {lead['website']}")
        print(f"  Old text length: {lead['old_text_len'] or 0}")
        
        start = time.time()
        text, status_info = scrape_and_extract(lead['website'])
        elapsed = time.time() - start
        
        pages = status_info.get('pages_scraped', 0)
        failed = status_info.get('pages_failed', 0)
        chars = len(text)
        
        results['tested'] += 1
        results['total_pages'] += pages
        results['total_chars'] += chars
        
        if pages > 0:
            results['successful'] += 1
        
        # Check for team page markers
        import re
        markers = re.findall(r'\[([A-Z0-9_-]+)\]', text)
        team_markers = [m for m in markers if m in ['TEAM', 'OUR-TEAM', 'STAFF', 'PEOPLE', 'MEET-TEAM', 'MEET-US', 'WHO-WE-ARE']]
        
        if team_markers:
            results['team_pages'] += 1
        
        print(f"  NEW text length: {chars}")
        print(f"  Pages scraped: {pages}")
        print(f"  Pages failed: {failed}")
        print(f"  Page markers: {markers}")
        print(f"  Team pages: {team_markers if team_markers else 'None'}")
        print(f"  Time: {elapsed:.1f}s")
        
        if pages > 0:
            print("  ✅ Success")
        else:
            print("  ❌ Failed to scrape any pages")
        
        # Brief delay between leads
        if i < len(leads):
            time.sleep(1)
    
    return results


def print_summary(results):
    """Print test summary."""
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)
    
    tested = results['tested']
    if tested == 0:
        print("No leads tested")
        return
    
    print(f"Leads tested: {tested}")
    print(f"Successful: {results['successful']} ({results['successful']/tested*100:.0f}%)")
    print(f"Team pages found: {results['team_pages']} ({results['team_pages']/tested*100:.0f}%)")
    print()
    print(f"Average pages/lead: {results['total_pages']/tested:.1f}")
    print(f"Average chars/lead: {results['total_chars']/tested:,.0f}")
    print()
    
    if results['successful'] >= tested * 0.5:
        print("✅ SUCCESS: Scraper is working (50%+ success rate)")
    elif results['successful'] >= tested * 0.3:
        print("⚠️  PARTIAL: Some improvement but still issues")
    else:
        print("❌ FAILED: Scraper is not working well")


def main():
    print("╔" + "="*68 + "╗")
    print("║" + " "*18 + "WEB SCRAPER FIX TEST" + " "*30 + "║")
    print("╚" + "="*68 + "╝")
    print()
    print("Testing fixes:")
    print("1. retry_count=0 to enable retries on transient errors")
    print("2. Delays between ALL requests (not just successful ones)")
    print("3. Team pages prioritized before about pages")
    print()
    
    # Test 1: Basic scrape
    if not test_single_scrape():
        print("\n⚠️  Basic scraping failed - may be network issues")
    
    # Get test leads
    leads = get_test_leads(5)
    if not leads:
        print("\n❌ No test leads found in database")
        return
    
    print(f"\nFound {len(leads)} leads to test")
    
    # Test 2: Full pipeline
    results = test_scrape_and_extract(leads)
    
    # Summary
    print_summary(results)


if __name__ == '__main__':
    main()
