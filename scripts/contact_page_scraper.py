#!/usr/bin/env python3
"""
Email Discovery Script - Phase B
Scrapes contact/about pages to find emails
"""

import sqlite3
import re
import os
import time
import requests
from urllib.parse import urljoin, urlparse
from datetime import datetime
from bs4 import BeautifulSoup

# Email regex pattern
EMAIL_PATTERN = re.compile(
    r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
)

# Common generic emails to deprioritize
GENERIC_PREFIXES = {'info', 'contact', 'sales', 'support', 'hello', 'admin', 'webmaster', 'office', 'mail', 'general', 'enquiries', 'inquiries'}

# Emails to skip
SKIP_PATTERNS = {'noreply', 'no-reply', 'donotreply', 'example.com', 'test.com', '.png', '.jpg', '.jpeg', '.gif', '.svg', 'wix.com', 'sentry.io', 'wixpress.com', 'sentry', 'wordpress.com', 'squarespace', 'godaddy', 'domain.com', 'yourdomain', 'yoursite', 'email@', 'xxx@xxx', 'mysite.com', '@example', 'placeholder', 'sample@', 'your-email', 'name@domain'}

# Contact page paths to try
CONTACT_PATHS = [
    '/contact',
    '/contact-us',
    '/contactus',
    '/about',
    '/about-us',
    '/aboutus',
    '/team',
    '/our-team',
    '/staff',
    '/connect',
]

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
}

def extract_emails_from_html(html):
    """Extract emails from HTML content."""
    if not html:
        return []
    
    # Search raw HTML for emails first (catches mailto links and inline)
    raw_html = html.lower()
    
    # Also check href attributes for mailto links
    mailto_emails = re.findall(r'mailto:([a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,})', raw_html)
    
    # Find all emails in raw HTML
    raw_emails = EMAIL_PATTERN.findall(raw_html)
    
    # Combine and filter
    all_emails = set(mailto_emails + raw_emails)
    
    valid_emails = []
    for email in all_emails:
        # Skip bad patterns
        if any(skip in email for skip in SKIP_PATTERNS):
            continue
        valid_emails.append(email)
    
    return list(valid_emails)

def fetch_page(url, timeout=10):
    """Fetch a page and return HTML content."""
    try:
        response = requests.get(url, headers=HEADERS, timeout=timeout, allow_redirects=True)
        if response.status_code == 200:
            return response.text
    except Exception as e:
        pass
    return None

def scrape_contact_pages(website):
    """Scrape contact pages for a website and return found emails."""
    if not website:
        return [], None
    
    # Normalize URL
    if not website.startswith(('http://', 'https://')):
        website = 'http://' + website
    
    # Parse base URL
    parsed = urlparse(website)
    base_url = f"{parsed.scheme}://{parsed.netloc}"
    
    all_emails = set()
    source_pages = []
    
    # First try the main page
    html = fetch_page(website)
    if html:
        emails = extract_emails_from_html(html)
        if emails:
            all_emails.update(emails)
            source_pages.append(website)
    
    # Try contact pages
    for path in CONTACT_PATHS:
        if len(all_emails) >= 3:  # Stop if we have enough
            break
        
        url = urljoin(base_url, path)
        time.sleep(0.3)  # Rate limit
        
        html = fetch_page(url)
        if html:
            emails = extract_emails_from_html(html)
            if emails:
                all_emails.update(emails)
                source_pages.append(url)
    
    return list(all_emails), source_pages[0] if source_pages else None

def classify_and_prioritize(emails):
    """Classify emails and return best owner_email and contact_email."""
    if not emails:
        return None, None
    
    personal = []
    generic = []
    
    for email in emails:
        prefix = email.split('@')[0]
        if any(prefix.startswith(g) for g in GENERIC_PREFIXES):
            generic.append(email)
        else:
            personal.append(email)
    
    owner_email = personal[0] if personal else None
    contact_email = generic[0] if generic else (personal[1] if len(personal) > 1 else None)
    
    return owner_email, contact_email

