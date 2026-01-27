# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Quick Start

```bash
cd "C:\Projects_Local\Sweet leaf sales\nursery-enrichment-pipeline"
.\venv\Scripts\Activate.ps1
py app.py
```

Application runs at http://127.0.0.1:5000

## Project Overview

Local Flask app that enriches nursery B2B leads for cold email outreach. Takes Excel lists (business name + address) and transforms them into scored, tiered, personalized leads ready for Instantly.ai export.

**Tech Stack:** Python/Flask, SQLite (data/leads.db), Google Places API, Google Gemini API (gemini-2.5-flash)

## Architecture: The Enrichment Pipeline

The pipeline runs in **4 sequential steps** (all orchestrated via `run_full_pipeline()` in app.py:293-482):

### Step 1: Google Places Enrichment
- **Module:** `enrichment/google_places.py`
- **Purpose:** Enriches business_name + city + state with Google Places API data
- **Adds:** phone, website, rating, review_count, hours, place_id, google_maps_url
- **Status tracking:** `enrichment_status` column ('pending' → 'enriched' or 'failed')

### Step 2: Website Scraping
- **Module:** `enrichment/web_scraper.py`
- **Purpose:** Scrapes website content for AI analysis
- **Adds:** `website_text` (stored as plain text in SQLite)
- **Status tracking:** `scrape_status` column ('pending' → 'scraped' or 'failed')
- **Note:** Uses requests + BeautifulSoup, may fail on JS-heavy sites

### Step 3: AI Enrichment (Gemini)
- **Module:** `enrichment/gemini_client.py`
- **Purpose:** Analyzes website_text to extract business intelligence
- **Adds:** business_type, organic_focus, crops_grown, size_signals, is_wholesale, container_production, owner_name, owner_email
- **Status tracking:** `gemini_status` column ('pending' → 'enriched' or 'failed')
- **Rate limit:** 1 request/second (hardcoded sleep in app.py:827)
- **Model:** gemini-2.5-flash (latest GA model, Jan 2026, configured in gemini_client.py:19)

### Step 4: Scoring
- **Module:** `enrichment/scorer.py`
- **Purpose:** Calculates lead quality score based on positive/negative signals
- **Scoring logic:**
  - Positive signals: is_wholesale (+35), cannabis_business (+30), closed_weekends (+25), large_greenhouse (+25), container_production (+25), etc.
  - Negative signals: christmas_tree (-30), sod_turf (-30), landscaping_services (-20), gift_shop (-15), high_reviews (-10), etc.
- **Output:** `score` (int), `tier` ('A'=80+, 'B'=50-79, 'C'=30-49, 'U'=<30), `score_breakdown` (JSON), `negative_indicators` (JSON)
- **Tier override:** Users can manually override tier via review UI (stored in `tier_override` column)

### Optional: Personalization (Step 5)
- **Module:** `enrichment/gemini_client.py:generate_personalization()`
- **Purpose:** Generates custom email opening lines for Tier A/B leads
- **Adds:** `custom_line`, `email_angle`
- **Triggered separately:** Not part of main pipeline, runs via `/personalize/start` endpoint

## Key Database Schema Details

**Leads table** (database/models.py:21-35, extended via migrations):
- Core: business_name, address, city, state, zip, phone, website, source_file
- Enrichment status: enrichment_status, scrape_status, gemini_status, personalization_status
- Google Places data: rating, review_count, place_id, google_maps_url, hours
- Scraped content: website_text (full text extraction)
- AI insights: business_type, organic_focus, crops_grown (JSON array), size_signals (JSON array), is_wholesale, container_production, owner_name, owner_email
- Scoring: score, tier, score_breakdown (JSON), negative_indicators (JSON)
- Review: reviewed, reviewed_at, reviewed_by, tier_override, review_notes
- Personalization: custom_line, email_angle

**Processing log** (database/models.py:38-47): Audit trail for all lead actions

**Exports** (database/models.py:50-60): Export history tracking

## Running the Pipeline

### Option 1: Full Pipeline (recommended)
```bash
# Start full pipeline via UI: http://127.0.0.1:5000/leads
# Or via API:
curl -X POST http://127.0.0.1:5000/pipeline/start -H "Content-Type: application/json" -d '{"batch_size": 10}'
```
Runs all 4 steps sequentially on N leads. Progress tracked via SSE endpoint `/pipeline/status`

