"""
Web Search Enrichment (Step 1 alternative)
==========================================
Uses Brave Search API instead of Google Places for segments where
Places API has poor match rates (hemp, cannabis).

Hemp/cannabis leads come from the USDA registry — they have only
business name + city/state/zip, no address. Web search finds their
site more reliably than Places for these small/niche operations.

Returns the same structure as enrich_business() in google_places.py
so callers don't need to branch.
"""

import os
import re
import logging
import requests

logger = logging.getLogger(__name__)

TAVILY_SEARCH_URL = "https://api.tavily.com/search"

# Skip these domains when extracting a business's own website from results.
# These are directories, aggregators, and social platforms — not the business site.
SKIP_DOMAINS = {
    'yelp.com', 'google.com', 'facebook.com', 'linkedin.com',
    'instagram.com', 'twitter.com', 'x.com', 'bbb.org', 'manta.com',
    'yellowpages.com', 'chamberofcommerce.com', 'bizapedia.com',
    'bloomberg.com', 'dnb.com', 'opencorporates.com', 'mapquest.com',
    'whitepages.com', 'ripoffreport.com', 'indeed.com', 'glassdoor.com',
    'bizbuysell.com', 'zoominfo.com', 'usda.gov', 'ams.usda.gov',
    'agriculture.gov', 'state.il.us', 'state.wi.us', 'state.mn.us',
    'state.mi.us', 'state.oh.us', 'state.in.us', 'cannabis.gov',
    'hempindustrydaily.com', 'cbdoilreview.org', 'ministryofhemp.com',
    'weedmaps.com', 'leafly.com', 'crunchbase.com', 'bizstanding.com',
}

# Domains that are never a small business's own website — hard false positives
FALSE_POSITIVE_DOMAINS = {
    'wikipedia.org', 'wikimedia.org', 'wiktionary.org',
    'amazon.com', 'ebay.com', 'etsy.com', 'walmart.com',
    'reddit.com', 'quora.com', 'medium.com',
    'nytimes.com', 'washingtonpost.com', 'cnn.com', 'reuters.com',
}


def _is_directory_url(url: str) -> bool:
    """Return True if URL is a business directory or known false positive."""
    try:
        from urllib.parse import urlparse
        netloc = urlparse(url).netloc.lower().lstrip('www.')
        all_skip = SKIP_DOMAINS | FALSE_POSITIVE_DOMAINS
        return any(skip in netloc for skip in all_skip)
    except Exception:
        return False


def _url_matches_business(url: str, business_name: str) -> bool:
    """
    Heuristic: does the URL domain plausibly relate to the business name?
    Returns True if it seems related or we can't tell (benefit of the doubt).
    Returns False only for obvious mismatches (e.g. 'robertcboyce.com' for 'Natural Environments').
    """
    try:
        from urllib.parse import urlparse
        netloc = urlparse(url).netloc.lower().lstrip('www.').split('.')[0]
        clean = _clean_business_name(business_name).lower()
        # Ignore generic words when comparing
        stop_words = {'the', 'llc', 'inc', 'corp', 'ltd', 'farm', 'farms',
                      'company', 'co', 'and', 'of', 'for', 'a', 'an'}
        words = [w for w in re.split(r'\W+', clean) if len(w) > 2 and w not in stop_words]
        if not words:
            return True  # Can't determine — allow
        for word in words:
            if word in netloc:
                return True
        return False
    except Exception:
        return True  # Benefit of the doubt


def _clean_business_name(name: str) -> str:
    """
    Strip address artifacts that sometimes get embedded in business names
    from the USDA registry (e.g. 'Ford family farms PO Box 43 Smithfield IL 61477').
    """
    if not name:
        return name
    # Strip trailing PO Box + anything after
    name = re.sub(r'\s+P\.?O\.?\s+Box\s+\S+.*', '', name, flags=re.IGNORECASE)
    # Strip trailing street address patterns: digits + street + city + state + zip
    name = re.sub(r'\s+\d+\s+\w+[\w\s]+\w{2}\s+\d{5}.*', '', name)
    # Strip trailing state abbreviation + zip
    name = re.sub(r'\s+[A-Z]{2}\s+\d{5}.*', '', name)
    return name.strip()


def _extract_phone(text: str):
    """Pull first US phone number from a string. Returns None if not found."""
    if not text:
        return None
    match = re.search(r'\(?\d{3}\)?[\s.\-]?\d{3}[\s.\-]?\d{4}', text)
    return match.group(0).strip() if match else None


