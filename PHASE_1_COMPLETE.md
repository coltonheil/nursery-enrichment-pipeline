# Phase 1: Complete Implementation ✅

**Status:** READY TO RUN  
**Date:** 2026-01-29  
**Leads Ready:** 325 contactable Tier A+B leads  

---

## 🎯 What Phase 1 Does

**Complete pipeline:** Database → Instantly Campaigns

1. **Extract** qualified Tier A/B leads from database
2. **Format** with custom variables for personalization
3. **Sync** to appropriate Instantly campaigns (Tier A → Campaign A, Tier B → Campaign B)
4. **Track** sync status in database
5. **Report** results with detailed statistics

---

## 📊 Current Lead Status

**From Export Test:**
- **Total Tier A+B:** 1,168 leads
- **With owner_email:** 318 leads
- **With contact_email:** 72 leads
- **Total contactable:** 325 leads (27.8%)

**Breakdown:**
- **Tier A:** 151 contactable leads (32.3% of 468 total)
- **Tier B:** 174 contactable leads (24.9% of 700 total)

**Sample Lead (Tier A):**
```json
{
  "email": "william.bos@bosgreenhouse.com",
  "first_name": "William",
  "last_name": "Bos",
  "company_name": "BOS WILLIAM GREENHOUSE & FARMS",
  "custom_variables": {
    "city": "GRAND RAPIDS",
    "state": "MI",
    "business_type": "greenhouse_propagation",
    "tier": "A",
    "score": "110",
    "phone": "+1 616-949-0407",
    "website": "http://www.bosgreenhouse.com/",
    "lead_id": "1619"
  }
}
```

---

## 🏗️ Architecture

### Module 1: `phase1_lead_export.py` (13.4 KB)

**Purpose:** Extract and format leads from database

**Key Classes:**
- `InstantlyLead` - Data structure for Instantly API format
- `LeadExporter` - Database query and export logic

**Features:**
- Tier filtering (A, B, or AB)
- Email preference (owner_email vs contact_email)
- Contact name parsing
- Custom variable generation
- Export statistics

**Test:** ✅ PASSED
```bash
python phase1_lead_export.py
# Output: 325 leads ready for export
```

---

### Module 2: `phase1_instantly_integration.py` (16.7 KB)

**Purpose:** Sync leads to Instantly campaigns via API

**Key Classes:**
- `InstantlyClient` - Direct Instantly API V2 client
- `SyncResult` - Result tracking for each lead
- `InstantlySyncManager` - Batch sync orchestration

**Features:**
- Duplicate detection (checks if lead already in campaign)
- Batch processing with progress tracking
- Rate limiting (0.5s delay between API calls)
- Database sync log (tracks every sync attempt)
- Detailed error reporting

**Database Tables Created:**
```sql
CREATE TABLE instantly_sync_log (
    id INTEGER PRIMARY KEY,
    lead_id INTEGER NOT NULL,
    campaign_id TEXT NOT NULL,
    email TEXT NOT NULL,
    tier TEXT NOT NULL,
    sync_status TEXT,        -- 'synced' or 'failed'
    sync_error TEXT,
    synced_at TIMESTAMP,
    response_data TEXT,
    UNIQUE(lead_id, campaign_id)
);
```

**Test:** Ready (requires API key)

---

### Module 3: `phase1_run.py` (11.1 KB)

**Purpose:** Main orchestrator - ties everything together

**Features:**
- Command-line interface
- Tier selection (A, B, or AB)
- Test mode (limit to 5 leads)
- Dry run mode (preview without syncing)
- Progress tracking
- Final statistics report

**Usage Examples:**
```bash
# Test with 5 leads
python phase1_run.py --test

# Dry run (preview)
python phase1_run.py --tier AB --dry-run

# Sync Tier A only
python phase1_run.py --tier A

# Sync Tier B only
python phase1_run.py --tier B

# Sync all A+B leads
python phase1_run.py --tier AB
```

---

## 🚀 How to Run

