#!/usr/bin/env python3
"""
Test enhanced web scraper on sample leads.
Compare before/after to validate improvement.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

import sqlite3
from enrichment.web_scraper import scrape_and_extract
import time

def test_enhanced_scraper():
    """Test enhanced scraper on 5 Tier A/B leads."""
    
    conn = sqlite3.connect('data/leads.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Get 5 Tier A/B leads with websites but no owner name
    cursor.execute("""
        SELECT 
            id, business_name, website, 
            owner_name, 
            LENGTH(website_text) as old_text_len,
            website_text
        FROM leads
        WHERE tier IN ('A', 'B')
            AND website IS NOT NULL
            AND (owner_name IS NULL OR owner_name = '')
        ORDER BY tier ASC, score DESC
        LIMIT 5
    """)
    
    leads = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    if not leads:
        print("❌ No suitable test leads found")
        return
    
    print("╔" + "="*68 + "╗")
    print("║" + " "*15 + "ENHANCED SCRAPER TEST" + " "*32 + "║")
    print("╚" + "="*68 + "╝")
    print()
    print(f"Testing on {len(leads)} Tier A/B leads")
    print("Comparing OLD data vs NEW scraping")
    print("="*70)
    
    results = {
        'tested': 0,
        'improved': 0,
        'team_pages_found': 0,
        'contact_mentions_found': 0,
        'total_pages_before': 0,
        'total_pages_after': 0
    }
    
    for i, lead in enumerate(leads, 1):
        print(f"\n[{i}/5] {lead['business_name'][:50]}")
        print(f"  Website: {lead['website']}")
        
        # Check OLD data
        old_text = lead.get('website_text', '')
        old_len = len(old_text) if old_text else 0
        old_has_team = any(keyword in old_text.lower() for keyword in ['[team', 'meet our team', 'our staff']) if old_text else False
        old_has_names = any(keyword in old_text.lower() for keyword in ['owner:', 'founder:', 'manager:']) if old_text else False
        
        # Count pages in old data (rough estimate)
        old_page_count = old_text.count('[') if old_text else 1
        results['total_pages_before'] += old_page_count
        
        print(f"  OLD: {old_len:,} chars, {old_page_count} pages")
        if old_has_team:
            print(f"       ✓ Had team page indicators")
        if old_has_names:
            print(f"       ✓ Had name mentions")
        
        # Scrape with ENHANCED scraper
        try:
            new_text, status_info = scrape_and_extract(lead['website'])
            
            new_len = len(new_text)
            new_pages = status_info.get('pages_scraped', 0)
            results['total_pages_after'] += new_pages
            
            # Check NEW data
            new_has_team = any(keyword in new_text.lower() for keyword in ['[team', '[our-team', '[staff', '[people', 'meet the team', 'our team'])
            new_has_names = any(keyword in new_text.lower() for keyword in ['owner:', 'founder:', 'manager:', 'grower:', 'president:'])
            
            print(f"  NEW: {new_len:,} chars, {new_pages} pages scraped")
            
            improvement = False
            if new_has_team and not old_has_team:
                print(f"       ✅ NEW: Found team page!")
                results['team_pages_found'] += 1
                improvement = True
            
            if new_has_names and not old_has_names:
                print(f"       ✅ NEW: Found contact mentions!")
                results['contact_mentions_found'] += 1
                improvement = True
            
            if new_len > old_len * 1.5:
                print(f"       ✅ NEW: {((new_len/max(old_len,1))-1)*100:.0f}% more content")
                improvement = True
            
            if new_pages > old_page_count:
                print(f"       ✅ NEW: {new_pages - old_page_count} more pages")
                improvement = True
            
            if improvement:
                results['improved'] += 1
                
                # Show sample of new content if team page found
                if new_has_team:
                    team_section = new_text.lower()
                    team_idx = team_section.find('[team')
                    if team_idx == -1:
                        team_idx = team_section.find('[our-team')
                    if team_idx == -1:
                        team_idx = team_section.find('[staff')
                    
                    if team_idx >= 0:
                        snippet = new_text[team_idx:team_idx+200]
                        print(f"       Sample: {snippet[:100]}...")
            else:
                print(f"       ⚠️  No significant improvement")
            
            results['tested'] += 1
            
            # Small delay between requests
            if i < len(leads):
                time.sleep(2)
        
        except Exception as e:
            print(f"       ❌ Error: {str(e)[:100]}")
    
    # Summary
    print()
    print("="*70)
    print("TEST SUMMARY")
    print("="*70)
    print(f"Leads tested: {results['tested']}/5")
    print(f"Leads improved: {results['improved']}/5 ({results['improved']/max(results['tested'],1)*100:.0f}%)")
    print()
    print(f"NEW team pages found: {results['team_pages_found']}")
    print(f"NEW contact mentions: {results['contact_mentions_found']}")
    print()
    print(f"Average pages/lead:")
    print(f"  BEFORE: {results['total_pages_before']/max(results['tested'],1):.1f}")
    print(f"  AFTER:  {results['total_pages_after']/max(results['tested'],1):.1f}")
    print("="*70)
    
    if results['improved'] >= 3:
        print("\n✅ SUCCESS: Enhanced scraper is working!")
        print("   Ready to re-scrape full batch")
    elif results['improved'] >= 2:
        print("\n⚠️  PARTIAL: Some improvement, but not as much as expected")
        print("   May still be worth running on full batch")
    else:
        print("\n❌ INSUFFICIENT: Enhancement not working as expected")
        print("   Need to review scraper logic")

if __name__ == '__main__':
    test_enhanced_scraper()
