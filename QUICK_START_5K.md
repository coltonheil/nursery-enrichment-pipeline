# Quick Start: Run 5K Lead Batch

**Goal:** Process 5,000 leads through the full pipeline with email hunting optimizations active.

**Time:** ~2-4 hours (depending on API limits and website speeds)

---

## Option 1: Process Next 5K Pending Leads (RECOMMENDED)

You already have 4,647 pending leads. Let's process them:

### Step 1: Start Flask Server

```bash
cd ~/clawd/projects/nursery-enrichment-pipeline
./venv/bin/python app.py
```

Server will start on `http://localhost:5000`

### Step 2: Run the Pipeline

**Option A: Use the helper script (automated monitoring)**
```bash
# In a new terminal
cd ~/clawd/projects/nursery-enrichment-pipeline
chmod +x run_5k_batch.py
./venv/bin/python run_5k_batch.py --fresh
```

This will:
- Start the pipeline for 5,000 pending leads
- Show real-time progress with ETA
- Display final Tier A/B distribution
- Track email coverage

**Option B: Use the web UI (manual monitoring)**
1. Open browser: `http://localhost:5000`
2. Click "Start Full Pipeline"
3. Set batch size: 5000
4. Click "Start"
5. Monitor progress on the page

---

## Option 2: Upload New Lead File

If you want to start with a fresh 5K lead file:

### Upload via Script

```bash
./venv/bin/python run_5k_batch.py --upload /path/to/your/leads.xlsx
```

### Upload via Web UI

1. Go to `http://localhost:5000`
2. Click "Upload Leads"
3. Select your Excel file
4. Click "Upload"
5. Then start the pipeline (Step 2 above)

---

## What to Expect

### Pipeline Steps (4 stages)

1. **Google Places** (~1-2s per lead)
   - Enriches business data
   - Finds websites, phones, ratings

2. **Website Scraping** (~2-5s per lead)
   - Downloads website content
   - Extracts text for AI analysis

3. **Gemini AI** (~3-4s per lead)
   - Extracts structured data
   - Identifies business type, owner name
   - Assesses soil/growing media relevance

4. **Email Hunting & Scoring** (~0.5s per lead)
   - **NEW:** 3-layer email discovery
   - Pattern inference (free, fast)
   - Brave search fallback (if needed)
   - Generic email backup (100% coverage)
   - Calculates tier (A/B/C/U)

### Expected Timeline

| Leads | Time (min) | Time (hours) |
|-------|------------|--------------|
| 1,000 | ~40-60 min | 0.7-1.0h |
| 2,500 | ~100-150 min | 1.7-2.5h |
| 5,000 | ~200-300 min | 3.3-5.0h |

**Bottleneck:** Website scraping + Gemini AI (Steps 2-3)

### Expected Results (Based on Current Data)

| Metric | Current (9K) | Expected (5K) |
|--------|--------------|---------------|
| Tier A | 2.1% | ~105 leads |
| Tier B | 5.1% | ~255 leads |
| Tier C | 10.7% | ~535 leads |
| Tier U | 82.0% | ~4,105 leads |

**High-Value Leads (A+B):** ~360 leads (7.2%)

**Email Coverage:**
- Before optimization: ~77% (Tier A+B only)
- After optimization: **~85-90%** (with 3-layer fallback)
- Generic fallback: **100%** (all domains)

---

## Monitoring Progress

### Real-Time Stats

While pipeline is running:

**Via Script:**
```bash
./venv/bin/python run_5k_batch.py --fresh
# Shows: [45%] ai_enrichment Step 3/4: AI enrichment ETA: 85m
```

**Via Web UI:**
- Go to `http://localhost:5000`
- Progress bar shows overall completion
- Status message shows current step

**Via API:**
```bash
curl http://localhost:5000/pipeline-status
curl http://localhost:5000/api/stats
```

### Check Progress Manually

