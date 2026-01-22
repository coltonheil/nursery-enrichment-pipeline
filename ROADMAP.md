# Sales Enrichment Pipeline: 10-Phase Implementation Roadmap

## Document Purpose

This document provides a **MECE (Mutually Exclusive, Collectively Exhaustive)** implementation roadmap for transforming the Sweet Leaf Sales enrichment pipeline into a high-precision lead qualification system. Each phase is designed to be executed sequentially by Claude CLI with zero ambiguity.

**Project Location:** `C:\Projects_Local\Sweet leaf sales\nursery-enrichment-pipeline`

---

## Pre-Implementation: Claude Code Skills Installation

### Why Install Skills

Claude Code skills provide battle-tested patterns, reduce errors, and enable autonomous multi-step workflows. For this project, we need skills covering: TDD methodology, frontend design, database operations, and systematic debugging.

### Top 5 Required Skills

#### 1. obra/superpowers
**What it does:** Core development methodology with TDD, debugging, brainstorm→plan→execute workflow, and subagent-driven development.

**Why we need it:** Provides `/superpowers:brainstorm`, `/superpowers:write-plan`, `/superpowers:execute-plan` commands. Enforces RED-GREEN-REFACTOR TDD. Systematic debugging for the complex pipeline.

**Installation:**
```bash
# In Claude Code terminal
/plugin marketplace add obra/superpowers-marketplace
/plugin install superpowers@superpowers-marketplace
```

**Key skills activated:**
- `test-driven-development` — Write failing tests first, implement, refactor
- `systematic-debugging` — 4-phase root cause analysis
- `brainstorming` — Design refinement before coding
- `subagent-driven-development` — Parallel task execution with review

---

#### 2. anthropics/frontend-design
**What it does:** Creates distinctive, production-grade UI that avoids generic "AI slop" aesthetics.

**Why we need it:** The current Flask frontend needs significant improvement. This skill guides Claude to make bold design choices with proper typography, color, and motion.

**Installation:**
```bash
# Already available in Claude Code plugins
/plugin marketplace add anthropics/claude-code
/plugin install frontend-design@anthropics
```

**Key guidance:**
- Typography: Distinctive fonts, not Arial/Inter
- Color: Dominant colors with sharp accents, CSS variables
- Motion: CSS animations, scroll-triggered effects
- Layouts: Responsive, accessible, professional

---

#### 3. mrgoonie/claudekit-skills
**What it does:** Comprehensive skill collection including databases (PostgreSQL, MongoDB, SQLite patterns), backend development, and frontend development.

**Why we need it:** Database schema modifications, Flask backend patterns, and API design guidance.

**Installation:**
```bash
/plugin marketplace add mrgoonie/claudekit-skills
/plugin install databases@claudekit-skills
/plugin install backend-development@claudekit-skills
```

**Key skills activated:**
- `databases` — Schema design, query optimization, migrations
- `backend-development` — Flask/Python patterns, API design, testing

---

#### 4. richard-gyiko/data-wrangler-plugin
**What it does:** SQL analytics over CSV, Parquet, JSON, Excel, and databases using DuckDB.

**Why we need it:** Lead data analysis, export validation, scoring model testing on real data.

**Installation:**
```bash
/plugin marketplace add richard-gyiko/data-wrangler-plugin
/plugin install data-wrangler@data-wrangler-marketplace
```

**Key capabilities:**
- Direct SQLite queries from Claude
- CSV/Excel analysis for lead exports
- Data transformation and validation

---

#### 5. anthropics/webapp-testing
**What it does:** Tests local web applications using Playwright for UI verification and debugging.

**Why we need it:** Frontend changes need automated testing. Playwright can verify lead cards render correctly, forms work, exports generate.

**Installation:**
```bash
/plugin install webapp-testing@anthropics
```

**Key capabilities:**
- UI regression testing
- Form submission verification
- Screenshot capture for review

---

### Skills Installation Verification

After installing all skills, verify with:
```bash
/help
# Should show /superpowers:brainstorm, /superpowers:write-plan, /superpowers:execute-plan
```

---

## Phase Overview

| Phase | Name | Primary Focus | Dependencies | Deliverables |
|-------|------|---------------|--------------|--------------|
| 1 | Database Schema Evolution | Add new columns for ICP signals | None | Migration script, updated models.py |
| 2 | Gemini Prompt Engineering | Extract ICP-specific signals | Phase 1 | Updated gemini_client.py |
| 3 | Scoring Model Overhaul | ICP qualification gate + new signals | Phases 1-2 | New scorer.py |
| 4 | Geographic Intelligence | State-based scoring | Phase 3 | Geo scoring in scorer.py |
| 5 | Re-Enrichment Pipeline | Process existing leads with new prompts | Phases 1-4 | Updated leads in database |
| 6 | Frontend: Lead Card Redesign | Visual score breakdown | Phase 5 | Updated templates |
| 7 | Frontend: Review Workflow | Keyboard shortcuts, bulk actions | Phase 6 | JS + routes |
| 8 | Frontend: Dashboard | Pipeline stats, tier distribution | Phase 7 | New dashboard route |
| 9 | Pipeline Reliability | Resumable state, retry logic | Phase 8 | Updated app.py |
| 10 | Testing & Validation | End-to-end tests, manual review | Phase 9 | Test suite, validation report |

---

## Phase 1: Database Schema Evolution

### Objective
Add new columns to the `leads` table to store ICP-specific extraction fields from Gemini.

### Pre-Conditions
- Database exists at `data/leads.db`
- SQLite is accessible
- `database/models.py` has migration logic

### New Columns to Add

| Column Name | Type | Purpose |
|-------------|------|---------|
| `uses_growing_media` | BOOLEAN | Core ICP signal: do they use soil/growing media? |
| `production_method` | TEXT | "field", "container", "greenhouse", "hydroponic", "mixed" |
| `is_organic_certified` | BOOLEAN | Organic certification detected |
| `scale_indicators` | TEXT (JSON) | ["12 greenhouses", "40 acres", "500k plants/year"] |
| `purchases_soil` | BOOLEAN | Explicit mention of buying potting mix |
| `soil_brands_mentioned` | TEXT (JSON) | ["Pro-Mix", "Sungro", "Berger"] |
| `disqualification_signals` | TEXT (JSON) | ["landscaping", "lawn care", "retail only"] |
| `geo_score` | INTEGER | Geographic proximity score |
| `icp_qualified` | BOOLEAN | Passed ICP qualification gate |
| `icp_type` | TEXT | "primary", "secondary", "tertiary", "disqualified" |

### Implementation Steps

#### Step 1.1: Update models.py with new columns

**File:** `database/models.py`

**Location:** Add to `migrate_db()` function (around line 75-140)

```python
# New ICP-related columns
new_columns = [
    ("uses_growing_media", "BOOLEAN DEFAULT NULL"),
    ("production_method", "TEXT DEFAULT NULL"),
    ("is_organic_certified", "BOOLEAN DEFAULT NULL"),
    ("scale_indicators", "TEXT DEFAULT NULL"),  # JSON array
    ("purchases_soil", "BOOLEAN DEFAULT NULL"),
    ("soil_brands_mentioned", "TEXT DEFAULT NULL"),  # JSON array
    ("disqualification_signals", "TEXT DEFAULT NULL"),  # JSON array
    ("geo_score", "INTEGER DEFAULT 0"),
    ("icp_qualified", "BOOLEAN DEFAULT NULL"),
    ("icp_type", "TEXT DEFAULT NULL"),
]

for col_name, col_type in new_columns:
    try:
        cursor.execute(f"ALTER TABLE leads ADD COLUMN {col_name} {col_type}")
        print(f"Added column: {col_name}")
    except sqlite3.OperationalError as e:
        if "duplicate column" not in str(e).lower():
            raise
```

#### Step 1.2: Update Lead model class

**File:** `database/models.py`

**Location:** Lead class definition (around line 21-35)

Add these attributes to the Lead class or dataclass if using one.

#### Step 1.3: Run migration

```bash
cd "C:\Projects_Local\Sweet leaf sales\nursery-enrichment-pipeline"
.\venv\Scripts\Activate.ps1
python -c "from database.models import migrate_db; migrate_db()"
```

#### Step 1.4: Verify migration

```bash
sqlite3 data/leads.db ".schema leads" | grep -E "(uses_growing_media|icp_qualified|geo_score)"
```

### Acceptance Criteria
- [ ] All 10 new columns exist in `leads` table
- [ ] Migration runs without errors on existing database
- [ ] Existing lead data is preserved
- [ ] Column types match specification

### Rollback Plan
```sql
-- If needed, columns can be dropped (SQLite limitation: requires table recreation)
-- For safety, backup database before migration:
-- copy data/leads.db data/leads.db.backup
```

---

## Phase 2: Gemini Prompt Engineering

### Objective
Update the Gemini enrichment prompts to extract ICP-specific signals from website content.

### Pre-Conditions
- Phase 1 complete (new database columns exist)
- Gemini API key configured in `.env`
- `enrichment/gemini_client.py` exists

### Current State Analysis

**Current extraction fields (from CLAUDE.md):**
```
business_type, organic_focus, crops_grown, size_signals,
is_wholesale, container_production, owner_name, owner_email
```

**New extraction fields needed:**
```
uses_growing_media, production_method, is_organic_certified,
scale_indicators, purchases_soil, soil_brands_mentioned,
disqualification_signals
```

### Implementation Steps

#### Step 2.1: Define new JSON schema for Gemini response

**File:** `enrichment/gemini_client.py`

**Location:** Near top of file, after imports

```python
ENRICHMENT_SCHEMA = {
    "type": "object",
    "properties": {
        # Existing fields
        "business_type": {"type": "string"},
        "organic_focus": {"type": "boolean"},
        "crops_grown": {"type": "array", "items": {"type": "string"}},
        "size_signals": {"type": "array", "items": {"type": "string"}},
        "is_wholesale": {"type": "boolean"},
        "container_production": {"type": "boolean"},
        "owner_name": {"type": "string"},
        "owner_email": {"type": "string"},
        
        # NEW ICP fields
        "uses_growing_media": {
            "type": "boolean",
            "description": "Does this business use soil, potting mix, or growing media in production?"
        },
        "production_method": {
            "type": "string",
            "enum": ["field", "container", "greenhouse", "hydroponic", "mixed", "unknown"],
            "description": "Primary method of plant production"
        },
        "is_organic_certified": {
            "type": "boolean",
            "description": "Is the business certified organic or explicitly organic-focused?"
        },
        "scale_indicators": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Specific mentions of scale: square footage, greenhouse count, acreage, employee count, production volume"
        },
        "purchases_soil": {
            "type": "boolean",
            "description": "Any mention of purchasing potting soil, growing media, amendments, or soil inputs"
        },
        "soil_brands_mentioned": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Specific soil/amendment brands mentioned: Pro-Mix, Sungro, Berger, etc."
        },
        "disqualification_signals": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Signals that disqualify from ICP: landscaping services, lawn care, mowing, equipment dealer, retail only, gift shop"
        }
    },
    "required": ["uses_growing_media", "production_method", "disqualification_signals"]
}
```

