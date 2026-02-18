"""
Email Web Search — Tavily-powered email discovery for nursery leads.

Tavily is an AI-native search API that returns full page content (not just snippets),
making it far more effective for finding emails on small business websites than
traditional search APIs.

Two-step approach:
1. Search: Find pages likely to contain the business's email
2. Extract: Pull full content from contact/about pages for email parsing

API: https://api.tavily.com
Auth: Bearer token via TAVILY_API_KEY env var
Free tier: 1,000 credits/month (search=1 credit, extract=2 credits per 5 URLs)
"""

import re
import os
import time
import json
import logging
import urllib.request
import urllib.error
import urllib.parse
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# ─── Email extraction ─────────────────────────────────────────────────────────

EMAIL_PATTERN = re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,6}(?![a-zA-Z.])')

GENERIC_PREFIXES = [
    'info', 'contact', 'hello', 'sales', 'support', 'admin',
    'office', 'help', 'team', 'mail', 'email', 'enquiries',
    'general', 'marketing', 'billing', 'orders', 'service'
]

JUNK_DOMAINS = [
    'example.com', 'schema.org', 'sentry.io', 'w3.org',
    'wix.com', 'wordpress.', 'cloudflare', 'microsoft.com',
    'bing.com', 'google.com', 'googleapis.com', 'gstatic.com',
    'facebook.com', 'twitter.com', 'instagram.com', 'linkedin.com',
    'youtube.com', 'pinterest.com', 'tiktok.com', 'yelp.com',
    'squarespace.com', 'godaddy.com', 'wixsite.com', 'weebly.com',
    'shopify.com', 'mailchimp.com', 'constantcontact.com',
    'sentry-next.wixpress.com', 'parastorage.com',
]


def extract_emails_from_text(text: str, preferred_domain: Optional[str] = None) -> List[str]:
    """Extract, deduplicate, and rank emails from text content."""
    if not text:
        return []

    # Also handle obfuscated emails
    clean_text = text.replace('&#64;', '@').replace('&#46;', '.').replace(' [at] ', '@').replace(' (at) ', '@')

    # Handle spaced emails: "user @ domain . com"
    spaced_pattern = r'([a-zA-Z0-9._%+-]+)\s*@\s*([a-zA-Z0-9.-]+)\s*\.\s*([a-zA-Z]{2,})'
    spaced_matches = re.findall(spaced_pattern, clean_text)
    spaced_emails = [f"{m[0]}@{m[1]}.{m[2]}".replace(' ', '').lower() for m in spaced_matches]

    # Standard regex
    standard_emails = [e.lower() for e in EMAIL_PATTERN.findall(clean_text)]

    all_emails = list(dict.fromkeys(standard_emails + spaced_emails))  # dedupe preserving order

    # Clean up malformed TLDs (e.g., "user@domain.com.phone" → "user@domain.com")
    cleaned = []
    valid_tlds_pattern = re.compile(r'^(.+@.+\.(com|net|org|edu|gov|io|co|us|info|biz|me|tv|cc))(?:\.[a-z]+)*$', re.IGNORECASE)
    for e in all_emails:
        m = valid_tlds_pattern.match(e)
        if m:
            cleaned.append(m.group(1).lower())
        else:
            cleaned.append(e)
    all_emails = list(dict.fromkeys(cleaned))  # re-dedupe after cleanup

    # Filter junk
    filtered = []
    for e in all_emails:
        domain = e.split('@')[1] if '@' in e else ''
        local = e.split('@')[0] if '@' in e else ''
        if (len(local) > 1
                and '.' in domain
                and not e.endswith(('.png', '.jpg', '.gif', '.svg', '.css', '.js'))
                and not any(j in domain for j in JUNK_DOMAINS)):
            filtered.append(e)

    # Score and sort
    def score(email):
        local = email.split('@')[0]
        domain = email.split('@')[1]
        s = 0
        if preferred_domain and domain == preferred_domain:
            s += 100
        if local in GENERIC_PREFIXES:
            s -= 50
        if '.' in local:
            s += 20  # Looks like a name (first.last)
        elif 3 < len(local) < 20:
            s += 10
        return s

    filtered.sort(key=score, reverse=True)
    return filtered


# ─── Rate limiting ─────────────────────────────────────────────────────────────

_last_request_time = 0.0


def _rate_limit(min_interval: float = 1.0):
    """Simple rate limiter — minimum interval between requests."""
    global _last_request_time
    now = time.time()
    elapsed = now - _last_request_time
    if elapsed < min_interval:
        time.sleep(min_interval - elapsed)
    _last_request_time = time.time()


# ─── Tavily API ───────────────────────────────────────────────────────────────

def _get_tavily_api_key() -> Optional[str]:
    """Get Tavily API key from environment."""
    key = os.getenv('TAVILY_API_KEY')
    if not key:
        logger.debug("TAVILY_API_KEY not set — web search layer unavailable")
        return None
    return key


