"""
Email Hunter — 5-layer email discovery for nursery leads.

Layer 1: Direct extraction
    - Google Places API email (stored as places_email)
    - Regex extraction from already-scraped website_text in DB
    - Contact-page scrape (/contact, /about, /contact-us)

Layer 2: Pattern inference
    - With owner_name + domain: first.last@, first@, flast@, etc.
    - Domain-only (no owner_name): generic patterns info@, hello@, contact@
    - MX validation on domain before inferring

Layer 3: Web search (Tavily API)
    - Direct API calls, 1 req/sec rate limit
    - Queries: "{business}" email, "{business}" "{owner}" email contact

Layer 4: Paid API (Hunter.io / Snov.io)
    - Dormant until HUNTER_API_KEY or SNOV creds are set

Layer 5: Email verification (post-discovery, pre-export)
    - Runs on all found emails via email_verifier_api.py
    - Reoon already configured; ZeroBounce activates with key

CRITICAL CHANGE (vs old code):
    Old: only ran if owner_name AND website both present (missed 70% of leads)
    New: runs for ALL leads that have any domain — owner_name is optional
"""

import logging
import re
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

from .email_patterns import generate_email_patterns, extract_domain, normalize_name
from .email_verifier import EmailVerifier

logger = logging.getLogger(__name__)

# Email regex for scraping raw text
EMAIL_RE = re.compile(r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}')

# Generic fallback prefixes (deprioritised but valid)
GENERIC_PREFIXES = ['info', 'hello', 'contact', 'sales', 'office', 'team', 'mail']

# Contact page paths to try (Layer 1)
CONTACT_PATHS = ['/contact', '/contact-us', '/about', '/about-us', '/reach-us', '/get-in-touch']


