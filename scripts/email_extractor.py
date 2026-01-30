#!/usr/bin/env python3
"""
Email Discovery Script - Phase A
Extracts emails from existing website_text content
"""

import sqlite3
import re
import os
import time
import json
from datetime import datetime

# Email regex pattern
EMAIL_PATTERN = re.compile(
    r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
)

# Common generic emails to deprioritize
GENERIC_PREFIXES = {'info', 'contact', 'sales', 'support', 'hello', 'admin', 'webmaster', 'office', 'mail', 'general', 'enquiries', 'inquiries'}

# Emails to skip entirely (bots, noreply, etc)
SKIP_PREFIXES = {'noreply', 'no-reply', 'donotreply', 'do-not-reply', 'mailer-daemon', 'postmaster', 'bounce'}

def extract_emails_from_text(text):
    """Extract all valid emails from text, excluding skip patterns."""
    if not text:
        return []
    
    emails = EMAIL_PATTERN.findall(text.lower())
    
    # Filter out skip prefixes and invalid TLDs
    valid_emails = []
    for email in emails:
        prefix = email.split('@')[0]
        domain = email.split('@')[1] if '@' in email else ''
        
        # Skip noreply and bot emails
        if any(prefix.startswith(skip) for skip in SKIP_PREFIXES):
            continue
        
        # Skip common placeholder/example emails
        if 'example.com' in domain or 'test.com' in domain:
            continue
        
        # Skip image extensions mistakenly captured
        if domain.endswith(('.png', '.jpg', '.jpeg', '.gif', '.svg')):
            continue
        
        valid_emails.append(email)
    
    return list(set(valid_emails))  # Dedupe

def prioritize_emails(emails, business_name=None, owner_name=None):
    """
    Prioritize emails - personal > generic.
    Returns tuple: (best_owner_email, best_contact_email)
    """
    if not emails:
        return None, None
    
    personal_emails = []
    generic_emails = []
    
    for email in emails:
        prefix = email.split('@')[0]
        if any(prefix.startswith(gen) for gen in GENERIC_PREFIXES):
            generic_emails.append(email)
        else:
            personal_emails.append(email)
    
    # If we have owner_name, try to match
    if owner_name and personal_emails:
        name_parts = owner_name.lower().split()
        for email in personal_emails:
            prefix = email.split('@')[0]
            if any(part in prefix for part in name_parts if len(part) > 2):
                return email, generic_emails[0] if generic_emails else None
    
    # Return best matches
    owner_email = personal_emails[0] if personal_emails else None
    contact_email = generic_emails[0] if generic_emails else (personal_emails[1] if len(personal_emails) > 1 else None)
    
    return owner_email, contact_email

def process_batch(batch_size=50, dry_run=False):
    """Process a batch of leads with website_text but no email."""
    conn = sqlite3.connect('data/leads.db')
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    # Get candidates
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
        'owner_emails': 0,
        'contact_emails': 0,
        'no_email': 0,
        'examples': []
    }
    
    for lead in leads:
        results['processed'] += 1
        
        emails = extract_emails_from_text(lead['website_text'])
        owner_email, contact_email = prioritize_emails(
            emails, 
            lead['business_name'], 
            lead['owner_name']
        )
        
        if owner_email or contact_email:
            results['emails_found'] += 1
            if owner_email:
                results['owner_emails'] += 1
            if contact_email:
                results['contact_emails'] += 1
            
            # Save example
            if len(results['examples']) < 5:
                results['examples'].append({
                    'business': lead['business_name'],
                    'owner_email': owner_email,
                    'contact_email': contact_email,
                    'all_found': emails[:5]
                })
            
            if not dry_run:
                # Update database
                c.execute('''
                    UPDATE leads SET
                        owner_email = COALESCE(?, owner_email),
                        contact_email = COALESCE(?, contact_email),
                        email_method = 'regex_extraction',
                        email_source = 'website_text',
                        email_found_at = ?
                    WHERE id = ?
                ''', (owner_email, contact_email, datetime.now().isoformat(), lead['id']))
        else:
            results['no_email'] += 1
    
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
        'coverage': (with_email / total * 100) if total > 0 else 0
    }

if __name__ == '__main__':
    import sys
    
    dry_run = '--dry-run' in sys.argv
    batch_size = 100
    
    for arg in sys.argv:
        if arg.startswith('--batch='):
            batch_size = int(arg.split('=')[1])
    
    print(f"{'[DRY RUN] ' if dry_run else ''}Processing batch of {batch_size} leads...")
    print()
    
    stats_before = get_current_stats()
    print(f"Before: {stats_before['with_email']}/{stats_before['total']} ({stats_before['coverage']:.1f}%)")
    
    results = process_batch(batch_size, dry_run)
    
    stats_after = get_current_stats()
    
    print(f"\n=== Results ===")
    print(f"Processed: {results['processed']}")
    print(f"Emails found: {results['emails_found']} ({results['emails_found']/results['processed']*100:.1f}%)")
    print(f"  - Owner emails: {results['owner_emails']}")
    print(f"  - Contact emails: {results['contact_emails']}")
    print(f"No email found: {results['no_email']}")
    
    if results['examples']:
        print(f"\n=== Examples ===")
        for ex in results['examples'][:3]:
            print(f"  {ex['business']}: {ex['owner_email'] or ex['contact_email']}")
    
    if not dry_run:
        print(f"\nAfter: {stats_after['with_email']}/{stats_after['total']} ({stats_after['coverage']:.1f}%)")
        print(f"Progress: +{stats_after['with_email'] - stats_before['with_email']} emails")
