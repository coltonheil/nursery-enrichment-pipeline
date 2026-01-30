#!/usr/bin/env python3
"""
Manual Review Queue for Contact Form Automation

CLI tool to manage forms that failed auto-detection:
- List forms needing manual review
- Provide field mappings manually
- Retry submissions with custom mappings
- Skip or mark leads as unprocessable
"""

import asyncio
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List
import json

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))


class ManualQueueManager:
    """
    Manages the manual review queue for contact form submissions.
    """
    
    DB_PATH = Path(__file__).parent.parent / 'data' / 'leads.db'
    MAPPINGS_PATH = Path(__file__).parent.parent / 'data' / 'form_mappings.json'
    
    def __init__(self):
        self.mappings = self._load_mappings()
    
    def _load_mappings(self) -> Dict:
        """Load saved field mappings."""
        if self.MAPPINGS_PATH.exists():
            with open(self.MAPPINGS_PATH, 'r') as f:
                return json.load(f)
        return {}
    
    def _save_mappings(self):
        """Save field mappings."""
        with open(self.MAPPINGS_PATH, 'w') as f:
            json.dump(self.mappings, f, indent=2)
    
    def get_queue(self) -> List[Dict]:
        """Get all leads in manual review queue."""
        conn = sqlite3.connect(self.DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, business_name, city, state, contact_form_url, tier,
                   form_error, form_tracking_id
            FROM leads
            WHERE form_submission_status = 'manual_review'
            ORDER BY 
                CASE tier WHEN 'A' THEN 1 WHEN 'B' THEN 2 ELSE 3 END,
                id
        ''')
        
        leads = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return leads
    
    def get_failed(self) -> List[Dict]:
        """Get all leads that failed submission."""
        conn = sqlite3.connect(self.DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, business_name, city, state, contact_form_url, tier,
                   form_error, form_tracking_id
            FROM leads
            WHERE form_submission_status = 'failed'
            ORDER BY id
        ''')
        
        leads = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return leads
    
    def print_queue(self, queue_type: str = 'manual'):
        """Print the manual review queue."""
        if queue_type == 'manual':
            leads = self.get_queue()
            title = "MANUAL REVIEW QUEUE"
        else:
            leads = self.get_failed()
            title = "FAILED SUBMISSIONS"
        
        print("\n" + "=" * 70)
        print(f"       {title}")
        print("=" * 70)
        
        if not leads:
            print("\n  ✨ Queue is empty!\n")
            return
        
        print(f"\n  Found {len(leads)} leads:\n")
        
        for i, lead in enumerate(leads, 1):
            print(f"  [{i}] ID: {lead['id']} | Tier {lead['tier']}")
            print(f"      {lead['business_name']}")
            print(f"      {lead['city']}, {lead['state']}")
            print(f"      URL: {lead['contact_form_url'][:60]}...")
            if lead['form_error']:
                print(f"      Error: {lead['form_error'][:60]}...")
            print()
        
        print("=" * 70)
    
    def update_status(self, lead_id: int, status: str, error: str = None):
        """Update a lead's submission status."""
        conn = sqlite3.connect(self.DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE leads 
            SET form_submission_status = ?,
                form_error = ?
            WHERE id = ?
        ''', (status, error, lead_id))
        
        conn.commit()
        conn.close()
        print(f"✅ Lead {lead_id} status updated to: {status}")
    
    def skip_lead(self, lead_id: int, reason: str = "Manually skipped"):
        """Mark a lead as skipped (won't be processed)."""
        self.update_status(lead_id, 'skipped', reason)
    
    def reset_lead(self, lead_id: int):
        """Reset a lead to pending status for retry."""
        self.update_status(lead_id, 'pending', None)
    
    def save_field_mapping(self, lead_id: int, mapping: Dict[str, str]):
        """
        Save a custom field mapping for a lead.
        
        Args:
            lead_id: Lead ID
            mapping: Dict of field_type -> selector
                    e.g., {'email': '#email-field', 'message': 'textarea.contact-msg'}
        """
        self.mappings[str(lead_id)] = {
            'mapping': mapping,
            'created_at': datetime.now().isoformat()
        }
        self._save_mappings()
        print(f"✅ Field mapping saved for lead {lead_id}")
    
    def get_field_mapping(self, lead_id: int) -> Optional[Dict[str, str]]:
        """Get saved field mapping for a lead."""
        entry = self.mappings.get(str(lead_id))
        if entry:
            return entry.get('mapping')
        return None
    
    def interactive_mapping(self, lead_id: int):
        """Interactively create field mapping for a lead."""
        print(f"\n📝 Creating field mapping for lead {lead_id}")
        print("Enter CSS selectors for each field (or press Enter to skip):\n")
        
        mapping = {}
        fields = [
            ('name', 'Name field'),
            ('email', 'Email field'),
            ('phone', 'Phone field (optional)'),
            ('company', 'Company field (optional)'),
            ('subject', 'Subject field (optional)'),
            ('message', 'Message field'),
            ('submit', 'Submit button'),
        ]
        
        for field_key, field_name in fields:
            selector = input(f"  {field_name}: ").strip()
            if selector:
                mapping[field_key] = selector
        
        if mapping:
            self.save_field_mapping(lead_id, mapping)
            print("\n✅ Mapping saved! Use --retry to submit with these mappings.")
        else:
            print("\n❌ No mappings entered.")
    
    async def retry_with_mapping(self, lead_id: int, dry_run: bool = False):
        """Retry submission using saved field mapping."""
        from scripts.form_submitter import FormSubmitter, Lead
        from playwright.async_api import async_playwright
        from playwright_stealth import Stealth
        
        mapping = self.get_field_mapping(lead_id)
        if not mapping:
            print(f"❌ No field mapping found for lead {lead_id}")
            print("   Use --map to create one first")
            return
        
        # Get lead details
        conn = sqlite3.connect(self.DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, business_name, city, state, contact_form_url, tier,
                   is_wholesale, crops_grown
            FROM leads WHERE id = ?
        ''', (lead_id,))
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            print(f"❌ Lead {lead_id} not found")
            return
        
        lead = Lead(
            id=row['id'],
            business_name=row['business_name'],
            city=row['city'] or '',
            state=row['state'] or '',
            contact_form_url=row['contact_form_url'],
            tier=row['tier'] or 'U',
            is_wholesale=bool(row['is_wholesale']),
            crops_grown=row['crops_grown']
        )
        
        print(f"\n🔄 Retrying submission for: {lead.business_name}")
        print(f"   URL: {lead.contact_form_url}")
        print(f"   Using custom mapping: {mapping}")
        
        submitter = FormSubmitter(headless=False)
        
        # Generate message
        tracking_id = submitter._generate_tracking_id(lead)
        template_variant = submitter._select_template(lead)
        message = submitter._personalize_message(template_variant, lead, tracking_id)
        
        async with async_playwright() as playwright:
            browser, context = await submitter._create_browser_context(playwright)
            page = await context.new_page()
            
            try:
                await page.goto(lead.contact_form_url, wait_until='domcontentloaded', timeout=30000)
                await asyncio.sleep(2)
                
                # Fill using custom mapping
                if 'name' in mapping:
                    await page.fill(mapping['name'], submitter.SENDER_NAME)
                    await asyncio.sleep(0.5)
                
                if 'email' in mapping:
                    await page.fill(mapping['email'], submitter.REPLY_EMAIL)
                    await asyncio.sleep(0.5)
                
                if 'phone' in mapping and submitter.SENDER_PHONE:
                    await page.fill(mapping['phone'], submitter.SENDER_PHONE)
                    await asyncio.sleep(0.5)
                
                if 'company' in mapping:
                    await page.fill(mapping['company'], submitter.SENDER_COMPANY)
                    await asyncio.sleep(0.5)
                
                if 'message' in mapping:
                    await page.fill(mapping['message'], message)
                    await asyncio.sleep(0.5)
                
                # Take screenshot
                screenshot_path = await submitter._take_screenshot(page, lead, 'manual_prefill')
                print(f"   Screenshot: {screenshot_path}")
                
                if dry_run:
                    print("\n   DRY RUN - Form filled but not submitted")
                    input("   Press Enter to close browser...")
                else:
                    # Submit
                    if 'submit' in mapping:
                        await page.click(mapping['submit'])
                    else:
                        await page.keyboard.press('Enter')
                    
                    await asyncio.sleep(3)
                    screenshot_path = await submitter._take_screenshot(page, lead, 'manual_submit')
                    
                    # Update database
                    self.update_status(lead_id, 'submitted')
                    
                    conn = sqlite3.connect(self.DB_PATH)
                    cursor = conn.cursor()
                    cursor.execute('''
                        UPDATE leads 
                        SET form_submitted_at = ?,
                            form_tracking_id = ?,
                            form_template_variant = ?
                        WHERE id = ?
                    ''', (datetime.now().isoformat(), tracking_id, template_variant, lead_id))
                    conn.commit()
                    conn.close()
                    
                    print(f"\n   ✅ Submitted! Tracking ID: {tracking_id}")
                
            except Exception as e:
                print(f"\n   ❌ Error: {e}")
            finally:
                await browser.close()
    
    def bulk_reset(self, status: str = 'failed'):
        """Reset all leads with given status back to pending."""
        conn = sqlite3.connect(self.DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE leads 
            SET form_submission_status = 'pending',
                form_error = NULL
            WHERE form_submission_status = ?
        ''', (status,))
        
        count = cursor.rowcount
        conn.commit()
        conn.close()
        
        print(f"✅ Reset {count} leads from '{status}' to 'pending'")


def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Manage manual review queue for contact forms',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  # List manual review queue
  python manual_queue.py --list
  
  # List failed submissions
  python manual_queue.py --list-failed
  
  # Skip a lead
  python manual_queue.py --skip 123 --reason "No contact form found"
  
  # Reset a lead to pending
  python manual_queue.py --reset 123
  
  # Create field mapping interactively
  python manual_queue.py --map 123
  
  # Retry with saved mapping
  python manual_queue.py --retry 123 --dry-run
  
  # Reset all failed to pending
  python manual_queue.py --bulk-reset failed
        '''
    )
    
    parser.add_argument('--list', action='store_true',
                       help='List leads in manual review queue')
    parser.add_argument('--list-failed', action='store_true',
                       help='List failed submissions')
    parser.add_argument('--skip', type=int, metavar='ID',
                       help='Skip a lead (mark as skipped)')
    parser.add_argument('--reason', type=str, default='Manually skipped',
                       help='Reason for skipping')
    parser.add_argument('--reset', type=int, metavar='ID',
                       help='Reset lead to pending status')
    parser.add_argument('--map', type=int, metavar='ID',
                       help='Interactively create field mapping for lead')
    parser.add_argument('--retry', type=int, metavar='ID',
                       help='Retry submission with saved mapping')
    parser.add_argument('--dry-run', action='store_true',
                       help='Fill form but do not submit')
    parser.add_argument('--bulk-reset', type=str, metavar='STATUS',
                       choices=['failed', 'manual_review', 'skipped'],
                       help='Reset all leads with status to pending')
    
    args = parser.parse_args()
    manager = ManualQueueManager()
    
    if args.list:
        manager.print_queue('manual')
        return
    
    if args.list_failed:
        manager.print_queue('failed')
        return
    
    if args.skip:
        manager.skip_lead(args.skip, args.reason)
        return
    
    if args.reset:
        manager.reset_lead(args.reset)
        return
    
    if args.map:
        manager.interactive_mapping(args.map)
        return
    
    if args.retry:
        asyncio.run(manager.retry_with_mapping(args.retry, args.dry_run))
        return
    
    if args.bulk_reset:
        manager.bulk_reset(args.bulk_reset)
        return
    
    # Default: show queue
    manager.print_queue('manual')


if __name__ == "__main__":
    main()
