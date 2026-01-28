#!/usr/bin/env python3
"""
Phase 0: Website Discovery for Tier U Leads
Searches Brave to find business websites for leads without them.
"""

import os
import re
import sqlite3
import sys
import time
from datetime import datetime
from urllib.parse import urlparse

import requests

sys.stdout.reconfigure(line_buffering=True)
sys.stderr.reconfigure(line_buffering=True)

# Load .env
from pathlib import Path
env_path = Path(__file__).parent / '.env'
if env_path.exists():
    for line in env_path.read_text().splitlines():
        if '=' in line and not line.startswith('#'):
            k, v = line.split('=', 1)
            os.environ.setdefault(k.strip(), v.strip())

DB_PATH = 'data/leads.db'
BRAVE_API_KEY = os.getenv('BRAVE_API_KEY')

# Domains to skip (social media, directories, aggregators, etc.)
SKIP_DOMAINS = {
    # Social media
    'facebook.com', 'fb.com', 'm.facebook.com',
    'twitter.com', 'x.com',
    'instagram.com',
    'linkedin.com',
    'youtube.com',
    'pinterest.com',
    'tiktok.com',
    # Business directories
    'yelp.com',
    'yellowpages.com', 'yp.com',
    'bbb.org',
    'manta.com',
    'buzzfile.com',
    'chamberofcommerce.com',
    'dnb.com',
    'zoominfo.com',
    'opencorporates.com',
    'findglocal.com',
    'cylex.us.com',
    'hotfrog.com',
    'thebluebook.com',
    'porch.com',
    'houzz.com',
    'homeadvisor.com',
    'angieslist.com', 'angi.com',
    'thumbtack.com',
    'buildzoom.com',
    'wellness.com',
    'brokersnapshot.com',
    'bizapedia.com',
    'corporationwiki.com',
    'opengovus.com',
    'uscompanies.com',
    'northdata.com',
    'spoke.com',
    'dandb.com',
    'owler.com',
    'crunchbase.com',
    # Maps and local
    'mapquest.com',
    'google.com',
    'apple.com',
    'bing.com',
    'foursquare.com',
    # Travel / reviews
    'tripadvisor.com',
    # Jobs
    'indeed.com',
    'glassdoor.com',
    'ziprecruiter.com',
    # News / media
    'crowrivermedia.com',
    'patch.com',
    # Government / misc
    'sec.gov',
    'state.gov',
    'usda.gov',
    # Wiki / info aggregators
    'wikizer.com',
    'wikipedia.org',
    'wikidata.org',
    'wikimedia.org',
    # Additional directories found during testing
    'nextdoor.com', 'us.nextdoor.com', 'join.nextdoor.com',
    'cmac.ws',
    'hub.biz',
    'siccode.com',
    'cortera.com', 'start.cortera.com',
    'fmcsa.dot.gov', 'safer.fmcsa.dot.gov',
    'local.yahoo.com', 'yahoo.com',
    'z1biz.com',
    'foodmarketmaker.com',
    'localdifference.org',
    'yardbook.com',
    'landscape.com',
    'davesgarden.com',
    'duluthdirect.us',
    'michigan.org',
    'etsy.com',
    'pinterest.com',
    # More directories found in testing
    'gardencenterguide.com',
    'michigancorporates.com',
    'homemove.biz',
    'iowanla.org',
    'wheree.com',
}

# Keywords that suggest a nursery/greenhouse website
NURSERY_KEYWORDS = [
    'nursery', 'greenhouse', 'garden', 'plant', 'tree', 'farm',
    'grower', 'landscap', 'floral', 'flower', 'shrub', 'perennial',
    'annual', 'wholesale', 'retail', 'horticulture'
]


def brave_search(query: str, count: int = 5) -> list:
    """Search using Brave Search API."""
    if not BRAVE_API_KEY:
        raise ValueError("BRAVE_API_KEY not set")
    
    url = "https://api.search.brave.com/res/v1/web/search"
    headers = {
        "Accept": "application/json",
        "X-Subscription-Token": BRAVE_API_KEY
    }
    params = {
        "q": query,
        "count": count,
        "safesearch": "off"
    }
    
    response = requests.get(url, headers=headers, params=params, timeout=15)
    response.raise_for_status()
    
    data = response.json()
    
    # Extract results
    results = []
    if 'web' in data and 'results' in data['web']:
        results = data['web']['results']
    
    return results


def extract_domain(url: str) -> str:
    """Extract domain from URL."""
    try:
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        if domain.startswith('www.'):
            domain = domain[4:]
        return domain
    except:
        return ''


