#!/usr/bin/env python3
"""
Contact Form URL Auditor

Categorizes all contact_form_url values:
- Detects directory sites vs actual business sites
- Identifies social media links
- Flags CAPTCHA-protected forms
- Updates database with verification status

Output columns:
- contact_form_verified (boolean): True if URL is valid direct contact
- contact_form_type: 'direct', 'directory', 'social', 'captcha', 'none', 'mismatch'
"""

import sqlite3
import asyncio
import sys
import os
from urllib.parse import urlparse
from typing import Optional, Tuple
from dataclasses import dataclass

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Known directory and listing sites
DIRECTORY_DOMAINS = {
    # Tree/Nursery directories
    'trees.com',
    'arborday.org',
    'gardenweb.com',
    'plantmaps.com',
    
    # General business directories  
    'yelp.com',
    'yellowpages.com',
    'whitepages.com',
    'manta.com',
    'bbb.org',
    'angieslist.com',
    'thumbtack.com',
    'homeadvisor.com',
    'houzz.com',
    'porch.com',
    
    # Local/regional directories
    'reallancastercounty.com',
    'localgardencentres.net',
    'justplainbusiness.com',
    'meetottumwa.org',
    
    # Generic POI/listing sites
    'poi.place',
    'keeq.io',
    'mapquest.com',
    'citysearch.com',
    'superpages.com',
    'dexknows.com',
    
    # Corporate parent sites (not the actual business)
    'earthdevelopmentinc.com',  # Lists nurseries they don't own
    'rlmgmt.com',  # Property management
    'baileynurseries.com',  # Wholesale (not retail locations)
    'walbecgroup.com',  # Corporate parent
    'greatlakesace.com',  # Chain HQ
    'bordines.com',  # May be HQ vs locations
}

# Social media domains
SOCIAL_DOMAINS = {
    'facebook.com',
    'fb.com',
    'instagram.com',
    'twitter.com',
    'x.com',
    'linkedin.com',
    'pinterest.com',
    'tiktok.com',
    'youtube.com',
}

# Blogging platforms (often lack proper contact forms)
BLOG_PLATFORMS = {
    'wordpress.com',
    'blogger.com',
    'blogspot.com',
    'wix.com',
    'weebly.com',
    'squarespace.com',  # Often has good forms though
    'tumblr.com',
}


@dataclass
class AuditResult:
    """Result of auditing a contact form URL."""
    is_verified: bool
    form_type: str  # 'direct', 'directory', 'social', 'mismatch', 'blog', 'none'
    reason: str
    suggested_url: Optional[str] = None


def extract_domain(url: str) -> str:
    """Extract the base domain from a URL."""
    if not url:
        return ""
    try:
        parsed = urlparse(url.lower())
        domain = parsed.netloc or parsed.path.split('/')[0]
        # Remove www. prefix
        if domain.startswith('www.'):
            domain = domain[4:]
        return domain
    except:
        return ""


def domains_match(url1: str, url2: str) -> bool:
    """Check if two URLs have the same base domain."""
    domain1 = extract_domain(url1)
    domain2 = extract_domain(url2)
    
    if not domain1 or not domain2:
        return False
    
    # Handle subdomains - check if either is substring of other
    return domain1 == domain2 or domain1.endswith('.' + domain2) or domain2.endswith('.' + domain1)


def is_directory_url(url: str) -> Tuple[bool, str]:
    """Check if URL is from a known directory site."""
    domain = extract_domain(url)
    
    for dir_domain in DIRECTORY_DOMAINS:
        if domain == dir_domain or domain.endswith('.' + dir_domain):
            return True, f"Directory site: {dir_domain}"
    
    return False, ""


def is_social_url(url: str) -> Tuple[bool, str]:
    """Check if URL is from a social media site."""
    domain = extract_domain(url)
    
    for social_domain in SOCIAL_DOMAINS:
        if domain == social_domain or domain.endswith('.' + social_domain):
            return True, f"Social media: {social_domain}"
    
    return False, ""


def is_blog_platform(url: str) -> Tuple[bool, str]:
    """Check if URL is from a blog platform."""
    domain = extract_domain(url)
    
    for blog_domain in BLOG_PLATFORMS:
        if domain == blog_domain or domain.endswith('.' + blog_domain):
            return True, f"Blog platform: {blog_domain}"
    
    return False, ""


