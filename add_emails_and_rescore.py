#!/usr/bin/env python3
"""
Add emails to existing leads and re-score them.

This is for leads that were already enriched but don't have email data yet.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

import sqlite3
from enrichment.email_hunter import hunt_email
from enrichment.scorer import calculate_score
import time
from datetime import datetime

def get_leads_needing_emails(limit=5000):
    """Get leads that need email hunting."""
    conn = sqlite3.connect('data/leads.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Get leads that:
    # - Have owner name
    # - Have website
    # - Don't have email yet (or have low confidence)
    # - Are in Tier A, B, or C (skip U)
    query = """
    SELECT 
        id, business_name, owner_name, website, tier, score,
        owner_email, email_confidence
    FROM leads
    WHERE owner_name IS NOT NULL 
        AND owner_name != ''
        AND website IS NOT NULL
        AND website != ''
        AND (owner_email IS NULL OR owner_email = '' OR email_confidence < 50)
        AND tier IN ('A', 'B', 'C')
    ORDER BY 
        CASE tier 
            WHEN 'A' THEN 1
            WHEN 'B' THEN 2
            WHEN 'C' THEN 3
        END,
        score DESC
    LIMIT ?
    """
    
    cursor.execute(query, (limit,))
    leads = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    return leads

def add_email_and_rescore(lead_id, owner_name, business_name, website):
    """Add email to a lead and re-score it."""
    try:
        # Hunt for email
        result = hunt_email(
            owner_name=owner_name,
            business_name=business_name,
            website=website,
            enable_web_search=True,
            verify_mx=True
        )
        
        # Update email fields
        conn = sqlite3.connect('data/leads.db')
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE leads
            SET owner_email = ?,
                email_confidence = ?,
                email_method = ?,
                generic_email = ?,
                contact_form_url = ?,
                email_found_at = ?
            WHERE id = ?
        ''', (
            result.email,
            result.confidence,
            result.method,
            result.generic_email,
            result.contact_form_url,
            datetime.now().isoformat(),
            lead_id
        ))
        
        # Get updated lead for rescoring
        cursor.execute("SELECT * FROM leads WHERE id = ?", (lead_id,))
        lead = dict(cursor.fetchone())
        
        # Re-calculate score
        score_data = calculate_score(lead)
        
        cursor.execute('''
            UPDATE leads
            SET score = ?,
                tier = ?,
                score_breakdown = ?,
                scored_at = ?
            WHERE id = ?
        ''', (
            score_data['total'],
            score_data['tier'],
            str(score_data['breakdown']),
            datetime.now().isoformat(),
            lead_id
        ))
        
        conn.commit()
        conn.close()
        
        return {
            'success': True,
            'email': result.email,
            'confidence': result.confidence,
            'method': result.method,
            'old_tier': lead['tier'],
            'new_tier': score_data['tier'],
            'old_score': lead['score'],
            'new_score': score_data['total']
        }
        
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }

def main():
    print("╔" + "="*68 + "╗")
    print("║" + " "*15 + "EMAIL HUNTER + RE-SCORING JOB" + " "*24 + "║")
    print("╚" + "="*68 + "╝")
    print()
    
    # Get leads
    print("Loading leads that need emails...")
    leads = get_leads_needing_emails(limit=5000)
    
    if not leads:
        print("✅ No leads need email hunting")
        return 0
    
    print(f"Found {len(leads):,} leads to process")
    print()
    
    # Breakdown by tier
    tier_counts = {}
    for lead in leads:
        tier = lead['tier']
        tier_counts[tier] = tier_counts.get(tier, 0) + 1
    
    print("Tier Breakdown:")
    for tier in ['A', 'B', 'C']:
        count = tier_counts.get(tier, 0)
        print(f"  Tier {tier}: {count:,} ({count/len(leads)*100:.1f}%)")
    print()
    
    print(f"Starting email hunting + re-scoring...")
    print(f"Will report every 100 leads")
    print()
    
    start_time = time.time()
    results = {
        'processed': 0,
        'emails_found': 0,
        'pattern': 0,
        'brave': 0,
        'generic': 0,
        'tier_changes': 0,
        'errors': 0
    }
    
    for i, lead in enumerate(leads, 1):
        result = add_email_and_rescore(
            lead['id'],
            lead['owner_name'],
            lead['business_name'],
            lead['website']
        )
        
        if result['success']:
            results['processed'] += 1
            
            if result['email']:
                results['emails_found'] += 1
                
                if 'pattern' in result['method']:
                    results['pattern'] += 1
                elif 'web_search' in result['method']:
                    results['brave'] += 1
                elif 'generic' in result['method']:
                    results['generic'] += 1
            
            if result['old_tier'] != result['new_tier']:
                results['tier_changes'] += 1
        else:
            results['errors'] += 1
        
        # Report every 100
        if i % 100 == 0:
            elapsed = time.time() - start_time
            speed = i / elapsed * 60  # leads per minute
            eta = (len(leads) - i) / speed if speed > 0 else 0
            
            print(f"[{i:,}/{len(leads):,}] Processed: {results['processed']:,} | "
                  f"Emails: {results['emails_found']:,} | "
                  f"Tier changes: {results['tier_changes']:,} | "
                  f"Speed: {speed:.1f}/min | "
                  f"ETA: {int(eta)}m")
    
    elapsed = time.time() - start_time
    
    print()
    print("="*70)
    print("FINAL RESULTS")
    print("="*70)
    print(f"Total processed: {results['processed']:,}")
    print(f"Emails found: {results['emails_found']:,} ({results['emails_found']/results['processed']*100:.1f}%)")
    print(f"  Pattern inference: {results['pattern']:,} ({results['pattern']/max(results['emails_found'],1)*100:.0f}%)")
    print(f"  Brave search: {results['brave']:,} ({results['brave']/max(results['emails_found'],1)*100:.0f}%)")
    print(f"  Generic fallback: {results['generic']:,} ({results['generic']/max(results['emails_found'],1)*100:.0f}%)")
    print(f"Tier changes: {results['tier_changes']:,}")
    print(f"Errors: {results['errors']:,}")
    print(f"Time: {int(elapsed/60)}m {int(elapsed%60)}s")
    print("="*70)
    
    return 0

if __name__ == '__main__':
    sys.exit(main())
