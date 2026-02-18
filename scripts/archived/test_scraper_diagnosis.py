#!/usr/bin/env python3
"""
Diagnostic test for web scraper issues.
Tests 5 sample nursery sites with verbose logging.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

import requests
import random
import time
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup

# Sample nursery sites to test (real public sites)
TEST_SITES = [
    "https://www.naturehillsnursery.com",
    "https://www.springhillnursery.com",
    "https://www.monrovia.com",
    "https://www.highcountrygarden.com",
    "https://www.forestfarm.com"
]

USER_AGENTS = [
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
]

def test_single_page(url, page_name="page"):
    """Test scraping a single page with verbose output."""
    print(f"\n  [{page_name}] {url}")
    
    headers = {
        'User-Agent': random.choice(USER_AGENTS),
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
    }
    
    try:
        start = time.time()
        response = requests.get(url, headers=headers, timeout=15, verify=False, allow_redirects=True)
        elapsed = time.time() - start
        
        if response.status_code == 200:
            content_len = len(response.content)
            soup = BeautifulSoup(response.content, 'html.parser')
            text_len = len(soup.get_text())
            print(f"       ✅ 200 OK | {content_len:,} bytes | {text_len:,} text chars | {elapsed:.1f}s")
            return True, text_len
        elif response.status_code == 404:
            print(f"       ⚪ 404 Not Found | {elapsed:.1f}s")
            return False, 0
        else:
            print(f"       ⚠️  HTTP {response.status_code} | {elapsed:.1f}s")
            return False, 0
            
    except requests.exceptions.Timeout:
        print(f"       ❌ TIMEOUT (15s)")
        return False, 0
    except requests.exceptions.SSLError as e:
        print(f"       ❌ SSL ERROR: {str(e)[:80]}")
        return False, 0
    except requests.exceptions.ConnectionError as e:
        print(f"       ❌ CONNECTION ERROR: {str(e)[:80]}")
        return False, 0
    except Exception as e:
        print(f"       ❌ ERROR: {str(e)[:80]}")
        return False, 0


def test_site_with_subpages(base_url):
    """Test a site's homepage + subpages."""
    parsed = urlparse(base_url)
    domain = f"{parsed.scheme}://{parsed.netloc}"
    
    print(f"\n{'='*70}")
    print(f"TESTING: {base_url}")
    print(f"{'='*70}")
    
    # Pages to try
    subpages = [
        ("", "homepage"),
        ("/about", "about"),
        ("/about-us", "about-us"),
        ("/team", "team"),
        ("/our-team", "our-team"),
        ("/staff", "staff"),
        ("/contact", "contact"),
        ("/contact-us", "contact-us"),
    ]
    
    success_count = 0
    total_text = 0
    
    for path, name in subpages:
        url = urljoin(domain, path) if path else base_url
        success, text_len = test_single_page(url, name)
        if success:
            success_count += 1
            total_text += text_len
        time.sleep(0.5)  # Small delay between requests
    
    print(f"\n  SUMMARY: {success_count}/{len(subpages)} pages found, {total_text:,} total chars")
    return success_count, total_text


def test_current_scraper():
    """Test current scraper implementation to see the bug."""
    from enrichment.web_scraper import scrape_and_extract
    
    print("\n" + "="*70)
    print("TESTING CURRENT SCRAPER IMPLEMENTATION")
    print("="*70)
    
    for site in TEST_SITES[:3]:
        print(f"\n>>> Testing: {site}")
        
        start = time.time()
        text, status = scrape_and_extract(site)
        elapsed = time.time() - start
        
        pages = status.get('pages_scraped', 0)
        failed = status.get('pages_failed', 0)
        total_chars = len(text)
        
        print(f"    Pages scraped: {pages}")
        print(f"    Pages failed: {failed}")
        print(f"    Total chars: {total_chars:,}")
        print(f"    Time: {elapsed:.1f}s")
        
        # Check for team content
        has_team = any(marker in text.lower() for marker in ['[team]', '[our-team]', '[staff]'])
        print(f"    Has team page: {'✅ Yes' if has_team else '❌ No'}")
        
        # Show page markers found
        import re
        markers = re.findall(r'\[([\w-]+)\]', text)
        if markers:
            print(f"    Pages found: {markers}")
        
        time.sleep(1)


def main():
    print("╔" + "="*68 + "╗")
    print("║" + " "*18 + "SCRAPER DIAGNOSTIC TEST" + " "*27 + "║")
    print("╚" + "="*68 + "╝")
    
    # Part 1: Direct HTTP tests (bypass our scraper)
    print("\n" + "="*70)
    print("PART 1: DIRECT HTTP TESTS (validating sites are reachable)")
    print("="*70)
    
    total_success = 0
    total_pages = 0
    total_text = 0
    
    for site in TEST_SITES[:3]:  # Test first 3 sites
        success, text = test_site_with_subpages(site)
        total_success += success
        total_pages += 8  # 8 subpages per site
        total_text += text
    
    print("\n" + "="*70)
    print("DIRECT HTTP SUMMARY")
    print("="*70)
    print(f"Total pages tested: {total_pages}")
    print(f"Successful pages: {total_success} ({total_success/total_pages*100:.0f}%)")
    print(f"Average pages/site: {total_success/3:.1f}")
    
    # Part 2: Test current scraper
    test_current_scraper()


if __name__ == '__main__':
    main()
