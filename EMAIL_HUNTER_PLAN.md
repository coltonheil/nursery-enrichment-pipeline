# Email Hunter Module - Implementation Plan

**Date:** January 27, 2026  
**Status:** Planning  
**Target:** Increase owner email capture from 2.4% to 65-80%

---

## 1. Executive Summary

### The Problem
- **Current email capture rate:** 2.4% (222/9,074 leads)
- **Owner names available:** 496 leads (5.5%)
- **Websites available:** 3,309 leads (36%)
- **Tier breakdown:** A=191, B=465, C=973, U=7,445

Only scraping and Gemini extraction currently find emails, missing the vast majority of potential contacts.

### The Solution
A multi-layer email discovery and verification pipeline that:
1. **Pattern inference** - Generate likely email formats from owner names + domains
2. **API enrichment** - Use Hunter.io/Apollo for email finder services
3. **Enhanced web scraping** - Target contact pages, about pages, team pages
4. **SMTP verification** - Validate inferred emails before use
5. **Catch-all detection** - Identify domains that accept all emails

### Expected Results
| Metric | Current | Target | Improvement |
|--------|---------|--------|-------------|
| Email capture (Tier A) | ~20% | 85% | +325% |
| Email capture (Tier B) | ~15% | 75% | +400% |
| Email capture (All) | 2.4% | 65% | +2,600% |
| Verification accuracy | N/A | 97%+ | New |

### Estimated Costs
| Service | Monthly Cost | Per-Lead Cost | Notes |
|---------|--------------|---------------|-------|
| Hunter.io Starter | $34/mo | $0.017/email found | 2,000 credits/mo |
| DeBounce | Pay-as-you-go | $0.003/verification | No subscription |
| Total (1,000 leads/mo) | ~$50-75/mo | ~$0.05-0.075/lead | Blended cost |

**ROI:** At $5-50 potential value per qualified lead email, the investment pays for itself on the first 2-15 successful contacts per month.

---

## 2. Research Findings

### 2.1 Email Finding Best Practices

**Primary Methods (Industry Standard):**

1. **Pattern Inference (Free, High Volume)**
   - Most companies use predictable email patterns
   - Common patterns: `first.last@`, `first@`, `flast@`, `firstl@`, `f.last@`
   - Pattern detection: Look at existing known emails from domain to infer pattern
   - Success rate: 40-60% when pattern is known

2. **API Services (Paid, High Accuracy)**
   - Hunter.io: 107M+ verified professional emails, pattern detection built-in
   - Apollo.io: Living database with 270M+ contacts
   - Snov.io: Email finder + verification combo
   - Success rate: 60-80% for B2B contacts

3. **Web Scraping (Free, Variable)**
   - Contact pages often list owner/manager emails
   - About/Team pages may have direct emails
   - Footer emails (often generic: info@, contact@)
   - mailto: links in HTML
   - Success rate: 10-30%

4. **Social/LinkedIn (Manual, High Quality)**
   - LinkedIn profiles sometimes show emails
   - Twitter/X bios occasionally include contact info
   - Not automatable at scale without ToS issues

### 2.2 Email Verification Methods

**SMTP Verification (Direct Check):**
- Connects to mail server, simulates send without delivering
- Checks if mailbox exists
- **Pros:** Free, real-time, no third-party dependency
- **Cons:** Rate limits, some servers block, can't detect catch-all reliably
- **Accuracy:** 85-90%

**API Verification Services:**
- ZeroBounce, NeverBounce, DeBounce, EmailListVerify
- Additional checks: spam trap detection, disposable email detection, role account flagging
- **Pros:** Higher accuracy, catch-all detection, detailed results
- **Cons:** Cost per verification ($0.003-0.01)
- **Accuracy:** 97%+

**Catch-All Domain Detection:**
- Some domains accept ALL emails (valid or not)
- Makes SMTP verification unreliable
- API services can detect catch-all status
- For catch-all domains: Must use pattern inference + social proof

### 2.3 Legal & Compliance

**CAN-SPAM Act (US - Primary Concern):**
- ✅ **Allows** cold emailing for commercial purposes
- ✅ **No consent required** before first email
- ⚠️ **Requirements:**
  - Accurate "From" and "Reply-To" headers
  - Honest subject lines
  - Physical postal address in email
  - Clear opt-out mechanism (honor within 10 business days)
  - Identify message as advertisement
