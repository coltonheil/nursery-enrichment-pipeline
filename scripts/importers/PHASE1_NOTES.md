# Phase 1 Importer Notes

## Scope
Phase 1 importer hardening only (MI/IL/OR/USDA/MT).

## Changes implemented

- `import_mi_cra.py`
  - Added machine-readable run summary output: `--summary-json <path>`.
  - Added explicit non-zero contract for empty fetches (exit code `2` by default).
  - Added override flag `--allow-empty-fetch` for controlled diagnostics runs.

- `import_or_olcc.py`
  - Added machine-readable run summary output: `--summary-json <path>`.
  - Added explicit non-zero contract for empty fetches (exit code `2` by default).
  - Added override flag `--allow-empty-fetch` for controlled diagnostics runs.

- `import_usda_hemp.py`
  - Added reproducible acquisition strategy and discovery references.
  - Supports env override `USDA_HEMP_CSV_URL` (and `--csv-url`) as canonical ingestion path.
  - Added CSV schema validation with explicit errors/warnings when key columns are missing.
  - Added machine-readable run summary output: `--summary-json <path>`.

- `import_mt_revenue.py`
  - Added parser diagnostics (matched/unmatched line counts + reject reasons).
  - Added manual fallback path: `--manual-artifact <local.csv|local.json>`.
  - Added configurable PDF source via `MT_REVENUE_CULTIVATOR_PDF_URL` or `--pdf-url`.
  - Added machine-readable run summary output: `--summary-json <path>`.

- `import_il_idfpr.py`
  - Added explicit provenance note documenting why `registry_source=il_idfpr` is retained while source document is IDOA-hosted.

## USDA source-discovery policy evidence
Tavily-first discovery run used for source references:
- `https://hemp.ams.usda.gov/s/PublicSearchTool`
- `https://www.ams.usda.gov/rules-regulations/hemp/information-for-hemp-growers`
- `https://www.ams.usda.gov/sites/default/files/media/FOIAUSDAHempLicensees.pdf`

## Montana manual fallback workflow

1. Prepare local artifact (`.csv` or `.json`) with fields:
   - required: `business_name` (or `name`), `city`
   - optional: `license_number`, `license_type`, `license_status`, `address`, `zip`, `county`
2. Run dry run first:
   - `python3 scripts/importers/import_mt_revenue.py --manual-artifact data/mt_cultivators_manual.csv --dry-run --summary-json scripts/importers/evidence/mt_manual_dry.json`
3. Run live import:
   - `python3 scripts/importers/import_mt_revenue.py --manual-artifact data/mt_cultivators_manual.csv --summary-json scripts/importers/evidence/mt_manual_live.json`
4. Re-run for idempotency proof:
   - `python3 scripts/importers/import_mt_revenue.py --manual-artifact data/mt_cultivators_manual.csv --summary-json scripts/importers/evidence/mt_manual_rerun.json`

## Exit behavior contract

- MI/OR importers return exit code `2` when fetch result is unexpectedly zero (default behavior).
- `--allow-empty-fetch` can be used for investigation runs where zero rows should not fail the process.
- USDA/MT return exit code `2` when blocked by missing/invalid source configuration.
