#!/usr/bin/env python3
"""
Fast Email Scraper - Optimized for speed
Only tries homepage + /contact page
"""

import sqlite3
import re
import time
import requests
from urllib.parse import urljoin, urlparse
from datetime import datetime
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
    'Accept': 'text/html,application/xhtml+xml',
}

# Only essential paths
CONTACT_PATHS = ['', '/contact', '/contact-us', '/about']

EMAIL_PATTERN = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', re.IGNORECASE)
MAILTO_PATTERN = re.compile(r'mailto:([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})', re.IGNORECASE)

SKIP_DOMAINS = {
    'example.com', 'test.com', 'domain.com', 'wix.com', 'wixpress.com', 'sentry.io',
    'wordpress.com', 'squarespace.com', 'mailchimp.com', 'hubspot.com',
    'facebook.com', 'twitter.com', 'instagram.com', 'google.com',
    'godaddy.com', 'latofonts.com', 'juliana.com', 'yoga.com', 'email.com',
    '10-min.js', '2x.png', '2x.webp', 'placeholder.com',
}

SKIP_PREFIXES = {'noreply', 'no-reply', 'donotreply', 'postmaster'}
GENERIC_PREFIXES = {'info', 'contact', 'sales', 'support', 'hello', 'admin', 'office'}

def is_valid_email(email):
    if not email or len(email) < 6 or '@' not in email:
        return False
    local, domain = email.lower().split('@', 1)
    if any(skip in domain for skip in SKIP_DOMAINS):
        return False
    if any(local.startswith(skip) for skip in SKIP_PREFIXES):
        return False
    if 'xxx' in email or 'example' in email or 'your' in domain:
        return False
    # Skip file extensions being captured as emails
    if any(ext in domain for ext in ['.js', '.png', '.jpg', '.webp', '.gif', '.svg', '.css']):
        return False
    # Skip common template placeholders
    if any(p in email for p in ['filler', 'template', 'placeholder', '@2x', 'logo']):
        return False
    tld = domain.split('.')[-1]
    if not (2 <= len(tld) <= 10):
        return False
    # TLD must be letters only
    if not tld.isalpha():
        return False
    return True

def fetch_page(url, timeout=5):
    try:
        r = requests.get(url, headers=HEADERS, timeout=timeout, allow_redirects=True)
        return r.text if r.status_code == 200 else None
    except:
        return None

def extract_emails(html):
    if not html:
        return []
    emails = set()
    for e in EMAIL_PATTERN.findall(html):
        if is_valid_email(e):
            emails.add(e.lower())
    for e in MAILTO_PATTERN.findall(html):
        if is_valid_email(e):
            emails.add(e.lower())
    return list(emails)

def scrape_lead(lead):
    """Scrape a single lead, return (lead_id, owner_email, contact_email, source)"""
    lead_id, name, owner_name, website = lead
    
    if not website:
        return (lead_id, None, None, None, name)
    
    if not website.startswith(('http://', 'https://')):
        website = 'https://' + website
    
    parsed = urlparse(website)
    base_url = f"{parsed.scheme}://{parsed.netloc}"
    
    all_emails = set()
    source = None
    
    for path in CONTACT_PATHS:
        url = urljoin(base_url, path)
        html = fetch_page(url)
        if html:
            emails = extract_emails(html)
            if emails:
                all_emails.update(emails)
                if not source:
                    source = url
                if len(all_emails) >= 2:
                    break
    
    if not all_emails:
        return (lead_id, None, None, None, name)
    
    # Prioritize
    personal = []
    generic = []
    for email in all_emails:
        prefix = email.split('@')[0]
        if any(prefix.startswith(g) for g in GENERIC_PREFIXES):
            generic.append(email)
        else:
            personal.append(email)
    
    owner_email = personal[0] if personal else None
    contact_email = generic[0] if generic else (personal[1] if len(personal) > 1 else None)
    
    return (lead_id, owner_email, contact_email, source, name)

def process_batch(batch_size=100, offset=0, workers=10, dry_run=False):
    conn = sqlite3.connect('data/leads.db')
    c = conn.cursor()
    
    c.execute('''
        SELECT id, business_name, owner_name, website
        FROM leads
        WHERE tier IN ('A', 'B')
        AND website IS NOT NULL AND website != ''
        AND (owner_email IS NULL OR owner_email = '')
        LIMIT ? OFFSET ?
    ''', (batch_size, offset))
    
    leads = c.fetchall()
    
    results = {'processed': 0, 'found': 0, 'examples': []}
    
    print(f"Processing {len(leads)} leads with {workers} workers...\n")
    
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(scrape_lead, lead): lead for lead in leads}
        
        for future in as_completed(futures):
            results['processed'] += 1
            lead_id, owner_email, contact_email, source, name = future.result()
            
            if owner_email or contact_email:
                results['found'] += 1
                email = owner_email or contact_email
                print(f"  ✓ {name[:40]}: {email}")
                
                if len(results['examples']) < 20:
                    results['examples'].append({'name': name, 'email': email})
                
                if not dry_run:
                    c.execute('''
                        UPDATE leads SET
                            owner_email = COALESCE(?, owner_email),
                            contact_email = COALESCE(?, contact_email),
                            email_method = 'fast_scrape_v2',
                            email_source = ?,
                            email_found_at = ?
                        WHERE id = ?
                    ''', (owner_email, contact_email, source, datetime.now().isoformat(), lead_id))
                    conn.commit()
            
            if results['processed'] % 20 == 0:
                print(f"  ... {results['processed']}/{len(leads)} ({results['found']} found)")
    
    conn.close()
    return results

def get_stats():
    conn = sqlite3.connect('data/leads.db')
    c = conn.cursor()
    c.execute('''SELECT COUNT(*), SUM(CASE WHEN owner_email IS NOT NULL AND owner_email != '' THEN 1 ELSE 0 END) FROM leads WHERE tier IN ('A', 'B')''')
    total, with_email = c.fetchone()
    c.execute('''SELECT COUNT(*) FROM leads WHERE tier IN ('A', 'B') AND website IS NOT NULL AND website != '' AND (owner_email IS NULL OR owner_email = '')''')
    remaining = c.fetchone()[0]
    conn.close()
    return {'total': total, 'with_email': with_email, 'coverage': with_email/total*100, 'needed': max(0, 584-with_email), 'remaining': remaining}

if __name__ == '__main__':
    dry_run = '--dry-run' in sys.argv
    batch_size = 100
    offset = 0
    workers = 10
    
    for arg in sys.argv:
        if arg.startswith('--batch='): batch_size = int(arg.split('=')[1])
        if arg.startswith('--offset='): offset = int(arg.split('=')[1])
        if arg.startswith('--workers='): workers = int(arg.split('=')[1])
    
    stats = get_stats()
    print(f"{'[DRY RUN] ' if dry_run else ''}Fast Scraper")
    print(f"Current: {stats['with_email']}/{stats['total']} ({stats['coverage']:.1f}%)")
    print(f"Remaining: {stats['remaining']} | Need: {stats['needed']}\n")
    
    results = process_batch(batch_size, offset, workers, dry_run)
    
    print(f"\n=== Results ===")
    print(f"Processed: {results['processed']}")
    print(f"Emails found: {results['found']} ({results['found']/max(1,results['processed'])*100:.1f}%)")
    
    if not dry_run:
        stats_after = get_stats()
        print(f"\nAfter: {stats_after['with_email']}/{stats_after['total']} ({stats_after['coverage']:.1f}%)")
        print(f"Progress: +{stats_after['with_email'] - stats['with_email']}")
        print(f"Still need: {stats_after['needed']}")
