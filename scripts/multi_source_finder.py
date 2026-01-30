#!/usr/bin/env python3
"""
Multi-Source Email Finder v3
Combines: Web scraping, WHOIS, and pattern generation
"""

import sqlite3
import subprocess
import re
import sys
import requests
from urllib.parse import urljoin, urlparse
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
}

CONTACT_PATHS = [
    '', '/contact', '/contact-us', '/about', '/about-us',
    '/contactus', '/our-team', '/team', '/staff'
]

EMAIL_PATTERN = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', re.IGNORECASE)
MAILTO_PATTERN = re.compile(r'mailto:([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})', re.IGNORECASE)

# Domains to skip
SKIP_DOMAINS = {
    'example.com', 'domain.com', 'wix.com', 'wixpress.com', 'sentry.io',
    'wordpress.com', 'squarespace.com', 'mailchimp.com', 'hubspot.com',
    'facebook.com', 'twitter.com', 'instagram.com', 'google.com', 'gmail.com',
    'godaddy.com', 'latofonts.com', 'gstatic.com', 'w3.org', 'schema.org',
    'googleapis.com', 'verisign-grs.com', 'verisign.com', 'markmonitor.com',
    'networksolutions', 'namecheap.com', 'cloudflare.com', 'privatewho.is',
    'tucows.com', 'enom.com', 'dynadot.com', 'gandi.net', 'porkbun.com',
    'register.com', 'hover.com', 'imagemanagement.com', 'fleetfarm.com'
}

SKIP_PREFIXES = {'noreply', 'no-reply', 'donotreply', 'postmaster', 'webmaster', 
                  'hostmaster', 'abuse', 'whois', 'privacy', 'proxy', 'filler'}
GENERIC_PREFIXES = {'info', 'contact', 'sales', 'support', 'hello', 'admin', 'office', 'mail'}

def is_valid_email(email, business_domain=None):
    if not email or len(email) < 6 or '@' not in email:
        return False
    email = email.lower()
    local, domain = email.split('@', 1)
    
    if any(skip in domain for skip in SKIP_DOMAINS):
        return False
    if any(local.startswith(skip) for skip in SKIP_PREFIXES):
        return False
    if 'xxx' in email or 'example' in email or 'your' in domain:
        return False
    if any(ext in domain for ext in ['.js', '.png', '.jpg', '.webp', '.gif', '.svg', '.css']):
        return False
    if any(p in email for p in ['template', 'placeholder', '@2x', 'logo', 'icon']):
        return False
    
    tld = domain.split('.')[-1]
    if not (2 <= len(tld) <= 10) or not tld.isalpha():
        return False
    if len(domain) < 4:
        return False
    
    return True

def get_domain(website):
    if not website:
        return None
    if not website.startswith(('http://', 'https://')):
        website = 'https://' + website
    parsed = urlparse(website)
    return parsed.netloc.lower().replace('www.', '')

def fetch_page(url, timeout=8):
    try:
        r = requests.get(url, headers=HEADERS, timeout=timeout, allow_redirects=True)
        return r.text if r.status_code == 200 else None
    except:
        return None

def extract_emails_from_html(html, business_domain=None):
    if not html:
        return []
    emails = set()
    
    for e in EMAIL_PATTERN.findall(html):
        if is_valid_email(e, business_domain):
            emails.add(e.lower())
    
    for e in MAILTO_PATTERN.findall(html):
        if is_valid_email(e, business_domain):
            emails.add(e.lower())
    
    return list(emails)

def scrape_website(website):
    """Try to find email by scraping website"""
    if not website:
        return None, None
    
    if not website.startswith(('http://', 'https://')):
        website = 'https://' + website
    
    parsed = urlparse(website)
    base_url = f"{parsed.scheme}://{parsed.netloc}"
    domain = parsed.netloc.lower().replace('www.', '')
    
    all_emails = set()
    source = None
    
    for path in CONTACT_PATHS:
        url = urljoin(base_url, path)
        html = fetch_page(url)
        if html:
            emails = extract_emails_from_html(html, domain)
            if emails:
                all_emails.update(emails)
                if not source:
                    source = url
                if len(all_emails) >= 2:
                    break
    
    if not all_emails:
        return None, None
    
    # Prioritize emails matching business domain
    matching = [e for e in all_emails if domain.split('.')[0] in e]
    personal = [e for e in all_emails if not any(e.split('@')[0].startswith(g) for g in GENERIC_PREFIXES)]
    generic = [e for e in all_emails if any(e.split('@')[0].startswith(g) for g in GENERIC_PREFIXES)]
    
    if matching:
        return matching[0], source
    elif personal:
        return personal[0], source
    elif generic:
        return generic[0], source
    
    return list(all_emails)[0], source

