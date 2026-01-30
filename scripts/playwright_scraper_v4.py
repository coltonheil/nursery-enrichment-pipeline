#!/usr/bin/env python3
"""
Email Discovery v4 - Playwright Scraper
Uses headless Chromium to render JS-heavy sites and extract emails + detect contact forms
"""

import sqlite3
import re
import time
from datetime import datetime
from urllib.parse import urljoin, urlparse
from concurrent.futures import ThreadPoolExecutor, as_completed

# Playwright imports
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

DB_PATH = 'data/leads.db'

# Email regex - standard pattern
EMAIL_PATTERN = re.compile(
    r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b'
)

# Skip these email patterns (false positives)
SKIP_PATTERNS = [
    r'@example\.', r'@test\.', r'@localhost',
    r'@sentry\.', r'@wixpress\.', r'@godaddy\.', 
    r'@squarespace\.', r'@weebly\.', r'@shopify\.',
    r'@latofonts\.', r'@wordpress\.', r'@w3\.org',
    r'your@', r'email@', r'info@info\.', r'name@',
    r'placeholder', r'sample', r'filler',
    r'\.jpg$', r'\.png$', r'\.gif$', r'\.webp$',
    r'\.js$', r'\.css$', r'\.svg$',
    r'@\d+x\d+', r'@2x\.', r'@3x\.',  # Image sizes
]
SKIP_RE = re.compile('|'.join(SKIP_PATTERNS), re.IGNORECASE)

# Contact form indicators
FORM_INDICATORS = [
    'contact form', 'send message', 'get in touch', 'send us a message',
    'submit', 'send inquiry', 'contact us form', 'send email',
    'your message', 'your name', 'your email'
]

# Paths to check for emails/contact pages
CONTACT_PATHS = ['/', '/contact', '/contact-us', '/about', '/about-us']


def is_valid_email(email: str) -> bool:
    """Check if email is valid and not a false positive"""
    email = email.lower().strip()
    
    # Basic sanity checks
    if len(email) < 6 or len(email) > 254:
        return False
    
    if SKIP_RE.search(email):
        return False
    
    # Must have proper TLD
    parts = email.split('@')
    if len(parts) != 2:
        return False
    
    domain = parts[1]
    if '.' not in domain:
        return False
    
    tld = domain.split('.')[-1]
    if len(tld) < 2:
        return False
    
    return True


def extract_emails_from_html(html: str) -> set:
    """Extract valid emails from HTML content"""
    if not html:
        return set()
    
    # Find all email-like patterns
    raw_emails = EMAIL_PATTERN.findall(html)
    
    # Also check for mailto: links explicitly
    mailto_pattern = re.compile(r'mailto:([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7})', re.IGNORECASE)
    mailto_emails = mailto_pattern.findall(html)
    
    all_emails = set(raw_emails) | set(mailto_emails)
    
    # Filter valid emails
    valid_emails = {e.lower() for e in all_emails if is_valid_email(e)}
    
    return valid_emails


def detect_contact_form(html: str, url: str) -> tuple[bool, str]:
    """Detect if page has a contact form. Returns (has_form, form_url)"""
    if not html:
        return False, None
    
    html_lower = html.lower()
    
    # Check for form elements with contact-related attributes
    has_form_tag = '<form' in html_lower
    has_contact_indicators = any(ind in html_lower for ind in FORM_INDICATORS)
    
    # Check for contact form fields
    has_message_field = any(x in html_lower for x in ['textarea', 'type="message"', 'name="message"'])
    has_email_input = any(x in html_lower for x in ['type="email"', 'name="email"', 'id="email"'])
    has_name_input = any(x in html_lower for x in ['name="name"', 'id="name"', 'your name'])
    
    # Need form tag + indicators or multiple contact fields
    if has_form_tag and (has_contact_indicators or (has_message_field and has_email_input)):
        return True, url
    
    if has_form_tag and has_message_field and has_name_input:
        return True, url
    
    return False, None


def scrape_with_playwright(lead_id: int, business_name: str, website: str, browser) -> dict:
    """Scrape a single website using Playwright browser instance"""
    result = {
        'id': lead_id,
        'business_name': business_name,
        'emails_found': set(),
        'has_contact_form': False,
        'contact_form_url': None,
        'error': None
    }
    
    if not website:
        result['error'] = 'No website'
        return result
    
    # Normalize URL
    if not website.startswith(('http://', 'https://')):
        website = 'https://' + website
    
    try:
        page = browser.new_page()
        page.set_default_timeout(12000)  # 12 second timeout
        
        for path in CONTACT_PATHS:
            try:
                url = urljoin(website, path)
                
                # Navigate and wait for network idle
                page.goto(url, wait_until='networkidle', timeout=12000)
                
                # Get rendered HTML
                html = page.content()
                
                # Extract emails
                emails = extract_emails_from_html(html)
                result['emails_found'].update(emails)
                
                # Detect contact forms (only if no email found yet)
                if not result['emails_found'] and not result['has_contact_form']:
                    has_form, form_url = detect_contact_form(html, url)
                    if has_form:
                        result['has_contact_form'] = True
                        result['contact_form_url'] = form_url
                
                # If we found an email, we can stop early
                if result['emails_found']:
                    break
                    
            except PlaywrightTimeout:
                continue
            except Exception as e:
                continue
        
        page.close()
        
    except Exception as e:
        result['error'] = str(e)[:100]
    
    return result


