#!/usr/bin/env python3
"""
Form Submission Engine for Contact Form Automation

Main submission logic using Playwright with stealth:
- Loads contact form URLs
- Auto-detects and fills form fields
- Uses human-like behavior patterns
- Takes screenshots on success/failure
- Updates database with submission status
"""

import asyncio
import sqlite3
import os
import sys
import random
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List, NamedTuple
from dataclasses import dataclass

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from playwright.async_api import async_playwright, Page, Browser, BrowserContext
from playwright_stealth import Stealth

from scripts.form_detector_v2 import FormDetectorV2, FormAnalysis, FieldType, ProtectionType, safe_css_selector
from scripts.human_behavior import HumanBehavior

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class Lead:
    """Represents a lead to contact."""
    id: int
    business_name: str
    city: str
    state: str
    contact_form_url: str
    tier: str
    is_wholesale: bool = False
    crops_grown: Optional[str] = None
    
    
@dataclass
class SubmissionResult:
    """Result of a form submission attempt."""
    success: bool
    lead_id: int
    tracking_id: str
    template_variant: str
    error: Optional[str] = None
    screenshot_path: Optional[str] = None
    message_sent: Optional[str] = None


class FormSubmitter:
    """
    Main form submission engine.
    
    Handles the complete workflow:
    1. Load the contact form page
    2. Detect form fields
    3. Fill fields with human-like behavior
    4. Submit and verify
    5. Record results
    """
    
    # Configuration
    TEMPLATES_DIR = Path(__file__).parent.parent / 'templates' / 'contact_form'
    SCREENSHOTS_DIR = Path(__file__).parent.parent / 'data' / 'form_screenshots'
    DB_PATH = Path(__file__).parent.parent / 'data' / 'leads.db'
    
    # Reply email for all submissions
    REPLY_EMAIL = "colton@sweetleafsoil.com"
    SENDER_NAME = "Colton"
    SENDER_COMPANY = "Sweet Leaf Soil"
    SENDER_PHONE = ""  # Optional - leave empty to skip phone field
    
    # Browser configuration
    VIEWPORT = {'width': 1920, 'height': 1080}
    USER_AGENT = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    
    # Proxy configuration (placeholder - set actual proxies here)
    PROXY_LIST: List[Dict] = []  # Format: [{'server': 'http://proxy:port', 'username': 'user', 'password': 'pass'}]
    
    def __init__(self, headless: bool = False, use_proxy: bool = False):
        """
        Initialize the form submitter.
        
        Args:
            headless: Run browser in headless mode (default False for visibility)
            use_proxy: Enable proxy rotation
        """
        self.headless = headless
        self.use_proxy = use_proxy
        self.form_detector = FormDetectorV2()
        self.human_behavior = HumanBehavior()
        self.templates = self._load_templates()
        
        # Ensure directories exist
        self.SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    
    def _load_templates(self) -> Dict[str, str]:
        """Load message templates from files."""
        templates = {}
        for template_file in ['template_a.txt', 'template_b.txt', 'template_c.txt']:
            path = self.TEMPLATES_DIR / template_file
            if path.exists():
                with open(path, 'r') as f:
                    variant = template_file.replace('template_', '').replace('.txt', '').upper()
                    templates[variant] = f.read()
        return templates
    
    def _select_template(self, lead: Lead) -> str:
        """Select best template variant for a lead."""
        if lead.is_wholesale:
            return 'A'  # Direct offer for wholesale
        elif lead.crops_grown:
            return 'B'  # Problem-solution for production focus
        else:
            return 'C'  # Regional angle as default
    
    def _generate_tracking_id(self, lead: Lead) -> str:
        """Generate unique tracking ID for submission."""
        return f"REF-{lead.tier}{str(lead.id).zfill(3)}"
    
    def _personalize_message(self, template_variant: str, lead: Lead, tracking_id: str) -> str:
        """Fill in personalization variables in template."""
        template = self.templates.get(template_variant, self.templates.get('C', ''))
        
        message = template.replace('{{business_name}}', lead.business_name)
        message = message.replace('{{city}}', lead.city or '')
        message = message.replace('{{state}}', lead.state or '')
        message = message.replace('{{tracking_id}}', tracking_id)
        
        return message
    
    def _get_proxy(self) -> Optional[Dict]:
        """Get a random proxy from the pool."""
        if not self.use_proxy or not self.PROXY_LIST:
            return None
        return random.choice(self.PROXY_LIST)
    
    async def _create_browser_context(self, playwright) -> tuple[Browser, BrowserContext]:
        """Create a new browser and context with stealth settings."""
        browser = await playwright.chromium.launch(
            headless=self.headless,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
                '--no-sandbox',
            ]
        )
        
        # Context options
        context_options = {
            'viewport': self.VIEWPORT,
            'user_agent': self.USER_AGENT,
            'locale': 'en-US',
            'timezone_id': 'America/Chicago',
            'geolocation': {'latitude': 41.5868, 'longitude': -93.6250},  # Des Moines area
            'permissions': ['geolocation'],
        }
        
        # Add proxy if enabled
        proxy = self._get_proxy()
        if proxy:
            context_options['proxy'] = proxy
        
        context = await browser.new_context(**context_options)
        
        # Apply stealth using the new Stealth class
        stealth = Stealth(
            navigator_webdriver=True,  # Hide webdriver flag
            navigator_user_agent=True,
            navigator_vendor=True,
        )
        await stealth.apply_stealth_async(context)
        
        return browser, context
    
    async def _take_screenshot(self, page: Page, lead: Lead, suffix: str) -> str:
        """Take a screenshot and return the path."""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"lead_{lead.id}_{suffix}_{timestamp}.png"
        path = self.SCREENSHOTS_DIR / filename
        await page.screenshot(path=str(path), full_page=False)
        return str(path)
    
    async def _fill_form(self, page: Page, analysis: FormAnalysis, lead: Lead,
                         message: str) -> None:
        """Fill form fields with human-like behavior."""
        
        # Prepare for form interaction
        await self.human_behavior.prepare_for_form(page)
        
        # Fill name field
        name_field = analysis.get_field(FieldType.NAME) or analysis.get_field(FieldType.FIRST_NAME)
        if name_field:
            await asyncio.sleep(self.human_behavior.get_field_delay('name'))
            await self.human_behavior.type_with_human_behavior(
                page, name_field.selector, self.SENDER_NAME
            )
        
        # Fill last name if separate
        last_name_field = analysis.get_field(FieldType.LAST_NAME)
        if last_name_field:
            await asyncio.sleep(self.human_behavior.get_field_delay('name'))
            await self.human_behavior.type_with_human_behavior(
                page, last_name_field.selector, ""  # Optional
            )
        
        # Fill email field (required)
        email_field = analysis.get_field(FieldType.EMAIL)
        if email_field:
            await asyncio.sleep(self.human_behavior.get_field_delay('email'))
            await self.human_behavior.type_with_human_behavior(
                page, email_field.selector, self.REPLY_EMAIL
            )
        
        # Fill phone if we have one and field exists
        phone_field = analysis.get_field(FieldType.PHONE)
        if phone_field and self.SENDER_PHONE:
            await asyncio.sleep(self.human_behavior.get_field_delay('phone'))
            await self.human_behavior.type_with_human_behavior(
                page, phone_field.selector, self.SENDER_PHONE
            )
        
        # Fill company/business name
        company_field = analysis.get_field(FieldType.COMPANY)
        if company_field:
            await asyncio.sleep(self.human_behavior.get_field_delay('company'))
            await self.human_behavior.type_with_human_behavior(
                page, company_field.selector, self.SENDER_COMPANY
            )
        
        # Fill subject if present
        subject_field = analysis.get_field(FieldType.SUBJECT)
        if subject_field:
            subjects = [
                "Quick question about soil amendments",
                f"Free sample for {lead.business_name}",
                "Introducing Sweet Leaf Soil",
            ]
            await asyncio.sleep(self.human_behavior.get_field_delay('subject'))
            await self.human_behavior.type_with_human_behavior(
                page, subject_field.selector, random.choice(subjects)
            )
        
        # Fill message (required) - longer delay for "composing"
        message_field = analysis.get_field(FieldType.MESSAGE)
        if message_field:
            await asyncio.sleep(self.human_behavior.get_field_delay('message'))
            await self.human_behavior.type_with_human_behavior(
                page, message_field.selector, message
            )
        
        # Leave honeypot fields empty (already empty by default)
        # Just verify we don't accidentally fill them
    
    async def _verify_submission(self, page: Page) -> bool:
        """Verify form was submitted successfully."""
        # Wait a bit for response
        await asyncio.sleep(2)
        
        # Check for common success indicators
        success_patterns = [
            'thank', 'success', 'received', 'submitted', 'sent',
            'we will', 'we\'ll', 'contact you', 'get back'
        ]
        
        try:
            page_text = (await page.content()).lower()
            for pattern in success_patterns:
                if pattern in page_text:
                    return True
            
            # Check if form is gone (replaced with success message)
            form = await page.query_selector('form')
            if not form:
                return True
                
        except:
            pass
        
        # Check for error indicators
        error_patterns = ['error', 'invalid', 'required', 'failed', 'try again']
        try:
            page_text = (await page.content()).lower()
            for pattern in error_patterns:
                if pattern in page_text:
                    return False
        except:
            pass
        
        # Assume success if no clear error
        return True
    
    async def submit_form(self, lead: Lead, dry_run: bool = False) -> SubmissionResult:
        """
        Submit a contact form for a single lead.
        
        Args:
            lead: Lead to contact
            dry_run: If True, fills form but doesn't submit
            
        Returns:
            SubmissionResult with outcome details
        """
        tracking_id = self._generate_tracking_id(lead)
        template_variant = self._select_template(lead)
        message = self._personalize_message(template_variant, lead, tracking_id)
        
        logger.info(f"Processing lead {lead.id}: {lead.business_name}")
        logger.info(f"Template: {template_variant}, Tracking: {tracking_id}")
        
        browser = None
        screenshot_path = None
        
        try:
            async with async_playwright() as playwright:
                browser, context = await self._create_browser_context(playwright)
                page = await context.new_page()
                
                # Navigate to contact form
                logger.info(f"Loading: {lead.contact_form_url}")
                await page.goto(lead.contact_form_url, wait_until='domcontentloaded', timeout=30000)
                await asyncio.sleep(random.uniform(2, 4))  # Let page settle
                
                # Analyze the form
                logger.info("Analyzing form structure...")
                analysis = await self.form_detector.analyze_form(page)
                
                # Check if we can auto-submit
                if analysis.requires_manual:
                    logger.warning(f"Form requires manual review: {analysis.issues}")
                    screenshot_path = await self._take_screenshot(page, lead, 'manual_needed')
                    await browser.close()
                    
                    return SubmissionResult(
                        success=False,
                        lead_id=lead.id,
                        tracking_id=tracking_id,
                        template_variant=template_variant,
                        error=f"Manual review needed: {', '.join(analysis.issues)}",
                        screenshot_path=screenshot_path,
                        message_sent=None
                    )
                
                # Log detected fields
                logger.info(f"Detected {len(analysis.fields)} fields, confidence: {analysis.confidence:.2f}")
                for field in analysis.fields:
                    logger.debug(f"  {field.field_type.value}: {field.selector}")
                
                # Fill the form
                logger.info("Filling form fields...")
                await self._fill_form(page, analysis, lead, message)
                
                # Take pre-submit screenshot
                screenshot_path = await self._take_screenshot(page, lead, 'prefill')
                
                if dry_run:
                    logger.info("DRY RUN - Form filled but not submitted")
                    await browser.close()
                    
                    return SubmissionResult(
                        success=True,
                        lead_id=lead.id,
                        tracking_id=tracking_id,
                        template_variant=template_variant,
                        error="DRY RUN - not submitted",
                        screenshot_path=screenshot_path,
                        message_sent=message
                    )
                
                # Submit the form
                logger.info("Submitting form...")
                await asyncio.sleep(self.human_behavior.get_field_delay('submit'))
                
                if analysis.submit_selector:
                    await self.human_behavior.human_click(page, analysis.submit_selector)
                else:
                    # Try pressing Enter as fallback
                    await page.keyboard.press('Enter')
                
                # Wait for submission to process
                await asyncio.sleep(3)
                
                # Verify submission
                success = await self._verify_submission(page)
                
                # Take post-submit screenshot
                screenshot_path = await self._take_screenshot(page, lead, 'success' if success else 'failed')
                
                await browser.close()
                
                if success:
                    logger.info(f"✅ Successfully submitted form for {lead.business_name}")
                else:
                    logger.warning(f"❌ Submission may have failed for {lead.business_name}")
                
                return SubmissionResult(
                    success=success,
                    lead_id=lead.id,
                    tracking_id=tracking_id,
                    template_variant=template_variant,
                    error=None if success else "Submission verification failed",
                    screenshot_path=screenshot_path,
                    message_sent=message
                )
                
        except Exception as e:
            logger.error(f"Error submitting form for lead {lead.id}: {e}")
            
            if browser:
                try:
                    await browser.close()
                except:
                    pass
            
            return SubmissionResult(
                success=False,
                lead_id=lead.id,
                tracking_id=tracking_id,
                template_variant=template_variant,
                error=str(e),
                screenshot_path=screenshot_path,
                message_sent=None
            )
    
    def update_database(self, result: SubmissionResult) -> None:
        """Update database with submission result."""
        conn = sqlite3.connect(self.DB_PATH)
        cursor = conn.cursor()
        
        status = 'submitted' if result.success else 'failed'
        if result.error and 'manual' in result.error.lower():
            status = 'manual_review'
        if result.error and 'dry run' in result.error.lower():
            status = 'dry_run'
        
        cursor.execute('''
            UPDATE leads 
            SET form_submission_status = ?,
                form_submitted_at = ?,
                form_tracking_id = ?,
                form_template_variant = ?,
                form_error = ?
            WHERE id = ?
        ''', (
            status,
            datetime.now().isoformat() if result.success else None,
            result.tracking_id,
            result.template_variant,
            result.error,
            result.lead_id
        ))
        
        conn.commit()
        conn.close()
        
        logger.info(f"Database updated for lead {result.lead_id}: status={status}")


