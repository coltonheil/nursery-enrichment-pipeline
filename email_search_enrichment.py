"""
Phase 2: Email Search Enrichment via Brave Search
Finds emails for leads with contact names but no emails.
"""

import re
import time
from database.models import get_db_connection, log_action

def brave_search(query, count=2):
    """Search using Brave Search API."""
    import os
    import requests
    
    api_key = os.getenv('BRAVE_API_KEY')
    if not api_key:
        raise ValueError("BRAVE_API_KEY not found in environment")
    
    url = "https://api.search.brave.com/res/v1/web/search"
    headers = {
        "Accept": "application/json",
        "X-Subscription-Token": api_key
    }
    params = {
        "q": query,
        "count": count
    }
    
    response = requests.get(url, headers=headers, params=params, timeout=10)
    response.raise_for_status()
    
    data = response.json()
    
    # Try different result locations
    results = []
    if 'web' in data and 'results' in data['web']:
        results = data['web']['results']
    elif 'mixed' in data:
        # New API format
        mixed = data['mixed']
        results = mixed.get('main', []) + mixed.get('top', []) + mixed.get('side', [])
    
    return results

def fetch_page(url, timeout=5):
    """Fetch page content (reuse existing scraper logic)."""
    import requests
    from bs4 import BeautifulSoup
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    
    response = requests.get(url, headers=headers, timeout=timeout, allow_redirects=True)
    response.raise_for_status()
    
    soup = BeautifulSoup(response.text, 'html.parser')
    
    # Remove scripts, styles, etc.
    for element in soup(['script', 'style', 'meta', 'link']):
        element.decompose()
    
    return soup.get_text(separator=' ', strip=True)

def extract_emails_from_text(text):
    """Extract all email addresses from text."""
    # Pattern: username@domain.tld
    pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    emails = re.findall(pattern, text, re.IGNORECASE)
    
    # Filter out common junk
    junk_patterns = [
        r'example\.com',
        r'test\.com',
        r'yourdomain\.com',
        r'email\.com',
        r'sentry\.io',
        r'privacy@',
        r'legal@',
        r'noreply@',
        r'no-reply@',
        r'donotreply@',
        r'support@',
        r'@facebook\.com',
        r'@twitter\.com',
        r'@youtube\.com',
    ]
    
    filtered = []
    for email in emails:
        if not any(re.search(p, email, re.I) for p in junk_patterns):
            filtered.append(email.lower())
    
    return list(set(filtered))  # Dedupe

def score_email_relevance(email, contact_name, business_name):
    """Score how likely this email belongs to the contact."""
    score = 0
    email_local = email.split('@')[0].lower()
    contact_parts = contact_name.lower().split()
    
    # High confidence: First or last name in email
    for part in contact_parts:
        if len(part) > 2 and part in email_local:
            score += 50
    
    # Medium confidence: Business name in domain
    domain = email.split('@')[1].lower()
    business_words = business_name.lower().split()
    for word in business_words:
        if len(word) > 3 and word in domain:
            score += 30
    
    # Low confidence: Common personal domains
    if any(d in domain for d in ['gmail.com', 'yahoo.com', 'outlook.com', 'hotmail.com']):
        score += 10
    
    # Penalty: Generic emails
    if any(g in email_local for g in ['info', 'contact', 'sales', 'admin', 'office']):
        score -= 20
    
    return score

def calculate_email_confidence(email, contact_name, business_name, source):
    """
    Calculate confidence score (0-100) for an email address.
    
    Factors:
    - Name match in email (50 points max)
    - Business domain match (30 points max)
    - Source quality (20 points max)
    - Penalties for generic patterns
    """
    score = 0
    email_local = email.split('@')[0].lower()
    domain = email.split('@')[1].lower()
    
    # Name matching (0-50 points)
    contact_parts = contact_name.lower().split()
    for part in contact_parts:
        if len(part) > 2 and part in email_local:
            score += 50  # Full name match
            break
        elif len(part) > 2 and part[0] == email_local[0]:
            score += 15  # First initial match
    
    # Business domain match (0-30 points)
    business_words = business_name.lower().replace('&', '').replace(',', '').split()
    for word in business_words:
        if len(word) > 3 and word in domain:
            score += 30
            break
    
    # Source quality (0-20 points)
    if source == 'snippet':
        score += 20  # Found in search snippet (high confidence)
    elif source == 'page':
        score += 15  # Found on page (good confidence)
    elif source == 'gemini':
        score += 10  # Extracted by AI (moderate confidence)
    
    # Domain type bonus
    if not any(d in domain for d in ['gmail.com', 'yahoo.com', 'outlook.com', 'hotmail.com']):
        score += 10  # Business domain
    
    # Penalties
    if any(g in email_local for g in ['info', 'contact', 'sales', 'admin', 'office', 'support']):
        score -= 20  # Generic business email
    
    if email_local.replace('.', '').replace('_', '').isdigit():
        score -= 30  # All numbers (spam pattern)
    
    # Clamp to 0-100
    return max(0, min(100, score))

