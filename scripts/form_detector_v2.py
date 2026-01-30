#!/usr/bin/env python3
"""
Form Detector V2 - Robust Contact Form Detection

Improvements over V1:
- Safe CSS selector escaping (handles special chars in IDs)
- Multiple detection strategies (standard, platform-specific, heuristic)
- Platform-specific handlers (Wix, Squarespace, WordPress, Shopify, DudaMobile, etc.)
- Fallback to visual/heuristic detection
- Iframe inspection for embedded forms
- Better field type detection using multiple signals
"""

import re
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
from urllib.parse import urlparse
import logging

logger = logging.getLogger(__name__)


# Directory domains that should be rejected
DIRECTORY_DOMAINS = {
    'yelp.com', 'yellowpages.com', 'bbb.org', 'manta.com', 
    'facebook.com', 'instagram.com', 'linkedin.com',
    'trees.com', 'arborday.org',
}


class FieldType(Enum):
    """Types of form fields we can detect."""
    NAME = "name"
    FIRST_NAME = "first_name"
    LAST_NAME = "last_name"
    EMAIL = "email"
    PHONE = "phone"
    COMPANY = "company"
    SUBJECT = "subject"
    MESSAGE = "message"
    CITY = "city"
    STATE = "state"
    ZIP = "zip"
    UNKNOWN = "unknown"


class ProtectionType(Enum):
    """Types of form protection mechanisms."""
    NONE = "none"
    HONEYPOT = "honeypot"
    RECAPTCHA_V2 = "recaptcha_v2"
    RECAPTCHA_V3 = "recaptcha_v3"
    HCAPTCHA = "hcaptcha"
    TURNSTILE = "turnstile"
    CLOUDFLARE = "cloudflare"
    CUSTOM_CAPTCHA = "custom_captcha"
    UNKNOWN = "unknown"


class DetectionStrategy(Enum):
    """Which strategy successfully detected the form."""
    STANDARD_FORM = "standard_form"
    WPFORMS = "wpforms"
    CONTACT_FORM_7 = "contact_form_7"
    GRAVITY_FORMS = "gravity_forms"
    FUSION_BUILDER = "fusion_builder"
    DUDAMOBILE = "dudamobile"
    ELEMENTOR = "elementor"
    SHOPIFY = "shopify"
    WIX = "wix"
    SQUARESPACE = "squarespace"
    HEURISTIC = "heuristic"
    NONE = "none"


@dataclass
class FieldMapping:
    """Represents a detected form field."""
    field_type: FieldType
    selector: str
    element_type: str  # input, textarea, select
    is_required: bool = False
    max_length: Optional[int] = None
    placeholder: Optional[str] = None
    label: Optional[str] = None
    confidence: float = 1.0
    
    def __repr__(self):
        return f"<Field {self.field_type.value}: {self.selector}>"


@dataclass
class FormAnalysis:
    """Complete analysis of a contact form."""
    form_selector: Optional[str] = None
    submit_selector: Optional[str] = None
    fields: List[FieldMapping] = field(default_factory=list)
    protection_type: ProtectionType = ProtectionType.NONE
    honeypot_selectors: List[str] = field(default_factory=list)
    requires_manual: bool = False
    issues: List[str] = field(default_factory=list)
    platform: Optional[str] = None
    detection_strategy: DetectionStrategy = DetectionStrategy.NONE
    confidence: float = 0.0
    page_blocked: bool = False
    http_status: Optional[int] = None
    
    def get_field(self, field_type: FieldType) -> Optional[FieldMapping]:
        """Get a field by type."""
        for f in self.fields:
            if f.field_type == field_type:
                return f
        return None
    
    def has_required_fields(self) -> bool:
        """Check if form has minimum required fields (email + message)."""
        has_email = self.get_field(FieldType.EMAIL) is not None
        has_message = self.get_field(FieldType.MESSAGE) is not None
        return has_email and has_message
    
    def has_name_field(self) -> bool:
        """Check if form has a name field."""
        return (
            self.get_field(FieldType.NAME) is not None or
            self.get_field(FieldType.FIRST_NAME) is not None
        )


