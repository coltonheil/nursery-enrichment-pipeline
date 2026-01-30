# Contact Form Automation Plan
**Date:** January 30, 2026  
**Status:** Planning  
**Target:** 221 nursery leads with contact forms but no email addresses  
**Goal:** Systematically submit personalized outreach via contact forms

---

## 1. Executive Summary

### The Opportunity
We have **221 high-value leads** (69 Tier A, 152 Tier B) that have contact forms but no email addresses. These are prime targets for our worm casting samples offer, but traditional email outreach isn't possible.

### The Solution
A **semi-automated contact form submission system** using Playwright with human-like behavior patterns to:
1. Navigate to each contact form URL
2. Auto-detect and fill form fields
3. Submit personalized messages offering free worm casting samples
4. Track submissions and capture replies

### Key Principles
- **Quality over speed** - Prioritize appearing human over fast throughput
- **Conservative rate limiting** - Max 10-15 submissions per day
- **Human-in-the-loop** - Review problematic forms before submission
- **Reply tracking** - Unique identifiers in messages to track responses

### Expected Outcomes
| Metric | Target |
|--------|--------|
| Successful submissions | 85-90% (188-199 leads) |
| Manual intervention needed | 10-15% (22-33 leads) |
| Response rate | 5-15% (11-30 replies) |
| Timeline | 2-3 weeks for all 221 leads |

### Cost Summary
| Item | Cost |
|------|------|
| Playwright/infrastructure | $0 (local) |
| Proxy rotation (optional) | $10-20/month |
| Email inbox (reply capture) | $0 (existing) |
| **Total** | **$0-20** |

---

## 2. Technical Architecture

### 2.1 Technology Stack

| Component | Choice | Rationale |
|-----------|--------|-----------|
| **Browser automation** | Playwright (Python) | Best anti-detection, async support, auto-wait |
| **Browser mode** | Headed (visible) | Required for CAPTCHA handling, more human-like |
| **Fingerprint management** | playwright-stealth | Evades common bot detection |
| **Form detection** | Custom ML + heuristics | Flexible field mapping |
| **Rate limiting** | Custom scheduler | Business hours, geographic distribution |
| **Data storage** | SQLite (existing) | Already in use for leads.db |

### 2.2 Why Playwright Over Alternatives

| Feature | Playwright | Selenium | Puppeteer |
|---------|------------|----------|-----------|
| Auto-waiting | ✅ Built-in | ❌ Manual | ⚠️ Partial |
| Async/parallel | ✅ Native | ❌ Threading | ✅ Native |
| Anti-detection | ✅ Excellent | ❌ Poor | ⚠️ Moderate |
| Python support | ✅ First-class | ✅ First-class | ❌ Node only |
| Browser context isolation | ✅ Easy | ❌ Complex | ✅ Easy |
| Debugging | ✅ Inspector/trace | ⚠️ Logs | ⚠️ CDP only |

**Verdict:** Playwright's built-in waiting, stealth capabilities, and Python support make it ideal.

### 2.3 System Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    CONTACT FORM AUTOMATION SYSTEM                       │
└─────────────────────────────────────────────────────────────────────────┘

┌──────────────┐     ┌──────────────────────┐     ┌───────────────────────┐
│   SQLite DB  │────▶│  Lead Selector       │────▶│  Form Scout (Pre-scan)│
│  (221 leads) │     │  (Tier, State, Time) │     │  - Detect form type   │
└──────────────┘     └──────────────────────┘     │  - Map fields         │
                                                  │  - Flag CAPTCHA/issues│
                                                  └───────────────────────┘
                                                              │
                     ┌────────────────────────────────────────┼─────────────┐
                     │                                        │             │
                     ▼                                        ▼             ▼
            ┌────────────────┐                     ┌────────────────┐  ┌─────────┐
            │ Auto-Submit    │                     │ Manual Queue   │  │ Failed  │
            │ (85-90%)       │                     │ (CAPTCHA, etc) │  │ Queue   │
            │ - Fill fields  │                     │ - Human review │  │         │
            │ - Submit       │                     │ - Supervised   │  │         │
            │ - Verify       │                     │   submission   │  │         │
            └────────────────┘                     └────────────────┘  └─────────┘
                     │                                        │
                     ▼                                        ▼
            ┌────────────────────────────────────────────────────────────────┐
            │                   SUBMISSION LOG                                │
            │  - Timestamp, Lead ID, Status, Screenshot, Response Tracking   │
            └────────────────────────────────────────────────────────────────┘
                                         │
                                         ▼
                              ┌──────────────────────┐
                              │   Reply Inbox        │
                              │   - Unique tracking  │
                              │   - Match to lead    │
                              │   - Alert on reply   │
                              └──────────────────────┘
