# Kimi Orchestration Plan
*Created: 2026-02-18 — Mike review response (Conditional Pass)*

## Architecture

Kimi K2.5 (`nvidia/moonshotai/kimi-k2.5`) runs as the orchestrating agent driving the enrichment pipeline.
Gemini 2.0 Flash stays hardwired in `enrichment/gemini_client.py` for website AI extraction (unchanged).

---

## 1. Error Handling Plan

### NVIDIA API Failures
- **Timeout / 5xx:** Retry up to 3x with exponential backoff (2s, 4s, 8s). After 3 failures, log the lead as `kimi_orchestration_failed` and skip to next lead.
- **429 Rate Limit:** Backoff 30s then retry. Max 3 retries before marking lead skipped.
- **Auth errors (401/403):** Halt immediately. Do not retry. Alert human.

### Kimi Output Truncation
- Kimi's max output is 16,384 tokens. If orchestration output is truncated (no closing JSON/block), split the batch into smaller chunks (5 leads max) and rerun.
- Never proceed with a truncated orchestration response — treat as a failure and retry with smaller scope.

### Malformed Output
- If Kimi returns output that can't be parsed into the expected action (API endpoint, parameters), log the raw output to `outputs/kimi_errors.log` with the lead ID and skip.
- Never silently drop leads — all skips must be logged with reason.

### Lead Tracking
- Maintain a `kimi_run_log.json` per batch with: lead_id, status (success/skipped/failed), timestamp, and any error message.
- At end of run, print summary: N enriched, N skipped, N failed.

---

## 2. Email-Finding Decision Validation Plan

### During the 10-Lead Test Run
- For every email-finding decision Kimi makes (which search strategy, which pattern to try first, how to handle no-website leads), log the decision + Kimi's reasoning to `outputs/kimi_email_decisions.log`.

### Validation Approach
- After the 10-lead run, compare email hit rates: how many leads got a verified email vs. typical Sonnet-run baseline.
- If hit rate < 50% or decisions look arbitrary, constrain Kimi to a fixed ruleset:
  1. Try website contact page scrape first
  2. Brave search: `"[business name]" "[city]" email`
  3. Pattern generation (info@, owner@, etc.) + Reoon verify
  4. Skip if still no hit

### Pass Criteria for Full Batch
- ≥60% email hit rate on test batch (consistent with prior runs)
- No obviously bad decisions in the log (e.g., skipping leads that had emails on their contact page)
- No more than 2 unrecoverable errors in 10 leads

---

## Test Batch: First 10 Leads
- Source: `data/leads.db` — leads with `enrichment_status='pending'` or `gemini_status='pending'`
- Process through full pipeline: Google Places → Scrape → Gemini → Score
- Kimi monitors progress, handles retries, logs decisions
- Human reviews results before any Instantly push

---

## 3. Facebook Fallback Email Discovery (Stage 5b)

*Added: 2026-02-18*

### Overview
Hemp/cannabis leads often have no discoverable website or no email on their site.
A significant fraction of small hemp farms maintain a Facebook page as their only
online presence. Stage 5b searches for that page and extracts any email listed there.

### When It Runs
- After Stage 5 (email hunting) completes
- Only for segments: `hemp_producer`, `cannabis_grower`, `hemp`, `cannabis`
- Only for leads where `owner_email IS NULL`
- Only if `facebook_fallback_attempted IS NULL` (idempotent — won't re-run)

### Pipeline Position
```
Stage 1  Google Places / Web Search  → website, phone
Stage 2  Web Scraping                → website_text
Stage 3  Gemini AI Enrichment        → contacts, email (if on website)
Stage 4  Scoring
Stage 5  Email Hunting               → owner_email (pattern matching, Hunter.io, etc.)
Stage 5b Facebook Fallback           → owner_email (if still NULL, hemp/cannabis only) ← NEW
Stage 6  Reoon Email Verification
Stage 7  Supabase Sync
```

### Implementation
- **`enrichment/web_search_enrichment.py`**
  - `search_facebook_page(business_name, city, state)` — Tavily `site:facebook.com` search
  - `extract_email_from_facebook_page(fb_url)` — scrape page + `/about` tab for emails
  - `_extract_email_from_text(text)` — regex email extractor with junk-domain filtering

- **`enrichment/enrichment_router.py`**
  - `enrich_lead_facebook_fallback(lead)` — orchestrates the full fallback; checks guard conditions,
    calls Tavily, checks snippet (fast path), then scrapes if needed
  - Returns `{'email': str, 'source': 'facebook_page', 'facebook_url': str}` or `None`

- **`overnight_pipeline.py`**
  - `run_stage5b_facebook_fallback(segment, tier, limit)` — DB query + loop + writes
  - Auto-migrates `facebook_fallback_attempted` and `facebook_url` columns (idempotent)
  - Result logged as stage key `51` ("5b") in the pipeline summary

### DB Columns Added
| Column | Type | Purpose |
|--------|------|---------|
| `facebook_fallback_attempted` | BOOLEAN | Idempotency: 1 once attempted |
| `facebook_url` | TEXT | Stores the found Facebook page URL |
| `email_source` | TEXT | Set to `'facebook_page'` when email found this way |

### Usage
```bash
# Run only the Facebook fallback (hemp/cannabis leads with no email)
python overnight_pipeline.py --segment hemp_producer --stage 6 --skip-sync

# Run full pipeline including 5b for all segments
python overnight_pipeline.py --segment all
```

### Limitations
- Facebook is JS-rendered; the basic scraper may get limited content
- Emails on Facebook are not always publicly visible (some require login)
- Best results come from the Tavily snippet (fast path) when Tavily indexes the page text
- If hit rate is low, upgrade to Camofox for `/about` tab scraping
