"""
Email Hunter - Multi-strategy email finder for nursery leads.

Strategies (in order of preference):
1. Pattern inference - Generate emails from common patterns
2. MX verification - Validate domain has email capability
3. Web search (optional) - Search web for public emails

Usage:
    from enrichment.email_hunter import hunt_email, hunt_emails_batch
    
    # Single lead
    result = hunt_email(
        owner_name="John Smith",
        business_name="Green Valley Nursery",
        website="https://greenvalleynursery.com"
    )
    
    # Batch processing
    results = hunt_emails_batch(leads_df, enable_web_search=False)
"""

import logging
from typing import Dict, List, Optional, Tuple
import pandas as pd
from dataclasses import dataclass

from .email_patterns import (
    generate_email_patterns,
    extract_domain,
    normalize_name
)
from .email_verifier import EmailVerifier

logger = logging.getLogger(__name__)


@dataclass
class EmailHuntResult:
    """Result of email hunting."""
    email: Optional[str] = None
    confidence: int = 0
    method: str = 'none'
    all_candidates: List[str] = None
    domain_valid: bool = False
    mx_hosts: List[str] = None
    error: Optional[str] = None
    
    def __post_init__(self):
        if self.all_candidates is None:
            self.all_candidates = []
        if self.mx_hosts is None:
            self.mx_hosts = []
    
    def to_dict(self) -> Dict:
        return {
            'email': self.email,
            'confidence': self.confidence,
            'method': self.method,
            'all_candidates': self.all_candidates,
            'domain_valid': self.domain_valid,
            'mx_hosts': self.mx_hosts,
            'error': self.error
        }


def hunt_email(
    owner_name: str,
    business_name: str,
    website: Optional[str] = None,
    enable_web_search: bool = False,
    verify_mx: bool = True
) -> EmailHuntResult:
    """
    Hunt for an email address using multiple strategies.
    
    Args:
        owner_name: Full name of the owner (e.g., "John Smith")
        business_name: Name of the business
        website: Business website URL
        enable_web_search: Enable web search (slower, requires Brave API)
        verify_mx: Verify domain has valid MX records
    
    Returns:
        EmailHuntResult with found email and metadata
    """
    result = EmailHuntResult()
    
    # Extract domain from website
    domain = extract_domain(website) if website else None
    
    if not domain:
        logger.debug(f"No domain for {business_name}")
        result.error = 'No domain available'
        
        # Try web search as fallback if enabled
        if enable_web_search:
            return _hunt_via_web_search(owner_name, business_name, result)
        return result
    
    # Check if domain has valid MX records
    if verify_mx:
        verifier = EmailVerifier()
        mx_hosts = verifier.get_mx_records(domain)
        result.domain_valid = len(mx_hosts) > 0
        result.mx_hosts = mx_hosts
        
        if not result.domain_valid:
            logger.debug(f"No MX records for {domain}")
            result.error = f"Domain {domain} has no MX records"
            
            # Try web search as fallback if enabled
            if enable_web_search:
                return _hunt_via_web_search(owner_name, business_name, result)
            return result
    
    # Parse owner name
    name_parts = normalize_name(owner_name)
    
    if not name_parts or not name_parts.get('first') or not name_parts.get('last'):
        logger.debug(f"Could not parse name: {owner_name}")
        # Use business-based generic email
        result.email = f"info@{domain}"
        result.confidence = 20
        result.method = 'generic_fallback'
        return result
    
    first = name_parts['first']
    last = name_parts['last']
    
    # Generate candidates - returns list of dicts with 'email', 'pattern', 'weight'
    candidate_dicts = generate_email_patterns(first, last, domain)
    
    if not candidate_dicts:
        result.error = 'No candidates generated'
        return result
    
    # Extract just email strings for the candidates list
    result.all_candidates = [c['email'] for c in candidate_dicts]
    
    # Sort by weight (highest first) and pick the best
    candidate_dicts.sort(key=lambda x: x.get('weight', 0), reverse=True)
    
    # Use the highest-weighted candidate
    best = candidate_dicts[0]
    result.email = best['email']
    result.method = 'pattern_inference'
    
    # Confidence based on pattern weight
    weight = best.get('weight', 0.1)
    if weight >= 0.30:
        result.confidence = 65  # first.last is most common
    elif weight >= 0.20:
        result.confidence = 60  # first is common
    elif weight >= 0.10:
        result.confidence = 50  # flast, firstl
    else:
        result.confidence = 40  # other patterns
    
    # Boost confidence if domain has MX records
    if result.domain_valid:
        result.confidence = min(result.confidence + 10, 80)
    
    return result


def _hunt_via_web_search(
    owner_name: str,
    business_name: str,
    result: EmailHuntResult
) -> EmailHuntResult:
    """Try to find email via web search."""
    try:
        from .email_web_search import search_email_for_lead
        
        search_result = search_email_for_lead(
            owner_name, business_name, website=None, use_brave=True
        )
        
        if search_result.get('email'):
            result.email = search_result['email']
            result.confidence = search_result.get('confidence', 40)
            result.method = f"web_search_{search_result.get('source', 'unknown')}"
            result.all_candidates = search_result.get('emails_found', [])
        else:
            result.error = search_result.get('error', 'No email found via search')
            
    except ImportError:
        result.error = 'Web search module not available'
    except Exception as e:
        result.error = f'Web search failed: {str(e)[:50]}'
    
    return result


