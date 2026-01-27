"""
Email Web Search Module

Two approaches:
1. Brave API (fast, 2000 free searches/month) - requires API key
2. Browser automation via Clawdbot browser tool (slower, but works)

For batch processing, Brave API is recommended.
"""

import re
import time
import logging
import subprocess
import json
from typing import Dict, List, Optional
from urllib.parse import quote_plus

logger = logging.getLogger(__name__)

# Email extraction pattern
EMAIL_PATTERN = re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}')

# Generic prefixes to deprioritize
GENERIC_PREFIXES = [
    'info', 'contact', 'hello', 'sales', 'support', 'admin',
    'office', 'help', 'team', 'mail', 'email', 'enquiries',
    'general', 'marketing', 'billing', 'orders', 'service'
]


def extract_emails_from_text(text: str, target_domain: Optional[str] = None) -> List[str]:
    """Extract and rank emails from text."""
    if not text:
        return []
    
    emails = EMAIL_PATTERN.findall(text)
    emails = list(set(e.lower() for e in emails))
    
    # Filter out obvious junk
    junk_domains = [
        'example.com', 'schema.org', 'sentry.io', 'w3.org', 
        'wix.com', 'wordpress.', 'cloudflare', 'microsoft.com',
        'bing.com', 'google.com', 'googleapis.com', 'gstatic.com'
    ]
    
    emails = [e for e in emails if 
              '.' in e.split('@')[1] and
              len(e.split('@')[0]) > 1 and
              not e.endswith('.png') and
              not e.endswith('.jpg') and
              not e.endswith('.gif') and
              not any(j in e for j in junk_domains)]
    
    # Score and sort emails
    def score_email(email):
        local = email.split('@')[0]
        domain = email.split('@')[1]
        
        score = 0
        
        # Prefer target domain
        if target_domain and domain == target_domain:
            score += 100
        
        # Penalize generic prefixes
        if local in GENERIC_PREFIXES:
            score -= 50
        
        # Prefer emails that look like names (contain dot or reasonable length)
        if '.' in local:
            score += 20
        elif len(local) > 3 and len(local) < 20:
            score += 10
        
        return score
    
    emails.sort(key=score_email, reverse=True)
    return emails


