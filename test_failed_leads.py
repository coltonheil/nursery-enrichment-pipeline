#!/usr/bin/env python3
"""
Test email hunter optimizations on previously failed leads.

Loads leads that had no email found in the previous run and attempts
to find emails using the new 3-layer architecture.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

import sqlite3
from enrichment.email_hunter import hunt_email
from dotenv import load_dotenv
import time

# Load environment variables
load_dotenv()

def get_failed_leads(limit=50):
    """Get leads that failed to find email in previous run."""
    conn = sqlite3.connect('data/leads.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Get leads with no owner_email or very low confidence
    query = """
    SELECT 
        id,
        business_name,
        owner_name,
        website,
        city,
        state,
        owner_email,
        tier
    FROM leads
    WHERE 
        (owner_email IS NULL OR owner_email = '')
        AND owner_name IS NOT NULL
        AND owner_name != ''
        AND tier IN ('A', 'B')  -- Focus on high-value leads
    ORDER BY tier ASC  -- A first, then B
    LIMIT ?
    """
    
    cursor.execute(query, (limit,))
    leads = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    return leads


def test_on_failed_leads(leads, enable_brave=True, delay=2.0):
    """
    Test email hunter on failed leads.
    
    Args:
        leads: List of lead dicts
        enable_brave: Enable Brave search fallback
        delay: Delay between Brave searches (rate limiting)
    
    Returns:
        Results dict with stats
    """
    print("=" * 80)
    print(f"Testing Email Hunter v2 on {len(leads)} Previously Failed Leads")
    print("=" * 80)
    print()
    
    results = {
        'total': len(leads),
        'recovered': 0,
        'pattern_found': 0,
        'brave_found': 0,
        'generic_fallback': 0,
        'still_failed': 0,
        'examples': []
    }
    
    for i, lead in enumerate(leads, 1):
        lead_id = lead['id']
        owner_name = lead['owner_name']
        business_name = lead['business_name']
        website = lead['website']
        tier = lead['tier']
        
        print(f"[{i}/{len(leads)}] Testing: {owner_name} at {business_name}")
        print(f"  Website: {website or 'N/A'}")
        print(f"  Tier: {tier}")
        
        # Hunt for email
        result = hunt_email(
            owner_name=owner_name,
            business_name=business_name,
            website=website,
            enable_web_search=enable_brave,
            verify_mx=True
        )
        
        # Categorize result
        if result.email:
            if result.method == 'pattern_inference':
                results['pattern_found'] += 1
                results['recovered'] += 1
                status = "✅ PATTERN"
            elif result.method.startswith('web_search'):
                results['brave_found'] += 1
                results['recovered'] += 1
                status = "🔍 BRAVE"
            elif 'generic' in result.method:
                results['generic_fallback'] += 1
                status = "📧 GENERIC"
            else:
                status = "❓ UNKNOWN"
            
            print(f"  {status}: {result.email} (confidence: {result.confidence}%)")
            
            # Save example
            if len(results['examples']) < 10:
                results['examples'].append({
                    'lead_id': lead_id,
                    'owner_name': owner_name,
                    'business_name': business_name,
                    'email': result.email,
                    'method': result.method,
                    'confidence': result.confidence,
                    'tier': tier
                })
        else:
            results['still_failed'] += 1
            print(f"  ❌ NO EMAIL (error: {result.error})")
        
        # Show generic email if available
        if result.generic_email:
            print(f"  📋 Generic fallback: {result.generic_email}")
        
        print()
        
        # Rate limiting for Brave searches
        if enable_brave and i < len(leads):
            time.sleep(delay)
    
    return results


def print_summary(results):
    """Print test summary."""
    print("=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    print()
    
    total = results['total']
    recovered = results['recovered']
    pattern = results['pattern_found']
    brave = results['brave_found']
    generic = results['generic_fallback']
    failed = results['still_failed']
    
    print(f"Total leads tested:        {total}")
    print(f"Emails recovered:          {recovered} ({recovered/total*100:.1f}%)")
    print()
    print(f"  Pattern inference:       {pattern} ({pattern/total*100:.1f}%)")
    print(f"  Brave search:            {brave} ({brave/total*100:.1f}%)")
    print(f"  Generic fallback:        {generic} ({generic/total*100:.1f}%)")
    print(f"  Still failed:            {failed} ({failed/total*100:.1f}%)")
    print()
    
    if results['examples']:
        print("=" * 80)
        print("EXAMPLE RECOVERIES")
        print("=" * 80)
        print()
        
        for ex in results['examples']:
            print(f"Lead #{ex['lead_id']} (Tier {ex['tier']})")
            print(f"  {ex['owner_name']} at {ex['business_name']}")
            print(f"  Email: {ex['email']}")
            print(f"  Method: {ex['method']}")
            print(f"  Confidence: {ex['confidence']}%")
            print()
    
    # Calculate improvement
    print("=" * 80)
    print("IMPROVEMENT ANALYSIS")
    print("=" * 80)
    print()
    
    baseline_rate = 76.8  # From EMAIL_HUNTER_EVAL.md
    recovery_rate = (recovered / total * 100) if total > 0 else 0
    
    print(f"Baseline (before optimization): {baseline_rate}%")
    print(f"Recovery rate on failed leads:  {recovery_rate:.1f}%")
    print()
    
    if recovery_rate > 0:
        print(f"✅ SUCCESS: Recovered {recovery_rate:.1f}% of previously failed leads!")
        print()
        print("Projected impact on full dataset:")
        total_failed = 35  # From eval
        projected_recovery = int(total_failed * (recovery_rate / 100))
        print(f"  Failed leads in eval: {total_failed}")
        print(f"  Projected recovery: {projected_recovery} leads")
        print(f"  New baseline: {baseline_rate + (projected_recovery / 151 * 100):.1f}%")
    else:
        print("⚠️  No leads recovered - may need to adjust strategy")


def main():
    """Main test function."""
    print("\n")
    print("╔" + "=" * 78 + "╗")
    print("║" + " " * 15 + "EMAIL HUNTER v2 - FAILED LEADS TEST" + " " * 28 + "║")
    print("╚" + "=" * 78 + "╝")
    print("\n")
    
    # Check for database
    if not os.path.exists('data/leads.db'):
        print("❌ Error: Database not found at data/leads.db")
        print("   Make sure you're in the nursery-enrichment-pipeline directory")
        return 1
    
    # Get failed leads
    print("Loading previously failed leads from database...")
    leads = get_failed_leads(limit=50)
    
    if not leads:
        print("❌ No failed leads found in database")
        print("   (This might mean all leads have emails, which is great!)")
        return 1
    
    print(f"✅ Loaded {len(leads)} failed leads (Tier A/B only)")
    print()
    
    # Ask about Brave search
    brave_key = os.getenv('BRAVE_API_KEY')
    
    if brave_key:
        print(f"✅ Brave API key found: {brave_key[:10]}...")
        print("   Will use Brave search as fallback")
        enable_brave = True
    else:
        print("⚠️  No Brave API key found - will skip web search layer")
        print("   Set BRAVE_API_KEY in .env to enable (2000 free searches/month)")
        enable_brave = False
    
    print()
    # Skip input prompt if non-interactive
    if sys.stdin.isatty():
        input("Press ENTER to start testing...")
    else:
        print("Starting test in 2 seconds...")
        time.sleep(2)
    print()
    
    # Run test
    results = test_on_failed_leads(leads, enable_brave=enable_brave, delay=2.0)
    
    # Print summary
    print_summary(results)
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
