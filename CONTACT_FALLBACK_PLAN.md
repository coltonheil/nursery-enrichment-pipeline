# Contact Fallback Strategy
**Date:** 2026-01-27  
**Problem:** 75% of high-value leads have no owner name extracted  
**Solution:** Expand contact hierarchy beyond just owner

---

## 🎯 Contact Hierarchy (Priority Order)

### For Bulk Soil/Growing Media Buyers

**Priority 1: Owner/President** ✅ (Current target)
- Sole proprietors, family businesses
- Final decision maker
- Example: "Dave Bresina" at Dave Bresina's Nursery

**Priority 2: Operations Manager** 🆕
- Oversees production operations
- Controls input purchasing (soil, containers, etc)
- Often handles vendor relationships
- Keywords: "Operations Manager", "Production Manager", "General Manager"

**Priority 3: Head Grower/Grower** 🆕
- Hands-on with soil mixing
- Knows what works, influences purchasing
- Common in mid-large nurseries
- Keywords: "Head Grower", "Master Grower", "Lead Grower", "Production Grower"

**Priority 4: Purchasing Manager** 🆕
- Direct buyer of supplies
- Exists in larger operations (50+ employees)
- Keywords: "Purchasing Manager", "Procurement", "Supply Chain"

**Priority 5: Propagation Manager** 🆕
- Uses growing media daily
- Influences soil mix decisions
- Keywords: "Propagation Manager", "Propagator"

**Priority 6: Greenhouse Manager** 🆕
- Manages greenhouse operations
- Involved in media selection
- Keywords: "Greenhouse Manager", "Hoop House Manager"

**Priority 7: Sales/Marketing Contact** (Last Resort)
- May know internal buyers
- Can forward inquiry
- Keywords: "Sales Manager", "Marketing Director"

---

## 📝 Enhanced Gemini Extraction Prompt

### Current Prompt (Owner-Only)
```
Extract the owner's full name if clearly stated.
Return null if not found.
```

### New Prompt (Contact Hierarchy)
```
Extract contact information for someone who would purchase bulk growing media/soil.

Priority order (return the FIRST match found):
1. Owner/President name (e.g., "John Smith, Owner")
2. Operations Manager (e.g., "Sarah Johnson, Operations Manager")
3. Head Grower or Master Grower
4. Purchasing Manager or Procurement
5. Propagation Manager
6. Greenhouse Manager
7. Sales or Marketing contact (last resort)

Return:
- contact_name: Full name
- contact_title: Their role/title
- contact_priority: 1-7 (which level in hierarchy)
- contact_source: Where you found this (about page, team page, etc)

If NONE found, return null for all fields.

Look for:
- "About Us" sections with leadership
- "Our Team" or "Staff" pages
- Contact page with names and titles
- Bio sections
- Email addresses with names (e.g., "john.smith@...")
```

---

## 🔄 Re-Enrichment Process

### Step 1: Identify Leads Needing Re-Enrichment

**Criteria:**
```sql
SELECT * FROM leads
WHERE tier IN ('A', 'B', 'C')  -- High value
  AND (
    owner_name IS NULL 
    OR owner_name = ''
    OR owner_name NOT LIKE '% %'  -- Single word, likely incomplete
  )
  AND website_text IS NOT NULL  -- Has scraped data
  AND website_text != ''
ORDER BY tier ASC, score DESC
```

**Expected:** ~1,220 leads

### Step 2: Update Gemini Prompt

**New extraction fields:**
- `contact_name` (replaces `owner_name`)
- `contact_title` (new)
- `contact_priority` (new, 1-7)
- `contact_source` (new, for validation)

### Step 3: Run Re-Enrichment

**Process:**
1. For each lead:
   - Send enhanced prompt to Gemini
   - Extract contact using hierarchy
   - Update database with new contact info
   - Flag as `re_enrichment_status: 'completed'`

**Time estimate:**
- 1,220 leads × 3s per Gemini call = ~60 minutes
- With rate limiting: ~90 minutes

### Step 4: Email Hunting

**After re-enrichment:**
```sql
SELECT COUNT(*) FROM leads
WHERE tier IN ('A', 'B', 'C')
  AND contact_name IS NOT NULL
  AND website IS NOT NULL
  AND owner_email IS NULL
```

**Expected:** 800-1,000 leads ready for email hunting (vs 212 currently)

---

## 📊 Expected Results

### Before Re-Enrichment
| Metric | Current | Target |
|--------|---------|--------|
| Tier A/B with contact name | 212 (32%) | - |
| Tier A/B with email | 217 (33%) | - |

### After Re-Enrichment
| Metric | Expected | Notes |
|--------|----------|-------|
| Tier A/B with contact name | 500-600 (76-91%) | +140-288% |
| Tier A/B with email | 450-540 (69-82%) | +107-149% |
| Contact hierarchy breakdown | 30% owner, 40% ops/grower, 20% purchasing, 10% other | Estimated |