- ⚠️ **Penalties:** Up to $53,088 per violation
- **Bottom line:** Scraped/inferred emails are LEGAL to use IF you follow CAN-SPAM rules

**GDPR (EU - Secondary):**
- Article 6(1)(f): "Legitimate Interests" basis for B2B marketing
- ✅ **B2B exception:** Business contact info can be processed without consent
- ⚠️ **Requirements:**
  - Must offer opt-out
  - Data minimization (only collect what's needed)
  - Clear privacy policy
  - Record of processing activities
- **Bottom line:** B2B cold email is generally allowed under legitimate interests

**Best Practices for Compliance:**
1. Never email scraped personal (non-business) addresses
2. Always include unsubscribe link
3. Honor opt-outs immediately
4. Document data sources
5. Don't resell scraped data
6. Use business domain emails only (avoid @gmail, @yahoo for first contact)

### 2.4 Technical Findings

**Hunter.io API Capabilities:**
```
Email Finder: domain + first_name + last_name → email
- Returns: email, confidence score (0-100), sources
- Cost: 1 credit per email found ($0.017 on Starter plan)
- Rate limit: 15 req/sec, 500 req/min

Domain Search: domain → all known emails
- Returns: up to 100 emails with names, positions, sources
- Cost: 1 credit per email returned
- Useful for: Pattern detection, alternative contacts

Email Verifier: email → verification status
- Returns: status (valid/invalid/accept_all/unknown), score
- Cost: 0.5 credits per verification
- Catches: deliverable, risky, invalid, catch-all
```

**DeBounce API (Verification):**
```
Single Verification: email → result
- Cost: 1 credit per validation (~$0.003)
- Results: deliverable, accept_all, unknown, invalid, disposable
- Catch-all detection: 10 credits per check
- Speed: 100k/hour processing
- Accuracy: 97.5% deliverability guarantee
```

**Email Pattern Detection:**
| Pattern Name | Format | Prevalence |
|--------------|--------|------------|
| first.last | john.smith@ | 35% |
| first | john@ | 25% |
| flast | jsmith@ | 15% |
| firstl | johns@ | 10% |
| first_last | john_smith@ | 8% |
| last.first | smith.john@ | 5% |
| Other | various | 2% |

---

## 3. Technical Architecture

### 3.1 Module Structure

```
enrichment/
├── email_hunter.py          # Main orchestrator
├── email_patterns.py        # Pattern generation & detection
├── email_verifier.py        # SMTP + API verification
├── hunter_client.py         # Hunter.io API wrapper
├── email_scraper.py         # Enhanced contact page scraping
└── __init__.py
```

### 3.2 Data Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                    EMAIL HUNTER PIPELINE                            │
└─────────────────────────────────────────────────────────────────────┘

┌──────────┐     ┌──────────────────┐     ┌───────────────────┐
│  Lead    │────▶│ Layer 1: Scrape  │────▶│ Email found?      │
│  Input   │     │ Contact Pages    │     │ YES → Verify      │
└──────────┘     └──────────────────┘     │ NO → Layer 2      │
                                          └───────────────────┘
                                                    │
                                                    ▼
┌──────────────────┐     ┌───────────────────┐     ┌───────────────────┐
│ Layer 2: Hunter  │────▶│ Email found?      │     │ Layer 3: Pattern  │
│ API Email Finder │     │ YES → Verify      │────▶│ Inference         │
└──────────────────┘     │ NO → Layer 3      │     └───────────────────┘
                         └───────────────────┘              │
                                                            ▼
┌──────────────────┐     ┌───────────────────┐     ┌───────────────────┐
│ Catch-all?       │◀────│ SMTP/API Verify   │◀────│ Generate Patterns │
│ YES → Confidence │     │ All Candidates    │     │ (5-8 variants)    │
│ NO → Best Valid  │     └───────────────────┘     └───────────────────┘
└──────────────────┘
         │
         ▼
┌──────────────────────────────────────────────────────────────────────┐
│ RESULT: email, verification_status, confidence, source, catch_all   │
└──────────────────────────────────────────────────────────────────────┘
```

### 3.3 Database Schema Additions

```sql
-- New columns for leads table
ALTER TABLE leads ADD COLUMN email_source TEXT;           -- 'scraped', 'hunter', 'pattern', 'gemini'
ALTER TABLE leads ADD COLUMN email_verification TEXT;     -- 'valid', 'invalid', 'risky', 'catch_all', 'unknown'
ALTER TABLE leads ADD COLUMN email_confidence INTEGER;    -- 0-100 confidence score
ALTER TABLE leads ADD COLUMN email_found_at TIMESTAMP;
ALTER TABLE leads ADD COLUMN domain_is_catchall BOOLEAN DEFAULT FALSE;
ALTER TABLE leads ADD COLUMN email_pattern TEXT;          -- Detected pattern for domain

-- Email candidates table (store all attempted patterns for debugging)
CREATE TABLE IF NOT EXISTS email_candidates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    lead_id INTEGER NOT NULL,
    email TEXT NOT NULL,
    source TEXT NOT NULL,                                 -- 'pattern', 'hunter', 'scrape'
    pattern_type TEXT,                                    -- 'first.last', 'first', etc.
    verification_status TEXT,
    verification_date TIMESTAMP,
    confidence INTEGER,
    selected BOOLEAN DEFAULT FALSE,
    FOREIGN KEY (lead_id) REFERENCES leads(id)
);

