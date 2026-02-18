# Phase 1 Evidence Log

Date: 2026-02-18
Scope: MI / OR / IL / USDA / MT importer hardening + verification only.

## Checkpoint A — Diagnostics + Provenance

### Completed
- Added machine-readable summary output on all five importers (`--summary-json` + alias `--json`).
- Enforced explicit exit-code contracts:
  - `0`: success
  - `2`: unexpected empty fetch/parse (`failed_empty_fetch`)
  - `3`: blocked due to missing source (`blocked_no_source`)
- IL provenance naming ambiguity resolved in script docs/summary payload:
  - canonical source label now explicitly **IDOA** (Illinois Department of Agriculture)
  - registry key kept as `il_idfpr` for backward compatibility

## Checkpoint B — USDA + MT Hardening

### USDA (`import_usda_hemp.py`)
- Added schema validation for required source fields:
  - required: one of `producer_name|business_name|name`
  - required: one of `state|producer_state`
- Added explicit warnings for missing optional columns.
- Added explicit schema failure status/exit behavior (`schema_invalid`, exit `4`).
- Added normalization diagnostics buckets for accepted/filtered/rejected row reasons.

### MT (`import_mt_revenue.py`)
- Added parse diagnostics for PDF path:
  - `lines_total`, `matched_pdf`, `unmatched_pdf`, `reject_missing_name_pdf`
- Added manual fallback ingest path:
  - `--input-file <csv|json>`
- Added manual row diagnostics (`accepted_manual`, reject/filter reason buckets).

### Docs
- Added reproducible acquisition/workflow doc:
  - `scripts/importers/PHASE1_SOURCE_WORKFLOWS.md`

## Checkpoint C — Evidence Bundle + Runs

### Run artifacts
- Directory: `outputs/phase1_evidence/`
- JSON summaries generated for dry/live/rerun per importer (or blocked equivalents).

### Dry-run / live / rerun outcomes
- `mi_cra`: dry/live/rerun all `failed_empty_fetch`
- `or_olcc`: dry/live/rerun all `failed_empty_fetch`
- `il_idfpr`: dry/live/rerun all `ok` (`fetched=227`, `new=0`, `existing=227` in this run window)
- `usda_hemp`: dry/live/rerun all `blocked_no_source`
- `mt_revenue`:
  - no-source path: dry/live/rerun all `blocked_no_source`
  - manual fallback path (`--input-file outputs/phase1_evidence/mt_manual_seed.json`):
    - dry: `new=2`
    - live: `new=2`
    - rerun dry: `new=0`, `existing=2` (idempotency proven)

### Blocker proof + exact unblock steps

#### MI CRA (`mi_cra`)
- Proof: repeated fetches return zero records across A/B/C classes with no parser crash.
- Exact unblock:
  1. Capture browser HAR for successful Accela search.
  2. Diff hidden ASP.NET fields/event target/pagination parameters.
  3. Update POST payload + pagination event args.
  4. Re-run dry/live/rerun and verify non-zero fetch.

#### OR OLCC (`or_olcc`)
- Proof: Tableau endpoint fails SSL cert verification in this environment; CAMP endpoint returns non-JSON for current usage.
- Exact unblock:
  1. Acquire official OR data export CSV (manual export or stable endpoint).
  2. Add/enable manual CSV ingestion path or replace endpoint strategy.
  3. Re-run dry/live/rerun against artifacted source.

#### USDA (`usda_hemp`)
- Proof: deterministic `blocked_no_source` when no CSV URL is supplied.
- Exact unblock:
  1. Obtain USDA HeMP producer CSV export from authorized/public workflow.
  2. Run with `--csv-url <export>` or set `USDA_HEMP_CSV_URL`.
  3. Confirm schema valid, then re-run dry/live/rerun.

#### MT (`mt_revenue`)
- Proof: deterministic `blocked_no_source` with no source, plus functional/idempotent manual fallback path.
- Exact unblock to official-source evidence:
  1. Acquire stable MT official source file (PDF/CSV) with provenance.
  2. Run importer using official source (not seed fallback).
  3. Verify non-seed inserts and idempotent rerun.

## Checkpoint D — OR official-source unlock (2026-02-18)

### Tavily-first discovery
- Query: `Oregon OLCC cannabis licensee csv export public`
- Official-source hit used: `https://www.oregon.gov/olcc/marijuana/Documents/Cannabis-Business-Licenses-All.xlsx`

### Importer change
- `import_or_olcc.py`
  - Added official XLSX source path (default + env/CLI override):
    - env: `OR_OLCC_XLSX_URL`
    - CLI: `--official-xlsx-url`
  - Added XLSX parser (`openpyxl`) and cultivator filtering via `License Type`.

