#!/usr/bin/env python3
"""
Check Tier U enrichment status and estimate completion time/cost.
"""

import sqlite3
import json
from pathlib import Path
from datetime import datetime, timedelta

DB_PATH = 'data/leads.db'
CHECKPOINT_FILE = 'data/tier_u_checkpoint.json'

# Rate limiting assumptions
BASE_DELAY = 4.5  # seconds per request
BATCH_SIZE = 50
BATCH_BREAK = 30  # seconds

# Pricing (Gemini 2.0 Flash free tier limits)
FREE_TIER_LIMIT = 1500  # requests per day
COST_PER_REQUEST = 0  # Free tier (but could hit limits)

def check_status():
    """Check current Tier U enrichment status."""
    
    print("=" * 80)
    print("TIER U ENRICHMENT STATUS")
    print("=" * 80)
    print()
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Overall Tier U stats
    cursor.execute("""
        SELECT 
            COUNT(*) as total,
            SUM(CASE WHEN gemini_status = 'enriched' THEN 1 ELSE 0 END) as enriched,
            SUM(CASE WHEN gemini_status = 'failed' THEN 1 ELSE 0 END) as failed,
            SUM(CASE WHEN gemini_status = 'pending' OR gemini_status IS NULL THEN 1 ELSE 0 END) as pending,
            SUM(CASE WHEN website_text IS NOT NULL AND LENGTH(website_text) > 1000 THEN 1 ELSE 0 END) as has_good_content,
            SUM(CASE WHEN website_text IS NULL OR LENGTH(website_text) <= 1000 THEN 1 ELSE 0 END) as poor_content
        FROM leads
        WHERE tier = 'U'
    """)
    
    row = cursor.fetchone()
    total, enriched, failed, pending, has_good_content, poor_content = row
    
    print(f"📊 Tier U Lead Distribution:")
    print(f"   Total Tier U leads: {total:,}")
    print(f"   └─ Enriched: {enriched:,} ({enriched/max(total,1)*100:.1f}%)")
    print(f"   └─ Failed: {failed:,} ({failed/max(total,1)*100:.1f}%)")
    print(f"   └─ Pending: {pending:,} ({pending/max(total,1)*100:.1f}%)")
    print()
    
    print(f"📄 Content Quality:")
    print(f"   Has good content (>1000 chars): {has_good_content:,} ({has_good_content/max(total,1)*100:.1f}%)")
    print(f"   Poor/no content: {poor_content:,} ({poor_content/max(total,1)*100:.1f}%)")
    print()
    
    # Processable leads (good content + not enriched)
    cursor.execute("""
        SELECT COUNT(*) 
        FROM leads
        WHERE tier = 'U'
          AND website_text IS NOT NULL
          AND LENGTH(website_text) > 1000
          AND (gemini_status IS NULL OR gemini_status NOT IN ('complete', 'enriched'))
    """)
    
    processable = cursor.fetchone()[0]
    
    print(f"✅ Ready to Process:")
    print(f"   Leads ready for enrichment: {processable:,}")
    print()
    
    # Check checkpoint
    checkpoint_exists = Path(CHECKPOINT_FILE).exists()
    if checkpoint_exists:
        with open(CHECKPOINT_FILE, 'r') as f:
            checkpoint = json.load(f)
        
        processed_ids = checkpoint.get('processed_ids', [])
        stats = checkpoint.get('stats', {})
        
        print(f"💾 Checkpoint Found:")
        print(f"   Already processed: {len(processed_ids):,} leads")
        print(f"   Upgraded to A: {stats.get('upgraded_a', 0)}")
        print(f"   Upgraded to B: {stats.get('upgraded_b', 0)}")
        print(f"   Upgraded to C: {stats.get('upgraded_c', 0)}")
        print(f"   Contacts found: {stats.get('contacts_found', 0)}")
        print()
        
        remaining = processable - len(processed_ids)
    else:
        print(f"💾 No checkpoint found (starting fresh)")
        print()
        remaining = processable
    
    print(f"⏳ Remaining to Process: {remaining:,} leads")
    print()
    
    # Estimate time and cost
    if remaining > 0:
        # Time calculation
        requests_per_batch = BATCH_SIZE
        batches = (remaining + BATCH_SIZE - 1) // BATCH_SIZE  # Round up
        
        request_time = remaining * BASE_DELAY  # Time for requests
        batch_break_time = (batches - 1) * BATCH_BREAK  # Time for breaks
        total_seconds = request_time + batch_break_time
        
        hours = total_seconds / 3600
        
        print(f"⏱️  Estimated Completion Time:")
        print(f"   Request time: {request_time/3600:.1f} hours ({remaining} × {BASE_DELAY}s)")
        print(f"   Break time: {batch_break_time/60:.0f} min ({batches} batches × {BATCH_BREAK}s)")
        print(f"   Total: {hours:.1f} hours ({total_seconds/60:.0f} minutes)")
        print()
        
        if hours < 1:
            eta = f"~{int(total_seconds/60)} minutes"
        elif hours < 24:
            eta = f"~{hours:.1f} hours"
        else:
            days = hours / 24
            eta = f"~{days:.1f} days"
        
        print(f"   ETA: {eta}")
        print()
        
        # Cost calculation (free tier)
        if remaining <= FREE_TIER_LIMIT:
            print(f"💰 Cost Estimate:")
            print(f"   Within free tier limit ({FREE_TIER_LIMIT} RPD)")
            print(f"   Cost: $0.00 (Gemini 2.0 Flash free tier)")
        else:
            print(f"💰 Cost Estimate:")
            print(f"   ⚠️  Exceeds free tier limit!")
            print(f"   Requests needed: {remaining:,}")
            print(f"   Free tier limit: {FREE_TIER_LIMIT:,} per day")
            print(f"   Days needed: {remaining/FREE_TIER_LIMIT:.1f}")
            print()
            print(f"   Strategy: Process {FREE_TIER_LIMIT} per day to stay in free tier")
            print(f"   Total time: ~{remaining/FREE_TIER_LIMIT:.0f} days")
        
        print()
        
        # Expected results (based on historical data)
        # From previous Tier U run: 21.2% upgraded to A, 7.7% to B
        expected_a = remaining * 0.212
        expected_b = remaining * 0.077
        expected_contacts = remaining * 0.20  # ~20% contact extraction rate
        
        print(f"📈 Expected Results (Based on Historical Data):")
        print(f"   New Tier A leads: ~{int(expected_a)} (21.2% of processed)")
        print(f"   New Tier B leads: ~{int(expected_b)} (7.7% of processed)")
        print(f"   Total A+B upgrades: ~{int(expected_a + expected_b)}")
        print(f"   Contacts extracted: ~{int(expected_contacts)} (20% of processed)")
        print()
        
        # Value calculation
        value_per_a = 5  # $5 per Tier A lead
        value_per_b = 3  # $3 per Tier B lead
        value_per_contact = 2  # $2 per contact
        
        estimated_value = (expected_a * value_per_a) + (expected_b * value_per_b) + (expected_contacts * value_per_contact)
        
        print(f"💎 Estimated Value:")
        print(f"   Tier A leads: {int(expected_a)} × ${value_per_a} = ${int(expected_a * value_per_a)}")
        print(f"   Tier B leads: {int(expected_b)} × ${value_per_b} = ${int(expected_b * value_per_b)}")
        print(f"   Contacts: {int(expected_contacts)} × ${value_per_contact} = ${int(expected_contacts * value_per_contact)}")
        print(f"   Total estimated value: ${int(estimated_value)}")
        print()
    
    # Recent upgrade stats
    cursor.execute("""
        SELECT tier, COUNT(*) 
        FROM leads 
        WHERE tier IN ('A', 'B', 'C')
          AND gemini_enriched_at > date('now', '-7 days')
        GROUP BY tier
    """)
    
    recent_upgrades = dict(cursor.fetchall())
    
    if recent_upgrades:
        print(f"📊 Recent Activity (Last 7 Days):")
        print(f"   Upgraded to A: {recent_upgrades.get('A', 0)}")
        print(f"   Upgraded to B: {recent_upgrades.get('B', 0)}")
        print(f"   Upgraded to C: {recent_upgrades.get('C', 0)}")
        print()
    
    conn.close()
    
    print("=" * 80)
    
    # Recommendations
    if remaining > 0:
        print()
        print("💡 Recommended Next Steps:")
        print()
        
        if remaining <= FREE_TIER_LIMIT:
            print(f"1️⃣  Run enrichment NOW (will complete in {eta}):")
            print(f"   python enrich_tier_u_v2.py")
            print()
        else:
            daily_runs = (remaining + FREE_TIER_LIMIT - 1) // FREE_TIER_LIMIT
            print(f"1️⃣  Process in daily batches to stay in free tier:")
            print(f"   Day 1: python enrich_tier_u_v2.py  # Processes {FREE_TIER_LIMIT} leads")
            print(f"   Day 2: python enrich_tier_u_v2.py  # Resumes from checkpoint")
            print(f"   ... ({daily_runs} days total)")
            print()
        
        if checkpoint_exists:
            print(f"2️⃣  Resume from checkpoint (if interrupted):")
            print(f"   python enrich_tier_u_v2.py")
            print()
            
            print(f"3️⃣  Start fresh (ignore checkpoint):")
            print(f"   python enrich_tier_u_v2.py --fresh")
            print()
        else:
            print(f"2️⃣  Test first (process 50 leads):")
            print(f"   python enrich_tier_u_v2.py --test")
            print()
    else:
        print()
        print("✅ All Tier U leads with good content have been processed!")
        print()
        print("💡 Next Steps:")
        print("   1. Export Tier A+B leads to Instantly.ai")
        print("   2. Run contact extraction on new A/B upgrades")
        print("   3. Review Tier C for any manual opportunities")
        print()

if __name__ == '__main__':
    check_status()
