# Nursery Enrichment Pipeline — Implementation Roadmap

## Current Status
- ✅ **Phase 1: Foundation** — Complete (upload, database, display leads)
- ✅ **Phase 2: Google Places Enrichment** — Complete (phone, website, ratings, hours)
- 🔄 **Phase 3+** — Starting now

---

## Architecture Principles

### Avoid Common Pitfalls
1. **Bot Detection** — Randomized delays, rotating user agents, respect rate limits
2. **Brittle Scraping** — Graceful failures, retry logic, don't break on edge cases
3. **Lost Progress** — Save after each operation, resume capability
4. **Bad AI Output** — Validate JSON, fallback values, store raw responses
5. **Scoring Opacity** — Show point breakdown, make scores explainable
6. **Export Mismatches** — Validate Instantly.ai format requirements

### Data Flow
```
Excel Import → Google Places → Website Scrape → Gemini Analysis → Scoring → Review → Personalization → Export
     ↓              ↓               ↓                ↓             ↓         ↓           ↓            ↓
  leads.db      +website       +website_text    +business_type   +score   +reviewed   +custom_line   CSV
               +phone          +scrape_status   +owner_name      +tier    +notes
               +hours                           +size_signals
                                               +negative_indicators
```

---

## Phase 3: Website Scraping

### 3A: Scraper Foundation
**Goal:** Build robust scraper that won't get blocked

**Create `enrichment/web_scraper.py`:**
```python
# Core scraper with:
# - 10 rotating user agents (Chrome, Firefox, Safari variants)
# - Random delay between 2-5 seconds per request
# - 15 second timeout
# - SSL verification disabled (many nursery sites have bad certs)
# - Redirect following (max 3)
# - Response size limit (5MB max)
```

**Database changes:**
- Add `website_text` (TEXT) — Scraped content
- Add `scrape_status` (TEXT) — pending/scraped/failed/skipped
- Add `scrape_error` (TEXT) — Error message if failed
- Add `scraped_at` (TIMESTAMP)

**Test:** Scrape 5 random leads manually, verify no blocks

---

### 3B: Content Extraction
**Goal:** Extract clean, useful text from HTML

**Enhance scraper to:**
- Fetch homepage + /about + /contact (3 pages max per site)
- Remove: scripts, styles, nav, header, footer, ads
- Extract: paragraphs, headings, list items, meta descriptions
- Combine into single text block (max 15,000 chars)
- Detect and skip non-English sites

**Test:** Compare raw HTML vs extracted text for 3 sites

---

### 3C: Batch Processing UI
**Goal:** Process all leads with progress visibility

**Add to Flask app:**
- Route: `/scrape/start` — Begin batch scraping
- Route: `/scrape/status` — SSE endpoint for live progress
- Route: `/scrape/stop` — Pause scraping (saves progress)

**Add to UI:**
- "Start Scraping" button (disabled if already running)
- Live progress: "Scraping 142/500 — Johnson's Nursery..."
- Success/fail counters updating in real-time
- "Pause" button to stop gracefully
- Resume capability (skips already-scraped leads)

**Test:** Scrape 50 leads, pause, resume, verify no duplicates

---

### 3D: Error Handling & Edge Cases
**Goal:** Handle real-world messiness