def is_skip_domain(url: str) -> bool:
    """Check if URL is from a domain we should skip."""
    domain = extract_domain(url)
    
    # Check exact match
    if domain in SKIP_DOMAINS:
        return True
    
    # Check if subdomain of skip domain
    for skip in SKIP_DOMAINS:
        if domain.endswith('.' + skip):
            return True
    
    return False


def score_result(result: dict, business_name: str, city: str, state: str) -> int:
    """Score how likely this result is the business's actual website."""
    score = 0
    url = result.get('url', '').lower()
    title = result.get('title', '').lower()
    description = result.get('description', '').lower()
    domain = extract_domain(url)
    
    # Skip social media / directories
    if is_skip_domain(url):
        return -100
    
    # Business name in domain is strong signal
    name_parts = business_name.lower().split()
    for part in name_parts:
        if len(part) > 3 and part in domain:
            score += 30
    
    # Business name in title
    name_lower = business_name.lower()
    if name_lower in title:
        score += 20
    elif any(p in title for p in name_parts if len(p) > 3):
        score += 10
    
    # Location match
    if city.lower() in title or city.lower() in description:
        score += 10
    if state.lower() in title or state.lower() in description:
        score += 5
    
    # Nursery keywords
    combined = title + ' ' + description + ' ' + domain
    for keyword in NURSERY_KEYWORDS:
        if keyword in combined:
            score += 5
            break
    
    # Penalize obviously wrong results
    if 'obituary' in combined or 'death' in combined:
        score -= 50
    if 'linkedin.com/in/' in url:
        score -= 50
    
    # Prefer .com, .net, .org
    if domain.endswith('.com') or domain.endswith('.net') or domain.endswith('.org'):
        score += 5
    
    return score


def find_website(business_name: str, city: str, state: str) -> dict:
    """Search for and return the most likely website for a business."""
    
    # Clean business name (remove suffixes like LLC, Inc, etc.)
    clean_name = business_name
    for suffix in [' LLC', ' INC', ' CORP', ' CO', ' DBA', ' LTD', ' LP']:
        clean_name = clean_name.replace(suffix, '')
    clean_name = clean_name.strip()
    
    # Try multiple search queries (NO QUOTES - quotes kill results!)
    queries = [
        f'{clean_name} {city} {state} official website',
        f'{clean_name} nursery {state}',
    ]
    
    all_results = []
    for query in queries:
        try:
            results = brave_search(query, count=5)
            all_results.extend(results)
        except Exception as e:
            continue
        
        # Rate limit between queries
        time.sleep(0.5)
    
    if not all_results:
        return {'success': False, 'error': 'No results', 'website': None}
    
    # Deduplicate by URL
    seen_urls = set()
    unique_results = []
    for r in all_results:
        url = r.get('url', '')
        if url not in seen_urls:
            seen_urls.add(url)
            unique_results.append(r)
    
    # Score each result
    scored = []
    for r in unique_results:
        score = score_result(r, business_name, city, state)
        scored.append({
            'url': r.get('url'),
            'title': r.get('title'),
            'score': score,
            'domain': extract_domain(r.get('url', ''))
        })
    
    # Sort by score
    scored.sort(key=lambda x: x['score'], reverse=True)
    
    # Return best result if score is reasonably high
    best = scored[0]
    if best['score'] >= 15:  # Minimum threshold for confidence
        return {
            'success': True,
            'website': best['url'],
            'domain': best['domain'],
            'score': best['score'],
            'title': best['title']
        }
    else:
        return {
            'success': False,
            'error': 'No confident match found',
            'website': None,
            'top_result': best
        }


