#!/usr/bin/env python3
"""
Run enrichment pipeline on 5K leads and track Tier A/B results.

Usage:
    ./venv/bin/python run_5k_batch.py [--upload FILE.xlsx]

Options:
    --upload FILE   Upload new leads first, then process
    --resume        Resume existing pipeline (continue where left off)
    --fresh         Process next 5K pending leads from database

This script:
1. Uploads leads (if --upload provided) OR selects next 5K pending
2. Runs full pipeline: Places → Scraping → Gemini → Email → Scoring
3. Tracks progress and shows real-time stats
4. Reports Tier A/B distribution when complete
"""

import sys
import os
import time
import requests
import argparse
from pathlib import Path

# Configuration
API_BASE = "http://localhost:5000"
BATCH_SIZE = 5000

def check_server():
    """Check if Flask server is running."""
    try:
        resp = requests.get(f"{API_BASE}/", timeout=2)
        return resp.status_code == 200
    except:
        return False

def upload_file(filepath):
    """Upload Excel file to server."""
    print(f"Uploading {filepath}...")
    
    with open(filepath, 'rb') as f:
        files = {'file': (Path(filepath).name, f, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')}
        resp = requests.post(f"{API_BASE}/upload", files=files)
    
    if resp.status_code == 200:
        data = resp.json()
        print(f"✅ Uploaded {data.get('leads_imported', 0)} leads")
        return True
    else:
        print(f"❌ Upload failed: {resp.text}")
        return False

def start_pipeline(batch_size=5000):
    """Start the full enrichment pipeline."""
    print(f"\nStarting pipeline for {batch_size:,} leads...")
    
    resp = requests.post(f"{API_BASE}/start-full-pipeline", json={'batch_size': batch_size})
    
    if resp.status_code == 200:
        print("✅ Pipeline started")
        return True
    else:
        print(f"❌ Failed to start: {resp.text}")
        return False

def get_pipeline_status():
    """Get current pipeline status."""
    try:
        resp = requests.get(f"{API_BASE}/pipeline-status")
        if resp.status_code == 200:
            return resp.json()
        return None
    except:
        return None

def get_lead_stats():
    """Get current lead statistics."""
    try:
        resp = requests.get(f"{API_BASE}/api/stats")
        if resp.status_code == 200:
            return resp.json()
        return None
    except:
        return None

def monitor_pipeline():
    """Monitor pipeline progress and show real-time stats."""
    print("\n" + "="*70)
    print("MONITORING PIPELINE")
    print("="*70)
    
    last_progress = 0
    start_time = time.time()
    
    while True:
        status = get_pipeline_status()
        
        if not status:
            print("⚠️  Could not get status")
            time.sleep(5)
            continue
        
        if not status.get('running'):
            print("\n✅ Pipeline completed!")
            break
        
        progress = status.get('overall_progress', 0)
        current_step = status.get('current_step', 'unknown')
        message = status.get('status_message', '')
        
        # Show progress if changed
        if progress != last_progress:
            elapsed = time.time() - start_time
            eta_total = (elapsed / max(progress, 1)) * 100 - elapsed if progress > 0 else 0
            
            print(f"\r[{progress:3}%] {current_step:20} {message[:40]:40} ETA: {int(eta_total/60)}m", end='', flush=True)
            last_progress = progress
        
        time.sleep(2)
    
    elapsed = time.time() - start_time
    print(f"\nTotal time: {int(elapsed/60)}m {int(elapsed%60)}s")

def show_final_stats():
    """Show final tier distribution and email coverage."""
    print("\n" + "="*70)
    print("FINAL RESULTS")
    print("="*70)
    
    stats = get_lead_stats()
    
    if not stats:
        print("❌ Could not fetch stats")
        return
    
    total = stats.get('total_leads', 0)
    tier_a = stats.get('tier_a', 0)
    tier_b = stats.get('tier_b', 0)
    tier_c = stats.get('tier_c', 0)
    tier_u = stats.get('tier_u', 0)
    with_email = stats.get('with_email', 0)
    
    print(f"\nTotal Leads Processed: {total:,}")
    print(f"\nTier Distribution:")
    print(f"  Tier A: {tier_a:,} ({tier_a/max(total,1)*100:.1f}%)")
    print(f"  Tier B: {tier_b:,} ({tier_b/max(total,1)*100:.1f}%)")
    print(f"  Tier C: {tier_c:,} ({tier_c/max(total,1)*100:.1f}%)")
    print(f"  Tier U: {tier_u:,} ({tier_u/max(total,1)*100:.1f}%)")
    
    print(f"\nEmail Coverage:")
    print(f"  With Email: {with_email:,} ({with_email/max(total,1)*100:.1f}%)")
    
    # Calculate high-value leads
    high_value = tier_a + tier_b
    print(f"\nHigh-Value Leads (A+B): {high_value:,} ({high_value/max(total,1)*100:.1f}%)")
    
    if high_value > 0:
        # Estimate emails in A+B (assuming similar rate)
        estimated_ab_emails = int(with_email * (high_value / max(total, 1)))
        print(f"  Estimated A+B with Email: ~{estimated_ab_emails:,}")
    
    print("="*70)

def main():
    parser = argparse.ArgumentParser(description='Run 5K lead enrichment pipeline')
    parser.add_argument('--upload', type=str, help='Upload Excel file first')
    parser.add_argument('--resume', action='store_true', help='Resume existing pipeline')
    parser.add_argument('--fresh', action='store_true', help='Process next 5K pending leads')
    
    args = parser.parse_args()
    
    print("╔" + "="*68 + "╗")
    print("║" + " "*15 + "5K LEAD ENRICHMENT PIPELINE" + " "*26 + "║")
    print("╚" + "="*68 + "╝")
    print()
    
    # Check server
    print("Checking Flask server...")
    if not check_server():
        print("❌ Flask server not running!")
        print("   Start it with: cd projects/nursery-enrichment-pipeline && ./venv/bin/python app.py")
        return 1
    print("✅ Server is running")
    
    # Upload file if provided
    if args.upload:
        if not os.path.exists(args.upload):
            print(f"❌ File not found: {args.upload}")
            return 1
        
        if not upload_file(args.upload):
            return 1
    
    # Start pipeline unless resuming
    if not args.resume:
        if not start_pipeline(BATCH_SIZE):
            return 1
    else:
        print("Resuming existing pipeline...")
    
    # Monitor progress
    try:
        monitor_pipeline()
    except KeyboardInterrupt:
        print("\n\n⚠️  Monitoring stopped (pipeline still running in background)")
        print("   Check http://localhost:5000/pipeline-status for progress")
        return 0
    
    # Show final stats
    show_final_stats()
    
    print("\n✅ Pipeline complete!")
    print("   View results: http://localhost:5000/leads")
    
    return 0

if __name__ == '__main__':
    sys.exit(main())