**Handle these cases:**
- No website URL → Skip, mark as "skipped"
- Connection timeout → Retry once, then mark "failed"
- 404/403/500 errors → Mark "failed" with error code
- SSL certificate errors → Try without verification
- JavaScript-only sites → Mark "failed-js" (can't scrape)
- Redirect loops → Abort after 3 redirects
- Empty content → Mark "failed-empty"
- Non-HTML response (PDF, image) → Skip

**Add logging:**
- Log each attempt to `processing_log` table
- Include: URL, status code, content length, error message

**Test:** Intentionally test with bad URLs, verify graceful handling

---

## Phase 4: Gemini AI Enrichment

### 4A: Gemini API Client
**Goal:** Reliable API wrapper with error handling

**Create `enrichment/gemini_client.py`:**
```python
# Wrapper for Gemini API with:
# - Retry logic (3 attempts with exponential backoff)
# - Rate limiting (respect 60 requests/minute free tier)
# - JSON response parsing with validation
# - Timeout handling (30 seconds)
# - Cost tracking (token counting)
```

**Test:** Send 5 test prompts, verify responses

---

### 4B: Enrichment Prompt Engineering
**Goal:** Reliable structured extraction

**The prompt must extract (from strategy doc):**
```json
{
  "owner_name": "string or null",
  "email": "string or null",
  "business_type": "wholesale_nursery|retail_nursery|container_production|grower_only|garden_center|cannabis_cultivator|landscape_supplier|christmas_tree_farm|sod_farm|orchard|tree_farm|mixed|unknown",
  "is_wholesale": "boolean",
  "is_retail": "boolean",
  "greenhouse_sqft": "integer or null",
  "acreage": "number or null",
  "multiple_locations": "boolean",
  "size_signals": ["array of text snippets"],
  "container_production": "boolean",
  "soil_relevance": "boolean",
  "organic_focus": "boolean",
  "crops_grown": ["array"],
  "negative_indicators": {
    "christmas_tree": "boolean",
    "sod_turf": "boolean",
    "bare_root": "boolean",
    "ball_and_burlap": "boolean",
    "landscaping_services": "boolean",
    "gift_shop": "boolean",
    "workshops_classes": "boolean",
    "orchard_upick": "boolean",
    "tree_farm_field": "boolean"
  },
  "appointment_only": "boolean",
  "closed_weekends": "boolean",
  "confidence": "low|medium|high"
}
```

**Prompt design principles:**
- Explicit JSON schema in prompt
- Few-shot examples (2-3)
- "Return ONLY valid JSON" instruction
- Fallback parsing if JSON is wrapped in markdown

**Test:** Run on 10 scraped websites, validate JSON output

---

### 4C: Database Schema for Enrichment
**Goal:** Store all extracted fields

**Add columns to leads table:**
- `owner_name` (TEXT)
- `owner_email` (TEXT)
- `business_type` (TEXT)
- `is_wholesale` (BOOLEAN)
- `is_retail` (BOOLEAN)
- `greenhouse_sqft` (INTEGER)
- `acreage` (REAL)
- `multiple_locations` (BOOLEAN)
- `container_production` (BOOLEAN)
- `soil_relevance` (BOOLEAN)
- `organic_focus` (BOOLEAN)
- `crops_grown` (TEXT) — JSON array
- `size_signals` (TEXT) — JSON array
- `negative_indicators` (TEXT) — JSON object
- `appointment_only` (BOOLEAN)
- `gemini_confidence` (TEXT)
- `gemini_raw_response` (TEXT) — Full response for debugging
- `gemini_enriched_at` (TIMESTAMP)
- `gemini_status` (TEXT) — pending/enriched/failed
- `gemini_error` (TEXT)

---

### 4D: Batch Gemini Processing
**Goal:** Process all scraped leads through Gemini

**Add to Flask app:**
- Route: `/enrich-ai/start` — Begin AI enrichment
- Route: `/enrich-ai/status` — SSE for progress
- Route: `/enrich-ai/stop` — Pause

**Processing logic:**
- Only process leads where `scrape_status = 'scraped'`
- Skip leads already enriched (`gemini_status = 'enriched'`)
- Rate limit: 1 request per second (safe for free tier)
- Save after each successful enrichment

**UI updates:**
- Progress bar with percentage
- Show current lead being processed
- Display success/fail counts
- Show sample of extracted data in real-time

**Test:** Run on 20 leads, verify data quality

---

## Phase 5: Scoring Engine

### 5A: Scoring Function
**Goal:** Implement full scoring model from strategy doc

**Create `enrichment/scorer.py`:**

**Positive signals (from strategy doc):**
| Signal | Points |
|--------|--------|
| is_wholesale = true | +35 |
| cannabis in business_type | +30 |
| closed_weekends = true (from Google hours) | +25 |
| greenhouse_sqft > 5000 | +25 |
| container_production = true | +25 |
| acreage mentioned | +20 |
| appointment_only = true | +20 |
| multiple_locations = true | +20 |
| soil_relevance = true | +15 |
| closed_saturday OR closed_sunday | +10 |
| state = 'WI' | +10 |
| no_hours_listed = true | +5 |

**Negative signals:**
| Signal | Points |
|--------|--------|
| christmas_tree = true | -30 |
| sod_turf = true | -30 |
| bare_root = true | -20 |
| ball_and_burlap = true | -20 |
| landscaping_services = true | -20 |
| gift_shop = true | -15 |
| workshops_classes = true | -15 |
| review_count > 100 | -10 |
| orchard_upick = true | -10 |
| tree_farm_field = true | -10 |

**Tier assignment:**
- Tier A: score >= 60
- Tier B: score 30-59
- Tier C: score < 30
- Tier U: insufficient data (no website OR gemini_status != 'enriched')

---

### 5B: Score Breakdown Storage
**Goal:** Make scores explainable

**Add columns:**
- `score` (INTEGER)
- `score_breakdown` (TEXT) — JSON showing each signal and points
- `tier` (TEXT) — A/B/C/U
- `scored_at` (TIMESTAMP)

**Breakdown format:**
```json
{
  "total": 72,
  "signals": [
    {"signal": "is_wholesale", "points": 35, "value": true},
    {"signal": "container_production", "points": 25, "value": true},
    {"signal": "soil_relevance", "points": 15, "value": true},
    {"signal": "gift_shop", "points": -15, "value": true},
    {"signal": "state_wi", "points": 10, "value": true}
  ],
  "tier": "A"
}
```

---

### 5C: Scoring UI
**Goal:** Score all leads and show distribution

**Add to Flask app:**
- Route: `/score/all` — Score all enriched leads
- Route: `/score/<lead_id>` — Rescore single lead

**UI updates:**
- "Score All Leads" button
- Tier distribution summary:
  - Tier A: 47 leads (7%)
  - Tier B: 234 leads (35%)
  - Tier C: 312 leads (46%)
  - Tier U: 85 leads (12%)
- Color-coded tier badges on lead list
- Click lead to see score breakdown

**Test:** Score all leads, verify distribution looks reasonable

---

## Phase 6: Review Interface

### 6A: Filterable Lead Table
**Goal:** Quickly find and review leads

**Enhance leads list:**
- Filter by: Tier, State, Business Type, Score Range
- Sort by: Score (desc), Business Name, City
- Search by: Business name
- Pagination (50 per page)
- Bulk select checkboxes

---

### 6B: Lead Detail Modal
**Goal:** See everything about a lead

**Modal shows:**
- All Google Places data
- All Gemini extracted data
- Score breakdown (visual)
- Scraped website text (collapsible)
- Raw Gemini response (collapsible, for debugging)
- Edit buttons for tier override

---

### 6C: Manual Override & Notes
**Goal:** Human-in-the-loop adjustments

**Add columns:**
- `tier_override` (TEXT) — Manual tier if different from calculated
- `review_notes` (TEXT) — Free text notes
- `reviewed_at` (TIMESTAMP)
- `reviewed_by` (TEXT) — For future multi-user

**UI:**
- Tier override dropdown in modal
- Notes text area
- "Mark Reviewed" button
- Visual indicator for reviewed vs unreviewed

---

### 6D: Bulk Actions
**Goal:** Efficiently process multiple leads

**Add:**
- "Select All on Page" checkbox
- Bulk actions dropdown:
  - Change tier to A/B/C
  - Mark as reviewed
  - Add to export queue
- Confirmation dialog for bulk changes

**Test:** Select 10 leads, bulk change tier, verify updates

---

## Phase 7: Email Personalization

### 7A: Personalization Prompt
**Goal:** Generate compelling first lines

**Prompt based on strategy doc:**
- Input: business_name, business_type, organic_focus, crops_grown, size_signals
- Output: Single line, max 15 words, references something specific
- Examples built into prompt

**Add columns:**
- `custom_line` (TEXT)
- `email_angle` (TEXT) — organic/wholesale/cannabis/etc
- `personalization_status` (TEXT)
- `personalization_generated_at` (TIMESTAMP)

---

### 7B: Batch Personalization
**Goal:** Generate lines for Tier A + B

**Processing:**
- Only process Tier A and B leads
- Only process leads with gemini_status = 'enriched'
- Rate limit same as enrichment

**UI:**
- "Generate Personalization" button
- Progress indicator
- Preview generated lines before export

---

## Phase 8: Export System

### 8A: CSV Export for Instantly.ai
**Goal:** Export ready-to-upload CSV

**CSV columns (from strategy doc):**
- email
- first_name
- last_name
- company_name
- phone
- website
- location
- custom_line (maps to {{Personalization}})
- tier (for reference)
- score (for reference)
- business_type (for reference)

**Export logic:**
- Filter: Only leads with email AND tier A or B
- Handle missing fields gracefully (empty string, not null)
- UTF-8 encoding
- Proper CSV escaping

---

### 8B: Export Configuration UI
**Goal:** Flexible export options

**UI:**
- Tier filter: A only, A+B, All
- Require email: Yes/No
- Require reviewed: Yes/No (for Tier A)
- Preview count before export
- Download button

**Add table:**
```sql
CREATE TABLE exports (
  id INTEGER PRIMARY KEY,
  filename TEXT,
  tier_filter TEXT,
  record_count INTEGER,
  created_at TIMESTAMP
);
```

---

### 8C: Excel Export Option
**Goal:** Backup/analysis export

**Export all data to Excel:**
- All columns
- All tiers
- Score breakdowns
- For your records and analysis

---

## Phase 9: Polish & Production Hardening

### 9A: Error Recovery
- Add retry buttons for failed operations
- "Retry All Failed" for batch operations
- Better error messages

### 9B: Logging & Debugging
- Comprehensive logging to file
- Debug mode toggle in UI
- Export logs for troubleshooting

### 9C: Rate Limit Handling
- Detect rate limit responses (429)
- Auto-pause and resume
- Show rate limit status in UI

### 9D: Data Validation
- Validate email format before export
- Flag suspicious data (e.g., obviously wrong business types)
- Data quality report

### 9E: Performance
- Database indexes for common queries
- Pagination everywhere
- Lazy loading for large text fields

---

## Implementation Order for Claude CLI

Give Claude CLI these prompts in order. Each builds on the previous.

### Prompt 1: Phase 3A — Scraper Foundation
```
Build Phase 3A: Web Scraper Foundation

Create enrichment/web_scraper.py with:
1. List of 10 rotating user agents (modern Chrome, Firefox, Safari)
2. Function scrape_website(url) that:
   - Picks random user agent
   - Adds random delay 2-5 seconds
   - Sets 15 second timeout
   - Disables SSL verification
   - Follows up to 3 redirects
   - Returns (html_content, status_code, error_message)
3. Handle exceptions: timeout, connection error, SSL error, too many redirects

Add database columns via migration:
- website_text TEXT
- scrape_status TEXT DEFAULT 'pending'
- scrape_error TEXT
- scraped_at TIMESTAMP

Test by scraping 3 URLs from your leads and showing results.
```

### Prompt 2: Phase 3B — Content Extraction
```
Build Phase 3B: Content Extraction

Update enrichment/web_scraper.py to add:
1. Function extract_text(html) that:
   - Uses BeautifulSoup to parse HTML
   - Removes: script, style, nav, header, footer, aside tags
   - Extracts text from: p, h1-h6, li, article, main, div tags
   - Cleans whitespace (collapse multiple spaces/newlines)
   - Limits to 15,000 characters
   - Returns cleaned text

2. Function scrape_and_extract(url) that:
   - Calls scrape_website for homepage
   - Tries /about and /contact if they exist
   - Combines all text
   - Returns final extracted text

Test on 5 leads with websites, show raw HTML length vs extracted text length.
```

### Prompt 3: Phase 3C — Batch Scraping UI
```
Build Phase 3C: Batch Scraping with Progress

Add to app.py:
1. Route /scrape/start (POST) - starts background scraping job
2. Route /scrape/status (GET) - SSE endpoint streaming progress
3. Route /scrape/stop (POST) - sets flag to stop after current item

Scraping logic:
- Get all leads where website is not null and scrape_status = 'pending'
- Process one at a time
- After each: update database, yield progress event
- Track: total, completed, failed, current lead name
- Save progress so it can resume

Update templates/leads.html:
- Add "Scrape Websites" button
- Show progress bar when running
- Show live counter: "Scraped: 45/500 | Failed: 3"
- "Stop" button to pause

Test by starting scrape, letting it run for 20 leads, then stopping. Verify it can resume.
```

### Prompt 4: Phase 4A-B — Gemini Client & Prompt
```
Build Phase 4A-B: Gemini AI Client

Create enrichment/gemini_client.py with:
1. Function call_gemini(prompt, max_retries=3) that:
   - Uses google.generativeai library
   - Loads GEMINI_API_KEY from environment
   - Implements exponential backoff (1s, 2s, 4s)
   - Returns parsed JSON or raises exception
   - Handles rate limits (429 response)

2. Function enrich_lead_with_gemini(website_text, business_name, city, state) that:
   - Builds the enrichment prompt (use prompt from strategy doc)
   - Calls Gemini
   - Parses JSON response
   - Validates required fields exist
   - Returns dict with all extracted fields

Add to requirements.txt:
- google-generativeai

Test on 3 scraped leads, show extracted JSON for each.
```

### Prompt 5: Phase 4C-D — Gemini Batch Processing
```
Build Phase 4C-D: Batch Gemini Enrichment

Add database columns:
- owner_name, owner_email, business_type, is_wholesale, is_retail
- greenhouse_sqft, acreage, multiple_locations, container_production
- soil_relevance, organic_focus, crops_grown (JSON), size_signals (JSON)
- negative_indicators (JSON), appointment_only, gemini_confidence
- gemini_raw_response, gemini_enriched_at, gemini_status, gemini_error

Add to app.py:
1. Route /enrich-ai/start - starts batch Gemini enrichment
2. Route /enrich-ai/status - SSE for progress
3. Route /enrich-ai/stop - pause

Processing:
- Only leads where scrape_status = 'scraped' AND gemini_status != 'enriched'
- 1 second delay between requests (rate limiting)
- Save after each success
- Log errors but continue

Update UI:
- "AI Enrich" button
- Progress bar
- Success/fail counts

Test on 10 leads, verify data quality.
```

### Prompt 6: Phase 5 — Scoring Engine
```
Build Phase 5: Scoring Engine

Create enrichment/scorer.py with:
1. SCORING_RULES dict defining all signals and points (use values from strategy doc)
2. Function calculate_score(lead) that:
   - Evaluates each rule against lead data
   - Returns total score and breakdown dict
3. Function assign_tier(score, has_data) that:
   - Returns A/B/C/U based on thresholds

Add database columns:
- score INTEGER
- score_breakdown TEXT (JSON)
- tier TEXT
- scored_at TIMESTAMP

Add to app.py:
- Route /score/all - score all enriched leads
- Route /score/<id> - rescore single lead

Update UI:
- "Score All" button
- Tier distribution summary (A: 47, B: 234, C: 312, U: 85)
- Color-coded tier badges
- Click lead to see score breakdown

Test: Score all leads, show distribution.
```

### Prompt 7: Phase 6 — Review Interface
```
Build Phase 6: Review Interface

Enhance templates/leads.html:
1. Filter bar:
   - Tier dropdown (All, A, B, C, U)
   - State dropdown
   - Business type dropdown
   - Score range slider
   - Search box

2. Sortable columns: Score, Name, City, Tier

3. Lead detail modal (click row to open):
   - All data fields organized in sections
   - Score breakdown visualization
   - Tier override dropdown
   - Notes textarea
   - "Mark Reviewed" button
   - "Save" button

Add database columns:
- tier_override TEXT
- review_notes TEXT
- reviewed_at TIMESTAMP

4. Bulk actions:
   - Checkbox on each row
   - "Select All" checkbox
   - Actions dropdown: Change Tier, Mark Reviewed

Test: Filter to Tier A, review 5 leads, add notes, override 1 tier.
```

### Prompt 8: Phase 7 — Personalization
```
Build Phase 7: Email Personalization

Add to enrichment/gemini_client.py:
1. Function generate_personalization(lead_data) that:
   - Uses the personalization prompt from strategy doc
   - Returns custom_line string (max 15 words)

Add database columns:
- custom_line TEXT
- email_angle TEXT
- personalization_status TEXT
- personalization_generated_at TIMESTAMP

Add to app.py:
- Route /personalize/start - batch generate for Tier A+B
- Route /personalize/status - SSE progress

Update UI:
- "Generate Personalization" button
- Only enabled if scoring complete
- Preview lines in lead detail modal

Test: Generate for 10 Tier A leads, review quality.
```

### Prompt 9: Phase 8 — Export
```
Build Phase 8: Export System

Create exporters/instantly_exporter.py:
1. Function export_to_csv(leads, filename) that:
   - Writes CSV with Instantly.ai columns
   - email, first_name, last_name, company_name, phone, website, location, custom_line
   - Handles missing values (empty string)
   - UTF-8 encoding

Add database table:
CREATE TABLE exports (
  id INTEGER PRIMARY KEY,
  filename TEXT,
  tier_filter TEXT,
  record_count INTEGER,
  created_at TIMESTAMP
)

Add to app.py:
- Route /export (GET) - show export config page
- Route /export/csv (POST) - generate and download CSV
- Route /export/excel (POST) - generate and download Excel

Create templates/export.html:
- Tier filter checkboxes
- Require email checkbox
- Preview count
- Download buttons

Test: Export Tier A+B to CSV, verify format matches Instantly requirements.
```

---

## Testing Checkpoints

After each phase, verify:

| Phase | Test |
|-------|------|
| 3A | Scrape 5 URLs manually, no blocks |
| 3B | Extracted text is clean, reasonable length |
| 3C | Batch scrape 50, pause, resume works |
| 4A-B | Gemini returns valid JSON for 5 leads |
| 4C-D | Batch enrich 20, data quality good |
| 5 | Score distribution looks reasonable |
| 6 | Can filter, sort, review, override |
| 7 | Personalization lines feel specific |
| 8 | CSV imports to Instantly without errors |

---

## File Structure (Final)

```
nursery-enrichment-pipeline/
├── app.py
├── config.py
├── requirements.txt
├── .env
├── database/
│   ├── __init__.py
│   ├── models.py
│   └── leads.db
├── enrichment/
│   ├── __init__.py
│   ├── google_places.py      ✅ Done
│   ├── web_scraper.py        Phase 3
│   ├── gemini_client.py      Phase 4
│   └── scorer.py             Phase 5
├── importers/
│   └── excel_importer.py     ✅ Done
├── exporters/
│   └── instantly_exporter.py Phase 8
├── static/
│   ├── css/style.css
│   └── js/app.js
├── templates/
│   ├── base.html             ✅ Done
│   ├── upload.html           ✅ Done
│   ├── leads.html            Enhance in Phase 6
│   └── export.html           Phase 8
└── data/
    └── uploads/
```