def discover_websites(limit: int = 100, dry_run: bool = False):
    """Discover websites for Tier U leads."""
    
    print("=" * 80)
    print("TIER U WEBSITE DISCOVERY")
    print("=" * 80)
    print()
    
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Get Tier U leads without websites (prioritize likely nurseries)
    # Expanded criteria to catch lawn care, turf, sod, flowers, etc.
    query = """
        SELECT id, business_name, city, state
        FROM leads
        WHERE tier = 'U'
          AND (website IS NULL OR website = '' OR website LIKE '%facebook%')
          AND (
            business_name LIKE '%NURSERY%'
            OR business_name LIKE '%GREENHOUSE%'
            OR business_name LIKE '%GARDEN%'
            OR business_name LIKE '%TREE%'
            OR business_name LIKE '%FARM%'
            OR business_name LIKE '%LANDSCAP%'
            OR business_name LIKE '%GROWER%'
            OR business_name LIKE '%FLORAL%'
            OR business_name LIKE '%PLANT%'
            OR business_name LIKE '%LAWN%'
            OR business_name LIKE '%TURF%'
            OR business_name LIKE '%SOD %'
            OR business_name LIKE '%SEED %'
            OR business_name LIKE '%FLOWER%'
            OR business_name LIKE '%BLOOM%'
            OR business_name LIKE '%IRRIGATION%'
            OR business_name LIKE '%OUTDOOR%'
            OR business_name LIKE '%SUPPLY%'
            OR business_name LIKE '%EVERGREEN%'
            OR business_name LIKE '%PERENNIAL%'
            OR business_name LIKE '%DAYLIL%'
            OR business_name LIKE '%BLOSSOM%'
            OR business_name LIKE '%PRODUCE%'
            OR business_name LIKE '%BERRY%'
            OR business_name LIKE '%ORCHARD%'
            OR business_name LIKE '%NATIVE%'
            OR business_name LIKE '%ORGANIC%'
            OR business_name LIKE '%HYDROPON%'
          )
        ORDER BY RANDOM()
        LIMIT ?
    """
    
    cursor.execute(query, (limit,))
    leads = cursor.fetchall()
    
    print(f"✅ Found {len(leads)} Tier U leads to process")
    print(f"   Mode: {'DRY RUN' if dry_run else 'LIVE UPDATE'}")
    print()
    print("Starting discovery...")
    print("=" * 80)
    print()
    
    stats = {
        'total': len(leads),
        'processed': 0,
        'found': 0,
        'not_found': 0,
        'errors': 0,
        'start_time': time.time()
    }
    
    found_websites = []
    
    for idx, lead in enumerate(leads, 1):
        lead_id = lead['id']
        business_name = lead['business_name']
        city = lead['city'] or ''
        state = lead['state'] or ''
        
        # Search for website
        result = find_website(business_name, city, state)
        stats['processed'] += 1
        
        if result['success']:
            stats['found'] += 1
            website = result['website']
            
            found_websites.append({
                'id': lead_id,
                'name': business_name,
                'city': city,
                'state': state,
                'website': website,
                'score': result['score']
            })
            
            print(f"[{idx}/{len(leads)}] ✅ {business_name[:35]:<35} → {result['domain'][:30]} (score: {result['score']})")
            
            if not dry_run:
                cursor.execute("""
                    UPDATE leads
                    SET website = ?
                    WHERE id = ?
                """, (website, lead_id))
                conn.commit()
        else:
            if 'error' in result and 'No' not in result['error']:
                stats['errors'] += 1
                print(f"[{idx}/{len(leads)}] ❌ {business_name[:35]:<35} → ERROR: {result['error'][:30]}")
            else:
                stats['not_found'] += 1
                print(f"[{idx}/{len(leads)}] ⚪ {business_name[:35]:<35} → No website found")
        
        # Rate limiting: 1 request per second (Brave free tier)
        time.sleep(1.0)
        
        # Progress report every 25 leads
        if idx % 25 == 0:
            elapsed = time.time() - stats['start_time']
            rate = stats['processed'] / elapsed * 60
            remaining = stats['total'] - stats['processed']
            eta_min = remaining / rate if rate > 0 else 0
            
            print()
            print(f"--- Progress: {idx}/{stats['total']} ---")
            print(f"    Found: {stats['found']} ({stats['found']/stats['processed']*100:.1f}%)")
            print(f"    Not found: {stats['not_found']}")
            print(f"    Errors: {stats['errors']}")
            print(f"    Speed: {rate:.1f}/min | ETA: {int(eta_min)}min")
            print()
    
    conn.close()
    
    # Final summary
    elapsed = time.time() - stats['start_time']
    
    print()
    print("=" * 80)
    print("DISCOVERY COMPLETE")
    print("=" * 80)
    print(f"Total processed: {stats['processed']}")
    print(f"Websites found: {stats['found']} ({stats['found']/max(stats['processed'],1)*100:.1f}%)")
    print(f"Not found: {stats['not_found']}")
    print(f"Errors: {stats['errors']}")
    print()
    print(f"Time elapsed: {elapsed/60:.1f} minutes")
    print()
    
    if found_websites:
        print("=" * 80)
        print("SAMPLE FOUND WEBSITES (Top 10 by score)")
        print("=" * 80)
        found_websites.sort(key=lambda x: x['score'], reverse=True)
        for fw in found_websites[:10]:
            print(f"  {fw['name'][:40]:<40} | {fw['website'][:50]}")
    
    print()
    if dry_run:
        print("⚠️  DRY RUN - No changes made to database")
    else:
        print("✅ Database updated with discovered websites")
    print("=" * 80)
    
    return stats


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Discover websites for Tier U leads')
    parser.add_argument('--limit', type=int, default=100, help='Number of leads to process')
    parser.add_argument('--dry-run', action='store_true', help='Do not update database')
    
    args = parser.parse_args()
    
    try:
        discover_websites(limit=args.limit, dry_run=args.dry_run)
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
