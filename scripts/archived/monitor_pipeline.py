#!/usr/bin/env python3
"""
Monitor 5K pipeline run and report to Slack every 500 leads.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

import time
import sqlite3
from datetime import datetime
import threading

# KPIs from RUN_KPIS.md
KPIS = {
    'tier_a_target': 2.1,  # percent
    'tier_b_target': 5.1,  # percent
    'high_value_target': 7.2,  # percent (A+B)
    'email_coverage_target': 85,  # percent for A+B
    'personal_email_target': 305,  # count for 5K leads
}

def get_lead_stats(conn):
    """Get current lead statistics."""
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM leads")
    total = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM leads WHERE tier = 'A'")
    tier_a = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM leads WHERE tier = 'B'")
    tier_b = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM leads WHERE tier = 'C'")
    tier_c = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM leads WHERE tier = 'U' OR tier IS NULL")
    tier_u = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM leads WHERE owner_email IS NOT NULL AND owner_email != ''")
    with_email = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM leads WHERE tier IN ('A', 'B')")
    high_value = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM leads WHERE tier IN ('A', 'B') AND owner_email IS NOT NULL AND owner_email != ''")
    high_value_with_email = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM leads WHERE email_method = 'pattern_inference'")
    pattern_emails = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM leads WHERE email_method LIKE 'web_search%'")
    brave_emails = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM leads WHERE email_method LIKE '%generic%'")
    generic_emails = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM leads WHERE enrichment_status = 'failed'")
    failed = cursor.fetchone()[0]
    
    return {
        'total': total,
        'tier_a': tier_a,
        'tier_b': tier_b,
        'tier_c': tier_c,
        'tier_u': tier_u,
        'high_value': high_value,
        'with_email': with_email,
        'high_value_with_email': high_value_with_email,
        'pattern_emails': pattern_emails,
        'brave_emails': brave_emails,
        'generic_emails': generic_emails,
        'failed': failed
    }

def format_checkpoint_report(stats, checkpoint, elapsed_mins):
    """Format checkpoint report for Slack."""
    total = stats['total']
    tier_a = stats['tier_a']
    tier_b = stats['tier_b']
    high_value = stats['high_value']
    with_email = stats['with_email']
    hv_with_email = stats['high_value_with_email']
    
    # Calculate percentages
    tier_a_pct = (tier_a / max(total, 1)) * 100
    tier_b_pct = (tier_b / max(total, 1)) * 100
    hv_pct = (high_value / max(total, 1)) * 100
    email_coverage = (hv_with_email / max(high_value, 1)) * 100 if high_value > 0 else 0
    
    # Status indicators
    def status_emoji(actual, target, tolerance=0.5):
        if actual >= target - tolerance:
            return "✅"
        elif actual >= target - tolerance * 2:
            return "⚠️"
        else:
            return "❌"
    
    tier_a_status = status_emoji(tier_a_pct, KPIS['tier_a_target'])
    tier_b_status = status_emoji(tier_b_pct, KPIS['tier_b_target'])
    hv_status = status_emoji(hv_pct, KPIS['high_value_target'])
    email_status = status_emoji(email_coverage, KPIS['email_coverage_target'], 5)
    
    # Estimate ETA
    if checkpoint < 5000 and elapsed_mins > 0:
        speed = checkpoint / elapsed_mins
        remaining = 5000 - checkpoint
        eta_mins = int(remaining / speed) if speed > 0 else 0
        eta_str = f"{eta_mins // 60}h {eta_mins % 60}m"
    else:
        eta_str = "Complete"
    
    report = f"""
{'═'*65}
CHECKPOINT: {checkpoint:,} LEADS PROCESSED
Time: {elapsed_mins // 60}h {elapsed_mins % 60}m | ETA: {eta_str}
{'═'*65}

TIER DISTRIBUTION:
  Tier A:    {tier_a:3} ({tier_a_pct:.1f}%) | Target: {KPIS['tier_a_target']}% {tier_a_status}
  Tier B:    {tier_b:3} ({tier_b_pct:.1f}%) | Target: {KPIS['tier_b_target']}% {tier_b_status}
  Tier C:    {stats['tier_c']:3} ({stats['tier_c']/max(total,1)*100:.1f}%)
  Tier U:    {stats['tier_u']:4} ({stats['tier_u']/max(total,1)*100:.1f}%)
  High-Value: {high_value:3} ({hv_pct:.1f}%) | Target: {KPIS['high_value_target']}% {hv_status}

EMAIL COVERAGE:
  With Personal Email: {hv_with_email}/{high_value} A+B ({email_coverage:.1f}%) | Target: {KPIS['email_coverage_target']}% {email_status}
  Pattern Inference: {stats['pattern_emails']} ({stats['pattern_emails']/max(with_email,1)*100:.0f}% of found)
  Brave Search: {stats['brave_emails']} ({stats['brave_emails']/max(with_email,1)*100:.0f}% of found)
  Generic Fallback: {stats['generic_emails']}
  Total with Email: {with_email:,}

PIPELINE HEALTH:
  Enrichment Success: {total - stats['failed']}/{total} ({(total-stats['failed'])/max(total,1)*100:.1f}%)
  Failed Leads: {stats['failed']} ({stats['failed']/max(total,1)*100:.1f}%)
  Processing Speed: {checkpoint / max(elapsed_mins, 1):.1f} leads/min

"""
    
    # Overall status
    statuses = [tier_a_status, tier_b_status, hv_status, email_status]
    if all(s == "✅" for s in statuses):
        report += "STATUS: ✅ ALL KPIS ON TRACK\n"
    elif any(s == "❌" for s in statuses):
        report += "STATUS: ❌ SOME KPIS BELOW TARGET\n"
    else:
        report += "STATUS: ⚠️ MONITORING REQUIRED\n"
    
    report += "═" * 65
    
    return report

def monitor_pipeline(batch_size=5000):
    """Monitor pipeline and report every 500 leads."""
    print("Starting pipeline monitor...")
    print(f"Target: {batch_size:,} leads")
    print(f"Reporting every 500 leads")
    print()
    
    conn = sqlite3.connect('data/leads.db')
    
    start_time = time.time()
    last_checkpoint = 0
    checkpoints = [500, 1000, 1500, 2000, 2500, 3000, 3500, 4000, 4500, 5000]
    
    # Get initial count
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM leads WHERE tier IS NOT NULL")
    initial_count = cursor.fetchone()[0]
    
    print(f"Initial lead count: {initial_count:,}")
    print(f"Monitoring for new leads...")
    print()
    
    try:
        while True:
            cursor.execute("SELECT COUNT(*) FROM leads WHERE tier IS NOT NULL")
            current_count = cursor.fetchone()[0]
            processed = current_count - initial_count
            
            # Check if we've hit a checkpoint
            next_checkpoint = min([c for c in checkpoints if c > last_checkpoint], default=None)
            
            if next_checkpoint and processed >= next_checkpoint:
                elapsed_mins = int((time.time() - start_time) / 60)
                stats = get_lead_stats(conn)
                report = format_checkpoint_report(stats, processed, elapsed_mins)
                
                print(report)
                print()
                
                last_checkpoint = next_checkpoint
                
                # Stop if we've processed 5000
                if processed >= 5000:
                    break
            
            # Wait before checking again
            time.sleep(30)
    
    except KeyboardInterrupt:
        print("\n⚠️  Monitoring stopped")
    finally:
        conn.close()
    
    print("\n✅ Monitoring complete")

if __name__ == '__main__':
    monitor_pipeline()
