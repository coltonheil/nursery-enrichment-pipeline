#!/usr/bin/env python3
"""
OMRI PDF Parser V2 - Fixed Column Detection

Properly handles 3-column layout by detecting column boundaries
based on character positions.

Usage:
    python scripts/parse_omri_pdf_v2.py --iteration 2
"""

import re
import json
import subprocess
import argparse
from pathlib import Path
from dataclasses import dataclass, asdict, field
from typing import List, Optional, Dict, Tuple
from datetime import datetime
from collections import defaultdict

# Paths
PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"
PDF_PATH = DATA_DIR / "CropByCompany-NOP-EN.pdf"
OUTPUT_DIR = DATA_DIR / "parsing_iterations"


@dataclass
class Company:
    """Parsed company data from OMRI PDF."""
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
PHONE_PATTERN = re.compile(r'P:\s*([+\d\s\-\(\)]+)')
FAX_PATTERN = re.compile(r'F:\s*([+\d\s\-\(\)]+)')
WEBSITE_PATTERN = re.compile(r'(?:https?://|www\.)[\w\.\-/]+', re.IGNORECASE)

COUNTRIES = {
    'United States', 'USA', 'US', 'Canada', 'Mexico', 'México', 'India', 'China',
    'Sri Lanka', 'Lithuania', 'Germany', 'Spain', 'Italy', 'France', 'Brazil',
    'Australia', 'New Zealand', 'Chile', 'Colombia', 'Peru', 'Argentina',
    'United Kingdom', 'UK', 'Ireland', 'Netherlands', 'Belgium', 'Japan',
    'South Korea', 'Thailand', 'Vietnam', 'Philippines', 'Indonesia'
}


def extract_columns_fixed_width(pdf_path: Path) -> List[str]:
    """
    Extract text from PDF and split into columns using fixed character positions.
    
    Based on analysis: columns are roughly at positions 0-46, 47-93, 94-140
    """
    # Extract with fixed layout
    cmd = ['pdftotext', '-layout', '-fixed', '3', str(pdf_path), '-']
    result = subprocess.run(cmd, capture_output=True, text=True)
    raw_text = result.stdout
    
    # Define column boundaries (character positions)
    # These were estimated from the PDF - may need tuning
    COL1_END = 46
    COL2_END = 93
    
    columns = [[], [], []]
    
    for line in raw_text.split('\n'):
        # Skip short lines (headers, footers, page numbers)
        if len(line.strip()) < 10:
            continue
        
        # Skip header/footer lines
        if 'OMRI Products List' in line or 'Crop Products by Company' in line:
            continue
        if line.strip().isdigit():  # Page numbers
            continue
        
        # Extract each column based on position
        col1 = line[:COL1_END].strip() if len(line) > 0 else ""
        col2 = line[COL1_END:COL2_END].strip() if len(line) > COL1_END else ""
        col3 = line[COL2_END:].strip() if len(line) > COL2_END else ""
        
        if col1:
            columns[0].append(col1)
        if col2:
            columns[1].append(col2)
        if col3:
            columns[2].append(col3)
    
    return ['\n'.join(col) for col in columns]


def is_company_name_line(line: str, next_line: str = "") -> bool:
    """
    Detect if a line is likely a company name.
    
    Company names:
    - Start with a capital letter or number
    - Don't start with field prefixes (P:, F:, Products:, www, http)
    - Don't contain @ (emails)
    - Don't start with common address words (Av., No., Suite, Unit, P.O.)
    - Are relatively short (< 60 chars typically)
    - Next line is often a person name (two capitalized words)
    """
    line = line.strip()
    if not line:
        return False
    
    # Skip obvious non-company lines
    skip_starters = (
        'P:', 'F:', 'Products:', 'Product:', 'www.', 'http', 'Tel:', 
        'Av.', 'Av ', 'No.', 'No ', 'Suite', 'Unit', 'P.O.', 'PO Box',
        'Calle', 'Carrera', 'Km', 'Col.', 'Floor', 'Piso'
    )
    if any(line.startswith(p) for p in skip_starters):
        return False
    
    # Skip lines with @ (emails)
    if '@' in line:
        return False
    
    # Skip lines that are just countries
    if line in COUNTRIES:
        return False
    
    # Skip lines that look like addresses (start with numbers followed by spaces)
    if re.match(r'^\d+\s+\w', line):
        return False
    
    # Skip lines that look like zip codes
    if re.match(r'^[A-Z]\d[A-Z]\s*\d[A-Z]\d', line):  # Canadian postal
        return False
    if re.match(r'^\d{5}(-\d{4})?$', line):  # US zip
        return False
    
    # Skip product code lines
    if re.match(r'^\([a-z]{2,4}-\d{4,6}\)', line, re.IGNORECASE):
        return False
    
    # Company names typically start with capital letter or number
    if not (line[0].isupper() or line[0].isdigit()):
        return False
    
    # Check if next line looks like a person name (helps confirm)
    if next_line:
        # Person names: typically two+ words, each capitalized
        words = next_line.strip().split()
        if len(words) >= 2 and all(w[0].isupper() for w in words[:2] if w):
            return True
    
    # If line is title case and reasonable length, likely a company
    words = line.split()
    if len(words) >= 2 and len(line) < 60:
        # Check if mostly capitalized words
        cap_words = sum(1 for w in words if w[0].isupper())
        if cap_words >= len(words) * 0.5:
            return True
    
    return False


