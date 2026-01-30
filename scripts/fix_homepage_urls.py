#!/usr/bin/env python3
"""
Fix Homepage URLs - Simple synchronous version.
Finds /contact paths for homepage-type URLs.
"""

import sqlite3
import requests
import sys
import os
from urllib.parse import urljoin, urlparse

# Suppress SSL warnings
import urllib3
urllib3.disable_warnings()

CONTACT_PATHS = ['/contact', '/contact-us', '/contactus', '/contact/', '/contact-us/']

FORM_INDICATORS = ['<form', 'contact-form', 'wpcf7', 'type="email"', 'name="email"']


def has_contact_form(html: str) -> bool:
    """Check if HTML has form indicators."""
    html_lower = html.lower()
    return any(ind in html_lower for ind in FORM_INDICATORS)


def find_contact_path(base_url: str) -> tuple:
    """Try to find /contact path. Returns (url, has_form)."""
    headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)'}
    
    for path in CONTACT_PATHS:
        try:
            url = urljoin(base_url, path)
            resp = requests.get(url, headers=headers, timeout=10, verify=False, allow_redirects=True)
            if resp.status_code == 200:
                if has_contact_form(resp.text):
                    return str(resp.url), True
        except:
            continue
    
    # Check homepage
    try:
        resp = requests.get(base_url, headers=headers, timeout=10, verify=False, allow_redirects=True)
        if resp.status_code == 200 and has_contact_form(resp.text):
            return str(resp.url), True
    except:
        pass
    
    return None, False


def main():
    db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data/leads.db')
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT id, business_name, website, contact_form_url 
        FROM leads WHERE contact_form_type = 'homepage'
    """)
    leads = cursor.fetchall()
    
    print(f"Processing {len(leads)} homepage leads...\n")
    
    found = 0
    not_found = 0
    updates = []
    
    for lead_id, name, website, old_url in leads:
        print(f"[{found+not_found+1}/{len(leads)}] {name[:40]:<40}", end=' ')
        
        if not website:
            print("❌ No website")
            not_found += 1
            continue
        
        url, has_form = find_contact_path(website)
        
        if url and has_form:
            print(f"✅ {url[:50]}")
            updates.append((url, True, 'direct', lead_id))
            found += 1
        else:
            print("❌ No form found")
            not_found += 1
    
    # Update DB
    if updates:
        print(f"\n💾 Updating {len(updates)} records...")
        cursor.executemany("""
            UPDATE leads SET contact_form_url=?, contact_form_verified=?, contact_form_type=?
            WHERE id=?
        """, updates)
        conn.commit()
    
    conn.close()
    print(f"\n✅ Found: {found}, ❌ Not found: {not_found}")


if __name__ == "__main__":
    main()
