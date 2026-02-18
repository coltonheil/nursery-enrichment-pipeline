# Phase 1 Evidence Bundle (MI/IL/OR/USDA/MT)

Date: 2026-02-18
Scope: Phase 1 importer DoD hardening + verification only.

## 1) Commands run (with artifacts)

### Discovery (Tavily-first)
```bash
source ~/.openclaw/.secrets/master.env
uv run --with tavily-python python3 ~/.openclaw/workspace/skills/tavily/scripts/tavily_search.py "USDA AMS hemp producer license list csv" --api-key "$TAVILY_API_KEY"
uv run --with tavily-python python3 ~/.openclaw/workspace/skills/tavily/scripts/tavily_search.py "Montana Department of Revenue cannabis license list pdf" --api-key "$TAVILY_API_KEY"
```

### Importer verification runs
```bash
# MI
python3 scripts/importers/import_mi_cra.py --dry-run --summary-json scripts/importers/evidence/mi_dry_summary.json
python3 scripts/importers/import_mi_cra.py --summary-json scripts/importers/evidence/mi_live_summary.json
python3 scripts/importers/import_mi_cra.py --summary-json scripts/importers/evidence/mi_rerun_summary.json

# IL
python3 scripts/importers/import_il_idfpr.py --dry-run
python3 scripts/importers/import_il_idfpr.py
python3 scripts/importers/import_il_idfpr.py

# OR
python3 scripts/importers/import_or_olcc.py --dry-run --summary-json scripts/importers/evidence/or_dry_summary.json
python3 scripts/importers/import_or_olcc.py --summary-json scripts/importers/evidence/or_live_summary.json
python3 scripts/importers/import_or_olcc.py --summary-json scripts/importers/evidence/or_rerun_summary.json

# USDA
python3 scripts/importers/import_usda_hemp.py --dry-run --summary-json scripts/importers/evidence/usda_dry_summary.json
python3 scripts/importers/import_usda_hemp.py --summary-json scripts/importers/evidence/usda_live_summary.json
python3 scripts/importers/import_usda_hemp.py --summary-json scripts/importers/evidence/usda_rerun_summary.json

# MT PDF attempt (diagnostics)
python3 scripts/importers/import_mt_revenue.py --dry-run --pdf-url https://revenuefiles.mt.gov/files/Cannabis/Licensed-Cultivator-List.pdf --summary-json scripts/importers/evidence/mt_dry_summary.json

# MT manual fallback path proof
python3 scripts/importers/import_mt_revenue.py --dry-run --input-file scripts/importers/evidence/mt_manual_fallback.csv --summary-json scripts/importers/evidence/mt_manual_dry_summary.json
python3 scripts/importers/import_mt_revenue.py --input-file scripts/importers/evidence/mt_manual_fallback.csv --summary-json scripts/importers/evidence/mt_manual_live_summary.json
python3 scripts/importers/import_mt_revenue.py --input-file scripts/importers/evidence/mt_manual_fallback.csv --summary-json scripts/importers/evidence/mt_manual_rerun_summary.json
```

## 2) DoD run matrix (dry/live/rerun)

| Importer | Dry-run | Live-run attempt | Rerun idempotency | Evidence |
|---|---|---|---|---|
| MI (`mi_cra`) | BLOCKED (0 fetched, exit non-zero) | BLOCKED (0 fetched, exit non-zero) | BLOCKED same reproducible result | `evidence/mi_*` |
| IL (`il_idfpr`) | PASS (`0 new, 227 existing`) | PASS (`0 new, 227 existing`) | PASS (`0 new, 227 existing`) | `evidence/il_*` |
| OR (`or_olcc`) | BLOCKED (0 fetched, exit non-zero) | BLOCKED (0 fetched, exit non-zero) | BLOCKED same reproducible result | `evidence/or_*` |
| USDA (`usda_hemp`) | BLOCKED (no configured USDA CSV source) | BLOCKED same | BLOCKED same | `evidence/usda_*` |
| MT (`mt_revenue`) | PDF parse: 0 matched / 549 unmatched (diagnostics emitted) | Manual fallback live run: `3 new` | Manual fallback rerun: `0 new, 3 existing` | `evidence/mt_*` |

