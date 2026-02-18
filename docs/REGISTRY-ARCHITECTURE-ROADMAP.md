# Sweet Leaf Soil — Registry Architecture Review + Phased Build Roadmap
**Reviewer:** Mike (Senior Review Gate)
**Date:** 2026-02-17
**Status:** CONDITIONAL PASS — Architecture is sound. Six issues require fixes before build starts. Roadmap below addresses all of them.

---

## Section 1: Architecture Validation

### Verdict: Sound in principle. Six gaps require explicit resolution.

The three-layer model (Registry → Leads → CRM) is the correct approach. It separates concern cleanly: raw public records stay in the registry, enrichment cost happens only once per promoted record, and the CRM receives only verified and scored leads. The FK relationship (registries → leads) provides provenance tracing. This is the right design.

What follows are the six gaps that will bite if unaddressed.

---

### Gap 1: ICP Qualification Gate Disqualifies Hemp Producers by Default

**File:** `enrichment/scorer.py`, function `check_icp_qualification()`

Hemp producers (field-grown) will return `(False, "disqualified")` from the ICP gate. The logic qualifies a lead as primary ICP only if `uses_growing_media = True`, `production_method` in `[container, greenhouse, mixed]`, `container_production = True`, or `business_type = soil_mixer`. Field-grown hemp hits none of these conditions unless organic certified.

Field hemp producers ARE a legitimate target for worm castings — they apply amendments to soil between crop cycles. But they grow in fields. The current scorer will send every organic-uncertified hemp producer to Tier C automatically.

**Fix required:** Add `hemp_grower` and `cannabis_cultivator` to `ICP_PRIMARY_SIGNALS.business_type`. Add `field` to the production method allowlist when `segment = hemp_producer`. Or add a segment-aware bypass in `check_icp_qualification()` that passes hemp and cannabis leads through regardless of production method, then scores them on segment-specific signals.

---

### Gap 2: Oregon Gets a Geo Penalty (-5) But Is Priority Target #4

**File:** `enrichment/scorer.py`, `GEO_TIERS` dict

Oregon is in the "Far" tier: -5 geo modifier. That's correct from Wisconsin's freight perspective. But Oregon is explicitly listed as priority target #4 with ~1,500 cannabis cultivators. A 25-point geo penalty for every Oregon cannabis lead will systematically push them to Tier B or below.

This isn't wrong from a pure shipping-cost standpoint. It IS wrong if the business decision is to pursue Oregon regardless. The geo scoring should be segment-aware OR the Oregon target should be acknowledged as a "manually queue for review" situation rather than auto-scored.

**Fix required:** Either (a) add segment-aware geo scoring where Oregon cannabis leads get +0 instead of -5, or (b) document that Oregon leads will score lower and plan for manual tier override on export. Do not silently penalize a target market.

---

### Gap 3: Registry Deduplication on `(business_name, city)` Is Insufficient

**File:** `database/models.py`, function `insert_lead()`

The existing dedup logic is `WHERE business_name = ? AND city = ?`. Case-sensitive. No normalization. State cannabis registries frequently have:
- Legal entity name different from DBA ("Green Valley LLC" vs "Green Valley Cultivation")
- Same DBA across cities (multi-location operations)
- Identical city names across states

Registry imports need a separate dedup key. The state databases include license numbers. That is the correct primary key for deduplication within the registries table. The `registries` table must have a `UNIQUE(license_number, registry_source)` constraint, and the promotion step must check `registry_id` on the leads table to prevent promoting the same registry record twice.

**Fix required:** Define `registries` table schema with `UNIQUE(license_number, registry_source)`. Promotion script must check `WHERE registry_id = ?` before insert, not re-use the `(business_name, city)` check for promoted leads.

---

### Gap 4: `sync_to_supabase.py` Does Not Pass `segment` to CRM

**File:** `scripts/sync_to_supabase.py`, function `map_row()`

The current mapping produces: `company_name, contact_name, phone, email, city, state, zip, status, notes, source, enrichment_tier`. No `segment`. The Supabase `prospects` table will receive cannabis and nursery leads identically labeled. Kanban boards, Instantly campaign assignments, and follow-up sequences all need to differentiate segment.

**Fix required:** Add `segment` to `map_row()`. Add `segment` column to Supabase `prospects` table (migration required). Update `load_leads()` to select `segment` from SQLite.

---

### Gap 5: `get_leads_for_export()` Has No `segment` Filter

**File:** `database/models.py`, function `get_leads_for_export()`

No `segment` parameter exists. The Instantly exporter will mix nursery and cannabis leads in the same export if both are Tier A/B with emails. Cannabis cold email campaigns need different templates, sequences, subject lines, and senders than nursery campaigns. Mixing segments in one Instantly campaign is a deliverability and conversion risk.

**Fix required:** Add `segment` (or `segments: list`) parameter to `get_leads_for_export()`, `get_export_preview_count()`, and the Flask export route in `app.py`. Update `instantly_exporter.py` to accept and pass through segment filter.

---

### Gap 6: Google Places Has No Retry Logic — Enrichment Script Will Stall on 429

