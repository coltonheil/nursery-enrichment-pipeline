# Phase 5: Scoring Engine - COMPLETE

## Summary

Successfully implemented a comprehensive scoring engine that evaluates leads based on 23 weighted signals (13 positive, 10 negative) and assigns them to tiers (A/B/C/U) for prioritization.

## Test Results

**Scoring Test: 678 leads scored in database**

### Tier Distribution:
- **Tier A** (≥60 points): 1 lead (0.1%) - Top wholesale prospects
- **Tier B** (30-59 points): 0 leads (0.0%) - Medium priority
- **Tier C** (<30 points): 2 leads (0.3%) - Lower priority
- **Tier U** (No data): 675 leads (99.6%) - Not yet enriched

### Top Scored Leads:

**Tier A:**
- Noffke Machining and Trees: **70 points** (5 signals)
  - +35 wholesale
  - +20 multiple locations
  - +15 soil relevance
  - +10 state (WI)

**Tier C:**
- Klein's Floral And Greenhouses: **10 points** (6 signals)
  - +25 container production, +15 soil relevance, +10 state (WI)
  - -15 gift shop, -15 workshops, -10 high reviews
- Outdoor Expressions: **5 points** (3 signals)
  - -20 landscaping services, +15 soil relevance, +10 state (WI)

**Note:** Most leads are Tier U because only 3/678 have been enriched with Gemini AI. Once all leads are scraped and enriched, the distribution will be more balanced.

---

## What Was Built

### 1. Scoring Engine (`enrichment/scorer.py`)

**Positive Signals (13 total):**
| Signal | Points | Description |
|--------|--------|-------------|
| is_wholesale | +35 | Sells to wholesale/trade customers |
| cannabis_business | +30 | Cannabis cultivation business |
| closed_weekends | +25 | Closed both Saturday and Sunday |
| large_greenhouse | +25 | Greenhouse > 5,000 sq ft |
| container_production | +25 | Container/pot production |
| acreage_mentioned | +20 | Acreage mentioned (significant size) |
| appointment_only | +20 | Appointment only (not retail-focused) |
| multiple_locations | +20 | Multiple physical locations |
| soil_relevance | +15 | Uses potting soil/growing media |
| closed_saturday | +10 | Closed on Saturday |
| closed_sunday | +10 | Closed on Sunday |
| state_wi | +10 | Located in Wisconsin |
| no_hours_listed | +5 | No hours listed (wholesale indicator) |

**Negative Signals (10 total):**
| Signal | Points | Description |
|--------|--------|-------------|
| christmas_tree | -30 | Christmas tree farm |
| sod_turf | -30 | Sod/turf grass production |
| bare_root | -20 | Bare root production |
| ball_and_burlap | -20 | Ball and burlap (B&B) trees |
| landscaping_services | -20 | Landscaping installation services |
| gift_shop | -15 | Gift shop/home decor focus |
| workshops_classes | -15 | Workshops, classes, or events |
| high_reviews | -10 | High review count (> 100) |
| orchard_upick | -10 | U-pick orchard/fruit farm |
| tree_farm_field | -10 | Field-grown tree farm |

**Tier Thresholds:**
- **Tier A:** Score ≥ 60 (highest priority)
- **Tier B:** Score 30-59 (medium priority)
- **Tier C:** Score < 30 (lower priority)
- **Tier U:** No data (no website or not enriched)

### 2. Core Functions

```python
def calculate_score(lead):
    """
    Calculate score based on all signals.
    Returns: {total, signals, tier, has_data}
    """

def assign_tier(score, has_data):
    """Assign tier based on score thresholds"""

def parse_hours(hours_json):
    """Parse Google Places hours to detect weekend closures"""
```

**Smart Features:**
- Graceful handling of missing data (defaults to False/None)
- JSON parsing for arrays (crops_grown, size_signals)
- JSON parsing for objects (negative_indicators)
- Hours parsing to detect closed weekends vs individual days
- Score breakdown with explanations for each signal

