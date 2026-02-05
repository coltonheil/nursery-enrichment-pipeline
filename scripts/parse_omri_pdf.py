#!/usr/bin/env python3
"""
OMRI PDF Parser - Iterative Extraction

Parses CropByCompany-NOP-EN.pdf to extract company data with contact info.

Usage:
    python scripts/parse_omri_pdf.py --iteration 1
    python scripts/parse_omri_pdf.py --validate
    python scripts/parse_omri_pdf.py --export
"""

import re
import json
import subprocess
import argparse
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import List, Optional, Dict
from datetime import datetime

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
    products: List[str] = None
    product_codes: List[str] = None
    raw_text: Optional[str] = None
    parse_confidence: float = 0.0
    parse_issues: List[str] = None
    
    def __post_init__(self):
        if self.products is None:
            self.products = []
        if self.product_codes is None:
            self.product_codes = []
        if self.parse_issues is None:
            self.parse_issues = []


# ============================================================================
# VALIDATION PATTERNS
# ============================================================================

# Product code pattern: 3 letters, dash, 5 digits (e.g., acd-12345)
PRODUCT_CODE_PATTERN = re.compile(r'\b([a-z]{2,4})-(\d{4,6})\b', re.IGNORECASE)

# Email pattern
EMAIL_PATTERN = re.compile(r'[\w\.-]+@[\w\.-]+\.\w+')

# Phone pattern (various formats)
PHONE_PATTERN = re.compile(r'P:\s*([+\d\s\-\(\)]+)')

# Fax pattern
FAX_PATTERN = re.compile(r'F:\s*([+\d\s\-\(\)]+)')

# Website pattern
WEBSITE_PATTERN = re.compile(r'https?://[\w\.-]+\.\w+/?[\w\./\-]*|www\.[\w\.-]+\.\w+/?[\w\./\-]*')

# Products line pattern
PRODUCTS_LINE_PATTERN = re.compile(r'^Products?:\s*(.+)', re.IGNORECASE | re.MULTILINE)

# Country indicators
COUNTRIES = {
    'United States', 'USA', 'US', 'Canada', 'Mexico', 'India', 'China', 
    'Sri Lanka', 'Lithuania', 'Germany', 'Spain', 'Italy', 'France',
    'Australia', 'New Zealand', 'Brazil', 'Chile', 'Colombia', 'Peru'
}


# ============================================================================
# EXTRACTION METHODS
# ============================================================================

def extract_text_pdftotext(pdf_path: Path, layout: bool = True) -> str:
    """Extract text using pdftotext with layout preservation."""
    cmd = ['pdftotext']
    if layout:
        cmd.append('-layout')
    cmd.extend([str(pdf_path), '-'])
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"pdftotext failed: {result.stderr}")
    return result.stdout


def extract_text_raw(pdf_path: Path) -> str:
    """Extract text using pdftotext without layout (raw mode)."""
    cmd = ['pdftotext', '-raw', str(pdf_path), '-']
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.stdout


def split_into_columns(text: str, num_columns: int = 3) -> List[str]:
    """
    Split layout-preserved text into columns based on character positions.
    
    The PDF has 3 columns. We detect column boundaries by finding
    large horizontal gaps in the text.
    """
    lines = text.split('\n')
    
    # Find typical column positions by analyzing spacing
    # For a 3-column PDF, columns typically start around positions 0, 35, 70
    # but this varies - we'll detect dynamically
    
    columns = [[], [], []]
    
    for line in lines:
        if not line.strip():
            continue
            
        # Simple heuristic: split by large spaces (5+ spaces)
        parts = re.split(r'\s{5,}', line)
        
        for i, part in enumerate(parts[:3]):  # Max 3 columns
            if part.strip():
                columns[min(i, 2)].append(part.strip())
    
    return ['\n'.join(col) for col in columns]


# ============================================================================
# COMPANY BLOCK PARSING
# ============================================================================