```bash
cd ~/clawd/projects/nursery-enrichment-pipeline
./venv/bin/python << 'EOF'
import sqlite3
conn = sqlite3.connect('data/leads.db')
cursor = conn.cursor()

cursor.execute("SELECT COUNT(*) FROM leads WHERE tier = 'A'")
tier_a = cursor.fetchone()[0]

cursor.execute("SELECT COUNT(*) FROM leads WHERE tier = 'B'")
tier_b = cursor.fetchone()[0]

cursor.execute("SELECT COUNT(*) FROM leads WHERE owner_email IS NOT NULL")
with_email = cursor.fetchone()[0]

print(f"Tier A: {tier_a}")
print(f"Tier B: {tier_b}")
print(f"With Email: {with_email}")
conn.close()
EOF
```

---

## After Pipeline Completes

### View Results

**Web UI:**
- Go to `http://localhost:5000/leads`
- Filter by Tier A or B
- Sort by score (highest first)
- Review emails and confidence scores

**Export for Instantly.ai:**
- Click "Export" tab
- Select Tier A and/or B
- Click "Export to CSV" or "Export to Excel"
- Import into Instantly.ai

### Analyze Results

```bash
./venv/bin/python << 'EOF'
import sqlite3
import pandas as pd

conn = sqlite3.connect('data/leads.db')

# Get Tier A+B with emails
df = pd.read_sql_query("""
    SELECT 
        business_name,
        owner_name,
        owner_email,
        email_confidence,
        email_method,
        tier,
        score,
        state
    FROM leads
    WHERE tier IN ('A', 'B')
        AND owner_email IS NOT NULL
    ORDER BY score DESC
""", conn)

conn.close()

print("Top 10 Leads:")
print(df.head(10))

print(f"\nTotal A+B with Email: {len(df)}")
print(f"Avg Confidence: {df['email_confidence'].mean():.1f}%")
print(f"Method Breakdown:")
print(df['email_method'].value_counts())
EOF
```

---

## Troubleshooting

### Pipeline Stuck

```bash
# Check what's happening
curl http://localhost:5000/pipeline-status | jq

# Stop pipeline
curl -X POST http://localhost:5000/stop-full-pipeline

# Resume from where it left off
./venv/bin/python run_5k_batch.py --resume
```

### Server Not Responding

```bash
# Restart Flask
# Kill old process
ps aux | grep app.py | grep -v grep | awk '{print $2}' | xargs kill

# Start fresh
cd ~/clawd/projects/nursery-enrichment-pipeline
./venv/bin/python app.py
```

### API Rate Limits

**Gemini:** 1-2s delay between requests (hardcoded)
**Brave Search:** 2s delay between searches (if needed)
**Google Places:** ~60 requests/min (user account limit)

If hitting limits: Pipeline will retry with exponential backoff

---

## What's New (Optimizations Active)

✅ **3-Layer Email Discovery:**
1. Pattern inference from owner name
2. Brave search fallback (if pattern fails)
3. Generic email (info@, contact@) as backup

✅ **Edge Case Handling:**
- Single names: "Joe" → joe@domain
- Couples: "Wayne and Michelle" → wayne@domain
- Noise removal: "a.k.a. ATTN:" stripped
- Family suffix: "Bachhuber family" → bachhuber@domain

✅ **100% Domain Coverage:**
- Even leads with no MX records get generic_email stored
- contact_form_url stored for manual outreach

✅ **All Integrated:**
- Email hunting runs automatically in Step 4
- Results stored: owner_email, email_confidence, email_method, generic_email

---

## Expected Outcome

**After 5K leads:**
- ~360 Tier A+B leads (7.2%)
- ~305 with personal emails (85%+)
- ~360 with generic fallback (100%)
- Ready to export to Instantly.ai
- Cost: ~$65 (Google Places + Gemini + Brave)

**Next Steps:**
1. Export Tier A+B to CSV
2. Import to Instantly.ai
3. Start email campaign
4. Monitor bounce rate to validate email quality

---

## Questions?

**Check logs:**
```bash
tail -f ~/clawd/projects/nursery-enrichment-pipeline/flask.log
```

**Database stats:**
```bash
sqlite3 data/leads.db "SELECT tier, COUNT(*) FROM leads GROUP BY tier;"
```

**Email coverage:**
```bash
sqlite3 data/leads.db "SELECT COUNT(*) FROM leads WHERE owner_email IS NOT NULL;"
```

---

**Ready to start?** Choose Option 1 (process pending) or Option 2 (upload new file) and run! 🚀