#### Step 2.2: Update the enrichment prompt

**File:** `enrichment/gemini_client.py`

**Location:** `enrich_lead_with_gemini()` function (around line 100+)

```python
ENRICHMENT_PROMPT = """
You are analyzing a business website to determine if they are a potential buyer of bulk worm castings (vermicompost) for agricultural or horticultural use.

WEBSITE CONTENT:
{website_text}

EXTRACTION FOCUS - Soil Amendment Buyer Signals:

1. PRODUCTION METHOD DETECTION (Critical)
   - Container grown / potted plants / plug trays / liner production = HIGH priority
   - Greenhouse propagation / heated greenhouse = HIGH priority  
   - Field grown (non-organic) = MEDIUM priority
   - Microgreens in soil trays = HIGH priority
   - Hydroponic / no soil = LOW priority (but still note it)
   - Landscaping installation / lawn care = DISQUALIFY

2. ORGANIC SIGNALS (Strong buying indicator)
   - "Certified Organic" or USDA Organic logo
   - "Organic" in business name
   - Mentions of organic practices, organic certification
   - Sustainable/regenerative farming language

3. SCALE INDICATORS (Volume potential)
   - Square footage of greenhouse space (e.g., "180,000 sq ft facility")
   - Number of greenhouses or hoop houses (e.g., "12 greenhouses")
   - Acreage under production (e.g., "100 acres")
   - Annual plant/crop production numbers (e.g., "500,000 plants/year")
   - Employee count if mentioned
   - Multiple locations

4. SOIL/AMENDMENT SIGNALS (Confirmed soil buyer)
   - Any mention of: potting soil, growing media, amendments, compost, 
     worm castings, vermicompost, peat, coco coir, perlite
   - Brand names: Pro-Mix, Sungro, Berger, Fox Farm, etc.
   - "We mix our own soil" = VERY HIGH priority
   - "Soil health" or "building soil" language

5. DISQUALIFICATION TRIGGERS (Cap at Tier C)
   - "landscape installation", "lawn care", "mowing services"
   - "equipment dealer", "machinery sales", "parts"
   - "retail only", "gift shop", "home decor"
   - "florist" with no growing operation
   - Christmas tree farm (field grown, no containers)
   - Sod/turf production

6. BUSINESS TYPE CLASSIFICATION
   Classify as one of:
   - nursery_wholesale: Wholesale nursery growing plants for resale
   - nursery_retail: Retail garden center (lower priority)
   - greenhouse_propagation: Plug/liner/cutting production
   - organic_vegetable_farm: Organic produce operation
   - hemp_cannabis: Hemp or cannabis cultivation
   - microgreens_specialty: Microgreens, sprouts, specialty greens
   - soil_mixer: Company that blends/sells growing media
   - farm_supply: Wholesaler of farm inputs
   - landscaper: Landscape installation company (disqualify)
   - other: Doesn't fit above categories

RESPOND WITH JSON ONLY. No markdown, no explanation.
"""
```

#### Step 2.3: Update the response parsing

**File:** `enrichment/gemini_client.py`

**Location:** After API call, in response parsing section

```python
def parse_enrichment_response(response_text: str, lead_id: int) -> dict:
    """Parse Gemini response and map to database columns."""
    try:
        # Strip markdown code blocks if present
        clean_text = response_text.strip()
        if clean_text.startswith("```"):
            clean_text = clean_text.split("```")[1]
            if clean_text.startswith("json"):
                clean_text = clean_text[4:]
        clean_text = clean_text.strip()
        
        data = json.loads(clean_text)
        
        return {
            # Existing fields
            "business_type": data.get("business_type"),
            "organic_focus": data.get("organic_focus") or data.get("is_organic_certified"),
            "crops_grown": json.dumps(data.get("crops_grown", [])),
            "size_signals": json.dumps(data.get("size_signals", []) + data.get("scale_indicators", [])),
            "is_wholesale": data.get("is_wholesale"),
            "container_production": data.get("container_production"),
            "owner_name": data.get("owner_name"),
            "owner_email": data.get("owner_email"),
            
            # NEW ICP fields
            "uses_growing_media": data.get("uses_growing_media"),
            "production_method": data.get("production_method"),
            "is_organic_certified": data.get("is_organic_certified"),
            "scale_indicators": json.dumps(data.get("scale_indicators", [])),
            "purchases_soil": data.get("purchases_soil"),
            "soil_brands_mentioned": json.dumps(data.get("soil_brands_mentioned", [])),
            "disqualification_signals": json.dumps(data.get("disqualification_signals", [])),
        }
    except json.JSONDecodeError as e:
        logging.error(f"Failed to parse Gemini response for lead {lead_id}: {e}")
        return None
```

#### Step 2.4: Update database save logic

**File:** `enrichment/gemini_client.py` or `app.py`

**Location:** Where enrichment results are saved to database

Ensure all new fields are included in the UPDATE statement.

### Testing Strategy

```python
# Test with a known good website
test_website_text = """
Green Valley Nursery is a wholesale greenhouse operation with 12 heated greenhouses
totaling 180,000 square feet. We specialize in container-grown perennials and 
annuals, propagating over 500,000 plants annually. Certified Organic since 2015.
We mix our own potting soil using Pro-Mix as a base with added compost.
"""

# Expected output should have:
# - uses_growing_media: True
# - production_method: "greenhouse"
# - is_organic_certified: True
# - scale_indicators: ["12 greenhouses", "180,000 square feet", "500,000 plants annually"]
# - purchases_soil: True
# - soil_brands_mentioned: ["Pro-Mix"]
# - disqualification_signals: []
```

### Acceptance Criteria
- [ ] Gemini returns all new ICP fields in response
- [ ] JSON parsing handles new fields
- [ ] Database UPDATE includes all new columns
- [ ] Test with 5 known websites produces expected results
- [ ] Rate limiting still works (1 req/sec)

---

## Phase 3: Scoring Model Overhaul

### Objective
Rewrite `scorer.py` with ICP qualification gate and new scoring signals based on sample requester analysis.

### Pre-Conditions
- Phase 2 complete (new fields populated in database)
- Sample requester data analyzed (23 companies)
- Current scoring rules understood

### Sample Requester Insights (Ground Truth)

From 23 companies that requested samples during cold calling:

| Signal | Count | Weight Implication |
|--------|-------|-------------------|
| "Organics" in name | 6 (26%) | +30 points |
| "Farm/Farms" in name | 10 (43%) | +15 points |
| "Greenhouse/Growers" | 4 (17%) | +20 points |
| Hemp-specific | 2 (9%) | +25 points |
| Wisconsin location | 23 (100%) | +25 points (geo) |

### Implementation Steps

#### Step 3.1: Define ICP qualification logic

**File:** `enrichment/scorer.py`

**Location:** Top of file, new constants

```python
# ICP Qualification Constants
# A lead MUST have at least one ICP signal to score above Tier C

ICP_PRIMARY_SIGNALS = {
    # These indicate the business USES growing media in production
    "uses_growing_media": True,
    "production_method": ["container", "greenhouse", "mixed"],
    "container_production": True,
}

ICP_SECONDARY_SIGNALS = {
    # These indicate the business RESELLS growing media
    "business_type": ["soil_mixer", "farm_supply"],
}

DISQUALIFICATION_KEYWORDS = [
    "landscaping", "landscape installation", "lawn care", "mowing",
    "equipment dealer", "machinery", "parts dealer",
    "retail only", "gift shop", "home decor",
    "christmas tree", "sod", "turf",
]