**File:** `enrichment/google_places.py`, function `search_place()`

On 429, the function returns `{'error': 'Rate limit exceeded', 'retry_after': 60}` — and does nothing else. The calling code in the Flask enrichment loop (see `app.py` pipeline thread) logs the error and moves on. 429s during a 2,400-lead cannabis batch will silently skip leads and leave them in `enrichment_status = 'pending'` permanently with no retry flag.

Gemini has proper retry logic (`call_gemini()` with exponential backoff). Google Places does not. This asymmetry will cause silent data gaps.

**Fix required:** Add retry logic with exponential backoff to the Google Places enrichment loop. Add a `enrichment_status = 'rate_limited'` status so skipped leads can be re-queued. Or build a rate-limited queue that respects 10 req/min.

---

## Section 2: Registries Table Schema

Before any Phase 1 work, this schema must be finalized. Nothing else can be built without it.

```sql
CREATE TABLE IF NOT EXISTS registries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    
    -- Core identity
    business_name TEXT NOT NULL,
    license_number TEXT,           -- State-issued license/registration number
    license_type TEXT,             -- cultivator, craft_grower, hemp_producer, etc.
    license_status TEXT,           -- active, expired, suspended
    
    -- Location
    address TEXT,
    city TEXT,
    state TEXT NOT NULL,
    zip TEXT,
    county TEXT,
    
    -- Contact (raw from registry — may be sparse)
    phone TEXT,
    website TEXT,
    contact_name TEXT,
    contact_email TEXT,
    
    -- Classification
    registry_source TEXT NOT NULL, -- mi_cra, il_idfpr, or_olcc, usda_hemp, mt_revenue
    segment TEXT NOT NULL,         -- cannabis_grower, hemp_producer
    
    -- Promotion tracking
    promoted_at TIMESTAMP,         -- When this record was promoted to leads table
    lead_id INTEGER,               -- FK to leads.id once promoted
    
    -- Audit
    imported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    raw_data TEXT,                 -- JSON of original row from source (for debugging)
    
    -- Dedup constraint
    UNIQUE(license_number, registry_source),
    FOREIGN KEY (lead_id) REFERENCES leads(id)
);

CREATE INDEX IF NOT EXISTS idx_registries_state ON registries(state);
CREATE INDEX IF NOT EXISTS idx_registries_segment ON registries(segment);
CREATE INDEX IF NOT EXISTS idx_registries_promoted ON registries(promoted_at);
CREATE INDEX IF NOT EXISTS idx_registries_source ON registries(registry_source);
```

Note: Records without a license number (e.g., Montana PDF) should dedup on `UNIQUE(business_name, city, registry_source)` instead. Handle this in the importer logic, not schema-level.

---

## Section 3: Phased Roadmap

### Phase 0: Schema Foundation
**Description:** Add the `registries` table and new columns to `leads`. Migrate existing 9,074 leads to `segment = 'nursery'`. This phase has zero risk to existing data if done correctly — all changes are additive.

**Complexity:** S

**Dependencies:** None

**Tasks:**
1. Add `registries` table via `migrate_db()` in `database/models.py`
2. Add `segment TEXT DEFAULT 'nursery'` column to `leads` via migration
3. Add `registry_id INTEGER DEFAULT NULL` column to `leads` via migration
4. Add FK index: `CREATE INDEX idx_leads_registry_id ON leads(registry_id)`
5. Add FK index: `CREATE INDEX idx_leads_segment ON leads(segment)`
6. Backfill: `UPDATE leads SET segment = 'nursery' WHERE segment IS NULL`
7. Add `segment` and `registry_id` to `get_leads_filtered()`, `get_leads_for_export()`, `get_export_preview_count()`, `map_row()` in sync script

**Definition of Done:**
- `sqlite3 data/leads.db "SELECT COUNT(*) FROM leads WHERE segment = 'nursery';"` returns 9074
- `sqlite3 data/leads.db "SELECT COUNT(*) FROM registries;"` returns 0 (table exists, empty)
- `sqlite3 data/leads.db "PRAGMA table_info(leads);" | grep segment` returns the column
- `sqlite3 data/leads.db "PRAGMA table_info(leads);" | grep registry_id` returns the column
- `migrate_db()` is idempotent — running it twice produces no errors
- All existing Flask UI pages load without error
- Tier distribution unchanged: A=191, B=465, C=973, U=7445

---

### Phase 1: Registry Importers
**Description:** Build one idempotent importer script per source. Each importer reads from a source (API, HTML scrape, CSV, PDF) and upserts into the `registries` table. No enrichment. No API calls beyond the source scrape itself. Priority order matches target state list.

**Complexity:** M

**Dependencies:** Phase 0 complete

**Tasks:**

**1A — Michigan CRA Cannabis Cultivators (~800 records)**
- Source: https://michigan.gov/cra — license search, filterable by license type
- Method: HTML scrape or CSV export (CRA provides data downloads)
- Fields: business_name, license_number, license_type (class_a/b/c_cultivator), city, state, zip, status
- Dedup: `UNIQUE(license_number, 'mi_cra')`
- Segment tag: `cannabis_grower`

