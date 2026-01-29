#!/usr/bin/env python3
"""
Progress Monitor
================
Real-time view of pipeline progress from checkpoints.
"""

import json
import glob
import os
import time
import sys
from datetime import datetime

CHECKPOINT_DIR = 'data'

def get_latest_checkpoint():
    """Get the most recent checkpoint file."""
    pattern = os.path.join(CHECKPOINT_DIR, 'checkpoint_*.json')
    checkpoints = sorted(glob.glob(pattern), reverse=True)
    
    if not checkpoints:
        return None
    
    # Skip 9999 (final checkpoint) if there are others
    if len(checkpoints) > 1 and checkpoints[0].endswith('9999.json'):
        return checkpoints[1]
    
    return checkpoints[0]

def format_time(seconds):
    """Format seconds into human-readable time."""
    if seconds < 60:
        return f"{seconds:.0f}s"
    elif seconds < 3600:
        return f"{seconds/60:.1f}m"
    else:
        return f"{seconds/3600:.1f}h"

def monitor_once():
    """Display current progress once."""
    checkpoint_file = get_latest_checkpoint()
    
    if not checkpoint_file:
        print("No checkpoints found. Pipeline may not have started yet.")
        return
    
    try:
        with open(checkpoint_file, 'r') as f:
            data = json.load(f)
    except Exception as e:
        print(f"Error reading checkpoint: {e}")
        return
    
    stats = data.get('stats', {})
    totals = data.get('totals', {})
    timestamp = data.get('timestamp', '')
    
    # Calculate time stats
    if timestamp:
        checkpoint_time = datetime.fromisoformat(timestamp)
        now = datetime.now()
        age = (now - checkpoint_time).total_seconds()
    else:
        age = 0
    
    # Display
    print("\n" + "=" * 80)
    print(f"PIPELINE PROGRESS - Checkpoint {data.get('checkpoint', '?')}")
    print("=" * 80)
    
    if age > 300:  # 5 minutes
        print(f"⚠️  Last update: {format_time(age)} ago (pipeline may have stopped)")
    else:
        print(f"✅ Last update: {format_time(age)} ago")
    
    print()
    print("This Session:")
    print(f"  Tier: {stats.get('current_tier', '?')}")
    print(f"  Processed: {stats.get('leads_processed', 0)}")
    print(f"  Scraped: {stats.get('leads_scraped', 0)} ({stats.get('scrape_success_rate', '0%')})")
    print(f"  With name: {stats.get('leads_with_name', 0)} ({stats.get('name_rate', '0%')})")
    print(f"  With email: {stats.get('leads_with_email', 0)} ({stats.get('email_rate', '0%')})")
    
    print()
    print("Overall Totals:")
    print(f"  Campaign-ready: {totals.get('campaign_ready', 0)}")
    print(f"  Has email: {totals.get('has_email', 0)}")
    print(f"  Has name: {totals.get('has_name', 0)}")
    
    print()
    print("Quality Metrics:")
    print(f"  Avg text: {stats.get('avg_text_chars', '0')} chars")
    print(f"  Scrape success: {stats.get('scrape_success_rate', '0%')}")
    print(f"  Extraction rate: {stats.get('name_rate', '0%')}")
    
    if stats.get('errors'):
        errors = stats['errors']
        print()
        print(f"Errors: {len(errors)}")
        if len(errors) > 0:
            print("  Recent:")
            for err in errors[-3:]:
                print(f"    - {err}")
    
    print("=" * 80)

def monitor_loop(interval=30):
    """Monitor progress continuously with updates every N seconds."""
    print(f"Monitoring pipeline progress (refreshing every {interval}s)...")
    print("Press Ctrl+C to stop")
    
    try:
        while True:
            os.system('clear' if os.name != 'nt' else 'cls')
            monitor_once()
            time.sleep(interval)
    except KeyboardInterrupt:
        print("\n\nStopped monitoring.")

def main():
    import argparse
    parser = argparse.ArgumentParser(description='Monitor pipeline progress')
    parser.add_argument('--once', action='store_true', help='Show progress once and exit')
    parser.add_argument('--interval', type=int, default=30, help='Refresh interval in seconds (default: 30)')
    args = parser.parse_args()
    
    if args.once:
        monitor_once()
    else:
        monitor_loop(args.interval)

if __name__ == '__main__':
    main()