def update_database(result: dict, conn: sqlite3.Connection):
    """Update database with scraping results"""
    c = conn.cursor()
    
    emails = result['emails_found']
    
    if emails:
        # Use the first email found
        email = sorted(emails)[0]
        c.execute("""UPDATE leads SET contact_email = ?, email_source = 'playwright_v4'
                    WHERE id = ? AND (contact_email IS NULL OR contact_email = '')""",
                  (email, result['id']))
        conn.commit()
        return 'email_found', email
    
    elif result['has_contact_form']:
        c.execute("""UPDATE leads SET has_contact_form = 1, contact_form_url = ?
                    WHERE id = ?""",
                  (result['contact_form_url'], result['id']))
        conn.commit()
        return 'contact_form', result['contact_form_url']
    
    return 'nothing', None


def get_candidates(conn: sqlite3.Connection, limit: int = 500) -> list:
    """Get leads that need email discovery"""
    c = conn.cursor()
    c.execute("""
        SELECT id, business_name, website FROM leads 
        WHERE tier IN ('A', 'B')
        AND (owner_email IS NULL OR owner_email = '')
        AND (contact_email IS NULL OR contact_email = '')
        AND website IS NOT NULL AND website != ''
        AND (has_contact_form IS NULL OR has_contact_form = 0)
        LIMIT ?
    """, (limit,))
    return c.fetchall()


def main():
    print(f"=" * 60)
    print(f"Email Discovery v4 - Playwright Scraper")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"=" * 60)
    
    conn = sqlite3.connect(DB_PATH)
    candidates = get_candidates(conn, limit=500)
    
    print(f"\nFound {len(candidates)} candidates to process")
    
    if not candidates:
        print("No candidates to process!")
        return
    
    # Stats tracking
    stats = {
        'processed': 0,
        'emails_found': 0,
        'contact_forms': 0,
        'errors': 0,
        'nothing': 0
    }
    
    with sync_playwright() as p:
        # Launch browser once
        browser = p.chromium.launch(headless=True)
        
        print(f"\nProcessing with Playwright (headless Chromium)...")
        print("-" * 60)
        
        for i, (lead_id, business_name, website) in enumerate(candidates, 1):
            try:
                result = scrape_with_playwright(lead_id, business_name, website, browser)
                status, data = update_database(result, conn)
                
                stats['processed'] += 1
                
                if status == 'email_found':
                    stats['emails_found'] += 1
                    print(f"[{i}/{len(candidates)}] ✅ EMAIL: {business_name[:30]} -> {data}")
                elif status == 'contact_form':
                    stats['contact_forms'] += 1
                    print(f"[{i}/{len(candidates)}] 📝 FORM: {business_name[:30]} -> {data[:50] if data else ''}")
                else:
                    stats['nothing'] += 1
                    if i % 20 == 0:
                        print(f"[{i}/{len(candidates)}] ... {business_name[:30]}")
                
                if result['error']:
                    stats['errors'] += 1
                    
            except Exception as e:
                stats['errors'] += 1
                print(f"[{i}/{len(candidates)}] ❌ ERROR: {business_name[:30]} - {str(e)[:50]}")
            
            # Progress checkpoint every 50
            if i % 50 == 0:
                print(f"\n--- Checkpoint at {i} ---")
                print(f"Emails: {stats['emails_found']}, Forms: {stats['contact_forms']}, Errors: {stats['errors']}")
                print("-" * 60)
        
        browser.close()
    
    # Final report
    print(f"\n" + "=" * 60)
    print(f"FINAL RESULTS")
    print(f"=" * 60)
    print(f"Processed: {stats['processed']}")
    print(f"Emails found: {stats['emails_found']}")
    print(f"Contact forms tagged: {stats['contact_forms']}")
    print(f"Nothing found: {stats['nothing']}")
    print(f"Errors: {stats['errors']}")
    
    # Check new coverage
    c = conn.cursor()
    c.execute("""SELECT COUNT(*) FROM leads WHERE tier IN ('A', 'B')""")
    total_ab = c.fetchone()[0]
    
    c.execute("""SELECT COUNT(*) FROM leads 
                 WHERE tier IN ('A', 'B')
                 AND ((owner_email IS NOT NULL AND owner_email != '')
                   OR (contact_email IS NOT NULL AND contact_email != ''))""")
    with_email_ab = c.fetchone()[0]
    
    c.execute("""SELECT COUNT(*) FROM leads WHERE tier IN ('A', 'B') AND has_contact_form = 1""")
    with_form_ab = c.fetchone()[0]
    
    print(f"\n--- Tier A/B Coverage ---")
    print(f"Total: {total_ab}")
    print(f"With email: {with_email_ab} ({with_email_ab/total_ab*100:.1f}%)")
    print(f"With contact form: {with_form_ab}")
    print(f"Combined reachable: {with_email_ab + with_form_ab} ({(with_email_ab + with_form_ab)/total_ab*100:.1f}%)")
    
    conn.close()
    print(f"\nCompleted: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == '__main__':
    main()