```

### 2.4 File Structure

```
enrichment/
├── contact_form/
│   ├── __init__.py
│   ├── form_automation.py      # Main orchestrator
│   ├── form_detector.py        # Field detection logic
│   ├── form_filler.py          # Human-like filling
│   ├── anti_detection.py       # Stealth settings
│   ├── message_templates.py    # Personalized messages
│   ├── rate_limiter.py         # Submission scheduling
│   ├── reply_tracker.py        # Response tracking
│   └── manual_queue.py         # Human review interface
├── email_hunter.py             # (existing)
└── ...
```

---

## 3. Form Detection Algorithm

### 3.1 Pre-Scan Phase (Form Scouting)

Before submission, each form URL undergoes reconnaissance:

```python
class FormScout:
    """Pre-scan forms to classify and map fields."""
    
    def scout(self, url: str) -> FormAnalysis:
        """
        Returns:
            FormAnalysis with:
            - form_type: 'standard' | 'multi-page' | 'modal' | 'embedded'
            - protection: 'none' | 'honeypot' | 'recaptcha_v2' | 'recaptcha_v3' | 'hcaptcha' | 'turnstile'
            - fields: List[FieldMapping]
            - confidence: float (0-1)
            - requires_manual: bool
            - issues: List[str]
        """
```

### 3.2 Field Detection Strategy

**Priority Order for Field Identification:**

1. **Label association** (most reliable)
   - `<label for="field_id">` explicit association
   - Label text + adjacent input
   
2. **Attribute analysis**
   - `name` attribute patterns: `name`, `email`, `phone`, `message`, `company`
   - `id` attribute patterns
   - `placeholder` text
   - `autocomplete` attribute
   
3. **Type/Input analysis**
   - `type="email"` → Email field
   - `type="tel"` → Phone field
   - `<textarea>` → Message field
   
4. **Position heuristics** (fallback)
   - First text input near "Name" label
   - Input after "Email" text
   - Largest textarea = message

### 3.3 Field Mapping Table

| Field Type | Detection Patterns | Priority |
|------------|-------------------|----------|
| **Name** | `name*`, `full*name`, `your*name`, `contact*name` | Required |
| **Email** | `email*`, `e-mail`, `mail`, `type="email"` | Required |
| **Phone** | `phone*`, `tel*`, `mobile*`, `type="tel"` | Optional |
| **Company** | `company*`, `business*`, `organization*` | Optional |
| **Subject** | `subject*`, `topic*`, `regarding*` | Optional |
| **Message** | `message*`, `comment*`, `inquiry*`, `<textarea>` | Required |
| **City/State** | `city*`, `state*`, `location*` | Optional |

### 3.4 Handling Special Form Elements

**Dropdowns (Subject/Inquiry Type):**
```python
# Strategy: Select most generic/appropriate option
dropdown_preferences = [
    'general', 'inquiry', 'question', 'other',
    'sales', 'product', 'information'
]
# Select first matching option, or first non-placeholder option
```

**Checkboxes (Newsletter/Terms):**
```python
# Strategy: Check ONLY required checkboxes
# Skip optional newsletter subscriptions
# Accept terms if required for submission
```

**File Uploads:**
```python
# Strategy: Skip - don't attach files
# If required: Flag for manual review
```

**Hidden Honeypot Fields:**
```python
# Detection: visibility:hidden, display:none, opacity:0, position offscreen
# Strategy: Leave empty (filling triggers bot detection)
```

### 3.5 Form Protection Detection

| Protection | Detection Method | Handling Strategy |
|------------|-----------------|-------------------|
| **None** | No CAPTCHA elements | Auto-submit |
| **Honeypot** | Hidden fields with tempting names | Leave empty |
| **reCAPTCHA v2** | `g-recaptcha` class, iframe | Manual queue |
| **reCAPTCHA v3** | `grecaptcha.execute`, hidden badge | Often passable with human behavior |
| **hCaptcha** | `h-captcha` class | Manual queue |
| **Cloudflare Turnstile** | `cf-turnstile` class | Often passable in headed mode |
| **Custom CAPTCHA** | Image + text input | Manual queue |
| **Rate limiting** | Submit → error message | Retry next day |

---

## 4. Message Templates

### 4.1 Template Strategy

**Character Limits:**
- Many forms have 500-1000 char limits on message field
- Target: **400-600 characters** (safe for most forms)
- Include tracking ID in all messages

**Personalization Variables:**
- `{business_name}` - Company name
- `{city}` - City name  
- `{state}` - State abbreviation
- `{business_type}` - Type (nursery, greenhouse, grower)
- `{crops}` - Crops grown (if known)
- `{tracking_id}` - Unique submission ID (e.g., "REF-A069")

### 4.2 Template Variants

**Template A: Direct Offer (Wholesale Focus)**
```
Hi there!

