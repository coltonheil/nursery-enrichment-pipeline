# Phase 1 Source Acquisition Workflows (Reproducible)

## USDA Hemp (`import_usda_hemp.py`)

### Objective
Provide a reproducible way to acquire a CSV suitable for direct ingestion when USDA HeMP public producer endpoints are not directly downloadable without portal interaction.

### Steps
1. Obtain USDA HeMP producer export CSV from authorized/public workflow (portal export or provided file).
2. Save file locally, e.g.:
   - `data/sources/usda_hemp_export_YYYYMMDD.csv`
3. Validate required schema fields exist:
   - at least one of `producer_name | business_name | name`
   - at least one of `state | producer_state`
4. Run dry-run with summary:
   - `python scripts/importers/import_usda_hemp.py --dry-run --csv-url "file://..." --json outputs/usda_dryrun.json`
   - or host CSV and pass URL in `--csv-url`
5. Run live import:
   - `python scripts/importers/import_usda_hemp.py --csv-url "..." --json outputs/usda_live.json`

### Failure/diagnostic contract
- Exit `3` + `status=blocked_no_source` when no `--csv-url` provided.
- Exit `4` + `status=schema_invalid` when required columns missing.
- Exit `2` + `status=failed_empty_fetch` when schema passes but normalized record count is zero.

---

## Montana Revenue (`import_mt_revenue.py`)

### Objective
Support two reproducible ingestion paths despite unstable MT source formats:
1) PDF parse path (best effort) and
2) Manual fallback CSV/JSON path.

### Path A: PDF parse
1. Acquire MT source PDF URL or file.
2. Run:
   - `python scripts/importers/import_mt_revenue.py --dry-run --pdf-url "<url-or-path>" --json outputs/mt_pdf_dryrun.json`
3. Review parse diagnostics in summary JSON:
   - `lines_total`, `matched_pdf`, `unmatched_pdf`, `reject_missing_name_pdf`

### Path B: Manual fallback input (CSV/JSON)
1. Build a normalized file with columns/keys:
   - `business_name` (required), `state` (defaults to MT), optional: `license_number`, `city`, `zip`, `status`, `license_type`, `address`, `county`
2. Save as `.csv` or `.json` list of rows.
3. Run:
   - `python scripts/importers/import_mt_revenue.py --dry-run --input-file data/sources/mt_manual.csv --json outputs/mt_manual_dryrun.json`
4. Promote to live run without `--dry-run`.

### Failure/diagnostic contract
- Exit `3` + `status=blocked_no_source` when neither `--pdf-url` nor `--input-file` is provided.
- Exit `2` + `status=failed_empty_fetch` when source provided but yields zero parsed/accepted records.
- Summary JSON includes reasoned diagnostics for parse and reject/filter categories.
