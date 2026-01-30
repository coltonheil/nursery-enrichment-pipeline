#!/usr/bin/env python3
"""
Email Discovery Script v2 - Enhanced Extraction
Handles obfuscated emails and structured data
"""

import sqlite3
import re
import os
import time
import json
from datetime import datetime

# Standard email pattern
EMAIL_PATTERN = re.compile(
    r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
    re.IGNORECASE
)

# Obfuscated email patterns
OBFUSCATED_PATTERNS = [
    # [at] and [dot] variations
    re.compile(r'\b([A-Za-z0-9._%+-]+)\s*\[\s*at\s*\]\s*([A-Za-z0-9.-]+)\s*\[\s*dot\s*\]\s*([A-Za-z]{2,})\b', re.IGNORECASE),
    # (at) and (dot) variations
    re.compile(r'\b([A-Za-z0-9._%+-]+)\s*\(\s*at\s*\)\s*([A-Za-z0-9.-]+)\s*\(\s*dot\s*\)\s*([A-Za-z]{2,})\b', re.IGNORECASE),
    # {at} and {dot} variations
    re.compile(r'\b([A-Za-z0-9._%+-]+)\s*\{\s*at\s*\}\s*([A-Za-z0-9.-]+)\s*\{\s*dot\s*\}\s*([A-Za-z]{2,})\b', re.IGNORECASE),
    # " at " and " dot " with spaces
    re.compile(r'\b([A-Za-z0-9._%+-]+)\s+at\s+([A-Za-z0-9.-]+)\s+dot\s+([A-Za-z]{2,})\b', re.IGNORECASE),
    # @ but (dot)
    re.compile(r'\b([A-Za-z0-9._%+-]+)@([A-Za-z0-9.-]+)\s*\(\s*dot\s*\)\s*([A-Za-z]{2,})\b', re.IGNORECASE),
    re.compile(r'\b([A-Za-z0-9._%+-]+)@([A-Za-z0-9.-]+)\s*\[\s*dot\s*\]\s*([A-Za-z]{2,})\b', re.IGNORECASE),
    # HTML entity encoded @ (%40, &#64;, &commat;)
    re.compile(r'\b([A-Za-z0-9._%+-]+)(?:%40|&#64;|&commat;)([A-Za-z0-9.-]+\.[A-Za-z]{2,})\b', re.IGNORECASE),
]

# Mailto pattern in href
MAILTO_PATTERN = re.compile(r'mailto:([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})', re.IGNORECASE)

# JSON-LD email pattern
JSONLD_EMAIL = re.compile(r'"email"\s*:\s*"([^"]+@[^"]+)"', re.IGNORECASE)

# Skip patterns - expanded
SKIP_PATTERNS = {
    'noreply', 'no-reply', 'donotreply', 'do-not-reply', 
    'example.com', 'test.com', 'domain.com', 'yourdomain', 'yoursite',
    '.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp',
    'wix.com', 'sentry.io', 'wixpress.com', 'sentry', 
    'wordpress.com', 'squarespace.com', 'godaddy.com',
    'xxx@xxx', 'email@email', 'name@domain', 'your@email',
    'example@', 'sample@', 'placeholder', 'your-email',
    'protection#', 'protected', '[email', 'email]',
    'username@', 'user@domain', 'mysite.com', 'myemail.com',
    '@email.com', '@mail.com', '@domain.', '@example.',
    'mailchimp.com', 'constantcontact.com', 'hubspot',
    'facebook.com', 'twitter.com', 'instagram.com', 'linkedin.com',
}

GENERIC_PREFIXES = {
    'info', 'contact', 'sales', 'support', 'hello', 'admin', 
    'webmaster', 'office', 'mail', 'general', 'enquiries', 'inquiries',
    'service', 'help', 'customerservice', 'orders', 'billing'
}

def is_valid_email(email):
    """Check if email passes validation filters."""
    if not email or len(email) < 6:
        return False
    
    email_lower = email.lower()
    
    # Check skip patterns
    for skip in SKIP_PATTERNS:
        if skip in email_lower:
            return False
    
    # Must have @ and .
    if '@' not in email or '.' not in email.split('@')[1]:
        return False
    
    # Domain must be reasonable
    domain = email.split('@')[1]
    if len(domain) < 4:
        return False
    
    # TLD must be 2-10 chars
    tld = domain.split('.')[-1]
    if not (2 <= len(tld) <= 10):
        return False
    
    return True

def extract_standard_emails(text):
    """Extract standard format emails."""
    if not text:
        return []
    return [e.lower() for e in EMAIL_PATTERN.findall(text) if is_valid_email(e)]

def extract_obfuscated_emails(text):
    """Extract obfuscated emails like 'name [at] domain [dot] com'."""
    if not text:
        return []
    
    emails = []
    for pattern in OBFUSCATED_PATTERNS:
        matches = pattern.findall(text)
        for match in matches:
            if len(match) >= 3:
                email = f"{match[0]}@{match[1]}.{match[2]}".lower()
                if is_valid_email(email):
                    emails.append(email)
            elif len(match) == 2:
                email = f"{match[0]}@{match[1]}".lower()
                if is_valid_email(email):
                    emails.append(email)
    
    return emails

def extract_mailto_links(text):
    """Extract emails from mailto: links."""
    if not text:
        return []
    return [e.lower() for e in MAILTO_PATTERN.findall(text) if is_valid_email(e)]

