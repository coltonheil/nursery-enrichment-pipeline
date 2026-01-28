#!/usr/bin/env python3
"""
Overnight Pipeline Orchestrator
===============================
Processes all leads through: Scrape → Gemini Enrich → Email Hunt → Score

Features:
- Processes by tier (A → B → C → U)
- Tests every 500 leads
- Self-corrects if quality drops
- Tracks progress and estimates completion
- Outputs campaign-ready leads

KPI Targets:
- Scrape success: >90%
- Text quality: >2000 chars average
- Email extraction: >25% of scraped leads
- Campaign-ready (name + email): 1500+ leads

Usage:
    python overnight_pipeline.py [--test] [--tier A|B|C|U]
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))
sys.stdout.reconfigure(line_buffering=True)

import sqlite3
import time
import json
import argparse
from datetime import datetime
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, asdict

# Import enrichment modules
from enrichment.web_scraper import scrape_and_extract
from enrichment.gemini_client import enrich_lead_with_gemini
from enrichment.email_hunter import hunt_email
from enrichment.scorer import calculate_score

# Configuration
DB_PATH = 'data/leads.db'
BATCH_SIZE = 25  # Process in small batches
TEST_INTERVAL = 500  # Test every N leads
RATE_LIMIT_DELAY = 0.5  # Seconds between requests

# KPI Thresholds
MIN_SCRAPE_SUCCESS = 0.85
MIN_TEXT_CHARS = 1500
MIN_EMAIL_RATE = 0.15
TARGET_CAMPAIGN_READY = 1500


@dataclass
class PipelineStats:
    """Track pipeline statistics."""
    started_at: str = ""
    current_tier: str = ""
    leads_processed: int = 0
    leads_scraped: int = 0
    leads_enriched: int = 0
    leads_with_email: int = 0
    leads_with_name: int = 0
    campaign_ready: int = 0
    scrape_failures: int = 0
    enrich_failures: int = 0
    total_chars_scraped: int = 0
    errors: List[str] = None
    
    def __post_init__(self):
        if self.errors is None:
            self.errors = []
    
    @property
    def scrape_success_rate(self) -> float:
        if self.leads_processed == 0:
            return 0
        return self.leads_scraped / self.leads_processed
    
    @property
    def avg_text_chars(self) -> float:
        if self.leads_scraped == 0:
            return 0
        return self.total_chars_scraped / self.leads_scraped
    
    @property
    def email_rate(self) -> float:
        if self.leads_scraped == 0:
            return 0
        return self.leads_with_email / self.leads_scraped
    
    @property
    def name_rate(self) -> float:
        if self.leads_scraped == 0:
            return 0
        return self.leads_with_name / self.leads_scraped
    
    def to_dict(self) -> Dict:
        d = asdict(self)
        d['scrape_success_rate'] = f"{self.scrape_success_rate:.1%}"
        d['avg_text_chars'] = f"{self.avg_text_chars:.0f}"
        d['email_rate'] = f"{self.email_rate:.1%}"
        d['name_rate'] = f"{self.name_rate:.1%}"
        return d


def log(msg: str, level: str = "INFO"):
    """Print timestamped log message."""
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] [{level}] {msg}", flush=True)


def get_leads_to_process(tier: str, limit: int = 500) -> List[Dict]:
    """Get leads that need processing for a tier."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Get leads that need scraping or enrichment
    cursor.execute("""
        SELECT id, business_name, website, owner_name, contact_name,
               owner_email, contact_email, website_text, tier, city, state,
               LENGTH(website_text) as text_len
        FROM leads
        WHERE tier = ?
          AND website IS NOT NULL
          AND (
              website_text IS NULL 
              OR LENGTH(website_text) < 2000
              OR (owner_name IS NULL AND contact_name IS NULL)
              OR (owner_email IS NULL AND contact_email IS NULL)
          )
        ORDER BY 
            CASE WHEN website_text IS NULL THEN 0 ELSE 1 END,
            LENGTH(website_text) ASC
        LIMIT ?
    """, (tier, limit))
    
    leads = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return leads