def is_company_header(line: str, prev_line: str = "") -> bool:
    """
    Detect if a line is likely a company name header.
    
    Heuristics:
    - Not starting with common field prefixes (P:, F:, Products:, www, http)
    - Not an email
    - Not a continuation of previous line
    - Contains at least one capital letter
    - Relatively short (company names usually < 60 chars)
    """
    line = line.strip()
    if not line:
        return False
    
    # Skip obvious non-headers
    skip_prefixes = ('P:', 'F:', 'Products:', 'www.', 'http', 'Tel:', 'Tel ', 'Fax:')
    if any(line.startswith(p) for p in skip_prefixes):
        return False
    
    # Skip emails
    if '@' in line:
        return False
    
    # Skip product codes standalone
    if PRODUCT_CODE_PATTERN.fullmatch(line):
        return False
    
    # Skip lines that look like addresses (start with numbers)
    if re.match(r'^\d+\s', line):
        return False
    
    # Skip lines that are just countries
    if line in COUNTRIES:
        return False
    
    # Company names typically have capital letters
    if not any(c.isupper() for c in line):
        return False
    
    # Company names are usually reasonably short
    if len(line) > 80:
        return False
    
    return True


def parse_company_block(text: str) -> Company:
    """
    Parse a single company text block into structured data.
    """
    lines = [l.strip() for l in text.strip().split('\n') if l.strip()]
    
    if not lines:
        return None
    
    company = Company(name=lines[0], raw_text=text)
    
    address_lines = []
    in_address = True
    
    for i, line in enumerate(lines[1:], 1):
        # Extract email
        email_match = EMAIL_PATTERN.search(line)
        if email_match:
            company.email = email_match.group(0)
            continue
        
        # Extract website
        web_match = WEBSITE_PATTERN.search(line)
        if web_match:
            company.website = web_match.group(0)
            continue
        
        # Extract phone
        phone_match = PHONE_PATTERN.search(line)
        if phone_match:
            company.phone = phone_match.group(1).strip()
            # Check for fax on same line
            fax_match = FAX_PATTERN.search(line)
            if fax_match:
                company.fax = fax_match.group(1).strip()
            in_address = False
            continue
        
        # Extract products
        products_match = PRODUCTS_LINE_PATTERN.search(line)
        if products_match:
            products_text = products_match.group(1)
            # Continue reading products on subsequent lines
            for j in range(i + 1, len(lines)):
                if is_company_header(lines[j]):
                    break
                products_text += ' ' + lines[j]
            
            # Extract product codes
            codes = PRODUCT_CODE_PATTERN.findall(products_text)
            company.product_codes = [f"{c[0]}-{c[1]}" for c in codes]
            
            # Extract product names (text before each code)
            company.products = re.split(r'\([a-z]{2,4}-\d{4,6}\)', products_text, flags=re.IGNORECASE)
            company.products = [p.strip(' ,') for p in company.products if p.strip(' ,')]
            in_address = False
            continue
        
        # Check for country (ends address section)
        if line in COUNTRIES or line.upper() in [c.upper() for c in COUNTRIES]:
            company.country = line
            in_address = False
            continue
        
        # Accumulate address lines
        if in_address and i < 6:  # Address usually within first 6 lines
            # Check if it's the contact person (usually line 2, no numbers)
            if i == 1 and not any(c.isdigit() for c in line):
                company.contact_person = line
            else:
                address_lines.append(line)
    
    # Parse accumulated address
    if address_lines:
        company.address = ', '.join(address_lines)
        
        # Try to extract city, state, zip from last address line
        last_addr = address_lines[-1] if address_lines else ""
        # Pattern: City, State ZIP or City, Province ZIP
        addr_match = re.match(r'(.+?),?\s+([A-Z]{2})\s+(\d{5}(?:-\d{4})?)', last_addr)
        if addr_match:
            company.city = addr_match.group(1)
            company.state = addr_match.group(2)
            company.zip_code = addr_match.group(3)
    
    # Calculate parse confidence
    company.parse_confidence = calculate_confidence(company)
    
    return company


def calculate_confidence(company: Company) -> float:
    """
    Calculate confidence score (0-1) for parsed company data.
    """
    score = 0.0
    issues = []
    
    # Name is required
    if company.name:
        score += 0.2
    else:
        issues.append("Missing company name")
    
    # Contact info (at least one of: email, phone, website)
    if company.email:
        score += 0.2
    else:
        issues.append("Missing email")
    
    if company.phone:
        score += 0.1
    
    if company.website:
        score += 0.15
    
    # Address
    if company.address or company.city:
        score += 0.1
    
    if company.country:
        score += 0.05
    
    # Products (indicates this is a real company entry)
    if company.product_codes:
        score += 0.2
    else:
        issues.append("No product codes found")
    
    company.parse_issues = issues
    return min(score, 1.0)