-- Domain patterns cache (avoid re-detecting patterns)
CREATE TABLE IF NOT EXISTS domain_patterns (
    domain TEXT PRIMARY KEY,
    detected_pattern TEXT,
    is_catchall BOOLEAN,
    sample_emails TEXT,                                   -- JSON array of known emails
    checked_at TIMESTAMP
);
```

### 3.4 Integration Points

**Existing Pipeline Integration:**
```python
# In app.py - Add email hunting step after Gemini enrichment

def run_email_hunting(lead_id, max_retries=3):
    """Hunt for owner email using multi-layer approach."""
    from enrichment.email_hunter import EmailHunter
    
    hunter = EmailHunter()
    result = hunter.find_email(lead_id)
    
    # Update lead with results
    update_lead_email(
        lead_id=lead_id,
        owner_email=result.get('email'),
        email_source=result.get('source'),
        email_verification=result.get('verification'),
        email_confidence=result.get('confidence'),
        domain_is_catchall=result.get('is_catchall', False)
    )
```

---

## 4. Implementation Phases

### Phase 1: Foundation (Week 1)
**Goal:** Set up infrastructure and basic pattern inference

**Tasks:**
1. Create database migrations for new columns
2. Implement `email_patterns.py`:
   - Pattern generator from name + domain
   - Pattern detector from existing emails
3. Implement basic SMTP verification
4. Create `email_hunter.py` orchestrator skeleton
5. Add `/email-hunt/start` and `/email-hunt/status` endpoints

**Deliverables:**
- [ ] Database schema updated
- [ ] Pattern generation working for 6+ patterns
- [ ] Basic SMTP verification functional
- [ ] Endpoint scaffolding complete

### Phase 2: Enhanced Scraping (Week 2)
**Goal:** Improve email extraction from websites

**Tasks:**
1. Enhance `web_scraper.py` to target:
   - Contact pages (`/contact`, `/contact-us`, `/about/contact`)
   - About pages (`/about`, `/about-us`, `/team`)
   - Team/Staff pages (`/team`, `/staff`, `/our-team`)
2. Add mailto: link extraction
3. Improve email regex patterns
4. Extract emails near owner names

**Deliverables:**
- [ ] Multi-page scraping for email discovery
- [ ] Improved email extraction regex
- [ ] Owner name proximity matching

### Phase 3: Hunter.io Integration (Week 3)
**Goal:** Add API-based email discovery

**Tasks:**
1. Create `hunter_client.py` with:
   - Email Finder API integration
   - Domain Search for pattern detection
   - Rate limiting and retry logic
2. Add Hunter API key to config
3. Implement credit tracking
4. Cache domain patterns

**Deliverables:**
- [ ] Hunter.io Email Finder working
- [ ] Domain pattern detection via Hunter
- [ ] Credit usage logging

### Phase 4: Verification Layer (Week 4)
**Goal:** Robust email verification pipeline

**Tasks:**
1. Create `email_verifier.py`:
   - SMTP verification with timeout handling
   - DeBounce API integration
   - Catch-all domain detection
2. Implement verification result caching
3. Add retry logic for transient failures
4. Create verification status dashboard

**Deliverables:**
- [ ] Dual verification (SMTP + API)
- [ ] Catch-all detection working
- [ ] Results cached to avoid re-verification

### Phase 5: Orchestration & Priority (Week 5)
**Goal:** Smart email hunting with prioritization

**Tasks:**
1. Implement cost-aware strategy:
   - Free methods first (scrape, pattern+SMTP)
   - Paid methods only when needed (Hunter)
2. Add tier-based priority:
   - Tier A: All methods, highest spend
   - Tier B: Most methods, moderate spend
   - Tier C/U: Free methods only
3. Confidence scoring algorithm
4. Best email selection logic

**Deliverables:**
- [ ] Tiered hunting strategy
- [ ] Cost tracking per lead
- [ ] Confidence-based email selection

### Phase 6: Testing & Optimization (Week 6)
**Goal:** Production-ready with metrics

**Tasks:**
1. Unit tests for all modules
2. Integration tests with mock APIs
3. Batch processing optimization
4. Performance benchmarking
5. Documentation and usage guide

**Deliverables:**
- [ ] Test coverage >80%
- [ ] Processing benchmark: 100+ leads/hour
- [ ] User documentation complete

---

## 5. Risk Mitigation

### 5.1 Legal Risks

| Risk | Mitigation | Priority |
|------|------------|----------|
| CAN-SPAM violation | Auto-add unsubscribe links, physical address in templates | HIGH |
| GDPR complaints | B2B-only emails, clear opt-out, data retention limits | MEDIUM |
| Spam trap hits | Use verification APIs with spam trap detection | HIGH |
| Blacklisting | Warm up sending domains, monitor reputation | HIGH |

**Recommended Actions:**
1. Add legal disclaimer to all outbound emails
2. Implement immediate unsubscribe processing
3. Never email personal Gmail/Yahoo addresses
4. Document all data sources for GDPR compliance

### 5.2 Technical Risks

| Risk | Mitigation | Priority |
|------|------------|----------|
| API rate limits | Implement exponential backoff, respect limits | HIGH |
| SMTP blocking | Rotate IPs, use verification APIs as fallback | MEDIUM |
| Catch-all false positives | Multi-layer verification, confidence scoring | HIGH |
| Cost overruns | Per-lead budget caps, tier-based spending | MEDIUM |

### 5.3 Deliverability Risks

| Risk | Mitigation | Priority |
|------|------------|----------|
| High bounce rate | Verify before sending, target <2% bounce | HIGH |
| Spam folder placement | Domain warmup, authentication (SPF/DKIM/DMARC) | HIGH |
| Low open rates | Clean subject lines, verified addresses only | MEDIUM |

---

## 6. API/Service Recommendations

### 6.1 Primary Recommendation: Hunter.io

**Why Hunter.io:**
- Best B2B email database (107M+ contacts)
- Pattern detection built-in
- Verification included
- Fair pricing for startups

**Recommended Plan:** Starter ($34/month)
- 2,000 credits/month
- Auto-verification included
- API access
- Cost per email: ~$0.017

**Usage Strategy:**
- Use Domain Search first to detect patterns (1 credit/10 emails)
- Use Email Finder for high-value Tier A/B leads
- Skip for Tier C/U (use pattern inference instead)

### 6.2 Verification: DeBounce

**Why DeBounce:**
- Pay-as-you-go (no subscription needed)
- $0.003/verification (very cheap)
- 97.5% accuracy guarantee
- Catch-all detection available

**Usage Strategy:**
- Verify all pattern-inferred emails before use
- Use catch-all detection for suspicious domains ($0.03)
- Skip verification for Hunter-verified emails

### 6.3 Cost Projections

**Monthly Volume: 500 Tier A/B Leads**

| Method | Volume | Unit Cost | Monthly Cost |
|--------|--------|-----------|--------------|
| Hunter Email Finder | 300 lookups | $0.017 | $5.10 |
| DeBounce Verification | 400 emails | $0.003 | $1.20 |
| DeBounce Catch-all | 50 domains | $0.03 | $1.50 |
| **Total** | | | **$7.80** |

Plus Hunter.io subscription: $34/month  
**Total monthly cost: ~$42**

### 6.4 Alternative Services

| Service | Use Case | Pricing | Notes |
|---------|----------|---------|-------|
| Apollo.io | All-in-one prospecting | Free tier available | Good for testing |
| Snov.io | Email finder + drip campaigns | $39/mo for 1,000 credits | Integrated platform |
| Clearbit | Enterprise enrichment | $99+/mo | Overkill for this use case |
| ZeroBounce | Bulk verification | $0.008/email | More expensive than DeBounce |

---

## 7. Success Metrics

### 7.1 Primary KPIs

| Metric | Baseline | Target | Measurement |
|--------|----------|--------|-------------|
| Email capture rate (Tier A) | 20% | 85% | Weekly |
| Email capture rate (Tier B) | 15% | 75% | Weekly |
| Email capture rate (overall) | 2.4% | 65% | Weekly |
| Verification accuracy | N/A | 97%+ | Per batch |
| Bounce rate on sends | Unknown | <2% | Per campaign |

### 7.2 Secondary KPIs

| Metric | Target | Measurement |
|--------|--------|-------------|
| Cost per verified email | <$0.10 | Monthly |
| Processing speed | 100+ leads/hour | Per run |
| API credit utilization | >80% | Monthly |
| Pattern inference success rate | 40%+ | Per batch |
| Scraping email discovery rate | 15%+ | Per batch |

### 7.3 Quality Gates

Before production rollout:
- [ ] Bounce rate on test batch <3%
- [ ] No spam trap hits
- [ ] Verification accuracy >95%
- [ ] Processing completes without errors
- [ ] Cost within budget projections

---

## 8. Code Scaffolding

### 8.1 File Structure

```
enrichment/
├── email_hunter.py          # Main orchestrator
├── email_patterns.py        # Pattern generation & detection
├── email_verifier.py        # SMTP + API verification
├── hunter_client.py         # Hunter.io API wrapper
├── email_scraper.py         # Enhanced contact page scraping
├── gemini_client.py         # (existing)
├── google_places.py         # (existing)
├── scorer.py                # (existing)
└── web_scraper.py           # (existing)
```

### 8.2 Key Classes & Functions

#### email_patterns.py

```python
"""Email pattern generation and detection."""

