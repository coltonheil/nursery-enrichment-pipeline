#!/usr/bin/env python3
"""
Email Discovery v4b - Playwright Scraper (with immediate output)
"""

import sqlite3
import re
import sys
from datetime import datetime
from urllib.parse import urljoin
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

DB_PATH = 'data/leads.db'

EMAIL_PATTERN = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b')

SKIP_PATTERNS = [
    r'@example\.', r'@test\.', r'@localhost', r'@sentry\.',
    r'@wixpress\.', r'@godaddy\.', r'@squarespace\.', r'@weebly\.',
    r'@shopify\.', r'@latofonts\.', r'@wordpress\.', r'@w3\.org',
    r'your@', r'email@', r'info@info\.', r'name@',
    r'placeholder', r'sample', r'filler',
    r'\.jpg$', r'\.png$', r'\.gif$', r'\.webp$', r'\.js$', r'\.css$',
]
SKIP_RE = re.compile('|'.join(SKIP_PATTERNS), re.IGNORECASE)

CONTACT_PATHS = ['/', '/contact', '/contact-us', '/about', '/about-us']
FORM_INDICATORS = ['contact form', 'send message', 'get in touch', 'send us a message',
                   'submit', 'send inquiry', 'your message', 'your name', 'your email']


def log(msg):
    print(msg, flush=True)


def is_valid_email(email):
    email = email.lower().strip()
    if len(email) < 6 or len(email) > 254:
        return False
    if SKIP_RE.search(email):
        return False
    parts = email.split('@')
    if len(parts) != 2 or '.' not in parts[1]:
        return False
    return True


def extract_emails(html):
    if not html:
        return set()
    raw = EMAIL_PATTERN.findall(html)
    mailto = re.findall(r'mailto:([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7})', html, re.I)
    return {e.lower() for e in (set(raw) | set(mailto)) if is_valid_email(e)}


def detect_form(html, url):
    if not html:
        return False, None
    h = html.lower()
    if '<form' in h:
        if any(x in h for x in FORM_INDICATORS):
            return True, url
        if 'textarea' in h and ('type="email"' in h or 'name="email"' in h):
            return True, url
    return False, None


def scrape_site(browser, website):
    """Returns (emails_set, has_form, form_url, error)"""
    if not website:
        return set(), False, None, "No website"
    
    if not website.startswith(('http://', 'https://')):
        website = 'https://' + website
    
    emails = set()
    has_form = False
    form_url = None
    
    try:
        page = browser.new_page()
        page.set_default_timeout(12000)
        
        for path in CONTACT_PATHS:
            try:
                url = urljoin(website, path)
                page.goto(url, wait_until='networkidle', timeout=12000)
                html = page.content()
                
                # Extract emails
                found = extract_emails(html)
                emails.update(found)
                
                # Detect form if no email yet
                if not emails and not has_form:
                    has_form, form_url = detect_form(html, url)
                
                # Stop early if email found
                if emails:
                    break
                    
            except PlaywrightTimeout:
                continue
            except Exception:
                continue
        
        page.close()
        return emails, has_form, form_url, None
        
    except Exception as e:
        return emails, has_form, form_url, str(e)[:80]


def main():
    log("=" * 60)
    log(f"Email Discovery v4b - Playwright Scraper")
    log(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log("=" * 60)
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # Get candidates
    c.execute("""
        SELECT id, business_name, website FROM leads 
        WHERE tier IN ('A', 'B')
        AND (owner_email IS NULL OR owner_email = '')
        AND (contact_email IS NULL OR contact_email = '')
        AND website IS NOT NULL AND website != ''
        AND (has_contact_form IS NULL OR has_contact_form = 0)
        LIMIT 500
    """)
    candidates = c.fetchall()
    
    log(f"\nCandidates: {len(candidates)}")
    
    if not candidates:
        log("No candidates!")
        return
    
    # Stats
    emails_found = 0
    forms_found = 0
    errors = 0
    nothing = 0
    
    with sync_playwright() as p:
        log("\nLaunching Chromium...")
        browser = p.chromium.launch(headless=True)
        log("Browser ready!\n")
        
        for i, (lid, name, website) in enumerate(candidates, 1):
            try:
                emails, has_form, form_url, err = scrape_site(browser, website)
                
                if emails:
                    email = sorted(emails)[0]
                    c.execute("""UPDATE leads SET contact_email = ?, email_source = 'playwright_v4'
                                WHERE id = ? AND (contact_email IS NULL OR contact_email = '')""",
                              (email, lid))
                    conn.commit()
                    emails_found += 1
                    log(f"[{i}/{len(candidates)}] ✅ EMAIL: {name[:35]} -> {email}")
                    
                elif has_form:
                    c.execute("""UPDATE leads SET has_contact_form = 1, contact_form_url = ?
                                WHERE id = ?""", (form_url, lid))
                    conn.commit()
                    forms_found += 1
                    log(f"[{i}/{len(candidates)}] 📝 FORM: {name[:35]}")
                    
                else:
                    nothing += 1
                    if i % 25 == 0:
                        log(f"[{i}/{len(candidates)}] ... {emails_found} emails, {forms_found} forms so far")
                
                if err:
                    errors += 1
                    
            except Exception as e:
                errors += 1
                log(f"[{i}/{len(candidates)}] ❌ ERR: {name[:30]} - {str(e)[:40]}")
            
            # Progress checkpoint
            if i % 50 == 0:
                log(f"\n--- {i} processed: {emails_found} emails, {forms_found} forms, {errors} errors ---\n")
        
        browser.close()
    
    # Final stats
    log("\n" + "=" * 60)
    log("RESULTS")
    log("=" * 60)
    log(f"Processed: {len(candidates)}")
    log(f"Emails found: {emails_found}")
    log(f"Contact forms tagged: {forms_found}")
    log(f"Nothing found: {nothing}")
    log(f"Errors: {errors}")
    
    # Coverage check
    c.execute("SELECT COUNT(*) FROM leads WHERE tier IN ('A', 'B')")
    total = c.fetchone()[0]
    
    c.execute("""SELECT COUNT(*) FROM leads WHERE tier IN ('A', 'B')
                 AND ((owner_email IS NOT NULL AND owner_email != '')
                   OR (contact_email IS NOT NULL AND contact_email != ''))""")
    with_email = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM leads WHERE tier IN ('A', 'B') AND has_contact_form = 1")
    with_form = c.fetchone()[0]
    
    log(f"\n--- Tier A/B Coverage ---")
    log(f"Total: {total}")
    log(f"With email: {with_email} ({with_email/total*100:.1f}%)")
    log(f"With contact form: {with_form}")
    log(f"Reachable: {with_email + with_form} ({(with_email+with_form)/total*100:.1f}%)")
    
    conn.close()
    log(f"\nDone: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == '__main__':
    main()