**1B — Illinois IDFPR Craft Growers + Cultivation Centers (~108 records)**
- Source: IDFPR cannabis license search or state data portal
- Method: HTML scrape or CSV
- Fields: business_name, license_number, license_type, city, county, status
- Dedup: `UNIQUE(license_number, 'il_idfpr')`
- Segment tag: `cannabis_grower`

**1C — Oregon OLCC Cannabis Cultivators (~1,500 records)**
- Source: OLCC license lookup — provides CSV downloads at https://www.oregon.gov/olcc
- Method: CSV parse (OLCC publishes active license lists)
- Fields: business_name, license_number, license_type, city, county, zip, status
- Dedup: `UNIQUE(license_number, 'or_olcc')`
- Segment tag: `cannabis_grower`

**1D — USDA Hemp Registry (MN, WI, MI, IL, IA, IN, OH)**
- Source: USDA AMS hemp producer registry — public data export
- Method: CSV download filtered by state
- Fields: producer_name, state, county, acreage (if available)
- Dedup: Note: USDA registry does not always include license numbers. Use `UNIQUE(business_name, city, 'usda_hemp')` fallback. Handle NULL license_number gracefully.
- Segment tag: `hemp_producer`

**1E — Montana Revenue Cultivator List (PDF)**
- Source: Montana Dept of Revenue PDF — one-time parse
- Method: `pdfplumber` or `pdfminer` to extract table rows
- Fields: business_name, city, license_number (if present)
- Dedup: `UNIQUE(business_name, city, 'mt_revenue')` (license numbers may not be in PDF)
- Segment tag: `cannabis_grower`
- Note: Montana is lowest priority. If PDF is unstructured, manually enter or skip.

**All importers must:**
- Use `INSERT OR IGNORE` (or `ON CONFLICT DO NOTHING`) for idempotency
- Store `raw_data` as JSON of the original row
- Print a summary on completion: `Imported X new, Y already existed, Z errors`
- Accept a `--dry-run` flag that prints the summary without writing

**Definition of Done:**
- Each importer runs to completion without error
- Re-running any importer produces 0 new inserts (idempotency verified)
- `SELECT registry_source, segment, COUNT(*) FROM registries GROUP BY registry_source, segment` shows expected record counts per source (within ±10% of estimates)
- All records have `state` and `business_name` populated
- No records have `promoted_at` set (registry is fresh, unpromoted)
- `--dry-run` mode prints counts without writing to DB

---

### Phase 2: Scoring Engine Updates for New Segments
**Description:** The existing scorer is nursery-calibrated. Three changes required: (1) hemp producers must pass the ICP gate, (2) Oregon geo penalty must be handled for cannabis leads, (3) segment-specific scoring signals must be added.

**Complexity:** M

**Dependencies:** Phase 0 complete (segment column required)

**Tasks:**

**2A — ICP Gate Fix for Hemp and Cannabis**
In `check_icp_qualification()`:
- Add `cannabis_cultivator` and `hemp_grower` to `ICP_PRIMARY_SIGNALS["business_type"]`
- OR add a segment-aware early-return: if `lead['segment'] in ['cannabis_grower', 'hemp_producer']`, skip to secondary signal check and return `(True, 'primary')` immediately
- Cannabis and hemp leads must never fall to `disqualified` solely because they grow in fields

**2B — Segment-Specific Scoring Signals**
Add to `SCORING_RULES`:
```python
"indoor_cannabis_cultivation": {"points": 30, "description": "Indoor cannabis cultivation facility"},
"outdoor_licensed_cannabis": {"points": 20, "description": "Licensed outdoor/greenhouse cannabis"},
"hemp_field_acreage": {"points": 15, "description": "Hemp producer with documented acreage"},
"cannabis_organic_cert": {"points": 20, "description": "Cannabis cultivator with organic/clean cert"},
"dispensary_not_cultivator": {"points": -40, "description": "Dispensary only, no cultivation license"},
```

In `calculate_score()`, add segment-aware signal checks:
- If `segment = 'cannabis_grower'` and `business_type = 'cannabis_cultivator'`: trigger `indoor_cannabis_cultivation` or `outdoor_licensed_cannabis` based on Gemini extraction
- If `segment = 'hemp_producer'` and `acreage > 0`: trigger `hemp_field_acreage`
- Penalize dispensary-only records that were incorrectly promoted

**2C — Oregon Geo Score Fix**
Two options — pick one:
- Option A: Change `GEO_TIERS["OR"]` from -5 to 0 (neutral instead of penalty). Rationale: we are explicitly targeting Oregon; neutralize the freight bias.
- Option B: Add segment-aware geo override: if `segment = 'cannabis_grower'` and `state = 'OR'`, return 0 regardless of GEO_TIERS.
- Do not set Oregon to positive geo score — the freight cost is real.