def hunt_emails_batch(
    leads_df: pd.DataFrame,
    name_col: str = 'owner_name',
    business_col: str = 'business_name',
    website_col: str = 'website',
    enable_web_search: bool = False,
    verify_mx: bool = True,
    progress_callback: callable = None
) -> pd.DataFrame:
    """
    Hunt emails for a batch of leads.
    
    Args:
        leads_df: DataFrame with lead information
        name_col: Column name for owner name
        business_col: Column name for business name
        website_col: Column name for website
        enable_web_search: Enable web search for leads without domain
        verify_mx: Verify MX records
        progress_callback: Optional callback(current, total) for progress
    
    Returns:
        DataFrame with added columns: email_found, email_confidence, email_method
    """
    results = []
    total = len(leads_df)
    
    for idx, row in leads_df.iterrows():
        owner_name = row.get(name_col, '')
        business_name = row.get(business_col, '')
        website = row.get(website_col, '')
        
        if progress_callback:
            progress_callback(idx + 1, total)
        
        if not owner_name or not business_name:
            results.append({
                'email_found': None,
                'email_confidence': 0,
                'email_method': 'skipped',
                'email_error': 'Missing name or business'
            })
            continue
        
        result = hunt_email(
            owner_name=str(owner_name),
            business_name=str(business_name),
            website=str(website) if website else None,
            enable_web_search=enable_web_search,
            verify_mx=verify_mx
        )
        
        results.append({
            'email_found': result.email,
            'email_confidence': result.confidence,
            'email_method': result.method,
            'email_error': result.error,
            'email_domain_valid': result.domain_valid
        })
    
    # Create results DataFrame
    results_df = pd.DataFrame(results)
    
    # Combine with original (reset index to align)
    output_df = leads_df.reset_index(drop=True).copy()
    for col in results_df.columns:
        output_df[col] = results_df[col]
    
    return output_df


def summarize_results(df: pd.DataFrame) -> Dict:
    """
    Summarize email hunting results.
    
    Args:
        df: DataFrame with email_found, email_confidence columns
    
    Returns:
        Summary statistics
    """
    total = len(df)
    found = df['email_found'].notna().sum()
    
    # Confidence breakdown
    high_conf = (df['email_confidence'] >= 70).sum()
    med_conf = ((df['email_confidence'] >= 40) & (df['email_confidence'] < 70)).sum()
    low_conf = ((df['email_confidence'] > 0) & (df['email_confidence'] < 40)).sum()
    
    # Method breakdown
    methods = df['email_method'].value_counts().to_dict()
    
    # Domain validity
    domain_valid = df.get('email_domain_valid', pd.Series([False]*total)).sum()
    
    return {
        'total_leads': total,
        'emails_found': found,
        'find_rate': f"{(found/total*100):.1f}%" if total > 0 else "0%",
        'high_confidence': high_conf,
        'medium_confidence': med_conf,
        'low_confidence': low_conf,
        'methods': methods,
        'domains_with_mx': domain_valid
    }


# ============================================================
# CLI Interface
# ============================================================

def main():
    """CLI for email hunting."""
    import argparse
    import sys
    
    parser = argparse.ArgumentParser(description='Hunt for email addresses')
    parser.add_argument('--name', required=True, help='Owner name')
    parser.add_argument('--business', required=True, help='Business name')
    parser.add_argument('--website', help='Website URL')
    parser.add_argument('--web-search', action='store_true', help='Enable web search')
    parser.add_argument('--no-mx-verify', action='store_true', help='Skip MX verification')
    parser.add_argument('--json', action='store_true', help='Output JSON')
    
    args = parser.parse_args()
    
    logging.basicConfig(level=logging.INFO)
    
    result = hunt_email(
        owner_name=args.name,
        business_name=args.business,
        website=args.website,
        enable_web_search=args.web_search,
        verify_mx=not args.no_mx_verify
    )
    
    if args.json:
        import json
        print(json.dumps(result.to_dict(), indent=2))
    else:
        print(f"\n{'='*50}")
        print(f"Email Hunt Results")
        print(f"{'='*50}")
        print(f"Name: {args.name}")
        print(f"Business: {args.business}")
        print(f"Website: {args.website or 'N/A'}")
        print(f"{'='*50}")
        print(f"Email Found: {result.email or 'None'}")
        print(f"Confidence: {result.confidence}%")
        print(f"Method: {result.method}")
        print(f"Domain Valid: {result.domain_valid}")
        if result.error:
            print(f"Error: {result.error}")
        if result.all_candidates:
            print(f"All Candidates: {', '.join(result.all_candidates[:5])}")
        print(f"{'='*50}")


if __name__ == '__main__':
    main()