def get_unscored_leads(limit: int = 500) -> List[Dict]:
    """Get U-tier leads that need full processing."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT id, business_name, website, owner_name, contact_name,
               owner_email, contact_email, website_text, tier, city, state
        FROM leads
        WHERE tier = 'U'
          AND website IS NOT NULL
        ORDER BY id
        LIMIT ?
    """, (limit,))
    
    leads = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return leads


def process_lead(lead: Dict, stats: PipelineStats) -> Dict:
    """Process a single lead through the full pipeline."""
    lead_id = lead['id']
    result = {'id': lead_id, 'success': False, 'steps': []}
    
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Step 1: Scrape if needed
        needs_scrape = lead.get('website_text') is None or len(lead.get('website_text', '') or '') < 2000
        
        if needs_scrape and lead.get('website'):
            try:
                text, info = scrape_and_extract(lead['website'])
                if text and len(text) > 0:
                    stats.leads_scraped += 1
                    stats.total_chars_scraped += len(text)
                    result['steps'].append(f"scraped:{len(text)}chars")
                    
                    cursor.execute("""
                        UPDATE leads 
                        SET website_text = ?, scrape_status = 'complete', scraped_at = ?
                        WHERE id = ?
                    """, (text, datetime.now().isoformat(), lead_id))
                    lead['website_text'] = text
                else:
                    stats.scrape_failures += 1
                    result['steps'].append("scrape:failed")
            except Exception as e:
                stats.scrape_failures += 1
                result['steps'].append(f"scrape:error:{str(e)[:30]}")
        else:
            if lead.get('website_text'):
                stats.leads_scraped += 1
                stats.total_chars_scraped += len(lead['website_text'])
        
        # Step 2: Gemini enrichment if we have text and need name OR email
        if lead.get('website_text') and len(lead['website_text']) > 100:
            needs_name = lead.get('owner_name') is None and lead.get('contact_name') is None
            needs_email = lead.get('owner_email') is None and lead.get('contact_email') is None
            needs_enrich = needs_name or needs_email
            
            if needs_enrich:
                try:
                    enrichment = enrich_lead_with_gemini(
                        website_text=lead['website_text'],
                        business_name=lead['business_name'],
                        city=lead.get('city', ''),
                        state=lead.get('state', '')
                    )
                    
                    if enrichment:
                        stats.leads_enriched += 1
                        
                        # Update lead with enrichment
                        owner_name = enrichment.get('owner_name') or enrichment.get('contact_name')
                        contact_name = enrichment.get('contact_name')
                        email = enrichment.get('email') or enrichment.get('owner_email')
                        
                        if owner_name or contact_name:
                            stats.leads_with_name += 1
                            result['steps'].append(f"name:{owner_name or contact_name}")
                        
                        if email:
                            stats.leads_with_email += 1
                            result['steps'].append(f"email:{email}")
                        
                        cursor.execute("""
                            UPDATE leads
                            SET owner_name = COALESCE(?, owner_name),
                                contact_name = COALESCE(?, contact_name),
                                owner_email = COALESCE(?, owner_email),
                                gemini_status = 'complete',
                                gemini_enriched_at = ?
                            WHERE id = ?
                        """, (owner_name, contact_name, email, datetime.now().isoformat(), lead_id))
                        
                        lead['owner_name'] = owner_name
                        lead['contact_name'] = contact_name
                        lead['owner_email'] = email
                        
                except Exception as e:
                    stats.enrich_failures += 1
                    result['steps'].append(f"enrich:error:{str(e)[:30]}")
        
        # Step 3: Email hunting if we have a name but no email
        has_name = lead.get('owner_name') or lead.get('contact_name')
        has_email = lead.get('owner_email') or lead.get('contact_email')
        
        if has_name and not has_email and lead.get('website'):
            try:
                email_result = hunt_email(
                    owner_name=lead.get('owner_name') or lead.get('contact_name'),
                    business_name=lead['business_name'],
                    website=lead['website']
                )
                
                if email_result and email_result.email:
                    stats.leads_with_email += 1
                    result['steps'].append(f"hunted:{email_result.email}")
                    
                    cursor.execute("""
                        UPDATE leads
                        SET contact_email = ?,
                            email_method = ?,
                            email_confidence = ?
                        WHERE id = ?
                    """, (email_result.email, email_result.method, 
                          email_result.confidence, lead_id))
                    
            except Exception as e:
                result['steps'].append(f"hunt:error:{str(e)[:30]}")
        
        # Step 4: Check if campaign-ready
        conn.commit()
        
        # Re-check current state
        cursor.execute("""
            SELECT owner_name, contact_name, owner_email, contact_email
            FROM leads WHERE id = ?
        """, (lead_id,))
        row = cursor.fetchone()
        
        if row:
            final_has_name = row[0] or row[1]
            final_has_email = row[2] or row[3]
            
            if final_has_name and final_has_email:
                stats.campaign_ready += 1
                result['campaign_ready'] = True
        
        conn.close()
        result['success'] = True
        stats.leads_processed += 1
        
    except Exception as e:
        stats.errors.append(f"Lead {lead_id}: {str(e)[:50]}")
        result['error'] = str(e)
    
    return result