def extract_jsonld_emails(text):
    """Extract emails from JSON-LD structured data."""
    if not text:
        return []
    return [e.lower() for e in JSONLD_EMAIL.findall(text) if is_valid_email(e)]

def extract_all_emails(text):
    """Extract all emails using all methods."""
    if not text:
        return []
    
    all_emails = set()
    
    # Standard regex
    all_emails.update(extract_standard_emails(text))
    
    # Obfuscated patterns
    all_emails.update(extract_obfuscated_emails(text))
    
    # Mailto links
    all_emails.update(extract_mailto_links(text))
    
    # JSON-LD
    all_emails.update(extract_jsonld_emails(text))
    
    return list(all_emails)

def prioritize_emails(emails, owner_name=None):
    """Prioritize emails: personal > generic."""
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

def process_batch(batch_size=100, dry_run=False):
    """Process leads with website_text but no email."""
    conn = sqlite3.connect('data/leads.db')
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    c.execute('''
        SELECT id, business_name, owner_name, website, website_text
        FROM leads
        WHERE tier IN ('A', 'B')
        AND website_text IS NOT NULL AND website_text != ''
        AND (owner_email IS NULL OR owner_email = '')
        LIMIT ?
    ''', (batch_size,))
    
    leads = c.fetchall()
    
    results = {
        'processed': 0,
        'emails_found': 0,
        'methods': {'standard': 0, 'obfuscated': 0, 'mailto': 0, 'jsonld': 0},
        'examples': []
    }
    
    for lead in leads:
        results['processed'] += 1
        
        text = lead['website_text'] or ''
        
        # Track which methods found emails
        standard = extract_standard_emails(text)
        obfuscated = extract_obfuscated_emails(text)
        mailto = extract_mailto_links(text)
        jsonld = extract_jsonld_emails(text)
        
        all_emails = list(set(standard + obfuscated + mailto + jsonld))
        
        if all_emails:
            # Track methods
            if standard: results['methods']['standard'] += 1
            if obfuscated: results['methods']['obfuscated'] += 1
            if mailto: results['methods']['mailto'] += 1
            if jsonld: results['methods']['jsonld'] += 1
            
            owner_email, contact_email = prioritize_emails(all_emails, lead['owner_name'])
            
            if owner_email or contact_email:
                results['emails_found'] += 1
                
                if len(results['examples']) < 10:
                    results['examples'].append({
                        'business': lead['business_name'],
                        'owner_email': owner_email,
                        'contact_email': contact_email,
                        'methods': {
                            'standard': bool(standard),
                            'obfuscated': bool(obfuscated),
                            'mailto': bool(mailto),
                            'jsonld': bool(jsonld)
                        }
                    })
                
                if not dry_run:
                    c.execute('''
                        UPDATE leads SET
                            owner_email = COALESCE(?, owner_email),
                            contact_email = COALESCE(?, contact_email),
                            email_method = 'enhanced_extraction_v2',
                            email_source = 'website_text',
                            email_found_at = ?
                        WHERE id = ?
                    ''', (owner_email, contact_email, datetime.now().isoformat(), lead['id']))
                    conn.commit()  # Commit per email
    
    conn.close()
    return results

def get_stats():
    """Get current stats."""
    conn = sqlite3.connect('data/leads.db')
    c = conn.cursor()
    c.execute('''
        SELECT COUNT(*), SUM(CASE WHEN owner_email IS NOT NULL AND owner_email != '' THEN 1 ELSE 0 END)
        FROM leads WHERE tier IN ('A', 'B')
    ''')
    total, with_email = c.fetchone()
    conn.close()
    return {'total': total, 'with_email': with_email, 'coverage': with_email/total*100, 'needed': max(0, 584-with_email)}

if __name__ == '__main__':
    import sys
    
    dry_run = '--dry-run' in sys.argv
    batch_size = 200
    
    for arg in sys.argv:
        if arg.startswith('--batch='):
            batch_size = int(arg.split('=')[1])
    
    stats_before = get_stats()
    print(f"{'[DRY RUN] ' if dry_run else ''}Enhanced Email Extraction v2")
    print(f"Before: {stats_before['with_email']}/{stats_before['total']} ({stats_before['coverage']:.1f}%)")
    print(f"Need: {stats_before['needed']} more for 50%")
    print(f"Processing {batch_size} leads...\n")
    
    results = process_batch(batch_size, dry_run)
    
    stats_after = get_stats()
    
    print(f"\n=== Results ===")
    print(f"Processed: {results['processed']}")
    print(f"Emails found: {results['emails_found']} ({results['emails_found']/max(1,results['processed'])*100:.1f}%)")
    print(f"\nMethods breakdown:")
    for method, count in results['methods'].items():
        print(f"  - {method}: {count}")
    
    if results['examples']:
        print(f"\n=== Examples ===")
        for ex in results['examples'][:5]:
            print(f"  {ex['business'][:40]}: {ex['owner_email'] or ex['contact_email']}")
    
    if not dry_run:
        print(f"\nAfter: {stats_after['with_email']}/{stats_after['total']} ({stats_after['coverage']:.1f}%)")
        print(f"Progress: +{stats_after['with_email'] - stats_before['with_email']} emails")
        print(f"Still need: {stats_after['needed']}")
