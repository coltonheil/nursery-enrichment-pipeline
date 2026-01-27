"""
Email Pattern Generation and Detection

Generates candidate email addresses from owner names and domains,
and detects email patterns from known examples.
"""

import re
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse

# Common email patterns with prevalence weights (based on industry research)
EMAIL_PATTERNS = [
    ('first.last', '{first}.{last}@{domain}', 0.35),
    ('first', '{first}@{domain}', 0.25),
    ('flast', '{f}{last}@{domain}', 0.15),
    ('firstl', '{first}{l}@{domain}', 0.10),
    ('first_last', '{first}_{last}@{domain}', 0.08),
    ('last.first', '{last}.{first}@{domain}', 0.03),
    ('f.last', '{f}.{last}@{domain}', 0.02),
    ('lastf', '{last}{f}@{domain}', 0.02),
]

# Titles and suffixes to strip from names
TITLES = ['mr', 'mrs', 'ms', 'miss', 'dr', 'prof', 'rev', 'sr', 'jr', 'ii', 'iii', 'iv']
SUFFIXES = ['jr', 'sr', 'ii', 'iii', 'iv', 'phd', 'md', 'dds', 'esq', 'cpa', 'family', 'families']
# Prefixes/noise to strip
NOISE_PREFIXES = ['a.k.a.', 'aka', 'attn:', 'attn', 'attention:', 'c/o', 'care of']

# Generic email prefixes to deprioritize
GENERIC_PREFIXES = [
    'info', 'contact', 'hello', 'hi', 'sales', 'support', 'admin',
    'office', 'help', 'team', 'mail', 'email', 'enquiries', 'inquiries',
    'general', 'marketing', 'billing', 'orders', 'service', 'customerservice'
]


def normalize_name(full_name: str) -> Optional[Dict[str, str]]:
    """
    Parse and normalize owner name into components.
    
    Args:
        full_name: Full name like "John Smith" or "Dr. John P. Smith Jr."
        
    Returns:
        Dict with 'first', 'last', 'f' (first initial), 'l' (last initial)
        or None if name cannot be parsed
    """
    if not full_name or not full_name.strip():
        return None
    
    # Clean the name
    name = full_name.strip()
    
    # Strip noise prefixes (a.k.a., ATTN:, etc.)
    name_lower = name.lower()
    for prefix in NOISE_PREFIXES:
        if name_lower.startswith(prefix):
            name = name[len(prefix):].strip()
            name_lower = name.lower()
    
    # Handle co-owners: "Bob & Mary Johnson" -> "Bob Johnson" or "Grant & Joan Wery" -> "Grant Wery"
    # Also handle couples without shared surname: "Wayne and Michelle" -> just "Wayne"
    if ' & ' in name or ' and ' in name.lower():
        parts = re.split(r'\s*[&]\s*|\s+and\s+', name, flags=re.IGNORECASE)
        # Get the first person's first name
        first_person = parts[0].strip()
        
        if len(parts) > 1:
            second_part = parts[1].strip().split()
            first_person_words = first_person.split()
            
            # Check if second part has more than just a first name (i.e., has a surname)
            if len(second_part) > 1:
                # "Bob & Mary Johnson" -> second_part = ["Mary", "Johnson"]
                # Last word is the shared surname
                last_name = second_part[-1]
                if first_person_words:
                    name = first_person_words[0] + ' ' + last_name
                else:
                    name = first_person
            elif len(second_part) == 1 and len(first_person_words) > 1:
                # "Bob Johnson & Mary" -> first person has last name
                name = first_person
            else:
                # "Wayne and Michelle" -> no shared surname, just use first name
                # This will become a single-name case
                name = first_person_words[0] if first_person_words else first_person
        else:
            name = first_person
    
    # Remove titles and suffixes
    words = name.split()
    cleaned_words = []
    
    for word in words:
        word_lower = word.lower().rstrip('.,')
        if word_lower not in TITLES and word_lower not in SUFFIXES:
            # Also remove single letters (middle initials)
            if len(word.rstrip('.')) > 1 or len(cleaned_words) == 0:
                cleaned_words.append(word.rstrip('.,'))
    
    if len(cleaned_words) < 1:
        return None
    
    # Handle single name - don't duplicate it
    if len(cleaned_words) == 1:
        first = cleaned_words[0].lower()
        first = re.sub(r'[^a-z]', '', first)
        if not first:
            return None
        return {
            'first': first,
            'last': None,  # No last name - will trigger first-name-only patterns
            'f': first[0],
            'l': None,
            'full': full_name,
            'single_name': True
        }
    
    # First and last name
    first = cleaned_words[0].lower()
    last = cleaned_words[-1].lower()
    
    # Remove any non-alphanumeric characters
    first = re.sub(r'[^a-z]', '', first)
    last = re.sub(r'[^a-z]', '', last)
    
    if not first or not last:
        return None
    
    return {
        'first': first,
        'last': last,
        'f': first[0],
        'l': last[0],
        'full': full_name
    }


