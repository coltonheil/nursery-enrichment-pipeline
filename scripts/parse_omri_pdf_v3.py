#!/usr/bin/env python3
"""
OMRI PDF Parser V3 - Anchor-Based Parsing

Uses "Products:" line as anchor point and works backwards to find company info.
This is more reliable than trying to detect company names forward.

Usage:
    python scripts/parse_omri_pdf_v3.py --iteration 3
"""

import re
import json
import subprocess
from pathlib import Path
from dataclasses import dataclass, asdict, field
from typing import List, Optional, Dict
from datetime import datetime

PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"
PDF_PATH = DATA_DIR / "CropByCompany-NOP-EN.pdf"
OUTPUT_DIR = DATA_DIR / "parsing_iterations"


@dataclass
class Company:
    name: str
    contact_person: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip_code: Optional[str] = None
    country: Optional[str] = None
    phone: Optional[str] = None
    fax: Optional[str] = None
    email: Optional[str] = None
    website: Optional[str] = None
    products: List[str] = field(default_factory=list)
    product_codes: List[str] = field(default_factory=list)
    raw_text: Optional[str] = None
    parse_confidence: float = 0.0
    parse_issues: List[str] = field(default_factory=list)


# Patterns
PRODUCT_CODE_PATTERN = re.compile(r'\(([a-z]{2,4})-(\d{4,6})\)', re.IGNORECASE)
EMAIL_PATTERN = re.compile(r'[\w\.\-]+@[\w\.\-]+\.[a-z]{2,}', re.IGNORECASE)
PHONE_PATTERN = re.compile(r'P:\s*([+\d\s\-\(\),]+)')
FAX_PATTERN = re.compile(r'F:\s*([+\d\s\-\(\)]+)')
WEBSITE_PATTERN = re.compile(r'(?:https?://|www\.)[\w\.\-/]+', re.IGNORECASE)
PRODUCTS_LINE_PATTERN = re.compile(r'^Products?:\s*', re.IGNORECASE | re.MULTILINE)

COUNTRIES = {
    'United States', 'USA', 'US', 'Canada', 'Mexico', 'México', 'India', 'China',
    'Sri Lanka', 'Lithuania', 'Germany', 'Spain', 'Italy', 'France', 'Brazil',
    'Australia', 'New Zealand', 'Chile', 'Colombia', 'Peru', 'Argentina',
    'United Kingdom', 'UK', 'Ireland', 'Netherlands', 'Belgium', 'Japan',
    'South Korea', 'Thailand', 'Vietnam', 'Philippines', 'Indonesia'
}


def extract_raw_text(pdf_path: Path) -> str:
    """Extract text in raw mode (reading order)."""
    cmd = ['pdftotext', '-raw', str(pdf_path), '-']
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.stdout


def is_person_name(line: str) -> bool:
    """Check if line looks like a person name (First Last or First Middle Last)."""
    line = line.strip()
    if not line:
        return False
    
    # Person names: 2-4 words, all capitalized, no numbers, no special chars
    words = line.split()
    if not (2 <= len(words) <= 5):
        return False
    
    # Should be all capitalized words
    if not all(w[0].isupper() for w in words if w):
        return False
    
    # Should not contain numbers
    if any(c.isdigit() for c in line):
        return False
    
    # Should not contain company suffixes
    company_terms = ['inc', 'llc', 'ltd', 'corp', 'co.', 'company', 'gmbh', 'pvt', 's.a.']
    if any(term in line.lower() for term in company_terms):
        return False
    
    # Should not contain address words
    address_terms = ['street', 'st.', 'road', 'rd.', 'avenue', 'ave', 'blvd', 'drive', 'dr.']
    if any(term in line.lower() for term in address_terms):
        return False
    
    return True


def is_company_name(line: str, next_line: str = "") -> bool:
    """
    Check if a line is likely a company name.
    
    Key insight: company name is followed by a contact person name.
    """
    line = line.strip()
    if not line or len(line) < 2:
        return False
    
    # Skip obvious non-company patterns
    if any(line.lower().startswith(x) for x in ['p:', 'f:', 'products:', 'www.', 'http', 'tel:']):
        return False
    if '@' in line or 'www.' in line.lower():
        return False
    
    # Skip lines that look like addresses (start with number)
    if re.match(r'^\d+\s', line):
        return False
    if re.match(r'^P\.?O\.?\s*Box', line, re.IGNORECASE):
        return False
    
    # Skip lines that are city/state/zip
    if re.match(r'^[\w\s]+,\s*[A-Z]{2}\s+\d{5}', line):
        return False
    
    # Skip country names
    if line in COUNTRIES:
        return False
    
    # If next line looks like a person name, this is likely the company name
    if next_line and is_person_name(next_line):
        return True
    
    # Company name indicators (explicit suffixes)
    company_suffixes = ['Inc.', 'Inc', 'LLC', 'Ltd.', 'Ltd', 'Corp.', 'Corp', 'Co.', 
                        'S.A.', 'S.A', 'S.L.', 'GmbH', 'Pty', 'Pvt', 'Limited',
                        'Company', 'Corporation', 'Enterprises', 'Industries',
                        'Organics', 'Farms', 'Farm', 'Products']
    
    for suffix in company_suffixes:
        if line.endswith(suffix) or f' {suffix}' in line or f' {suffix},' in line:
            return True
    
    return False