### Prerequisites

1. **Environment variables set** (`.env`):
   ```
   INSTANTLY_API_KEY=MzBkNGMxZj...
   INSTANTLY_CAMPAIGN_TIER_A=ed77b2f2-2e17-40f3-a8d8-e79bb31f874a
   INSTANTLY_CAMPAIGN_TIER_B=ebc01294-5440-46b0-ae6d-bdab2d0a252b
   ```

2. **Virtual environment activated**:
   ```bash
   cd ~/clawd/projects/nursery-enrichment-pipeline
   source venv/bin/activate
   ```

3. **Campaigns are PAUSED** in Instantly.ai (daily_max_leads = 0)
   - This prevents emails from sending immediately
   - You can review leads in Instantly UI first
   - Activate when ready by setting daily_max_leads > 0

---

### Step 1: Test with 5 Leads

**Recommended first step to validate everything works**

```bash
python phase1_run.py --test
```

**What happens:**
1. Exports 5 Tier A leads from database
2. Formats them for Instantly
3. Checks for duplicates
4. Syncs to appropriate campaigns
5. Shows detailed results

**Expected output:**
```
======================================================================
Phase 1: Lead Export → Instantly Campaigns
======================================================================

🧪 TEST MODE: Limiting to 5 leads

📊 Step 1: Analyzing Database
----------------------------------------------------------------------
Tier Filter: AB
  Total leads in tier: 1168
  With owner email: 318
  With contact email: 72
  Total contactable: 325 (27.8%)
  Breakdown: {'A': 151, 'B': 174}

📤 Step 2: Exporting Leads
----------------------------------------------------------------------
✅ Exported 5 leads

🎯 Step 3: Grouping by Tier
----------------------------------------------------------------------
Tier A: 5 leads
Tier B: 0 leads

🚀 Step 4: Syncing to Instantly
----------------------------------------------------------------------
✅ Sync log table created/verified

📤 Syncing 5 Tier A leads...
   Campaign: ed77b2f2-2e17-40f3-a8d8-e79bb31f874a

  [ 20%] ✅ william.bos@bosgreenhouse.com                    (1/5)
  [ 40%] ✅ audrey@eggplantsupply.com                        (2/5)
  [ 60%] ✅ andy.pleasantvalley@gmail.com                    (3/5)
  [ 80%] ✅ jackie@jwherbs.com                                (4/5)
  [100%] ✅ sales@hilltopgreenhouse.com                       (5/5)

======================================================================
📊 Final Results
======================================================================

Total Leads: 5
  ✅ Successful: 5
  ❌ Failed: 0

Database Sync History:
  Total synced (all time): 5
  Total failed (all time): 0
  By tier: {'A': {'synced': 5, 'failed': 0}}

✅ All leads synced successfully!
```

**If test succeeds:** ✅ Ready for full batch!  
**If test fails:** ❌ Check error messages and fix before continuing

---

### Step 2: Dry Run (Preview Full Batch)

**See what would be synced without actually syncing**

```bash
python phase1_run.py --tier AB --dry-run
```

**What happens:**
1. Exports all 325 contactable leads
2. Shows which campaigns they'll go to
3. Previews first 5 leads of each tier
4. **Does NOT sync** (safe to run multiple times)

**Expected output:**
```
⚠️  DRY RUN MODE - No leads will be synced

📊 Step 1: Analyzing Database
----------------------------------------------------------------------
...

🎯 Step 3: Grouping by Tier
----------------------------------------------------------------------
Tier A: 151 leads
Tier B: 174 leads

📋 Dry Run: Would sync the following leads:

Tier A → Campaign: ed77b2f2...
  1. william.bos@bosgreenhouse.com - BOS WILLIAM GREENHOUSE & FARMS (GRAND RAPIDS, MI)
  2. audrey@eggplantsupply.com - EGG PLANT URBAN FARM SUPPLY CO (SAINT PAUL, MN)
  3. andy.pleasantvalley@gmail.com - Pleasant Valley Greenhouse (Baldwin, WI)
  4. jackie@jwherbs.com - HERBAL THYMES & GATHERINGS LLC (SALINE, MI)
  5. sales@hilltopgreenhouse.com - HILLTOP GREENHOUSE & FARM LLC (ELLENDALE, MN)
  ... and 146 more

Tier B → Campaign: ebc01294...
  1. [...]
  ... and 169 more
```

