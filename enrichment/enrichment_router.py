"""
Enrichment Router — Step 1 Entry Point
=======================================
Single function that routes step-1 enrichment by segment.

  nursery            → Google Places API  (rating, reviews, phone, website)
  hemp / cannabis    → Brave web search   (website, phone — better hit rate on registry data)

Both paths return the same dict shape so the pipeline doesn't branch downstream.
Import and call enrich_lead_step1(lead) everywhere instead of enrich_business() directly.

Facebook Fallback
-----------------
enrich_lead_facebook_fallback(lead) is a secondary enrichment pass for hemp/cannabis
leads that still have no email after the main pipeline finishes.  It searches for the
business's Facebook page via Tavily and scrapes the /about tab for a contact email.
Call it after Stage 5 (email hunting) for leads where owner_email is still NULL.
"""

import logging
from enrichment.google_places import enrich_business
from enrichment.web_search_enrichment import (
    web_search_enrich,
    search_facebook_page,
    extract_email_from_facebook_page,
    _extract_email_from_text,
)

logger = logging.getLogger(__name__)

# Segments that should use web search instead of Google Places
WEB_SEARCH_SEGMENTS = {'hemp', 'cannabis', 'hemp_producer', 'cannabis_grower'}


def enrich_lead_step1(lead: dict) -> dict:
    """
    Route step-1 enrichment based on lead segment.

    Args:
        lead: dict (or sqlite3.Row converted to dict) with at minimum:
              business_name, city, state, zip, segment

    Returns:
        dict with at minimum: website (str|None), phone (str|None)
        OR {'error': '...'} if enrichment failed
    """
    segment = (lead.get('segment') or 'nursery').lower()

    if segment in WEB_SEARCH_SEGMENTS:
        logger.info(f"[router] segment={segment} → web_search for '{lead.get('business_name')}'")
        return web_search_enrich(
            business_name=lead.get('business_name', ''),
            city=lead.get('city', '') or '',
            state=lead.get('state', '') or '',
            zip_code=lead.get('zip', '') or '',
        )
    else:
        logger.info(f"[router] segment={segment} → google_places for '{lead.get('business_name')}'")
        result = enrich_business(
            business_name=lead.get('business_name', ''),
            city=lead.get('city', '') or '',
            state=lead.get('state', '') or '',
        )
        if 'error' not in result:
            result.setdefault('enrichment_source', 'google_places')
        return result


# ---------------------------------------------------------------------------
# Facebook Fallback — Hemp / Cannabis leads with no email
# ---------------------------------------------------------------------------

def enrich_lead_facebook_fallback(lead: dict) -> dict | None:
    """
    Fallback email discovery via Facebook business page for hemp/cannabis leads.

    Trigger conditions (must satisfy ALL):
      - Lead segment is hemp, cannabis, hemp_producer, or cannabis_grower
      - Lead has NO owner_email yet (or owner_email is falsy)

    Strategy:
      1. Tavily search: '"{business_name}" {city} {state} site:facebook.com'
      2. Scrape the Facebook page's /about tab with the standard web scraper
      3. Extract the first valid email found in the page text
      4. Also check the Tavily snippet directly (fast path, no scrape needed)

    Args:
        lead: dict with at minimum:
              business_name, city, state, segment, owner_email (may be None)

    Returns:
        dict {'email': str, 'source': 'facebook_page', 'facebook_url': str}
            if an email was found
        None
            if trigger conditions not met OR no email discovered
    """
    # ── Guard: only for hemp/cannabis ────────────────────────────────────────
    segment = (lead.get('segment') or '').lower()
    if segment not in WEB_SEARCH_SEGMENTS:
        logger.debug(f"[fb_fallback] skipping — segment={segment} not hemp/cannabis")
        return None

    # ── Guard: only if no email already ──────────────────────────────────────
    existing_email = (lead.get('owner_email') or '').strip()
    if existing_email:
        logger.debug(f"[fb_fallback] skipping — already has email: {existing_email}")
        return None

    business_name = lead.get('business_name') or ''
    city          = lead.get('city') or ''
    state         = lead.get('state') or ''

    if not business_name:
        logger.warning("[fb_fallback] skipping — no business_name")
        return None

    logger.info(f"[fb_fallback] searching Facebook for '{business_name}' ({city}, {state})")

    # ── Step 1: Find Facebook page via Tavily ─────────────────────────────────
    fb_result = search_facebook_page(business_name, city, state)

    if 'error' in fb_result:
        logger.info(f"[fb_fallback] Tavily search failed: {fb_result['error']}")
        return None

    fb_url  = fb_result.get('url', '')
    snippet = fb_result.get('snippet', '')

    # ── Step 2: Fast path — check Tavily snippet for an email ────────────────
    if snippet:
        email_in_snippet = _extract_email_from_text(snippet)
        if email_in_snippet:
            logger.info(f"[fb_fallback] ✓ email found in snippet: {email_in_snippet}")
            return {
                'email':        email_in_snippet,
                'source':       'facebook_page',
                'facebook_url': fb_url,
            }

    # ── Step 3: Scrape the Facebook page for email ────────────────────────────
    if not fb_url:
        return None

    logger.info(f"[fb_fallback] scraping Facebook page: {fb_url}")
    email_from_page = extract_email_from_facebook_page(fb_url)

    if email_from_page:
        logger.info(f"[fb_fallback] ✓ email found on page: {email_from_page}")
        return {
            'email':        email_from_page,
            'source':       'facebook_page',
            'facebook_url': fb_url,
        }

    logger.info(f"[fb_fallback] no email found for '{business_name}'")
    return None