from typing import List, Dict, Optional
import re

# Common email patterns with prevalence weights
EMAIL_PATTERNS = [
    ('first.last', '{first}.{last}@{domain}', 0.35),
    ('first', '{first}@{domain}', 0.25),
    ('flast', '{f}{last}@{domain}', 0.15),
    ('firstl', '{first}{l}@{domain}', 0.10),
    ('first_last', '{first}_{last}@{domain}', 0.08),
    ('last.first', '{last}.{first}@{domain}', 0.05),
    ('f.last', '{f}.{last}@{domain}', 0.02),
]

def normalize_name(name: str) -> Dict[str, str]:
    """
    Parse and normalize owner name into components.
    
    Args:
        name: Full name like "John Smith" or "Dr. John P. Smith Jr."
        
    Returns:
        Dict with 'first', 'last', 'f' (first initial), 'l' (last initial)
    """
    # Remove titles and suffixes
    # Split into first/last
    # Handle edge cases (single name, multiple parts)
    pass

def generate_email_patterns(first_name: str, last_name: str, domain: str) -> List[Dict]:
    """
    Generate possible email addresses from name and domain.
    
    Args:
        first_name: First name
        last_name: Last name
        domain: Email domain (without @)
        
    Returns:
        List of dicts with 'email', 'pattern', 'weight'
    """
    pass

