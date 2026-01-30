#!/usr/bin/env python3
"""
Aggressive Email Finder v3 - Uses multiple techniques:
1. Fresh HTTP scraping with expanded paths
2. WHOIS lookups
3. Pattern inference from owner names (low confidence)
"""

import sqlite3
import re
import time
import subprocess
import requests
from urllib.parse import urljoin, urlparse
from datetime import datetime
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
}

# Extended paths for contact info
CONTACT_PATHS = [
    '', '/contact', '/contact-us', '/about', '/about-us',
    '/contactus', '/info', '/connect', '/reach-us',
    '/email', '/get-in-touch', '/our-team', '/team',
    '/staff', '/people', '/directory', '/locations'
]

EMAIL_PATTERN = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', re.IGNORECASE)
MAILTO_PATTERN = re.compile(r'mailto:([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})', re.IGNORECASE)

# Obfuscated email patterns
OBFUSCATED_PATTERNS = [
    re.compile(r'([A-Za-z0-9._%+-]+)\s*[\[\(]at[\]\)]\s*([A-Za-z0-9.-]+)\s*[\[\(]dot[\]\)]\s*([A-Za-z]{2,})', re.IGNORECASE),
    re.compile(r'([A-Za-z0-9._%+-]+)\s*@\s*([A-Za-z0-9.-]+)\s*\.\s*([A-Za-z]{2,})', re.IGNORECASE),
    re.compile(r'([A-Za-z0-9._%+-]+)&#64;([A-Za-z0-9.-]+)\.([A-Za-z]{2,})', re.IGNORECASE),
]

SKIP_DOMAINS = {
    'example.com', 'test.com', 'domain.com', 'wix.com', 'wixpress.com', 'sentry.io',
    'wordpress.com', 'squarespace.com', 'mailchimp.com', 'hubspot.com',
    'facebook.com', 'twitter.com', 'instagram.com', 'google.com', 'gmail.com',
    'godaddy.com', 'latofonts.com', 'juliana.com', 'yoga.com', 'email.com',
    'gstatic.com', 'w3.org', 'schema.org', 'googleapis.com',
}

SKIP_PREFIXES = {'noreply', 'no-reply', 'donotreply', 'postmaster', 'webmaster', 'hostmaster'}
GENERIC_PREFIXES = {'info', 'contact', 'sales', 'support', 'hello', 'admin', 'office', 'mail'}

def is_valid_email(email, website_domain=None):
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
    if any(p in email for p in ['filler', 'template', 'placeholder', '@2x', 'logo', 'icon']):
        return False
    
    tld = domain.split('.')[-1]
    if not (2 <= len(tld) <= 10) or not tld.isalpha():
        return False
    
    # Extra validation: domain should look reasonable
    if len(domain) < 4:
        return False
    
    return True

def fetch_page(url, timeout=8):
    try:
        r = requests.get(url, headers=HEADERS, timeout=timeout, allow_redirects=True)
        return r.text if r.status_code == 200 else None
    except:
        return None

def extract_emails(html):
    if not html:
        return []
    emails = set()
    
    # Standard regex
    for e in EMAIL_PATTERN.findall(html):
        if is_valid_email(e):
            emails.add(e.lower())
    
    # Mailto links
    for e in MAILTO_PATTERN.findall(html):
        if is_valid_email(e):
            emails.add(e.lower())
    
    # Obfuscated patterns
    for pattern in OBFUSCATED_PATTERNS:
        for match in pattern.findall(html):
            if len(match) == 3:
                email = f"{match[0]}@{match[1]}.{match[2]}"
                if is_valid_email(email):
                    emails.add(email.lower())
    
    return list(emails)

def whois_email(domain):
    """Extract email from WHOIS data"""
    try:
        result = subprocess.run(['whois', domain], capture_output=True, text=True, timeout=10)
        output = result.stdout
        
        # Find emails in WHOIS output
        emails = EMAIL_PATTERN.findall(output)
        
        # Filter to relevant ones (skip abuse@, etc)
        for email in emails:
            email = email.lower()
            if not any(x in email for x in ['abuse@', 'whois@', 'privacy@', 'proxy@', 'domain@', 'registrant@', 'tech@', 'admin@registrar']):
                if is_valid_email(email):
                    return email
        return None
    except:
        return None

def generate_pattern_emails(owner_name, domain):
    """Generate likely email patterns from owner name"""
    if not owner_name or not domain:
        return []
    
    # Clean up name
    name = owner_name.lower().strip()
    parts = name.split()
    
    if len(parts) < 2:
        return []
    
    first = parts[0]
    last = parts[-1]
    
    # Remove common suffixes
    for suffix in [' jr', ' sr', ' ii', ' iii', ' iv']:
        if name.endswith(suffix):
            last = parts[-2] if len(parts) > 2 else parts[-1]
    
    # Clean non-alpha
    first = re.sub(r'[^a-z]', '', first)
    last = re.sub(r'[^a-z]', '', last)
    
    if len(first) < 2 or len(last) < 2:
        return []
    
    patterns = [
        f"{first}@{domain}",
        f"{first}.{last}@{domain}",
        f"{first[0]}{last}@{domain}",
        f"{first}{last[0]}@{domain}",
        f"{last}@{domain}",
    ]
    
    return patterns