# Business types that are automatically disqualified
DISQUALIFIED_BUSINESS_TYPES = [
    "landscaper", "equipment_dealer", "retail_only"
]
```

#### Step 3.2: Define new scoring rules

**File:** `enrichment/scorer.py`

```python
SCORING_RULES = {
    # === HIGH-VALUE SIGNALS (from sample requesters) ===
    
    # Organic signals (26% of sample requesters had "Organic" in name)
    "organic_in_name": {
        "points": 30,
        "condition": lambda lead: "organic" in (lead.get("business_name") or "").lower(),
        "description": "Organic in business name"
    },
    "is_organic_certified": {
        "points": 25,
        "condition": lambda lead: lead.get("is_organic_certified") == True,
        "description": "Certified organic operation"
    },
    
    # Production method signals
    "greenhouse_production": {
        "points": 25,
        "condition": lambda lead: lead.get("production_method") in ["greenhouse", "container"],
        "description": "Greenhouse/container production"
    },
    "uses_growing_media": {
        "points": 20,
        "condition": lambda lead: lead.get("uses_growing_media") == True,
        "description": "Uses growing media in production"
    },
    
    # Business type signals (43% were farms)
    "farm_in_name": {
        "points": 15,
        "condition": lambda lead: "farm" in (lead.get("business_name") or "").lower(),
        "description": "Farm in business name"
    },
    "growers_in_name": {
        "points": 15,
        "condition": lambda lead: "grower" in (lead.get("business_name") or "").lower(),
        "description": "Grower(s) in business name"
    },
    
    # Hemp/Cannabis (9% of sample requesters)
    "hemp_cannabis": {
        "points": 25,
        "condition": lambda lead: lead.get("business_type") == "hemp_cannabis" or 
                                  "hemp" in (lead.get("business_name") or "").lower() or
                                  "cannabis" in (lead.get("business_type") or "").lower(),
        "description": "Hemp/cannabis operation"
    },
    
    # Wholesale signals
    "is_wholesale": {
        "points": 20,
        "condition": lambda lead: lead.get("is_wholesale") == True,
        "description": "Wholesale operation"
    },
    
    # Soil purchasing signals (confirms they buy inputs)
    "purchases_soil": {
        "points": 20,
        "condition": lambda lead: lead.get("purchases_soil") == True,
        "description": "Purchases potting soil/amendments"
    },
    "soil_brands_mentioned": {
        "points": 15,
        "condition": lambda lead: len(json.loads(lead.get("soil_brands_mentioned") or "[]")) > 0,
        "description": "Mentions soil brands (Pro-Mix, Sungro, etc.)"
    },
    
    # Scale signals
    "large_scale": {
        "points": 15,
        "condition": lambda lead: len(json.loads(lead.get("scale_indicators") or "[]")) >= 2,
        "description": "Multiple scale indicators"
    },
    "high_review_count": {
        "points": 10,
        "condition": lambda lead: (lead.get("review_count") or 0) >= 50,
        "description": "50+ Google reviews (business volume indicator)"
    },
    
    # === NEGATIVE SIGNALS (Disqualifiers) ===
    
    "landscaping_services": {
        "points": -50,
        "condition": lambda lead: any(kw in (lead.get("business_type") or "").lower() 
                                      for kw in ["landscap", "lawn care"]),
        "description": "Landscaping/lawn care services"
    },
    "christmas_tree": {
        "points": -40,
        "condition": lambda lead: "christmas" in (lead.get("business_name") or "").lower() or
                                  "christmas" in (lead.get("business_type") or "").lower(),
        "description": "Christmas tree farm"
    },
    "sod_turf": {
        "points": -40,
        "condition": lambda lead: "sod" in (lead.get("business_type") or "").lower() or
                                  "turf" in (lead.get("business_type") or "").lower(),
        "description": "Sod/turf production"
    },
    "gift_shop": {
        "points": -30,
        "condition": lambda lead: "gift" in (lead.get("business_type") or "").lower(),
        "description": "Gift shop focus"
    },
    "retail_only": {
        "points": -20,
        "condition": lambda lead: lead.get("business_type") == "nursery_retail" and 
                                  not lead.get("is_wholesale"),
        "description": "Retail only, no wholesale"
    },
}
```

#### Step 3.3: Implement ICP qualification gate

**File:** `enrichment/scorer.py`

```python
def check_icp_qualification(lead: dict) -> tuple[bool, str]:
    """
    Check if lead passes ICP qualification gate.
    Returns (is_qualified, icp_type)
    
    ICP Types:
    - "primary": Uses growing media in production
    - "secondary": Resells growing media
    - "tertiary": Field farm (lower priority)
    - "disqualified": Has disqualification signals
    """
    
    # Check for disqualification first
    disqual_signals = json.loads(lead.get("disqualification_signals") or "[]")
    business_type = lead.get("business_type") or ""
    
    for keyword in DISQUALIFICATION_KEYWORDS:
        if keyword in business_type.lower():
            return False, "disqualified"
        for signal in disqual_signals:
            if keyword in signal.lower():
                return False, "disqualified"
    
    if business_type in DISQUALIFIED_BUSINESS_TYPES:
        return False, "disqualified"
    
    # Check primary ICP signals
    if lead.get("uses_growing_media") == True:
        return True, "primary"
    
    if lead.get("production_method") in ["container", "greenhouse", "mixed"]:
        return True, "primary"
    
    if lead.get("container_production") == True:
        return True, "primary"
    
    # Check secondary ICP signals (resellers)
    if business_type in ["soil_mixer", "farm_supply"]:
        return True, "secondary"
    
    # Check tertiary signals (field farms that might still buy)
    if lead.get("is_organic_certified") == True:
        return True, "tertiary"
    
    if "organic" in (lead.get("business_name") or "").lower():
        return True, "tertiary"
    
    if lead.get("production_method") == "field":
        return True, "tertiary"
    
    # No ICP signals detected
    return False, "disqualified"
```

#### Step 3.4: Implement main scoring function

**File:** `enrichment/scorer.py`

```python
def calculate_score(lead: dict) -> dict:
    """
    Calculate lead score with ICP qualification gate.
    
    Returns dict with:
    - score: int
    - tier: str ('A', 'B', 'C', 'U')
    - icp_qualified: bool
    - icp_type: str
    - geo_score: int
    - score_breakdown: dict
    - negative_indicators: list
    """
    
    score = 0
    breakdown = {}
    negative_indicators = []
    
    # Step 1: Check ICP qualification
    icp_qualified, icp_type = check_icp_qualification(lead)
    
    # Step 2: Apply scoring rules
    for rule_name, rule in SCORING_RULES.items():
        try:
            if rule["condition"](lead):
                points = rule["points"]
                score += points
                
                if points > 0:
                    breakdown[rule_name] = {
                        "points": points,
                        "description": rule["description"]
                    }
                else:
                    negative_indicators.append({
                        "signal": rule_name,
                        "points": points,
                        "description": rule["description"]
                    })
        except Exception as e:
            logging.warning(f"Error evaluating rule {rule_name}: {e}")
    
    # Step 3: Add geo score (calculated separately in Phase 4)
    geo_score = lead.get("geo_score") or 0
    score += geo_score
    if geo_score > 0:
        breakdown["geographic_proximity"] = {
            "points": geo_score,
            "description": f"State proximity bonus"
        }
    
    # Step 4: Apply ICP cap for disqualified leads
    if not icp_qualified:
        score = min(score, 29)  # Cap at Tier U
    
    # Step 5: Determine tier
    if score >= 80:
        tier = "A"
    elif score >= 50:
        tier = "B"
    elif score >= 30:
        tier = "C"
    else:
        tier = "U"  # Unqualified
    
    # If disqualified, force to C or U regardless of score
    if icp_type == "disqualified":
        tier = "U" if score < 30 else "C"
    
    return {
        "score": score,
        "tier": tier,
        "icp_qualified": icp_qualified,
        "icp_type": icp_type,
        "geo_score": geo_score,
        "score_breakdown": json.dumps(breakdown),
        "negative_indicators": json.dumps(negative_indicators)
    }
```

#### Step 3.5: Update database save for scoring

**File:** `enrichment/scorer.py` or `app.py`

```python
def save_score_to_db(lead_id: int, score_result: dict, cursor):
    """Save calculated score to database."""
    cursor.execute("""
        UPDATE leads SET
            score = ?,
            tier = ?,
            icp_qualified = ?,
            icp_type = ?,
            geo_score = ?,
            score_breakdown = ?,
            negative_indicators = ?
        WHERE id = ?
    """, (
        score_result["score"],
        score_result["tier"],
        score_result["icp_qualified"],
        score_result["icp_type"],
        score_result["geo_score"],
        score_result["score_breakdown"],
        score_result["negative_indicators"],
        lead_id
    ))
```

### Testing Strategy

```python
# Test cases based on sample requesters

# Test 1: Driftless Organics (should be Tier A)
test_lead_driftless = {
    "business_name": "Driftless Organics",
    "is_organic_certified": True,
    "uses_growing_media": True,  # They do transplant production
    "production_method": "field",
    "state": "WI",
    "is_wholesale": True,
}
# Expected: Tier A, score ~85+

# Test 2: Random Landscaping Co (should be Tier U)
test_lead_landscaper = {
    "business_name": "Green Thumb Landscaping",
    "business_type": "landscaper",
    "disqualification_signals": '["landscape installation", "lawn care"]',
    "uses_growing_media": False,
}
# Expected: Tier U, icp_type = "disqualified"

# Test 3: Karthauser & Sons (should be Tier A)
test_lead_karthauser = {
    "business_name": "Karthauser & Sons",
    "production_method": "greenhouse",
    "uses_growing_media": True,
    "is_wholesale": True,
    "scale_indicators": '["180,000 square feet"]',
    "state": "WI",
}
# Expected: Tier A, score ~90+
```

### Acceptance Criteria
- [ ] ICP qualification gate implemented
- [ ] All sample requesters would score Tier A or B
- [ ] Landscapers/lawn care score Tier U
- [ ] Christmas tree farms score Tier C or U
- [ ] Score breakdown JSON is human-readable
- [ ] Scoring runs in <100ms per lead

---

## Phase 4: Geographic Intelligence

### Objective
Add state-based geographic scoring to prioritize leads within efficient shipping range of Wisconsin.

### Pre-Conditions
- Phase 3 complete (scoring model in place)
- Lead state data available (from address or Gemini extraction)

### Geographic Tiers

Based on shipping logistics from Wisconsin:

| Tier | States | Modifier | Rationale |
|------|--------|----------|-----------|
| Local | WI | +25 | Same-day/next-day delivery, lowest freight cost |
| Regional | IL, MN, IA, MI | +20 | Day-trip freight zone |
| Near | IN, OH, MO, NE, KY | +10 | 2-day freight, manageable cost |
| Mid | ND, SD, KS, TN, WV, PA, NY | +0 | No bonus, no penalty |
| Far | TX, CO, CA, FL, etc. | -5 | Higher shipping cost, longer lead time |

### Implementation Steps

#### Step 4.1: Define geographic constants

**File:** `enrichment/scorer.py`

**Location:** Top of file, after ICP constants

```python
# Geographic Scoring Constants
# Based on Wisconsin shipping logistics

GEO_TIERS = {
    # Local - same state
    "WI": 25,
    
    # Regional - day-trip freight
    "IL": 20,
    "MN": 20,
    "IA": 20,
    "MI": 20,
    
    # Near - 2-day freight
    "IN": 10,
    "OH": 10,
    "MO": 10,
    "NE": 10,
    "KY": 10,
    
    # Mid - no modifier
    "ND": 0, "SD": 0, "KS": 0, "TN": 0, 
    "WV": 0, "PA": 0, "NY": 0, "AR": 0,
    
    # Far - slight penalty (still viable, just harder)
    "TX": -5, "CO": -5, "CA": -5, "FL": -5,
    "AZ": -5, "NM": -5, "NC": -5, "SC": -5,
    "GA": -5, "AL": -5, "MS": -5, "LA": -5,
}

# Default for unlisted states
GEO_DEFAULT_SCORE = -5
```

#### Step 4.2: Implement geo scoring function

**File:** `enrichment/scorer.py`

```python
def calculate_geo_score(lead: dict) -> int:
    """
    Calculate geographic proximity score based on state.
    
    Tries multiple sources for state:
    1. lead["state"] column
    2. Parse from lead["address"]
    3. Parse from lead["city"] (if includes state)
    """
    
    state = lead.get("state")
    
    # Try to extract from address if state is missing
    if not state and lead.get("address"):
        state = extract_state_from_address(lead["address"])
    
    if not state:
        return 0  # Can't determine, no modifier
    
    # Normalize state to 2-letter code
    state = normalize_state(state)
    
    return GEO_TIERS.get(state, GEO_DEFAULT_SCORE)