def detect_domain_pattern(known_emails: List[str], domain: str) -> Optional[str]:
    """
    Detect the email pattern used by a domain from known examples.
    
    Args:
        known_emails: List of known emails from this domain
        domain: The domain to analyze
        
    Returns:
        Pattern name (e.g., 'first.last') or None
    """
    pass

def extract_domain(url_or_email: str) -> str:
    """Extract domain from URL or email address."""
    pass
```

#### email_verifier.py

```python
"""Email verification via SMTP and API services."""

import socket
import smtplib
import dns.resolver
from typing import Dict, Optional
from enum import Enum

class VerificationStatus(Enum):
    VALID = 'valid'
    INVALID = 'invalid'
    RISKY = 'risky'
    CATCH_ALL = 'catch_all'
    UNKNOWN = 'unknown'

class EmailVerifier:
    """Multi-method email verification."""
    
    def __init__(self, debounce_api_key: Optional[str] = None):
        self.debounce_api_key = debounce_api_key
        self._mx_cache = {}
        
    def verify_email(self, email: str, use_api: bool = True) -> Dict:
        """
        Verify email address using SMTP and optionally API.
        
        Args:
            email: Email address to verify
            use_api: Whether to use paid API for verification
            
        Returns:
            Dict with 'status', 'is_catchall', 'confidence', 'method'
        """
        pass
    
    def smtp_verify(self, email: str) -> Dict:
        """
        Verify email using SMTP handshake.
        
        Connects to MX server and simulates RCPT TO without sending.
        """
        pass
    
    def api_verify(self, email: str) -> Dict:
        """Verify email using DeBounce API."""
        pass
    
    def check_mx_records(self, domain: str) -> List[str]:
        """Get MX records for domain."""
        pass
    
    def is_catchall_domain(self, domain: str) -> bool:
        """Check if domain accepts all emails."""
        pass
