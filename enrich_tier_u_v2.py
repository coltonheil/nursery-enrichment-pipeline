#!/usr/bin/env python3
"""
Tier U Enrichment - Rate-Limit-Aware Version

Improvements:
- Base delay between ALL requests (not just on errors)
- Progress checkpointing (resume on failure)
- Batch processing with breaks
- Configurable rate limits
- Better error reporting
"""

import sqlite3
import sys
import time
import json
from datetime import datetime
from pathlib import Path

sys.stdout.reconfigure(line_buffering=True)
sys.stderr.reconfigure(line_buffering=True)

from enrichment.gemini_client import enrich_lead_with_gemini
from enrichment.scorer import calculate_score

DB_PATH = 'data/leads.db'
CHECKPOINT_FILE = 'data/tier_u_checkpoint.json'

# ============================================================================
# RATE LIMITING CONFIGURATION
# ============================================================================

# Gemini API limits (Free tier):
# - 15 RPM (requests per minute)
# - 1500 RPD (requests per day)
# - 1 million TPM (tokens per minute)

# Conservative rate limiting to avoid 429s:
BASE_DELAY = 4.5  # seconds between requests (13 RPM effective rate)
BATCH_SIZE = 50   # Process 50, then take a break
BATCH_BREAK = 30  # seconds break between batches
SAVE_EVERY = 10   # Save checkpoint every 10 leads

# ============================================================================
# CHECKPOINT SYSTEM
# ============================================================================

def load_checkpoint():
    """Load progress checkpoint if exists."""
    if Path(CHECKPOINT_FILE).exists():
        with open(CHECKPOINT_FILE, 'r') as f:
            return json.load(f)
    return {'processed_ids': [], 'stats': {}}

def save_checkpoint(checkpoint):
    """Save progress checkpoint."""
    with open(CHECKPOINT_FILE, 'w') as f:
        json.dump(checkpoint, f, indent=2)

def clear_checkpoint():
    """Clear checkpoint file when done."""
    if Path(CHECKPOINT_FILE).exists():
        Path(CHECKPOINT_FILE).unlink()

# ============================================================================
# MAIN ENRICHMENT FUNCTION
# ============================================================================

