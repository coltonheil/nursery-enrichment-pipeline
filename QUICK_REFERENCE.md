# Phase 1: Quick Reference

## 🚀 Run Commands

```bash
# Activate environment
cd ~/clawd/projects/nursery-enrichment-pipeline
source venv/bin/activate

# Test with 5 leads
python phase1_run.py --test

# Preview full batch (no syncing)
python phase1_run.py --tier AB --dry-run

# Sync Tier A only
python phase1_run.py --tier A

# Sync Tier B only
python phase1_run.py --tier B

# Sync all A+B leads
python phase1_run.py --tier AB
```

## 📊 Check Status

```bash
# Export stats
python phase1_lead_export.py

# Sync stats (after running)
sqlite3 data/leads.db "
SELECT sync_status, tier, COUNT(*) as count
FROM instantly_sync_log
GROUP BY sync_status, tier;
"

# Failed syncs
sqlite3 data/leads.db "
SELECT email, tier, sync_error
FROM instantly_sync_log
WHERE sync_status = 'failed';
"
```

## 🎯 Current Stats

- **Tier A contactable:** 151 leads (32.3% of 468 total)
- **Tier B contactable:** 174 leads (24.9% of 700 total)
- **Total ready to sync:** 325 leads

## 📋 Campaign IDs

```
Tier A: ed77b2f2-2e17-40f3-a8d8-e79bb31f874a
Tier B: ebc01294-5440-46b0-ae6d-bdab2d0a252b
```

## ⚡ Recommended Flow

1. `python phase1_run.py --test` → Validate with 5 leads
2. `python phase1_run.py --dry-run --tier AB` → Preview full batch
3. `python phase1_run.py --tier A` → Sync Tier A (highest quality)
4. Review in Instantly.ai
5. `python phase1_run.py --tier B` → Sync Tier B
6. Final review and activate campaigns

---

**Full docs:** `PHASE_1_COMPLETE.md`