def extract_domain(url_or_email: str) -> Optional[str]:
    """
    Extract domain from URL or email address.
    
    Args:
        url_or_email: Website URL or email address
        
    Returns:
        Domain string (e.g., 'example.com') or None
    """
    if not url_or_email:
        return None
    
    url_or_email = url_or_email.strip()
    
    # If it's an email, extract domain
    if '@' in url_or_email:
        return url_or_email.split('@')[-1].lower()
    
    # Parse URL
    if not url_or_email.startswith(('http://', 'https://')):
        url_or_email = 'https://' + url_or_email
    
    try:
        parsed = urlparse(url_or_email)
        domain = parsed.netloc or parsed.path.split('/')[0]
        
        # Remove www. prefix
        if domain.startswith('www.'):
            domain = domain[4:]
        
        # Remove port if present
        domain = domain.split(':')[0]
        
        return domain.lower() if domain else None
    except Exception:
        return None


def generate_email_patterns(
    first_name: str,
    last_name: Optional[str],
    domain: str,
    include_weights: bool = True
) -> List[Dict]:
    """
    Generate possible email addresses from name and domain.
    
    Args:
        first_name: First name (already cleaned)
        last_name: Last name (already cleaned) - can be None for single names
        domain: Email domain (without @)
        include_weights: Include prevalence weights
        
    Returns:
        List of dicts with 'email', 'pattern', 'weight'
    """
    if not first_name or not domain:
        return []
    
    # Clean inputs
    first = first_name.lower().strip()
    first = re.sub(r'[^a-z]', '', first)
    domain = domain.lower().strip()
    
    if not first:
        return []
    
    results = []
    seen_emails = set()
    
    # Handle single-name case (no last name)
    if not last_name:
        # Only generate first-name patterns
        single_patterns = [
            ('first', '{first}@{domain}', 0.60),  # Most likely for single name
        ]
        
        for pattern_name, pattern_template, weight in single_patterns:
            email = pattern_template.format(first=first, domain=domain)
            if email not in seen_emails:
                seen_emails.add(email)
                result = {'email': email, 'pattern': pattern_name}
                if include_weights:
                    result['weight'] = weight
                results.append(result)
        
        return results
    
    # Full name case - clean last name
    last = last_name.lower().strip()
    last = re.sub(r'[^a-z]', '', last)
    
    if not last:
        # Fall back to first-name only
        return generate_email_patterns(first_name, None, domain, include_weights)
    
    for pattern_name, pattern_template, weight in EMAIL_PATTERNS:
        try:
            email = pattern_template.format(
                first=first,
                last=last,
                f=first[0],
                l=last[0],
                domain=domain
            )
            
            # Avoid duplicates (e.g., if first == last)
            if email not in seen_emails:
                seen_emails.add(email)
                result = {
                    'email': email,
                    'pattern': pattern_name,
                }
                if include_weights:
                    result['weight'] = weight
                results.append(result)
        except (IndexError, KeyError):
            continue
    
    # Sort by weight (most likely first)
    if include_weights:
        results.sort(key=lambda x: x.get('weight', 0), reverse=True)
    
    return results


def generate_from_owner_name(
    owner_name: str,
    website_or_domain: str
) -> List[Dict]:
    """
    High-level function to generate email candidates from owner name and website.
    
    Args:
        owner_name: Full owner name
        website_or_domain: Website URL or domain
        
    Returns:
        List of email candidates with pattern and weight
    """
    name_parts = normalize_name(owner_name)
    if not name_parts:
        return []
    
    domain = extract_domain(website_or_domain)
    if not domain:
        return []
    
    return generate_email_patterns(
        name_parts['first'],
        name_parts['last'],
        domain
    )


