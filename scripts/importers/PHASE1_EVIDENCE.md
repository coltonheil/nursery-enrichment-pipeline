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