```

#### hunter_client.py

```python
"""Hunter.io API client for email finding and verification."""

import requests
from typing import Dict, List, Optional
import time

class HunterClient:
    """Hunter.io API wrapper with rate limiting."""
    
    BASE_URL = 'https://api.hunter.io/v2'
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self._last_request = 0
        self._min_interval = 0.1  # 10 requests/second max
        
    def find_email(self, domain: str, first_name: str, last_name: str) -> Dict:
        """
        Find email using Hunter Email Finder API.
        
        Args:
            domain: Company domain
            first_name: Person's first name
            last_name: Person's last name
            
        Returns:
            Dict with 'email', 'confidence', 'sources', 'found'
        """
        pass
    
    def domain_search(self, domain: str, limit: int = 10) -> Dict:
        """
        Search for all emails at a domain.
        
        Useful for pattern detection and alternative contacts.
        """
        pass
    
    def verify_email(self, email: str) -> Dict:
        """Verify email using Hunter's verification."""
        pass
    
    def _rate_limit(self):
        """Enforce rate limiting between requests."""
        pass
```

#### email_hunter.py

```python
"""Main email hunter orchestrator."""

from typing import Dict, Optional, List
from enum import Enum
import logging

from .email_patterns import generate_email_patterns, detect_domain_pattern
from .email_verifier import EmailVerifier, VerificationStatus
from .hunter_client import HunterClient
from .email_scraper import scrape_emails_from_site

logger = logging.getLogger(__name__)

class EmailSource(Enum):
    SCRAPED = 'scraped'
    GEMINI = 'gemini'
    HUNTER = 'hunter'
    PATTERN = 'pattern'

class EmailHunter:
    """
    Multi-layer email discovery pipeline.
    
    Layers (in order):
    1. Existing email from Gemini extraction
    2. Enhanced web scraping
    3. Hunter.io API lookup
    4. Pattern inference + verification
    """
    
    def __init__(
        self,
        hunter_api_key: Optional[str] = None,
        debounce_api_key: Optional[str] = None,
        tier_budgets: Optional[Dict[str, float]] = None
    ):
        self.hunter = HunterClient(hunter_api_key) if hunter_api_key else None
        self.verifier = EmailVerifier(debounce_api_key)
        
        # Default tier-based spending limits (per lead)
        self.tier_budgets = tier_budgets or {
            'A': 0.10,   # $0.10 per Tier A lead
            'B': 0.05,   # $0.05 per Tier B lead
            'C': 0.01,   # $0.01 per Tier C lead (pattern only)
            'U': 0.00,   # Free methods only for unscored
        }
        
    def find_email(
        self,
        owner_name: Optional[str],
        business_name: str,
        website: Optional[str],
        existing_email: Optional[str] = None,
        tier: str = 'U'
    ) -> Dict:
        """
        Find and verify email for a lead.
        
        Args:
            owner_name: Owner/contact full name
            business_name: Business name
            website: Business website URL
            existing_email: Email already extracted (from Gemini)
            tier: Lead tier for budget decisions
            
        Returns:
            Dict with:
                - email: Best email found (or None)
                - source: EmailSource enum value
                - verification: VerificationStatus
                - confidence: 0-100 score
                - is_catchall: Boolean
                - candidates: List of all emails tried
        """
        pass
    
    def _layer1_existing(self, existing_email: str) -> Dict:
        """Layer 1: Verify existing email from Gemini."""
        pass
    
    def _layer2_scrape(self, website: str) -> List[Dict]:
        """Layer 2: Scrape website for emails."""
        pass
    
    def _layer3_hunter(self, domain: str, first_name: str, last_name: str) -> Dict:
        """Layer 3: Hunter.io API lookup."""
        pass
    
    def _layer4_pattern(
        self, 
        first_name: str, 
        last_name: str, 
        domain: str
    ) -> List[Dict]:
        """Layer 4: Pattern inference + verification."""
        pass
    
    def _select_best_email(self, candidates: List[Dict]) -> Dict:
        """Select best email from candidates based on confidence and verification."""
        pass
