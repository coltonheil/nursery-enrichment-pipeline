#!/usr/bin/env python3
"""
Deep Contact Page Scraper v2
Aggressively finds emails from contact pages
"""

import sqlite3
import re
import os
import time
import requests
from urllib.parse import urljoin, urlparse
from datetime import datetime
import sys

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9',
}

# Extended contact paths
CONTACT_PATHS = [
    '', # Homepage
    '/contact',
    '/contact-us',
    '/contactus',
    '/contact.html',
    '/contact.php',
    '/about',
    '/about-us',
    '/aboutus',
    '/about.html',
    '/team',
    '/our-team',
    '/staff',
    '/people',
    '/connect',
    '/location',
    '/locations',
    '/find-us',
    '/reach-us',
    '/get-in-touch',
    '/info',
    '/information',
    '/company',
    '/footer',  # Some sites have email only in footer
]

# Email patterns
EMAIL_PATTERN = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', re.IGNORECASE)
MAILTO_PATTERN = re.compile(r'mailto:([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})', re.IGNORECASE)
JSONLD_EMAIL = re.compile(r'"email"\s*:\s*["\']([^"\']+@[^"\']+)["\']', re.IGNORECASE)

# Obfuscated patterns
OBFUSCATED_AT = re.compile(r'\b([A-Za-z0-9._%+-]+)\s*[\[\(\{]\s*at\s*[\]\)\}]\s*([A-Za-z0-9.-]+)\s*[\[\(\{]\s*dot\s*[\]\)\}]\s*([A-Za-z]{2,})\b', re.IGNORECASE)
SPACED_AT = re.compile(r'\b([A-Za-z0-9._%+-]+)\s+at\s+([A-Za-z0-9.-]+)\s+dot\s+([A-Za-z]{2,})\b', re.IGNORECASE)

# Skip patterns
SKIP_DOMAINS = {
    'example.com', 'test.com', 'domain.com', 'yourdomain.com', 'yoursite.com',
    'wix.com', 'wixpress.com', 'sentry.io', 'sentry.com',
    'wordpress.com', 'squarespace.com', 'godaddy.com', 'weebly.com',
    'mailchimp.com', 'constantcontact.com', 'hubspot.com', 'hubspotmail.com',
    'facebook.com', 'twitter.com', 'instagram.com', 'linkedin.com',
    'google.com', 'gmail.com', 'yahoo.com', 'hotmail.com', 'outlook.com',  # Skip generic providers
    'privacy.com', 'protected.com',
}

SKIP_PREFIXES = {'noreply', 'no-reply', 'donotreply', 'postmaster', 'mailer-daemon', 'bounce'}

GENERIC_PREFIXES = {'info', 'contact', 'sales', 'support', 'hello', 'admin', 'webmaster', 'office', 'mail', 'general'}

def is_valid_email(email, lead_domain=None):
    """Validate email and optionally match to lead domain."""
    if not email or len(email) < 6:
        return False
    
    email = email.lower().strip()
    
    # Basic structure
    if '@' not in email or email.count('@') > 1:
        return False
    
    local, domain = email.split('@')
    
    # Skip patterns
    if any(skip in domain for skip in SKIP_DOMAINS):
        return False
    if any(local.startswith(skip) for skip in SKIP_PREFIXES):
        return False
    
    # Skip placeholder patterns
    if 'xxx' in email or 'example' in email or 'your' in domain:
        return False
    if domain.endswith(('.png', '.jpg', '.jpeg', '.gif', '.svg')):
        return False
    
    # TLD validation
    tld = domain.split('.')[-1]
    if not (2 <= len(tld) <= 10) or not tld.isalpha():
        return False
    
    return True

def extract_emails_from_html(html, lead_domain=None):
    """Extract all valid emails from HTML content."""
    if not html:
        return []
    
    all_emails = set()
    
    # Standard emails
    for email in EMAIL_PATTERN.findall(html):
        if is_valid_email(email, lead_domain):
            all_emails.add(email.lower())
    
    # Mailto links
    for email in MAILTO_PATTERN.findall(html):
        if is_valid_email(email, lead_domain):
            all_emails.add(email.lower())
    
    # JSON-LD
    for email in JSONLD_EMAIL.findall(html):
        if is_valid_email(email, lead_domain):
            all_emails.add(email.lower())
    
    # Obfuscated patterns
    for match in OBFUSCATED_AT.findall(html):
        email = f"{match[0]}@{match[1]}.{match[2]}"
        if is_valid_email(email, lead_domain):
            all_emails.add(email.lower())
    
    for match in SPACED_AT.findall(html):
        email = f"{match[0]}@{match[1]}.{match[2]}"
        if is_valid_email(email, lead_domain):
            all_emails.add(email.lower())
    
    return list(all_emails)

def get_domain_from_url(url):
    """Extract domain from URL."""
    if not url:
        return None
    if not url.startswith(('http://', 'https://')):
        url = 'http://' + url
    parsed = urlparse(url)
    return parsed.netloc.lower().replace('www.', '')

def fetch_page(url, timeout=8):
    """Fetch a page with error handling."""
    try:
        response = requests.get(url, headers=HEADERS, timeout=timeout, allow_redirects=True)
        if response.status_code == 200:
            return response.text
    except:
        pass
    return None

