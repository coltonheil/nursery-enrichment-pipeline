#!/usr/bin/env python3
"""
OMRI PDF Company Extractor

Extracts company information from OMRI CropByCompany PDF using column-aware parsing.
The PDF has a 3-column layout, so we need to:
1. Extract text blocks with their positions
2. Group by column based on x-coordinate
3. Reconstruct company entries by following vertical flow
"""

import fitz  # PyMuPDF
import re
import json
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import List, Optional

@dataclass
class Company:
    name: str
    contact_name: Optional[str] = None
    address: Optional[str] = None
    city_state_zip: Optional[str] = None
    country: Optional[str] = None
    phone: Optional[str] = None
    fax: Optional[str] = None
    email: Optional[str] = None
    website: Optional[str] = None
    products: List[str] = None
    product_codes: List[str] = None
    raw_text: str = ""
    
    def __post_init__(self):
        if self.products is None:
            self.products = []
        if self.product_codes is None:
            self.product_codes = []

def extract_text_blocks(pdf_path: str, start_page: int = 0, end_page: int = None) -> List[dict]:
    """Extract text blocks with position info from PDF."""
    doc = fitz.open(pdf_path)
    all_blocks = []
    
    if end_page is None:
        end_page = len(doc)
    
    for page_num in range(start_page, min(end_page, len(doc))):
        page = doc[page_num]
        # Get text blocks: (x0, y0, x1, y1, "text", block_no, block_type)
        blocks = page.get_text("blocks")
        
        for block in blocks:
            if len(block) >= 5 and block[6] == 0:  # text block
                all_blocks.append({
                    'page': page_num,
                    'x0': block[0],
                    'y0': block[1],
                    'x1': block[2],
                    'y1': block[3],
                    'text': block[4].strip()
                })
    
    doc.close()
    return all_blocks

def group_blocks_by_column(blocks: List[dict], page_width: float = 612) -> List[List[dict]]:
    """Group text blocks into columns based on x-coordinate."""
    # Define column boundaries (roughly thirds of the page)
    col1_max = page_width * 0.33
    col2_max = page_width * 0.66
    
    columns = [[], [], []]
    
    for block in blocks:
        center_x = (block['x0'] + block['x1']) / 2
        if center_x < col1_max:
            columns[0].append(block)
        elif center_x < col2_max:
            columns[1].append(block)
        else:
            columns[2].append(block)
    
    # Sort each column by page, then y-coordinate (top to bottom)
    for col in columns:
        col.sort(key=lambda b: (b['page'], b['y0']))
    
    return columns

def parse_company_block(text: str) -> Optional[Company]:
    """Parse a company text block into structured data."""
    lines = [l.strip() for l in text.split('\n') if l.strip()]
    if not lines:
        return None
    
    company = Company(name="", raw_text=text)
    
    # First line is usually company name (bold in PDF)
    company.name = lines[0]
    
    # Parse remaining lines
    products_started = False
    address_lines = []
    
    for i, line in enumerate(lines[1:], 1):
        line_lower = line.lower()
        
        # Check for Products: section
        if line.startswith('Products:') or 'Products:' in line:
            products_started = True
            products_text = line.replace('Products:', '').strip()
            if products_text:
                company.products.append(products_text)
            continue
        
        if products_started:
            company.products.append(line)
            continue
        
        # Phone number
        if line.startswith('P:') or line.startswith('P :'):
            phone_match = re.search(r'P:\s*([+\d\-\(\)\s]+)', line)
            if phone_match:
                company.phone = phone_match.group(1).strip()
            fax_match = re.search(r'F:\s*([+\d\-\(\)\s]+)', line)
            if fax_match:
                company.fax = fax_match.group(1).strip()
            continue
        
        # Email
        email_match = re.search(r'[\w\.\-]+@[\w\.\-]+\.\w+', line)
        if email_match and not company.email:
            company.email = email_match.group(0)
            # If line is just email, continue
            if line == company.email:
                continue
        
        # Website
        if 'www.' in line_lower or 'http' in line_lower:
            www_match = re.search(r'(?:https?://)?(?:www\.)?[\w\.\-]+\.\w+(?:/[\w\.\-]*)?', line)
            if www_match:
                company.website = www_match.group(0)
                continue
        
        # Country detection
        countries = ['United States', 'USA', 'US', 'Canada', 'Mexico', 'México', 
                    'India', 'China', 'Australia', 'UK', 'Germany', 'France',
                    'Sri Lanka', 'Lithuania', 'Netherlands']
        if any(c.lower() == line_lower or c.lower() in line_lower for c in countries):
            company.country = line
            continue
        
        # State/zip pattern (US addresses)
        state_zip = re.search(r'([A-Z]{2})\s+(\d{5}(?:-\d{4})?)', line)
        if state_zip:
            company.city_state_zip = line
            continue
        
        # If second line and looks like a name (not an address)
        if i == 1 and not any(c.isdigit() for c in line) and len(line.split()) <= 4:
            # Likely a contact name
            company.contact_name = line
        else:
            # Accumulate as address
            address_lines.append(line)
    
    if address_lines:
        company.address = '\n'.join(address_lines)
    
    # Extract product codes
    product_text = ' '.join(company.products)
    codes = re.findall(r'\(([a-z]{2,4}-\d{4,6})\)', product_text)
    company.product_codes = codes
    
    return company