def search_with_brave_cli(
    owner_name: str,
    business_name: str,
    domain: Optional[str] = None
) -> Dict:
    """
    Search using Clawdbot's web_search tool via CLI.
    Requires Brave API key to be configured.
    
    This is the RECOMMENDED approach - fast and reliable.
    """
    result = {
        'email': None,
        'emails_found': [],
        'source': 'brave_search',
        'confidence': 0,
        'error': None
    }
    
    query = f'"{owner_name}" "{business_name}" email contact'
    
    try:
        # Use clawdbot CLI to run web search
        # This requires Brave API key configured
        proc = subprocess.run(
            ['clawdbot', 'web-search', '--json', query],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if proc.returncode != 0:
            if 'missing_brave_api_key' in proc.stderr or 'BRAVE_API_KEY' in proc.stderr:
                result['error'] = 'Brave API key not configured'
            else:
                result['error'] = f'Search failed: {proc.stderr[:100]}'
            return result
        
        data = json.loads(proc.stdout)
        
        # Extract emails from search results snippets
        all_text = ''
        for item in data.get('results', []):
            all_text += ' ' + item.get('title', '')
            all_text += ' ' + item.get('description', '')
        
        emails = extract_emails_from_text(all_text, domain)
        
        if emails:
            result['emails_found'] = emails[:5]
            result['email'] = emails[0]
            result['confidence'] = 70 if domain and domain in emails[0] else 50
        
        return result
        
    except subprocess.TimeoutExpired:
        result['error'] = 'Search timeout'
        return result
    except json.JSONDecodeError:
        result['error'] = 'Invalid JSON response'
        return result
    except Exception as e:
        result['error'] = str(e)[:100]
        return result


def search_with_curl_fallback(
    owner_name: str,
    business_name: str,
    domain: Optional[str] = None
) -> Dict:
    """
    Fallback search using curl + web scraping.
    Less reliable but works without API keys.
    
    Uses DuckDuckGo's HTML version.
    """
    result = {
        'email': None,
        'emails_found': [],
        'source': 'duckduckgo_scrape',
        'confidence': 0,
        'error': None
    }
    
    query = f'{owner_name} {business_name} email contact'
    search_url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"
    
    try:
        proc = subprocess.run(
            ['curl', '-s', '-A', 
             'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
             '-L', search_url],
            capture_output=True,
            text=True,
            timeout=15
        )
        
        if proc.returncode != 0:
            result['error'] = 'curl failed'
            return result
        
        emails = extract_emails_from_text(proc.stdout, domain)
        
        if emails:
            result['emails_found'] = emails[:5]
            result['email'] = emails[0]
            result['confidence'] = 40 if domain and domain in emails[0] else 30
        
        return result
        
    except subprocess.TimeoutExpired:
        result['error'] = 'Search timeout'
        return result
    except Exception as e:
        result['error'] = str(e)[:100]
        return result


def search_email_for_lead(
    owner_name: str,
    business_name: str,
    website: Optional[str] = None,
    use_brave: bool = True
) -> Dict:
    """
    Search for a lead's email.
    
    Args:
        owner_name: Owner's name
        business_name: Business name
        website: Website URL (to extract domain for prioritization)
        use_brave: Try Brave API first (recommended)
    
    Returns:
        Dict with 'email', 'confidence', 'source', 'error'
    """
    from .email_patterns import extract_domain
    
    domain = extract_domain(website) if website else None
    
    # Try Brave API first (if enabled)
    if use_brave:
        result = search_with_brave_cli(owner_name, business_name, domain)
        if result['email'] or 'API key not configured' not in str(result.get('error', '')):
            return result
        
        logger.info("Brave API not available, falling back to scraping")
    
    # Fallback to curl scraping
    return search_with_curl_fallback(owner_name, business_name, domain)


# ============================================================
# Batch processing
# ============================================================

def batch_search_emails(
    leads: List[Dict],
    delay: float = 2.0,
    max_leads: int = 50,
    use_brave: bool = True
) -> List[Dict]:
    """
    Search for emails for multiple leads.
    
    Args:
        leads: List of dicts with 'owner_name', 'business_name', 'website'
        delay: Seconds between searches
        max_leads: Maximum leads to process
        use_brave: Try Brave API first
    
    Returns:
        List of results
    """
    results = []
    
    for i, lead in enumerate(leads[:max_leads]):
        owner = lead.get('owner_name', '')
        business = lead.get('business_name', '')
        website = lead.get('website', '')
        
        if not owner or not business:
            results.append({
                'lead': lead,
                'error': 'Missing owner_name or business_name'
            })
            continue
        
        logger.info(f"[{i+1}/{min(len(leads), max_leads)}] Searching: {owner} at {business}")
        
        result = search_email_for_lead(owner, business, website, use_brave)
        result['lead'] = lead
        results.append(result)
        
        # Rate limiting
        if i < len(leads) - 1:
            time.sleep(delay)
    
    return results


# ============================================================
# Test
# ============================================================

def test_search():
    """Test email search."""
    logging.basicConfig(level=logging.INFO)
    
    print("Testing email web search...\n")
    
    result = search_email_for_lead(
        owner_name="Dave Bresina",
        business_name="Dave Bresina's Nursery",
        website=None,
        use_brave=True
    )
    
    print(f"\nResult:")
    print(f"  Email: {result.get('email')}")
    print(f"  Confidence: {result.get('confidence')}%")
    print(f"  Source: {result.get('source')}")
    print(f"  All found: {result.get('emails_found')}")
    print(f"  Error: {result.get('error')}")


if __name__ == '__main__':
    test_search()