def split_into_company_blocks(column_text: str) -> List[str]:
    """
    Split a column's text into individual company blocks.
    """
    lines = column_text.split('\n')
    blocks = []
    current_block = []
    
    for i, line in enumerate(lines):
        next_line = lines[i + 1] if i + 1 < len(lines) else ""
        
        if is_company_name_line(line, next_line) and current_block:
            # Start of new company - save current block
            block_text = '\n'.join(current_block)
            if len(block_text.strip()) > 20:  # Skip tiny fragments
                blocks.append(block_text)
            current_block = [line]
        else:
            current_block.append(line)
    
    # Don't forget the last block
    if current_block:
        block_text = '\n'.join(current_block)
        if len(block_text.strip()) > 20:
            blocks.append(block_text)
    
    return blocks


def parse_company_block(text: str) -> Optional[Company]:
    """
    Parse a company block into structured data.
    """
    lines = [l.strip() for l in text.split('\n') if l.strip()]
    
    if not lines:
        return None
    
    company = Company(name=lines[0], raw_text=text)
    
    # Build up the company info from remaining lines
    all_text = ' '.join(lines[1:])
    
    # Extract email
    email_match = EMAIL_PATTERN.search(all_text)
    if email_match:
        company.email = email_match.group(0)
    
    # Extract website
    web_match = WEBSITE_PATTERN.search(all_text)
    if web_match:
        company.website = web_match.group(0)
    
    # Extract phone
    phone_match = PHONE_PATTERN.search(all_text)
    if phone_match:
        company.phone = phone_match.group(1).strip()
    
    # Extract fax
    fax_match = FAX_PATTERN.search(all_text)
    if fax_match:
        company.fax = fax_match.group(1).strip()
    
    # Extract product codes
    codes = PRODUCT_CODE_PATTERN.findall(all_text)
    company.product_codes = [f"{c[0].lower()}-{c[1]}" for c in codes]
    
    # Extract products text (after "Products:" until end or next field)
    products_match = re.search(r'Products?:\s*(.+?)(?:$|\n(?=[A-Z]))', all_text, re.IGNORECASE | re.DOTALL)
    if products_match:
        products_text = products_match.group(1)
        # Split by product codes to get product names
        parts = PRODUCT_CODE_PATTERN.split(products_text)
        company.products = [p.strip(' ,()') for p in parts[::3] if p.strip(' ,()')]
    
    # Find contact person (usually line 2, name-like)
    if len(lines) > 1:
        potential_person = lines[1]
        words = potential_person.split()
        if (2 <= len(words) <= 4 and 
            all(w[0].isupper() for w in words if w) and
            not any(c.isdigit() for c in potential_person)):
            company.contact_person = potential_person
    
    # Find country
    for line in lines:
        if line in COUNTRIES:
            company.country = line
            break
    
    # Find city/state/zip from address lines
    for line in lines[2:]:
        # US pattern: City, ST 12345
        match = re.match(r'^([^,]+),\s*([A-Z]{2})\s+(\d{5}(?:-\d{4})?)', line)
        if match:
            company.city = match.group(1)
            company.state = match.group(2)
            company.zip_code = match.group(3)
            break
    
    # Calculate confidence
    company.parse_confidence = calculate_confidence(company)
    
    return company


def calculate_confidence(company: Company) -> float:
    """Calculate parse confidence score."""
    score = 0.0
    issues = []
    
    if company.name and len(company.name) > 3:
        score += 0.15
    else:
        issues.append("Invalid/missing name")
    
    if company.email:
        score += 0.25
    else:
        issues.append("Missing email")
    
    if company.phone:
        score += 0.1
    
    if company.website:
        score += 0.15
    
    if company.product_codes:
        score += 0.25
        if len(company.product_codes) > 1:
            score += 0.05
    else:
        issues.append("No product codes")
    
    if company.country:
        score += 0.05
    
    company.parse_issues = issues
    return min(score, 1.0)