```

#### email_scraper.py

```python
"""Enhanced email scraping from websites."""

import re
from typing import List, Dict, Optional
from urllib.parse import urljoin
from bs4 import BeautifulSoup

from .web_scraper import scrape_website

# Pages to check for contact info
CONTACT_PAGES = [
    '/contact',
    '/contact-us',
    '/about/contact',
    '/about-us',
    '/about',
    '/team',
    '/our-team',
    '/staff',
    '/leadership',
]

# Email regex pattern
EMAIL_REGEX = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'

def scrape_emails_from_site(
    base_url: str,
    owner_name: Optional[str] = None,
    max_pages: int = 5
) -> List[Dict]:
    """
    Scrape website for email addresses.
    
    Args:
        base_url: Website base URL
        owner_name: Owner name for proximity matching
        max_pages: Maximum pages to scrape
        
    Returns:
        List of dicts with 'email', 'page', 'context', 'confidence'
    """
    pass

def extract_emails_from_html(html: str, owner_name: Optional[str] = None) -> List[Dict]:
    """
    Extract emails from HTML content.
    
    Looks for:
    - mailto: links
    - Email regex matches
    - Emails near owner name
    """
    pass

def filter_generic_emails(emails: List[str]) -> List[str]:
    """Filter out generic emails like info@, contact@, sales@."""
    GENERIC_PREFIXES = ['info', 'contact', 'sales', 'support', 'admin', 'hello', 'team']
    return [e for e in emails if not any(e.lower().startswith(p + '@') for p in GENERIC_PREFIXES)]
```

### 8.3 Configuration

```python
# Add to .env.example
HUNTER_API_KEY=your_hunter_api_key_here
DEBOUNCE_API_KEY=your_debounce_api_key_here
EMAIL_HUNT_ENABLED=true
EMAIL_HUNT_TIER_A_BUDGET=0.10
EMAIL_HUNT_TIER_B_BUDGET=0.05
```

### 8.4 API Endpoints

```python
# Add to app.py

@app.route('/email-hunt/start', methods=['POST'])
def start_email_hunt():
    """Start email hunting for leads."""
    data = request.get_json() or {}
    batch_size = data.get('batch_size', 10)
    tier_filter = data.get('tier_filter', 'AB')  # Only hunt for Tier A/B by default
    # Start background job
    pass

@app.route('/email-hunt/stop', methods=['POST'])
def stop_email_hunt():
    """Stop email hunting job."""
    pass

@app.route('/email-hunt/status')
def email_hunt_status():
    """SSE endpoint for email hunt progress."""
    pass

@app.route('/api/lead/<int:lead_id>/hunt-email', methods=['POST'])
def hunt_single_email(lead_id):
    """Hunt email for a single lead."""
    pass
