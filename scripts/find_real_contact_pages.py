#!/usr/bin/env python3
"""
Find Real Contact Pages

For leads where contact_form_url is a directory site or homepage:
1. Use the actual `website` field
2. Try common paths: /contact, /contact-us, /about, /about-us
3. Verify the page exists and has a contact form
4. Update contact_form_url with the correct URL
"""

import sqlite3
import asyncio
import sys
import os
import httpx
from urllib.parse import urljoin, urlparse
from typing import Optional, List, Tuple
from dataclasses import dataclass

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Common contact page paths to try
CONTACT_PATHS = [
    '/contact',
    '/contact-us',
    '/contact/',
    '/contact-us/',
    '/contactus',
    '/get-in-touch',
    '/reach-us',
    '/connect',
]

# Additional paths that often have contact info
ABOUT_PATHS = [
    '/about',
    '/about-us',
    '/about/',
    '/about-us/',
]

# Form detection keywords in HTML
FORM_INDICATORS = [
    '<form',
    'contact-form',
    'wpcf7',
    'gform',
    'wpforms',
    'email-form',
    'contact_form',
    'formspree',
    'netlify-form',
    'type="email"',
    'name="email"',
    'placeholder="email"',
    'placeholder="your email"',
]


@dataclass 
class ContactPageResult:
    """Result of searching for a contact page."""
    found: bool
    url: Optional[str]
    has_form: bool
    method: str  # 'path_scan', 'homepage_form', 'none'
    error: Optional[str] = None


async def check_url_exists(client: httpx.AsyncClient, url: str) -> Tuple[bool, str]:
    """Check if URL exists and return final URL after redirects."""
    try:
        response = await client.head(url, follow_redirects=True, timeout=10.0)
        if response.status_code == 200:
            return True, str(response.url)
        # Try GET if HEAD fails
        response = await client.get(url, follow_redirects=True, timeout=10.0)
        return response.status_code == 200, str(response.url)
    except Exception as e:
        return False, str(e)


async def check_page_has_form(client: httpx.AsyncClient, url: str) -> Tuple[bool, str]:
    """Check if a page likely contains a contact form."""
    try:
        response = await client.get(url, follow_redirects=True, timeout=15.0)
        if response.status_code != 200:
            return False, ""
        
        html = response.text.lower()
        
        # Check for form indicators
        for indicator in FORM_INDICATORS:
            if indicator.lower() in html:
                return True, str(response.url)
        
        return False, str(response.url)
    except Exception as e:
        return False, ""


async def find_contact_page(client: httpx.AsyncClient, website_url: str) -> ContactPageResult:
    """
    Find the contact page for a website.
    
    Args:
        client: httpx async client
        website_url: Base website URL
    
    Returns:
        ContactPageResult with found URL
    """
    if not website_url:
        return ContactPageResult(False, None, False, 'none', 'No website URL')
    
    # Normalize website URL
    website_url = website_url.strip()
    if not website_url.startswith(('http://', 'https://')):
        website_url = 'https://' + website_url
    
    # Remove query strings and fragments from base URL
    parsed = urlparse(website_url)
    base_url = f"{parsed.scheme}://{parsed.netloc}"
    
    # Try contact paths first
    for path in CONTACT_PATHS:
        test_url = urljoin(base_url, path)
        exists, final_url = await check_url_exists(client, test_url)
        
        if exists:
            has_form, _ = await check_page_has_form(client, final_url)
            if has_form:
                return ContactPageResult(True, final_url, True, 'path_scan')
    
    # Try about paths (sometimes have contact forms)
    for path in ABOUT_PATHS:
        test_url = urljoin(base_url, path)
        has_form, final_url = await check_page_has_form(client, test_url)
        
        if has_form:
            return ContactPageResult(True, final_url, True, 'path_scan')
    
    # Check if homepage itself has a form
    has_form, final_url = await check_page_has_form(client, base_url)
    if has_form:
        return ContactPageResult(True, final_url, True, 'homepage_form')
    
    # No contact page found
    return ContactPageResult(False, None, False, 'none', 'No contact page found')


async def process_leads(db_path: str, dry_run: bool = False, limit: int = None):
    """
    Process all leads with directory/homepage contact URLs.
    
    Args:
        db_path: Path to database
        dry_run: If True, don't update database
        limit: Max leads to process (for testing)
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Get leads that need fixing - ONLY homepage cases where domain is correct
    # Directory cases need a different approach (web search for real site)
    query = """
        SELECT id, business_name, website, contact_form_url, contact_form_type
        FROM leads 
        WHERE contact_form_type = 'homepage'
    """
    
    if limit:
        query += f" LIMIT {limit}"
    
    cursor.execute(query)
    leads = cursor.fetchall()
    
    if not leads:
        print("✅ No leads need contact page discovery!")
        return
    
    print(f"\n🔍 Finding real contact pages for {len(leads)} leads...\n")
    
    stats = {
        'processed': 0,
        'found': 0,
        'not_found': 0,
        'errors': 0,
    }
    
    updates = []
    
    # Use async HTTP client
    async with httpx.AsyncClient(
        headers={
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        },
        verify=False,  # Some nursery sites have bad SSL
        timeout=20.0
    ) as client:
        
        for lead in leads:
            stats['processed'] += 1
            business_name = lead['business_name']
            website = lead['website']
            old_url = lead['contact_form_url']
            form_type = lead['contact_form_type']
            
            print(f"[{stats['processed']}/{len(leads)}] {business_name[:40]:<40}", end=' ')
            
            if not website or website.strip() == '':
                print("⚠️  No website URL")
                stats['not_found'] += 1
                continue
            
            result = await find_contact_page(client, website)
            
            if result.found and result.url:
                print(f"✅ Found: {result.url[:50]}")
                stats['found'] += 1
                
                updates.append((
                    result.url,
                    True,  # verified
                    'direct',  # type
                    lead['id']
                ))
            else:
                reason = result.error or 'No contact page'
                print(f"❌ {reason}")
                stats['not_found'] += 1
            
            # Small delay to be nice
            await asyncio.sleep(0.3)
    
    # Update database
    if updates and not dry_run:
        print(f"\n💾 Updating {len(updates)} records...")
        
        cursor.executemany("""
            UPDATE leads 
            SET contact_form_url = ?,
                contact_form_verified = ?,
                contact_form_type = ?
            WHERE id = ?
        """, updates)
        
        conn.commit()
        print("✅ Database updated")
    elif dry_run:
        print(f"\n🔍 DRY RUN - would update {len(updates)} records")
    
    conn.close()
    
    # Print summary
    print("\n" + "="*60)
    print("📊 CONTACT PAGE DISCOVERY SUMMARY")
    print("="*60)
    print(f"Total processed: {stats['processed']}")
    print(f"✅ Found contact pages: {stats['found']} ({stats['found']/stats['processed']*100:.1f}%)")
    print(f"❌ Not found: {stats['not_found']}")
    print(f"🔧 Errors: {stats['errors']}")


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Find real contact pages')
    parser.add_argument('--dry-run', action='store_true', help='Do not update database')
    parser.add_argument('--limit', type=int, help='Max leads to process')
    parser.add_argument('--db', default='data/leads.db', help='Path to database')
    
    args = parser.parse_args()
    
    db_path = args.db
    if not os.path.isabs(db_path):
        db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), db_path)
    
    if not os.path.exists(db_path):
        print(f"❌ Database not found: {db_path}")
        sys.exit(1)
    
    asyncio.run(process_leads(db_path, dry_run=args.dry_run, limit=args.limit))


if __name__ == "__main__":
    main()