def escape_css_id(element_id: str) -> str:
    r"""
    Escape special characters in a CSS ID selector.
    
    CSS selector spec requires escaping: !"#$%&'()*+,./:;<=>?@[\]^`{|}~ and space
    """
    if not element_id:
        return element_id
    
    # Escape special characters with backslash
    escaped = re.sub(r'([!"#$%&\'()*+,./:;<=>?@\[\]\\^`{|}~ ])', r'\\\1', element_id)
    return escaped


def safe_css_selector(tag: str, name: Optional[str] = None, 
                      element_id: Optional[str] = None,
                      class_name: Optional[str] = None) -> str:
    """
    Build a safe CSS selector that handles special characters.
    
    Prefers attribute selectors for reliability with special chars.
    """
    if element_id:
        # Use attribute selector for IDs with special chars OR numeric IDs
        # CSS selectors can't start with a digit, so #123 is invalid
        if re.search(r'[!"#$%&\'()*+,./:;<=>?@\[\]\\^`{|}~ ]', element_id) or element_id[0].isdigit():
            return f'{tag}[id="{element_id}"]'
        else:
            return f'#{element_id}'
    
    if name:
        return f'{tag}[name="{name}"]'
    
    if class_name:
        # Take first class and escape if needed
        first_class = class_name.split()[0]
        if re.search(r'[!"#$%&\'()*+,./:;<=>?@\[\]\\^`{|}~ ]', first_class):
            return f'{tag}[class*="{first_class}"]'
        else:
            return f'{tag}.{first_class}'
    
    return tag