def scrape_lead(lead):
    """Scrape a single lead, return result dict"""
    lead_id, name, owner_name, website = lead
    
    result = {
        'id': lead_id,
        'name': name,
        'email': None,
        'method': None,
        'source': None,
        'confidence': None
    }
    
    if not website:
        return result
    
    if not website.startswith(('http://', 'https://')):
        website = 'https://' + website
    
    parsed = urlparse(website)
    base_url = f"{parsed.scheme}://{parsed.netloc}"
    domain = parsed.netloc.replace('www.', '')
    
    # Phase 1: Fresh HTTP scraping
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
                if len(all_emails) >= 3:
                    break
    
    if all_emails:
        # Prioritize personal over generic
        personal = [e for e in all_emails if not any(e.split('@')[0].startswith(g) for g in GENERIC_PREFIXES)]
        generic = [e for e in all_emails if any(e.split('@')[0].startswith(g) for g in GENERIC_PREFIXES)]
        
        result['email'] = personal[0] if personal else generic[0]
        result['method'] = 'fresh_scrape_v3'
        result['source'] = source
        result['confidence'] = 'high'
        return result
    
    # Phase 2: WHOIS lookup
    whois = whois_email(domain)
    if whois:
        result['email'] = whois
        result['method'] = 'whois'
        result['source'] = 'whois'
        result['confidence'] = 'medium'
        return result
    
    # Phase 3: Pattern inference (marked low confidence)
    if owner_name:
        patterns = generate_pattern_emails(owner_name, domain)
        if patterns:
            # We'll store the first pattern but mark as unverified
            result['email'] = patterns[0]
            result['method'] = 'pattern'
            result['source'] = f'pattern:{owner_name}'
            result['confidence'] = 'pattern'
            return result
    
    return result

def process_batch(batch_size=100, offset=0, workers=15, dry_run=False, skip_pattern=False):
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
    
    stats = {
        'processed': 0,
        'fresh_scrape': 0,
        'whois': 0,
        'pattern': 0,
        'examples': []
    }
    
    print(f"Processing {len(leads)} leads with {workers} workers...\n")
    
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(scrape_lead, lead): lead for lead in leads}
        
        for future in as_completed(futures):
            stats['processed'] += 1
            result = future.result()
            
            if result['email']:
                # Skip patterns if requested
                if skip_pattern and result['method'] == 'pattern':
                    continue
                
                method = result['method']
                stats[method] = stats.get(method, 0) + 1
                
                confidence_emoji = {'high': '✓', 'medium': '~', 'pattern': '?'}.get(result['confidence'], '?')
                print(f"  {confidence_emoji} [{method[:8]}] {result['name'][:35]}: {result['email']}")
                
                if len(stats['examples']) < 20:
                    stats['examples'].append(result)
                
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
            
            if stats['processed'] % 25 == 0:
                found = stats['fresh_scrape'] + stats['whois'] + stats.get('pattern', 0)
                print(f"  ... {stats['processed']}/{len(leads)} ({found} found)")
    
    conn.close()
    return stats

def get_stats():
    conn = sqlite3.connect('data/leads.db')
    c = conn.cursor()
    c.execute('''
        SELECT COUNT(*), 
               SUM(CASE WHEN owner_email IS NOT NULL AND owner_email != '' THEN 1 ELSE 0 END)
        FROM leads WHERE tier IN ('A', 'B')
    ''')
    total, with_email = c.fetchone()
    c.execute('''
        SELECT COUNT(*) FROM leads 
        WHERE tier IN ('A', 'B') 
        AND website IS NOT NULL AND website != '' 
        AND (owner_email IS NULL OR owner_email = '')
    ''')
    remaining = c.fetchone()[0]
    conn.close()
    
    target_80 = int(total * 0.8)
    target_90 = int(total * 0.9)
    
    return {
        'total': total, 
        'with_email': with_email, 
        'coverage': with_email/total*100 if total else 0,
        'remaining': remaining,
        'need_80': max(0, target_80 - with_email),
        'need_90': max(0, target_90 - with_email)
    }

if __name__ == '__main__':
    dry_run = '--dry-run' in sys.argv
    skip_pattern = '--no-pattern' in sys.argv
    batch_size = 547  # All remaining
    offset = 0
    workers = 15
    
    for arg in sys.argv:
        if arg.startswith('--batch='): batch_size = int(arg.split('=')[1])
        if arg.startswith('--offset='): offset = int(arg.split('=')[1])
        if arg.startswith('--workers='): workers = int(arg.split('=')[1])
    
    stats = get_stats()
    print(f"{'[DRY RUN] ' if dry_run else ''}Aggressive Email Finder v3")
    print(f"Current: {stats['with_email']}/{stats['total']} ({stats['coverage']:.1f}%)")
    print(f"Remaining leads: {stats['remaining']}")
    print(f"Need for 80%: {stats['need_80']} | Need for 90%: {stats['need_90']}\n")
    
    results = process_batch(batch_size, offset, workers, dry_run, skip_pattern)
    
    total_found = results['fresh_scrape'] + results['whois'] + results.get('pattern', 0)
    
    print(f"\n=== Results ===")
    print(f"Processed: {results['processed']}")
    print(f"Total found: {total_found}")
    print(f"  - Fresh scrape: {results['fresh_scrape']}")
    print(f"  - WHOIS: {results['whois']}")
    print(f"  - Pattern: {results.get('pattern', 0)}")
    
    if not dry_run:
        stats_after = get_stats()
        print(f"\nAfter: {stats_after['with_email']}/{stats_after['total']} ({stats_after['coverage']:.1f}%)")
        print(f"Progress: +{stats_after['with_email'] - stats['with_email']}")
        print(f"Still need for 80%: {stats_after['need_80']}")