def find_company_blocks_by_products(text: str) -> List[Dict]:
    """
    Find company blocks by using Products: as an anchor.
    
    For each Products: line, look backwards to find the company name,
    and collect contact info in between.
    """
    lines = text.split('\n')
    companies = []
    
    i = 0
    while i < len(lines):
        line = lines[i]
        
        # Look for Products: line as anchor
        if re.match(r'^Products?:\s*\S', line, re.IGNORECASE):
            # Found a Products: line - now look backwards for company name
            products_line_idx = i
            
            # Collect the products (may span many lines - some companies have 50+)
            products_text = line
            j = i + 1
            consecutive_non_product_lines = 0
            while j < len(lines) and j < i + 150:  # Allow up to 150 lines for products
                next_line = lines[j].strip()
                if not next_line:  # Empty line
                    consecutive_non_product_lines += 1
                    j += 1
                    if consecutive_non_product_lines > 2:  # Multiple empty lines = end
                        break
                    continue
                    
                # Products END when we hit another Products: line
                if re.match(r'^Products?:', next_line, re.IGNORECASE):
                    break
                
                # Check if this line contains a product code - if so, definitely continue
                if PRODUCT_CODE_PATTERN.search(next_line):
                    products_text += ' ' + next_line
                    consecutive_non_product_lines = 0
                    j += 1
                    continue
                
                # Check for signs that a new company block is starting
                # Must be: a line that's a company name AND followed by a person name
                # AND NOT containing product-related text
                next_next = lines[j + 1].strip() if j + 1 < len(lines) else ""
                is_new_company = (
                    is_company_name(next_line, next_next) and
                    is_person_name(next_next) and
                    not any(x in next_line.lower() for x in ['fertilizer', 'compost', 'soil', 'plant food', 'nutrient'])
                )
                
                if is_new_company:
                    break
                
                # Otherwise, this line is likely part of products (continuation)
                products_text += ' ' + next_line
                consecutive_non_product_lines = 0
                j += 1
            
            # Look backwards for company name (within 15 lines)
            company_name = None
            company_name_idx = None
            for k in range(products_line_idx - 1, max(-1, products_line_idx - 15), -1):
                if k < 0:
                    break
                prev_line = lines[k].strip()
                next_line = lines[k + 1].strip() if k + 1 < len(lines) else ""
                if is_company_name(prev_line, next_line):
                    company_name = prev_line
                    company_name_idx = k
                    break
            
            if company_name:
                # Extract the block from company name to products
                block_lines = lines[company_name_idx:products_line_idx]
                block_text = '\n'.join(block_lines) + '\n' + products_text
                
                # Parse the block
                company = parse_block_v3(company_name, block_text, products_text)
                if company:
                    companies.append(company)
            
            i = j  # Skip past the products we processed
        else:
            i += 1
    
    return companies


def parse_block_v3(company_name: str, block_text: str, products_text: str) -> Optional[Company]:
    """Parse a company block into structured data."""
    company = Company(name=company_name, raw_text=block_text)
    
    # Extract product codes
    codes = PRODUCT_CODE_PATTERN.findall(products_text)
    company.product_codes = [f"{c[0].lower()}-{c[1]}" for c in codes]
    
    # Extract contact info from block
    email_match = EMAIL_PATTERN.search(block_text)
    if email_match:
        company.email = email_match.group(0)
    
    web_match = WEBSITE_PATTERN.search(block_text)
    if web_match:
        company.website = web_match.group(0)
    
    phone_match = PHONE_PATTERN.search(block_text)
    if phone_match:
        # Clean up phone - take first valid number
        phone_str = phone_match.group(1).strip()
        # Split by comma and take first
        phones = [p.strip() for p in phone_str.split(',')]
        company.phone = phones[0] if phones else None
    
    fax_match = FAX_PATTERN.search(block_text)
    if fax_match:
        company.fax = fax_match.group(1).strip()
    
    # Find country
    for country in COUNTRIES:
        if country in block_text:
            company.country = country
            break
    
    # Find city/state/zip (US format)
    city_match = re.search(r'^([A-Za-z\s]+),\s*([A-Z]{2})\s+(\d{5}(?:-\d{4})?)', block_text, re.MULTILINE)
    if city_match:
        company.city = city_match.group(1).strip()
        company.state = city_match.group(2)
        company.zip_code = city_match.group(3)
    
    # Calculate confidence
    score = 0.0
    issues = []
    
    if company.name and len(company.name) > 5:
        score += 0.2
    else:
        issues.append("Short/missing name")
    
    if company.email:
        score += 0.25
    else:
        issues.append("Missing email")
    
    if company.website:
        score += 0.15
    
    if company.phone:
        score += 0.1
    
    if company.product_codes:
        score += 0.25
        if len(company.product_codes) >= 2:
            score += 0.05
    else:
        issues.append("No products")
    
    company.parse_confidence = min(score, 1.0)
    company.parse_issues = issues
    
    return company