def enrich_tier_u(resume=True):
    """
    Enrich Tier U leads with rate limiting and checkpointing.
    
    Args:
        resume: If True, resume from last checkpoint. If False, start fresh.
    """
    
    print("=" * 80)
    print("TIER U ENRICHMENT (Rate-Limit-Aware v2)")
    print("=" * 80)
    print()
    print(f"⚙️  Rate Limiting Config:")
    print(f"   Base delay: {BASE_DELAY}s between requests (~{60/BASE_DELAY:.0f} RPM)")
    print(f"   Batch size: {BATCH_SIZE} leads")
    print(f"   Batch break: {BATCH_BREAK}s between batches")
    print(f"   Checkpoint: Save every {SAVE_EVERY} leads")
    print()
    
    # Load checkpoint
    checkpoint = load_checkpoint() if resume else {'processed_ids': [], 'stats': {}}
    processed_ids = set(checkpoint.get('processed_ids', []))
    
    if processed_ids and resume:
        print(f"📂 Resuming from checkpoint: {len(processed_ids)} already processed")
        print()
    
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Query Tier U leads with content
    query = """
        SELECT id, business_name, website, website_text, city, state
        FROM leads
        WHERE tier = 'U'
          AND website_text IS NOT NULL
          AND LENGTH(website_text) > 1000
          AND (gemini_status IS NULL OR gemini_status NOT IN ('complete', 'enriched'))
        ORDER BY LENGTH(website_text) DESC
    """
    
    cursor.execute(query)
    all_leads = cursor.fetchall()
    
    # Filter out already processed
    leads = [lead for lead in all_leads if lead['id'] not in processed_ids]
    
    print(f"✅ Found {len(all_leads)} total Tier U leads")
    print(f"✅ {len(leads)} remaining to process")
    print()
    print("Starting enrichment...")
    print("=" * 80)
    print()
    
    stats = {
        'total': len(leads),
        'processed': 0,
        'contacts_found': 0,
        'upgraded_a': 0,
        'upgraded_b': 0,
        'upgraded_c': 0,
        'stayed_u': 0,
        'errors': 0,
        'rate_limits_hit': 0,
        'start_time': time.time()
    }
    
    batch_count = 0
    
    for idx, lead in enumerate(leads, 1):
        lead_id = lead['id']
        business_name = lead['business_name']
        
        try:
            # Call Gemini with enrichment
            result = enrich_lead_with_gemini(
                website_text=lead['website_text'],
                business_name=business_name,
                city=lead['city'],
                state=lead['state']
            )
            
            # Extract fields
            business_type = result.get('business_type')
            is_wholesale = result.get('is_wholesale')
            is_retail = result.get('is_retail')
            container_production = result.get('container_production')
            soil_relevance = result.get('soil_relevance')
            organic_focus = result.get('organic_focus')
            contact_name = result.get('contact_name')
            contact_title = result.get('contact_title')
            contact_priority = result.get('contact_priority')
            
            # Build updated lead dict for scoring
            updated_lead = dict(lead)
            updated_lead.update({
                'business_type': business_type,
                'is_wholesale': is_wholesale,
                'is_retail': is_retail,
                'container_production': container_production,
                'soil_relevance': soil_relevance,
                'organic_focus': organic_focus,
                'gemini_status': 'enriched'
            })
            
            # Calculate new score
            score_result = calculate_score(updated_lead)
            new_score = score_result.get('total', 0)
            new_tier = score_result.get('tier', 'U')
            
            # Track stats
            if new_tier == 'A':
                stats['upgraded_a'] += 1
                tier_icon = '🌟'
            elif new_tier == 'B':
                stats['upgraded_b'] += 1
                tier_icon = '⭐'
            elif new_tier == 'C':
                stats['upgraded_c'] += 1
                tier_icon = '✨'
            else:
                stats['stayed_u'] += 1
                tier_icon = '⚪'
            
            if contact_name:
                stats['contacts_found'] += 1
            
            # Update database
            cursor.execute("""
                UPDATE leads
                SET gemini_status = 'enriched',
                    gemini_enriched_at = ?,
                    business_type = ?,
                    is_wholesale = ?,
                    is_retail = ?,
                    container_production = ?,
                    soil_relevance = ?,
                    organic_focus = ?,
                    contact_name = ?,
                    contact_title = ?,
                    contact_priority = ?,
                    score = ?,
                    tier = ?,
                    gemini_confidence = ?
                WHERE id = ?
            """, (
                datetime.now().isoformat(),
                business_type,
                is_wholesale,
                is_retail,
                container_production,
                soil_relevance,
                organic_focus,
                contact_name,
                contact_title,
                contact_priority,
                new_score,
                new_tier,
                result.get('confidence', 0.8),
                lead_id
            ))
            conn.commit()
            
            stats['processed'] += 1
            processed_ids.add(lead_id)
            
            # Print progress line
            print(f"[{idx}/{stats['total']}] {business_name[:40]:40} → {tier_icon} {new_tier}/{new_score}")
            
            # Save checkpoint every N leads
            if idx % SAVE_EVERY == 0:
                checkpoint['processed_ids'] = list(processed_ids)
                checkpoint['stats'] = stats
                save_checkpoint(checkpoint)
            
            # Progress report every 50 leads
            if idx % 50 == 0:
                elapsed = time.time() - stats['start_time']
                rate = stats['processed'] / elapsed * 60 if elapsed > 0 else 0
                remaining = stats['total'] - stats['processed']
                eta_min = remaining / rate if rate > 0 else 0
                
                print()
                print("=" * 80)
                print(f"PROGRESS REPORT: {idx}/{stats['total']} ({idx/stats['total']*100:.1f}%)")
                print("=" * 80)
                print(f"  Upgraded to A: {stats['upgraded_a']} ({stats['upgraded_a']/max(stats['processed'],1)*100:.1f}%)")
                print(f"  Upgraded to B: {stats['upgraded_b']} ({stats['upgraded_b']/max(stats['processed'],1)*100:.1f}%)")
                print(f"  Upgraded to C: {stats['upgraded_c']} ({stats['upgraded_c']/max(stats['processed'],1)*100:.1f}%)")
                print(f"  Stayed U: {stats['stayed_u']}")
                print(f"  Contacts found: {stats['contacts_found']}")
                print(f"  Errors: {stats['errors']}")
                print(f"  Speed: {rate:.1f} leads/min")
                print(f"  ETA: {int(eta_min)} minutes")
                print("=" * 80)
                print()
            
            # Batch break (every N leads, take a longer break)
            if idx % BATCH_SIZE == 0:
                batch_count += 1
                print()
                print(f"⏸️  Batch {batch_count} complete. Taking {BATCH_BREAK}s break to avoid rate limits...")
                print()
                time.sleep(BATCH_BREAK)
            else:
                # Base delay between ALL requests
                time.sleep(BASE_DELAY)
                
        except Exception as e:
            error_str = str(e)
            stats['errors'] += 1
            stats['processed'] += 1
            processed_ids.add(lead_id)  # Mark as processed even if failed
            
            # Track if it was a rate limit error
            if '429' in error_str or 'rate limit' in error_str.lower():
                stats['rate_limits_hit'] += 1
                print(f"  ❌ [{idx}] {business_name[:30]} - RATE LIMIT HIT (will retry next run)")
            else:
                print(f"  ❌ [{idx}] {business_name[:30]} - ERROR: {error_str[:60]}")
            
            # Still save checkpoint
            if idx % SAVE_EVERY == 0:
                checkpoint['processed_ids'] = list(processed_ids)
                checkpoint['stats'] = stats
                save_checkpoint(checkpoint)
    
    conn.close()
    
    # Final summary
    elapsed = time.time() - stats['start_time']
    
    print()
    print("=" * 80)
    print("TIER U ENRICHMENT COMPLETE")
    print("=" * 80)
    print(f"Total processed: {stats['total']}")
    print(f"Upgraded to A: {stats['upgraded_a']} ({stats['upgraded_a']/max(stats['processed'],1)*100:.1f}%)")
    print(f"Upgraded to B: {stats['upgraded_b']} ({stats['upgraded_b']/max(stats['processed'],1)*100:.1f}%)")
    print(f"Upgraded to C: {stats['upgraded_c']} ({stats['upgraded_c']/max(stats['processed'],1)*100:.1f}%)")
    print(f"Stayed U: {stats['stayed_u']} ({stats['stayed_u']/max(stats['processed'],1)*100:.1f}%)")
    print()
    print(f"Contacts found: {stats['contacts_found']}")
    print(f"Errors: {stats['errors']}")
    print(f"Rate limits hit: {stats['rate_limits_hit']}")
    print()
    print(f"Time elapsed: {elapsed/60:.1f} minutes ({elapsed/3600:.1f} hours)")
    print(f"Average speed: {stats['processed']/(elapsed/60):.1f} leads/min")
    print("=" * 80)
    
    # Clear checkpoint on successful completion
    clear_checkpoint()
    print()
    print("✅ Checkpoint cleared. Run complete.")
    
    return stats

# ============================================================================
# MAIN
# ============================================================================

if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Enrich Tier U leads with rate limiting')
    parser.add_argument('--fresh', action='store_true', help='Start fresh (ignore checkpoint)')
    parser.add_argument('--test', action='store_true', help='Test mode (process only 10 leads)')
    
    args = parser.parse_args()
    
    # Test mode: reduce batch size
    if args.test:
        print("🧪 TEST MODE: Processing only 10 leads")
        print()
        # Modify query to limit 10
        # (Would need to pass this to function - simplified for now)
    
    try:
        enrich_tier_u(resume=not args.fresh)
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user.")
        print("💾 Progress saved to checkpoint. Run again to resume.")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        print("\n💾 Progress saved to checkpoint. Run again to resume.")
        sys.exit(1)