@dataclass
class EmailHuntResult:
    """Result of the full email discovery flow."""
    email: Optional[str] = None          # Best email found
    confidence: int = 0                   # 0–100
    method: str = 'none'                  # How it was found (maps to email_source)
    all_candidates: List[str] = field(default_factory=list)
    domain_valid: bool = False
    mx_hosts: List[str] = field(default_factory=list)
    error: Optional[str] = None
    generic_email: Optional[str] = None   # Fallback info@domain
    contact_form_url: Optional[str] = None
    contact_page_text: Optional[str] = None  # Raw text from /contact page
    # Verification fields (Fix 1 — wired via Reoon API)
    verified: bool = False
    verification_status: str = ''
    verification_provider: str = ''
    verification_result: Optional[dict] = None  # Full VerificationResult.to_dict()

    def to_dict(self) -> Dict:
        return {
            'email': self.email,
            'confidence': self.confidence,
            'method': self.method,
            'all_candidates': self.all_candidates,
            'domain_valid': self.domain_valid,
            'mx_hosts': self.mx_hosts,
            'error': self.error,
            'generic_email': self.generic_email,
            'contact_form_url': self.contact_form_url,
            'verified': self.verified,
            'verification_status': self.verification_status,
            'verification_provider': self.verification_provider,
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _extract_emails_from_text(text: str, preferred_domain: Optional[str] = None) -> List[str]:
    """Extract and rank emails from raw text."""
    if not text:
        return []

    raw = EMAIL_RE.findall(text)
    emails = list({e.lower() for e in raw})

    junk_domains = {
        'example.com', 'schema.org', 'w3.org', 'google.com',
        'sentry.io', 'cloudflare.com', 'amazonaws.com',
        'wix.com', 'wordpress.com', 'squarespace.com',
    }

    clean = [
        e for e in emails
        if '@' in e
        and len(e.split('@')[0]) >= 2
        and '.' in e.split('@')[1]
        and not any(j in e.split('@')[1] for j in junk_domains)
        and not e.endswith(('.png', '.jpg', '.gif', '.css', '.js'))
    ]

    def score(e: str) -> int:
        local, dom = e.split('@')
        s = 0
        if preferred_domain and dom == preferred_domain:
            s += 100
        if local in {'info', 'contact', 'hello', 'sales', 'support', 'admin', 'office'}:
            s -= 30
        if '.' in local:
            s += 15
        if 3 <= len(local) <= 20:
            s += 10
        return s

    clean.sort(key=score, reverse=True)
    return clean


def _fetch_contact_page(base_url: str, timeout: int = 8) -> Optional[str]:
    """
    Try to fetch a contact/about page from the website.
    Returns plain text if successful, None on failure.
    Only uses stdlib — no requests dependency.
    """
    if not base_url:
        return None

    # Normalise base
    if not base_url.startswith(('http://', 'https://')):
        base_url = 'https://' + base_url
    base_url = base_url.rstrip('/')

    headers = {
        'User-Agent': (
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
            'AppleWebKit/537.36 (KHTML, like Gecko) '
            'Chrome/121.0.0.0 Safari/537.36'
        ),
        'Accept': 'text/html,application/xhtml+xml,*/*;q=0.8',
    }

    for path in CONTACT_PATHS:
        url = base_url + path
        try:
            req = Request(url)
            for k, v in headers.items():
                req.add_header(k, v)
            with urlopen(req, timeout=timeout) as resp:
                if resp.status != 200:
                    continue
                ct = resp.headers.get('Content-Type', '')
                if 'text' not in ct and 'html' not in ct:
                    continue
                raw = resp.read(1024 * 128)  # max 128 KB
                text = raw.decode('utf-8', errors='ignore')
                # Strip HTML tags crudely
                text = re.sub(r'<[^>]+>', ' ', text)
                text = re.sub(r'\s+', ' ', text).strip()
                if len(text) > 100:
                    logger.debug(f"Contact page found: {url}")
                    return text
        except (HTTPError, URLError, Exception):
            pass  # Try next path
        time.sleep(0.3)

    return None


# ---------------------------------------------------------------------------
# Layer 1: Direct extraction
# ---------------------------------------------------------------------------

def _layer1_direct_extraction(
    domain: str,
    website: Optional[str],
    website_text: Optional[str],
    places_email: Optional[str],
) -> Optional[tuple]:
    """
    Try to find email via direct extraction.
    Returns (email, method, contact_page_text) or None.
    """
    # 1a. Google Places email (highest confidence — straight from Google)
    if places_email and '@' in places_email:
        logger.debug(f"Layer 1a: found Places email {places_email}")
        return (places_email, 'places', None)

    # 1b. Extract from already-scraped website_text (no new HTTP call)
    if website_text:
        emails = _extract_emails_from_text(website_text, domain)
        if emails:
            logger.debug(f"Layer 1b: found email in website_text: {emails[0]}")
            return (emails[0], 'website_scrape', None)

    # 1c. Scrape contact page specifically
    if website:
        contact_text = _fetch_contact_page(website)
        if contact_text:
            emails = _extract_emails_from_text(contact_text, domain)
            if emails:
                logger.debug(f"Layer 1c: found email on contact page: {emails[0]}")
                return (emails[0], 'contact_page', contact_text)
            return (None, None, contact_text)  # Got the page but no email

    return None


# ---------------------------------------------------------------------------
# Layer 2: Pattern inference
# ---------------------------------------------------------------------------

def _layer2_pattern_inference(
    domain: str,
    owner_name: Optional[str],
    mx_valid: Optional[bool],
) -> Optional[tuple]:
    """
    Try pattern inference.
    - With name:  first.last@, first@, flast@, etc.
    - Without name: generic patterns (info@, contact@, etc.)
    Returns (email, method, candidates) or None.

    Args:
        mx_valid: True = MX confirmed, False = MX check ran and failed,
                  None = MX check was skipped (treat as unknown/valid).
    """
    # 2a. Named patterns — run regardless of MX status.
    # A real name+domain email might still work even on domains with broken MX
    # records (rare, but possible — e.g. catch-all or misconfigured MX).
    if owner_name:
        name_parts = normalize_name(owner_name)
        if name_parts and name_parts.get('first'):
            first = name_parts['first']
            last = name_parts.get('last')
            candidate_dicts = generate_email_patterns(first, last, domain)
            if candidate_dicts:
                candidate_dicts.sort(key=lambda x: x.get('weight', 0), reverse=True)
                best = candidate_dicts[0]
                logger.debug(f"Layer 2a: pattern email {best['email']}")
                return (best['email'], 'pattern', [c['email'] for c in candidate_dicts])

    # 2b. Generic patterns (domain-only, no name).
    # Skip entirely when MX is *explicitly* invalid — info@ to a domain with no
    # MX records is a guaranteed bounce.  mx_valid=None means "not checked", so
    # we allow it through (conservative default).
    if mx_valid is False:
        logger.debug(f"Layer 2b: skipping generic patterns — MX explicitly invalid for {domain}")
        return None

    for prefix in GENERIC_PREFIXES:
        email = f'{prefix}@{domain}'
        logger.debug(f"Layer 2b: generic pattern {email}")
    # Return the first generic as candidate
    generic = f'{GENERIC_PREFIXES[0]}@{domain}'
    return (generic, 'generic', [f'{p}@{domain}' for p in GENERIC_PREFIXES])


# ---------------------------------------------------------------------------
# Email verification helper (Fix 1)
# ---------------------------------------------------------------------------

def _do_verify(result: EmailHuntResult) -> None:
    """
    Run email verification via Reoon (or fallback provider) and update the
    EmailHuntResult in-place.

    If the primary email fails verification, iterates all_candidates in order
    and replaces result.email with the first candidate that passes.  Adds a
    0.5 s sleep between API calls to respect Reoon rate limits.

    This is a no-op when result.email is None or empty.
    """
    from .email_verifier_api import verify_email

    if not result.email:
        return

    time.sleep(0.5)
    vr = verify_email(result.email)
    result.verified = vr.is_deliverable
    result.verification_status = vr.status
    result.verification_provider = vr.provider
    result.verification_result = vr.to_dict()

    if vr.is_usable():
        logger.debug(f"Verification passed: {result.email} ({vr.status} via {vr.provider})")
        return

    logger.debug(
        f"Verification failed: {result.email} ({vr.status}) — "
        f"trying {len(result.all_candidates)} candidate(s)"
    )

    tried = {result.email.lower()}
    for candidate in result.all_candidates:
        if not candidate or candidate.lower() in tried:
            continue
        tried.add(candidate.lower())
        time.sleep(0.5)
        vr2 = verify_email(candidate)
        if vr2.is_usable():
            result.email = candidate
            result.verified = True
            result.verification_status = vr2.status
            result.verification_provider = vr2.provider
            result.verification_result = vr2.to_dict()
            result.confidence = max(result.confidence, vr2.confidence)
            logger.debug(f"Verification: switched to candidate {candidate} ({vr2.status})")
            return

    logger.debug(
        f"Verification: no valid candidate found, keeping {result.email} as unverified"
    )


# ---------------------------------------------------------------------------
# Main orchestrator
# ---------------------------------------------------------------------------

def hunt_email(
    owner_name: str,
    business_name: str,
    website: Optional[str] = None,
    website_text: Optional[str] = None,      # Pre-scraped text from DB
    places_email: Optional[str] = None,       # Email from Google Places (if any)
    enable_web_search: bool = True,
    verify_mx: bool = True,
    verify_email_result: bool = True,         # Run Reoon verification after finding email
) -> EmailHuntResult:
    """
    Hunt for an email using the 5-layer fallback architecture.

    CRITICAL: Runs for ALL leads with a domain — owner_name is OPTIONAL.

    Args:
        owner_name:          Owner name (may be empty — Layer 2 still runs generics)
        business_name:       Business name (required for web search)
        website:             Business website URL
        website_text:        Pre-scraped content already in DB (avoids re-scrape)
        places_email:        Email extracted from Google Places response
        enable_web_search:   Enable Layer 3 (Tavily search)
        verify_mx:           Check domain has MX records before pattern inference
        verify_email_result: Run Reoon API verification on the discovered email.
                             If the email fails verification, tries all_candidates
                             before giving up.  Set False to skip (e.g. testing).

    Returns:
        EmailHuntResult — always returns something, never raises
    """
    result = EmailHuntResult()

    # --- Domain extraction ---
    domain = extract_domain(website) if website else None

    # Reject social media / directory domains — they're not business email domains
    SOCIAL_DOMAINS = {
        'facebook.com', 'instagram.com', 'twitter.com', 'x.com',
        'linkedin.com', 'yelp.com', 'google.com', 'maps.google.com',
        'youtube.com', 'tiktok.com', 'pinterest.com',
        'yellowpages.com', 'bbb.org', 'angieslist.com',
    }
    if domain and domain in SOCIAL_DOMAINS:
        social_domain = domain  # capture before nulling
        logger.debug(f"Website is social media ({social_domain}) for {business_name} — skipping")
        domain = None
        result.error = f'Website is a social media page ({social_domain}) — no email domain'

    if not domain:
        logger.debug(f"No domain for {business_name} — trying web search only")
        result.error = result.error or 'No domain available'
        if enable_web_search:
            _apply_web_search(result, owner_name, business_name, website, None)
        return result

    # Always set generic fallback
    result.generic_email = f'info@{domain}'
    result.contact_form_url = f'https://{domain}/contact'

    # --- MX validation ---
    if verify_mx:
        verifier = EmailVerifier()
        mx_hosts = verifier.get_mx_records(domain)
        result.domain_valid = len(mx_hosts) > 0
        result.mx_hosts = mx_hosts
        if not result.domain_valid:
            logger.debug(f"No MX for {domain}")
    else:
        # If we're skipping MX verification, assume the domain is valid
        result.domain_valid = True

    # -------------------------------------------------------------------
    # LAYER 1: Direct extraction
    # -------------------------------------------------------------------
    layer1 = _layer1_direct_extraction(domain, website, website_text, places_email)
    if layer1:
        email, method, contact_text = layer1
        if contact_text:
            result.contact_page_text = contact_text
        if email:
            result.email = email
            result.method = method
            result.domain_valid = result.domain_valid or True  # Places email implies domain works
            if method == 'places':
                result.confidence = 90
            elif method == 'website_scrape':
                result.confidence = 75
            elif method == 'contact_page':
                result.confidence = 70
            _boost_confidence_if_mx(result)
            logger.info(f"Layer 1 ({method}): {email} for {business_name}")
            if verify_email_result:
                _do_verify(result)
            return result

    # Layer 1 got a contact page but no email — store it for record
    if layer1 and layer1[2]:
        result.contact_page_text = layer1[2]

    # -------------------------------------------------------------------
    # LAYER 2: Pattern inference
    # -------------------------------------------------------------------
    # Always attempt Layer 2 — named patterns (2a) can still work even without
    # valid MX (rare but real).  Generic patterns (2b) are skipped inside
    # _layer2_pattern_inference when mx_valid is explicitly False.
    # Pass mx_valid=None when MX check was skipped (verify_mx=False) so the
    # function treats it as "unknown" and allows generic patterns through.
    mx_status: Optional[bool] = result.domain_valid if verify_mx else None
    layer2 = _layer2_pattern_inference(domain, owner_name, mx_status)
    if layer2:
        email, method, candidates = layer2
        if candidates:
            result.all_candidates = candidates

        if method == 'pattern' and email:
            result.email = email
            result.method = 'pattern'
            result.confidence = 65
            _boost_confidence_if_mx(result)
            logger.info(f"Layer 2 (pattern): {email} for {business_name}")
            # Don't return yet — still try web search to get a real email
            # if confidence is below threshold
            if result.confidence >= 70:
                if verify_email_result:
                    _do_verify(result)
                return result
        elif method == 'generic' and email:
            # Store generic as backup but keep hunting
            result.generic_email = email

    # -------------------------------------------------------------------
    # LAYER 3: Web search (Tavily)
    # -------------------------------------------------------------------
    if enable_web_search:
        pre_email = result.email  # Remember what we had
        _apply_web_search(result, owner_name, business_name, website, domain)
        if result.email and result.email != pre_email:
            logger.info(f"Layer 3 (web_search): {result.email} for {business_name}")
            if verify_email_result:
                _do_verify(result)
            return result

    # -------------------------------------------------------------------
    # LAYER 4: Paid API (Hunter.io / Snov.io)
    # -------------------------------------------------------------------
    if not result.email or result.confidence < 40:
        try:
            from .email_providers import find_email_paid
            paid = find_email_paid(domain, 
                                   _get_first_name(owner_name), 
                                   _get_last_name(owner_name))
            if paid.email:
                result.email = paid.email
                result.method = paid.source  # 'hunter_io' or 'snov_io'
                result.confidence = paid.confidence
                logger.info(f"Layer 4 ({paid.source}): {paid.email} for {business_name}")
                if verify_email_result:
                    _do_verify(result)
                return result
        except Exception as e:
            logger.debug(f"Layer 4 error: {e}")

    # -------------------------------------------------------------------
    # Final: If nothing found, return generic or partial pattern result
    # -------------------------------------------------------------------
    if not result.email:
        if result.domain_valid:
            result.email = result.generic_email
            result.method = 'generic'
            result.confidence = 20
            logger.debug(f"Fallback to generic: {result.email} for {business_name}")
        else:
            result.error = result.error or 'No email found via any layer'
            result.method = 'none'

    if verify_email_result and result.email:
        _do_verify(result)
    return result


def _apply_web_search(
    result: EmailHuntResult,
    owner_name: Optional[str],
    business_name: str,
    website: Optional[str],
    domain: Optional[str],
) -> None:
    """Run Layer 3 web search and update result in-place."""
    try:
        from .email_web_search import search_email_for_lead
        search_result = search_email_for_lead(
            owner_name=owner_name or '',
            business_name=business_name,
            website=website,
            
        )
        if search_result.get('email'):
            found = search_result['email']
            conf = search_result.get('confidence', 40)
            # Only upgrade if better than what we have
            if not result.email or conf > result.confidence:
                result.email = found
                result.confidence = conf
                result.method = f"web_search"
                result.all_candidates = (
                    result.all_candidates + search_result.get('emails_found', [])
                )
        else:
            if not result.error:
                result.error = search_result.get('error', 'Web search: no results')
    except Exception as e:
        logger.debug(f"Web search error: {e}")
        if not result.error:
            result.error = f'Web search failed: {str(e)[:50]}'


def _boost_confidence_if_mx(result: EmailHuntResult) -> None:
    """Add +10 confidence if domain has valid MX records."""
    if result.domain_valid:
        result.confidence = min(result.confidence + 10, 90)


def _get_first_name(owner_name: Optional[str]) -> Optional[str]:
    if not owner_name:
        return None
    parts = normalize_name(owner_name)
    return parts.get('first') if parts else None


def _get_last_name(owner_name: Optional[str]) -> Optional[str]:
    if not owner_name:
        return None
    parts = normalize_name(owner_name)
    return parts.get('last') if parts else None


# ---------------------------------------------------------------------------
# Batch helpers
# ---------------------------------------------------------------------------

def hunt_emails_batch(
    leads,  # list of dicts or DB row objects
    enable_web_search: bool = False,
    verify_mx: bool = True,
    progress_callback=None,
) -> List[Dict]:
    """
    Hunt emails for a list of leads.

    Args:
        leads: Iterable of lead dicts (or sqlite3.Row objects)
        enable_web_search: Enable Tavily search layer
        verify_mx: Verify MX records
        progress_callback: Optional callable(current, total)

    Returns:
        List of result dicts parallel to input leads
    """
    results = []
    total = len(leads) if hasattr(leads, '__len__') else 0

    for idx, lead in enumerate(leads):
        if progress_callback and total:
            progress_callback(idx + 1, total)

        # Support both dicts and sqlite3.Row
        def g(key, default=None):
            try:
                return lead[key] or default
            except (KeyError, IndexError, TypeError):
                return default

        result = hunt_email(
            owner_name=g('owner_name', ''),
            business_name=g('business_name', ''),
            website=g('website'),
            website_text=g('website_text'),
            places_email=g('places_email'),
            enable_web_search=enable_web_search,
            verify_mx=verify_mx,
        )

        results.append({
            'lead_id': g('id'),
            'email': result.email,
            'confidence': result.confidence,
            'method': result.method,
            'error': result.error,
            'domain_valid': result.domain_valid,
            'generic_email': result.generic_email,
            'contact_page_text': result.contact_page_text,
            'all_candidates': result.all_candidates,
        })

    return results