def get_pending_leads(db_path: str, limit: int = 10) -> List[Lead]:
    """Get leads that need form submission."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT id, business_name, city, state, contact_form_url, tier, 
               is_wholesale, crops_grown
        FROM leads
        WHERE has_contact_form = 1
          AND contact_form_url IS NOT NULL
          AND contact_form_url != ''
          AND (form_submission_status IS NULL OR form_submission_status = 'pending')
          AND (owner_email IS NULL OR owner_email = '')
          AND (contact_email IS NULL OR contact_email = '')
          AND (generic_email IS NULL OR generic_email = '')
        ORDER BY 
            CASE tier WHEN 'A' THEN 1 WHEN 'B' THEN 2 ELSE 3 END,
            id
        LIMIT ?
    ''', (limit,))
    
    leads = []
    for row in cursor.fetchall():
        leads.append(Lead(
            id=row[0],
            business_name=row[1],
            city=row[2] or '',
            state=row[3] or '',
            contact_form_url=row[4],
            tier=row[5] or 'U',
            is_wholesale=bool(row[6]),
            crops_grown=row[7]
        ))
    
    conn.close()
    return leads


async def test_single_submission():
    """Test submission on a single lead."""
    # Get one pending lead
    leads = get_pending_leads(
        str(Path(__file__).parent.parent / 'data' / 'leads.db'),
        limit=1
    )
    
    if not leads:
        print("No pending leads with contact forms found!")
        return
    
    lead = leads[0]
    print(f"\nTest lead: {lead.business_name}")
    print(f"URL: {lead.contact_form_url}")
    print(f"Tier: {lead.tier}")
    
    submitter = FormSubmitter(headless=False)
    result = await submitter.submit_form(lead, dry_run=True)
    
    print(f"\nResult:")
    print(f"  Success: {result.success}")
    print(f"  Tracking ID: {result.tracking_id}")
    print(f"  Template: {result.template_variant}")
    print(f"  Error: {result.error}")
    print(f"  Screenshot: {result.screenshot_path}")
    
    if result.message_sent:
        print(f"\nMessage preview:")
        print("-" * 40)
        print(result.message_sent[:500])
        print("-" * 40)


if __name__ == "__main__":
    asyncio.run(test_single_submission())