def normalize_state(state: str) -> str:
    """Convert state name or abbreviation to 2-letter code."""
    if not state:
        return None
        
    state = state.strip().upper()
    
    # Already 2-letter code
    if len(state) == 2:
        return state
    
    # Full state names
    STATE_NAMES = {
        "WISCONSIN": "WI", "ILLINOIS": "IL", "MINNESOTA": "MN",
        "IOWA": "IA", "MICHIGAN": "MI", "INDIANA": "IN",
        "OHIO": "OH", "MISSOURI": "MO", "NEBRASKA": "NE",
        "KENTUCKY": "KY", "TEXAS": "TX", "COLORADO": "CO",
        "CALIFORNIA": "CA", "FLORIDA": "FL", "ARIZONA": "AZ",
        "NEW MEXICO": "NM", "NORTH CAROLINA": "NC", "SOUTH CAROLINA": "SC",
        "GEORGIA": "GA", "ALABAMA": "AL", "MISSISSIPPI": "MS",
        "LOUISIANA": "LA", "NORTH DAKOTA": "ND", "SOUTH DAKOTA": "SD",
        "KANSAS": "KS", "TENNESSEE": "TN", "WEST VIRGINIA": "WV",
        "PENNSYLVANIA": "PA", "NEW YORK": "NY", "ARKANSAS": "AR",
    }
    
    return STATE_NAMES.get(state, state[:2] if len(state) > 2 else None)


def extract_state_from_address(address: str) -> str:
    """Extract state from address string."""
    if not address:
        return None
    
    # Common patterns: "City, ST 12345" or "City, State"
    import re
    
    # Try to find 2-letter state code before zip
    match = re.search(r',\s*([A-Z]{2})\s*\d{5}', address.upper())
    if match:
        return match.group(1)
    
    # Try to find state code after comma
    match = re.search(r',\s*([A-Z]{2})\s*$', address.upper())
    if match:
        return match.group(1)
    
    return None
```

#### Step 4.3: Integrate geo scoring into main scorer

**File:** `enrichment/scorer.py`

**Location:** In `calculate_score()` function

```python
# Add this before Step 3 in calculate_score():

# Calculate geo score
geo_score = calculate_geo_score(lead)
```

#### Step 4.4: Add geo score to database during scoring

The `save_score_to_db` function from Phase 3 already includes `geo_score`.

### Testing Strategy

```python
# Test geo scoring
test_leads = [
    {"business_name": "WI Nursery", "state": "WI"},      # Expected: +25
    {"business_name": "IL Growers", "state": "IL"},      # Expected: +20
    {"business_name": "Texas Farm", "state": "TX"},      # Expected: -5
    {"business_name": "Unknown", "state": None},         # Expected: 0
    {"business_name": "Address Only", "address": "123 Main St, Madison, WI 53703"},  # Expected: +25
]

for lead in test_leads:
    score = calculate_geo_score(lead)
    print(f"{lead['business_name']}: {score}")
```

### Acceptance Criteria
- [ ] All 50 US states mapped
- [ ] Wisconsin leads get +25
- [ ] Regional states (IL, MN, IA, MI) get +20
- [ ] State extraction works from address field
- [ ] Geo score appears in score_breakdown JSON

---

## Phase 5: Re-Enrichment Pipeline

### Objective
Re-process existing leads with updated Gemini prompts and re-score with new model.

### Pre-Conditions
- Phases 1-4 complete
- Database has existing leads
- Gemini API quota available (~3,200 leads × $0.005 = ~$16)

### Implementation Steps

#### Step 5.1: Add re-enrichment status tracking

**File:** `database/models.py`

Add column to track re-enrichment:

```python
("re_enrichment_status", "TEXT DEFAULT 'pending'"),
("re_enriched_at", "TIMESTAMP DEFAULT NULL"),
```

#### Step 5.2: Create re-enrichment endpoint

**File:** `app.py`

```python
@app.route('/re-enrich/start', methods=['POST'])
def start_re_enrichment():
    """
    Re-enrich existing leads with updated Gemini prompts.
    Only processes leads that have website_text but haven't been re-enriched.
    """
    if re_enrichment_state['running']:
        return jsonify({"error": "Re-enrichment already running"}), 400
    
    batch_size = request.json.get('batch_size', 50)
    
    # Start background thread
    thread = threading.Thread(
        target=run_re_enrichment,
        args=(batch_size,),
        daemon=True
    )
    thread.start()
    
    return jsonify({"status": "started", "batch_size": batch_size})


