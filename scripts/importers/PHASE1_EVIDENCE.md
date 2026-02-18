# Phase 1 Evidence Log

## Checkpoint A — Diagnostics + Provenance
Date: 2026-02-18

### Completed
- Added machine-readable summary output option to all five Phase 1 importers:
  - `import_mi_cra.py`
  - `import_or_olcc.py`
  - `import_il_idfpr.py`
  - `import_usda_hemp.py`
  - `import_mt_revenue.py`
- Standardized CLI option alias: `--summary-json` and `--json` now both supported.
- Enforced explicit exit-code contracts on no-data scenarios:
  - `2` for unexpected empty parse/fetch (`failed_empty_fetch`)
  - `3` for source-blocked/no-source scenarios (`blocked_no_source`)
  - `0` on success
- Resolved IL provenance naming ambiguity in importer labeling/docs:
  - Canonical source label now explicitly IDOA (Illinois Department of Agriculture) in script docs and summary payload.
  - Registry key remains `il_idfpr` for backward compatibility with existing DB rows.

### Notes
- Scope intentionally constrained to importer behavior and evidence docs only (no broad refactor).

## Checkpoint B — USDA + MT Hardening
Date: 2026-02-18

### Completed
- USDA importer hardening (`import_usda_hemp.py`):
  - Added schema validation with explicit required-column checks.
  - Added explicit warning/error surfaces for missing columns.
  - Added deterministic schema failure exit code (`4`, `schema_invalid`).
  - Added row-level normalization diagnostics (`accepted`, filtered/rejected reason buckets).
- Montana importer hardening (`import_mt_revenue.py`):
  - Added parse diagnostics counters for PDF path (`matched/unmatched/reject reasons`).
  - Added manual fallback input path via `--input-file` supporting both CSV and JSON.
  - Added per-row manual fallback accept/reject diagnostics.
- Added reproducible acquisition/workflow docs:
  - `scripts/importers/PHASE1_SOURCE_WORKFLOWS.md`

### Notes
- MT manual path is now the stable fallback when PDF sources are scan-heavy or structurally inconsistent.
- USDA source path remains externally dependent, but importer now fails loudly and predictably on source/schema issues.