def parse_pdf_v2(iteration: int = 2) -> Dict:
    """
    Run V2 parsing with fixed column detection.
    """
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    print(f"=== OMRI PDF Parser V2 - Iteration {iteration} ===")
    print(f"PDF: {PDF_PATH}")
    print()
    
    # Step 1: Extract columns
    print("Step 1: Extracting columns with fixed-width detection...")
    columns = extract_columns_fixed_width(PDF_PATH)
    print(f"  Column line counts: {[len(c.split(chr(10))) for c in columns]}")
    
    # Step 2: Split each column into company blocks
    print("Step 2: Splitting into company blocks...")
    all_blocks = []
    for i, col_text in enumerate(columns):
        blocks = split_into_company_blocks(col_text)
        print(f"  Column {i+1}: {len(blocks)} blocks")
        all_blocks.extend(blocks)
    
    print(f"  Total blocks: {len(all_blocks)}")
    
    # Step 3: Parse each block
    print("Step 3: Parsing company blocks...")
    companies = []
    for block in all_blocks:
        company = parse_company_block(block)
        if company and company.name and len(company.name) > 2:
            companies.append(company)
    
    print(f"  Parsed {len(companies)} companies")
    
    # Step 4: Deduplicate by name
    print("Step 4: Deduplicating...")
    seen_names = set()
    unique_companies = []
    for c in companies:
        name_key = c.name.lower().strip()
        if name_key not in seen_names:
            seen_names.add(name_key)
            unique_companies.append(c)
    
    print(f"  Unique companies: {len(unique_companies)}")
    
    # Step 5: Validate
    print("\nStep 5: Validation...")
    metrics = validate_results_v2(unique_companies)
    
    # Step 6: Save
    output_file = OUTPUT_DIR / f"iteration_{iteration}.json"
    results = {
        'iteration': iteration,
        'version': 'v2',
        'timestamp': datetime.now().isoformat(),
        'metrics': metrics,
        'companies': [asdict(c) for c in unique_companies]
    }
    
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\nResults saved to: {output_file}")
    
    # Show some sample companies
    print("\n=== Sample Companies (High Confidence) ===")
    high_conf = sorted(unique_companies, key=lambda c: c.parse_confidence, reverse=True)
    for c in high_conf[:5]:
        print(f"\n{c.name}")
        print(f"  Email: {c.email}")
        print(f"  Website: {c.website}")
        print(f"  Products: {len(c.product_codes)} codes")
        print(f"  Confidence: {c.parse_confidence:.0%}")
    
    return results


def validate_results_v2(companies: List[Company]) -> Dict:
    """Validate parsed results."""
    metrics = {
        'total_companies': len(companies),
        'with_email': sum(1 for c in companies if c.email),
        'with_phone': sum(1 for c in companies if c.phone),
        'with_website': sum(1 for c in companies if c.website),
        'with_products': sum(1 for c in companies if c.product_codes),
        'total_products': sum(len(c.product_codes) for c in companies),
        'high_confidence': sum(1 for c in companies if c.parse_confidence >= 0.7),
        'medium_confidence': sum(1 for c in companies if 0.4 <= c.parse_confidence < 0.7),
        'low_confidence': sum(1 for c in companies if c.parse_confidence < 0.4),
        'avg_confidence': sum(c.parse_confidence for c in companies) / max(1, len(companies)),
        'known_companies_found': [],
    }
    
    # Check for known companies
    known = ['FoxFarm', 'Dr. Earth', 'Coast of Maine', 'Espoma', 'Down To Earth', 
             'Botanicare', 'General Hydroponics', 'Scotts', 'Miracle-Gro']
    for company in companies:
        for k in known:
            if k.lower() in company.name.lower():
                metrics['known_companies_found'].append(company.name)
    
    n = metrics['total_companies']
    print(f"""
╔══════════════════════════════════════════════════════════════╗
║                    VALIDATION REPORT V2                      ║
╠══════════════════════════════════════════════════════════════╣
║  Total Companies:     {n:>6}                              ║
║  With Email:          {metrics['with_email']:>6} ({metrics['with_email']/max(1,n)*100:>5.1f}%)                     ║
║  With Phone:          {metrics['with_phone']:>6} ({metrics['with_phone']/max(1,n)*100:>5.1f}%)                     ║
║  With Website:        {metrics['with_website']:>6} ({metrics['with_website']/max(1,n)*100:>5.1f}%)                     ║
║  With Products:       {metrics['with_products']:>6} ({metrics['with_products']/max(1,n)*100:>5.1f}%)                     ║
║  Total Product Codes: {metrics['total_products']:>6}                              ║
╠══════════════════════════════════════════════════════════════╣
║  CONFIDENCE DISTRIBUTION                                     ║
║  High (≥70%):         {metrics['high_confidence']:>6}                              ║
║  Medium (40-70%):     {metrics['medium_confidence']:>6}                              ║
║  Low (<40%):          {metrics['low_confidence']:>6}                              ║
║  Average:             {metrics['avg_confidence']*100:>6.1f}%                             ║
╠══════════════════════════════════════════════════════════════╣
║  Known Companies:     {len(metrics['known_companies_found']):>6}                              ║
╚══════════════════════════════════════════════════════════════╝
""")
    
    if metrics['known_companies_found']:
        print("Found:", ', '.join(metrics['known_companies_found'][:8]))
    
    return metrics


def main():
    parser = argparse.ArgumentParser(description='Parse OMRI PDF V2')
    parser.add_argument('--iteration', '-i', type=int, default=2)
    args = parser.parse_args()
    
    parse_pdf_v2(args.iteration)


if __name__ == '__main__':
    main()