def run_re_enrichment(batch_size: int):
    """Background task for re-enrichment."""
    global re_enrichment_state
    re_enrichment_state = {
        'running': True,
        'stop_requested': False,
        'total': 0,
        'completed': 0,
        'failed': 0,
        'current_lead': None,
        'errors': []
    }
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get leads that need re-enrichment
    cursor.execute("""
        SELECT id, business_name, website_text, state, address
        FROM leads
        WHERE website_text IS NOT NULL
        AND website_text != ''
        AND (re_enrichment_status = 'pending' OR re_enrichment_status IS NULL)
        LIMIT ?
    """, (batch_size,))
    
    leads = cursor.fetchall()
    re_enrichment_state['total'] = len(leads)
    
    for lead in leads:
        if re_enrichment_state['stop_requested']:
            break
        
        lead_id = lead['id']
        re_enrichment_state['current_lead'] = lead['business_name']
        
        try:
            # Re-enrich with Gemini
            enrichment_data = enrich_lead_with_gemini(
                lead['website_text'],
                lead_id
            )
            
            if enrichment_data:
                # Save new enrichment data
                save_enrichment_to_db(lead_id, enrichment_data, cursor)
                
                # Calculate geo score
                lead_dict = dict(lead)
                lead_dict.update(enrichment_data)
                geo_score = calculate_geo_score(lead_dict)
                
                # Re-score with new model
                lead_dict['geo_score'] = geo_score
                score_result = calculate_score(lead_dict)
                save_score_to_db(lead_id, score_result, cursor)
                
                # Mark as re-enriched
                cursor.execute("""
                    UPDATE leads SET
                        re_enrichment_status = 'completed',
                        re_enriched_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (lead_id,))
                
                conn.commit()
                re_enrichment_state['completed'] += 1
            else:
                raise Exception("Gemini returned no data")
                
        except Exception as e:
            re_enrichment_state['failed'] += 1
            re_enrichment_state['errors'].append({
                'lead_id': lead_id,
                'error': str(e)
            })
            cursor.execute("""
                UPDATE leads SET re_enrichment_status = 'failed'
                WHERE id = ?
            """, (lead_id,))
            conn.commit()
        
        # Rate limiting
        time.sleep(1)
    
    conn.close()
    re_enrichment_state['running'] = False
```

#### Step 5.3: Create re-enrichment status endpoint

**File:** `app.py`

```python
@app.route('/re-enrich/status')
def re_enrichment_status():
    """SSE endpoint for re-enrichment progress."""
    def generate():
        while re_enrichment_state['running']:
            yield f"data: {json.dumps(re_enrichment_state)}\n\n"
            time.sleep(1)
        yield f"data: {json.dumps(re_enrichment_state)}\n\n"
    
    return Response(generate(), mimetype='text/event-stream')
```

#### Step 5.4: Create score-only endpoint

For leads that already have enrichment data but need rescoring:

```python
@app.route('/rescore/all', methods=['POST'])
def rescore_all_leads():
    """Re-score all enriched leads with new scoring model."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT * FROM leads
        WHERE gemini_status = 'enriched'
    """)
    
    leads = cursor.fetchall()
    updated = 0
    
    for lead in leads:
        lead_dict = dict(lead)
        
        # Calculate geo score
        lead_dict['geo_score'] = calculate_geo_score(lead_dict)
        
        # Calculate full score
        score_result = calculate_score(lead_dict)
        save_score_to_db(lead['id'], score_result, cursor)
        updated += 1
    
    conn.commit()
    conn.close()
    
    return jsonify({"status": "completed", "leads_updated": updated})
```

### Execution Plan

1. **Backup database first:**
   ```bash
   copy data\leads.db data\leads.db.pre-re-enrich
   ```

2. **Run re-scoring only (fast, no API calls):**
   ```bash
   curl -X POST http://127.0.0.1:5000/rescore/all
   ```

3. **Run full re-enrichment in batches:**
   ```bash
   # Batch 1: 100 leads
   curl -X POST http://127.0.0.1:5000/re-enrich/start -H "Content-Type: application/json" -d '{"batch_size": 100}'
   # Monitor progress
   # Repeat until all leads processed
   ```

### Acceptance Criteria
- [ ] Re-enrichment processes leads without errors
- [ ] Rate limiting prevents API quota issues
- [ ] Progress tracking works via SSE
- [ ] Scores update correctly with new model
- [ ] Re-enrichment is resumable (tracks status per lead)

---

## Phase 6: Frontend - Lead Card Redesign

### Objective
Create visually informative lead cards that show score breakdown, ICP status, and key signals at a glance.

### Pre-Conditions
- Phases 1-5 complete (leads have new data)
- Flask templates exist in `templates/`
- Current UI is functional but basic

### Design Specification

```
┌─────────────────────────────────────────────────────────────────┐
│ [TIER A]  Green Valley Nursery                    📍 Madison, WI │
│ ────────────────────────────────────────────────────────────────│
│                                                                  │
│ SCORE: 92                                                        │
│ ████████████████████████░░░░░  92/100                           │
│                                                                  │
│ ICP: Primary (Greenhouse Production)     GEO: +25 (Wisconsin)    │
│                                                                  │
│ ┌─────────────────────────────┐  ┌─────────────────────────────┐│
│ │ POSITIVE SIGNALS            │  │ DETAILS                     ││
│ │ ✓ Organic certified   +25   │  │ 📞 (608) 555-0123           ││
│ │ ✓ Greenhouse          +25   │  │ 🌐 greenvalley.com          ││
│ │ ✓ Uses growing media  +20   │  │ ⭐ 4.8 (127 reviews)        ││
│ │ ✓ Wholesale           +20   │  │                             ││
│ │ ✓ Purchases soil      +20   │  │ SCALE                       ││
│ │                             │  │ • 12 greenhouses            ││
│ └─────────────────────────────┘  │ • 180,000 sq ft             ││
│                                  └─────────────────────────────┘│
│                                                                  │
│ [Override Tier ▾]  [View Website]  [Mark Reviewed]  [Export]     │
└─────────────────────────────────────────────────────────────────┘
```

### Implementation Steps

#### Step 6.1: Create lead card component template

**File:** `templates/components/lead_card.html`

```html
{% macro lead_card(lead) %}
<div class="lead-card tier-{{ lead.tier|lower }}" data-lead-id="{{ lead.id }}">
    <div class="lead-header">
        <span class="tier-badge tier-{{ lead.tier|lower }}">TIER {{ lead.tier }}</span>
        <h3 class="lead-name">{{ lead.business_name }}</h3>
        <span class="lead-location">
            📍 {{ lead.city }}{% if lead.state %}, {{ lead.state }}{% endif %}
        </span>
    </div>
    
    <div class="lead-score-section">
        <div class="score-display">
            <span class="score-label">SCORE:</span>
            <span class="score-value">{{ lead.score or 0 }}</span>
        </div>
        <div class="score-bar">
            <div class="score-fill" style="width: {{ lead.score or 0 }}%"></div>
        </div>
    </div>
    
    <div class="lead-icp-geo">
        <span class="icp-badge icp-{{ lead.icp_type or 'unknown' }}">
            ICP: {{ lead.icp_type|title if lead.icp_type else 'Unknown' }}
            {% if lead.production_method %}({{ lead.production_method|title }}){% endif %}
        </span>
        <span class="geo-badge">
            GEO: {{ '+' if (lead.geo_score or 0) >= 0 else '' }}{{ lead.geo_score or 0 }}
            {% if lead.state %}({{ lead.state }}){% endif %}
        </span>
    </div>
    
    <div class="lead-body">
        <div class="signals-column">
            <h4>POSITIVE SIGNALS</h4>
            <ul class="signal-list positive">
                {% set breakdown = lead.score_breakdown|default('{}')|from_json %}
                {% for signal, data in breakdown.items() %}
                <li>
                    <span class="signal-check">✓</span>
                    <span class="signal-name">{{ data.description }}</span>
                    <span class="signal-points">+{{ data.points }}</span>
                </li>
                {% endfor %}
            </ul>
            
            {% set negatives = lead.negative_indicators|default('[]')|from_json %}
            {% if negatives %}
            <h4>NEGATIVE SIGNALS</h4>
            <ul class="signal-list negative">
                {% for neg in negatives %}
                <li>
                    <span class="signal-check">✗</span>
                    <span class="signal-name">{{ neg.description }}</span>
                    <span class="signal-points">{{ neg.points }}</span>
                </li>
                {% endfor %}
            </ul>
            {% endif %}
        </div>
        
        <div class="details-column">
            <h4>CONTACT</h4>
            <div class="contact-info">
                {% if lead.phone %}
                <div class="contact-item">📞 {{ lead.phone }}</div>
                {% endif %}
                {% if lead.website %}
                <div class="contact-item">
                    🌐 <a href="{{ lead.website }}" target="_blank">{{ lead.website|truncate(30) }}</a>
                </div>
                {% endif %}
                {% if lead.owner_email %}
                <div class="contact-item">✉️ {{ lead.owner_email }}</div>
                {% endif %}
                {% if lead.rating %}
                <div class="contact-item">⭐ {{ lead.rating }} ({{ lead.review_count or 0 }} reviews)</div>
                {% endif %}
            </div>
            
            {% set scale = lead.scale_indicators|default('[]')|from_json %}
            {% if scale %}
            <h4>SCALE INDICATORS</h4>
            <ul class="scale-list">
                {% for indicator in scale %}
                <li>• {{ indicator }}</li>
                {% endfor %}
            </ul>
            {% endif %}
        </div>
    </div>
    
    <div class="lead-actions">
        <select class="tier-override" data-lead-id="{{ lead.id }}">
            <option value="">Override Tier...</option>
            <option value="A" {% if lead.tier_override == 'A' %}selected{% endif %}>Tier A</option>
            <option value="B" {% if lead.tier_override == 'B' %}selected{% endif %}>Tier B</option>
            <option value="C" {% if lead.tier_override == 'C' %}selected{% endif %}>Tier C</option>
            <option value="U" {% if lead.tier_override == 'U' %}selected{% endif %}>Tier U</option>
        </select>
        {% if lead.website %}
        <a href="{{ lead.website }}" target="_blank" class="btn btn-secondary">View Website</a>
        {% endif %}
        <button class="btn btn-primary mark-reviewed" data-lead-id="{{ lead.id }}">
            {% if lead.reviewed %}Reviewed ✓{% else %}Mark Reviewed{% endif %}
        </button>
        <button class="btn btn-outline add-to-export" data-lead-id="{{ lead.id }}">
            + Export
        </button>
    </div>
</div>
{% endmacro %}
```

#### Step 6.2: Create CSS for lead cards

**File:** `static/css/lead-cards.css`

```css
/* Lead Card Styles */
.lead-card {
    background: #fff;
    border-radius: 8px;
    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    margin-bottom: 1rem;
    padding: 1.5rem;
    border-left: 4px solid #ccc;
    transition: box-shadow 0.2s;
}

.lead-card:hover {
    box-shadow: 0 4px 12px rgba(0,0,0,0.15);
}

/* Tier colors */
.lead-card.tier-a { border-left-color: #22c55e; }
.lead-card.tier-b { border-left-color: #3b82f6; }
.lead-card.tier-c { border-left-color: #f59e0b; }
.lead-card.tier-u { border-left-color: #ef4444; }

.tier-badge {
    display: inline-block;
    padding: 0.25rem 0.75rem;
    border-radius: 4px;
    font-weight: 600;
    font-size: 0.75rem;
    text-transform: uppercase;
}

.tier-badge.tier-a { background: #dcfce7; color: #166534; }
.tier-badge.tier-b { background: #dbeafe; color: #1e40af; }
.tier-badge.tier-c { background: #fef3c7; color: #92400e; }
.tier-badge.tier-u { background: #fee2e2; color: #991b1b; }

/* Header */
.lead-header {
    display: flex;
    align-items: center;
    gap: 1rem;
    margin-bottom: 1rem;
}

.lead-name {
    flex: 1;
    margin: 0;
    font-size: 1.25rem;
}

.lead-location {
    color: #666;
    font-size: 0.875rem;
}

/* Score display */
.lead-score-section {
    margin-bottom: 1rem;
}

.score-display {
    display: flex;
    align-items: baseline;
    gap: 0.5rem;
    margin-bottom: 0.5rem;
}

.score-label {
    font-size: 0.75rem;
    font-weight: 600;
    color: #666;
    text-transform: uppercase;
}

.score-value {
    font-size: 1.5rem;
    font-weight: 700;
}

.score-bar {
    height: 8px;
    background: #e5e7eb;
    border-radius: 4px;
    overflow: hidden;
}

.score-fill {
    height: 100%;
    background: linear-gradient(90deg, #22c55e 0%, #3b82f6 50%, #f59e0b 100%);
    border-radius: 4px;
    transition: width 0.3s;
}

/* ICP and Geo badges */
.lead-icp-geo {
    display: flex;
    gap: 1rem;
    margin-bottom: 1rem;
}

.icp-badge, .geo-badge {
    font-size: 0.875rem;
    padding: 0.25rem 0.5rem;
    border-radius: 4px;
    background: #f3f4f6;
}

.icp-badge.icp-primary { background: #dcfce7; color: #166534; }
.icp-badge.icp-secondary { background: #dbeafe; color: #1e40af; }
.icp-badge.icp-tertiary { background: #fef3c7; color: #92400e; }
.icp-badge.icp-disqualified { background: #fee2e2; color: #991b1b; }

/* Body layout */
.lead-body {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 1.5rem;
    margin-bottom: 1rem;
}

@media (max-width: 768px) {
    .lead-body {
        grid-template-columns: 1fr;
    }
}

.lead-body h4 {
    font-size: 0.75rem;
    font-weight: 600;
    color: #666;
    text-transform: uppercase;
    margin: 0 0 0.5rem 0;
}

/* Signal lists */
.signal-list {
    list-style: none;
    padding: 0;
    margin: 0 0 1rem 0;
}

.signal-list li {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.25rem 0;
    font-size: 0.875rem;
}

.signal-check {
    width: 1rem;
    text-align: center;
}

.signal-list.positive .signal-check { color: #22c55e; }
.signal-list.negative .signal-check { color: #ef4444; }

.signal-name {
    flex: 1;
}

.signal-points {
    font-weight: 600;
    font-family: monospace;
}

.signal-list.positive .signal-points { color: #22c55e; }
.signal-list.negative .signal-points { color: #ef4444; }

/* Contact info */
.contact-info {
    margin-bottom: 1rem;
}

.contact-item {
    padding: 0.25rem 0;
    font-size: 0.875rem;
}

.contact-item a {
    color: #3b82f6;
    text-decoration: none;
}

.contact-item a:hover {
    text-decoration: underline;
}

/* Scale list */
.scale-list {
    list-style: none;
    padding: 0;
    margin: 0;
    font-size: 0.875rem;
    color: #666;
}

/* Actions */
.lead-actions {
    display: flex;
    gap: 0.5rem;
    padding-top: 1rem;
    border-top: 1px solid #e5e7eb;
}

.lead-actions .btn {
    padding: 0.5rem 1rem;
    border-radius: 4px;
    font-size: 0.875rem;
    cursor: pointer;
    border: 1px solid #e5e7eb;
    background: #fff;
    transition: all 0.2s;
}

.lead-actions .btn:hover {
    background: #f3f4f6;
}

.lead-actions .btn-primary {
    background: #3b82f6;
    color: #fff;
    border-color: #3b82f6;
}

.lead-actions .btn-primary:hover {
    background: #2563eb;
}

.tier-override {
    padding: 0.5rem;
    border-radius: 4px;
    border: 1px solid #e5e7eb;
    font-size: 0.875rem;
}
```

#### Step 6.3: Add Jinja2 filter for JSON parsing

**File:** `app.py`

```python
import json

@app.template_filter('from_json')
def from_json_filter(value):
    """Parse JSON string in templates."""
    if not value:
        return {}
    try:
        return json.loads(value)
    except:
        return {}
```

#### Step 6.4: Update leads list template

**File:** `templates/leads.html`

Update to use the new lead_card component.

### Acceptance Criteria
- [ ] Lead cards show score breakdown visually
- [ ] ICP type and geo score visible
- [ ] Positive/negative signals listed with points
- [ ] Tier badge color-coded
- [ ] Responsive on mobile
- [ ] Actions (override, review, export) functional

---

## Phase 7: Frontend - Review Workflow

### Objective
Add keyboard shortcuts and bulk actions for rapid lead review.

### Pre-Conditions
- Phase 6 complete (lead cards exist)
- JavaScript can be added to templates

### Implementation Steps

#### Step 7.1: Add keyboard navigation

**File:** `static/js/lead-review.js`

```javascript
// Lead Review Keyboard Shortcuts
class LeadReviewer {
    constructor() {
        this.leads = [];
        this.currentIndex = 0;
        this.selectedLeads = new Set();
        this.init();
    }
    
    init() {
        this.leads = document.querySelectorAll('.lead-card');
        if (this.leads.length === 0) return;
        
        this.bindKeyboardShortcuts();
        this.bindClickHandlers();
        this.highlightCurrent();
    }
    
    bindKeyboardShortcuts() {
        document.addEventListener('keydown', (e) => {
            // Don't trigger if typing in input
            if (e.target.tagName === 'INPUT' || e.target.tagName === 'SELECT') return;
            
            switch(e.key.toLowerCase()) {
                case 'j':
                    this.nextLead();
                    break;
                case 'k':
                    this.prevLead();
                    break;
                case 'a':
                    this.setTier('A');
                    break;
                case 'b':
                    this.setTier('B');
                    break;
                case 'c':
                    this.setTier('C');
                    break;
                case 'u':
                    this.setTier('U');
                    break;
                case 'r':
                    this.markReviewed();
                    break;
                case 'x':
                    this.toggleSelect();
                    break;
                case 'o':
                    this.openWebsite();
                    break;
                case '?':
                    this.showHelp();
                    break;
            }
        });
    }
    
    bindClickHandlers() {
        // Tier override dropdowns
        document.querySelectorAll('.tier-override').forEach(select => {
            select.addEventListener('change', (e) => {
                const leadId = e.target.dataset.leadId;
                const tier = e.target.value;
                if (tier) this.saveTierOverride(leadId, tier);
            });
        });
        
        // Mark reviewed buttons
        document.querySelectorAll('.mark-reviewed').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const leadId = e.target.dataset.leadId;
                this.saveReviewed(leadId);
            });
        });
        
        // Add to export buttons
        document.querySelectorAll('.add-to-export').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const leadId = e.target.dataset.leadId;
                this.toggleExportSelection(leadId);
            });
        });
    }
    
    highlightCurrent() {
        this.leads.forEach((lead, i) => {
            lead.classList.toggle('current', i === this.currentIndex);
        });
        this.leads[this.currentIndex]?.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
    
    nextLead() {
        if (this.currentIndex < this.leads.length - 1) {
            this.currentIndex++;
            this.highlightCurrent();
        }
    }
    
    prevLead() {
        if (this.currentIndex > 0) {
            this.currentIndex--;
            this.highlightCurrent();
        }
    }
    
    getCurrentLead() {
        return this.leads[this.currentIndex];
    }
    
    getCurrentLeadId() {
        return this.getCurrentLead()?.dataset.leadId;
    }
    
    setTier(tier) {
        const leadId = this.getCurrentLeadId();
        if (!leadId) return;
        
        this.saveTierOverride(leadId, tier);
        
        // Update UI
        const select = this.getCurrentLead().querySelector('.tier-override');
        if (select) select.value = tier;
        
        // Update badge
        const badge = this.getCurrentLead().querySelector('.tier-badge');
        if (badge) {
            badge.textContent = `TIER ${tier}`;
            badge.className = `tier-badge tier-${tier.toLowerCase()}`;
        }
        
        // Auto-advance to next lead
        setTimeout(() => this.nextLead(), 200);
    }
    
    async saveTierOverride(leadId, tier) {
        try {
            const response = await fetch(`/api/leads/${leadId}/tier-override`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ tier })
            });
            
            if (!response.ok) throw new Error('Failed to save');
            
            this.showToast(`Tier set to ${tier}`);
        } catch (e) {
            this.showToast('Error saving tier', 'error');
        }
    }
    
    markReviewed() {
        const leadId = this.getCurrentLeadId();
        if (!leadId) return;
        this.saveReviewed(leadId);
    }
    
    async saveReviewed(leadId) {
        try {
            const response = await fetch(`/api/leads/${leadId}/reviewed`, {
                method: 'POST'
            });
            
            if (!response.ok) throw new Error('Failed to save');
            
            // Update button
            const btn = document.querySelector(`.mark-reviewed[data-lead-id="${leadId}"]`);
            if (btn) btn.textContent = 'Reviewed ✓';
            
            this.showToast('Marked as reviewed');
        } catch (e) {
            this.showToast('Error saving', 'error');
        }
    }
    
    toggleSelect() {
        const leadId = this.getCurrentLeadId();
        if (!leadId) return;
        
        if (this.selectedLeads.has(leadId)) {
            this.selectedLeads.delete(leadId);
            this.getCurrentLead().classList.remove('selected');
        } else {
            this.selectedLeads.add(leadId);
            this.getCurrentLead().classList.add('selected');
        }
        
        this.updateSelectionCount();
    }
    
    updateSelectionCount() {
        const counter = document.getElementById('selection-count');
        if (counter) {
            counter.textContent = `${this.selectedLeads.size} selected`;
        }
    }
    
    openWebsite() {
        const lead = this.getCurrentLead();
        const link = lead?.querySelector('.contact-item a');
        if (link) window.open(link.href, '_blank');
    }
    
    showHelp() {
        alert(`Keyboard Shortcuts:
j/k - Next/Previous lead
a/b/c/u - Set tier A/B/C/U
r - Mark as reviewed
x - Toggle selection
o - Open website
? - Show this help`);
    }
    
    showToast(message, type = 'success') {
        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;
        toast.textContent = message;
        document.body.appendChild(toast);
        setTimeout(() => toast.remove(), 2000);
    }
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    new LeadReviewer();
});
```

#### Step 7.2: Add API endpoints for review actions

**File:** `app.py`

```python
@app.route('/api/leads/<int:lead_id>/tier-override', methods=['POST'])
def set_tier_override(lead_id):
    """Set manual tier override for a lead."""
    data = request.get_json()
    tier = data.get('tier')
    
    if tier not in ['A', 'B', 'C', 'U', '']:
        return jsonify({"error": "Invalid tier"}), 400
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE leads SET 
            tier_override = ?,
            reviewed = 1,
            reviewed_at = CURRENT_TIMESTAMP
        WHERE id = ?
    """, (tier if tier else None, lead_id))
    conn.commit()
    conn.close()
    
    return jsonify({"status": "ok", "tier": tier})