class FormDetectorV2:
    """
    Robust form detector with multiple detection strategies.
    
    Detection order:
    1. Platform-specific detection (WPForms, CF7, Gravity, etc.)
    2. Standard HTML form detection
    3. Heuristic detection (any inputs + textarea on page)
    """
    
    # Field type patterns (name, id, placeholder, label text)
    FIELD_PATTERNS = {
        FieldType.NAME: [
            r'\bname\b', r'\bfull.?name\b', r'\byour.?name\b', 
            r'\bcontact.?name\b', r'\bname_field\b', r'\bdmform-0\b'
        ],
        FieldType.FIRST_NAME: [
            r'\bfirst.?name\b', r'\bfname\b', r'\bgiven.?name\b',
            r'\[first\]', r'_first\b'
        ],
        FieldType.LAST_NAME: [
            r'\blast.?name\b', r'\blname\b', r'\bsurname\b', 
            r'\bfamily.?name\b', r'\[last\]', r'_last\b'
        ],
        FieldType.EMAIL: [
            r'\bemail\b', r'\be-mail\b', r'\bmail\b', r'\bemailaddress\b',
            r'\bdmform-1\b'  # DudaMobile email field
        ],
        FieldType.PHONE: [
            r'\bphone\b', r'\btel\b', r'\bmobile\b', r'\bcell\b', 
            r'\bcontact.?number\b', r'\btelephone\b', r'\bdmform-2\b'
        ],
        FieldType.COMPANY: [
            r'\bcompany\b', r'\bbusiness\b', r'\borganization\b', 
            r'\borg\b', r'\bcompany.?name\b', r'\bbusiness.?name\b'
        ],
        FieldType.SUBJECT: [
            r'\bsubject\b', r'\btopic\b', r'\bregarding\b', r'\bre\b',
            r'\binquiry.?type\b', r'\breason\b'
        ],
        FieldType.MESSAGE: [
            r'\bmessage\b', r'\bcomment\b', r'\binquiry\b', r'\bquestion\b',
            r'\bdetails\b', r'\bdescription\b', r'\bcontent\b', r'\bbody\b',
            r'\bhow.?can.?we.?help\b', r'\bhow.?may.?we.?help\b',
            r'\btell.?us\b', r'\bdmform-3\b'  # DudaMobile message
        ],
    }
    
    # Platform detection patterns
    PLATFORM_PATTERNS = {
        'wpforms': [r'wpforms-form', r'wpforms-submit', r'wpforms\[fields\]'],
        'contact_form_7': [r'wpcf7', r'contact-form-7'],
        'gravity_forms': [r'gform_wrapper', r'gfield', r'gravityforms'],
        'ninja_forms': [r'ninja-forms', r'nf-form'],
        'fusion_builder': [r'fusion-form', r'fusion-button'],
        'elementor': [r'elementor-form', r'elementor-field'],
        'divi': [r'et_pb_contact_form'],
        'dudamobile': [r'dmform', r'dmRespDesignRow', r'dmformsendto'],
        'wix': [r'wix\.com', r'wixforms', r'_wix'],
        'squarespace': [r'squarespace', r'sqs-block-form', r'form-wrapper'],
        'shopify': [r'cdn\.shopify', r'shopify'],
        'hubspot': [r'hs-form', r'hsforms', r'hubspot'],
        'jotform': [r'jotform', r'form-all'],
        'typeform': [r'typeform'],
        'mailchimp': [r'mc-embedded', r'mailchimp'],
    }
    
    # Honeypot patterns
    HONEYPOT_PATTERNS = [
        r'\bhoney\b', r'\bpot\b', r'\btrap\b', r'\bhoneypot\b',
        r'\bwebsite\b', r'\burl\b', r'\baddress2\b', r'\bfax\b',
        r'\bleave.?blank\b', r'\bdo.?not.?fill\b', r'\bhp\b',
        r'wpforms\[hp\]'
    ]
    
    # Blocked page indicators - must be in visible text, not JS
    # These patterns indicate the page is blocked, not just mentions in code
    BLOCKED_PATTERNS = [
        r'checking your browser.*this will only take',
        r'just a moment.*verifying',
        r'please wait while we verify',
        r'ddos protection by',
        r'access denied.*forbidden',
        r'error 403.*forbidden',
        r'error 1020.*access denied',
    ]
    
    def __init__(self):
        self.compiled_field_patterns = {}
        self._compile_patterns()
    
    def _compile_patterns(self):
        """Pre-compile regex patterns for efficiency."""
        for field_type, patterns in self.FIELD_PATTERNS.items():
            self.compiled_field_patterns[field_type] = [
                re.compile(p, re.IGNORECASE) for p in patterns
            ]
    
    async def analyze_form(self, page) -> FormAnalysis:
        """
        Main entry point: Analyze a page to detect contact forms.
        
        Tries multiple detection strategies in order of reliability.
        """
        analysis = FormAnalysis()
        
        # Check for blocked page first - check visible text, not just HTML
        try:
            html = await page.content()
            html_lower = html.lower()
            
            # Get visible text for more accurate block detection
            try:
                visible_text = await page.evaluate("() => document.body.innerText.toLowerCase()")
            except:
                visible_text = html_lower
            
            # Check if page appears blocked
            is_blocked = False
            for pattern in self.BLOCKED_PATTERNS:
                if re.search(pattern, visible_text):
                    is_blocked = True
                    break
            
            # Also check if page is suspiciously short (< 1000 chars) AND has block keywords
            if is_blocked or (len(visible_text) < 1000 and any(
                kw in visible_text for kw in ['checking', 'verifying', 'moment', 'wait']
            )):
                # Verify it's actually a block page by checking for forms
                forms = await page.query_selector_all('form')
                inputs = await page.query_selector_all('input:not([type="hidden"])')
                
                # If we find substantial form elements, it's not a block page
                if len(forms) >= 1 and len(inputs) >= 2:
                    logger.info("Page has block keywords but also has forms, proceeding...")
                else:
                    analysis.page_blocked = True
                    analysis.protection_type = ProtectionType.CLOUDFLARE
                    analysis.requires_manual = True
                    analysis.issues.append("Page blocked by anti-bot protection")
                    logger.warning("Page blocked by anti-bot protection")
                    return analysis
                    
        except Exception as e:
            logger.error(f"Error getting page content: {e}")
            analysis.issues.append(f"Error accessing page: {e}")
            return analysis
        
        # Detect platform
        analysis.platform = self._detect_platform(html_lower)
        logger.info(f"Detected platform: {analysis.platform}")
        
        # Try platform-specific detection first
        if analysis.platform:
            result = await self._detect_platform_specific(page, analysis.platform)
            if result and result.has_required_fields():
                result.platform = analysis.platform
                return result
        
        # Try standard form detection
        result = await self._detect_standard_form(page)
        if result and result.has_required_fields():
            return result
        
        # Try heuristic detection (find any inputs/textareas)
        result = await self._detect_heuristic(page)
        if result and result.has_required_fields():
            return result
        
        # No form found
        analysis.requires_manual = True
        analysis.issues.append("No contact form detected")
        return analysis
    
    def _detect_platform(self, html: str) -> Optional[str]:
        """Detect which platform/form builder the site uses."""
        for platform, patterns in self.PLATFORM_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, html, re.IGNORECASE):
                    return platform
        return None
    
    async def _detect_platform_specific(self, page, platform: str) -> Optional[FormAnalysis]:
        """Use platform-specific detection logic."""
        handlers = {
            'wpforms': self._detect_wpforms,
            'contact_form_7': self._detect_cf7,
            'gravity_forms': self._detect_gravity,
            'fusion_builder': self._detect_fusion,
            'dudamobile': self._detect_dudamobile,
            'elementor': self._detect_elementor,
        }
        
        handler = handlers.get(platform)
        if handler:
            try:
                return await handler(page)
            except Exception as e:
                logger.error(f"Platform-specific detection failed for {platform}: {e}")
        
        return None
    
    async def _detect_wpforms(self, page) -> Optional[FormAnalysis]:
        """Detect WPForms fields."""
        analysis = FormAnalysis(detection_strategy=DetectionStrategy.WPFORMS)
        
        # Find WPForms container
        form = await page.query_selector('form[id^="wpforms-form-"]')
        if not form:
            form = await page.query_selector('.wpforms-form')
        
        if not form:
            return None
        
        form_id = await form.get_attribute('id')
        analysis.form_selector = f'#{form_id}' if form_id else '.wpforms-form'
        
        # Find all inputs
        inputs = await form.query_selector_all('input:not([type="hidden"]):not([type="submit"])')
        textareas = await form.query_selector_all('textarea')
        
        for inp in inputs:
            field = await self._analyze_input(inp)
            if field and field.field_type != FieldType.UNKNOWN:
                # Check if it's a honeypot
                name = await inp.get_attribute('name') or ''
                if 'hp' in name.lower() or not await inp.is_visible():
                    analysis.honeypot_selectors.append(field.selector)
                else:
                    analysis.fields.append(field)
        
        for ta in textareas:
            field = await self._analyze_textarea(ta)
            if field:
                analysis.fields.append(field)
        
        # Find submit button
        submit = await form.query_selector('button[type="submit"], .wpforms-submit')
        if submit:
            analysis.submit_selector = 'button[type="submit"], .wpforms-submit'
        
        analysis.confidence = 0.9 if analysis.has_required_fields() else 0.3
        return analysis
    
    async def _detect_cf7(self, page) -> Optional[FormAnalysis]:
        """Detect Contact Form 7 fields."""
        analysis = FormAnalysis(detection_strategy=DetectionStrategy.CONTACT_FORM_7)
        
        form = await page.query_selector('.wpcf7-form')
        if not form:
            return None
        
        analysis.form_selector = '.wpcf7-form'
        
        # CF7 uses specific class naming
        inputs = await form.query_selector_all('.wpcf7-form-control:not([type="submit"])')
        
        for inp in inputs:
            field = await self._analyze_input(inp)
            if field:
                analysis.fields.append(field)
        
        submit = await form.query_selector('.wpcf7-submit')
        if submit:
            analysis.submit_selector = '.wpcf7-submit'
        
        analysis.confidence = 0.9 if analysis.has_required_fields() else 0.3
        return analysis
    
    async def _detect_gravity(self, page) -> Optional[FormAnalysis]:
        """Detect Gravity Forms fields."""
        analysis = FormAnalysis(detection_strategy=DetectionStrategy.GRAVITY_FORMS)
        
        form = await page.query_selector('.gform_wrapper form')
        if not form:
            return None
        
        analysis.form_selector = '.gform_wrapper form'
        
        inputs = await form.query_selector_all('.gfield input, .gfield textarea, .gfield select')
        
        for inp in inputs:
            field = await self._analyze_input(inp)
            if field:
                analysis.fields.append(field)
        
        submit = await form.query_selector('.gform_button, input[type="submit"]')
        if submit:
            analysis.submit_selector = '.gform_button, input[type="submit"]'
        
        analysis.confidence = 0.9 if analysis.has_required_fields() else 0.3
        return analysis
    
    async def _detect_fusion(self, page) -> Optional[FormAnalysis]:
        """Detect Fusion Builder (Avada theme) forms."""
        analysis = FormAnalysis(detection_strategy=DetectionStrategy.FUSION_BUILDER)
        
        form = await page.query_selector('.fusion-form')
        if not form:
            return None
        
        # Get form class for selector
        form_class = await form.get_attribute('class')
        analysis.form_selector = '.fusion-form'
        
        # Find all inputs
        inputs = await form.query_selector_all('input:not([type="hidden"]):not([type="submit"])')
        textareas = await form.query_selector_all('textarea')
        
        for inp in inputs:
            field = await self._analyze_input(inp)
            if field and await inp.is_visible():
                analysis.fields.append(field)
        
        for ta in textareas:
            field = await self._analyze_textarea(ta)
            if field and await ta.is_visible():
                analysis.fields.append(field)
        
        submit = await form.query_selector('button[type="submit"], .fusion-button')
        if submit:
            analysis.submit_selector = 'button[type="submit"]'
        
        analysis.confidence = 0.9 if analysis.has_required_fields() else 0.3
        return analysis
    
    async def _detect_dudamobile(self, page) -> Optional[FormAnalysis]:
        """Detect DudaMobile forms."""
        analysis = FormAnalysis(detection_strategy=DetectionStrategy.DUDAMOBILE)
        
        form = await page.query_selector('form.dmRespDesignRow, form[id]')
        if not form:
            # DudaMobile sometimes doesn't use form tags properly
            # Look for dmform inputs
            inputs = await page.query_selector_all('input[name^="dmform-"]')
            if not inputs:
                return None
            form = await inputs[0].evaluate('el => el.closest("form")')
        
        if form:
            form_id = await page.evaluate('(el) => el.id', form) if form else None
            analysis.form_selector = f'#{form_id}' if form_id else 'form'
        else:
            analysis.form_selector = 'body'
        
        # DudaMobile naming: dmform-0 = name, dmform-1 = email, dmform-2 = phone, dmform-3 = message
        duda_inputs = await page.query_selector_all('input[name^="dmform-"]')
        duda_textareas = await page.query_selector_all('textarea[name^="dmform-"]')
        
        for inp in duda_inputs:
            name = await inp.get_attribute('name')
            element_id = await inp.get_attribute('id')
            placeholder = await inp.get_attribute('placeholder')
            inp_type = await inp.get_attribute('type')
            visible = await inp.is_visible()
            
            if not visible or inp_type in ['hidden', 'submit']:
                continue
            
            # DudaMobile field mapping
            field_type = FieldType.UNKNOWN
            if name == 'dmform-0' or (placeholder and 'name' in placeholder.lower()):
                field_type = FieldType.NAME
            elif name == 'dmform-1' or inp_type == 'email':
                field_type = FieldType.EMAIL
            elif name == 'dmform-2' or inp_type == 'tel':
                field_type = FieldType.PHONE
            
            if field_type != FieldType.UNKNOWN:
                selector = safe_css_selector('input', name=name, element_id=element_id)
                analysis.fields.append(FieldMapping(
                    field_type=field_type,
                    selector=selector,
                    element_type='input',
                    placeholder=placeholder,
                    confidence=0.9
                ))
        
        for ta in duda_textareas:
            name = await ta.get_attribute('name')
            element_id = await ta.get_attribute('id')
            placeholder = await ta.get_attribute('placeholder')
            visible = await ta.is_visible()
            
            if visible:
                selector = safe_css_selector('textarea', name=name, element_id=element_id)
                analysis.fields.append(FieldMapping(
                    field_type=FieldType.MESSAGE,
                    selector=selector,
                    element_type='textarea',
                    placeholder=placeholder,
                    confidence=0.9
                ))
        
        # Find submit button
        submit = await page.query_selector('input[type="submit"], button[type="submit"]')
        if submit:
            submit_id = await submit.get_attribute('id')
            tag = await submit.evaluate('el => el.tagName.toLowerCase()')
            if submit_id:
                # Use safe selector for numeric IDs
                analysis.submit_selector = safe_css_selector(tag, element_id=submit_id)
            else:
                analysis.submit_selector = 'input[type="submit"], button[type="submit"]'
        
        analysis.confidence = 0.9 if analysis.has_required_fields() else 0.3
        return analysis
    
    async def _detect_elementor(self, page) -> Optional[FormAnalysis]:
        """Detect Elementor forms."""
        analysis = FormAnalysis(detection_strategy=DetectionStrategy.ELEMENTOR)
        
        form = await page.query_selector('.elementor-form')
        if not form:
            return None
        
        analysis.form_selector = '.elementor-form'
        
        inputs = await form.query_selector_all('.elementor-field:not([type="submit"])')
        
        for inp in inputs:
            field = await self._analyze_input(inp)
            if field:
                analysis.fields.append(field)
        
        submit = await form.query_selector('.elementor-button[type="submit"], button[type="submit"]')
        if submit:
            analysis.submit_selector = '.elementor-button[type="submit"], button[type="submit"]'
        
        analysis.confidence = 0.9 if analysis.has_required_fields() else 0.3
        return analysis
    
    async def _detect_standard_form(self, page) -> Optional[FormAnalysis]:
        """Detect standard HTML forms."""
        analysis = FormAnalysis(detection_strategy=DetectionStrategy.STANDARD_FORM)
        
        # Try various form selectors
        form_selectors = [
            'form[action*="contact"]',
            'form[id*="contact"]',
            'form[class*="contact"]',
            '#contact-form',
            '.contact-form',
            'form[method="post"]',
        ]
        
        form = None
        for selector in form_selectors:
            try:
                candidate = await page.query_selector(selector)
                if candidate:
                    # Check if it has meaningful inputs (not just search)
                    inputs = await candidate.query_selector_all('input:not([type="search"]):not([type="hidden"])')
                    textareas = await candidate.query_selector_all('textarea')
                    if len(inputs) >= 2 or (len(inputs) >= 1 and len(textareas) >= 1):
                        form = candidate
                        analysis.form_selector = selector
                        break
            except:
                continue
        
        if not form:
            # Last resort: find any form with inputs
            forms = await page.query_selector_all('form')
            for f in forms:
                inputs = await f.query_selector_all('input:not([type="search"]):not([type="hidden"]):not([type="submit"])')
                textareas = await f.query_selector_all('textarea')
                if len(inputs) >= 2 or (len(inputs) >= 1 and len(textareas) >= 1):
                    form = f
                    form_id = await f.get_attribute('id')
                    analysis.form_selector = f'#{form_id}' if form_id else 'form'
                    break
        
        if not form:
            return None
        
        # Analyze fields
        inputs = await form.query_selector_all('input:not([type="hidden"]):not([type="submit"])')
        textareas = await form.query_selector_all('textarea')
        
        for inp in inputs:
            field = await self._analyze_input(inp)
            if field and await inp.is_visible():
                # Check honeypot
                name = await inp.get_attribute('name') or ''
                element_id = await inp.get_attribute('id') or ''
                if self._is_honeypot(name, element_id):
                    analysis.honeypot_selectors.append(field.selector)
                else:
                    analysis.fields.append(field)
        
        for ta in textareas:
            field = await self._analyze_textarea(ta)
            if field and await ta.is_visible():
                analysis.fields.append(field)
        
        # Find submit button
        submit = await form.query_selector('button[type="submit"], input[type="submit"], button:has-text("Submit"), button:has-text("Send")')
        if submit:
            analysis.submit_selector = 'button[type="submit"], input[type="submit"]'
        
        analysis.confidence = 0.8 if analysis.has_required_fields() else 0.3
        return analysis
    
    async def _detect_heuristic(self, page) -> Optional[FormAnalysis]:
        """
        Heuristic detection: Find any visible inputs + textarea on page.
        
        Used as fallback when no proper form structure is detected.
        """
        analysis = FormAnalysis(detection_strategy=DetectionStrategy.HEURISTIC)
        analysis.form_selector = 'body'  # No specific form
        
        # Find all visible inputs on page
        inputs = await page.query_selector_all('input[type="text"], input[type="email"], input[type="tel"]')
        textareas = await page.query_selector_all('textarea')
        
        visible_inputs = []
        for inp in inputs:
            if await inp.is_visible():
                visible_inputs.append(inp)
        
        visible_textareas = []
        for ta in textareas:
            if await ta.is_visible():
                visible_textareas.append(ta)
        
        # Need at least email/name + message
        if len(visible_inputs) < 1 or len(visible_textareas) < 1:
            return None
        
        for inp in visible_inputs:
            field = await self._analyze_input(inp)
            if field:
                analysis.fields.append(field)
        
        for ta in visible_textareas:
            field = await self._analyze_textarea(ta)
            if field:
                analysis.fields.append(field)
        
        # Find any submit-like button
        submit = await page.query_selector('button[type="submit"], input[type="submit"], button:has-text("Submit"), button:has-text("Send"), button:has-text("Contact")')
        if submit and await submit.is_visible():
            submit_id = await submit.get_attribute('id')
            if submit_id:
                analysis.submit_selector = safe_css_selector('button', element_id=submit_id)
            else:
                analysis.submit_selector = 'button[type="submit"], input[type="submit"]'
        
        analysis.confidence = 0.6 if analysis.has_required_fields() else 0.2
        return analysis
    
    async def _analyze_input(self, element) -> Optional[FieldMapping]:
        """Analyze a single input element."""
        try:
            name = await element.get_attribute('name') or ''
            element_id = await element.get_attribute('id') or ''
            class_attr = await element.get_attribute('class') or ''
            placeholder = await element.get_attribute('placeholder') or ''
            input_type = await element.get_attribute('type') or 'text'
            required = await element.get_attribute('required') is not None
            maxlength = await element.get_attribute('maxlength')
            
            # Skip hidden, submit, button
            if input_type in ['hidden', 'submit', 'button', 'reset', 'search']:
                return None
            
            # Determine field type
            if input_type == 'email':
                field_type = FieldType.EMAIL
            elif input_type == 'tel':
                field_type = FieldType.PHONE
            else:
                # Check patterns
                all_text = ' '.join([name, element_id, class_attr, placeholder])
                field_type = self._match_field_type(all_text)
            
            # Build safe selector
            selector = safe_css_selector('input', name=name, element_id=element_id, class_name=class_attr)
            
            return FieldMapping(
                field_type=field_type,
                selector=selector,
                element_type='input',
                is_required=required,
                max_length=int(maxlength) if maxlength else None,
                placeholder=placeholder,
                confidence=0.9 if field_type != FieldType.UNKNOWN else 0.4
            )
        except Exception as e:
            logger.error(f"Error analyzing input: {e}")
            return None
    
    async def _analyze_textarea(self, element) -> Optional[FieldMapping]:
        """Analyze a textarea element."""
        try:
            name = await element.get_attribute('name') or ''
            element_id = await element.get_attribute('id') or ''
            class_attr = await element.get_attribute('class') or ''
            placeholder = await element.get_attribute('placeholder') or ''
            required = await element.get_attribute('required') is not None
            maxlength = await element.get_attribute('maxlength')
            
            # Textareas are almost always message fields
            selector = safe_css_selector('textarea', name=name, element_id=element_id, class_name=class_attr)
            
            return FieldMapping(
                field_type=FieldType.MESSAGE,
                selector=selector,
                element_type='textarea',
                is_required=required,
                max_length=int(maxlength) if maxlength else None,
                placeholder=placeholder,
                confidence=0.95
            )
        except Exception as e:
            logger.error(f"Error analyzing textarea: {e}")
            return None
    
    def _match_field_type(self, text: str) -> FieldType:
        """Match text against patterns to determine field type."""
        if not text:
            return FieldType.UNKNOWN
        
        for field_type, patterns in self.compiled_field_patterns.items():
            for pattern in patterns:
                if pattern.search(text):
                    return field_type
        
        return FieldType.UNKNOWN
    
    def _is_honeypot(self, name: str, element_id: str) -> bool:
        """Check if a field is likely a honeypot."""
        text = (name + element_id).lower()
        for pattern in self.HONEYPOT_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                return True
        return False


# Convenience function
async def detect_form_fields(page) -> FormAnalysis:
    """
    Convenience function to detect form fields on a page.
    
    Args:
        page: Playwright page object
        
    Returns:
        FormAnalysis with detected fields
    """
    detector = FormDetectorV2()
    return await detector.analyze_form(page)


if __name__ == "__main__":
    print("Form Detector V2")
    print("Use with Playwright page object:")
    print("  from form_detector_v2 import FormDetectorV2, detect_form_fields")
    print("  analysis = await detect_form_fields(page)")
    print("  print(analysis.fields)")
