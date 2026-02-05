# FACTS.md - Nursery Enrichment Pipeline

*Critical invariants and deployment facts for the nursery lead enrichment and outreach pipeline.*

**Last Updated:** 2026-02-05 06:45

---

## Soil Mixer Integration (Phase 11)

**Added:** 2026-02-05

**Purpose:** Import OMRI-certified organic soil blenders as high-value leads for worm castings sales.

**Data Source:** OMRI US Product List (https://www.omri.org/us-list)
- Search: "potting soil" → 7,206 products
- Scraped 4 pages, extracted 62 unique companies
- Classified: 38 Tier 1 (craft), 12 Tier 2 (commodity), 12 unknown

**Key Files:**
- `data/omri_soil_companies.json` — Scraped company data with tier classification
- `scripts/import_omri_soil_companies.py` — Import script
- `scripts/omri_scraper.py` — Browser scraping utilities

**Database Columns Added:**
- `data_source` — omri/google_places/manual
- `omri_code`, `omri_url` — OMRI identifier and profile URL
- `soil_mixer_tier` — tier_1 (craft) / tier_2 (commodity)
- `soil_mixer_signals` — JSON with keywords, indicators
- `uses_worm_castings`, `worm_castings_potential` — Affinity indicators

**ICP Changes:**
- `soil_mixer` moved to PRIMARY ICP (was SECONDARY)
- Rationale: Soil mixers MAKE soil products, highest volume buyers

**Scoring Signals Added:**
- `soil_mixer_business`: +35 points
- `omri_certified`: +25 points  
- `soil_mixer_tier_1`: +15 points
- `uses_worm_castings`: +20 points
- `worm_keyword_in_name`: +25 points

**Current Stats:**
- 38 Tier 1 craft soil companies imported
- All scored as Tier A (100+ points)
- Top targets: FoxFarm, Coast of Maine, Dr. Earth, Brut Worm Farms

---

## Hosting & Deployment

**Primary Hosting:** UNKNOWN (likely local dev or Railway)  
**Database:** Google Sheets (lead storage and scoring)  
**Production URL:** UNKNOWN  
**Staging URL:** UNKNOWN  
**Repository:** https://github.com/coltonheil/nursery-enrichment-pipeline  

**Deploy Mechanism:**
- Python Flask application
- Likely deployed to Railway or similar (check for railway.json or Procfile)
- Manual start: `python app.py` (runs Flask dev server)

---

## Tech Stack

**Runtime:** Python 3.x  
**Framework:** Flask (web app for UI)  
**Language:** Python  
**Package Manager:** pip + venv (`.venv/` directory)  
**Environment:** Virtual environment in `.venv/`  

**Key Scripts:**
- `app.py` — Main Flask web application (70KB, main UI)
- `create_instantly_campaigns.py` — Composio Instantly.ai campaign creation
- `add_emails_and_rescore.py` — Email enrichment and lead scoring
- `check_tier_u_status.py` — Tier U status checking

---

## External Integrations

**Composio (OAuth Manager):**
- Provides OAuth 2.0 flows for Instantly.ai
- 47 pre-built actions for Instantly
- Webhook support for bi-directional sync
- API key stored in: `COMPOSIO_API_KEY` (env var)

**Instantly.ai (Email Outreach):**
- Connected via Composio OAuth
- Campaign management and email sending
- Connection setup: See `COMPOSIO_INSTANTLY_SETUP.md`

**Google Gemini (AI Enrichment):**
- API key: `GEMINI_API_KEY` or `GOOGLE_API_KEY`
- Used for lead scoring and enrichment

**Anthropic Claude:**
- API key: `ANTHROPIC_API_KEY`
- Likely used for enrichment or scoring

**Brave Search API:**
- API key: `BRAVE_API_KEY`
- Email web search fallback when pattern inference fails
- Free tier: 2000 searches/month

**Hunter.io (Optional):**
- API key: `HUNTER_API_KEY`
- Email verification/discovery (optional)

---

## Data Storage

**Primary Database:** Google Sheets  
**Lead Storage:** Google Sheets (ID unknown - check app.py for sheet URL)  
**Scoring Storage:** Google Sheets (enriched with Gemini AI scores)  

**Data Flow:**
1. Leads imported to Google Sheets
2. Enrichment via Gemini AI (scoring)
3. Email discovery (Hunter/Brave/pattern inference)
4. Campaigns created in Instantly.ai via Composio
5. Outreach sent via Instantly

---

## Secrets Storage

**Local Development:**
- `.env` file (gitignored)
- Required vars:
  - `GOOGLE_API_KEY` or `GEMINI_API_KEY`
  - `ANTHROPIC_API_KEY`
  - `COMPOSIO_API_KEY`
  - `HUNTER_API_KEY` (optional)
  - `BRAVE_API_KEY` (recommended for fallback)
  - `FLASK_SECRET_KEY`
  - `FLASK_DEBUG=true`

**Production:**
- Environment variables set in hosting platform
- No database credentials (uses Google Sheets with OAuth)

---

## Critical Invariants

1. **Virtual Environment Required:** Always activate `.venv` before running scripts
2. **Composio Authentication:** Instantly.ai access via Composio OAuth (not raw API key)
3. **Google Sheets as DB:** All lead data lives in Google Sheets (no SQL database)
4. **Email Discovery Fallback:** Brave Search used when pattern inference fails
5. **Flask Secret:** `FLASK_SECRET_KEY` must be set (session security)

---

## Verification Commands

**Activate virtual environment:**
```bash
cd ~/clawd/projects/nursery-enrichment-pipeline
source .venv/bin/activate
```

**Run Flask app:**
```bash
cd ~/clawd/projects/nursery-enrichment-pipeline
source .venv/bin/activate
python app.py
# Runs on http://localhost:5000 (default Flask port)
```

**Check Composio connection:**
```bash
cd ~/clawd/projects/nursery-enrichment-pipeline
source .venv/bin/activate
python -c "from composio import Composio; print(Composio().apps.list())"
```

**Check git status:**
```bash
cd ~/clawd/projects/nursery-enrichment-pipeline
git status
git remote -v  # github.com/coltonheil/nursery-enrichment-pipeline
```

---

## Unknowns (Backlog Items to Discover)

- [ ] **Production URL:** Where is this deployed? Railway? Local only?
- [ ] **Google Sheets ID:** Which sheet holds the lead data?
- [ ] **Instantly.ai campaigns:** What campaigns currently exist?
- [ ] **Composio connection status:** Is Instantly.ai currently connected?
- [ ] **Email discovery success rate:** What % of leads get emails enriched?
- [ ] **Deployment automation:** Is there a CI/CD pipeline or manual deploy?

**Action:** Add discovery tasks to appropriate workstream BACKLOG.md
