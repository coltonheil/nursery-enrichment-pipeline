#!/usr/bin/env python3
"""
Import OMRI Soil Companies into the Nursery Enrichment Pipeline

Reads from data/omri_soil_companies.json and imports Tier 1 craft soil blenders
as leads with soil_mixer business_type.

Usage:
    python scripts/import_omri_soil_companies.py
    python scripts/import_omri_soil_companies.py --tier all
    python scripts/import_omri_soil_companies.py --dry-run
"""

import json
import sqlite3
import argparse
from pathlib import Path
from datetime import datetime

# Project paths
PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"
DB_PATH = DATA_DIR / "leads.db"
OMRI_FILE = DATA_DIR / "omri_soil_companies.json"


def get_db_connection():
    """Create and return a database connection."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def check_existing_lead(conn, company_name: str, omri_code: str) -> dict:
    """Check if a lead already exists by name or OMRI code."""
    cursor = conn.cursor()
    
    # Check by OMRI code first (most reliable)
    cursor.execute(
        "SELECT id, business_name FROM leads WHERE omri_code = ?",
        (omri_code,)
    )
    result = cursor.fetchone()
    if result:
        return {"exists": True, "id": result["id"], "match_type": "omri_code"}
    
    # Check by business name (fuzzy)
    cursor.execute(
        "SELECT id, business_name FROM leads WHERE LOWER(business_name) = LOWER(?)",
        (company_name,)
    )
    result = cursor.fetchone()
    if result:
        return {"exists": True, "id": result["id"], "match_type": "name"}
    
    return {"exists": False}


def insert_omri_lead(conn, company: dict, dry_run: bool = False) -> tuple:
    """
    Insert an OMRI company as a lead.
    
    Returns:
        tuple: (lead_id, status) where status is 'created', 'exists', or 'error'
    """
    cursor = conn.cursor()
    
    # Check for existing
    existing = check_existing_lead(conn, company["name"], company["code"])
    if existing["exists"]:
        return (existing["id"], f"exists ({existing['match_type']})")
    
    if dry_run:
        return (None, "would_create")
    
    # Prepare data
    keywords = company.get("keywords", [])
    signals = json.dumps({
        "keywords": keywords,
        "source": "omri_scrape",
        "scraped_at": datetime.now().isoformat()
    })
    
    # Insert lead
    cursor.execute("""
        INSERT INTO leads (
            business_name,
            website,
            source_file,
            enrichment_status,
            business_type,
            data_source,
            omri_code,
            omri_url,
            soil_mixer_tier,
            soil_mixer_signals,
            organic_focus,
            is_organic_certified,
            created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
    """, (
        company["name"],
        company["url"],  # OMRI URL as initial website, will enrich later
        "omri_soil_companies.json",
        "pending",
        "soil_mixer",
        "omri",
        company["code"],
        company["url"],
        company.get("tier", "tier_1"),
        signals,
        True,  # organic_focus - all OMRI listings are organic
        True,  # is_organic_certified - OMRI = certified
    ))
    
    lead_id = cursor.lastrowid
    
    # Log the import
    cursor.execute("""
        INSERT INTO processing_log (lead_id, action, details)
        VALUES (?, 'imported', ?)
    """, (lead_id, f"Imported from OMRI scrape - {company['code']}"))
    
    conn.commit()
    return (lead_id, "created")


def import_omri_companies(tier_filter: str = "tier_1", dry_run: bool = False):
    """
    Import OMRI companies from JSON file.
    
    Args:
        tier_filter: "tier_1", "tier_2", or "all"
        dry_run: If True, don't actually insert, just report
    """
    # Load OMRI data
    with open(OMRI_FILE) as f:
        data = json.load(f)
    
    # Select companies based on tier
    companies = []
    if tier_filter in ("tier_1", "all"):
        companies.extend(data.get("tier_1_craft", []))
    if tier_filter in ("tier_2", "all"):
        companies.extend(data.get("tier_2_commodity", []))
    if tier_filter == "all":
        companies.extend(data.get("other_potting_media", []))
    
    print(f"{'[DRY RUN] ' if dry_run else ''}Importing {len(companies)} OMRI soil companies")
    print(f"Tier filter: {tier_filter}")
    print("-" * 60)
    
    conn = get_db_connection()
    
    stats = {"created": 0, "exists": 0, "error": 0}
    
    for company in companies:
        try:
            lead_id, status = insert_omri_lead(conn, company, dry_run)
            
            if "created" in status or "would_create" in status:
                stats["created"] += 1
                print(f"  ✅ {company['name']} ({company['code']}) - {status}")
            elif "exists" in status:
                stats["exists"] += 1
                print(f"  ⏭️  {company['name']} - {status}")
            else:
                stats["error"] += 1
                print(f"  ❌ {company['name']} - {status}")
                
        except Exception as e:
            stats["error"] += 1
            print(f"  ❌ {company['name']} - Error: {e}")
    
    conn.close()
    
    print("-" * 60)
    print(f"Summary: {stats['created']} created, {stats['exists']} existing, {stats['error']} errors")
    
    return stats


def main():
    parser = argparse.ArgumentParser(description="Import OMRI soil companies to pipeline")
    parser.add_argument("--tier", type=str, default="tier_1", 
                        choices=["tier_1", "tier_2", "all"],
                        help="Which tier(s) to import")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would be imported without inserting")
    args = parser.parse_args()
    
    import_omri_companies(tier_filter=args.tier, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
