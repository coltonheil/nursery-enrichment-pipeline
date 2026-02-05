#!/usr/bin/env python3
"""
Export final OMRI parsed data with quality filters.
"""

import json
import csv
import re
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"

def is_valid_company_name(name: str) -> bool:
    """Check if name looks like a valid company name."""
    if not name or len(name) < 3:
        return False
    
    # Skip URLs
    if 'www.' in name.lower() or 'http' in name.lower() or '.com' in name.lower():
        return False
    
    # Skip email-like
    if '@' in name:
        return False
    
    # Skip product codes in name
    if re.search(r'\([a-z]{2,4}-\d{4,6}\)', name, re.IGNORECASE):
        return False
    
    # Skip addresses (city, state zip)
    if re.match(r'^[\w\s]+,\s*[A-Z]{2}\s+\d{5}', name):
        return False
    
    # Skip lines that are just states/countries
    if name in ['United States', 'Canada', 'Mexico', 'US', 'USA']:
        return False
    
    return True


def export_final():
    # Load iteration 6 results
    with open(DATA_DIR / "parsing_iterations" / "iteration_6.json") as f:
        data = json.load(f)
    
    print(f"Loaded {len(data['companies'])} companies from iteration 6")
    
    # Filter for quality
    quality_companies = []
    for c in data['companies']:
        # Must have valid name
        if not is_valid_company_name(c['name']):
            continue
        
        # Must have email
        if not c.get('email'):
            continue
        
        # Must have products
        if not c.get('product_codes'):
            continue
        
        # Confidence >= 60%
        if c.get('parse_confidence', 0) < 0.6:
            continue
        
        quality_companies.append(c)
    
    print(f"Quality filtered: {len(quality_companies)} companies")
    
    # Identify soil-relevant companies
    soil_keywords = ['soil', 'potting', 'compost', 'media', 'mix', 'substrate', 
                     'peat', 'coir', 'vermicompost', 'worm', 'organic', 'humus',
                     'amendment', 'fertilizer', 'grow', 'plant']
    
    soil_companies = []
    for c in quality_companies:
        text = (c['name'] + ' ' + ' '.join(c.get('products', []))).lower()
        if any(kw in text for kw in soil_keywords):
            # Add soil relevance flag
            c['soil_relevant'] = True
            soil_companies.append(c)
    
    print(f"Soil-relevant: {len(soil_companies)} companies")
    
    # Export to JSON
    output = {
        'metadata': {
            'source': 'OMRI CropByCompany-NOP-EN.pdf',
            'extraction_date': datetime.now().isoformat(),
            'total_in_pdf': 2250,
            'quality_filtered': len(quality_companies),
            'soil_relevant': len(soil_companies),
        },
        'all_companies': quality_companies,
        'soil_companies': soil_companies,
    }
    
    json_path = DATA_DIR / "omri_companies_final.json"
    with open(json_path, 'w') as f:
        json.dump(output, f, indent=2)
    print(f"Saved JSON to: {json_path}")
    
    # Export soil companies to CSV for easy review
    csv_path = DATA_DIR / "omri_soil_companies_final.csv"
    with open(csv_path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=[
            'name', 'email', 'website', 'phone', 'country', 
            'city', 'state', 'zip_code', 'product_count', 'confidence'
        ])
        writer.writeheader()
        
        for c in soil_companies:
            writer.writerow({
                'name': c['name'],
                'email': c.get('email', ''),
                'website': c.get('website', ''),
                'phone': c.get('phone', ''),
                'country': c.get('country', ''),
                'city': c.get('city', ''),
                'state': c.get('state', ''),
                'zip_code': c.get('zip_code', ''),
                'product_count': len(c.get('product_codes', [])),
                'confidence': f"{c.get('parse_confidence', 0):.0%}",
            })
    
    print(f"Saved CSV to: {csv_path}")
    
    # Show top soil companies
    print("\n=== Top Soil Companies by Product Count ===")
    sorted_soil = sorted(soil_companies, key=lambda x: len(x.get('product_codes', [])), reverse=True)
    for c in sorted_soil[:20]:
        print(f"  [{len(c.get('product_codes', [])):3} prods] {c['name'][:45]:45} | {c.get('email', '')}")


if __name__ == '__main__':
    export_final()
