# Phase 1 Importer Notes

## Added / Updated
- `import_il_idfpr.py` (Illinois cannabis growers via IDOA licensee PDF)
- `import_usda_hemp.py` (USDA hemp importer with direct CSV ingestion mode + explicit block messaging when no direct source is configured)
- `import_mt_revenue.py` (Montana PDF importer scaffold + explicit blocked mode when source PDF is not provided)
- `import_mi_cra.py` and `import_or_olcc.py` updated for consistent idempotency + dry-run summary parity (`new/existing/errors`)

## Blockers documented
- USDA HeMP producer list is not available via a stable unauthenticated direct endpoint in this environment; importer supports `--csv-url` / `USDA_HEMP_CSV_URL` for direct USDA export ingestion.
- Montana DOR source remains PDF-first and unstable; importer supports `--pdf-url` for best-effort parse and clearly reports blocked mode otherwise.

## Verification run
- IL dry-run and live import executed.
- IL re-run confirms idempotency (`0 new, existing=N`).
- Source count query executed:
  - `SELECT registry_source, segment, COUNT(*) ...`