def run_quality_test(stats: PipelineStats) -> Tuple[bool, List[str]]:
    """Run quality tests and return (passed, issues)."""
    issues = []
    
    # Test 1: Scrape success rate
    if stats.scrape_success_rate < MIN_SCRAPE_SUCCESS:
        issues.append(f"Scrape rate {stats.scrape_success_rate:.1%} < {MIN_SCRAPE_SUCCESS:.0%} target")
    
    # Test 2: Text quality
    if stats.avg_text_chars < MIN_TEXT_CHARS:
        issues.append(f"Avg text {stats.avg_text_chars:.0f} chars < {MIN_TEXT_CHARS} target")
    
    # Test 3: Email rate
    if stats.email_rate < MIN_EMAIL_RATE:
        issues.append(f"Email rate {stats.email_rate:.1%} < {MIN_EMAIL_RATE:.0%} target")
    
    passed = len(issues) == 0
    return passed, issues


def get_current_totals() -> Dict:
    """Get current campaign-ready totals from database."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT 
            COUNT(*) as total,
            SUM(CASE WHEN (owner_email IS NOT NULL OR contact_email IS NOT NULL) 
                     AND (owner_name IS NOT NULL OR contact_name IS NOT NULL) 
                     THEN 1 ELSE 0 END) as campaign_ready,
            SUM(CASE WHEN owner_email IS NOT NULL OR contact_email IS NOT NULL THEN 1 ELSE 0 END) as has_email,
            SUM(CASE WHEN owner_name IS NOT NULL OR contact_name IS NOT NULL THEN 1 ELSE 0 END) as has_name
        FROM leads
        WHERE tier IN ('A', 'B', 'C')
    """)
    
    row = cursor.fetchone()
    conn.close()
    
    return {
        'total': row[0],
        'campaign_ready': row[1] or 0,
        'has_email': row[2] or 0,
        'has_name': row[3] or 0
    }


def save_checkpoint(stats: PipelineStats, checkpoint_num: int):
    """Save checkpoint to file."""
    checkpoint = {
        'checkpoint': checkpoint_num,
        'timestamp': datetime.now().isoformat(),
        'stats': stats.to_dict(),
        'totals': get_current_totals()
    }
    
    checkpoint_file = f"data/checkpoint_{checkpoint_num:04d}.json"
    with open(checkpoint_file, 'w') as f:
        json.dump(checkpoint, f, indent=2)
    
    log(f"Checkpoint {checkpoint_num} saved to {checkpoint_file}")


def print_progress(stats: PipelineStats, tier: str, batch_num: int):
    """Print progress summary."""
    totals = get_current_totals()
    
    print(f"\n{'='*60}")
    print(f"PROGRESS UPDATE - Tier {tier} - Batch {batch_num}")
    print(f"{'='*60}")
    print(f"This session:")
    print(f"  Processed: {stats.leads_processed}")
    print(f"  Scraped: {stats.leads_scraped} ({stats.scrape_success_rate:.1%})")
    print(f"  Avg text: {stats.avg_text_chars:.0f} chars")
    print(f"  With email: {stats.leads_with_email} ({stats.email_rate:.1%})")
    print(f"  With name: {stats.leads_with_name} ({stats.name_rate:.1%})")
    print(f"\nTotal campaign-ready: {totals['campaign_ready']} / {TARGET_CAMPAIGN_READY} target")
    print(f"{'='*60}\n")