def _tavily_request(endpoint: str, payload: dict) -> Optional[dict]:
    """Make an authenticated request to the Tavily API."""
    api_key = _get_tavily_api_key()
    if not api_key:
        return None

    _rate_limit(1.0)

    url = f'https://api.tavily.com/{endpoint}'
    data = json.dumps(payload).encode('utf-8')

    req = urllib.request.Request(url, data=data, method='POST')
    req.add_header('Content-Type', 'application/json')
    req.add_header('Authorization', f'Bearer {api_key}')

    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return json.loads(resp.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8', errors='replace')[:300] if hasattr(e, 'read') else ''
        logger.warning(f"Tavily {endpoint} HTTP {e.code}: {body}")
        return None
    except urllib.error.URLError as e:
        logger.warning(f"Tavily {endpoint} URL error: {e.reason}")
        return None
    except Exception as e:
        logger.warning(f"Tavily {endpoint} error: {str(e)[:100]}")
        return None


def tavily_search(query: str, max_results: int = 5, search_depth: str = 'basic') -> List[Dict]:
    """
    Search using Tavily API. Returns list of results with content.

    Each result has: url, title, content (full text snippet or NLP summary), score
    """
    payload = {
        'query': query,
        'max_results': max_results,
        'search_depth': search_depth,
        'include_answer': False,
    }

    resp = _tavily_request('search', payload)
    if not resp:
        return []

    return resp.get('results', [])


def tavily_extract(urls: List[str]) -> List[Dict]:
    """
    Extract full page content from URLs using Tavily Extract API.

    Returns list of dicts with: url, raw_content
    Cost: 2 credits per 5 URLs
    """
    if not urls:
        return []

    # Tavily extract takes up to 20 URLs
    payload = {
        'urls': urls[:20],
    }

    resp = _tavily_request('extract', payload)
    if not resp:
        return []

    return resp.get('results', [])


# ─── Email search orchestration ───────────────────────────────────────────────

def search_email_for_lead(
    owner_name: str,
    business_name: str,
    website: Optional[str] = None,
    **kwargs  # Accept and ignore legacy params for backward compat
) -> Dict:
    """
    Search for a lead's email using Tavily Search + Extract.

    Strategy:
    1. Search for "{business_name}" + email/contact keywords
    2. If owner_name provided, also search "{owner_name}" "{business_name}" email
    3. Extract content from top results (especially contact/about pages)
    4. Parse all content for email addresses
    5. Rank by domain match and personal vs generic

    Returns:
        Dict with 'email', 'confidence', 'source', 'emails_found', 'error'
    """
    from .email_patterns import extract_domain

    result = {
        'email': None,
        'emails_found': [],
        'source': 'tavily_search',
        'confidence': 0,
        'error': None,
    }

    if not _get_tavily_api_key():
        result['error'] = 'TAVILY_API_KEY not configured'
        return result

    domain = extract_domain(website) if website else None

    # Build search queries
    queries = [
        f'"{business_name}" email contact',
    ]
    if owner_name and owner_name.strip():
        queries.append(f'"{owner_name}" "{business_name}" email')

    # Step 1: Search
    all_emails = []
    extract_urls = []

    for query in queries:
        results = tavily_search(query, max_results=3, search_depth='basic')

        for r in results:
            # Extract emails from search result content
            content = r.get('content', '') + ' ' + r.get('title', '')
            found = extract_emails_from_text(content, domain)
            all_emails.extend(found)

            # Collect URLs for potential extraction (contact/about pages)
            url = r.get('url', '')
            if any(kw in url.lower() for kw in ['contact', 'about', 'team', 'staff']):
                extract_urls.append(url)

        # If we already found a domain-matching personal email, stop early
        if domain and any(domain in e and e.split('@')[0] not in GENERIC_PREFIXES for e in all_emails):
            break

    # Step 2: Extract content from contact/about pages for deeper email mining
    if not all_emails and extract_urls:
        extracted = tavily_extract(extract_urls[:5])
        for page in extracted:
            raw = page.get('raw_content', '')
            found = extract_emails_from_text(raw, domain)
            all_emails.extend(found)

    # Step 3: If still nothing and we have a website, extract the contact page directly
    if not all_emails and website and domain:
        contact_urls = [
            f'https://{domain}/contact',
            f'https://{domain}/about',
            f'https://{domain}/contact-us',
        ]
        extracted = tavily_extract(contact_urls)
        for page in extracted:
            raw = page.get('raw_content', '')
            found = extract_emails_from_text(raw, domain)
            all_emails.extend(found)

    # Deduplicate
    all_emails = list(dict.fromkeys(all_emails))

    if not all_emails:
        result['error'] = 'No emails found via Tavily search + extract'
        return result

    # Pick the best email
    best = all_emails[0]  # Already sorted by score in extract_emails_from_text
    result['email'] = best
    result['emails_found'] = all_emails[:10]

    # Confidence scoring
    local = best.split('@')[0]
    email_domain = best.split('@')[1]

    if domain and email_domain == domain:
        if local not in GENERIC_PREFIXES:
            result['confidence'] = 75  # Domain match + personal
        else:
            result['confidence'] = 45  # Domain match + generic
    elif local not in GENERIC_PREFIXES:
        result['confidence'] = 55  # No domain match but personal
    else:
        result['confidence'] = 30  # Generic, no domain match

    return result


# ─── Batch processing ──────────────────────────────────────────────────────────

def batch_search_emails(
    leads: List[Dict],
    delay: float = 1.5,
    max_leads: int = 50,
) -> List[Dict]:
    """
    Search for emails for multiple leads using Tavily.

    Args:
        leads: List of dicts with 'owner_name', 'business_name', 'website'
        delay: Seconds between searches (on top of rate limiting)
        max_leads: Maximum leads to process

    Returns:
        List of result dicts
    """
    results = []

    for i, lead in enumerate(leads[:max_leads]):
        owner = lead.get('owner_name', '')
        business = lead.get('business_name', '')
        website = lead.get('website', '')

        if not business:
            results.append({
                'lead': lead,
                'error': 'Missing business_name'
            })
            continue

        logger.info(f"[{i + 1}/{min(len(leads), max_leads)}] Searching: {owner or '(no name)'} at {business}")

        result = search_email_for_lead(owner, business, website)
        result['lead'] = lead
        results.append(result)

        # Extra delay between leads
        if delay > 0 and i < len(leads) - 1:
            time.sleep(delay)

    return results