### Runs
- Dry: `python3 scripts/importers/import_or_olcc.py --dry-run --summary-json outputs/phase1_evidence/or_official_dry.json`
  - result: `fetched=1380`, `new=1380`, `existing=0`, `status=ok`
- Live: `python3 scripts/importers/import_or_olcc.py --summary-json outputs/phase1_evidence/or_official_live.json`
  - result: `new=1380`, `existing=0`, `status=ok`
- Rerun dry: `python3 scripts/importers/import_or_olcc.py --dry-run --summary-json outputs/phase1_evidence/or_official_rerun_dry.json`
  - result: `new=0`, `existing=1380`, idempotency confirmed

## Checkpoint E — MT official-source unlock (2026-02-18)

### Tavily-first discovery
- Query: `Montana Department of Revenue cannabis license list cultivator`
- Official-source hit used: `https://revenuefiles.mt.gov/files/Cannabis/Licensed-Cultivator-List.pdf`

### Importer change
- `import_mt_revenue.py`
  - Replaced brittle line regex parser with column-aware `pdfplumber.extract_words()` parser using official PDF geometry.
  - Added wrapped-name handling and row diagnostics for matched/unmatched lines.

### Runs
- Dry: `python3 scripts/importers/import_mt_revenue.py --pdf-url 'https://revenuefiles.mt.gov/files/Cannabis/Licensed-Cultivator-List.pdf' --dry-run --summary-json outputs/phase1_evidence/mt_official_dry.json`
  - result: `fetched=327`, `new=327`, `existing=0`, `status=ok`
- Live: `python3 scripts/importers/import_mt_revenue.py --pdf-url 'https://revenuefiles.mt.gov/files/Cannabis/Licensed-Cultivator-List.pdf' --summary-json outputs/phase1_evidence/mt_official_live.json`
  - result: `new=282`, `existing=45`, `status=ok`
- Rerun dry: `python3 scripts/importers/import_mt_revenue.py --pdf-url 'https://revenuefiles.mt.gov/files/Cannabis/Licensed-Cultivator-List.pdf' --dry-run --summary-json outputs/phase1_evidence/mt_official_rerun_dry.json`
  - result: `new=0`, `existing=327`, idempotency confirmed

## Checkpoint F — MT hygiene hotfix + cleanup (2026-02-18)

### Importer hardening
- `import_mt_revenue.py`
  - Added strict noise reject patterns for MT header/footer contamination (e.g., `informational purposes`, `page X of Y`, `revenue.mt.gov`, `montana relay`, governor/director/header strings).
  - Added explicit validator guard before insert (`validate_record`) and validator diagnostics.
  - Insert summary now includes `rejected` count.

### One-time cleanup
- Added: `scripts/importers/cleanup_mt_revenue_noise.sql`
- Run: `sqlite3 data/leads.db < scripts/importers/cleanup_mt_revenue_noise.sql`
- Result: `deleted_rows=13` legacy noise rows removed.

### MT reruns after cleanup/hotfix
- Dry: `outputs/phase1_evidence/mt_hotfix_dry.json` → `fetched=327`, `new=12`, `existing=315`, `rejected=0`
- Live: `outputs/phase1_evidence/mt_hotfix_live.json` → `new=12`, `existing=315`, `rejected=0`
- Rerun dry: `outputs/phase1_evidence/mt_hotfix_rerun_dry.json` → `new=0`, `existing=327` (idempotent)

## Checkpoint G — MI fallback unblock (2026-02-18)

### Tavily-first discovery
- Query used: `Michigan CRA grower license csv` / `site:michigan.gov CRA licensing statistical reports downloadable csv`
- Official public source used for artifact extraction:
  - `https://aca-prod.accela.com/MIMM/Cap/CapHome.aspx?module=Adult_Use&TabName=Adult_Use`
  - (Public CRA verify flow instructions page: `https://www.michigan.gov/cra/verify-a-license-1`)

### Importer change
- `import_mi_cra.py`
  - Added manual fallback mode: `--input-file <csv|json>`
  - Added normalization/diagnostics for fallback ingest while retaining existing Accela flow as default path.

### Official artifact + fallback runs
- Artifact: `outputs/phase1_evidence/mi_official_accela_adultuse_growers.csv`
- Dry: `outputs/phase1_evidence/mi_fallback_dry.json` → `fetched=40`, `new=40`, `existing=0`
- Live: `outputs/phase1_evidence/mi_fallback_live.json` → `new=40`, `existing=0`
- Rerun dry: `outputs/phase1_evidence/mi_fallback_rerun_dry.json` → `new=0`, `existing=40` (idempotent)