def find_best_email(emails, contact_name, business_name):
    """Return the most relevant email (always returns best match, even if low confidence)."""
    if not emails:
        return None
    
    scored = [(e, score_email_relevance(e, contact_name, business_name)) 
              for e in emails]
    scored.sort(key=lambda x: x[1], reverse=True)
    
    # Always return best match, regardless of score
    return scored[0][0]

def enrich_emails_via_search(batch_size=50, test_mode=False):
    """
    Phase 2: Find emails via web search for leads with names but no emails.
    """
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get target leads
    limit_clause = f"LIMIT {batch_size}" if batch_size else ""
    
    cursor.execute(f"""
        SELECT id, business_name, contact_name, city, state, website, tier
        FROM leads
        WHERE tier IN ('A', 'B')
          AND contact_name IS NOT NULL
          AND (owner_email IS NULL OR owner_email = '')
        ORDER BY 
          CASE tier WHEN 'A' THEN 1 WHEN 'B' THEN 2 END,
          score DESC
        {limit_clause}
    """)
    
    leads = cursor.fetchall()
    
    print("=" * 80)
    print("PHASE 2: EMAIL SEARCH ENRICHMENT")
    print("=" * 80)
    print(f"Found {len(leads)} leads with names but no emails")
    print()
    
    if test_mode:
        print("⚠️  TEST MODE: Database updates disabled")
        print()
    
    stats = {
        'total': len(leads),
        'emails_found': 0,
        'searches_used': 0,
        'pages_fetched': 0,
        'errors': 0,
        'found_in_snippet': 0,
        'found_in_page': 0
    }
    
    for idx, lead in enumerate(leads, 1):
        lead_id, business_name, contact_name, city, state, website, tier = lead
        
        print(f"[{idx}/{len(leads)}] {business_name} - {contact_name} (Tier {tier})")
        
        try:
            # Build search query (without quotes - Brave API seems to prefer this)
            query = f'{business_name} {contact_name} email'
            
            print(f"   🔍 Searching...", flush=True)
            
            # Search with Brave
            results = brave_search(query, count=2)
            stats['searches_used'] += 1
            
            found_email = None
            found_confidence = 0
            source = None
            
            # Quick check: Extract from snippets first
            snippet_emails = []
            for result in results:
                snippet = result.get('description', '')
                title = result.get('title', '')
                combined_text = f"{title} {snippet}"
                
                emails = extract_emails_from_text(combined_text)
                snippet_emails.extend(emails)
                
                if emails:
                    best = find_best_email(emails, contact_name, business_name)
                    if best:
                        confidence = calculate_email_confidence(best, contact_name, business_name, 'snippet')
                        # Accept all emails, regardless of confidence
                        found_email = best
                        found_confidence = confidence
                        source = 'snippet'
                        stats['found_in_snippet'] += 1
                        
                        # Confidence indicator
                        if confidence >= 80:
                            conf_icon = "✅"
                        elif confidence >= 50:
                            conf_icon = "⚠️ "
                        elif confidence >= 20:
                            conf_icon = "⚙️ "
                        else:
                            conf_icon = "❓"
                        
                        print(f"   {conf_icon} Found in snippet: {found_email} (confidence: {confidence}%)", flush=True)
                        break
            
            # Fetch full pages (always try, even if snippet had low-confidence emails)
            if not found_email:
                for result_idx, result in enumerate(results[:2], 1):
                    url = result.get('url', '')
                    if not url:
                        continue
                    
                    # Skip Spokeo (paywall), yellowpages (often generic)
                    if 'spokeo.com' in url.lower():
                        print(f"   ⏭️  Skipping Spokeo (paywall)", flush=True)
                        continue
                    
                    try:
                        page_text = fetch_page(url, timeout=5)
                        stats['pages_fetched'] += 1
                        
                        emails = extract_emails_from_text(page_text)
                        
                        if emails:
                            best = find_best_email(emails, contact_name, business_name)
                            if best:
                                confidence = calculate_email_confidence(best, contact_name, business_name, 'page')
                                found_email = best
                                found_confidence = confidence
                                source = 'page'
                                stats['found_in_page'] += 1
                                
                                # Confidence indicator
                                if confidence >= 80:
                                    conf_icon = "✅"
                                elif confidence >= 50:
                                    conf_icon = "⚠️ "
                                elif confidence >= 20:
                                    conf_icon = "⚙️ "
                                else:
                                    conf_icon = "❓"
                                
                                print(f"   {conf_icon} Found on page: {found_email} (confidence: {confidence}%)", flush=True)
                                break
                    except Exception as e:
                        print(f"   ❌ Failed to fetch: {str(e)[:80]}", flush=True)
            
            # Update database
            if found_email:
                if not test_mode:
                    cursor.execute("""
                        UPDATE leads
                        SET owner_email = ?,
                            email_confidence = ?
                        WHERE id = ?
                    """, (found_email, found_confidence, lead_id))
                    conn.commit()
                    
                    log_action(lead_id, f'email_search_{source}', 
                              f"Found via search: {found_email} (confidence: {found_confidence}%)", cursor)
                
                stats['emails_found'] += 1
                
                # Track by confidence level
                if found_confidence >= 80:
                    stats['high_confidence'] = stats.get('high_confidence', 0) + 1
                elif found_confidence >= 50:
                    stats['medium_confidence'] = stats.get('medium_confidence', 0) + 1
                elif found_confidence >= 20:
                    stats['low_confidence'] = stats.get('low_confidence', 0) + 1
                else:
                    stats['very_low_confidence'] = stats.get('very_low_confidence', 0) + 1
            else:
                print(f"   ⚠️  No email found", flush=True)
                if not test_mode:
                    log_action(lead_id, 'email_search_none', 
                              "No email found in search results", cursor)
            
        except Exception as e:
            stats['errors'] += 1
            print(f"   ❌ Error: {str(e)[:100]}", flush=True)
            if not test_mode:
                log_action(lead_id, 'email_search_error', str(e)[:200], cursor)
        
        print(flush=True)
        
        # Rate limiting
        time.sleep(1.5)  # Be nice to Brave API
    
    conn.close()
    
    # Summary
    print()
    print("=" * 80)
    print("PHASE 2 COMPLETE")
    print("=" * 80)
    print(f"Total leads processed: {stats['total']}")
    print(f"Emails found: {stats['emails_found']} ({stats['emails_found']/stats['total']*100 if stats['total'] > 0 else 0:.1f}%)")
    print(f"  - Found in snippets: {stats['found_in_snippet']}")
    print(f"  - Found in pages: {stats['found_in_page']}")
    print()
    print("Confidence breakdown:")
    print(f"  - High (80-100): {stats.get('high_confidence', 0)} ✅")
    print(f"  - Medium (50-79): {stats.get('medium_confidence', 0)} ⚠️ ")
    print(f"  - Low (20-49): {stats.get('low_confidence', 0)} ⚙️ ")
    print(f"  - Very Low (0-19): {stats.get('very_low_confidence', 0)} ❓")
    print()
    print(f"Searches used: {stats['searches_used']}")
    print(f"Pages fetched: {stats['pages_fetched']}")
    print(f"Errors: {stats['errors']}")
    print()
    
    if stats['emails_found'] > 0:
        print(f"✅ Success! Added {stats['emails_found']} emails via web search")
    
    return stats

if __name__ == '__main__':
    import sys
    import os
    from dotenv import load_dotenv
    
    load_dotenv()
    
    # Parse arguments
    test_mode = '--test' in sys.argv
    
    # Get batch size
    batch_size = 5 if test_mode else 50
    for arg in sys.argv:
        if arg.startswith('--limit='):
            batch_size = int(arg.split('=')[1])
    
    # Run enrichment
    enrich_emails_via_search(batch_size=batch_size, test_mode=test_mode)