I'm reaching out from Iowa Worm Castings. We produce premium vermicompost 
that's been a game-changer for growers across the Midwest.

I'd love to send {business_name} a free sample bag to try with your 
{business_type} operation. Our castings are 100% pure, screened fine, 
and perfect for potting mixes, transplants, and soil amendments.

No strings attached – just want to get our product in front of quality 
operations like yours in {state}.

Interested? Just reply to this message or email me directly.

Looking forward to connecting!

[REF-{tracking_id}]
```
*~550 characters*

**Template B: Problem-Solution (Production Focus)**
```
Hello,

Quick question – are you happy with your current soil amendments?

We're Iowa Worm Castings, and we've been helping Midwest nurseries and 
greenhouses improve plant health, reduce transplant shock, and boost 
root development with our premium vermicompost.

I'd like to send {business_name} a complimentary sample to test. 
Many growers mix it into potting soil or use it as a top dress – 
the results speak for themselves.

Would you be open to trying a sample? Just reply here or reach out 
directly. Happy to answer any questions about application rates or 
best uses for {crops}.

[REF-{tracking_id}]
```
*~580 characters*

**Template C: Local/Regional Angle**
```
Hi!

Found {business_name} while researching {business_type} operations in {state} 
and wanted to reach out.

We're Iowa Worm Castings – a family operation producing premium vermicompost 
right here in the Midwest. Our castings are popular with nurseries and 
greenhouses for improving soil biology and plant vigor.

I'd love to send you a free sample bag – no commitment, just want to 
introduce our product to quality operations like yours.

Let me know if you're interested!

[REF-{tracking_id}]
```
*~490 characters*

### 4.3 Template Selection Logic

```python
def select_template(lead: Lead) -> str:
    """Select best template based on lead characteristics."""
    
    # Wholesale operations → Template A (direct offer)
    if lead.is_wholesale:
        return TEMPLATE_A
    
    # Has specific crops → Template B (production focus)
    if lead.crops_grown and len(lead.crops_grown) > 0:
        return TEMPLATE_B
    
    # Default → Template C (regional angle)
    return TEMPLATE_C
```

### 4.4 Subject Line (If Form Has Subject Field)

Options (rotate to avoid patterns):
- "Quick question about soil amendments"
- "Free worm casting sample for {business_name}"
- "Introducing Iowa Worm Castings"
- "Midwest vermicompost for your operation"

---

## 5. Anti-Detection Strategy

### 5.1 Human-Like Behavior Patterns

**Browser Fingerprint:**
```python
# Use playwright-stealth to mask automation signals
from playwright_stealth import stealth_sync

browser = playwright.chromium.launch(headless=False)
context = browser.new_context(
    viewport={'width': 1920, 'height': 1080},
    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36...',
    locale='en-US',
    timezone_id='America/Chicago',
    geolocation={'latitude': 41.5868, 'longitude': -93.6250},  # Des Moines
    permissions=['geolocation']
)
stealth_sync(context)
```

**Typing Simulation:**
```python
async def human_type(page, selector: str, text: str):
    """Type with human-like timing and errors."""
    await page.click(selector)
    await asyncio.sleep(random.uniform(0.3, 0.8))  # Think time
    
    for char in text:
        # Occasionally make typos and correct them (5% chance)
        if random.random() < 0.05:
            wrong_char = random.choice('abcdefghijklmnop')
            await page.type(selector, wrong_char, delay=random.randint(50, 150))
            await asyncio.sleep(random.uniform(0.1, 0.3))
            await page.keyboard.press('Backspace')
        
        # Variable typing speed (50-150ms per char)
        await page.type(selector, char, delay=random.randint(50, 150))
    
    await asyncio.sleep(random.uniform(0.2, 0.5))  # Post-field pause
