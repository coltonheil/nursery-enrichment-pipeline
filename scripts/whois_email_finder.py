#!/usr/bin/env python3
"""
WHOIS Email Finder - Extract emails from domain registration
"""

import sqlite3
import subprocess
import re
import sys
from urllib.parse import urlparse
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

EMAIL_PATTERN = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', re.IGNORECASE)

SKIP_EMAILS = {
    'abuse', 'whois', 'privacy', 'proxy', 'domain', 'noreply', 'no-reply',
    'postmaster', 'webmaster', 'hostmaster', 'admin@godaddy', 'admin@namecheap',
    'operations@web.com', 'withheld', 'redacted', 'contactprivacy',
    'domainsbyproxy', 'privacyguard', 'whoisprivacy', 'domains@',
    'verisign-grs.com', 'verisign.com', 'markmonitor.com', 'networksolutions',
    'godaddy.com', 'namecheap.com', 'cloudflare.com', 'register.com',
    'tucows.com', 'enom.com', 'name.com', 'hover.com', 'porkbun.com',
    'dynadot.com', 'gandi.net', 'publicdomainregistry', 'key-systems.net'
}

def get_domain(website):
    """Extract domain from website URL"""
    if not website:
        return None
    if not website.startswith(('http://', 'https://')):
        website = 'https://' + website
    parsed = urlparse(website)
    domain = parsed.netloc.lower()
    domain = domain.replace('www.', '')
    return domain

def whois_lookup(domain):
    """Extract email from WHOIS data"""
    try:
        result = subprocess.run(
            ['whois', domain], 
            capture_output=True, 
            text=True, 
            timeout=15
        )
        output = result.stdout
        
        # Find all emails
        emails = EMAIL_PATTERN.findall(output)
        
        # Filter and prioritize
        valid_emails = []
        for email in emails:
            email = email.lower()
            # Skip privacy/abuse emails
            if any(skip in email for skip in SKIP_EMAILS):
                continue
            # Skip obvious placeholders
            if 'example.com' in email or 'test.com' in email:
                continue
            # Prefer emails matching the domain
            if domain.split('.')[0] in email:
                return email
            valid_emails.append(email)
        
        return valid_emails[0] if valid_emails else None
        
    except Exception as e:
        return None

def process_lead(lead):
    """Process a single lead"""
    lead_id, name, website = lead
    domain = get_domain(website)
    
    if not domain:
        return (lead_id, name, None, None)
    
    email = whois_lookup(domain)
    return (lead_id, name, email, domain)

def main(batch_size=100, workers=10, dry_run=False):
    conn = sqlite3.connect('data/leads.db')
    c = conn.cursor()
    
    # Get leads without emails
    c.execute('''
        SELECT id, business_name, website
        FROM leads
        WHERE tier IN ('A', 'B')
        AND website IS NOT NULL AND website != ''
        AND (owner_email IS NULL OR owner_email = '')
        LIMIT ?
    ''', (batch_size,))
    
    leads = c.fetchall()
    
    # Get current stats
    c.execute('''
        SELECT COUNT(*), 
               SUM(CASE WHEN owner_email IS NOT NULL AND owner_email != '' THEN 1 ELSE 0 END)
        FROM leads WHERE tier IN ('A', 'B')
    ''')
    total, with_email = c.fetchone()
    
    print(f"{'[DRY RUN] ' if dry_run else ''}WHOIS Email Finder")
    print(f"Current: {with_email}/{total} ({with_email/total*100:.1f}%)")
    print(f"Processing {len(leads)} leads with {workers} workers...\n")
    
    found = 0
    
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(process_lead, lead): lead for lead in leads}
        
        for i, future in enumerate(as_completed(futures)):
            lead_id, name, email, domain = future.result()
            
            if email:
                found += 1
                print(f"  ✓ {name[:40]}: {email}")
                
                if not dry_run:
                    c.execute('''
                        UPDATE leads SET
                            owner_email = ?,
                            email_method = 'whois',
                            email_source = 'whois',
                            email_confidence = 'medium',
                            email_found_at = ?
                        WHERE id = ?
                    ''', (email, datetime.now().isoformat(), lead_id))
                    conn.commit()
            
            if (i + 1) % 25 == 0:
                print(f"  ... {i+1}/{len(leads)} processed ({found} found)")
    
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
        print(f"Found: {found}")
        print(f"After: {with_email_after}/{total_after} ({with_email_after/total_after*100:.1f}%)")
        print(f"Progress: +{with_email_after - with_email}")
    else:
        print(f"\n=== Results (DRY RUN) ===")
        print(f"Processed: {len(leads)}")
        print(f"Would find: {found}")
    
    conn.close()

if __name__ == '__main__':
    dry_run = '--dry-run' in sys.argv
    batch_size = 547
    workers = 10
    
    for arg in sys.argv:
        if arg.startswith('--batch='): batch_size = int(arg.split('=')[1])
        if arg.startswith('--workers='): workers = int(arg.split('=')[1])
    
    main(batch_size, workers, dry_run)
