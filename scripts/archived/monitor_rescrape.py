#!/usr/bin/env python3
"""
Monitor re-scraping progress and report status.
"""

import time
import os

def monitor_rescrape():
    """Monitor the rescrape.log file and report progress."""
    
    log_file = 'rescrape.log'
    
    if not os.path.exists(log_file):
        print("❌ Log file not found")
        return
    
    print("📊 Monitoring re-scraping progress...")
    print("Will report updates every 2 minutes")
    print()
    
    last_size = 0
    last_report = ""
    
    while True:
        try:
            # Check if process is still running
            if os.path.exists('rescrape.pid'):
                with open('rescrape.pid') as f:
                    pid = int(f.read().strip())
                
                try:
                    os.kill(pid, 0)  # Check if process exists
                    is_running = True
                except OSError:
                    is_running = False
            else:
                is_running = False
            
            # Read log file
            with open(log_file, 'r') as f:
                content = f.read()
            
            # Look for progress reports
            lines = content.split('\n')
            progress_lines = [l for l in lines if 'Progress Report' in l or 'RE-SCRAPING COMPLETE' in l]
            
            if progress_lines:
                # Find the last progress report
                report_start = None
                for i in range(len(lines)-1, -1, -1):
                    if 'Progress Report' in lines[i] or 'RE-SCRAPING COMPLETE' in lines[i]:
                        report_start = i
                        break
                
                if report_start:
                    # Get the report block
                    report_lines = []
                    for i in range(report_start, min(report_start + 10, len(lines))):
                        if lines[i].strip():
                            report_lines.append(lines[i])
                        if 'ETA:' in lines[i] or 'Speed:' in lines[i]:
                            break
                    
                    current_report = '\n'.join(report_lines)
                    
                    if current_report != last_report:
                        print("\n" + "="*70)
                        print(current_report)
                        print("="*70)
                        last_report = current_report
            
            # Check if complete
            if not is_running:
                print("\n✅ Re-scraping process has completed!")
                print("Check rescrape.log for full details")
                break
            
            # Wait before next check
            time.sleep(120)  # Check every 2 minutes
            
        except KeyboardInterrupt:
            print("\n\n⚠️  Monitoring stopped (re-scraping still running)")
            break
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(10)

if __name__ == '__main__':
    monitor_rescrape()
