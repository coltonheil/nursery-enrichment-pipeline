#!/usr/bin/env python3
"""
Form Detector Module for Contact Form Automation

Detects and maps form fields on contact pages:
- Identifies field types (name, email, phone, message, etc.)
- Detects CAPTCHA and protection mechanisms
- Handles common form builders (Wix, Squarespace, WordPress, etc.)
- Detects directory/listing sites that should be rejected
- Returns field mappings or flags for manual review
"""

import re
from typing import Dict, List, Optional, NamedTuple, Tuple
from dataclasses import dataclass, field
from enum import Enum
from urllib.parse import urlparse


# Known directory and listing sites - forms on these are NOT the business's contact
DIRECTORY_DOMAINS = {
    # Tree/Nursery directories
    'trees.com', 'arborday.org', 'gardenweb.com', 'plantmaps.com',
    # General business directories  
    'yelp.com', 'yellowpages.com', 'whitepages.com', 'manta.com',
    'bbb.org', 'angieslist.com', 'thumbtack.com', 'homeadvisor.com',
    'houzz.com', 'porch.com', 'nextdoor.com', 'alignable.com',
    # Local/regional directories
    'reallancastercounty.com', 'localgardencentres.net', 'justplainbusiness.com',
    'meetottumwa.org', 'chamberofcommerce.com',
    # Generic POI/listing sites
    'poi.place', 'keeq.io', 'mapquest.com', 'citysearch.com',
    'superpages.com', 'dexknows.com', 'merchantcircle.com',
    # Corporate parent sites (not individual locations)
    'earthdevelopmentinc.com', 'rlmgmt.com', 'baileynurseries.com',
    'walbecgroup.com', 'greatlakesace.com', 'bordines.com',
    # Social media (not proper contact forms)
    'facebook.com', 'fb.com', 'instagram.com', 'twitter.com', 'x.com',
    'linkedin.com', 'pinterest.com', 'tiktok.com', 'youtube.com',
}