def detect_domain_pattern(known_emails: List[str], domain: str) -> Optional[str]:
    """
    Detect the email pattern used by a domain from known examples.
    
    Args:
        known_emails: List of known emails from this domain
        domain: The domain to analyze
        
    Returns:
        Pattern name (e.g., 'first.last') or None
    """
    if not known_emails or not domain:
        return None
    
    domain = domain.lower()
    
    # Filter to emails matching this domain
    domain_emails = [e for e in known_emails if e.lower().endswith('@' + domain)]
    
    if not domain_emails:
        return None
    
    # Count pattern occurrences
    pattern_counts = {}
    
    for email in domain_emails:
        local_part = email.split('@')[0].lower()
        
        # Try to identify pattern
        if '.' in local_part:
            parts = local_part.split('.')
            if len(parts) == 2:
                if len(parts[0]) == 1:
                    pattern_counts['f.last'] = pattern_counts.get('f.last', 0) + 1
                else:
                    pattern_counts['first.last'] = pattern_counts.get('first.last', 0) + 1
        elif '_' in local_part:
            pattern_counts['first_last'] = pattern_counts.get('first_last', 0) + 1
        elif len(local_part) > 2:
            # Could be first, flast, firstl, etc.
            # Hard to detect without more info
            pattern_counts['first'] = pattern_counts.get('first', 0) + 1
    
    if not pattern_counts:
        return None
    
    # Return most common pattern
    return max(pattern_counts.keys(), key=lambda k: pattern_counts[k])


def is_generic_email(email: str) -> bool:
    """Check if email appears to be a generic/role-based address."""
    if not email:
        return False
    
    local_part = email.split('@')[0].lower()
    return local_part in GENERIC_PREFIXES


def classify_email(email: str) -> str:
    """
    Classify an email as personal, generic, or unknown.
    
    Returns: 'personal', 'generic', or 'unknown'
    """
    if not email:
        return 'unknown'
    
    local_part = email.split('@')[0].lower()
    
    if local_part in GENERIC_PREFIXES:
        return 'generic'
    
    # Check if it looks like a name (contains letters, maybe a dot or underscore)
    if re.match(r'^[a-z]+[._]?[a-z]*$', local_part):
        return 'personal'
    
    return 'unknown'


def extract_name_from_email(email: str) -> Optional[Dict[str, str]]:
    """
    Attempt to extract name parts from an email address.
    
    Args:
        email: Email address like john.smith@example.com
        
    Returns:
        Dict with 'first', 'last' or None
    """
    if not email or '@' not in email:
        return None
    
    local_part = email.split('@')[0].lower()
    
    # Try common patterns
    if '.' in local_part:
        parts = local_part.split('.')
        if len(parts) == 2:
            return {'first': parts[0], 'last': parts[1]}
    
    if '_' in local_part:
        parts = local_part.split('_')
        if len(parts) == 2:
            return {'first': parts[0], 'last': parts[1]}
    
    return None


# ============================================================
# Test functions
# ============================================================

def test_patterns():
    """Test pattern generation."""
    print("=== Testing Email Pattern Generation ===\n")
    
    test_cases = [
        ("John Smith", "greenvalleynursery.com"),
        ("Dr. Jane P. Williams Jr.", "example.com"),
        ("Bob & Mary Johnson", "familyfarm.com"),
        ("Single", "domain.com"),
        ("John O'Brien", "obrien-nursery.com"),
    ]
    
    for name, domain in test_cases:
        print(f"Name: {name}")
        print(f"Domain: {domain}")
        
        normalized = normalize_name(name)
        print(f"Normalized: {normalized}")
        
        if normalized:
            patterns = generate_email_patterns(
                normalized['first'],
                normalized['last'],
                domain
            )
            print("Candidates:")
            for p in patterns[:5]:
                print(f"  {p['email']:40} ({p['pattern']}, weight={p['weight']:.2f})")
        print()


if __name__ == '__main__':
    test_patterns()