def is_company_header(text: str, prev_text: str = "") -> bool:
    """Detect if text block starts a new company entry."""
    lines = text.split('\n')
    if not lines:
        return False
    
    first_line = lines[0].strip()
    
    # Skip common headers
    skip_patterns = ['OMRI Products List', 'Crop Products by Company', 
                    'COMPANIES', 'Crop Products', 'Updated']
    if any(p in first_line for p in skip_patterns):
        return False
    
    # A company name typically:
    # - Is short-ish (< 80 chars)
    # - Doesn't start with common field indicators
    # - Doesn't look like an address (has numbers at start)
    # - Comes after "Products:" in previous block or is at top of column
    
    if len(first_line) > 80:
        return False
    
    if first_line.startswith(('P:', 'F:', 'Products:', 'www.', 'http')):
        return False
    
    if re.match(r'^\d+\s', first_line):  # Starts with number (address)
        return False
    
    if '@' in first_line:  # Email
        return False
    
    # If previous text ended with products, this is likely a new company
    if prev_text and 'Products:' in prev_text:
        return True
    
    # Check if it looks like a company name format
    # Usually title case or has LLC, Inc, Corp, Ltd, etc.
    company_indicators = ['LLC', 'Inc', 'Corp', 'Ltd', 'GmbH', 'S.A.', 'Pvt', 
                         'Company', 'Co.', 'Group', 'International', 'Industries']
    if any(ind in first_line for ind in company_indicators):
        return True
    
    return True  # Default to assuming it's a company header

def extract_companies_from_column(blocks: List[dict]) -> List[Company]:
    """Extract company records from a single column of text blocks."""
    companies = []
    current_text = ""
    prev_text = ""
    
    for block in blocks:
        text = block['text']
        
        # Check if this starts a new company
        if current_text and is_company_header(text, current_text):
            # Parse the accumulated text as a company
            company = parse_company_block(current_text)
            if company and company.name:
                companies.append(company)
            prev_text = current_text
            current_text = text
        else:
            if current_text:
                current_text += "\n" + text
            else:
                current_text = text
    
    # Don't forget the last company
    if current_text:
        company = parse_company_block(current_text)
        if company and company.name:
            companies.append(company)
    
    return companies

def filter_soil_companies(companies: List[Company], keywords: List[str]) -> List[Company]:
    """Filter companies that have products matching keywords."""
    soil_companies = []
    
    for company in companies:
        products_text = ' '.join(company.products).lower()
        name_lower = company.name.lower()
        
        for kw in keywords:
            if kw in products_text or kw in name_lower:
                soil_companies.append(company)
                break
    
    return soil_companies