**2D — Update Tier Thresholds for New Segments**
Current thresholds: Tier A = 40+ points, Tier B = ICP qualified (any score).
For cannabis/hemp, verify these thresholds make sense against the new scoring signals. A cannabis cultivator with `indoor_cultivation` (30) + `cannabis_organic_cert` (20) + `geo_score` (10-20) = 60-70 points should hit Tier A. Run 10 sample records through the scorer and verify output before marking done.

**Definition of Done:**
- `check_icp_qualification({'segment': 'hemp_producer', 'business_type': 'hemp_grower', 'production_method': 'field', 'is_organic_certified': False})` returns `(True, 'primary')`
- `check_icp_qualification({'segment': 'cannabis_grower', 'business_type': 'cannabis_cultivator', 'production_method': 'greenhouse'})` returns `(True, 'primary')`
- Oregon cannabis lead with `indoor_cultivation + organic_cert + geo_OR(0)` scores >= 40 (Tier A)
- Oregon cannabis lead with no organic cert scores < 40 (Tier B, not C)
- Hemp field producer in WI with 50 acres scores >= 40 (Tier A candidate)
- Dispensary-only lead scores Tier C regardless of segment tag
- Existing nursery test cases in `test_scorer()` still pass unchanged
- `run_rescore.py` re-run on 9,074 existing leads produces identical tier distribution (A=191, B=465, C=973, U=7445) — confirm no regression

---

### Phase 3: Gemini Prompt Tuning for Cannabis and Hemp
**Description:** The existing Gemini prompt (`enrich_lead_with_gemini()`) frames extraction entirely around nursery signals. Cannabis and hemp websites use different language. Without prompt tuning, Gemini will miss key signals and mis-classify these businesses.

**Complexity:** M

**Dependencies:** Phase 0 (segment column available to pass to Gemini call)

**Tasks:**

**3A — Segment-Aware Prompt Routing**
In `gemini_client.py`, update `enrich_lead_with_gemini()` to accept `segment` parameter:
```python
def enrich_lead_with_gemini(website_text, business_name, city, state, segment='nursery'):
```
If `segment` is `cannabis_grower`, use `build_cannabis_prompt()`. If `hemp_producer`, use `build_hemp_prompt()`. Nursery path unchanged.

**3B — Cannabis Cultivator Prompt**
Key signals to extract:
- `cultivation_type`: indoor / outdoor / greenhouse / mixed
- `indoor_sqft`: square footage of indoor grow space (not greenhouse sqft)
- `plant_count`: licensed plant count if mentioned
- `license_type`: cultivator / caregiver / processor (disqualify processor-only)
- `uses_amendments`: do they mention soil amendments, compost, organic inputs?
- `uses_worm_castings`: explicit mention of vermicompost/worm castings
- `clean_certified`: any "clean green," "sun+earth," or third-party organic cert for cannabis
- `dispensary_only`: only a dispensary, no cultivation license (disqualify)

Reuse existing fields where possible: `business_type = 'cannabis_cultivator'`, `crops_grown = ['cannabis']`, `is_organic_certified`, `organic_focus`, `scale_indicators`.

**3C — Hemp Producer Prompt**
Key signals to extract:
- `hemp_type`: fiber / CBD / seed / mixed
- `acreage`: acres under hemp cultivation
- `processing_on_site`: do they process (extract, dry, bale) on site?
- `uses_amendments`: compost, worm castings, organic inputs mentioned
- `organic_certified`: USDA Organic, state organic cert
- `market_channel`: wholesale / retail / both

Reuse: `business_type = 'hemp_grower'`, `is_organic_certified`, `acreage`, `crops_grown`.

**3D — Validate JSON Field Compatibility**
Ensure all new prompt fields map to existing columns in the `leads` table OR are stored in `gemini_raw_response` JSON. Do not add new DB columns unless no existing column fits. Preferred mapping:
- `indoor_sqft` → `greenhouse_sqft` (reuse — column already exists)
- `cultivation_type` → `production_method`
- `uses_amendments` → `uses_growing_media` (close enough for ICP signal)
- `dispensary_only` → new key in `negative_indicators` JSON (no schema change)

**Definition of Done:**
- `enrich_lead_with_gemini(website_text, "Green Peak Cannabis", "Lansing", "MI", segment="cannabis_grower")` returns a dict with `business_type = 'cannabis_cultivator'` and `production_method` set
- Test on 5 real cannabis websites (scrape manually, pass text to function): all 5 return `business_type = 'cannabis_cultivator'` or `cannabis_grower`
- Test on 5 real hemp websites: all 5 return `business_type = 'hemp_grower'`
- No nursery test cases regress (run `test_gemini_simple.py`)
- Cannabis leads with indoor grow spaces have `greenhouse_sqft` > 0
- Hemp leads with field acreage have `acreage` > 0

---

### Phase 4: Promotion Flow
**Description:** Build the pipeline that promotes N records from `registries` to `leads`, triggering enrichment. This is the operational core of Layer 2.

**Complexity:** M

**Dependencies:** Phase 0 (schema), Phase 1 (registry populated), Phase 2 and 3 (scoring + Gemini ready for new segments)

**Tasks:**

**4A — `promote_from_registry()` Script**
New file: `scripts/promote_from_registry.py`