# ============================================================================
# MAIN PARSING PIPELINE
# ============================================================================

def parse_pdf_iteration(iteration: int = 1) -> Dict:
    """
    Run one iteration of PDF parsing and return results with metrics.
    """
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    print(f"=== OMRI PDF Parser - Iteration {iteration} ===")
    print(f"PDF: {PDF_PATH}")
    print()
    
    # Step 1: Extract text
    print("Step 1: Extracting text with layout preservation...")
    raw_text = extract_text_pdftotext(PDF_PATH, layout=True)
    print(f"  Extracted {len(raw_text):,} characters")
    
    # Step 2: Split into columns
    print("Step 2: Splitting into columns...")
    columns = split_into_columns(raw_text)
    print(f"  Column sizes: {[len(c) for c in columns]}")
    
    # Step 3: Merge columns into single stream
    # The columns are read left-to-right, top-to-bottom
    # But company entries may span columns on same page
    merged_text = '\n'.join(columns)
    
    # Step 4: Split into company blocks
    print("Step 3: Identifying company blocks...")
    
    # Strategy: Split on lines that look like company headers
    lines = merged_text.split('\n')
    blocks = []
    current_block = []
    
    for i, line in enumerate(lines):
        prev_line = lines[i-1] if i > 0 else ""
        
        if is_company_header(line, prev_line) and current_block:
            # Save previous block and start new one
            blocks.append('\n'.join(current_block))
            current_block = [line]
        else:
            current_block.append(line)
    
    if current_block:
        blocks.append('\n'.join(current_block))
    
    print(f"  Found {len(blocks)} potential company blocks")
    
    # Step 5: Parse each block
    print("Step 4: Parsing company blocks...")
    companies = []
    for block in blocks:
        company = parse_company_block(block)
        if company and company.name:
            companies.append(company)
    
    print(f"  Parsed {len(companies)} companies")
    
    # Step 6: Validate and report metrics
    print("\nStep 5: Validation...")
    metrics = validate_results(companies)
    
    # Step 7: Save results
    output_file = OUTPUT_DIR / f"iteration_{iteration}.json"
    results = {
        'iteration': iteration,
        'timestamp': datetime.now().isoformat(),
        'metrics': metrics,
        'companies': [asdict(c) for c in companies]
    }
    
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\nResults saved to: {output_file}")
    
    return results


def validate_results(companies: List[Company]) -> Dict:
    """
    Validate parsed results and return metrics.
    """
    metrics = {
        'total_companies': len(companies),
        'with_email': 0,
        'with_phone': 0,
        'with_website': 0,
        'with_products': 0,
        'with_address': 0,
        'high_confidence': 0,  # >= 0.7
        'medium_confidence': 0,  # 0.4-0.7
        'low_confidence': 0,  # < 0.4
        'avg_confidence': 0.0,
        'total_products': 0,
        'known_companies_found': [],
        'sample_issues': []
    }
    
    # Known companies we expect to find (validation check)
    known_companies = [
        'FoxFarm', 'Dr. Earth', 'Coast of Maine', 'Espoma', 
        'Down To Earth', 'Botanicare', 'General Hydroponics'
    ]
    
    confidence_sum = 0
    
    for company in companies:
        if company.email:
            metrics['with_email'] += 1
        if company.phone:
            metrics['with_phone'] += 1
        if company.website:
            metrics['with_website'] += 1
        if company.product_codes:
            metrics['with_products'] += 1
            metrics['total_products'] += len(company.product_codes)
        if company.address or company.city:
            metrics['with_address'] += 1
        
        if company.parse_confidence >= 0.7:
            metrics['high_confidence'] += 1
        elif company.parse_confidence >= 0.4:
            metrics['medium_confidence'] += 1
        else:
            metrics['low_confidence'] += 1
        
        confidence_sum += company.parse_confidence
        
        # Check for known companies
        for known in known_companies:
            if known.lower() in company.name.lower():
                metrics['known_companies_found'].append(company.name)
        
        # Collect sample issues
        if company.parse_issues and len(metrics['sample_issues']) < 10:
            metrics['sample_issues'].append({
                'company': company.name,
                'issues': company.parse_issues
            })
    
    if companies:
        metrics['avg_confidence'] = confidence_sum / len(companies)
    
    # Print validation report
    print(f"""
╔══════════════════════════════════════════════════════════════╗
║                    VALIDATION REPORT                         ║
╠══════════════════════════════════════════════════════════════╣
║  Total Companies:     {metrics['total_companies']:>6}                              ║
║  With Email:          {metrics['with_email']:>6} ({metrics['with_email']/max(1,metrics['total_companies'])*100:>5.1f}%)                     ║
║  With Phone:          {metrics['with_phone']:>6} ({metrics['with_phone']/max(1,metrics['total_companies'])*100:>5.1f}%)                     ║
║  With Website:        {metrics['with_website']:>6} ({metrics['with_website']/max(1,metrics['total_companies'])*100:>5.1f}%)                     ║
║  With Products:       {metrics['with_products']:>6} ({metrics['with_products']/max(1,metrics['total_companies'])*100:>5.1f}%)                     ║
║  Total Product Codes: {metrics['total_products']:>6}                              ║
╠══════════════════════════════════════════════════════════════╣
║  CONFIDENCE DISTRIBUTION                                     ║
║  High (≥70%):         {metrics['high_confidence']:>6}                              ║
║  Medium (40-70%):     {metrics['medium_confidence']:>6}                              ║
║  Low (<40%):          {metrics['low_confidence']:>6}                              ║
║  Average:             {metrics['avg_confidence']*100:>6.1f}%                             ║
╠══════════════════════════════════════════════════════════════╣
║  Known Companies Found: {len(metrics['known_companies_found']):>3}                               ║
╚══════════════════════════════════════════════════════════════╝
""")
    
    if metrics['known_companies_found']:
        print("Known companies found:", ', '.join(metrics['known_companies_found'][:5]))
    
    return metrics