def main():
    """Main extraction function."""
    pdf_path = Path(__file__).parent.parent / "data" / "CropByCompany-NOP-EN.pdf"
    
    if not pdf_path.exists():
        print(f"Error: PDF not found at {pdf_path}")
        return
    
    print(f"Extracting from: {pdf_path}")
    print("=" * 60)
    
    # Get page dimensions
    doc = fitz.open(pdf_path)
    page_width = doc[0].rect.width
    print(f"Page width: {page_width}")
    print(f"Total pages: {len(doc)}")
    doc.close()
    
    # Extract text blocks
    print("\n1. Extracting text blocks...")
    blocks = extract_text_blocks(str(pdf_path))
    print(f"   Found {len(blocks)} text blocks")
    
    # Group by column
    print("\n2. Grouping by column...")
    columns = group_blocks_by_column(blocks, page_width)
    for i, col in enumerate(columns):
        print(f"   Column {i+1}: {len(col)} blocks")
    
    # Extract companies from each column
    print("\n3. Extracting companies...")
    all_companies = []
    for i, col in enumerate(columns):
        companies = extract_companies_from_column(col)
        print(f"   Column {i+1}: {len(companies)} companies")
        all_companies.extend(companies)
    
    print(f"\n   Total companies extracted: {len(all_companies)}")
    
    # Filter for soil/media companies
    soil_keywords = [
        'potting soil', 'potting mix', 'growing media', 'growing mix',
        'soil mix', 'planting mix', 'container mix', 'seed starting',
        'seedling mix', 'transplant mix', 'organic soil', 'super soil',
        'living soil', 'coco coir', 'coco peat', 'peat moss', 'soilless',
        'raised bed', 'pro-mix', 'promix', 'substrate', 'compost blend'
    ]
    
    print("\n4. Filtering for soil/media companies...")
    soil_companies = filter_soil_companies(all_companies, soil_keywords)
    print(f"   Found {len(soil_companies)} companies with soil/media products")
    
    # Classify tiers
    craft_brands = ['foxfarm', 'fox farm', 'buildasoil', 'coast of maine', 
                   'down to earth', 'espoma', 'black gold', 'organic mechanics',
                   'roots organic', 'purple cow', 'opus grows', 'true organic']
    commodity_brands = ['scotts', 'miracle-gro', 'oldcastle', 'sun gro', 'premier tech']
    
    for company in soil_companies:
        name_lower = company.name.lower()
        if any(brand in name_lower for brand in craft_brands):
            company.tier = "Tier 1 - Craft"
        elif any(brand in name_lower for brand in commodity_brands):
            company.tier = "Tier 2 - Commodity"
        else:
            company.tier = "Tier 2 - Standard"
    
    # Save results
    output_path = pdf_path.parent / "omri_soil_companies_extracted.json"
    results = [asdict(c) for c in soil_companies]
    with open(output_path, 'w') as f:
        json.dump(results, f, indent=2)
    print(f"\n5. Saved to: {output_path}")
    
    # Print summary
    print("\n" + "=" * 60)
    print("EXTRACTION SUMMARY")
    print("=" * 60)
    
    # Group by tier
    tier1 = [c for c in soil_companies if hasattr(c, 'tier') and 'Tier 1' in c.tier]
    tier2 = [c for c in soil_companies if not hasattr(c, 'tier') or 'Tier 2' in c.tier]
    
    print(f"\nTier 1 (Craft Brands): {len(tier1)}")
    for c in tier1[:10]:
        print(f"  • {c.name}")
        if c.email:
            print(f"    Email: {c.email}")
        if c.products:
            print(f"    Products: {c.products[0][:60]}...")
    
    print(f"\nTier 2 (Standard/Commodity): {len(tier2)}")
    
    # Show US-based companies
    us_companies = [c for c in soil_companies if c.country and 'United States' in c.country]
    print(f"\nUS-based companies: {len(us_companies)}")
    
    return soil_companies

if __name__ == "__main__":
    main()