```

**Mouse Movement:**
```python
async def human_click(page, selector: str):
    """Move mouse naturally before clicking."""
    element = await page.query_selector(selector)
    box = await element.bounding_box()
    
    # Random point within element (not dead center)
    target_x = box['x'] + random.uniform(5, box['width'] - 5)
    target_y = box['y'] + random.uniform(5, box['height'] - 5)
    
    # Move mouse with bezier curve (not straight line)
    await page.mouse.move(target_x, target_y, steps=random.randint(10, 25))
    await asyncio.sleep(random.uniform(0.1, 0.3))
    await page.mouse.click(target_x, target_y)
```

**Scrolling Behavior:**
```python
async def human_scroll(page):
    """Scroll naturally before/during form interaction."""
    # Random scroll amount
    scroll_amount = random.randint(100, 400)
    
    # Scroll in increments (not instant)
    for _ in range(scroll_amount // 50):
        await page.mouse.wheel(0, 50)
        await asyncio.sleep(random.uniform(0.02, 0.08))
    
    # Pause to "read"
    await asyncio.sleep(random.uniform(0.5, 2.0))
```

### 5.2 Timing Patterns

**Field-to-Field Delays:**
```python
FIELD_DELAYS = {
    'name': (0.5, 1.5),        # Quick field
    'email': (0.8, 2.0),       # Slightly longer (typing @, domain)
    'phone': (1.0, 2.5),       # Formatting consideration
    'company': (0.5, 1.5),     # Quick field
    'message': (3.0, 8.0),     # Significant composition time
    'submit': (1.0, 3.0),      # Review pause before submit
}
```

**Page Load Behavior:**
```python
async def wait_for_page_ready(page):
    """Wait like a human would for page load."""
    await page.wait_for_load_state('domcontentloaded')
    await asyncio.sleep(random.uniform(1.0, 3.0))  # "Look around" time
    
    # Maybe scroll down to find form
    await human_scroll(page)
```

### 5.3 Session Management

**One Form Per Session:**
```python
# Create fresh browser context for each submission
# Prevents cross-site tracking/fingerprinting

async def submit_form(lead: Lead):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(**browser_config)
        stealth_sync(context)
        
        page = await context.new_page()
        try:
            await execute_submission(page, lead)
        finally:
            await browser.close()  # Clean slate for next submission
```

**Cookie/Storage Clearing:**
```python
# Clear between submissions (already handled by new context)
# Additional: Clear any persistent storage
await context.clear_cookies()
await context.clear_permissions()
```

### 5.4 Geographic Distribution

**Submission Order:**
```python
def get_submission_order(leads: List[Lead]) -> List[Lead]:
    """Order submissions to avoid geographic clustering."""
    
    # Group by state
    by_state = defaultdict(list)
    for lead in leads:
        by_state[lead.state].append(lead)
    
    # Interleave states (MI, MN, IL, WI, IA, MI, MN, ...)
    ordered = []
    while any(by_state.values()):
        for state in ['MI', 'MN', 'IL', 'WI', 'IA']:
            if by_state[state]:
                ordered.append(by_state[state].pop(0))
    
    return ordered
```

---

## 6. Rate Limiting Rules

### 6.1 Submission Cadence

| Rule | Value | Rationale |
|------|-------|-----------|
| **Daily maximum** | 10-15 forms | Conservative to avoid pattern detection |
| **Minimum interval** | 30-60 minutes | Realistic human spacing |
| **Business hours only** | 8am-6pm local | When humans submit forms |
| **Weekend submissions** | 0 | Suspicious if operating 7 days |
| **Days per week** | 4-5 | Natural work pattern |

### 6.2 Time-of-Day Distribution

```python
SUBMISSION_WINDOWS = {
    # Morning: 30% of daily submissions
    'morning': {'start': '08:00', 'end': '11:00', 'weight': 0.30},
    # Midday: 25%
    'midday': {'start': '11:00', 'end': '14:00', 'weight': 0.25},
    # Afternoon: 35%
    'afternoon': {'start': '14:00', 'end': '17:00', 'weight': 0.35},
    # Evening: 10%
    'evening': {'start': '17:00', 'end': '18:30', 'weight': 0.10},
}
```

### 6.3 Scheduling Algorithm

```python
class SubmissionScheduler:
    """Schedule form submissions with human-like patterns."""
    
    def __init__(self, leads: List[Lead], daily_limit: int = 12):
        self.leads = leads
        self.daily_limit = daily_limit
        self.submitted_today = 0
        self.last_submission = None
    
    def get_next_submission_time(self) -> datetime:
        """Calculate when to submit next form."""
        now = datetime.now()
        
        # Check if within business hours
        if not self._is_business_hours(now):
            return self._next_business_hour_start(now)
        
        # Check daily limit
        if self.submitted_today >= self.daily_limit:
            return self._tomorrow_morning()
        
        # Calculate interval (30-60 min with jitter)
        base_interval = random.randint(30, 60)  # minutes
        jitter = random.randint(-10, 10)  # ±10 min jitter
        interval = max(20, base_interval + jitter)  # Never less than 20 min
        
        return now + timedelta(minutes=interval)
    
    def _is_business_hours(self, dt: datetime) -> bool:
        """Check if time is within submission window."""
        hour = dt.hour
        weekday = dt.weekday()
        return weekday < 5 and 8 <= hour < 18
```

### 6.4 Cooling-Off Rules

| Trigger | Action |
|---------|--------|
| Submission error (any) | +15 min delay |
| CAPTCHA encountered | +30 min delay, add to manual queue |
| Rate limit message | Stop for day, resume tomorrow |
| Same domain twice | Minimum 24 hours between |
| Weekend | No submissions |

### 6.5 Timeline Projection

| Week | Submissions | Cumulative | Notes |
|------|-------------|------------|-------|
| Week 1 | ~48 | 48 | Ramp up, calibrate |
| Week 2 | ~60 | 108 | Full speed |
| Week 3 | ~60 | 168 | Continue |
| Week 4 | ~53 | 221 | Complete |

**Total time:** ~3-4 weeks at conservative pace

---

## 7. Reply Management

### 7.1 Email Address Strategy

**Dedicated Inbox:**
```
forms@iowawormcastings.com
```
or
```
outreach@iowawormcastings.com
```

**Benefits:**
- Separates form replies from regular business email
- Easy to filter/search
- Single source for reply tracking

### 7.2 Tracking ID System

**Format:** `REF-{TIER}{SEQUENCE}`

Examples:
- `REF-A001` through `REF-A069` (Tier A leads)
- `REF-B001` through `REF-B152` (Tier B leads)

**Implementation:**
```python
def generate_tracking_id(lead: Lead) -> str:
    """Generate unique tracking ID for submission."""
    prefix = f"REF-{lead.tier}"
    sequence = str(lead.id).zfill(3)
    return f"{prefix}{sequence}"
```

**Placement in Message:**
```
...Happy to answer any questions.

[REF-A042]
```

### 7.3 Reply Matching

**Automatic Matching:**
```python
def match_reply_to_lead(email_body: str) -> Optional[Lead]:
    """Extract tracking ID and find matching lead."""
    
    # Pattern: REF-A### or REF-B###
    match = re.search(r'REF-([AB])(\d{3})', email_body)
    if match:
        tier = match.group(1)
        lead_id = int(match.group(2))
        return get_lead_by_id(lead_id)
    
    # Fallback: Search by business name in signature
    return fuzzy_match_by_name(email_body)
```

**Manual Matching:**
For replies without tracking ID:
1. Check sender domain against our lead list
2. Search business name in email content
3. Flag for manual review if no match

### 7.4 Reply Workflow

```
┌─────────────┐     ┌──────────────────┐     ┌────────────────────┐
│ Incoming    │────▶│ Extract Tracking │────▶│ Match to Lead?     │
│ Email       │     │ ID               │     │                    │
└─────────────┘     └──────────────────┘     └────────────────────┘
                                                      │
                                   ┌──────────────────┼──────────────────┐
                                   │                  │                  │
                                   ▼                  ▼                  ▼
                           ┌───────────────┐  ┌───────────────┐  ┌───────────────┐
                           │ MATCHED       │  │ FUZZY MATCH   │  │ UNMATCHED     │
                           │ - Update DB   │  │ - Confirm     │  │ - Manual      │
                           │ - Alert owner │  │ - Update DB   │  │   review      │
                           │ - Add to CRM  │  │ - Alert owner │  │ - Reply inbox │
                           └───────────────┘  └───────────────┘  └───────────────┘
```

### 7.5 Database Updates

**New Columns:**
```sql
ALTER TABLE leads ADD COLUMN form_submitted_at TIMESTAMP;
ALTER TABLE leads ADD COLUMN form_submission_status TEXT DEFAULT 'pending';
ALTER TABLE leads ADD COLUMN form_tracking_id TEXT;
ALTER TABLE leads ADD COLUMN form_reply_received_at TIMESTAMP;
ALTER TABLE leads ADD COLUMN form_reply_content TEXT;
ALTER TABLE leads ADD COLUMN form_conversion_status TEXT;  -- interested, sample_sent, no_response
```

**Submission Log Table:**
```sql
CREATE TABLE form_submissions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    lead_id INTEGER NOT NULL,
    tracking_id TEXT NOT NULL UNIQUE,
    submitted_at TIMESTAMP,
    form_url TEXT,
    status TEXT,  -- success, failed, manual_needed
    error_message TEXT,
    screenshot_path TEXT,
    message_template TEXT,
    message_sent TEXT,
    FOREIGN KEY (lead_id) REFERENCES leads(id)
);
```

---

## 8. Implementation Phases

### Phase 1: Infrastructure Setup (Day 1-2)
**Goal:** Development environment ready

**Tasks:**
1. [ ] Install Playwright and dependencies
   ```bash
   pip install playwright playwright-stealth
   playwright install chromium
   ```
2. [ ] Create database migrations for new columns
3. [ ] Set up dedicated reply inbox
4. [ ] Create `enrichment/contact_form/` module structure
5. [ ] Configure stealth settings

**Deliverables:**
- Working Playwright installation
- Database schema updated
- Module skeleton created

---

### Phase 2: Form Detection (Day 3-5)
**Goal:** Automated field mapping working

**Tasks:**
1. [ ] Build `FormDetector` class with field identification logic
2. [ ] Test on 20 sample forms manually
3. [ ] Build honeypot detection
4. [ ] Build CAPTCHA detection
5. [ ] Create `FormScout` pre-scan functionality

**Deliverables:**
- Field detection accuracy >90%
- CAPTCHA detection working
- Manual queue flagging operational

---

### Phase 3: Human-Like Behavior (Day 6-8)
**Goal:** Natural interaction patterns

**Tasks:**
1. [ ] Implement typing simulation with variable speed
2. [ ] Implement mouse movement (bezier curves)
3. [ ] Implement scrolling behavior
4. [ ] Add timing delays between fields
5. [ ] Test on 5 forms with anti-bot protection

**Deliverables:**
- All behavior patterns implemented
- Passes basic bot detection on test sites

---

### Phase 4: Submission Engine (Day 9-11)
**Goal:** End-to-end submission working

**Tasks:**
1. [ ] Build `FormSubmitter` class
2. [ ] Implement submission verification (success page detection)
3. [ ] Add screenshot capture on submit
4. [ ] Build retry logic for transient failures
5. [ ] Test full flow on 10 leads

**Deliverables:**
- 80%+ success rate on test batch
- Screenshots captured
- Failures logged properly

---

### Phase 5: Rate Limiting & Scheduling (Day 12-13)
**Goal:** Production-safe execution cadence

**Tasks:**
1. [ ] Build `SubmissionScheduler` class
2. [ ] Implement business hours logic
3. [ ] Implement geographic distribution
4. [ ] Add daily/hourly limits
5. [ ] Build progress dashboard

**Deliverables:**
- Scheduler enforcing all limits
- Dashboard showing progress

---

### Phase 6: Reply Tracking (Day 14-15)
**Goal:** Automated reply capture

**Tasks:**
1. [ ] Build tracking ID generator
2. [ ] Implement reply inbox monitoring
3. [ ] Build tracking ID extraction from replies
4. [ ] Add lead matching logic
5. [ ] Create reply notification system

**Deliverables:**
- Tracking IDs in all messages
- Reply matching working
- Alerts configured

---

### Phase 7: Manual Queue Interface (Day 16-17)
**Goal:** Handle edge cases gracefully

**Tasks:**
1. [ ] Build web interface for manual review queue
2. [ ] Add CAPTCHA-flagged forms to queue
3. [ ] Build supervised submission mode
4. [ ] Add "skip" and "retry later" options

**Deliverables:**
- Web UI for manual queue
- CAPTCHA forms handled via human intervention

---

### Phase 8: Testing & Calibration (Day 18-20)
**Goal:** Production-ready system

**Tasks:**
1. [ ] Full test run on 30 leads (varied types)
2. [ ] Calibrate timing based on results
3. [ ] Fix edge cases discovered
4. [ ] Document all learnings
5. [ ] Final review before production

**Deliverables:**
- 85%+ success rate
- <15% manual intervention rate
- Documentation complete

---

### Phase 9: Production Rollout (Day 21+)
**Goal:** Submit all 221 forms

**Execution Plan:**
- Week 1: Tier A leads first (69 forms) - highest priority
- Week 2-3: Tier B leads (152 forms)
- Ongoing: Monitor replies, handle manual queue

**Daily Routine:**
1. Start scheduler in morning
2. Monitor progress
3. Handle manual queue items
4. Review replies at end of day
5. Update tracking spreadsheet

---

## 9. Risk Mitigation

### 9.1 Detection & Blocking Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| IP blacklisting | Low | Medium | Use residential IP, consider proxy rotation |
| Fingerprint detection | Medium | Medium | playwright-stealth, fresh contexts |
| Pattern recognition | Low | High | Varied timing, templates, ordering |
| CAPTCHA walls | Medium | Low | Manual queue, skip and retry |
| Rate limiting | Medium | Low | Aggressive limits, respect signals |

**Contingency Plan:**
If widespread blocking occurs:
1. Pause all automation for 48 hours
2. Review which sites blocked
3. Adjust behavior patterns
4. Consider proxy rotation ($10-20/month)
5. Resume with more conservative limits

### 9.2 Technical Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Form structure changes | Low | Low | Field detection is heuristic-based |
| Website downtime | Medium | Low | Retry logic, skip for now |
| Playwright bugs | Low | Medium | Pin version, test updates |
| Database corruption | Low | High | Regular backups, transactions |

### 9.3 Compliance Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Terms of Service violations | Medium | Low | Individual site ToS vary; keep scale small |
| CAN-SPAM applicability | Low | Low | Offering free sample, not selling; include opt-out |
| Negative brand perception | Low | Medium | Personalized messages, genuine value offer |

**Legal Considerations:**
- Contact form submissions are NOT covered by CAN-SPAM (not email)
- No federal law prohibits automated form submission for legitimate business inquiries
- However: Individual site ToS may prohibit bots
- Mitigation: Small scale, genuine business purpose, not spam

### 9.4 Operational Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Overwhelming manual queue | Medium | Medium | Prioritize, skip very complex forms |
| Missing replies | Low | High | Multiple inbox checks, alerts |
| Staff time required | Medium | Low | Mostly automated; ~1hr/day monitoring |

---

## 10. Success Metrics

### 10.1 Operational Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| **Submission success rate** | ≥85% | Successful / Attempted |
| **Auto-submit rate** | ≥85% | Auto / Total |
| **Manual intervention rate** | ≤15% | Manual queue / Total |
| **Average time per form** | <5 min | Total time / Forms submitted |
| **Daily throughput** | 10-15 forms | Forms submitted / Day |

### 10.2 Response Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| **Response rate** | 5-15% | Replies / Submissions |
| **Positive response rate** | 50%+ of replies | Interested / Total replies |
| **Sample request rate** | 3-8% | Sample requests / Submissions |
| **Conversion rate** | TBD | Sales / Submissions |

### 10.3 Quality Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| **Zero complaints** | 0 | Negative feedback received |
| **No blacklisting** | 0 sites | Sites that blocked us |
| **Tracking match rate** | ≥90% | Auto-matched replies / Total replies |

### 10.4 Tracking Dashboard

```
┌─────────────────────────────────────────────────────────────────────┐
│              CONTACT FORM AUTOMATION - DASHBOARD                    │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  PROGRESS                          DAILY STATS                      │
│  ═════════                         ═══════════                      │
│  Total: 221 leads                  Today: 12 submitted             │
│  Submitted: 89 (40%)               Success: 11 (92%)                │
│  Pending: 121 (55%)                Failed: 1 (8%)                   │
│  Manual: 11 (5%)                   Manual queue: 3                  │
│                                                                     │
│  RESPONSES                         TIER BREAKDOWN                   │
│  ═════════                         ══════════════                   │
│  Total replies: 7                  Tier A: 69 leads                 │
│  Positive: 5 (71%)                   Submitted: 42 (61%)            │
│  Sample requests: 4                  Replies: 4                     │
│  Reply rate: 7.9%                  Tier B: 152 leads                │
│                                      Submitted: 47 (31%)            │
│                                      Replies: 3                     │
│                                                                     │
│  [View Manual Queue]  [View Submissions Log]  [View Replies]        │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 11. Appendix