def main():
    parser = argparse.ArgumentParser(description='Overnight Pipeline Orchestrator')
    parser.add_argument('--test', action='store_true', help='Test mode - process 50 leads only')
    parser.add_argument('--tier', choices=['A', 'B', 'C', 'U'], help='Process specific tier only')
    args = parser.parse_args()
    
    log("="*60)
    log("OVERNIGHT PIPELINE ORCHESTRATOR")
    log("="*60)
    
    # Initialize stats
    stats = PipelineStats(started_at=datetime.now().isoformat())
    
    # Determine tier order
    if args.tier:
        tiers = [args.tier]
    else:
        tiers = ['A', 'B', 'C', 'U']
    
    # Check current status
    totals = get_current_totals()
    log(f"Current campaign-ready: {totals['campaign_ready']} / {TARGET_CAMPAIGN_READY}")
    
    if totals['campaign_ready'] >= TARGET_CAMPAIGN_READY:
        log(f"Target already met! Exiting.")
        return 0
    
    checkpoint_num = 0
    batch_num = 0
    
    for tier in tiers:
        stats.current_tier = tier
        log(f"Processing Tier {tier}...")
        
        while True:
            # Get batch of leads
            if tier == 'U':
                leads = get_unscored_leads(limit=BATCH_SIZE)
            else:
                leads = get_leads_to_process(tier, limit=BATCH_SIZE)
            
            if not leads:
                log(f"No more leads to process in Tier {tier}")
                break
            
            batch_num += 1
            log(f"Batch {batch_num}: Processing {len(leads)} leads...")
            
            # Process each lead
            for i, lead in enumerate(leads, 1):
                result = process_lead(lead, stats)
                
                # Rate limiting
                time.sleep(RATE_LIMIT_DELAY)
                
                # Progress indicator every 10 leads
                if i % 10 == 0:
                    print(f"  [{i}/{len(leads)}] {stats.campaign_ready} campaign-ready", flush=True)
            
            # Print progress
            print_progress(stats, tier, batch_num)
            
            # Quality test every TEST_INTERVAL leads
            if stats.leads_processed >= (checkpoint_num + 1) * TEST_INTERVAL:
                checkpoint_num += 1
                save_checkpoint(stats, checkpoint_num)
                
                passed, issues = run_quality_test(stats)
                
                if not passed:
                    log("QUALITY TEST FAILED:", "WARN")
                    for issue in issues:
                        log(f"  - {issue}", "WARN")
                    log("Consider investigating before continuing", "WARN")
                else:
                    log("Quality test PASSED ✓")
            
            # Check if target met
            totals = get_current_totals()
            if totals['campaign_ready'] >= TARGET_CAMPAIGN_READY:
                log(f"🎉 TARGET MET! {totals['campaign_ready']} campaign-ready leads")
                break
            
            # Test mode - exit early
            if args.test and stats.leads_processed >= 50:
                log("Test mode - stopping after 50 leads")
                break
        
        # Check if target met after tier
        totals = get_current_totals()
        if totals['campaign_ready'] >= TARGET_CAMPAIGN_READY:
            break
        
        if args.test:
            break
    
    # Final summary
    log("="*60)
    log("PIPELINE COMPLETE")
    log("="*60)
    
    totals = get_current_totals()
    print(f"\nFinal Results:")
    print(f"  Leads processed: {stats.leads_processed}")
    print(f"  Campaign-ready: {totals['campaign_ready']} / {TARGET_CAMPAIGN_READY}")
    print(f"  Has email: {totals['has_email']}")
    print(f"  Has name: {totals['has_name']}")
    
    if stats.errors:
        print(f"\nErrors ({len(stats.errors)}):")
        for err in stats.errors[:10]:
            print(f"  - {err}")
    
    # Save final checkpoint
    save_checkpoint(stats, 9999)
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