Logic:
```
1. SELECT N records FROM registries WHERE promoted_at IS NULL AND state = ? AND segment = ?
2. For each registry record:
   a. Check if leads table already has a record with registry_id = registry.id (idempotency)
   b. Insert into leads: business_name, city, state, zip, phone, website, segment, registry_id, source_file = registry_source
   c. UPDATE registries SET promoted_at = CURRENT_TIMESTAMP, lead_id = ? WHERE id = ?
3. Print summary: Promoted X records, Y already existed
```

Accept CLI args: `--state MI`, `--segment cannabis_grower`, `--limit 50`, `--dry-run`

**4B — Enrichment Pipeline Compatibility**
Verify that the existing `overnight_pipeline.py` and `scrape_all_pending.py` will pick up promoted cannabis/hemp leads correctly. These scripts query `WHERE enrichment_status = 'pending'` — promoted leads inherit the default value, so they will be picked up automatically. No changes needed to enrichment scripts if Phase 2/3 are done (scorer and Gemini are segment-aware).

**4C — Flask UI: Promotion Panel**
Add a `/registry` route in `app.py`:
- Show registry stats per source: total records, promoted count, remaining
- "Promote N" button per state/segment — calls `promote_from_registry()` in a background thread
- Uses SSE progress pattern (already implemented for other pipelines)

**4D — Rate Limiter for Google Places** (required before running enrichment on cannabis batch)
In the Google Places enrichment loop (either in `app.py` pipeline thread or standalone script):
- Add `time.sleep(0.1)` between requests (6 req/sec default; Google Places allows 10/sec on most plans)
- On 429: set `enrichment_status = 'rate_limited'`, continue to next lead, log to `processing_log`
- Add `get_leads_by_enrichment_status('rate_limited')` query to pick these up on retry run
- Add `--retry-rate-limited` flag to enrichment script

**Definition of Done:**
- `python3 scripts/promote_from_registry.py --state MI --segment cannabis_grower --limit 10 --dry-run` prints 10 records without writing to DB
- Running the promotion for real inserts 10 records into leads with `segment = 'cannabis_grower'`, `registry_id` set, and `enrichment_status = 'pending'`
- Re-running the same command produces "0 promoted, 10 already existed"
- `overnight_pipeline.py` picks up the 10 promoted leads and enriches them
- After enrichment, the 10 leads have `enrichment_status = 'enriched'`, `gemini_status = 'enriched'`, `tier` set
- Google Places rate-limited leads show `enrichment_status = 'rate_limited'`, not dropped silently

---

### Phase 5: Supabase CRM + Instantly Export Updates
**Description:** Update the sync and export pipeline so segment information flows through to the CRM and Instantly campaigns. Without this, Layers 2 and 3 are severed.

**Complexity:** S

**Dependencies:** Phase 0 (segment column on leads), Phase 4 (leads are being promoted and enriched)

**Tasks:**

**5A — `sync_to_supabase.py`**
- Add `segment` to `map_row()`:
  ```python
  "segment": lead.get("segment") or "nursery",
  ```
- Add `segment` to `load_leads()` SELECT statement
- Verify Supabase `prospects` table has a `segment` column (TEXT). If not, run migration: `ALTER TABLE prospects ADD COLUMN segment TEXT;`

**5B — `get_leads_for_export()` and `get_export_preview_count()`**
In `database/models.py`:
- Add `segment: str = None` parameter to both functions
- Add to WHERE clause: `if segment: where_conditions.append('segment = ?'); params.append(segment)`

**5C — Flask Export Route**
In `app.py`, update the export route to pass `segment` from request params to `get_leads_for_export()`.

**5D — Instantly Campaign Naming Convention**
When exporting for Instantly, use segment-prefixed filenames: `cannabis_grower_tier_a_2026-02.csv`, `hemp_producer_tier_b_wi_2026-02.csv`. This prevents campaign confusion.

**5E — Supabase `opportunities` and `kanban` tables**
If the kanban board in Supabase already exists, verify it can filter by segment. If not, add a `segment` column to the relevant views/tables.

**Definition of Done:**
- `python3 scripts/sync_to_supabase.py --dry-run` shows cannabis leads with `segment = 'cannabis_grower'` in sample rows
- Live sync inserts 1 cannabis Tier A lead to Supabase with correct `segment` value
- `get_leads_for_export(tier_filter='A', segment='cannabis_grower')` returns only cannabis Tier A leads, zero nursery leads
- Export CSV for cannabis Tier A has filename with `cannabis_grower` prefix
- Export CSV for nursery Tier A has zero cannabis records

---

### Phase 6: Rate Limiting and Fallback Strategy
**Description:** Define what happens when external APIs fail or exhaust quotas during a batch enrichment run. This phase formalizes the failure modes so they are handled gracefully, not silently.

**Complexity:** S

**Dependencies:** Phase 4 (enrichment pipeline running on new segments)

**Rate Limit Fallback Definitions:**