## 3) Source count table (`registry_source, segment, COUNT(*)`) + expected-range status

SQL run:
```sql
SELECT registry_source, segment, COUNT(*) AS cnt
FROM registries
GROUP BY registry_source, segment
ORDER BY registry_source, segment;
```

Observed:

| registry_source | segment | count | Expected range / rule | Status |
|---|---|---:|---|---|
| il_idfpr | cannabis_grower | 224 | 97–119 (roadmap estimate) | OUT OF RANGE (needs source/parse calibration) |
| mt_revenue | cannabis_grower | 3 | Best-effort (>=1 acceptable) | PASS (manual fallback artifact path) |
| mi_cra | cannabis_grower | 0 | 720–880 | BLOCKED (fetch returned zero) |
| or_olcc | cannabis_grower | 0 | 1,350–1,650 | BLOCKED (endpoint/connectivity/schema failures) |
| usda_hemp | hemp_producer | 0 | USDA published counts by target states | BLOCKED (no direct CSV configured) |

## 4) QA checks

SQL run:
```sql
SELECT COUNT(*) FROM registries WHERE business_name IS NULL OR TRIM(business_name)='';
SELECT COUNT(*) FROM registries WHERE state IS NULL OR TRIM(state)='';
SELECT COUNT(*) FROM registries WHERE promoted_at IS NOT NULL;
```

Results:
- Null/blank `business_name`: `0`
- Null/blank `state`: `0`
- `promoted_at IS NOT NULL`: `0`

## 5) Hardening evidence by requirement

### B) USDA unblocking hardening
- Added reproducible source strategy in importer docstring and notes.
- Added env var override + CLI override (`USDA_HEMP_CSV_URL`, `--csv-url`).
- Added explicit schema validation errors/warnings for missing key columns.
- Added blocked-mode hints with discovery URLs and reproducible setup steps.

### C) MT robustness
- PDF parse diagnostics now report matched/unmatched and reject reasons.
- Manual fallback path implemented and executed with local CSV artifact:
  - `scripts/importers/evidence/mt_manual_fallback.csv`
  - live run inserted 3 rows; rerun proved idempotency.

### D) MI/OR diagnostics hardening
- Added machine-readable summary output (`--summary-json`) in both importers.
- Added explicit non-zero exit on zero-fetch contract (default; overridable with `--allow-empty-fetch`).

### E) IL provenance alignment
- Added explicit provenance rationale in `import_il_idfpr.py` header and `PHASE1_NOTES.md`.
- Rationale: keep `registry_source=il_idfpr` for Phase 1 naming/query continuity while source document provenance is carried in `raw_data`.

## 6) Representative output snippets

MI blocked (repeatable):
```text
[MI CRA] ⚠️  No records fetched.
... portal blocked bot traffic / form change / table change ...
```

OR blocked (repeatable):
```text
Tableau error: SSLCertVerificationError ...
CAMP eLicensing error: Expecting value: line 1 column 1 (char 0)
[OR OLCC] ⚠️  No records fetched.
```

USDA blocked (repeatable):
```text
[USDA HEMP] BLOCKED: USDA HeMP producer-level public CSV URL not configured ...
[USDA HEMP] HINT: set USDA_HEMP_CSV_URL or pass --csv-url <usda-export.csv>
```

MT diagnostics + fallback:
```text
[MT REVENUE] Parse diagnostics: {"lines_total": 549, "matched_pdf": 0, "unmatched_pdf": 549}
[MT REVENUE] Using manual fallback input .../mt_manual_fallback.csv
[MT REVENUE] Import complete (dry_run=False): New records: 3
[MT REVENUE] Import complete (dry_run=False): New records: 0, Already existed: 3
```