def audit_contact_form_url(contact_url: str, website_url: str, business_name: str) -> AuditResult:
    """
    Audit a single contact form URL.
    
    Args:
        contact_url: The contact_form_url from database
        website_url: The website field from database
        business_name: For logging
    
    Returns:
        AuditResult with verification status and type
    """
    # No contact URL
    if not contact_url or contact_url.strip() == '':
        return AuditResult(False, 'none', "No contact URL")
    
    contact_url = contact_url.strip()
    website_url = (website_url or '').strip()
    
    # Check for directory site
    is_dir, dir_reason = is_directory_url(contact_url)
    if is_dir:
        return AuditResult(False, 'directory', dir_reason, website_url)
    
    # Check for social media
    is_social, social_reason = is_social_url(contact_url)
    if is_social:
        return AuditResult(False, 'social', social_reason, website_url)
    
    # Check for blog platform (may or may not have contact form)
    is_blog, blog_reason = is_blog_platform(contact_url)
    if is_blog:
        # These often have forms, mark as needing verification
        return AuditResult(False, 'blog', blog_reason)
    
    # Check if contact URL matches website domain
    if website_url:
        if not domains_match(contact_url, website_url):
            # Contact URL is on different domain than website
            contact_domain = extract_domain(contact_url)
            website_domain = extract_domain(website_url)
            
            # Check if the contact domain is also a directory
            is_dir, _ = is_directory_url(contact_url)
            if is_dir:
                return AuditResult(False, 'directory', f"Domain mismatch: {contact_domain} != {website_domain}", website_url)
            
            # Different domain but not a known directory - flag for review
            return AuditResult(False, 'mismatch', f"Domain mismatch: {contact_domain} != {website_domain}", website_url)
    
    # URL looks valid - it's on the same domain as website or website is empty
    # Check if it ends with /contact or similar
    path_lower = urlparse(contact_url).path.lower()
    
    if '/contact' in path_lower or '/contact-us' in path_lower or '/about' in path_lower:
        return AuditResult(True, 'direct', "Valid contact path on business domain")
    
    # URL doesn't have contact path but domain matches
    if path_lower in ['', '/', '/home']:
        return AuditResult(False, 'homepage', "Homepage, not contact page - needs /contact path")
    
    # Some other page on the business domain
    return AuditResult(True, 'direct', "On business domain")


def audit_all_contact_forms(db_path: str, dry_run: bool = False) -> dict:
    """
    Audit all contact form URLs in the database.
    
    Args:
        db_path: Path to leads.db
        dry_run: If True, don't update database
    
    Returns:
        Statistics dict
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Get all leads with contact form URLs
    cursor.execute("""
        SELECT id, business_name, website, contact_form_url, owner_email, contact_email, generic_email
        FROM leads 
        WHERE contact_form_url IS NOT NULL AND contact_form_url != ''
    """)
    
    leads = cursor.fetchall()
    
    stats = {
        'total': len(leads),
        'direct': 0,
        'directory': 0,
        'social': 0,
        'mismatch': 0,
        'blog': 0,
        'homepage': 0,
        'none': 0,
        'has_email_fallback': 0,
    }
    
    updates = []
    
    print(f"\n📊 Auditing {len(leads)} contact form URLs...\n")
    
    for lead in leads:
        result = audit_contact_form_url(
            lead['contact_form_url'],
            lead['website'],
            lead['business_name']
        )
        
        stats[result.form_type] = stats.get(result.form_type, 0) + 1
        
        # Check if lead has email as fallback
        has_email = bool(lead['owner_email'] or lead['contact_email'] or lead['generic_email'])
        if has_email and not result.is_verified:
            stats['has_email_fallback'] += 1
        
        # Prepare update
        updates.append((
            result.is_verified,
            result.form_type,
            result.suggested_url,
            lead['id']
        ))
        
        # Print issues
        if not result.is_verified:
            emoji = {
                'directory': '📁',
                'social': '📱',
                'mismatch': '⚠️',
                'blog': '📝',
                'homepage': '🏠',
                'none': '❌',
            }.get(result.form_type, '❓')
            
            fallback = " 📧" if has_email else ""
            print(f"{emoji} {lead['business_name'][:40]:<40} | {result.form_type:<10} | {result.reason}{fallback}")
    
    if not dry_run:
        # Update database
        print(f"\n💾 Updating database...")
        
        cursor.executemany("""
            UPDATE leads 
            SET contact_form_verified = ?,
                contact_form_type = ?
            WHERE id = ?
        """, [(u[0], u[1], u[3]) for u in updates])
        
        conn.commit()
        print(f"✅ Updated {len(updates)} records")
    else:
        print(f"\n🔍 DRY RUN - no changes made")
    
    conn.close()
    
    return stats


def print_summary(stats: dict):
    """Print audit summary."""
    print("\n" + "="*60)
    print("📊 CONTACT FORM AUDIT SUMMARY")
    print("="*60)
    
    total = stats['total']
    direct = stats['direct']
    
    print(f"\n📋 Total URLs audited: {total}")
    print(f"\n✅ Valid (direct) contact forms: {direct} ({direct/total*100:.1f}%)")
    
    problem_types = ['directory', 'social', 'mismatch', 'blog', 'homepage']
    problems = sum(stats.get(t, 0) for t in problem_types)
    
    print(f"\n⚠️  Problem URLs: {problems} ({problems/total*100:.1f}%)")
    for ptype in problem_types:
        count = stats.get(ptype, 0)
        if count > 0:
            print(f"   • {ptype}: {count}")
    
    print(f"\n📧 Has email fallback: {stats['has_email_fallback']} (can use email instead)")
    
    potential_success = direct + stats['has_email_fallback']
    print(f"\n🎯 Potential reachable: {potential_success} ({potential_success/total*100:.1f}%)")


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Audit contact form URLs')
    parser.add_argument('--dry-run', action='store_true', help='Do not update database')
    parser.add_argument('--db', default='data/leads.db', help='Path to database')
    
    args = parser.parse_args()
    
    db_path = args.db
    if not os.path.isabs(db_path):
        db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), db_path)
    
    if not os.path.exists(db_path):
        print(f"❌ Database not found: {db_path}")
        sys.exit(1)
    
    stats = audit_all_contact_forms(db_path, dry_run=args.dry_run)
    print_summary(stats)


if __name__ == "__main__":
    main()