**ROI:**
- Time: ~2 hours total (re-enrich + email hunt)
- Cost: ~$15 (Gemini API)
- Value: +250-350 high-value emails × $5 = **$1,250-1,750**

---

## 🎨 Contact Fallback Examples

### Example 1: Large Nursery (No Owner Publicly Listed)
**Website:** "About Us" page lists:
- Operations Manager: "Jennifer Martinez"
- Head Grower: "Robert Chen"
- Sales Manager: "David Wilson"

**Extraction:**
```json
{
  "contact_name": "Jennifer Martinez",
  "contact_title": "Operations Manager",
  "contact_priority": 2,
  "contact_source": "About Us page - leadership team"
}
```

**Why:** Priority 2 (Ops Manager) found, controls purchasing

---

### Example 2: Mid-Size Nursery (Owner + Staff)
**Website:** Owner mentioned, but also lists grower

**Before (current extraction):**
```json
{
  "owner_name": "Smith Family",  // Vague
}
```

**After (enhanced extraction):**
```json
{
  "contact_name": "Tom Smith",  // Found in team section
  "contact_title": "Owner/Head Grower",
  "contact_priority": 1,
  "contact_source": "Our Team page"
}
```

**Why:** Found actual person, not just "family"

---

### Example 3: Small Nursery (No Names at All)
**Website:** Generic content, no team page, email is info@

**Extraction:**
```json
{
  "contact_name": null,
  "contact_title": null,
  "contact_priority": null,
  "contact_source": "No contacts found on website"
}
```

**Fallback:** Use generic email (info@), but mark as low-priority for personal outreach

---

## 🔧 Implementation Steps

### Phase 1: Update Gemini Client (30 min)
- [ ] Add new extraction fields to prompt
- [ ] Update `enrich_lead_with_gemini()` function
- [ ] Add contact hierarchy logic
- [ ] Test on 10 sample leads

### Phase 2: Update Database Schema (10 min)
- [ ] Add `contact_name` column (alias for owner_name)
- [ ] Add `contact_title` column
- [ ] Add `contact_priority` column (1-7)
- [ ] Add `contact_source` column
- [ ] Add `re_enrichment_attempt` counter

### Phase 3: Re-Run Gemini (90 min)
- [ ] Query 1,220 leads needing re-enrichment
- [ ] Process with enhanced prompt
- [ ] Rate limit: 1-2s delay between calls
- [ ] Log results to `re_enrichment_results.csv`

### Phase 4: Email Hunting (60 min)
- [ ] Query leads with new contact names
- [ ] Run email hunter with 3-layer fallback
- [ ] Expected: 800-1,000 new leads ready
- [ ] Re-score with email data

### Phase 5: Analysis (15 min)
- [ ] Contact hierarchy breakdown (how many at each level?)
- [ ] Email coverage improvement
- [ ] Tier changes from new emails

**Total Time:** ~3 hours  
**Total Cost:** ~$15 (Gemini + Brave)  
**Expected Value:** +250-350 emails × $5 = **$1,250-1,750**

---

## ⚠️ Potential Issues

### Issue 1: Still No Contacts Found
**If 30%+ still have no names after re-enrichment:**

**Solutions:**
1. Manual research on top 50 Tier A leads
2. LinkedIn/social media lookup
3. Phone calls to get right contact
4. Use generic email with personalized company context

### Issue 2: Wrong Contact Type Extracted
**If Gemini extracts receptionist, retail staff, etc:**

**Solutions:**
1. Add negative filters to prompt ("NOT receptionist, retail clerk, cashier")
2. Validate titles against known purchasing roles
3. Manual review of Tier A extractions

### Issue 3: Vague Names
**If extractions are still vague ("Smith Family", "The Team"):**

**Solutions:**
1. Prompt refinement: "Return FULL name of ONE specific person"
2. Require first + last name validation
3. Flag ambiguous names for manual review

---

## 📈 Success Metrics

**After Re-Enrichment + Email Hunting:**

| Metric | Baseline | Target | Stretch |
|--------|----------|--------|---------|
| Tier A/B with contact name | 212 (32%) | 500 (76%) | 600 (91%) |
| Tier A/B with personal email | 217 (33%) | 450 (69%) | 540 (82%) |
| Contact priority 1-3 (high value) | - | 70%+ | 80%+ |
| Email confidence 50%+ | ~77% | 80%+ | 85%+ |

**Final Email Coverage Goal:**
- **Tier A: 80%+** (153/191)
- **Tier B: 75%+** (349/465)
- **Combined: 77%+** (502/656)

---

## 🚀 Ready to Execute?

**Recommended sequence:**
1. ✅ Approve this plan
2. Update Gemini prompt (30 min)
3. Test on 10 leads (10 min)
4. Run full re-enrichment (90 min)
5. Email hunt on new contacts (60 min)
6. Report results

**Total: ~3 hours, $15 cost, $1,250-1,750 value**

Say "go" and I'll start implementation! 🎯