def scrape_lead(website):
    """Scrape all contact pages for a lead."""
    if not website:
        return [], None
    
    if not website.startswith(('http://', 'https://')):
        website = 'https://' + website
    
    parsed = urlparse(website)
    base_url = f"{parsed.scheme}://{parsed.netloc}"
    lead_domain = parsed.netloc.lower().replace('www.', '')
    
    all_emails = set()
    source_url = None
    
    # Try each path
    for path in CONTACT_PATHS:
        if len(all_emails) >= 3:  # Stop if we have enough
            break
        
        url = urljoin(base_url, path)
        html = fetch_page(url)
        
        if html:
            emails = extract_emails_from_html(html, lead_domain)
            if emails:
                all_emails.update(emails)
                if not source_url:
                    source_url = url
        
        time.sleep(0.2)  # Rate limit
    
    return list(all_emails), source_url

def prioritize_emails(emails, owner_name=None):
    """Prioritize: personal > generic."""
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
    
    # Try to match owner name
    if owner_name and personal:
        name_parts = [p.lower() for p in owner_name.split() if len(p) > 2]
        for email in personal:
            prefix = email.split('@')[0]
            if any(part in prefix for part in name_parts):
                return email, generic[0] if generic else None
    
    owner_email = personal[0] if personal else None
    contact_email = generic[0] if generic else (personal[1] if len(personal) > 1 else None)
    
    return owner_email, contact_email

def process_batch(batch_size=50, offset=0, dry_run=False):
    """Process a batch of leads."""
    conn = sqlite3.connect('data/leads.db')
    conn.row_factory = sqlite3.Row
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
    
    results = {
        'processed': 0,
        'emails_found': 0,
        'scrape_success': 0,
        'scrape_fail': 0,
        'examples': []
    }
    
    for i, lead in enumerate(leads):
        results['processed'] += 1
        
        print(f"  [{i+1}/{len(leads)}] {lead['business_name'][:45]}...", end=' ', flush=True)
        
        emails, source = scrape_lead(lead['website'])
        
        if emails:
            results['scrape_success'] += 1
            owner_email, contact_email = prioritize_emails(emails, lead['owner_name'])
            
            if owner_email or contact_email:
                results['emails_found'] += 1
                print(f"✓ {owner_email or contact_email}")
                
                if len(results['examples']) < 20:
                    results['examples'].append({
                        'business': lead['business_name'],
                        'email': owner_email or contact_email,
                        'source': source
                    })
                
                if not dry_run:
                    c.execute('''
                        UPDATE leads SET
                            owner_email = COALESCE(?, owner_email),
                            contact_email = COALESCE(?, contact_email),
                            email_method = 'deep_scrape_v2',
                            email_source = ?,
                            email_found_at = ?
                        WHERE id = ?
                    ''', (owner_email, contact_email, source, datetime.now().isoformat(), lead['id']))
                    conn.commit()  # Commit immediately!
            else:
                print(f"✗ (emails filtered)")
        else:
            results['scrape_fail'] += 1
            print(f"✗")
        
        time.sleep(0.3)  # Rate limit between leads
    
    conn.close()
    return results

def get_stats():
    """Get current email coverage stats."""
    conn = sqlite3.connect('data/leads.db')
    c = conn.cursor()
    c.execute('''
        SELECT COUNT(*), SUM(CASE WHEN owner_email IS NOT NULL AND owner_email != '' THEN 1 ELSE 0 END)
        FROM leads WHERE tier IN ('A', 'B')
    ''')
    total, with_email = c.fetchone()
    
    c.execute('''
        SELECT COUNT(*) FROM leads
        WHERE tier IN ('A', 'B') AND website IS NOT NULL AND website != ''
        AND (owner_email IS NULL OR owner_email = '')
    ''')
    remaining = c.fetchone()[0]
    
    conn.close()
    return {
        'total': total,
        'with_email': with_email,
        'coverage': with_email/total*100,
        'needed': max(0, 584-with_email),
        'remaining': remaining
    }

if __name__ == '__main__':
    dry_run = '--dry-run' in sys.argv
    batch_size = 50
    offset = 0
    
    for arg in sys.argv:
        if arg.startswith('--batch='):
            batch_size = int(arg.split('=')[1])
        if arg.startswith('--offset='):
            offset = int(arg.split('=')[1])
    
    stats = get_stats()
    
    print(f"{'[DRY RUN] ' if dry_run else ''}Deep Scraper v2")
    print(f"Current: {stats['with_email']}/{stats['total']} ({stats['coverage']:.1f}%)")
    print(f"Remaining leads with websites: {stats['remaining']}")
    print(f"Need {stats['needed']} more for 50%")
    print(f"Processing batch of {batch_size} (offset {offset})...\n")
    
    results = process_batch(batch_size, offset, dry_run)
    
    print(f"\n=== Batch Results ===")
    print(f"Processed: {results['processed']}")
    print(f"Scrape success: {results['scrape_success']} ({results['scrape_success']/max(1,results['processed'])*100:.1f}%)")
    print(f"Emails found: {results['emails_found']} ({results['emails_found']/max(1,results['processed'])*100:.1f}%)")
    
    if not dry_run:
        stats_after = get_stats()
        print(f"\nAfter: {stats_after['with_email']}/{stats_after['total']} ({stats_after['coverage']:.1f}%)")
        print(f"Progress: +{stats_after['with_email'] - stats['with_email']} emails")
        print(f"Still need: {stats_after['needed']}")
        print(f"Remaining leads: {stats_after['remaining']}")