def analyze_failures(iteration: int) -> Dict:
    """
    Analyze failures from a parsing iteration and suggest fixes.
    """
    results_file = OUTPUT_DIR / f"iteration_{iteration}.json"
    
    if not results_file.exists():
        print(f"No results found for iteration {iteration}")
        return {}
    
    with open(results_file) as f:
        results = json.load(f)
    
    companies = results['companies']
    
    print(f"\n=== Failure Analysis for Iteration {iteration} ===\n")
    
    # Categorize issues
    issue_categories = {
        'missing_email': [],
        'missing_products': [],
        'low_confidence': [],
        'truncated_name': [],
        'merged_entries': []
    }
    
    for c in companies:
        if not c.get('email'):
            issue_categories['missing_email'].append(c['name'])
        if not c.get('product_codes'):
            issue_categories['missing_products'].append(c['name'])
        if c.get('parse_confidence', 0) < 0.4:
            issue_categories['low_confidence'].append(c['name'])
        if len(c.get('name', '')) > 60:
            issue_categories['merged_entries'].append(c['name'][:60] + '...')
    
    print("Issue Summary:")
    for category, items in issue_categories.items():
        print(f"  {category}: {len(items)} companies")
        if items[:3]:
            print(f"    Examples: {items[:3]}")
    
    # Suggest fixes based on patterns
    suggestions = []
    
    if len(issue_categories['missing_email']) > len(companies) * 0.5:
        suggestions.append("- Email extraction regex may need adjustment")
        suggestions.append("- Check if emails are on separate lines or inline")
    
    if len(issue_categories['missing_products']) > len(companies) * 0.3:
        suggestions.append("- Products line detection may be failing")
        suggestions.append("- Check if 'Products:' prefix varies (Product:, products:)")
    
    if len(issue_categories['merged_entries']) > 10:
        suggestions.append("- Company block splitting is merging entries")
        suggestions.append("- Improve is_company_header() detection")
    
    if suggestions:
        print("\nSuggested Fixes:")
        for s in suggestions:
            print(f"  {s}")
    
    return issue_categories


def main():
    parser = argparse.ArgumentParser(description='Parse OMRI PDF iteratively')
    parser.add_argument('--iteration', '-i', type=int, default=1,
                        help='Iteration number')
    parser.add_argument('--analyze', '-a', type=int,
                        help='Analyze failures from iteration N')
    parser.add_argument('--export', '-e', action='store_true',
                        help='Export final results to CSV')
    args = parser.parse_args()
    
    if args.analyze:
        analyze_failures(args.analyze)
    else:
        parse_pdf_iteration(args.iteration)


if __name__ == '__main__':
    main()
