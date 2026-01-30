#!/usr/bin/env python3
"""
Email Discovery Script - Gemini Extraction
Uses Gemini to extract emails from website_text where regex failed
"""

import sqlite3
import os
import time
import json
import re
from datetime import datetime
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

# Configure Gemini
genai.configure(api_key=os.getenv('GEMINI_API_KEY'))
model = genai.GenerativeModel('gemini-2.5-flash')

# Email validation regex
EMAIL_PATTERN = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b')

EXTRACTION_PROMPT = """Extract ALL email addresses from this website text. Look for:
- Standard emails (name@domain.com)
- Obfuscated emails (name [at] domain [dot] com, name(at)domain.com)
- Emails split across lines or with spaces
- Contact form destinations mentioned in text

Website text:
{text}

Return ONLY a JSON object with this format (no markdown, no explanation):
{{"emails": ["email1@domain.com", "email2@domain.com"], "owner_name_mentioned": "Name if found or null"}}

If no emails found, return: {{"emails": [], "owner_name_mentioned": null}}
"""

def extract_with_gemini(text, max_chars=8000):
    """Use Gemini to extract emails from text."""
    if not text or len(text) < 50:
        return [], None
    
    # Truncate if too long
    text = text[:max_chars]
    
    try:
        response = model.generate_content(
            EXTRACTION_PROMPT.format(text=text),
            generation_config={
                'temperature': 0.1,
                'max_output_tokens': 500
            }
        )
        
        result_text = response.text.strip()
        
        # Try to parse JSON
        # Handle markdown code blocks
        if '```json' in result_text:
            result_text = result_text.split('```json')[1].split('```')[0].strip()
        elif '```' in result_text:
            result_text = result_text.split('```')[1].split('```')[0].strip()
        
        result = json.loads(result_text)
        
        # Validate emails
        valid_emails = []
        for email in result.get('emails', []):
            email = email.lower().strip()
            if EMAIL_PATTERN.match(email):
                # Skip obvious bad ones
                if not any(x in email for x in ['example.com', 'test.com', 'noreply', '.png', '.jpg']):
                    valid_emails.append(email)
        
        return valid_emails, result.get('owner_name_mentioned')
        
    except Exception as e:
        print(f"  Gemini error: {e}")
        return [], None

def classify_email(email):
    """Classify email as personal or generic."""
    generic_prefixes = {'info', 'contact', 'sales', 'support', 'hello', 'admin', 'office', 'mail', 'general', 'enquiries', 'inquiries'}
    prefix = email.split('@')[0]
    return 'generic' if any(prefix.startswith(g) for g in generic_prefixes) else 'personal'

def process_batch(batch_size=50, dry_run=False):
    """Process leads with website_text but no email found by regex."""
    conn = sqlite3.connect('data/leads.db')
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    # Get candidates - those with website_text but still no email
    c.execute('''
        SELECT id, business_name, owner_name, website, website_text
        FROM leads
        WHERE tier IN ('A', 'B')
        AND website_text IS NOT NULL AND website_text != ''
        AND (owner_email IS NULL OR owner_email = '')
        AND (email_method IS NULL OR email_method = '')
        LIMIT ?
    ''', (batch_size,))
    
    leads = c.fetchall()
    
    results = {
        'processed': 0,
        'emails_found': 0,
        'skipped': 0,
        'errors': 0,
        'examples': []
    }
    
    for i, lead in enumerate(leads):
        results['processed'] += 1
        
        # Rate limit: 1 req/sec
        if i > 0:
            time.sleep(1)
        
        print(f"  [{i+1}/{len(leads)}] {lead['business_name'][:40]}...", end=' ')
        
        emails, owner_name = extract_with_gemini(lead['website_text'])
        
        if emails:
            results['emails_found'] += 1
            
            # Pick best emails
            personal = [e for e in emails if classify_email(e) == 'personal']
            generic = [e for e in emails if classify_email(e) == 'generic']
            
            owner_email = personal[0] if personal else None
            contact_email = generic[0] if generic else (personal[1] if len(personal) > 1 else None)
            
            print(f"✓ Found: {owner_email or contact_email}")
            
            if len(results['examples']) < 10:
                results['examples'].append({
                    'business': lead['business_name'],
                    'owner_email': owner_email,
                    'contact_email': contact_email,
                    'all_found': emails
                })
            
            if not dry_run:
                c.execute('''
                    UPDATE leads SET
                        owner_email = COALESCE(?, owner_email),
                        contact_email = COALESCE(?, contact_email),
                        email_method = 'gemini_extraction',
                        email_source = 'website_text',
                        email_found_at = ?
                    WHERE id = ?
                ''', (owner_email, contact_email, datetime.now().isoformat(), lead['id']))
        else:
            print(f"✗ No email")
    
    if not dry_run:
        conn.commit()
    conn.close()
    
    return results

def get_remaining_count():
    """Get count of remaining leads to process."""
    conn = sqlite3.connect('data/leads.db')
    c = conn.cursor()
    c.execute('''
        SELECT COUNT(*) FROM leads
        WHERE tier IN ('A', 'B')
        AND website_text IS NOT NULL AND website_text != ''
        AND (owner_email IS NULL OR owner_email = '')
        AND (email_method IS NULL OR email_method = '')
    ''')
    count = c.fetchone()[0]
    conn.close()
    return count

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
    
    remaining = get_remaining_count()
    stats_before = get_current_stats()
    
    print(f"{'[DRY RUN] ' if dry_run else ''}Gemini Email Extraction")
    print(f"Remaining candidates: {remaining}")
    print(f"Current coverage: {stats_before['with_email']}/{stats_before['total']} ({stats_before['coverage']:.1f}%)")
    print(f"Target: {stats_before['target']} (need {stats_before['needed']} more)")
    print(f"Processing batch of {batch_size}...\n")
    
    results = process_batch(batch_size, dry_run)
    
    print(f"\n=== Results ===")
    print(f"Processed: {results['processed']}")
    print(f"Emails found: {results['emails_found']} ({results['emails_found']/max(1,results['processed'])*100:.1f}%)")
    
    if not dry_run:
        stats_after = get_current_stats()
        print(f"\nAfter: {stats_after['with_email']}/{stats_after['total']} ({stats_after['coverage']:.1f}%)")
        print(f"Progress: +{stats_after['with_email'] - stats_before['with_email']} emails")
        print(f"Still need: {stats_after['needed']} to hit 50%")