```

---

## 9. Next Steps

### Immediate (This Week)
1. [ ] Review and approve this plan
2. [ ] Set up Hunter.io account (free tier to start)
3. [ ] Set up DeBounce account (pay-as-you-go)
4. [ ] Create feature branch for email hunter

### Phase 1 Start (Next Week)
1. [ ] Create database migrations
2. [ ] Implement email_patterns.py
3. [ ] Basic SMTP verification
4. [ ] Integration test with 10 leads

### Before Production
1. [ ] Test on 100 leads across all tiers
2. [ ] Verify bounce rate <3%
3. [ ] Confirm no spam trap hits
4. [ ] Document actual costs vs projections

---

## Appendix A: Email Pattern Examples

**From Current Data:**
```
[email protected] → first.last@domain (custom domain)
GregsTreeFarm@yahoo.com → business@freemail (generic)
info@summerschristmastreefarm.com → generic
TreeDocJD@gmail.com → nickname@freemail
```

**Pattern Distribution:**
- Custom domain emails: ~40%
- Gmail/Yahoo/etc: ~35%
- Generic (info@, contact@): ~25%

**Recommendation:** Focus on custom domain emails for pattern inference. Skip freemail domains.

---

## Appendix B: Compliance Checklist

**Before First Campaign:**
- [ ] Physical address configured in email templates
- [ ] Unsubscribe link in all templates
- [ ] Opt-out processing automated
- [ ] Privacy policy updated
- [ ] Data source documented
- [ ] SPF/DKIM/DMARC configured on sending domain

**Ongoing:**
- [ ] Weekly bounce rate review (<2% target)
- [ ] Immediate unsubscribe processing
- [ ] Quarterly list cleaning
- [ ] Annual compliance review

---

**Document Version:** 1.0  
**Last Updated:** January 27, 2026  
**Author:** Clawd AI (Research Subagent)

## Key Takeaways from X Research (84 tweets analyzed, 62 relevant)

### 1. Recommended Tech Stack (from practitioners)

**Finding Emails:**
- Apollo.io - Free tier available, most recommended
- Hunter.io - $34-49/mo, good for cold email
- Outscraper - $20/mo for scraping
- Clay - For enrichment at scale (but has row limits)

**Verification:**
- NeverBounce - $0.003/email (most mentioned)
- ZeroBounce - Similar pricing
- "Always verify before sending" - consistent advice

**Sending:**
- Instantly ($37/mo) - for beginners
- Smartlead ($39/mo) - for scale
- Budget: $50-100/month total to start

### 2. Deliverability Tips (High-Engagement Posts)

1. **Email content ratio matters:**
   - Aim for 60% live text / 40% images
   - Pure image emails hurt deliverability
   - Include copyable text for discount codes

2. **Subdomain strategy:**
   - Use subdomains for cold outreach
   - Protects main domain reputation
   - Helps recover from deliverability hits

3. **Inbox management:**
   - Artemis tool: 99 Outlook inboxes per domain from single tenant
   - Microsoft 365 Business Basic: $4-6/user/month
   - Multiple inboxes spread risk

### 3. Tools Mentioned by Security/OSINT Community

- Hunter.io - "Bug bounty hunters use this daily for reconnaissance"
- Email discovery for OSINT: find patterns, verify addresses, domain search
- "Pattern analysis" is key for company emails

### 4. Compliance Mentioned

- GDPR compliance required
- CAN-SPAM requirements
- CASL (Canadian) considerations
- "Compliance mastery" seen as differentiator

### 5. Pain Points Identified

- Clay row limits (1M rows) frustrating users
- Building alternatives with:
  - Unlimited email finder
  - Unlimited email verification
  - Unlimited website scraping
  - Google Maps scraping

### 6. Success Patterns

- "Own the entire email ecosystem" - not just copywriting
- Full stack: deliverability + automation + segmentation + strategy
- "Control the whole system = no competition"

---

## Actionable Items for Our Email Hunter Module

Based on X research, we should:

1. **Use Apollo free tier first** - most validated by community
2. **NeverBounce for verification** - $0.003/email, highly recommended
3. **Implement pattern inference** - "pattern analysis is key"
4. **Add deliverability awareness** - text/image ratio guidance in exports
5. **Consider subdomain recommendations** for users

## Cost Benchmark (from X)
- Minimum viable: ~$50/month
- Scale setup: ~$100-150/month
- Per-email verification: $0.003
- Email finder: $0.01-0.05/email

---

**X Research Date:** 2026-01-27 15:23
**Tweets Analyzed:** 84 unique, 62 relevant