def web_search_enrich(business_name: str, city: str, state: str,
                      zip_code: str = None) -> dict:
    """
    Find a business's website via Brave web search.

    Designed for hemp/cannabis leads from the USDA registry where
    Google Places has a low match rate due to minimal source data.

    Args:
        business_name: Business name (may contain embedded address artifacts)
        city:          City name
        state:         State abbreviation
        zip_code:      ZIP code (preferred over city for precision)

    Returns:
        dict with keys matching enrich_business() output:
            website, phone, enrichment_source
            OR {'error': '...'} on failure
    """
    api_key = os.environ.get('TAVILY_API_KEY')
    if not api_key:
        return {'error': 'TAVILY_API_KEY not configured'}

    clean_name = _clean_business_name(business_name)
    if not clean_name:
        return {'error': 'Empty business name after cleaning'}

    # Build a tight location string — zip is more precise than city for rural businesses
    location_parts = []
    if city:
        location_parts.append(city)
    if state:
        location_parts.append(state)
    if zip_code:
        location_parts.append(zip_code)
    location = ' '.join(location_parts)

    query = f'"{clean_name}" {location}'
    logger.info(f"Web search query: {query}")

    try:
        resp = requests.post(
            TAVILY_SEARCH_URL,
            json={
                'api_key': api_key,
                'query': query,
                'max_results': 5,
                'search_depth': 'basic',
                'include_answer': False,
            },
            timeout=10,
        )

        if resp.status_code == 429:
            return {'error': 'Tavily rate limit exceeded'}
        if resp.status_code != 200:
            return {'error': f'Tavily API error {resp.status_code}: {resp.text[:100]}'}

        data = resp.json()
        results = data.get('results', [])

        website = None
        all_snippets = []

        for result in results:
            url = result.get('url', '')
            snippet = result.get('content', '') or result.get('snippet', '')
            all_snippets.append(snippet)

            if url and not _is_directory_url(url) and website is None:
                if _url_matches_business(url, business_name):
                    website = url
                    logger.info(f"Found website: {website} (from: {result.get('title', '')})")
                else:
                    logger.warning(f"Skipping URL {url} — domain doesn't match '{business_name}'")

        if not website:
            logger.warning(f"No usable website found for: {query}")
            return {'error': 'No website found via web search'}

        phone = _extract_phone(' '.join(all_snippets))

        return {
            'website': website,
            'phone': phone,
            'rating': None,
            'review_count': None,
            'place_id': None,
            'google_maps_url': None,
            'enrichment_source': 'web_search',
        }

    except requests.Timeout:
        return {'error': 'Web search timed out'}
    except Exception as e:
        logger.error(f"web_search_enrich error: {e}")
        return {'error': f'Web search exception: {str(e)[:100]}'}


# ---------------------------------------------------------------------------
# Facebook Page Search — Hemp/Cannabis Fallback
# ---------------------------------------------------------------------------

# Email regex (intentionally broad — we apply junk-filter after)
_EMAIL_RE = re.compile(r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}')

_EMAIL_JUNK_DOMAINS = {
    'example.com', 'schema.org', 'w3.org', 'google.com',
    'sentry.io', 'cloudflare.com', 'amazonaws.com',
    'wix.com', 'wordpress.com', 'squarespace.com',
    'facebook.com', 'fb.com',          # FB internal addresses are never real leads
    'socalleafandcanopy.com',           # placeholder – add false positives here
}


def _extract_email_from_text(text: str) -> str | None:
    """
    Pull the first plausible email address from arbitrary text.
    Returns None if none found.
    """
    if not text:
        return None
    candidates = _EMAIL_RE.findall(text)
    for email in candidates:
        email = email.lower().rstrip('.,;)')
        local, _, domain = email.partition('@')
        if len(local) < 2:
            continue
        if '.' not in domain:
            continue
        if any(junk in domain for junk in _EMAIL_JUNK_DOMAINS):
            continue
        if email.endswith(('.png', '.jpg', '.gif', '.css', '.js', '.svg')):
            continue
        return email
    return None


def _tavily_search(api_key: str, query: str, max_results: int = 5) -> list:
    """
    Execute a single Tavily search and return the results list.
    Returns [] on any error (caller decides how to handle).
    """
    try:
        resp = requests.post(
            TAVILY_SEARCH_URL,
            json={
                'api_key':       api_key,
                'query':         query,
                'max_results':   max_results,
                'search_depth':  'basic',
                'include_answer': False,
            },
            timeout=10,
        )
        if resp.status_code == 429:
            logger.warning("[tavily] rate limit hit")
            return []
        if resp.status_code != 200:
            logger.warning(f"[tavily] HTTP {resp.status_code}")
            return []
        return resp.json().get('results', [])
    except Exception as e:
        logger.warning(f"[tavily] exception: {e}")
        return []