def parse_pdf_v3(iteration: int = 3) -> Dict:
    """Run V3 anchor-based parsing."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    print(f"=== OMRI PDF Parser V3 - Anchor-Based ===")
    print(f"PDF: {PDF_PATH}")
    print()
    
    # Step 1: Extract raw text
    print("Step 1: Extracting raw text...")
    raw_text = extract_raw_text(PDF_PATH)
    print(f"  Extracted {len(raw_text):,} characters")
    
    # Count Products: lines
    products_count = len(re.findall(r'^Products?:', raw_text, re.MULTILINE | re.IGNORECASE))
    print(f"  Found {products_count:,} Products: lines")
    
    # Step 2: Find company blocks
    print("\nStep 2: Finding company blocks by Products: anchor...")
    companies = find_company_blocks_by_products(raw_text)
    print(f"  Found {len(companies)} company blocks")
    
    # Step 3: Deduplicate
    print("\nStep 3: Deduplicating...")
    seen = set()
    unique = []
    for c in companies:
        key = c.name.lower().strip()
        if key not in seen and len(key) > 3:
            seen.add(key)
            unique.append(c)
    print(f"  Unique companies: {len(unique)}")
    
    # Step 4: Validate
    print("\nStep 4: Validation...")
    metrics = {
        'total': len(unique),
        'with_email': sum(1 for c in unique if c.email),
        'with_website': sum(1 for c in unique if c.website),
        'with_phone': sum(1 for c in unique if c.phone),
        'with_products': sum(1 for c in unique if c.product_codes),
        'total_products': sum(len(c.product_codes) for c in unique),
        'high_conf': sum(1 for c in unique if c.parse_confidence >= 0.7),
        'med_conf': sum(1 for c in unique if 0.4 <= c.parse_confidence < 0.7),
        'low_conf': sum(1 for c in unique if c.parse_confidence < 0.4),
        'avg_conf': sum(c.parse_confidence for c in unique) / max(1, len(unique)),
    }
    
    n = metrics['total']
    print(f"""
╔══════════════════════════════════════════════════════════════╗
║                    VALIDATION REPORT V3                      ║
╠══════════════════════════════════════════════════════════════╣
║  Total Companies:     {n:>6}                              ║
║  With Email:          {metrics['with_email']:>6} ({metrics['with_email']/max(1,n)*100:>5.1f}%)                     ║
║  With Website:        {metrics['with_website']:>6} ({metrics['with_website']/max(1,n)*100:>5.1f}%)                     ║
║  With Phone:          {metrics['with_phone']:>6} ({metrics['with_phone']/max(1,n)*100:>5.1f}%)                     ║
║  With Products:       {metrics['with_products']:>6} ({metrics['with_products']/max(1,n)*100:>5.1f}%)                     ║
║  Total Product Codes: {metrics['total_products']:>6}                              ║
╠══════════════════════════════════════════════════════════════╣
║  High Confidence:     {metrics['high_conf']:>6}                              ║
║  Medium Confidence:   {metrics['med_conf']:>6}                              ║
║  Low Confidence:      {metrics['low_conf']:>6}                              ║
║  Average:             {metrics['avg_conf']*100:>6.1f}%                             ║
╚══════════════════════════════════════════════════════════════╝
""")
    
    # Show known companies
    known = ['FoxFarm', 'Dr. Earth', 'Coast of Maine', 'Espoma', 'Down To Earth', 
             'Botanicare', 'General Hydroponics', 'Organic Mechanics']
    found_known = []
    for c in unique:
        for k in known:
            if k.lower() in c.name.lower():
                found_known.append(c.name)
    print(f"Known companies found: {len(found_known)}")
    if found_known:
        print(f"  {', '.join(found_known[:5])}")
    
    # Show sample good parses
    print("\n=== Sample Companies ===")
    good = sorted(unique, key=lambda c: c.parse_confidence, reverse=True)
    for c in good[:5]:
        print(f"\n{c.name}")
        print(f"  Email: {c.email}")
        print(f"  Website: {c.website}")
        print(f"  Phone: {c.phone}")
        print(f"  Products: {len(c.product_codes)} codes - {c.product_codes[:3]}")
        print(f"  Confidence: {c.parse_confidence:.0%}")
    
    # Save results
    output_file = OUTPUT_DIR / f"iteration_{iteration}.json"
    results = {
        'iteration': iteration,
        'version': 'v3_anchor',
        'timestamp': datetime.now().isoformat(),
        'metrics': metrics,
        'companies': [asdict(c) for c in unique]
    }
    
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\nResults saved to: {output_file}")
    
    return results


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--iteration', '-i', type=int, default=3)
    args = parser.parse_args()
    parse_pdf_v3(args.iteration)