def process_batch(batch_size=50, dry_run=False):
    """Process a batch of leads by scraping their contact pages."""
    conn = sqlite3.connect('data/leads.db')
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    # Get candidates with website but no email
    c.execute('''
        SELECT id, business_name, website
        FROM leads
        WHERE tier IN ('A', 'B')
        AND website IS NOT NULL AND website != ''
        AND (owner_email IS NULL OR owner_email = '')
        LIMIT ?
    ''', (batch_size,))
    
    leads = c.fetchall()
    
    results = {
        'processed': 0,
        'emails_found': 0,
        'owner_emails': 0,
        'contact_emails': 0,
        'scrape_failures': 0,
        'no_email': 0,
        'examples': []
    }
    
    for i, lead in enumerate(leads):
        results['processed'] += 1
        
        import sys
        print(f"  [{i+1}/{len(leads)}] {lead['business_name'][:40]}...", end=' ', flush=True)
        
        emails, source = scrape_contact_pages(lead['website'])
        owner_email, contact_email = classify_and_prioritize(emails)
        
        if owner_email or contact_email:
            results['emails_found'] += 1
            if owner_email:
                results['owner_emails'] += 1
            if contact_email:
                results['contact_emails'] += 1
            
            print(f"✓ {owner_email or contact_email}")
            
            if len(results['examples']) < 10:
                results['examples'].append({
                    'business': lead['business_name'],
                    'owner_email': owner_email,
                    'contact_email': contact_email,
                    'source': source
                })
            
            if not dry_run:
                c.execute('''
                    UPDATE leads SET
                        owner_email = COALESCE(?, owner_email),
                        contact_email = COALESCE(?, contact_email),
                        email_method = 'contact_page_scrape',
                        email_source = ?,
                        email_found_at = ?
                    WHERE id = ?
                ''', (owner_email, contact_email, source, datetime.now().isoformat(), lead['id']))
                # Commit after each successful email to avoid losing progress
                conn.commit()
        else:
            if emails:
                results['no_email'] += 1
            else:
                results['scrape_failures'] += 1
            print(f"✗")
        
        # Rate limit between leads
        time.sleep(0.5)
    
    if not dry_run:
        conn.commit()
    conn.close()
    
    return results

def get_current_stats():
    """Get current email coverage stats."""
    conn = sqlite3.connect('data/leads.db')
    c = conn.cursor()
    
    c.execute('''
        SELECT 
            COUNT(*) as total,
            SUM(CASE WHEN owner_email IS NOT NULL AND owner_email != '' THEN 1 ELSE 0 END) as with_email
        FROM leads
        WHERE tier IN ('A', 'B')
    ''')
    total, with_email = c.fetchone()
    conn.close()
    
    return {
        'total': total,
        'with_email': with_email,
        'missing': total - with_email,
        'coverage': (with_email / total * 100) if total > 0 else 0,
        'target': 584,
        'needed': max(0, 584 - with_email)
    }

if __name__ == '__main__':
    import sys
    
    dry_run = '--dry-run' in sys.argv
    batch_size = 50
    
    for arg in sys.argv:
        if arg.startswith('--batch='):
            batch_size = int(arg.split('=')[1])
    
    stats_before = get_current_stats()
    
    print(f"{'[DRY RUN] ' if dry_run else ''}Phase B: Contact Page Scraping")
    print(f"Current coverage: {stats_before['with_email']}/{stats_before['total']} ({stats_before['coverage']:.1f}%)")
    print(f"Target: {stats_before['target']} (need {stats_before['needed']} more)")
    print(f"Processing batch of {batch_size}...\n")
    
    results = process_batch(batch_size, dry_run)
    
    print(f"\n=== Results ===")
    print(f"Processed: {results['processed']}")
    print(f"Emails found: {results['emails_found']} ({results['emails_found']/max(1,results['processed'])*100:.1f}%)")
    print(f"  - Owner emails: {results['owner_emails']}")
    print(f"  - Contact emails: {results['contact_emails']}")
    print(f"Scrape failures: {results['scrape_failures']}")
    
    if not dry_run:
        stats_after = get_current_stats()
        print(f"\nAfter: {stats_after['with_email']}/{stats_after['total']} ({stats_after['coverage']:.1f}%)")
        print(f"Progress: +{stats_after['with_email'] - stats_before['with_email']} emails")
        print(f"Still need: {stats_after['needed']} to hit 50%")