def _extract_facebook_page(results: list) -> tuple[str | None, str]:
    """
    From a list of Tavily result dicts, extract:
      - the first canonical Facebook page URL (not a post/group/event)
      - combined snippet text from all results

    Returns: (best_url_or_None, combined_snippets)
    """
    # Sub-page types we don't want to scrape (but we still read their snippets)
    POST_PATHS = ['/search/', '/hashtag/', '/watch/', '/groups/', '/posts/', '/events/']

    best_url     = None
    all_snippets = []

    for result in results:
        url     = result.get('url', '')
        snippet = result.get('content', '') or result.get('snippet', '') or ''
        all_snippets.append(snippet)

        if 'facebook.com' not in url.lower():
            continue

        is_post = any(p in url for p in POST_PATHS)
        if not is_post and best_url is None:
            best_url = url
            logger.info(f"[facebook_search] page URL: {url}")

    return best_url, ' '.join(s for s in all_snippets if s)


def search_facebook_page(business_name: str, city: str, state: str) -> dict:
    """
    Search for a business's Facebook page via Tavily and return the best URL.

    Two-pass strategy:
    1. Restricted search: `"<name>" <city> <state> site:facebook.com`
       — Most accurate when Tavily has the page indexed.
    2. Broad fallback: `"<name>" <city> <state> facebook`
       — Catches cases where site: restriction returns nothing useful.
       — Facebook URLs found in ANY result are treated as the page.

    Args:
        business_name: Raw business name (may contain registry artifacts)
        city:          City name
        state:         State abbreviation

    Returns:
        dict:
            {'url': <facebook_url_or_empty>, 'snippet': <combined_snippet_text>}
                — url may be '' if only post URLs were found (snippet may still have email)
            {'error': '...'}
                — on API failure / no results at all
    """
    api_key = os.environ.get('TAVILY_API_KEY')
    if not api_key:
        return {'error': 'TAVILY_API_KEY not configured'}

    clean_name = _clean_business_name(business_name)
    if not clean_name:
        return {'error': 'Empty business name after cleaning'}

    # ── Pass 1: site-restricted search ───────────────────────────────────────
    q1 = f'"{clean_name}" {city} {state} site:facebook.com'
    logger.info(f"[facebook_search] pass-1 query: {q1}")
    results1 = _tavily_search(api_key, q1)

    if results1:
        best_url, snippet = _extract_facebook_page(results1)
        # A page URL *or* a non-empty snippet is good enough — snippet may hold email
        if best_url or snippet.strip():
            return {'url': best_url or '', 'snippet': snippet}

    # ── Pass 2: broad search for Facebook URLs ────────────────────────────────
    q2 = f'"{clean_name}" {city} {state} facebook'
    logger.info(f"[facebook_search] pass-2 query: {q2}")
    results2 = _tavily_search(api_key, q2)

    if results2:
        best_url, snippet = _extract_facebook_page(results2)
        if best_url or snippet.strip():
            return {'url': best_url or '', 'snippet': snippet}

    return {'error': 'No Facebook page found in results'}


def extract_email_from_facebook_page(fb_url: str) -> str | None:
    """
    Attempt to extract an email from a Facebook business page.

    Strategy (in order):
    1. Try the /about tab — most likely location for contact info
    2. Fall back to the page root
    3. Parse any visible email from the snippet/text

    Facebook is heavily JS-rendered so we may only get partial text.
    Returns the first plausible email found, or None.
    """
    from enrichment.web_scraper import scrape_website, extract_text

    # Try the /about sub-page first
    urls_to_try = []
    base = fb_url.rstrip('/')
    if '/about' not in base:
        urls_to_try.append(base + '/about')
    urls_to_try.append(base)

    for url in urls_to_try:
        try:
            html, status, error = scrape_website(url)
            if error or not html:
                logger.debug(f"[facebook_extract] scrape failed for {url}: {error}")
                continue
            text = extract_text(html)
            email = _extract_email_from_text(text)
            if email:
                logger.info(f"[facebook_extract] found email {email} at {url}")
                return email
        except Exception as e:
            logger.debug(f"[facebook_extract] exception for {url}: {e}")
            continue

    return None