**Google Places (10 req/sec default, quota per project per day):**
- On 429: mark lead `enrichment_status = 'rate_limited'`, log to `processing_log`, sleep 60s, resume
- On daily quota hit: stop pipeline, log `pipeline_runs` record with status `quota_hit`, send notification
- Fallback: leads without Google Places enrichment can still proceed through scrape + Gemini if `website` is known from registry data. Website scraping does NOT depend on Google Places.
- Recovery: `--retry-rate-limited` flag re-queues all `enrichment_status = 'rate_limited'` leads

**Gemini (already has retry logic — extend it):**
- Current: 5 retries with exponential backoff. Keep.
- Add: daily quota counter in `pipeline_runs`. If `gemini_error` count > 50 in one run, pause and alert.
- Fallback: leads without Gemini enrichment (`gemini_status = 'failed'`) are scored from Places data only. They score lower but are NOT dropped.
- Recovery: Re-run `scrape_all_pending.py` for failed leads — picks up `gemini_status = 'failed'` leads automatically

**Reoon Email Verification:**
- Add a balance check at the start of any email hunt batch: call Reoon `/v1/account` endpoint, check `balance` field
- If balance < $5.00: switch to `confidence_only` mode — verify via MX record + pattern matching only, skip Reoon API call
- If balance < $1.00: skip verification entirely, export with `email_verified = NULL` and note in export
- Log warning to Discord #soil-science when Reoon balance drops below $10.00
- Fallback: `confidence >= 85` leads can still export without Reoon verification (this logic already exists in `get_leads_for_export()` — keep it)

**Tavily (Layer 3 of email hunt):**
- On 429 or quota: skip Layer 3, proceed with Layer 2 (pattern inference) result
- Tavily is a best-effort layer, not required

**Definition of Done:**
- Simulated 429 from Google Places (mock the response) results in `enrichment_status = 'rate_limited'` on lead, NOT a silent skip
- Simulated Gemini quota error results in `gemini_status = 'failed'`, lead is scoreable from Places data
- Reoon balance check runs at batch start; output shows balance before hunt begins
- Balance < $5 produces a log line: `[WARN] Reoon balance low ($X) — MX-only verification mode`
- These behaviors are documented in `QUICK_REFERENCE.md`

---

### Phase 7: Integration Testing + Confidence Pillar Verification
**Description:** Run the full pipeline on real test records from each new segment. Verify all six confidence pillars score >0.95 before declaring the system production-ready.

**Complexity:** S

**Dependencies:** Phases 0-6 complete

**Tasks:**

**7A — End-to-End Test: Michigan Cannabis (10 records)**
1. Confirm 10 Michigan cannabis records exist in `registries` (from Phase 1A)
2. Promote 10 to `leads`
3. Run Google Places enrichment on 10
4. Run web scraper on 10
5. Run Gemini enrichment with `segment = 'cannabis_grower'` on 10
6. Run email hunter on 10
7. Run scorer on 10
8. Check tiers: expect >= 5 of 10 to be Tier A or B (not all C/U)
9. Sync 1 Tier A lead to Supabase, verify `segment = 'cannabis_grower'` in Supabase
10. Export Tier A cannabis leads to CSV, verify segment filter works

**7B — End-to-End Test: Wisconsin Hemp (10 records)**
Same flow as 7A but with `segment = 'hemp_producer'` and records from `usda_hemp` source, state = WI.

**7C — Regression Test: Existing Nursery Pipeline**
- Verify 9,074 nursery leads are untouched (COUNT(*) WHERE segment = 'nursery' = 9074)
- Re-run scorer on nursery leads: tier distribution must match A=191, B=465, C=973, U=7445 (±0)
- Run a nursery export: zero cannabis/hemp records appear

**Definition of Done:**
All six confidence pillars score >0.95. See Section 4 for exact pillar definitions and measurement criteria.

---

## Section 4: Confidence Pillar Definitions

Each pillar is measured as a pass rate against a test corpus. Target: all pillars >= 0.95 (95%).

---

### Pillar 1: Data Integrity
**Definition:** No duplicate records in registries, no orphaned FK references, all segment tags correct.

**Measurement:**
```sql
-- Dupe check: registries
SELECT license_number, registry_source, COUNT(*) as cnt 
FROM registries 
GROUP BY license_number, registry_source 
HAVING cnt > 1;
-- Expected: 0 rows

-- Orphaned registry_id on leads
SELECT l.id FROM leads l 
LEFT JOIN registries r ON l.registry_id = r.id 
WHERE l.registry_id IS NOT NULL AND r.id IS NULL;
-- Expected: 0 rows

-- Missing segment on leads
SELECT COUNT(*) FROM leads WHERE segment IS NULL;
-- Expected: 0

-- Nursery leads with wrong segment
SELECT COUNT(*) FROM leads 
WHERE segment != 'nursery' AND source_file NOT IN 
  ('mi_cra','il_idfpr','or_olcc','usda_hemp','mt_revenue');
-- Expected: 0

-- Existing lead count unchanged
SELECT COUNT(*) FROM leads WHERE segment = 'nursery';
-- Expected: 9074
```
**Score:** (checks passing) / 5 checks = must be 5/5 (1.0)