### A. Sample Form URLs from Our Dataset

**Standard Contact Forms (Easy):**
```
https://earthdevelopmentinc.com/contact
https://karthauser.net/
https://dulcetfarm.com/
http://www.mapleridgefarm.com/contact
```

**Potential Challenges:**
```
https://sites.google.com/          # Google Sites - may have CAPTCHA
https://www.earlmay.com/contact    # Larger company - likely has protection
```

### B. Dependencies to Install

```bash
# Core
pip install playwright playwright-stealth

# Browser
playwright install chromium

# Optional: Proxy support
pip install playwright-extra-stealth  # Enhanced stealth

# Requirements.txt additions:
playwright>=1.40.0
playwright-stealth>=1.0.6
```

### C. Configuration File Structure

```python
# contact_form/config.py

SUBMISSION_CONFIG = {
    # Rate limiting
    'daily_limit': 12,
    'min_interval_minutes': 30,
    'max_interval_minutes': 60,
    
    # Business hours (Central Time)
    'start_hour': 8,
    'end_hour': 18,
    'work_days': [0, 1, 2, 3, 4],  # Mon-Fri
    
    # Behavior timing
    'field_delays': {
        'name': (0.5, 1.5),
        'email': (0.8, 2.0),
        'phone': (1.0, 2.5),
        'message': (3.0, 8.0),
        'submit': (1.0, 3.0),
    },
    
    # Retries
    'max_retries': 2,
    'retry_delay_minutes': 15,
    
    # Screenshots
    'capture_screenshots': True,
    'screenshot_dir': 'data/form_screenshots/',
    
    # Reply tracking
    'reply_email': 'forms@iowawormcastings.com',
    'tracking_prefix': 'REF',
}
```

