#!/usr/bin/env python3
"""
Email Discovery v4 - Single-threaded Playwright (no parallelism issues)
"""
import sqlite3
import re
import sys
from datetime import datetime
from urllib.parse import urljoin
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

DB_PATH = 'data/leads.db'
PAGE_TIMEOUT = 8000  # 8 seconds

EMAIL_PATTERN = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b')
SKIP_RE = re.compile(r'@example\.|@test\.|@sentry\.|@wixpress\.|@godaddy\.|@squarespace\.|@shopify\.|@latofonts\.|@wordpress\.|@w3\.org|your@|email@|name@|placeholder|sample|filler|noreply|\.jpg$|\.png$|\.gif$|\.webp$|\.js$|\.css$|@facebook\.|@twitter\.', re.I)
CONTACT_PATHS = ['/contact', '/contact-us', '/']  # Contact first, then homepage
FORM_INDICATORS = ['contact form', 'send message', 'get in touch', 'submit', 'your message', 'your email']


def log(msg):
    print(msg, flush=True)


def is_valid(email):
    email = email.lower().strip()
    if len(email) < 6 or len(email) > 254 or SKIP_RE.search(email):
        return False
    parts = email.split('@')
    return len(parts) == 2 and '.' in parts[1]


def extract_emails(html):
    raw = EMAIL_PATTERN.findall(html or '')
    mailto = re.findall(r'mailto:([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7})', html or '', re.I)
    return {e.lower() for e in (set(raw) | set(mailto)) if is_valid(e)}


def detect_form(html, url):
    h = (html or '').lower()
    if '<form' in h and (any(x in h for x in FORM_INDICATORS) or ('textarea' in h and 'email' in h)):
        return True, url
    return False, None


def main():
    log("=" * 60)
    log(f"Email Discovery v4 - Sequential Playwright")
    log(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log("=" * 60)
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    c.execute("""SELECT id, business_name, website FROM leads 
        WHERE tier IN ('A', 'B')
        AND (owner_email IS NULL OR owner_email = '')
        AND (contact_email IS NULL OR contact_email = '')
        AND website IS NOT NULL AND website != ''
        AND (has_contact_form IS NULL OR has_contact_form = 0)
        LIMIT 500""")
    candidates = c.fetchall()
    
    log(f"\nCandidates: {len(candidates)}\n")
    
    if not candidates:
        log("No candidates!")
        return
    
    emails_found = 0
    forms_found = 0
    errors = 0
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        
        for i, (lid, name, website) in enumerate(candidates, 1):
            if not website:
                continue
            
            if not website.startswith(('http://', 'https://')):
                website = 'https://' + website
            
            emails = set()
            has_form = False
            form_url = None
            
            try:
                ctx = browser.new_context()
                page = ctx.new_page()
                page.set_default_timeout(PAGE_TIMEOUT)
                
                for path in CONTACT_PATHS:
                    try:
                        url = urljoin(website, path)
                        page.goto(url, wait_until='domcontentloaded', timeout=PAGE_TIMEOUT)
                        page.wait_for_timeout(500)  # Brief wait for JS
                        html = page.content()
                        
                        found = extract_emails(html)
                        emails.update(found)
                        
                        if not emails and not has_form:
                            has_form, form_url = detect_form(html, url)
                        
                        if emails:
                            break
                    except:
                        continue
                
                ctx.close()
                
                # Update database
                if emails:
                    email = sorted(emails)[0]
                    c.execute("""UPDATE leads SET contact_email = ?, email_source = 'playwright_v4'
                                WHERE id = ? AND (contact_email IS NULL OR contact_email = '')""",
                              (email, lid))
                    conn.commit()
                    emails_found += 1
                    log(f"[{i}/{len(candidates)}] ✅ {name[:35]} -> {email}")
                elif has_form:
                    c.execute("""UPDATE leads SET has_contact_form = 1, contact_form_url = ?
                                WHERE id = ?""", (form_url, lid))
                    conn.commit()
                    forms_found += 1
                    log(f"[{i}/{len(candidates)}] 📝 {name[:35]}")
                elif i % 30 == 0:
                    log(f"[{i}/{len(candidates)}] ... {emails_found} emails, {forms_found} forms")
                    
            except Exception as e:
                errors += 1
            
            # Progress checkpoint
            if i % 100 == 0:
                log(f"\n--- {i}: {emails_found} emails, {forms_found} forms ---\n")
        
        browser.close()
    
    # Final report
    log("\n" + "=" * 60)
    log("FINAL RESULTS")
    log("=" * 60)
    log(f"Processed: {len(candidates)}")
    log(f"Emails found: {emails_found}")
    log(f"Contact forms: {forms_found}")
    log(f"Errors: {errors}")
    
    c.execute("SELECT COUNT(*) FROM leads WHERE tier IN ('A', 'B')")
    total = c.fetchone()[0]
    c.execute("""SELECT COUNT(*) FROM leads WHERE tier IN ('A', 'B')
                 AND ((owner_email IS NOT NULL AND owner_email != '')
                   OR (contact_email IS NOT NULL AND contact_email != ''))""")
    with_email = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM leads WHERE tier IN ('A', 'B') AND has_contact_form = 1")
    with_form = c.fetchone()[0]
    
    log(f"\n--- Final Coverage ---")
    log(f"Tier A/B: {with_email}/{total} ({with_email/total*100:.1f}%)")
    log(f"Contact forms: {with_form}")
    log(f"Reachable: {with_email + with_form} ({(with_email+with_form)/total*100:.1f}%)")
    
    conn.close()
    log(f"\nDone: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == '__main__':
    main()