---

### Pillar 2: Enrichment Pipeline
**Definition:** Google Places + scrape + Gemini + email hunt all function correctly on cannabis and hemp test records.

**Measurement:** Run against 20 test records (10 cannabis MI, 10 hemp WI):
- Places enrichment: success rate = records with `enrichment_status = 'enriched'` / 20
- Scrape: success rate = records with `scrape_status = 'scraped'` / those with website
- Gemini: success rate = records with `gemini_status = 'enriched'` / scraped records
- Gemini segment accuracy: records where `business_type` matches expected segment / gemini enriched
- Email hunt: records with `owner_email IS NOT NULL` / 20 (may be lower — 0.60+ acceptable for new leads with sparse data)

**Score:** Average of Places + scrape + Gemini success + segment accuracy rates. Email hunt weighted at 0.5x (data quality varies by source). Overall >= 0.95.

**Critical sub-check:** Zero cannabis leads scored as `tier = 'C'` due to ICP gate misfire.

---

### Pillar 3: Registry Completeness
**Definition:** All target state registries are imported with record counts within ±10% of estimates.

**Measurement:**
```sql
SELECT registry_source, COUNT(*) FROM registries GROUP BY registry_source;
```
Expected ranges:
- `mi_cra`: 720–880 records
- `il_idfpr`: 97–119 records
- `or_olcc`: 1,350–1,650 records
- `usda_hemp` (MN+WI+MI+IL+IA+IN+OH): check against USDA published counts
- `mt_revenue`: best-effort (no count estimate; >= 1 record = pass)

**Score:** Sources with record count in expected range / 5 sources. All 5 must pass (1.0).

Exception: if a source's published count has changed significantly since the estimate, document the delta and adjust the expected range. Human review required for > ±25% variance.

---

### Pillar 4: Promotion Flow
**Definition:** Registry-to-leads promotion is clean, idempotent, and segment tags propagate correctly.

**Measurement:**
1. Promote 10 Michigan cannabis records. Verify: `SELECT COUNT(*) FROM leads WHERE registry_id IS NOT NULL AND segment = 'cannabis_grower'` = 10.
2. Re-run promotion. Verify: output says "0 promoted, 10 already existed." `COUNT(*)` still = 10.
3. Check `registries.promoted_at IS NOT NULL` for the 10 promoted records.
4. Check `registries.lead_id IS NOT NULL` for the 10 promoted records.
5. Verify `leads.segment = 'cannabis_grower'` for all 10.

**Score:** All 5 checks pass = 1.0. Any failure = re-run Phase 4.

---

### Pillar 5: Scoring Accuracy
**Definition:** Cannabis and hemp leads score appropriately. No nursery-bias artifacts pushing them to Tier C.

**Measurement:** Score a curated set of 20 records (10 cannabis, 10 hemp) with known expected tiers based on business profile. Build this test set manually before running.

Expected:
- Indoor cannabis cultivator with organic cert + 5,000 sqft grow room: Tier A
- Outdoor cannabis cultivator, no organic cert, OR: Tier B (not C)
- Hemp producer, 100 acres, WI, no organic cert: Tier A or B
- Hemp producer, 5 acres, out-of-target state: Tier B or C (acceptable)
- Dispensary-only (no cultivation): Tier C
- Registry record with no website or Google Places hit: Tier U (acceptable — insufficient data)

**Score:** Records matching expected tier / 20. Target >= 0.95 (19 of 20 correct). Re-examine any mismatches.

Nursery regression: Run `test_scorer()` from `enrichment/scorer.py`. All 4 existing test cases must pass unchanged.

---

### Pillar 6: Export Readiness
**Definition:** Segment-filtered exports for Instantly work correctly and produce no cross-segment contamination.

**Measurement:**
1. `get_leads_for_export(tier_filter='A', segment='cannabis_grower')`: count must be >= 0 (pipeline may not have Tier A cannabis yet; test with Tier B if needed), zero nursery records in result.
2. `get_leads_for_export(tier_filter='A', segment='nursery')`: zero cannabis/hemp records in result.
3. `get_leads_for_export(tier_filter='AB')` (no segment filter): includes both nursery and cannabis records (backward compatibility).
4. Export CSV contains `segment` column in output.
5. Supabase sync: Tier A cannabis lead has `segment = 'cannabis_grower'` in Supabase `prospects` table.

**Score:** All 5 checks pass = 1.0.

---

## Section 5: Integration Test Criteria (Full System)

Run after all phases complete. This is the pass/fail gate before running any production campaign.

### Test 1: Full Pipeline (Michigan Cannabis, 50 records)
1. 50 records from `mi_cra` in `registries` with `promoted_at IS NULL`
2. Run `promote_from_registry.py --state MI --segment cannabis_grower --limit 50`
3. Verify 50 leads in `leads` table with correct segment and registry_id
4. Run `overnight_pipeline.py` or equivalent for these 50 leads
5. After enrichment: verify distribution — expect >= 30 of 50 to have `gemini_status = 'enriched'` (some may fail due to no website)
6. Run scorer on 50 leads
7. Verify >= 5 Tier A, >= 10 Tier B among enriched leads
8. Run `sync_to_supabase.py --dry-run`: verify cannabis leads appear in sample output with correct segment
9. Export Tier A+B cannabis leads to CSV: verify no nursery records, segment column present
10. Verify no change to nursery lead count (still 9,074)