@app.route('/api/leads/<int:lead_id>/reviewed', methods=['POST'])
def mark_reviewed(lead_id):
    """Mark a lead as reviewed."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE leads SET 
            reviewed = 1,
            reviewed_at = CURRENT_TIMESTAMP
        WHERE id = ?
    """, (lead_id,))
    conn.commit()
    conn.close()
    
    return jsonify({"status": "ok"})


@app.route('/api/leads/bulk-tier', methods=['POST'])
def bulk_tier_override():
    """Set tier for multiple leads at once."""
    data = request.get_json()
    lead_ids = data.get('lead_ids', [])
    tier = data.get('tier')
    
    if not lead_ids or tier not in ['A', 'B', 'C', 'U']:
        return jsonify({"error": "Invalid request"}), 400
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    placeholders = ','.join('?' * len(lead_ids))
    cursor.execute(f"""
        UPDATE leads SET 
            tier_override = ?,
            reviewed = 1,
            reviewed_at = CURRENT_TIMESTAMP
        WHERE id IN ({placeholders})
    """, [tier] + lead_ids)
    
    conn.commit()
    conn.close()
    
    return jsonify({"status": "ok", "updated": len(lead_ids)})
```

#### Step 7.3: Add CSS for current/selected states

**File:** `static/css/lead-cards.css`

```css
/* Current lead highlight */
.lead-card.current {
    box-shadow: 0 0 0 2px #3b82f6;
}

/* Selected leads */
.lead-card.selected {
    background: #f0f9ff;
}

/* Toast notifications */
.toast {
    position: fixed;
    bottom: 2rem;
    right: 2rem;
    padding: 0.75rem 1.5rem;
    border-radius: 4px;
    background: #22c55e;
    color: white;
    font-weight: 500;
    z-index: 1000;
    animation: slideIn 0.2s ease;
}

.toast-error {
    background: #ef4444;
}

@keyframes slideIn {
    from { transform: translateX(100%); opacity: 0; }
    to { transform: translateX(0); opacity: 1; }
}

/* Keyboard shortcuts hint */
.keyboard-hint {
    position: fixed;
    bottom: 1rem;
    left: 1rem;
    padding: 0.5rem 1rem;
    background: #1f2937;
    color: #fff;
    border-radius: 4px;
    font-size: 0.75rem;
}