### 3. Database Schema (4 new columns)

Added to `database/models.py`:
```sql
score INTEGER              -- Total score
score_breakdown TEXT       -- JSON with full breakdown
tier TEXT                  -- A/B/C/U
scored_at TIMESTAMP        -- When scored
```

**Score Breakdown Format:**
```json
{
  "total": 70,
  "signals": [
    {"signal": "is_wholesale", "points": 35, "value": true, "description": "..."},
    {"signal": "multiple_locations", "points": 20, "value": true, "description": "..."},
    {"signal": "soil_relevance", "points": 15, "value": true, "description": "..."}
  ],
  "tier": "A",
  "has_data": true
}
```

### 4. Database Functions

```python
def update_lead_score(lead_id, score_data):
    """Save score and tier to database"""

def get_leads_by_tier(tier):
    """Get all leads with specific tier"""

def get_tier_distribution():
    """Get counts for each tier"""
    # Returns: {'A': 1, 'B': 0, 'C': 2, 'U': 675, 'total': 678}

def get_leads_for_scoring():
    """Get all leads for scoring"""
```

### 5. Flask Routes

**Added to `app.py`:**

- `POST /score/all` - Score all leads in database
- `POST /score/<lead_id>` - Rescore single lead
- `GET /api/tier-distribution` - Get tier counts (for UI)

**Response Format:**
```json
{
  "success": true,
  "message": "Scored 678 leads",
  "tier_distribution": {"A": 1, "B": 0, "C": 2, "U": 675}
}
```

### 6. User Interface

**Added to `templates/leads.html`:**

**Header:**
- "Score All Leads" button (green, calculator icon)

**Tier Distribution Dashboard:**
- 4-column card layout showing A/B/C/U counts
- Percentages calculated automatically
- Color-coded borders (green/blue/yellow/gray)
- Hidden until leads are scored

**Table Updates:**
- Added "Tier" column with color-coded badges:
  - Tier A: Green with trophy icon
  - Tier B: Blue
  - Tier C: Yellow
  - Tier U: Gray
  - Not Scored: Light gray
- Added "Score" column showing point total
- Removed redundant "Enrichment Status" column

**Added to `static/js/app.js`:**

- Score All button click handler
- Tier distribution loader (runs on page load)
- Tier distribution updater (after scoring)
- Auto-reload after scoring completes

### 7. Testing

**Test Files:**
1. `enrichment/scorer.py` - Built-in test with 3 cases
2. `test_scoring.py` - Full database test

**Test Coverage:**
- ✅ High-scoring wholesale nursery (155 points, Tier A)
- ✅ Retail garden center with negatives (35 points, Tier B)
- ✅ No data leads (0 points, Tier U)
- ✅ Real database: 678 leads scored
- ✅ Tier distribution calculation
- ✅ Score breakdown storage
- ✅ Top signals identification

---

## Scoring Logic Examples

### Example 1: High-Scoring Wholesale Nursery
**Input:**
- Wholesale nursery in Wisconsin
- 10,000 sq ft greenhouse
- 45 acres
- Container production
- Appointment only
- No hours listed

**Signals Triggered:**
- +35 wholesale
- +25 large greenhouse
- +25 container production
- +20 acreage
- +20 appointment only
- +15 soil relevance
- +10 state WI
- +5 no hours

**Total: 155 points → Tier A**

### Example 2: Retail Garden Center
**Input:**
- Retail garden center in Wisconsin
- Container plants sold
- Gift shop and workshops
- 150 reviews
- Closed on weekends

**Signals Triggered:**
- +25 closed weekends
- +25 container production
- +15 soil relevance
- +10 state WI
- -15 gift shop
- -15 workshops
- -10 high reviews

**Total: 35 points → Tier B**

### Example 3: Tier U (No Data)
**Input:**
- Lead has no website OR
- Gemini enrichment not completed

**Result: Tier U (insufficient data)**

