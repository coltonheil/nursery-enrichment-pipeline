#!/usr/bin/env python3
"""
OMRI Soil Company Scraper

Scrapes company data from OMRI's public search for potting soil products.
Collects company names, codes, and URLs for later enrichment.

Usage:
    python scripts/omri_scraper.py --pages 20
"""

import json
import time
import argparse
from pathlib import Path
import subprocess

# Known large/commodity companies to filter as Tier 2
TIER_2_COMPANIES = {
    "scotts", "miracle-gro", "oldcastle", "walmart", "home depot",
    "lowes", "national garden", "bonide", "bayer", "ortho",
    "pennington", "vigoro", "expert gardener", "schultz"
}

# Craft soil brand indicators (Tier 1)
TIER_1_KEYWORDS = [
    "organic", "living", "super soil", "biodynamic", "craft",
    "worm", "vermi", "compost", "local", "artisan", "small batch"
]


def scrape_page(page_num: int) -> list:
    """
    Scrape a single page of OMRI search results using browser automation.
    
    Returns list of company dicts: {name, code, url}
    """
    # Navigate to page
    url = f"https://www.omri.org/omri-search?page={page_num}&query=potting%20soil&exactMatchFilter=false"
    
    # Use openclaw browser control
    js_code = """
    () => {
        const companies = [];
        document.querySelectorAll('a[href*="/mfg/"]').forEach(link => {
            if (!link.href.includes('certificate')) {
                const name = link.textContent.trim();
                const code = link.pathname.split('/mfg/')[1];
                if (name && code && code.length <= 5) {
                    companies.push({name: name, code: code, url: link.href});
                }
            }
        });
        return [...new Map(companies.map(c => [c.code, c])).values()];
    }
    """
    
    # This would be called via browser tool - for now return placeholder
    return []


def classify_tier(company_name: str) -> str:
    """
    Classify company as Tier 1 (craft) or Tier 2 (commodity).
    """
    name_lower = company_name.lower()
    
    # Check for Tier 2 (big box/commodity)
    for keyword in TIER_2_COMPANIES:
        if keyword in name_lower:
            return "tier_2"
    
    # Check for Tier 1 indicators
    for keyword in TIER_1_KEYWORDS:
        if keyword in name_lower:
            return "tier_1"
    
    # Default to Tier 1 (most OMRI listings are smaller companies)
    return "tier_1"


def load_existing_companies(filepath: Path) -> dict:
    """Load existing scraped companies if file exists."""
    if filepath.exists():
        with open(filepath) as f:
            data = json.load(f)
            return {c['code']: c for c in data.get('companies', [])}
    return {}


def save_companies(companies: dict, filepath: Path, metadata: dict = None):
    """Save companies to JSON file."""
    output = {
        'metadata': metadata or {},
        'companies': list(companies.values()),
        'total_count': len(companies)
    }
    
    filepath.parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, 'w') as f:
        json.dump(output, f, indent=2)
    
    print(f"Saved {len(companies)} companies to {filepath}")


def main():
    parser = argparse.ArgumentParser(description='Scrape OMRI potting soil companies')
    parser.add_argument('--pages', type=int, default=10, help='Number of pages to scrape')
    parser.add_argument('--output', type=str, default='data/omri_soil_companies.json', help='Output file')
    parser.add_argument('--delay', type=float, default=2.0, help='Delay between page requests')
    args = parser.parse_args()
    
    output_path = Path(__file__).parent.parent / args.output
    
    # Load existing data
    companies = load_existing_companies(output_path)
    print(f"Loaded {len(companies)} existing companies")
    
    # For now, just print instructions since we need browser automation
    print(f"""
OMRI Scraper - Manual Mode

The scraper collected data from OMRI search. To continue:

1. Use the browser tool to navigate through pages
2. Run the JavaScript extraction on each page
3. Aggregate results into: {output_path}

Target: {args.pages} pages
Delay: {args.delay}s between requests
""")


if __name__ == '__main__':
    main()