.keyboard-hint kbd {
    background: #374151;
    padding: 0.125rem 0.375rem;
    border-radius: 2px;
    margin: 0 0.125rem;
}
```

### Acceptance Criteria
- [ ] j/k navigate between leads
- [ ] a/b/c/u set tier instantly
- [ ] r marks as reviewed
- [ ] x toggles selection
- [ ] Bulk tier change works for selected leads
- [ ] Toast notifications confirm actions
- [ ] Current lead visually highlighted

---

## Phase 8: Frontend - Dashboard

### Objective
Create a dashboard showing pipeline stats, tier distribution, and geographic heatmap.

### Pre-Conditions
- Phases 6-7 complete
- Database has scored leads

### Implementation Steps

#### Step 8.1: Create dashboard route

**File:** `app.py`

```python
@app.route('/dashboard')
def dashboard():
    """Dashboard with pipeline stats."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Pipeline progress
    cursor.execute("""
        SELECT
            COUNT(*) as total,
            SUM(CASE WHEN enrichment_status = 'enriched' THEN 1 ELSE 0 END) as google_enriched,
            SUM(CASE WHEN scrape_status = 'scraped' THEN 1 ELSE 0 END) as scraped,
            SUM(CASE WHEN gemini_status = 'enriched' THEN 1 ELSE 0 END) as ai_enriched,
            SUM(CASE WHEN score IS NOT NULL THEN 1 ELSE 0 END) as scored,
            SUM(CASE WHEN reviewed = 1 THEN 1 ELSE 0 END) as reviewed
        FROM leads
    """)
    pipeline = dict(cursor.fetchone())
    
    # Tier distribution
    cursor.execute("""
        SELECT 
            COALESCE(tier_override, tier, 'U') as tier,
            COUNT(*) as count
        FROM leads
        WHERE score IS NOT NULL
        GROUP BY COALESCE(tier_override, tier, 'U')
    """)
    tier_dist = {row['tier']: row['count'] for row in cursor.fetchall()}
    
    # Geographic distribution
    cursor.execute("""
        SELECT 
            state,
            COUNT(*) as count,
            AVG(score) as avg_score
        FROM leads
        WHERE state IS NOT NULL
        GROUP BY state
        ORDER BY count DESC
    """)
    geo_dist = [dict(row) for row in cursor.fetchall()]
    
    # ICP type distribution
    cursor.execute("""
        SELECT 
            COALESCE(icp_type, 'unknown') as icp_type,
            COUNT(*) as count
        FROM leads
        GROUP BY icp_type
    """)
    icp_dist = {row['icp_type']: row['count'] for row in cursor.fetchall()}
    
    # Top signals (most common positive signals)
    cursor.execute("""
        SELECT score_breakdown
        FROM leads
        WHERE score_breakdown IS NOT NULL
    """)
    signal_counts = {}
    for row in cursor.fetchall():
        try:
            breakdown = json.loads(row['score_breakdown'])
            for signal in breakdown.keys():
                signal_counts[signal] = signal_counts.get(signal, 0) + 1
        except:
            pass
    top_signals = sorted(signal_counts.items(), key=lambda x: -x[1])[:10]
    
    conn.close()
    
    return render_template('dashboard.html',
        pipeline=pipeline,
        tier_dist=tier_dist,
        geo_dist=geo_dist,
        icp_dist=icp_dist,
        top_signals=top_signals
    )
```

#### Step 8.2: Create dashboard template

**File:** `templates/dashboard.html`

```html
{% extends "base.html" %}

{% block content %}
<div class="dashboard">
    <h1>Pipeline Dashboard</h1>
    
    <!-- Pipeline Progress -->
    <section class="dashboard-section">
        <h2>Pipeline Progress</h2>
        <div class="progress-cards">
            <div class="progress-card">
                <div class="progress-value">{{ pipeline.total }}</div>
                <div class="progress-label">Total Leads</div>
            </div>
            <div class="progress-card">
                <div class="progress-value">{{ pipeline.google_enriched }}</div>
                <div class="progress-label">Google Enriched</div>
                <div class="progress-bar">
                    <div class="fill" style="width: {{ (pipeline.google_enriched / pipeline.total * 100)|round }}%"></div>
                </div>
            </div>
            <div class="progress-card">
                <div class="progress-value">{{ pipeline.scraped }}</div>
                <div class="progress-label">Websites Scraped</div>
                <div class="progress-bar">
                    <div class="fill" style="width: {{ (pipeline.scraped / pipeline.total * 100)|round }}%"></div>
                </div>
            </div>
            <div class="progress-card">
                <div class="progress-value">{{ pipeline.ai_enriched }}</div>
                <div class="progress-label">AI Enriched</div>
                <div class="progress-bar">
                    <div class="fill" style="width: {{ (pipeline.ai_enriched / pipeline.total * 100)|round }}%"></div>
                </div>
            </div>
            <div class="progress-card">
                <div class="progress-value">{{ pipeline.scored }}</div>
                <div class="progress-label">Scored</div>
                <div class="progress-bar">
                    <div class="fill" style="width: {{ (pipeline.scored / pipeline.total * 100)|round }}%"></div>
                </div>
            </div>
            <div class="progress-card">
                <div class="progress-value">{{ pipeline.reviewed }}</div>
                <div class="progress-label">Reviewed</div>
                <div class="progress-bar">
                    <div class="fill" style="width: {{ (pipeline.reviewed / pipeline.total * 100)|round }}%"></div>
                </div>
            </div>
        </div>
    </section>
    
    <!-- Tier Distribution -->
    <section class="dashboard-section">
        <h2>Tier Distribution</h2>
        <div class="tier-chart">
            {% for tier in ['A', 'B', 'C', 'U'] %}
            <div class="tier-bar tier-{{ tier|lower }}">
                <div class="bar" style="height: {{ (tier_dist.get(tier, 0) / pipeline.scored * 100)|round if pipeline.scored else 0 }}%"></div>
                <div class="label">{{ tier }}</div>
                <div class="count">{{ tier_dist.get(tier, 0) }}</div>
            </div>
            {% endfor %}
        </div>
    </section>
    
    <!-- Geographic Distribution -->
    <section class="dashboard-section">
        <h2>Geographic Distribution</h2>
        <table class="data-table">
            <thead>
                <tr>
                    <th>State</th>
                    <th>Leads</th>
                    <th>Avg Score</th>
                </tr>
            </thead>
            <tbody>
                {% for row in geo_dist[:10] %}
                <tr>
                    <td>{{ row.state }}</td>
                    <td>{{ row.count }}</td>
                    <td>{{ row.avg_score|round(1) }}</td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
    </section>
    
    <!-- ICP Distribution -->
    <section class="dashboard-section">
        <h2>ICP Type Distribution</h2>
        <div class="icp-chart">
            {% for icp_type, count in icp_dist.items() %}
            <div class="icp-row">
                <span class="icp-label">{{ icp_type|title }}</span>
                <div class="icp-bar">
                    <div class="fill icp-{{ icp_type }}" style="width: {{ (count / pipeline.total * 100)|round }}%"></div>
                </div>
                <span class="icp-count">{{ count }}</span>
            </div>
            {% endfor %}
        </div>
    </section>
    
    <!-- Top Signals -->
    <section class="dashboard-section">
        <h2>Most Common Positive Signals</h2>
        <ol class="signal-ranking">
            {% for signal, count in top_signals %}
            <li>
                <span class="signal-name">{{ signal|replace('_', ' ')|title }}</span>
                <span class="signal-count">{{ count }} leads</span>
            </li>
            {% endfor %}
        </ol>
    </section>
</div>
{% endblock %}
```

### Acceptance Criteria
- [ ] Pipeline progress shows all stages
- [ ] Tier distribution visualized
- [ ] Geographic breakdown by state
- [ ] ICP type distribution visible
- [ ] Top signals ranked
- [ ] Page loads in <2 seconds

---

## Phase 9: Pipeline Reliability

### Objective
Add resumable state, retry logic, and better progress tracking.

### Pre-Conditions
- Phases 1-8 complete
- Pipeline runs but may fail mid-batch

### Implementation Steps

#### Step 9.1: Create pipeline_runs table

**File:** `database/models.py`

```python
def create_pipeline_runs_table():
    """Create table for tracking pipeline runs."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS pipeline_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_type TEXT NOT NULL,
            status TEXT DEFAULT 'running',
            total_leads INTEGER DEFAULT 0,
            completed_leads INTEGER DEFAULT 0,
            failed_leads INTEGER DEFAULT 0,
            current_lead_id INTEGER,
            error_log TEXT,
            started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP,
            config TEXT
        )
    """)
    
    conn.commit()
    conn.close()
```

#### Step 9.2: Implement retry logic

**File:** `enrichment/gemini_client.py`

```python
import time
from functools import wraps

def retry_with_backoff(max_retries=3, base_delay=1):
    """Decorator for retry with exponential backoff."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    
                    if attempt < max_retries - 1:
                        delay = base_delay * (2 ** attempt)
                        logging.warning(f"Attempt {attempt + 1} failed: {e}. Retrying in {delay}s...")
                        time.sleep(delay)
                    else:
                        logging.error(f"All {max_retries} attempts failed: {e}")
            
            raise last_exception
        return wrapper
    return decorator


@retry_with_backoff(max_retries=3, base_delay=2)
def enrich_lead_with_gemini(website_text: str, lead_id: int) -> dict:
    """Enrich lead with Gemini API (with retry logic)."""
    # ... existing implementation
