#!/usr/bin/env python3
"""
Form Campaign Runner - Scheduler for Contact Form Submissions

Command-line interface for running the form submission campaign:
- Daily limit enforcement (30-40 submissions/day)
- Random intervals (30-90 min between submissions)
- Business hours only (8am-6pm CT)
- Resume capability (tracks progress)
- Dry-run mode for testing
"""

import asyncio
import argparse
import sqlite3
import random
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional
import logging

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.form_submitter import FormSubmitter, Lead, SubmissionResult, get_pending_leads

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(Path(__file__).parent.parent / 'logs' / 'form_campaign.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class CampaignScheduler:
    """
    Scheduler for contact form submission campaign.
    
    Enforces:
    - Daily submission limits
    - Business hours only
    - Random intervals between submissions
    - Geographic distribution
    """
    
    # Configuration
    DB_PATH = Path(__file__).parent.parent / 'data' / 'leads.db'
    
    # Rate limiting
    DEFAULT_DAILY_MIN = 30
    DEFAULT_DAILY_MAX = 40
    MIN_INTERVAL_MINUTES = 30
    MAX_INTERVAL_MINUTES = 90
    
    # Business hours (Central Time)
    BUSINESS_START_HOUR = 8   # 8 AM
    BUSINESS_END_HOUR = 18    # 6 PM
    WORK_DAYS = [0, 1, 2, 3, 4]  # Monday-Friday
    
    def __init__(self, daily_min: int = None, daily_max: int = None, 
                 dry_run: bool = False, headless: bool = False, force: bool = False, no_delay: bool = False):
        """
        Initialize campaign scheduler.
        
        Args:
            daily_min: Minimum submissions per day
            daily_max: Maximum submissions per day  
            dry_run: Fill forms but don't submit
            headless: Run browser in headless mode
            force: Bypass business hours check (for testing)
            no_delay: Skip delays between submissions (for testing)
        """
        self.daily_min = daily_min or self.DEFAULT_DAILY_MIN
        self.daily_max = daily_max or self.DEFAULT_DAILY_MAX
        self.dry_run = dry_run
        self.headless = headless
        self.force = force
        self.no_delay = no_delay
        
        self.submitter = FormSubmitter(headless=headless)
        self.submitted_today = 0
        self.daily_limit = random.randint(self.daily_min, self.daily_max)
        self.last_submission_time: Optional[datetime] = None
        
        # Ensure logs directory exists
        (Path(__file__).parent.parent / 'logs').mkdir(exist_ok=True)
    
    def is_business_hours(self, dt: datetime = None) -> bool:
        """Check if current time is within business hours."""
        # Force flag bypasses business hours check
        if self.force:
            return True
            
        if dt is None:
            dt = datetime.now()
        
        # Check day of week
        if dt.weekday() not in self.WORK_DAYS:
            return False
        
        # Check hour
        return self.BUSINESS_START_HOUR <= dt.hour < self.BUSINESS_END_HOUR
    
    def get_next_business_hour(self) -> datetime:
        """Get the next time business hours start."""
        now = datetime.now()
        
        # If before business hours today
        if now.weekday() in self.WORK_DAYS and now.hour < self.BUSINESS_START_HOUR:
            return now.replace(hour=self.BUSINESS_START_HOUR, minute=0, second=0)
        
        # Find next work day
        next_day = now + timedelta(days=1)
        while next_day.weekday() not in self.WORK_DAYS:
            next_day += timedelta(days=1)
        
        return next_day.replace(hour=self.BUSINESS_START_HOUR, minute=0, second=0)
    
    def get_next_submission_delay(self) -> int:
        """Get delay in seconds until next submission."""
        # Base interval with jitter
        base_minutes = random.randint(self.MIN_INTERVAL_MINUTES, self.MAX_INTERVAL_MINUTES)
        jitter = random.randint(-10, 10)
        interval_minutes = max(20, base_minutes + jitter)  # Never less than 20 min
        
        return interval_minutes * 60
    
    def should_continue_today(self) -> bool:
        """Check if we should continue submitting today."""
        if self.submitted_today >= self.daily_limit:
            return False
        if not self.is_business_hours():
            return False
        return True
    
    def reset_daily_counters(self):
        """Reset counters for a new day."""
        self.submitted_today = 0
        self.daily_limit = random.randint(self.daily_min, self.daily_max)
        logger.info(f"New day started. Daily limit: {self.daily_limit}")
    
    def get_submissions_today(self) -> int:
        """Get count of submissions made today from database."""
        conn = sqlite3.connect(self.DB_PATH)
        cursor = conn.cursor()
        
        today = datetime.now().strftime('%Y-%m-%d')
        cursor.execute('''
            SELECT COUNT(*) FROM leads
            WHERE form_submission_status = 'submitted'
              AND date(form_submitted_at) = ?
        ''', (today,))
        
        count = cursor.fetchone()[0]
        conn.close()
        return count
    
    def get_campaign_stats(self) -> dict:
        """Get overall campaign statistics."""
        conn = sqlite3.connect(self.DB_PATH)
        cursor = conn.cursor()
        
        # Total leads with forms
        cursor.execute('''
            SELECT COUNT(*) FROM leads 
            WHERE has_contact_form = 1 
              AND contact_form_url IS NOT NULL
              AND (owner_email IS NULL OR owner_email = '')
              AND (contact_email IS NULL OR contact_email = '')
        ''')
        total = cursor.fetchone()[0]
        
        # Submitted
        cursor.execute('''
            SELECT COUNT(*) FROM leads 
            WHERE form_submission_status = 'submitted'
        ''')
        submitted = cursor.fetchone()[0]
        
        # Failed
        cursor.execute('''
            SELECT COUNT(*) FROM leads 
            WHERE form_submission_status = 'failed'
        ''')
        failed = cursor.fetchone()[0]
        
        # Manual review
        cursor.execute('''
            SELECT COUNT(*) FROM leads 
            WHERE form_submission_status = 'manual_review'
        ''')
        manual = cursor.fetchone()[0]
        
        # Pending
        cursor.execute('''
            SELECT COUNT(*) FROM leads 
            WHERE has_contact_form = 1 
              AND contact_form_url IS NOT NULL
              AND (form_submission_status IS NULL OR form_submission_status = 'pending')
              AND (owner_email IS NULL OR owner_email = '')
              AND (contact_email IS NULL OR contact_email = '')
        ''')
        pending = cursor.fetchone()[0]
        
        # By tier
        cursor.execute('''
            SELECT tier, 
                   SUM(CASE WHEN form_submission_status = 'submitted' THEN 1 ELSE 0 END) as submitted,
                   SUM(CASE WHEN form_submission_status IS NULL OR form_submission_status = 'pending' THEN 1 ELSE 0 END) as pending
            FROM leads
            WHERE has_contact_form = 1 
              AND contact_form_url IS NOT NULL
              AND (owner_email IS NULL OR owner_email = '')
            GROUP BY tier
        ''')
        by_tier = {row[0]: {'submitted': row[1], 'pending': row[2]} for row in cursor.fetchall()}
        
        conn.close()
        
        return {
            'total': total,
            'submitted': submitted,
            'failed': failed,
            'manual_review': manual,
            'pending': pending,
            'by_tier': by_tier,
            'today': self.get_submissions_today()
        }
    
    def print_status(self):
        """Print current campaign status."""
        stats = self.get_campaign_stats()
        
        print("\n" + "=" * 60)
        print("       CONTACT FORM CAMPAIGN STATUS")
        print("=" * 60)
        print(f"\n📊 OVERALL PROGRESS")
        print(f"   Total leads with forms: {stats['total']}")
        print(f"   ✅ Submitted: {stats['submitted']} ({stats['submitted']/max(1,stats['total'])*100:.1f}%)")
        print(f"   ❌ Failed: {stats['failed']}")
        print(f"   👀 Manual review: {stats['manual_review']}")
        print(f"   ⏳ Pending: {stats['pending']}")
        
        print(f"\n📅 TODAY")
        print(f"   Submitted: {stats['today']}")
        print(f"   Limit: {self.daily_limit}")
        print(f"   Business hours: {'YES ✅' if self.is_business_hours() else 'NO ❌'}")
        
        print(f"\n📈 BY TIER")
        for tier, data in sorted(stats['by_tier'].items()):
            print(f"   Tier {tier}: {data['submitted']} submitted, {data['pending']} pending")
        
        print("=" * 60 + "\n")
    
    async def run_single(self, lead_id: int = None) -> Optional[SubmissionResult]:
        """
        Run a single submission.
        
        Args:
            lead_id: Specific lead ID, or None to get next pending
            
        Returns:
            SubmissionResult or None if no leads
        """
        if lead_id:
            # Get specific lead
            conn = sqlite3.connect(self.DB_PATH)
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, business_name, city, state, contact_form_url, tier, 
                       is_wholesale, crops_grown
                FROM leads WHERE id = ?
            ''', (lead_id,))
            row = cursor.fetchone()
            conn.close()
            
            if not row:
                logger.error(f"Lead {lead_id} not found")
                return None
            
            lead = Lead(
                id=row[0], business_name=row[1], city=row[2] or '',
                state=row[3] or '', contact_form_url=row[4], tier=row[5] or 'U',
                is_wholesale=bool(row[6]), crops_grown=row[7]
            )
        else:
            # Get next pending lead
            leads = get_pending_leads(str(self.DB_PATH), limit=1)
            if not leads:
                logger.info("No pending leads found")
                return None
            lead = leads[0]
        
        # Submit
        result = await self.submitter.submit_form(lead, dry_run=self.dry_run)
        
        # Update database (unless dry run)
        if not self.dry_run or self.dry_run:  # Always log even dry runs
            self.submitter.update_database(result)
        
        return result
    
    async def run_batch(self, count: int = None) -> List[SubmissionResult]:
        """
        Run a batch of submissions with rate limiting.
        
        Args:
            count: Number to submit, or None for daily limit
            
        Returns:
            List of SubmissionResults
        """
        results = []
        target = count or (self.daily_limit - self.submitted_today)
        
        logger.info(f"Starting batch of {target} submissions")
        
        # Get leads upfront
        leads = get_pending_leads(str(self.DB_PATH), limit=target)
        
        if not leads:
            logger.info("No pending leads to process")
            return results
        
        logger.info(f"Found {len(leads)} pending leads")
        
        for i, lead in enumerate(leads):
            # Check if we should continue
            if not self.should_continue_today():
                logger.info("Daily limit reached or outside business hours")
                break
            
            # Submit
            logger.info(f"\n[{i+1}/{len(leads)}] Processing: {lead.business_name}")
            result = await self.submitter.submit_form(lead, dry_run=self.dry_run)
            results.append(result)
            
            # Update database
            self.submitter.update_database(result)
            
            # Track progress
            if result.success:
                self.submitted_today += 1
            
            # Log result
            status = "✅ SUCCESS" if result.success else "❌ FAILED"
            logger.info(f"{status} - {lead.business_name} [{result.tracking_id}]")
            if result.error:
                logger.info(f"   Error: {result.error}")
            
            # Wait before next submission (unless last one or no_delay mode)
            if i < len(leads) - 1 and self.should_continue_today() and not self.no_delay:
                delay = self.get_next_submission_delay()
                next_time = datetime.now() + timedelta(seconds=delay)
                logger.info(f"⏱️  Next submission at {next_time.strftime('%H:%M:%S')} ({delay//60} min)")
                await asyncio.sleep(delay)
            elif i < len(leads) - 1 and self.no_delay:
                logger.info("⚡ No-delay mode: proceeding immediately")
        
        return results
    
    async def run_continuous(self):
        """
        Run continuously, respecting business hours and daily limits.
        
        Will pause overnight and on weekends, resuming automatically.
        """
        logger.info("Starting continuous campaign mode")
        self.print_status()
        
        while True:
            # Check if we have pending leads
            stats = self.get_campaign_stats()
            if stats['pending'] == 0:
                logger.info("🎉 All leads processed! Campaign complete.")
                break
            
            # Check business hours
            if not self.is_business_hours():
                next_start = self.get_next_business_hour()
                wait_seconds = (next_start - datetime.now()).total_seconds()
                logger.info(f"Outside business hours. Resuming at {next_start.strftime('%Y-%m-%d %H:%M')}")
                await asyncio.sleep(min(wait_seconds, 3600))  # Check every hour max
                continue
            
            # Check daily limit
            today_count = self.get_submissions_today()
            if today_count >= self.daily_limit:
                logger.info(f"Daily limit reached ({today_count}/{self.daily_limit}). Resuming tomorrow.")
                # Wait until tomorrow
                tomorrow = (datetime.now() + timedelta(days=1)).replace(
                    hour=self.BUSINESS_START_HOUR, minute=0, second=0
                )
                while tomorrow.weekday() not in self.WORK_DAYS:
                    tomorrow += timedelta(days=1)
                
                wait_seconds = (tomorrow - datetime.now()).total_seconds()
                await asyncio.sleep(min(wait_seconds, 3600))
                self.reset_daily_counters()
                continue
            
            # Run a batch
            remaining = self.daily_limit - today_count
            batch_size = min(remaining, 5)  # Process up to 5 at a time
            
            await self.run_batch(count=batch_size)
            
            # Update status
            self.print_status()


def main():
    parser = argparse.ArgumentParser(
        description='Run contact form submission campaign',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  # Show current status
  python run_form_campaign.py --status
  
  # Dry run on a single lead (test mode)
  python run_form_campaign.py --single --dry-run
  
  # Submit to specific lead
  python run_form_campaign.py --lead-id 123
  
  # Run batch of 5 submissions
  python run_form_campaign.py --batch 5
  
  # Run continuous campaign (with rate limiting)
  python run_form_campaign.py --continuous
        '''
    )
    
    parser.add_argument('--status', action='store_true',
                       help='Show campaign status and exit')
    parser.add_argument('--single', action='store_true',
                       help='Process single lead')
    parser.add_argument('--lead-id', type=int,
                       help='Specific lead ID to process')
    parser.add_argument('--batch', type=int, metavar='N',
                       help='Process N leads')
    parser.add_argument('--continuous', action='store_true',
                       help='Run continuously with rate limiting')
    parser.add_argument('--dry-run', action='store_true',
                       help='Fill forms but do not submit')
    parser.add_argument('--headless', action='store_true',
                       help='Run browser in headless mode')
    parser.add_argument('--daily-min', type=int, default=30,
                       help='Minimum daily submissions (default: 30)')
    parser.add_argument('--daily-max', type=int, default=40,
                       help='Maximum daily submissions (default: 40)')
    parser.add_argument('--force', action='store_true',
                       help='Bypass business hours check (for testing)')
    parser.add_argument('--no-delay', action='store_true',
                       help='Skip delays between submissions (for testing)')
    
    args = parser.parse_args()
    
    # Create scheduler
    scheduler = CampaignScheduler(
        daily_min=args.daily_min,
        daily_max=args.daily_max,
        dry_run=args.dry_run,
        headless=args.headless,
        force=args.force,
        no_delay=args.no_delay
    )
    
    # Handle commands
    if args.status:
        scheduler.print_status()
        return
    
    if args.single or args.lead_id:
        result = asyncio.run(scheduler.run_single(args.lead_id))
        if result:
            print(f"\nResult: {'SUCCESS' if result.success else 'FAILED'}")
            print(f"Tracking ID: {result.tracking_id}")
            if result.error:
                print(f"Error: {result.error}")
        return
    
    if args.batch:
        results = asyncio.run(scheduler.run_batch(args.batch))
        print(f"\nBatch complete: {len([r for r in results if r.success])}/{len(results)} successful")
        return
    
    if args.continuous:
        asyncio.run(scheduler.run_continuous())
        return
    
    # Default: show help
    parser.print_help()


if __name__ == "__main__":
    main()