# Blog platforms that may or may not have good contact forms
BLOG_PLATFORMS = {
    'wordpress.com', 'blogger.com', 'blogspot.com',
    'wix.com', 'weebly.com', 'tumblr.com',
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
    CUSTOM_CAPTCHA = "custom_captcha"
    UNKNOWN = "unknown"


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
    form_builder: Optional[str] = None  # wix, squarespace, wordpress, etc.
    confidence: float = 0.0
    
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
        has_name = (
            self.get_field(FieldType.NAME) is not None or
            self.get_field(FieldType.FIRST_NAME) is not None
        )
        return has_email and has_message


class FormDetector:
    """Detects and analyzes contact form fields."""
    
    # Patterns for field type detection
    FIELD_PATTERNS = {
        FieldType.NAME: [
            r'\bname\b', r'\bfull.?name\b', r'\byour.?name\b', 
            r'\bcontact.?name\b', r'\bname_field\b'
        ],
        FieldType.FIRST_NAME: [
            r'\bfirst.?name\b', r'\bfname\b', r'\bgiven.?name\b'
        ],
        FieldType.LAST_NAME: [
            r'\blast.?name\b', r'\blname\b', r'\bsurname\b', r'\bfamily.?name\b'
        ],
        FieldType.EMAIL: [
            r'\bemail\b', r'\be-mail\b', r'\bmail\b', r'\bemailaddress\b'
        ],
        FieldType.PHONE: [
            r'\bphone\b', r'\btel\b', r'\bmobile\b', r'\bcell\b', 
            r'\bcontact.?number\b', r'\btelephone\b'
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
            r'\bhow.?can.?we.?help\b', r'\btell.?us\b'
        ],
        FieldType.CITY: [
            r'\bcity\b', r'\btown\b', r'\blocality\b'
        ],
        FieldType.STATE: [
            r'\bstate\b', r'\bprovince\b', r'\bregion\b'
        ],
        FieldType.ZIP: [
            r'\bzip\b', r'\bpostal\b', r'\bpostcode\b', r'\bzip.?code\b'
        ],
    }
    
    # Form builder detection patterns
    FORM_BUILDER_PATTERNS = {
        'wix': [r'wix\.com', r'wixforms', r'wix-form'],
        'squarespace': [r'squarespace', r'sqs-block-form'],
        'wordpress_cf7': [r'wpcf7', r'contact-form-7', r'cf7'],
        'wordpress_gravity': [r'gform', r'gravity-form', r'gravityforms'],
        'wordpress_wpforms': [r'wpforms', r'wp-forms'],
        'wordpress_ninja': [r'ninja-forms', r'nf-form'],
        'hubspot': [r'hs-form', r'hubspot', r'hsforms'],
        'jotform': [r'jotform', r'form-all'],
        'typeform': [r'typeform'],
        'google_forms': [r'docs\.google\.com/forms'],
        'mailchimp': [r'mailchimp', r'mc-embedded'],
        'formidable': [r'frm_form', r'formidable'],
        'elementor': [r'elementor-form'],
        'divi': [r'et_pb_contact_form'],
    }
    
    # Honeypot detection patterns (fields that should be left empty)
    HONEYPOT_PATTERNS = [
        r'\bhoney\b', r'\bpot\b', r'\btrap\b', r'\bhoneypot\b',
        r'\bwebsite\b', r'\burl\b', r'\baddress2\b', r'\bfax\b',
        r'\bleave.?blank\b', r'\bdo.?not.?fill\b'
    ]
    
    # CAPTCHA detection selectors
    CAPTCHA_SELECTORS = {
        ProtectionType.RECAPTCHA_V2: [
            '.g-recaptcha', 'iframe[src*="recaptcha"]', '#recaptcha',
            '[data-sitekey]'
        ],
        ProtectionType.RECAPTCHA_V3: [
            '.grecaptcha-badge', 'script[src*="recaptcha/api.js?render="]'
        ],
        ProtectionType.HCAPTCHA: [
            '.h-captcha', 'iframe[src*="hcaptcha"]'
        ],
        ProtectionType.TURNSTILE: [
            '.cf-turnstile', 'iframe[src*="turnstile"]'
        ],
    }
    
    def __init__(self):
        self.compiled_patterns = {}
        self._compile_patterns()
    
    def _compile_patterns(self):
        """Pre-compile regex patterns for efficiency."""
        for field_type, patterns in self.FIELD_PATTERNS.items():
            self.compiled_patterns[field_type] = [
                re.compile(p, re.IGNORECASE) for p in patterns
            ]
    
    @staticmethod
    def validate_url(url: str, business_website: str = None) -> Tuple[bool, str, str]:
        """
        Validate if a URL is suitable for contact form submission.
        
        Args:
            url: The contact form URL to validate
            business_website: The business's actual website (optional)
        
        Returns:
            Tuple of (is_valid, url_type, reason)
            - is_valid: True if URL is suitable for form submission
            - url_type: 'direct', 'directory', 'social', 'blog', 'mismatch'
            - reason: Human-readable explanation
        """
        if not url or not url.strip():
            return False, 'none', "No URL provided"
        
        url = url.strip().lower()
        
        # Extract domain
        try:
            parsed = urlparse(url)
            domain = parsed.netloc or parsed.path.split('/')[0]
            if domain.startswith('www.'):
                domain = domain[4:]
        except:
            return False, 'invalid', "Could not parse URL"
        
        # Check against directory domains
        for dir_domain in DIRECTORY_DOMAINS:
            if domain == dir_domain or domain.endswith('.' + dir_domain):
                return False, 'directory', f"URL is on directory site: {dir_domain}"
        
        # Check against blog platforms
        for blog_domain in BLOG_PLATFORMS:
            if domain == blog_domain or domain.endswith('.' + blog_domain):
                return False, 'blog', f"URL is on blog platform: {blog_domain}"
        
        # Check domain mismatch if business website provided
        if business_website:
            try:
                biz_parsed = urlparse(business_website.lower())
                biz_domain = biz_parsed.netloc or biz_parsed.path.split('/')[0]
                if biz_domain.startswith('www.'):
                    biz_domain = biz_domain[4:]
                
                # Check if domains match
                if domain != biz_domain and not domain.endswith('.' + biz_domain) and not biz_domain.endswith('.' + domain):
                    return False, 'mismatch', f"Domain mismatch: {domain} != {biz_domain}"
            except:
                pass
        
        return True, 'direct', "URL appears valid for contact form"
    
    def _match_field_type(self, text: str) -> Optional[FieldType]:
        """Match text against field patterns to determine type."""
        if not text:
            return None
        
        for field_type, patterns in self.compiled_patterns.items():
            for pattern in patterns:
                if pattern.search(text):
                    return field_type
        
        return None
    
    async def analyze_form(self, page) -> FormAnalysis:
        """
        Analyze a page to detect and map contact form fields.
        
        Args:
            page: Playwright page object
            
        Returns:
            FormAnalysis with detected fields and metadata
        """
        analysis = FormAnalysis()
        
        # Detect form builder first (helps with field detection)
        analysis.form_builder = await self._detect_form_builder(page)
        
        # Detect CAPTCHA protection
        analysis.protection_type = await self._detect_protection(page)
        
        # Find the main form
        form_selector = await self._find_main_form(page)
        analysis.form_selector = form_selector
        
        # Detect fields
        analysis.fields = await self._detect_fields(page, form_selector)
        
        # Detect honeypot fields
        analysis.honeypot_selectors = await self._detect_honeypots(page, form_selector)
        
        # Find submit button
        analysis.submit_selector = await self._find_submit_button(page, form_selector)
        
        # Calculate confidence and check for issues
        analysis = self._evaluate_analysis(analysis)
        
        return analysis
    
    async def _detect_form_builder(self, page) -> Optional[str]:
        """Detect which form builder was used."""
        html = await page.content()
        
        for builder, patterns in self.FORM_BUILDER_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, html, re.IGNORECASE):
                    return builder
        
        return None
    
    async def _detect_protection(self, page) -> ProtectionType:
        """Detect CAPTCHA or other protection mechanisms."""
        for protection_type, selectors in self.CAPTCHA_SELECTORS.items():
            for selector in selectors:
                try:
                    element = await page.query_selector(selector)
                    if element:
                        return protection_type
                except:
                    continue
        
        return ProtectionType.NONE
    
    async def _find_main_form(self, page) -> Optional[str]:
        """Find the main contact form on the page."""
        # Try common form selectors
        selectors = [
            'form[action*="contact"]',
            'form[id*="contact"]',
            'form[class*="contact"]',
            'form[action*="submit"]',
            '#contact-form',
            '.contact-form',
            '#contactForm',
            '.contactForm',
            'form[method="post"]',
            'form',  # Fallback to any form
        ]
        
        for selector in selectors:
            try:
                forms = await page.query_selector_all(selector)
                for form in forms:
                    # Check if form has inputs (not just a search form)
                    inputs = await form.query_selector_all('input, textarea')
                    if len(inputs) >= 2:  # At least 2 fields
                        # Return a unique selector for this form
                        form_id = await form.get_attribute('id')
                        if form_id:
                            return f'#{form_id}'
                        form_class = await form.get_attribute('class')
                        if form_class:
                            first_class = form_class.split()[0]
                            return f'form.{first_class}'
                        return selector
            except:
                continue
        
        return 'form'  # Default fallback
    
    async def _detect_fields(self, page, form_selector: Optional[str]) -> List[FieldMapping]:
        """Detect and classify form fields."""
        fields = []
        base_selector = form_selector if form_selector else 'body'
        
        # Find all input fields
        input_selectors = [
            f'{base_selector} input[type="text"]',
            f'{base_selector} input[type="email"]',
            f'{base_selector} input[type="tel"]',
            f'{base_selector} input:not([type])',
            f'{base_selector} textarea',
            f'{base_selector} select',
        ]
        
        seen_selectors = set()
        
        for selector_pattern in input_selectors:
            try:
                elements = await page.query_selector_all(selector_pattern)
                
                for element in elements:
                    field_mapping = await self._analyze_field(page, element)
                    if field_mapping and field_mapping.selector not in seen_selectors:
                        seen_selectors.add(field_mapping.selector)
                        fields.append(field_mapping)
            except:
                continue
        
        return fields
    
    async def _analyze_field(self, page, element) -> Optional[FieldMapping]:
        """Analyze a single form field element."""
        try:
            # Get element attributes
            tag_name = await element.evaluate('el => el.tagName.toLowerCase()')
            element_type = tag_name
            
            name_attr = await element.get_attribute('name') or ''
            id_attr = await element.get_attribute('id') or ''
            class_attr = await element.get_attribute('class') or ''
            placeholder = await element.get_attribute('placeholder') or ''
            input_type = await element.get_attribute('type') or 'text'
            required = await element.get_attribute('required') is not None
            maxlength = await element.get_attribute('maxlength')
            
            # Skip hidden fields and buttons
            if input_type in ['hidden', 'submit', 'button', 'reset']:
                return None
            
            # Check if field is visible
            is_visible = await element.is_visible()
            if not is_visible:
                return None
            
            # Try to find associated label
            label_text = await self._find_label(page, element, id_attr)
            
            # Determine field type from multiple sources
            field_type = self._determine_field_type(
                name_attr, id_attr, class_attr, placeholder, label_text, input_type, tag_name
            )
            
            # Build selector for this field
            selector = self._build_selector(name_attr, id_attr, class_attr, tag_name)
            
            return FieldMapping(
                field_type=field_type,
                selector=selector,
                element_type=element_type,
                is_required=required,
                max_length=int(maxlength) if maxlength else None,
                placeholder=placeholder,
                label=label_text,
                confidence=0.8 if field_type != FieldType.UNKNOWN else 0.3
            )
            
        except Exception as e:
            return None
    
    async def _find_label(self, page, element, element_id: str) -> Optional[str]:
        """Find the label text associated with an input field."""
        if element_id:
            try:
                label = await page.query_selector(f'label[for="{element_id}"]')
                if label:
                    return await label.inner_text()
            except:
                pass
        
        # Try to find label as parent or sibling
        try:
            parent = await element.evaluate('''el => {
                let parent = el.parentElement;
                while (parent) {
                    if (parent.tagName === 'LABEL') {
                        return parent.innerText;
                    }
                    // Check siblings
                    let prev = el.previousElementSibling;
                    if (prev && prev.tagName === 'LABEL') {
                        return prev.innerText;
                    }
                    parent = parent.parentElement;
                }
                return null;
            }''')
            if parent:
                return parent.strip()[:100]  # Limit length
        except:
            pass
        
        return None
    
    def _determine_field_type(self, name: str, id_attr: str, class_attr: str,
                              placeholder: str, label: Optional[str],
                              input_type: str, tag_name: str) -> FieldType:
        """Determine field type from various attributes."""
        # Check input type first (most reliable for email/phone)
        if input_type == 'email':
            return FieldType.EMAIL
        if input_type == 'tel':
            return FieldType.PHONE
        
        # Textarea is usually message
        if tag_name == 'textarea':
            return FieldType.MESSAGE
        
        # Check all text sources
        all_text = ' '.join(filter(None, [name, id_attr, class_attr, placeholder, label]))
        
        # Try to match against patterns
        field_type = self._match_field_type(all_text)
        if field_type:
            return field_type
        
        return FieldType.UNKNOWN
    
    def _build_selector(self, name: str, id_attr: str, class_attr: str, tag_name: str) -> str:
        """Build a reliable CSS selector for a field."""
        if id_attr:
            return f'#{id_attr}'
        if name:
            return f'{tag_name}[name="{name}"]'
        if class_attr:
            first_class = class_attr.split()[0]
            return f'{tag_name}.{first_class}'
        return tag_name
    
    async def _detect_honeypots(self, page, form_selector: Optional[str]) -> List[str]:
        """Detect honeypot fields that should be left empty."""
        honeypots = []
        base = form_selector if form_selector else 'body'
        
        try:
            # Find hidden inputs or inputs with honeypot-like names
            inputs = await page.query_selector_all(f'{base} input')
            
            for inp in inputs:
                name = await inp.get_attribute('name') or ''
                id_attr = await inp.get_attribute('id') or ''
                style = await inp.evaluate('el => window.getComputedStyle(el).display')
                
                # Check if hidden
                if style == 'none':
                    selector = f'#{id_attr}' if id_attr else f'input[name="{name}"]'
                    honeypots.append(selector)
                    continue
                
                # Check for honeypot patterns in name/id
                for pattern in self.HONEYPOT_PATTERNS:
                    if re.search(pattern, name + id_attr, re.IGNORECASE):
                        selector = f'#{id_attr}' if id_attr else f'input[name="{name}"]'
                        honeypots.append(selector)
                        break
                        
        except:
            pass
        
        return honeypots
    
    async def _find_submit_button(self, page, form_selector: Optional[str]) -> Optional[str]:
        """Find the form submit button."""
        base = form_selector if form_selector else 'body'
        
        # Try various submit button selectors
        selectors = [
            f'{base} button[type="submit"]',
            f'{base} input[type="submit"]',
            f'{base} button:has-text("Submit")',
            f'{base} button:has-text("Send")',
            f'{base} button:has-text("Contact")',
            f'{base} .submit-button',
            f'{base} .btn-submit',
            f'{base} button',  # Fallback
        ]
        
        for selector in selectors:
            try:
                button = await page.query_selector(selector)
                if button and await button.is_visible():
                    return selector
            except:
                continue
        
        return None
    
    def _evaluate_analysis(self, analysis: FormAnalysis) -> FormAnalysis:
        """Evaluate the analysis and set confidence/issues."""
        issues = []
        confidence_factors = []
        
        # Check for required fields
        if not analysis.get_field(FieldType.EMAIL):
            issues.append("No email field detected")
            analysis.requires_manual = True
        else:
            confidence_factors.append(0.3)
        
        if not analysis.get_field(FieldType.MESSAGE):
            issues.append("No message field detected")
            analysis.requires_manual = True
        else:
            confidence_factors.append(0.3)
        
        # Check for name field
        if not (analysis.get_field(FieldType.NAME) or 
                analysis.get_field(FieldType.FIRST_NAME)):
            issues.append("No name field detected")
            confidence_factors.append(0.1)
        else:
            confidence_factors.append(0.2)
        
        # Check for submit button
        if not analysis.submit_selector:
            issues.append("No submit button found")
            analysis.requires_manual = True
        else:
            confidence_factors.append(0.2)
        
        # Check for CAPTCHA
        if analysis.protection_type not in [ProtectionType.NONE, ProtectionType.HONEYPOT]:
            issues.append(f"CAPTCHA detected: {analysis.protection_type.value}")
            analysis.requires_manual = True
        
        # Calculate confidence
        analysis.confidence = sum(confidence_factors) if confidence_factors else 0.0
        analysis.issues = issues
        
        return analysis


async def detect_form_fields(page) -> FormAnalysis:
    """
    Convenience function to detect form fields on a page.
    
    Args:
        page: Playwright page object
        
    Returns:
        FormAnalysis with detected fields
    """
    detector = FormDetector()
    return await detector.analyze_form(page)


if __name__ == "__main__":
    print("Form Detector Module")
    print("Use with Playwright page object:")
    print("  analysis = await detect_form_fields(page)")
    print("  print(analysis.fields)")
