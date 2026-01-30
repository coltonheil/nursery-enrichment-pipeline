#!/usr/bin/env python3
"""
Gemini Email Extractor - Uses AI to find obfuscated emails in website text
"""

import sqlite3
import os
import re
import time
import sys
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

import google.generativeai as genai

genai.configure(api_key=os.getenv('GEMINI_API_KEY'))
model = genai.GenerativeModel('gemini-2.0-flash')

# Standard email regex to validate Gemini's output
EMAIL_PATTERN = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', re.IGNORECASE)

SKIP_DOMAINS = {
    'example.com', 'test.com', 'domain.com', 'wix.com', 'wixpress.com', 'sentry.io',
    'wordpress.com', 'squarespace.com', 'mailchimp.com', 'hubspot.com',
    'facebook.com', 'twitter.com', 'instagram.com', 'google.com',
    'godaddy.com', 'latofonts.com', 'juliana.com', 'yoga.com', 'email.com',
}

SKIP_PREFIXES = {'noreply', 'no-reply', 'donotreply', 'postmaster'}

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
    if any(ext in domain for ext in ['.js', '.png', '.jpg', '.webp', '.gif', '.svg', '.css']):
        return False
    if any(p in email for p in ['filler', 'template', 'placeholder', '@2x', 'logo']):
        return False
    tld = domain.split('.')[-1]
    if not (2 <= len(tld) <= 10) or not tld.isalpha():
        return False
    return True

def extract_with_gemini(website_text, business_name, max_retries=2):
    """Use Gemini to extract emails from website text"""
    
    # Truncate text to avoid token limits
    text = website_text[:8000] if len(website_text) > 8000 else website_text
    
    prompt = f"""Analyze this website text for a business called "{business_name}".

Extract ANY email addresses you can find, including:
- Standard emails: example@domain.com
- Obfuscated: info [at] domain [dot] com, info(at)domain(dot)com
- Spaced: info @ domain . com
- HTML entities: info&#64;domain.com
- Any other format

ONLY return emails that are ACTUALLY in the text. DO NOT make up or guess emails.

Return ONLY the email addresses, one per line. If no emails found, return "NONE".

Website text:
{text}"""

    for attempt in range(max_retries):
        try:
            response = model.generate_content(prompt)
            result = response.text.strip()
            
            if result.upper() == 'NONE' or not result:
                return []
            
            # Extract and validate emails from response
            emails = []
            for line in result.split('\n'):
                line = line.strip().lower()
                # Clean up common formatting
                line = line.replace(' [at] ', '@').replace('[at]', '@')
                line = line.replace(' (at) ', '@').replace('(at)', '@')
                line = line.replace(' [dot] ', '.').replace('[dot]', '.')
                line = line.replace(' (dot) ', '.').replace('(dot)', '.')
                line = line.replace(' @ ', '@').replace(' . ', '.')
                line = line.replace('&#64;', '@')
                
                # Find emails in cleaned line
                found = EMAIL_PATTERN.findall(line)
                for email in found:
                    if is_valid_email(email):
                        emails.append(email.lower())
            
            return list(set(emails))
            
        except Exception as e:
            if 'quota' in str(e).lower() or 'rate' in str(e).lower():
                time.sleep(5 * (attempt + 1))
            else:
                print(f"    Error: {e}")
                break
    
    return []

def process_leads(batch_size=50, dry_run=False):
    conn = sqlite3.connect('data/leads.db')
    c = conn.cursor()
    
    # Get leads with website_text but no email
    c.execute('''
        SELECT id, business_name, website_text, website
        FROM leads
        WHERE tier IN ('A', 'B')
        AND website_text IS NOT NULL
        AND LENGTH(website_text) > 100
        AND (owner_email IS NULL OR owner_email = '')
        LIMIT ?
    ''', (batch_size,))
    
    leads = c.fetchall()
    
    stats = {'processed': 0, 'found': 0, 'emails': []}
    
    print(f"Processing {len(leads)} leads with Gemini...\n")
    
    for lead_id, name, text, website in leads:
        stats['processed'] += 1
        
        emails = extract_with_gemini(text, name)
        
        if emails:
            stats['found'] += 1
            email = emails[0]  # Take first valid email
            print(f"  ✓ {name[:45]}: {email}")
            stats['emails'].append({'name': name, 'email': email})
            
            if not dry_run:
                c.execute('''
                    UPDATE leads SET
                        owner_email = ?,
                        email_method = 'gemini',
                        email_source = ?,
                        email_confidence = 'high',
                        email_found_at = ?
                    WHERE id = ?
                ''', (email, website or 'gemini_analysis', datetime.now().isoformat(), lead_id))
                conn.commit()
        
        if stats['processed'] % 10 == 0:
            print(f"  ... {stats['processed']}/{len(leads)} ({stats['found']} found)")
        
        # Rate limiting
        time.sleep(0.5)
    
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
    conn.close()
    return {'total': total, 'with_email': with_email, 'coverage': with_email/total*100 if total else 0}

if __name__ == '__main__':
    dry_run = '--dry-run' in sys.argv
    batch_size = 50
    
    for arg in sys.argv:
        if arg.startswith('--batch='): batch_size = int(arg.split('=')[1])
    
    stats = get_stats()
    print(f"{'[DRY RUN] ' if dry_run else ''}Gemini Email Extractor")
    print(f"Current: {stats['with_email']}/{stats['total']} ({stats['coverage']:.1f}%)")
    print(f"Target: 80% = {int(stats['total'] * 0.8)} emails\n")
    
    results = process_leads(batch_size, dry_run)
    
    print(f"\n=== Results ===")
    print(f"Processed: {results['processed']}")
    print(f"Emails found: {results['found']} ({results['found']/max(1,results['processed'])*100:.1f}%)")
    
    if not dry_run:
        stats_after = get_stats()
        print(f"\nAfter: {stats_after['with_email']}/{stats_after['total']} ({stats_after['coverage']:.1f}%)")
        print(f"Progress: +{stats_after['with_email'] - stats['with_email']}")