---

### Step 3: Sync Production Batch

**IMPORTANT:** Only run this after:
1. ✅ Test with 5 leads succeeded
2. ✅ Dry run preview looks correct
3. ✅ Campaigns are PAUSED in Instantly
4. ✅ You're ready to add all leads

#### Option A: Sync Tier A First (Recommended)

**Start with highest-quality leads**

```bash
python phase1_run.py --tier A
```

**What happens:**
- Syncs 151 Tier A leads
- Takes ~2 minutes (0.5s delay per lead)
- Shows progress for each lead

**Then review in Instantly:**
1. Log into Instantly.ai
2. Open Tier A campaign
3. Review leads
4. When satisfied, proceed to Tier B

#### Option B: Sync Tier B

```bash
python phase1_run.py --tier B
```

**What happens:**
- Syncs 174 Tier B leads
- Takes ~2 minutes

#### Option C: Sync All A+B Together

```bash
python phase1_run.py --tier AB
```

**What happens:**
- Syncs all 325 leads
- Takes ~3-4 minutes total
- Progress shown for each lead

**Estimated time:** ~4 minutes for all 325 leads

---

## 🔍 Validation & Verification

### Check Sync Status in Database

```bash
sqlite3 data/leads.db "
SELECT 
  sync_status,
  tier,
  COUNT(*) as count
FROM instantly_sync_log
GROUP BY sync_status, tier
ORDER BY tier, sync_status;
"
```

**Expected output:**
```
synced|A|151
synced|B|174
```

### Check for Failed Syncs

```bash
sqlite3 data/leads.db "
SELECT email, tier, sync_error
FROM instantly_sync_log
WHERE sync_status = 'failed'
LIMIT 10;
"
```

**If any failures:** Review error messages and retry those specific leads

### Verify in Instantly.ai

1. **Log into Instantly:** https://app.instantly.ai
2. **Open Tier A Campaign:** `ed77b2f2-2e17-40f3-a8d8-e79bb31f874a`
   - Check lead count (should be 151)
   - Review custom variables (city, state, tier, etc.)
   - Verify email sequences are attached
3. **Open Tier B Campaign:** `ebc01294-5440-46b0-ae6d-bdab2d0a252b`
   - Check lead count (should be 174)
   - Same verification steps

---

## 📈 Success Metrics

**Phase 1 is successful when:**

- ✅ **Export test passes** (shows 325 leads)
- ✅ **Test sync passes** (5 leads sync successfully)
- ✅ **Full batch completes** with <5% failures
- ✅ **Leads appear in Instantly** campaigns
- ✅ **Custom variables populated** correctly
- ✅ **Sync log created** in database

**Expected Results:**
```
Total Leads Synced: 325
  Tier A: 151 (32% of Tier A total)
  Tier B: 174 (25% of Tier B total)
  Success Rate: >95%
```

---

## 🛡️ Safety Features

**Built-in Protection:**

1. **Duplicate Detection** - Won't add lead if already in campaign
2. **Rate Limiting** - 0.5s delay between API calls (prevents rate limit errors)
3. **Sync Logging** - Every sync attempt recorded in database
4. **Error Handling** - Failures logged but don't stop batch
5. **Dry Run Mode** - Preview before syncing
6. **Test Mode** - Validate with 5 leads first
7. **Campaigns Paused** - Emails won't send until you activate

---

## 🔧 Troubleshooting

### Error: "INSTANTLY_API_KEY not found"

**Fix:**
```bash
# Check .env file
cat .env | grep INSTANTLY_API_KEY

# If missing, add it
echo "INSTANTLY_API_KEY=your_key_here" >> .env
```

