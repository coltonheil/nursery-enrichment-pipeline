#!/usr/bin/env python3
"""
Import OMRI soil companies from PDF parsing into the leads database.
"""

import json
import sqlite3
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"
DB_PATH = DATA_DIR / "leads.db"


def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def import_soil_companies():
    # Load parsed data
    with open(DATA_DIR / "omri_companies_final.json") as f:
        data = json.load(f)
    
    soil_companies = data['soil_companies']
    print(f"Importing {len(soil_companies)} soil-relevant companies from OMRI PDF")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    stats = {'created': 0, 'skipped': 0, 'errors': 0}
    
    for company in soil_companies:
        name = company['name']
        
        # Check for existing by name or email
        cursor.execute("""
            SELECT id FROM leads 
            WHERE LOWER(business_name) = LOWER(?) 
               OR (owner_email IS NOT NULL AND LOWER(owner_email) = LOWER(?))
        """, (name, company.get('email', '')))
        
        existing = cursor.fetchone()
        if existing:
            stats['skipped'] += 1
            continue
        
        try:
            # Prepare signals JSON
            signals = json.dumps({
                'source': 'omri_pdf_parse',
                'products': company.get('products', [])[:5],
                'product_codes': company.get('product_codes', []),
                'product_count': len(company.get('product_codes', [])),
                'parse_confidence': company.get('parse_confidence', 0),
                'parsed_at': datetime.now().isoformat()
            })
            
            # Note: country stored in address field since no country column
            address = company.get('country', '')
            
            cursor.execute("""
                INSERT INTO leads (
                    business_name,
                    address,
                    city,
                    state,
                    zip,
                    phone,
                    website,
                    owner_email,
                    source_file,
                    enrichment_status,
                    business_type,
                    data_source,
                    omri_url,
                    soil_mixer_tier,
                    soil_mixer_signals,
                    organic_focus,
                    is_organic_certified,
                    created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (
                name,
                address,
                company.get('city'),
                company.get('state'),
                company.get('zip_code'),
                company.get('phone'),
                company.get('website'),
                company.get('email'),
                'omri_pdf_parse',
                'pending',
                'soil_mixer',
                'omri_pdf',
                f"https://www.omri.org/omri-search?query={name.replace(' ', '+')}",
                'tier_1',
                signals,
                True,
                True
            ))
            
            lead_id = cursor.lastrowid
            
            # Log the import
            cursor.execute("""
                INSERT INTO processing_log (lead_id, action, details)
                VALUES (?, 'imported', ?)
            """, (lead_id, f"Imported from OMRI PDF - {len(company.get('product_codes', []))} products"))
            
            stats['created'] += 1
            print(f"  ✅ {name} ({len(company.get('product_codes', []))} products)")
            
        except Exception as e:
            stats['errors'] += 1
            print(f"  ❌ {name}: {e}")
    
    conn.commit()
    conn.close()
    
    print(f"\n{'='*60}")
    print(f"Import complete!")
    print(f"  Created: {stats['created']}")
    print(f"  Skipped (existing): {stats['skipped']}")
    print(f"  Errors: {stats['errors']}")
    
    return stats


if __name__ == '__main__':
    import_soil_companies()