```

#### Step 9.3: Implement resumable pipeline

**File:** `app.py`

```python
def get_or_create_pipeline_run(run_type: str, config: dict = None):
    """Get existing incomplete run or create new one."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Check for incomplete run
    cursor.execute("""
        SELECT * FROM pipeline_runs
        WHERE run_type = ? AND status = 'running'
        ORDER BY started_at DESC
        LIMIT 1
    """, (run_type,))
    
    existing = cursor.fetchone()
    
    if existing:
        conn.close()
        return dict(existing), True  # (run, is_resume)
    
    # Create new run
    cursor.execute("""
        INSERT INTO pipeline_runs (run_type, config)
        VALUES (?, ?)
    """, (run_type, json.dumps(config or {})))
    
    run_id = cursor.lastrowid
    conn.commit()
    
    cursor.execute("SELECT * FROM pipeline_runs WHERE id = ?", (run_id,))
    new_run = dict(cursor.fetchone())
    conn.close()
    
    return new_run, False


def update_pipeline_progress(run_id: int, completed: int, failed: int, current_lead_id: int = None, error: str = None):
    """Update pipeline run progress."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        UPDATE pipeline_runs SET
            completed_leads = ?,
            failed_leads = ?,
            current_lead_id = ?,
            error_log = COALESCE(error_log, '') || ?
        WHERE id = ?
    """, (completed, failed, current_lead_id, 
          f"\n{error}" if error else "", run_id))
    
    conn.commit()
    conn.close()


def complete_pipeline_run(run_id: int, status: str = 'completed'):
    """Mark pipeline run as complete."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        UPDATE pipeline_runs SET
            status = ?,
            completed_at = CURRENT_TIMESTAMP
        WHERE id = ?
    """, (status, run_id))
    
    conn.commit()
    conn.close()
```

#### Step 9.4: Update pipeline to be resumable

**File:** `app.py`

```python
def run_full_pipeline(batch_size: int):
    """Run full enrichment pipeline with resume capability."""
    global pipeline_state
    
    # Get or create run
    run, is_resume = get_or_create_pipeline_run('full_pipeline', {'batch_size': batch_size})
    run_id = run['id']
    
    if is_resume:
        logging.info(f"Resuming pipeline run {run_id}")
        # Start from where we left off
        last_lead_id = run.get('current_lead_id', 0)
    else:
        last_lead_id = 0
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get leads to process
    cursor.execute("""
        SELECT id, business_name FROM leads
        WHERE id > ?
        AND (enrichment_status = 'pending' OR enrichment_status IS NULL)
        ORDER BY id
        LIMIT ?
    """, (last_lead_id, batch_size))
    
    leads = cursor.fetchall()
    pipeline_state['total'] = len(leads)
    completed = run.get('completed_leads', 0)
    failed = run.get('failed_leads', 0)
    
    for lead in leads:
        if pipeline_state['stop_requested']:
            complete_pipeline_run(run_id, 'stopped')
            break
        
        lead_id = lead['id']
        pipeline_state['current_lead'] = lead['business_name']
        
        try:
            # ... enrichment logic ...
            
            completed += 1
            pipeline_state['completed'] = completed
            update_pipeline_progress(run_id, completed, failed, lead_id)
            
        except Exception as e:
            failed += 1
            pipeline_state['failed'] = failed
            update_pipeline_progress(run_id, completed, failed, lead_id, str(e))
            logging.error(f"Lead {lead_id} failed: {e}")
    
    conn.close()
    
    if not pipeline_state['stop_requested']:
        complete_pipeline_run(run_id, 'completed')
    
    pipeline_state['running'] = False
```

### Acceptance Criteria
- [ ] Pipeline runs table tracks all runs
- [ ] Stopped pipeline can be resumed
- [ ] Retry logic handles transient failures
- [ ] Error log persisted for debugging
- [ ] Progress survives app restart

---

## Phase 10: Testing & Validation

### Objective
End-to-end testing and manual validation of the complete pipeline.

### Pre-Conditions
- Phases 1-9 complete
- Playwright installed for web testing

### Implementation Steps

#### Step 10.1: Create test suite structure

```
tests/
├── __init__.py
├── test_scoring.py
├── test_geo.py
├── test_gemini_parsing.py
├── test_api_endpoints.py
└── test_frontend.py
```

#### Step 10.2: Scoring model tests

**File:** `tests/test_scoring.py`

```python
import pytest
import sys
sys.path.insert(0, '..')
from enrichment.scorer import calculate_score, check_icp_qualification, calculate_geo_score

class TestICPQualification:
    """Test ICP qualification gate."""
    
    def test_primary_icp_greenhouse(self):
        lead = {
            "uses_growing_media": True,
            "production_method": "greenhouse"
        }
        qualified, icp_type = check_icp_qualification(lead)
        assert qualified == True
        assert icp_type == "primary"
    
    def test_disqualified_landscaper(self):
        lead = {
            "business_type": "landscaper",
            "disqualification_signals": '["landscape installation"]'
        }
        qualified, icp_type = check_icp_qualification(lead)
        assert qualified == False
        assert icp_type == "disqualified"
    
    def test_tertiary_organic_field(self):
        lead = {
            "business_name": "Organic Farm Co",
            "production_method": "field"
        }
        qualified, icp_type = check_icp_qualification(lead)
        assert qualified == True
        assert icp_type == "tertiary"


class TestScoring:
    """Test scoring calculations."""
    
    def test_tier_a_lead(self):
        """Sample requester profile should score Tier A."""
        lead = {
            "business_name": "Driftless Organics",
            "is_organic_certified": True,
            "uses_growing_media": True,
            "production_method": "greenhouse",
            "is_wholesale": True,
            "state": "WI",
            "geo_score": 25
        }
        result = calculate_score(lead)
        assert result['tier'] == 'A'
        assert result['score'] >= 80
        assert result['icp_qualified'] == True
    
    def test_tier_u_landscaper(self):
        """Landscaper should score Tier U."""
        lead = {
            "business_name": "Green Thumb Landscaping",
            "business_type": "landscaper",
            "disqualification_signals": '["landscaping", "lawn care"]',
            "uses_growing_media": False
        }
        result = calculate_score(lead)
        assert result['tier'] in ['U', 'C']
        assert result['icp_type'] == "disqualified"
    
    def test_score_breakdown_populated(self):
        """Score breakdown should list all matching signals."""
        lead = {
            "business_name": "Organic Growers Inc",
            "is_organic_certified": True,
            "is_wholesale": True,
            "uses_growing_media": True,
            "state": "WI",
            "geo_score": 25
        }
        result = calculate_score(lead)
        import json
        breakdown = json.loads(result['score_breakdown'])
        assert len(breakdown) > 0


class TestGeoScoring:
    """Test geographic scoring."""
    
    def test_wisconsin_bonus(self):
        lead = {"state": "WI"}
        assert calculate_geo_score(lead) == 25
    
    def test_regional_bonus(self):
        for state in ["IL", "MN", "IA", "MI"]:
            lead = {"state": state}
            assert calculate_geo_score(lead) == 20
    
    def test_far_state_penalty(self):
        lead = {"state": "TX"}
        assert calculate_geo_score(lead) == -5
    
    def test_address_extraction(self):
        lead = {"address": "123 Main St, Madison, WI 53703"}
        assert calculate_geo_score(lead) == 25
```

#### Step 10.3: Manual validation checklist

**File:** `VALIDATION_CHECKLIST.md`

```markdown
# Pre-Launch Validation Checklist

## Scoring Accuracy

- [ ] Pull 20 random Tier A leads - manually review, target 85%+ accuracy
- [ ] Pull 20 random Tier U leads - confirm they are truly disqualified
- [ ] Verify all 23 sample requesters would score Tier A or B
- [ ] Spot-check 5 leads per state for correct geo scoring

## Pipeline Functionality

- [ ] Full pipeline completes without errors on 50 leads
- [ ] Pipeline can be stopped and resumed
- [ ] Failed leads marked correctly
- [ ] Progress tracking accurate

## Frontend

- [ ] Lead cards render correctly
- [ ] Score breakdown displays all signals
- [ ] Tier override saves correctly
- [ ] Keyboard shortcuts work (j/k/a/b/c/u/r)
- [ ] Dashboard loads with correct stats
- [ ] Mobile responsive

## Export

- [ ] Instantly.ai CSV format correct
- [ ] Tier filter works
- [ ] Email required filter works
- [ ] Custom line included

## Performance

- [ ] Leads list loads in <2 seconds
- [ ] Dashboard loads in <2 seconds
- [ ] Scoring runs <100ms per lead
```

#### Step 10.4: Create validation script

**File:** `scripts/validate_scoring.py`

```python
"""
Validate scoring model against known sample requesters.
"""
import sqlite3
import json

# Sample requesters from cold calling
SAMPLE_REQUESTERS = [
    "Blue View Greenhouse",
    "Driftless Organics",
    "Hanson's Garden Village",
    "Southern Wisconsin Organics",
    "Wery's Blossom Creek",
    "West Star Organics",
    "BGC Growers",
    "Deep Rooted Organics",
    "Hauser's Superior View Farm",
    "Ledgeview Gardens",
    "Olden Organics",
    "Karthauser & Sons",
    "Rush Creek Growers",
    "Brookside Farms",
    "Schwertel Family Farms",
    "Stacks Family Farms",
    "Door Creek Orchard",
    "Fideler Farm",
    "Future Farm Hemp",
    "Hemp Haven Farms",
    "Ruesch Century Farm",
    "Vitruvian Farms",
]

def validate():
    conn = sqlite3.connect('data/leads.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    results = []
    
    for name in SAMPLE_REQUESTERS:
        cursor.execute("""
            SELECT business_name, tier, tier_override, score, icp_qualified, icp_type
            FROM leads
            WHERE business_name LIKE ?
            LIMIT 1
        """, (f"%{name}%",))
        
        row = cursor.fetchone()
        if row:
            effective_tier = row['tier_override'] or row['tier']
            results.append({
                "name": row['business_name'],
                "tier": effective_tier,
                "score": row['score'],
                "icp_qualified": row['icp_qualified'],
                "icp_type": row['icp_type'],
                "pass": effective_tier in ['A', 'B']
            })
        else:
            results.append({
                "name": name,
                "tier": "NOT FOUND",
                "score": None,
                "pass": False
            })
    
    conn.close()
    
    # Print results
    print("\n=== SAMPLE REQUESTER VALIDATION ===\n")
    
    passed = sum(1 for r in results if r['pass'])
    total = len(results)
    
    for r in results:
        status = "✓" if r['pass'] else "✗"
        print(f"{status} {r['name'][:30]:<30} Tier: {r['tier']} Score: {r['score']}")
    
    print(f"\n{passed}/{total} sample requesters scored Tier A/B ({passed/total*100:.0f}%)")
    
    if passed < total:
        print("\n⚠️  Some sample requesters did not score A/B - review scoring model")
    else:
        print("\n✓ All sample requesters would be contacted - scoring model validated")


if __name__ == "__main__":
    validate()
```

### Acceptance Criteria
- [ ] All unit tests pass
- [ ] Sample requester validation passes (100%)
- [ ] Manual checklist complete
- [ ] No critical bugs found
- [ ] Ready for production use

---

## Appendix A: File Change Summary

| Phase | Files Modified | Files Created |
|-------|---------------|---------------|
| 1 | database/models.py | - |
| 2 | enrichment/gemini_client.py | - |
| 3 | enrichment/scorer.py | - |
| 4 | enrichment/scorer.py | - |
| 5 | app.py | - |
| 6 | templates/leads.html | templates/components/lead_card.html, static/css/lead-cards.css |
| 7 | app.py | static/js/lead-review.js |
| 8 | app.py | templates/dashboard.html |
| 9 | app.py, database/models.py | - |
| 10 | - | tests/*.py, scripts/validate_scoring.py |

---

## Appendix B: Dependency Conflicts Prevention

### Rule 1: No Overlapping Column Names
- All new columns have unique prefixes
- `icp_` prefix for ICP-related columns
- `geo_` prefix for geographic columns

### Rule 2: Migration Order
- Always run Phase 1 (schema) before Phase 2 (Gemini)
- Always run Phase 3 (scoring) before Phase 4 (geo)
- Frontend phases (6-8) can run in parallel

### Rule 3: Backward Compatibility
- New columns have DEFAULT values
- Existing data not modified until re-enrichment
- Score calculation handles NULL values gracefully

### Rule 4: Testing Before Deployment
- Each phase has acceptance criteria
- Run tests before proceeding to next phase
- Backup database before destructive operations

---

## Appendix C: Rollback Procedures

### Phase 1 Rollback
```sql
-- Cannot drop columns in SQLite, must recreate table
-- Instead, just ignore new columns
```

### Phase 2 Rollback
```bash
git checkout HEAD~1 -- enrichment/gemini_client.py
```

### Phase 3 Rollback
```bash
git checkout HEAD~1 -- enrichment/scorer.py
# Re-run old scorer on all leads
curl -X POST http://127.0.0.1:5000/score/all
```

### Database Restore
```bash
copy data\leads.db.backup data\leads.db
```

---

## Execution Command Reference

```bash
# Phase 1: Migrate database
python -c "from database.models import migrate_db; migrate_db()"

# Phase 5: Re-score all leads (no API calls)
curl -X POST http://127.0.0.1:5000/rescore/all

# Phase 5: Re-enrich (uses API)
curl -X POST http://127.0.0.1:5000/re-enrich/start -H "Content-Type: application/json" -d '{"batch_size": 100}'

# Phase 10: Run tests
cd tests && pytest -v

# Phase 10: Validate scoring
python scripts/validate_scoring.py
```
