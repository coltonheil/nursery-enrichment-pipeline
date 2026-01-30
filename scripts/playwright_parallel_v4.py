#!/usr/bin/env python3
"""
Email Discovery v4 - Parallel Playwright Scraper
Uses multiple browser contexts for concurrent processing
"""

import sqlite3
import re
import sys
import threading
from datetime import datetime
from urllib.parse import urljoin
from concurrent.futures import ThreadPoolExecutor, as_completed
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

DB_PATH = 'data/leads.db'
MAX_WORKERS = 5  # Number of concurrent browser contexts
PAGE_TIMEOUT = 8000  # 8 seconds per page (aggressive)

EMAIL_PATTERN = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b')

SKIP_PATTERNS = [
    r'@example\.', r'@test\.', r'@localhost', r'@sentry\.',
    r'@wixpress\.', r'@godaddy\.', r'@squarespace\.', r'@weebly\.',
    r'@shopify\.', r'@latofonts\.', r'@wordpress\.', r'@w3\.org',
    r'your@', r'email@', r'info@info\.', r'name@', r'@facebook\.',
    r'placeholder', r'sample', r'filler', r'noreply', r'no-reply',
    r'\.jpg$', r'\.png$', r'\.gif$', r'\.webp$', r'\.js$', r'\.css$',
]
SKIP_RE = re.compile('|'.join(SKIP_PATTERNS), re.IGNORECASE)

CONTACT_PATHS = ['/contact', '/contact-us', '/']  # Prioritize contact pages
FORM_INDICATORS = ['contact form', 'send message', 'get in touch', 'send us a message',
                   'submit', 'send inquiry', 'your message', 'your email']

# Thread-safe print
print_lock = threading.Lock()
def log(msg):
    with print_lock:
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


def scrape_single_site(args):
    """Scrape a single site using a new browser context"""
    lid, name, website, browser = args
    
    if not website:
        return lid, name, set(), False, None, "No website"
    
    if not website.startswith(('http://', 'https://')):
        website = 'https://' + website
    
    emails = set()
    has_form = False
    form_url = None
    error = None
    
    try:
        context = browser.new_context()
        page = context.new_page()
        page.set_default_timeout(PAGE_TIMEOUT)
        
        for path in CONTACT_PATHS:
            try:
                url = urljoin(website, path)
                page.goto(url, wait_until='domcontentloaded', timeout=PAGE_TIMEOUT)
                
                # Wait a bit for JS to execute
                page.wait_for_timeout(1000)
                
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
            except Exception as e:
                continue
        
        context.close()
        
    except Exception as e:
        error = str(e)[:80]
    
    return lid, name, emails, has_form, form_url, error


# Thread-safe database access
db_lock = threading.Lock()

def update_db(conn, lid, emails, has_form, form_url):
    """Update database with thread safety"""
    with db_lock:
        c = conn.cursor()
        if emails:
            email = sorted(emails)[0]
            c.execute("""UPDATE leads SET contact_email = ?, email_source = 'playwright_v4'
                        WHERE id = ? AND (contact_email IS NULL OR contact_email = '')""",
                      (email, lid))
            conn.commit()
            return 'email', email
        elif has_form:
            c.execute("""UPDATE leads SET has_contact_form = 1, contact_form_url = ?
                        WHERE id = ?""", (form_url, lid))
            conn.commit()
            return 'form', form_url
        return None, None


def main():
    log("=" * 60)
    log(f"Email Discovery v4 - Parallel Playwright ({MAX_WORKERS} workers)")
    log(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log("=" * 60)
    
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
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
    stats = {'emails': 0, 'forms': 0, 'errors': 0, 'nothing': 0}
    
    with sync_playwright() as p:
        log("\nLaunching Chromium...")
        browser = p.chromium.launch(headless=True)
        log(f"Browser ready! Processing with {MAX_WORKERS} workers...\n")
        
        # Process in batches for better progress tracking
        batch_size = 20
        processed = 0
        
        for batch_start in range(0, len(candidates), batch_size):
            batch = candidates[batch_start:batch_start + batch_size]
            tasks = [(lid, name, website, browser) for lid, name, website in batch]
            
            with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
                futures = {executor.submit(scrape_single_site, t): t for t in tasks}
                
                for future in as_completed(futures):
                    lid, name, emails, has_form, form_url, err = future.result()
                    processed += 1
                    
                    result_type, data = update_db(conn, lid, emails, has_form, form_url)
                    
                    if result_type == 'email':
                        stats['emails'] += 1
                        log(f"[{processed}/{len(candidates)}] ✅ EMAIL: {name[:32]} -> {data}")
                    elif result_type == 'form':
                        stats['forms'] += 1
                        log(f"[{processed}/{len(candidates)}] 📝 FORM: {name[:32]}")
                    else:
                        stats['nothing'] += 1
                    
                    if err:
                        stats['errors'] += 1
            
            # Progress checkpoint
            log(f"\n--- Batch done: {processed}/{len(candidates)} | "
                f"Emails: {stats['emails']}, Forms: {stats['forms']} ---\n")
        
        browser.close()
    
    # Final stats
    log("\n" + "=" * 60)
    log("FINAL RESULTS")
    log("=" * 60)
    log(f"Processed: {processed}")
    log(f"Emails found: {stats['emails']}")
    log(f"Contact forms tagged: {stats['forms']}")
    log(f"Nothing found: {stats['nothing']}")
    log(f"Errors: {stats['errors']}")
    
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