### Error: "Campaign IDs not found"

**Fix:**
```bash
# Check campaign IDs in .env
cat .env | grep INSTANTLY_CAMPAIGN

# Should see:
# INSTANTLY_CAMPAIGN_TIER_A=ed77b2f2-2e17-40f3-a8d8-e79bb31f874a
# INSTANTLY_CAMPAIGN_TIER_B=ebc01294-5440-46b0-ae6d-bdab2d0a252b
```

### Error: "HTTP 429: Rate Limit"

**Fix:** Increase `rate_limit_delay` in `phase1_instantly_integration.py`:
```python
# Line 389 - increase from 0.5 to 1.0
rate_limit_delay=1.0,  # Slower but safer
```

### Some Leads Failed to Sync

**Diagnose:**
```bash
sqlite3 data/leads.db "
SELECT email, sync_error
FROM instantly_sync_log
WHERE sync_status = 'failed';
"
```

**Common errors:**
- "Lead already exists" → Already in campaign (safe to ignore)
- "Invalid email" → Email format issue (fix in database)
- "Timeout" → Network issue (retry)

**Retry failed leads:**
```bash
# Export failed lead IDs to CSV
sqlite3 data/leads.db -csv "
SELECT lead_id FROM instantly_sync_log WHERE sync_status = 'failed';
" > failed_leads.csv

# TODO: Create retry script if needed
```

---

## 📁 Files Created

**Phase 1 Modules:**
- `phase1_lead_export.py` (13.4 KB) - Export & formatting
- `phase1_instantly_integration.py` (16.7 KB) - Instantly API integration
- `phase1_run.py` (11.1 KB) - Main orchestrator

**Documentation:**
- `PHASE_1_COMPLETE.md` (this file) - Complete guide
- `CAMPAIGNS_READY.md` - Campaign details
- `COMPOSIO_INSTANTLY_SETUP.md` - Integration docs

**Configuration:**
- `.env` - API keys and campaign IDs

**Data:**
- `data/leads.db` - Main database (35 MB)
  - Table: `leads` - All lead data
  - Table: `instantly_sync_log` - Sync tracking (NEW)

---

## 🎯 Next Steps After Phase 1

**Once leads are synced:**

1. **Review in Instantly**
   - Check that custom variables populated correctly
   - Verify email sequences look good
   - Make any copy adjustments needed

2. **Activate Campaigns** (when ready to send)
   - Log into Instantly.ai
   - Set `daily_max_leads` for each campaign:
     - Start with 20-30 per day
     - Increase gradually as sender reputation builds
   - Monitor bounce rates (<2% is good)

3. **Phase 2: Review Interface** (Next Implementation)
   - Web UI to review leads before sending
   - Staging area with manual approval
   - Edit/remove specific leads
   - Batch operations

4. **Phase 3: Bi-directional Sync**
   - Webhook listener for replies
   - Update database with engagement data
   - Auto-tag interested leads
   - Reply tracking

---

## ✅ Phase 1 Checklist

**Before Running:**
- [ ] Campaigns created in Instantly (DONE ✓)
- [ ] Campaign IDs in `.env` (DONE ✓)
- [ ] Instantly API key in `.env` (DONE ✓)
- [ ] Database has Tier A/B leads (DONE ✓ - 325 contactable)
- [ ] Export test passes (DONE ✓)

**Execution:**
- [ ] Test sync (5 leads) passes
- [ ] Dry run preview looks correct
- [ ] Full batch sync completes
- [ ] Leads appear in Instantly campaigns
- [ ] Custom variables populated
- [ ] Sync log created in database

**Post-Sync:**
- [ ] Verified in Instantly UI
- [ ] Checked sync stats in database
- [ ] Reviewed any failures
- [ ] Ready for Phase 2 or campaign activation

---

**🎉 Phase 1 is READY TO RUN!**

Run `python phase1_run.py --test` to start.