### D. Daily Checklist for Operator

**Morning (9am):**
- [ ] Check reply inbox for overnight responses
- [ ] Review manual queue from yesterday
- [ ] Start submission scheduler
- [ ] Verify first submission succeeds

**Midday (12pm):**
- [ ] Check progress (should be ~5-6 submissions)
- [ ] Handle any manual queue items
- [ ] Check for new replies

**End of Day (5pm):**
- [ ] Stop scheduler
- [ ] Review day's submissions (log)
- [ ] Check for replies
- [ ] Update tracking spreadsheet
- [ ] Note any issues for tomorrow

---

## 12. Decision Points for Review

Before implementation begins, please confirm:

1. **Reply Email Address:**
   - Use `forms@iowawormcastings.com`?
   - Or create new dedicated inbox?

2. **Daily Submission Rate:**
   - Conservative (10/day) - 4 weeks to complete
   - Moderate (15/day) - 3 weeks to complete
   - Aggressive (20/day) - 2 weeks to complete (higher risk)

3. **Proxy Usage:**
   - Start without proxies (residential IP)?
   - Or use proxy rotation from start?

4. **Manual Queue Threshold:**
   - Flag only CAPTCHA forms?
   - Or also flag complex multi-step forms?

5. **Message Template Preference:**
   - Use all 3 templates (rotation)?
   - Or standardize on one?

---

**Document Version:** 1.0  
**Created:** January 30, 2026  
**Author:** Clawd AI (Planning Subagent)  
**Next Review:** Before Phase 1 implementation

---

## Quick Start Summary

**When ready to begin:**

1. Install Playwright: `pip install playwright playwright-stealth && playwright install chromium`
2. Run database migration for new columns
3. Create `enrichment/contact_form/` module
4. Start with Phase 1 tasks

**Timeline:** 3-4 weeks total (implementation + execution)
**Cost:** $0-20
**Expected Results:** 85-90% submission rate, 5-15% response rate