## Checkpoint H — USDA unblock via approved exported artifact (2026-02-18)

### Tavily-first discovery
- Query used: `USDA hemp producer csv public`
- Official/public source pinned:
  - FOIA public licensee source PDF: `https://www.ams.usda.gov/sites/default/files/media/FOIAUSDAHempLicensees.pdf`
- Approved exported CSV artifact produced from that official source:
  - `outputs/phase1_evidence/usda_foia_export_midwest.csv`

### Importer change
- `import_usda_hemp.py`
  - Added manual fallback mode: `--input-file <csv|json>` (keeps existing schema checks intact).

### USDA runs (target states MN/WI/MI/IL/IA/IN/OH)
- Dry: `outputs/phase1_evidence/usda_fallback_dry.json` → `fetched=811`, `new=811`, `existing=0`
- Live: `outputs/phase1_evidence/usda_fallback_live.json` → `new=811`, `existing=0`
- Rerun dry: `outputs/phase1_evidence/usda_fallback_rerun_dry.json` → `new=0`, `existing=811` (idempotent)

## Checkpoint I — MI official full extract path + completeness reconciliation (2026-02-18)

### Live official run (no fallback file)
- Live: `outputs/phase1_evidence/mi_official_full_live.json`
  - `fetched=2031`, `new=1652`, `existing=379`, `status=ok`
- Rerun dry: `outputs/phase1_evidence/mi_official_full_rerun_dry.json`
  - `fetched=2031`, `new=0`, `existing=2031` (idempotent)

### Reconciliation artifacts
- `outputs/phase1_evidence/mi_completeness_reconciliation_2026-02-18.txt`
- `outputs/phase1_evidence/mi_license_type_counts_2026-02-18.txt`

Notes:
- MI full official extraction now runs directly from CRA Accela path (not fallback-only).
- Fetched rows include overlapping license categories (notably excess grower overlap); canonical DB count is deduplicated at write-time by `(license_number, registry_source)` and fallback duplicate guards.

## Checkpoint J — USDA provenance hardening verification (2026-02-18)

### Provenance fields enforced in DB writes
- `source_url`
- `fetch_timestamp`
- `artifact_sha256`
- `import_batch_id`

### Attached PDF provenance run evidence
- Dry: `outputs/phase1_evidence/usda_attachedpdf_dry.json`
- Live: `outputs/phase1_evidence/usda_attachedpdf_live.json`
- Rerun dry: `outputs/phase1_evidence/usda_attachedpdf_rerun_dry.json`
- Audit query output: `outputs/phase1_evidence/usda_provenance_audit_2026-02-18.txt`
  - `missing_source_url=0`
  - `missing_fetch_timestamp=0`
  - `missing_artifact_sha256=0`
  - `missing_import_batch_id=0`

## Canonical final source counts (current DB state)
(From `outputs/phase1_evidence/final_counts_2026-02-18.txt`)

- `il_idfpr`, `cannabis_grower`, `224`
- `mi_cra`, `cannabis_grower`, `1692`
- `mt_revenue`, `cannabis_grower`, `286`
- `or_olcc`, `cannabis_grower`, `1380`
- `usda_hemp`, `hemp_producer`, `811`

## Evidence table: expected vs actual status (current)

- `mi_cra`: expected `ok` (official full extract path) → actual `ok`
- `or_olcc`: expected `ok` (official XLSX) → actual `ok`
- `il_idfpr`: expected `ok` → actual `ok`
- `usda_hemp`: expected `ok` (approved exported artifact + provenance fields) → actual `ok`
- `mt_revenue`: expected `ok` (official PDF + cleanup guard) → actual `ok`

## Current blockers snapshot (post-J)
- No strict Phase 1 importer blocker remains for MI/OR/IL/USDA/MT in this environment.
- Residual risk (non-blocking): MI Accela HTML/ASP.NET flow is vendor-controlled and could drift; fallback path remains available if portal structure changes.

## Data quality checks
(Null `business_name`, null `state`, and `promoted_at` null by source)

- `il_idfpr`: total=224, null_business_name=0, null_state=0, promoted_at_null=224
- `mi_cra`: total=1692, null_business_name=0, null_state=0, promoted_at_null=1692
- `mt_revenue`: total=286, null_business_name=0, null_state=0, promoted_at_null=286
- `or_olcc`: total=1380, null_business_name=0, null_state=0, promoted_at_null=1380
- `usda_hemp`: total=811, null_business_name=0, null_state=0, promoted_at_null=811
