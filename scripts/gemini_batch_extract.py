#!/usr/bin/env python3
"""
Gemini Batch Email Extractor - Processes leads in batches
Uses Gemini to find obfuscated/hidden emails
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

EMAIL_PATTERN = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', re.IGNORECASE)

SKIP_DOMAINS = {
    'example.com', 'domain.com', 'wix.com', 'squarespace.com', 'godaddy.com',
    'wordpress.com', 'mailchimp.com', 'hubspot.com', 'gstatic.com', 'w3.org',
    'schema.org', 'googleapis.com', 'sentry.io', 'facebook.com', 'google.com',
    'verisign-grs.com', 'latofonts.com', 'eyebytes.com', 'micahrich.com',
    'gulosolutions.com', 'southland.rentals', 'siteone.com'
}

def is_valid_email(email):
    if not email or len(email) < 6 or '@' not in email:
        return False
    email = email.lower()
    local, domain = email.split('@', 1)
    
    if any(skip in domain for skip in SKIP_DOMAINS):
        return False
    if local in ['noreply', 'no-reply', 'postmaster', 'webmaster', 'filler']:
        return False
    if 'example' in email or 'placeholder' in email or 'template' in email:
        return False
    if any(ext in domain for ext in ['.js', '.png', '.jpg', '.webp', '.css']):
        return False
    
    tld = domain.split('.')[-1]
    if not (2 <= len(tld) <= 10) or not tld.isalpha():
        return False
    
    return True

def clean_email(text):
    """Convert obfuscated formats to standard email"""
    text = text.lower().strip()
    text = text.replace(' [at] ', '@').replace('[at]', '@')
    text = text.replace(' (at) ', '@').replace('(at)', '@')
    text = text.replace(' [dot] ', '.').replace('[dot]', '.')
    text = text.replace(' (dot) ', '.').replace('(dot)', '.')
    text = text.replace(' @ ', '@').replace(' . ', '.')
    text = text.replace('&#64;', '@')
    return text

def extract_with_gemini(text, business_name):
    """Use Gemini to extract emails"""
    # Truncate to avoid token limits
    text = text[:6000] if len(text) > 6000 else text
    
    prompt = f"""Extract email addresses from this website content for "{business_name}".

Look for:
- Standard emails (name@domain.com)  
- Obfuscated formats (info [at] domain [dot] com)
- Spaced out emails (info @ domain . com)
- Mailto links

ONLY return emails that EXIST in the text. Do NOT invent or guess emails.

Return each email on a new line. If none found, return "NONE".

Text:
{text}"""

    try:
        response = model.generate_content(prompt)
        result = response.text.strip()
        
        if 'NONE' in result.upper() and len(result) < 20:
            return []
        
        emails = []
        for line in result.split('\n'):
            line = clean_email(line)
            found = EMAIL_PATTERN.findall(line)
            for email in found:
                if is_valid_email(email):
                    emails.append(email.lower())
        
        return list(set(emails))
        
    except Exception as e:
        if 'quota' in str(e).lower() or 'rate' in str(e).lower():
            time.sleep(2)
        return []

def main(batch_size=100, dry_run=False):
    conn = sqlite3.connect('data/leads.db')
    c = conn.cursor()
    
    # Get stats
    c.execute('''
        SELECT COUNT(*), 
               SUM(CASE WHEN owner_email IS NOT NULL AND owner_email != '' THEN 1 ELSE 0 END)
        FROM leads WHERE tier IN ('A', 'B')
    ''')
    total, with_email = c.fetchone()
    
    # Get leads with website_text but no email
    c.execute('''
        SELECT id, business_name, website_text, website
        FROM leads
        WHERE tier IN ('A', 'B')
        AND website_text IS NOT NULL
        AND LENGTH(website_text) > 200
        AND (owner_email IS NULL OR owner_email = '')
        LIMIT ?
    ''', (batch_size,))
    
    leads = c.fetchall()
    
    print(f"{'[DRY RUN] ' if dry_run else ''}Gemini Batch Extractor")
    print(f"Current: {with_email}/{total} ({with_email/total*100:.1f}%)")
    print(f"Processing {len(leads)} leads...\n")
    
    found = 0
    
    for i, (lead_id, name, text, website) in enumerate(leads):
        emails = extract_with_gemini(text, name)
        
        if emails:
            found += 1
            email = emails[0]
            print(f"  ✓ {name[:40]}: {email}")
            
            if not dry_run:
                c.execute('''
                    UPDATE leads SET
                        owner_email = ?,
                        email_method = 'gemini',
                        email_source = ?,
                        email_confidence = 'high',
                        email_found_at = ?
                    WHERE id = ?
                ''', (email, website or 'gemini', datetime.now().isoformat(), lead_id))
                conn.commit()
        
        if (i + 1) % 20 == 0:
            print(f"  ... {i+1}/{len(leads)} ({found} found)")
        
        # Rate limit
        time.sleep(0.3)
    
    print(f"\n=== Results ===")
    print(f"Processed: {len(leads)}")
    print(f"Found: {found}")
    
    if not dry_run:
        c.execute('''
            SELECT COUNT(*), 
                   SUM(CASE WHEN owner_email IS NOT NULL AND owner_email != '' THEN 1 ELSE 0 END)
            FROM leads WHERE tier IN ('A', 'B')
        ''')
        total_after, with_email_after = c.fetchone()
        print(f"\nAfter: {with_email_after}/{total_after} ({with_email_after/total_after*100:.1f}%)")
        print(f"Progress: +{with_email_after - with_email}")
    
    conn.close()

if __name__ == '__main__':
    dry_run = '--dry-run' in sys.argv
    batch_size = 200
    
    for arg in sys.argv:
        if arg.startswith('--batch='): batch_size = int(arg.split('=')[1])
    
    main(batch_size, dry_run)