def whois_lookup(domain):
    """Extract email from WHOIS data"""
    try:
        result = subprocess.run(['whois', domain], capture_output=True, text=True, timeout=12)
        output = result.stdout
        emails = EMAIL_PATTERN.findall(output)
        
        for email in emails:
            email = email.lower()
            if not any(skip in email for skip in SKIP_DOMAINS):
                if is_valid_email(email):
                    # Prefer emails matching the domain
                    if domain.split('.')[0] in email:
                        return email
        
        # Return first valid non-registrar email
        for email in emails:
            if is_valid_email(email.lower()):
                return email.lower()
        return None
    except:
        return None

def process_lead(lead):
    """Process a single lead through all methods"""
    lead_id, name, owner_name, website = lead
    
    result = {
        'id': lead_id,
        'name': name,
        'email': None,
        'method': None,
        'source': None,
        'confidence': None
    }
    
    domain = get_domain(website)
    
    # Method 1: Web scraping
    email, source = scrape_website(website)
    if email:
        result['email'] = email
        result['method'] = 'web_scrape_v3'
        result['source'] = source
        result['confidence'] = 'high'
        return result
    
    # Method 2: WHOIS
    if domain:
        email = whois_lookup(domain)
        if email:
            result['email'] = email
            result['method'] = 'whois'
            result['source'] = 'whois'
            result['confidence'] = 'medium'
            return result
    
    return result

def main(batch_size=200, workers=12, dry_run=False):
    conn = sqlite3.connect('data/leads.db')
    c = conn.cursor()
    
    # Get current stats
    c.execute('''
        SELECT COUNT(*), 
               SUM(CASE WHEN owner_email IS NOT NULL AND owner_email != '' THEN 1 ELSE 0 END)
        FROM leads WHERE tier IN ('A', 'B')
    ''')
    total, with_email = c.fetchone()
    
    # Get leads without emails
    c.execute('''
        SELECT id, business_name, owner_name, website
        FROM leads
        WHERE tier IN ('A', 'B')
        AND website IS NOT NULL AND website != ''
        AND (owner_email IS NULL OR owner_email = '')
        LIMIT ?
    ''', (batch_size,))
    
    leads = c.fetchall()
    
    target_80 = int(total * 0.8)
    need_80 = max(0, target_80 - with_email)
    
    print(f"{'[DRY RUN] ' if dry_run else ''}Multi-Source Email Finder v3")
    print(f"Current: {with_email}/{total} ({with_email/total*100:.1f}%)")
    print(f"Target 80%: {target_80} (need {need_80} more)")
    print(f"Processing {len(leads)} leads with {workers} workers...\n")
    
    stats = {'web_scrape_v3': 0, 'whois': 0, 'total': 0}
    
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(process_lead, lead): lead for lead in leads}
        
        for i, future in enumerate(as_completed(futures)):
            result = future.result()
            
            if result['email']:
                stats['total'] += 1
                stats[result['method']] = stats.get(result['method'], 0) + 1
                
                conf = {'high': '✓', 'medium': '~'}.get(result['confidence'], '?')
                print(f"  {conf} [{result['method'][:10]}] {result['name'][:35]}: {result['email']}")
                
                if not dry_run:
                    c.execute('''
                        UPDATE leads SET
                            owner_email = ?,
                            email_method = ?,
                            email_source = ?,
                            email_confidence = ?,
                            email_found_at = ?
                        WHERE id = ?
                    ''', (result['email'], result['method'], result['source'],
                          result['confidence'], datetime.now().isoformat(), result['id']))
                    conn.commit()
            
            if (i + 1) % 50 == 0:
                print(f"  ... {i+1}/{len(leads)} ({stats['total']} found)")
    
    # Final stats
    if not dry_run:
        c.execute('''
            SELECT COUNT(*), 
                   SUM(CASE WHEN owner_email IS NOT NULL AND owner_email != '' THEN 1 ELSE 0 END)
            FROM leads WHERE tier IN ('A', 'B')
        ''')
        total_after, with_email_after = c.fetchone()
        
        print(f"\n=== Results ===")
        print(f"Processed: {len(leads)}")
        print(f"Found: {stats['total']}")
        print(f"  - Web scrape: {stats.get('web_scrape_v3', 0)}")
        print(f"  - WHOIS: {stats.get('whois', 0)}")
        print(f"\nAfter: {with_email_after}/{total_after} ({with_email_after/total_after*100:.1f}%)")
        print(f"Progress: +{with_email_after - with_email}")
        print(f"Still need for 80%: {max(0, target_80 - with_email_after)}")
    else:
        print(f"\n=== Results (DRY RUN) ===")
        print(f"Would find: {stats['total']}")
    
    conn.close()

if __name__ == '__main__':
    dry_run = '--dry-run' in sys.argv
    batch_size = 524  # All remaining
    workers = 12
    
    for arg in sys.argv:
        if arg.startswith('--batch='): batch_size = int(arg.split('=')[1])
        if arg.startswith('--workers='): workers = int(arg.split('=')[1])
    
    main(batch_size, workers, dry_run)