### Option 2: Individual Steps
```bash
# Google Places only
curl -X POST http://127.0.0.1:5000/google-places/start -H "Content-Type: application/json" -d '{"batch_size": 10}'

# Scraping only (requires enriched leads with websites)
curl -X POST http://127.0.0.1:5000/scrape/start

# AI enrichment only (requires scraped leads)
curl -X POST http://127.0.0.1:5000/enrich-ai/start -H "Content-Type: application/json" -d '{"batch_size": 10}'

# Scoring only
curl -X POST http://127.0.0.1:5000/score/all -H "Content-Type: application/json" -d '{"batch_size": 10}'

# Personalization (Tier A/B only)
curl -X POST http://127.0.0.1:5000/personalize/start
```

### Monitoring Jobs
All background jobs expose SSE endpoints for real-time progress:
- Pipeline: `/pipeline/status`
- Google Places: `/google-places/status`
- Scraping: `/scrape/status`
- AI enrichment: `/enrich-ai/status`
- Personalization: `/personalize/status`

Stop jobs gracefully via POST to corresponding `/stop` endpoint

## Global State Architecture

Background jobs use global state dicts (app.py:24-80):
- `scraping_state`, `ai_enrichment_state`, `personalization_state`, `google_places_state`, `pipeline_state`
- Each tracks: `running`, `stop_requested`, `total`, `completed`, `failed`, `current_lead`, `errors`
- **Threading:** All jobs run as daemon threads (`threading.Thread(target=..., daemon=True)`)

**Important:** Only ONE instance of each job can run at a time (checked via `state['running']` flag)

## Export to Instantly.ai

**Module:** `exporters/instantly_exporter.py`

**Export formats:**
- CSV: Instantly.ai format (firstName, email, customField1=custom_line, companyName, website, phoneNumber, etc.)
- Excel: Same structure with additional metadata sheet

**Filter options:**
- `tier_filter`: 'A', 'B', 'AB', 'ABC', etc.
- `require_email`: Only leads with owner_email
- `require_personalization`: Only leads with custom_line

**UI:** http://127.0.0.1:5000/export

## Environment Variables

Required `.env` file (see .env.example):
```
GOOGLE_API_KEY=your_google_api_key_here
GEMINI_API_KEY=your_gemini_api_key_here
FLASK_SECRET_KEY=random_string_for_sessions
FLASK_DEBUG=true
```

Note: ANTHROPIC_API_KEY in .env.example is obsolete (no Anthropic calls in current code)

## Implementation Roadmap

This project follows a **10-phase implementation roadmap** documented in `ROADMAP.md`. The roadmap includes:
- Pre-implementation: Claude Code skills installation (obra/superpowers, frontend-design, claudekit-skills, data-wrangler, webapp-testing)
- Phase 1: Database Schema Evolution (ICP-specific columns)
- Phase 2: Gemini Prompt Engineering (enhanced extraction)
- Phase 3: Scoring Model Overhaul (ICP qualification gate)
- Phase 4: Geographic Intelligence (state-based scoring)
- Phase 5: Re-Enrichment Pipeline (process existing leads)
- Phases 6-8: Frontend improvements (lead cards, review workflow, dashboard)
- Phase 9: Pipeline Reliability (resumable state, retry logic)
- Phase 10: Testing & Validation

**Current Status:** Phases 1-8 complete (foundation, enrichment pipeline, scoring, review UI, personalization, export)

Refer to `ROADMAP.md` for detailed implementation steps and acceptance criteria for each phase.

## Development Notes

### Adding New Scoring Signals
1. Update `SCORING_RULES` dict in `enrichment/scorer.py`
2. Update detection logic in `calculate_score()` function (scorer.py:109+)
3. Re-run scoring: `POST /score/all` (will recalculate all leads)

### Modifying AI Prompts
- Business enrichment: `gemini_client.py:enrich_lead_with_gemini()` (~line 100+)
- Personalization: `gemini_client.py:generate_personalization()` (~line 200+)
- Both use structured JSON output with retry logic and rate limiting

### Database Migrations
Run via `migrate_db()` in database/models.py. New columns added via `ALTER TABLE` if not exists (models.py:75-140)

### Flask Routes Structure
- `/` - Upload page
- `/leads` - Leads list with filtering/pagination
- `/export` - Export configuration
- `/pipeline/*` - Pipeline control endpoints
- `/api/*` - JSON API endpoints for lead details, bulk operations
- All background job endpoints follow pattern: `/[job-name]/start`, `/[job-name]/stop`, `/[job-name]/status`