**Pass criteria:** Steps 1–10 all succeed. Zero data corruption. Zero cross-segment contamination.

### Test 2: Idempotency (Re-run everything)
1. Re-run all registry importers on same source data
2. Verify 0 new records inserted to `registries`
3. Re-run `promote_from_registry.py` for Michigan cannabis
4. Verify 0 new records inserted to `leads`
5. Re-run `overnight_pipeline.py` on already-enriched leads
6. Verify no data overwritten or duplicated

**Pass criteria:** All re-runs produce 0 new inserts. No status columns reset.

### Test 3: Nursery Regression
1. Check `SELECT COUNT(*), tier FROM leads WHERE segment = 'nursery' GROUP BY tier`
2. Compare against baseline: A=191, B=465, C=973, U=7445, total=9074
3. Run `sync_to_supabase.py --dry-run`: nursery sample rows still appear
4. Export Tier A nursery CSV: no cannabis/hemp records

**Pass criteria:** Exact match on all four tier counts. Zero cross-contamination.

---

## Section 6: Risk Register

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Oregon OLCC changes CSV format or removes public download | Medium | High | Download and cache CSV immediately. Don't rely on live scrape. |
| USDA hemp registry lacks city/zip for some states | High | Medium | Store county only; use county for geo scoring if city unavailable |
| Gemini misclassifies cannabis cultivators as "unknown" or "other" | Medium | High | Phase 3 validation with 5 real cannabis websites before batch |
| Reoon balance depletes mid-batch | Medium | Low | Balance check at batch start; confidence-only fallback already coded |
| Montana PDF is unstructured (scanned, not machine-readable) | Medium | Low | Montana is lowest priority; manual entry acceptable |
| Google Places can't find some cannabis businesses (unlisted or listed under legal name) | High | Medium | Fall back to website-only enrichment; registry already has business name |
| `(business_name, city)` dedup in `insert_lead()` collides with a cannabis lead that has same name as an existing nursery | Low | Low | Use `registry_id` as the FK instead of relying on `insert_lead()` for promoted records |
| Gemini extracts `uses_growing_media = False` for cannabis because website doesn't use that language | High | High | Phase 3 fix: segment-aware prompt that infers `uses_growing_media = True` from `cannabis_cultivator` type |
| Cannabis leads in Oregon score systematically low due to geo penalty | High | Medium | Phase 2C fix: neutralize Oregon geo penalty for cannabis segment |
| Future segments (e.g., mushroom farms, aquaponics) require schema changes | Low | Low | `segment` TEXT column is open-ended; scoring is segment-aware by design; no schema change needed for new segments |

---

## Section 7: Build Order and Estimated Timeline

| Phase | Name | Complexity | Est. Time | Blocker |
|-------|------|-----------|-----------|---------|
| 0 | Schema Foundation | S | 0.5 day | None |
| 1 | Registry Importers | M | 3–5 days | Phase 0 |
| 2 | Scoring Engine Updates | M | 2–3 days | Phase 0 |
| 3 | Gemini Prompt Tuning | M | 2–3 days | Phase 0 |
| 4 | Promotion Flow | M | 2–3 days | Phases 0, 1, 2, 3 |
| 5 | CRM + Export Updates | S | 1 day | Phase 0 |
| 6 | Rate Limiting + Fallbacks | S | 1 day | Phase 4 |
| 7 | Integration Testing | S | 1 day | Phases 0–6 |
| **Total** | | | **~12–17 days** | |

Phases 2, 3, and 5 can run in parallel after Phase 0 completes. Phase 4 is the integration point — it cannot start until Phases 1, 2, and 3 are all done.

---

## Section 8: What Must Not Change

These are hard constraints enforced at every phase:

1. `SELECT COUNT(*) FROM leads WHERE segment = 'nursery'` must always return 9,074 after any migration
2. Tier distribution for nursery (A=191, B=465, C=973, U=7445) must be reproducible by re-running the scorer
3. `insert_lead()` dedup logic for nursery leads is unchanged
4. `sync_to_supabase.py` still syncs nursery Tier A/B leads
5. Flask UI nursery views (all existing routes) load without error throughout all phases
6. No secret or credential is hardcoded into any new importer script — all use `master.env`

---

## Final Assessment

The architecture is approved for build with the six gaps addressed in the roadmap above. The most critical items before running any batch enrichment:

1. Phase 2 (ICP gate fix for hemp) — blocking. Hemp leads will all score Tier C without this.
2. Phase 3 (Gemini prompt for cannabis) — blocking. Cannabis websites will fail extraction without segment-aware prompts.
3. Phase 4D (Google Places rate limiter) — blocking for large batches. A 1,500-lead Oregon batch will hit quota without rate limiting.

Do those three before anything else. The rest can follow.