---

## Architecture Highlights

### Data Flow:
```
Lead → calculate_score() → {
  Checks has_data (website + gemini_status)
  Evaluates 23 signals
  Calculates total
  Assigns tier
  Returns breakdown
} → update_lead_score() → Database
```

### Signal Evaluation:
- All signals default to False/None (safe)
- Boolean checks: `if get_value('is_wholesale')`
- Numeric thresholds: `if greenhouse_sqft > 5000`
- JSON parsing: `json.loads(negative_indicators)`
- String checks: `if 'cannabis' in business_type.lower()`

### Hours Parsing:
```python
hours = {'0': 'Closed', '6': 'Closed'}  # Sunday and Saturday
→ closed_weekends = True (+25 points)

hours = {'6': 'Closed'}  # Saturday only
→ closed_saturday = True (+10 points)
```

---

## UI/UX Flow

1. **User clicks "Score All Leads"**
   - Confirmation dialog appears
   - Button shows spinner: "Scoring..."

2. **Backend processes**
   - Scores all 678 leads
   - Saves to database
   - Returns tier distribution

3. **UI updates**
   - Success alert: "Scored 678 leads"
   - Tier distribution cards appear
   - Table shows tier badges and scores
   - Page auto-reloads after 2 seconds

4. **Tier Distribution Display**
   - Card layout: A (green) | B (blue) | C (yellow) | U (gray)
   - Shows count and percentage for each
   - Hidden if no scores exist

---

## Current Database State

**Total Leads:** 678

**By Enrichment Status:**
- Scraped: 4 leads
- Gemini Enriched: 3 leads
- Pending: 674 leads

**By Tier (after scoring all):**
- Tier A: 1 lead (0.1%)
- Tier B: 0 leads (0.0%)
- Tier C: 2 leads (0.3%)
- Tier U: 675 leads (99.6%)

**Expected Distribution (after full enrichment):**
- Tier A: ~7-10% (best wholesale prospects)
- Tier B: ~30-35% (medium priority)
- Tier C: ~40-50% (lower priority)
- Tier U: ~10-15% (insufficient data)

---

## Next Steps

### Phase 6: Review Interface

Now ready to implement:
1. **Filterable table** - Filter by tier, state, business type
2. **Sortable columns** - Sort by score, name, tier
3. **Lead detail modal** - View full data + score breakdown
4. **Manual overrides** - Override tier, add notes
5. **Bulk actions** - Change tier for multiple leads

### Phase 7: Email Personalization

Once review interface is complete:
- Generate custom first lines for Tier A+B leads
- Use Gemini to create personalized opening lines
- Reference specific business details (organic focus, crops, etc.)

---

## Files Modified

1. ✅ `enrichment/scorer.py` - Created (600+ lines)
2. ✅ `database/models.py` - Added 4 columns + 4 functions
3. ✅ `app.py` - Added 3 routes + imports
4. ✅ `templates/leads.html` - Added tier UI + distribution
5. ✅ `static/js/app.js` - Added scoring handlers
6. ✅ `test_scoring.py` - Created

---

## Known Limitations

1. **Most Leads are Tier U:**
   - Only 3/678 leads have been enriched
   - Need to run full scraping + AI enrichment pipeline
   - Expected time: ~15 minutes for 678 leads

2. **Hours Parsing:**
   - Google Places hours format varies
   - Some businesses may not have hours data
   - Fallback: treats missing hours as "no_hours_listed" (+5 points)

3. **Cannabis Detection:**
   - Only checks business_type field
   - May miss cannabis businesses with generic names
   - Could enhance with website text scanning

---

## Phase 5 Status: ✅ COMPLETE

**Phase 5A:** ✅ Scoring Function (23 signals implemented)
**Phase 5B:** ✅ Score Breakdown Storage (JSON format)
**Phase 5C:** ✅ Scoring UI (tier distribution + badges)

**Ready for Phase 6: Review Interface**
