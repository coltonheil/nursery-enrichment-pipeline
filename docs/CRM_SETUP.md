# CRM SETUP - Nursery Growing Media Sales

**Recommended Platform:** HubSpot Free (0-1M records, unlimited users)  
**Target:** Wisconsin nursery sales pipeline  
**Last Updated:** 2026-01-29

---

## Why HubSpot Free?

**Pros:**
- ✅ Free tier supports 1M contacts (you have 7,769 leads)
- ✅ Built-in email tracking and templates
- ✅ Deal pipeline with custom stages
- ✅ Task management and follow-up reminders
- ✅ Basic reporting (conversion rates, deal value)
- ✅ No credit card required to start

**Cons:**
- ⚠️ Limited automation (upgrade to Starter $20/mo for workflows)
- ⚠️ No custom reporting (but exports work fine)
- ⚠️ Branding on forms/emails (removable in paid tiers)

**Alternative:** Airtable (more flexible, but not built for sales)

---

## Import Strategy

### Phase 1: Tier A Leads (398 leads)

**Priority:** Import first, start outreach immediately

**Fields to import:**
```csv
business_name, contact_name, contact_title, contact_email, owner_email, 
website, city, state, tier, score, business_type, is_wholesale, 
container_production, organic_focus, greenhouse_sqft
```

**HubSpot mapping:**
- `business_name` → Company Name
- `contact_name` → Contact Name (parse first/last)
- `contact_title` → Job Title
- `contact_email` → Email (primary)
- `owner_email` → Email (secondary if contact_email blank)
- `website` → Website
- `city` → City
- `state` → State
- `tier` → Custom Property: "Lead Tier" (A/B/C/U)
- `score` → Custom Property: "Lead Score" (number field)
- `business_type` → Custom Property: "Nursery Type" (dropdown)
- `is_wholesale` → Custom Property: "Wholesale Operation" (yes/no)
- `container_production` → Custom Property: "Container Production" (yes/no)
- `organic_focus` → Custom Property: "Organic Focus" (yes/no)
- `greenhouse_sqft` → Custom Property: "Greenhouse Size" (number)

---

### Phase 2: Tier B Leads (534 leads)

**Timing:** After Tier A outreach is underway (2-3 weeks)

**Same import process**, just filter for `tier = 'B'` in export.

---

### Phase 3: Tier C (Optional - for future campaigns)

**Only import if:**
- You have bandwidth for lower-priority outreach
- Want to track inbound inquiries from this segment
- Building email newsletter list

**Not urgent** - focus on A+B first.

---

## Custom Properties to Create

### Contact-Level Properties

| Property Name | Type | Options/Format | Purpose |
|---------------|------|----------------|---------|
| **Lead Tier** | Dropdown | A, B, C, U | Prioritization |
| **Lead Score** | Number | 0-150 | ICP qualification score |
| **Outreach Status** | Dropdown | Not Contacted, Contacted, Responded, Qualified, Unqualified, Nurture | Pipeline tracking |
| **Sample Requested** | Yes/No | Boolean | Track sample program |
| **Sample Sent Date** | Date | MM/DD/YYYY | Follow-up timing |
| **Estimated Annual Volume** | Number | Cubic yards | Qualification |
| **Current Supplier** | Text | Pro-Mix, SunGro, etc. | Competitive intel |
| **Next Follow-Up Date** | Date | MM/DD/YYYY | Task management |

### Company-Level Properties

| Property Name | Type | Options/Format | Purpose |
|---------------|------|----------------|---------|
| **Nursery Type** | Dropdown | Wholesale Nursery, Garden Center, Greenhouse, Tree Farm, Landscaper, Other | Segmentation |
| **Wholesale Operation** | Yes/No | Boolean | ICP fit |
| **Container Production** | Yes/No | Boolean | ICP fit |
| **Organic Focus** | Yes/No | Boolean | Product targeting |
| **Greenhouse Size (sq ft)** | Number | 0-1,000,000 | Scale proxy |
| **Estimated Order Frequency** | Dropdown | One-time, Seasonal (2x/year), Quarterly, Monthly | Revenue forecast |
| **Region** | Dropdown | SE Wisconsin, NE Wisconsin, Central, Western, Other | Delivery planning |

---

## Deal Pipeline Stages

### Pipeline Name: "Nursery Sales"

**Stages:**

1. **Sample Requested** (Entry Point)
   - Deal created when sample pallet is requested
   - Probability: 10%
   - Avg time in stage: 2 weeks

2. **Sample Delivered**
   - Sample sent, waiting for feedback
   - Probability: 20%
   - Avg time in stage: 1-2 weeks

3. **Quote Sent**
   - Pricing provided for full order
   - Probability: 40%
   - Avg time in stage: 1 week

4. **Negotiation**
   - Back-and-forth on pricing, delivery, terms
   - Probability: 60%
   - Avg time in stage: 1 week

5. **Verbal Commitment**
   - Customer says yes, pending PO or paperwork
   - Probability: 80%
   - Avg time in stage: 3-5 days

6. **Closed Won** 🎉
   - Order placed, delivery scheduled
   - Probability: 100%
   - Deal value = order total

7. **Closed Lost** ❌
   - Lost to competitor, no budget, timing not right
   - **Required:** Lost reason (dropdown)

**Lost Reasons:**
- Price too high
- Competitor (specify which)
- Volume too small
- Timing not right (mark for future follow-up)
- No response / ghosted
- Not a fit (wrong business type)

---

## Deal Properties

| Property | Type | Purpose |
|----------|------|---------|
| **Deal Name** | Text | Format: "[Company] - [Season] [Year]" (e.g., "Green Valley - Spring 2026") |
| **Deal Amount** | Currency | Estimated order value |
| **Order Volume (cu yd)** | Number | Cubic yards requested |
| **Product Blend** | Dropdown | Standard, Organic, Custom, Mix |
| **Delivery Date** | Date | When they need it |
| **Delivery Region** | Dropdown | SE WI, NE WI, Central, Western |
| **Freight Cost** | Currency | For margin tracking |
| **Margin %** | Number | For profitability analysis |
| **Season** | Dropdown | Spring, Summer, Fall, Winter, Year-Round |

---

## Email Templates (HubSpot)

### Template 1: Initial Outreach (Tier A)

**Name:** "Tier A - Initial Contact"  
**Subject:** "{{contact.firstname}}, bulk growing media question"

```
Hi {{contact.firstname}},

I noticed {{company.name}} runs {{company.nursery_type}} operations in {{company.city}}. 

We supply bulk growing media to Wisconsin nurseries. Most see:
- 15-25% cost savings vs. Pro-Mix/SunGro retail pricing
- Consistent quality across seasonal orders
- Same-day/next-day delivery in {{company.region}}

Worth a quick call to see if our pricing works for {{company.name}}'s spring season?

Best,
{{owner.firstname}}
{{owner.email}}
{{owner.phone}}
```

---

### Template 2: Follow-Up #1

**Name:** "Follow-Up - Price Sheet"  
**Subject:** "Re: {{contact.firstname}}, bulk growing media question"

```
Hi {{contact.firstname}},

Following up on my note about growing media supply for {{company.name}}.

I realize you're likely slammed with spring prep, but wanted to share:
- Current pricing sheet (attached)
- Delivery schedule for {{company.region}}

Even if timing isn't right for this season, worth keeping on file?

Best,
{{owner.firstname}}
```

**Attachments:** Price sheet PDF

---

### Template 3: Sample Program

**Name:** "Sample Offer"  
**Subject:** "Sample program for {{company.name}}"

```
Hi {{contact.firstname}},

We offer free sample pallets (2-3 cu yd) to Wisconsin nurseries before season starts. That way you can test quality before committing.

If you'd like a sample delivered for your spring trials, just reply with your delivery address. No obligation.

Best,
{{owner.firstname}}
```

---

## Task Workflows (Manual for Free Tier)

### After Initial Email Sent:

**Task 1:** Check for open (Day 1)  
**Task 2:** Send Follow-Up #1 if no response (Day 3)  
**Task 3:** Send Follow-Up #2 if no response (Day 8)  
**Task 4:** Final breakup email (Day 15)  
**Task 5:** Mark "Nurture" and set reminder for next season (Day 20)

**HubSpot Free Limitation:** No automated workflows - you manually create these tasks per contact. Upgrade to Starter ($20/mo) for automation.

---

## Sequences (Paid Feature - $20/mo)

**If you upgrade to Starter, create:**

**Sequence 1: Tier A Cold Outreach**
1. Day 0: Initial email (Template 1)
2. Day 3: Follow-up #1 (Template 2)
3. Day 8: Sample offer (Template 3)
4. Day 15: Breakup email

**Sequence 2: Tier B Cold Outreach**
(Same as Tier A, but different initial template focusing on volume/cost)

**Sequence 3: Sample Follow-Up**
1. Day 0: Sample delivered confirmation
2. Day 7: Check-in on sample quality
3. Day 14: Quote offer
4. Day 21: Final follow-up

---

## Reporting & Dashboards

### Key Metrics to Track (Free Tier)

**Lead Metrics:**
- Total contacts by tier (A/B/C)
- Outreach status distribution
- Response rate by tier
- Sample requests per week

**Deal Metrics:**
- Open deals by stage
- Avg deal size
- Win rate (Closed Won / Total Closed)
- Avg time to close
- Revenue by month

**Activity Metrics:**
- Emails sent per week
- Calls logged per week
- Tasks completed vs. overdue

### Reports to Create

**Report 1: Tier A Pipeline Health**
- Filter: Tier = A, Deal Stage != Closed Lost/Won
- Group by: Deal Stage
- Metric: Count + Total Value

**Report 2: Weekly Activity**
- Filter: Activity date = This Week
- Group by: Activity type (Email, Call, Meeting)
- Metric: Count

**Report 3: Win/Loss Analysis**
- Filter: Closed This Month
- Group by: Outcome (Won/Lost), Lost Reason
- Metric: Count + Revenue

---

## Import Process (Step-by-Step)

### Step 1: Export from SQLite

```bash
cd ~/clawd/projects/nursery-enrichment-pipeline

sqlite3 data/leads.db << 'EOF' > exports/tier_a_export.csv
.headers on
.mode csv
SELECT 
  business_name,
  contact_name,
  contact_title,
  contact_email,
  owner_email,
  website,
  city,
  state,
  tier,
  score,
  business_type,
  CASE WHEN is_wholesale = 1 THEN 'Yes' ELSE 'No' END as is_wholesale,
  CASE WHEN container_production = 1 THEN 'Yes' ELSE 'No' END as container_production,
  CASE WHEN organic_focus = 1 THEN 'Yes' ELSE 'No' END as organic_focus,
  greenhouse_sqft
FROM leads
WHERE tier = 'A'
ORDER BY score DESC;
EOF
```

**Result:** `exports/tier_a_export.csv` ready for HubSpot import

---

### Step 2: Clean Data

**Before importing, fix:**
- Split `contact_name` into `first_name` and `last_name`
- Remove any leads without email (`contact_email` OR `owner_email` required)
- Add default value for blanks (e.g., `business_type = 'Unknown'`)
- Format phone numbers consistently (if you have them)

**Script to clean:**

```bash
# Add first_name and last_name columns
# (Use Python/Node script or spreadsheet)
```

---

### Step 3: Import to HubSpot

1. Go to: Contacts → Import
2. Select: "Import from file"
3. Upload: `tier_a_export.csv`
4. Map fields:
   - Auto-match standard fields (email, name, company)
   - Manually map custom properties (tier, score, etc.)
5. Create properties if missing (e.g., "Lead Tier")
6. Import & review for duplicates

**Expected:** 398 contacts imported (Tier A)

---

### Step 4: Create Segmented Lists

**List 1: Tier A - Has Personal Email**
- Filter: Tier = A AND contact_email IS NOT EMPTY
- **Count:** ~72 contacts
- **Use:** Highest priority outreach

**List 2: Tier A - Generic Email Only**
- Filter: Tier = A AND contact_email IS EMPTY AND owner_email IS NOT EMPTY
- **Count:** ~146 contacts
- **Use:** Secondary outreach (less personalized)

**List 3: Tier A - Organic Focus**
- Filter: Tier = A AND organic_focus = Yes
- **Count:** ~TBD
- **Use:** Organic product messaging

**List 4: Tier A - Large Greenhouses**
- Filter: Tier = A AND greenhouse_sqft > 10000
- **Count:** ~TBD
- **Use:** High-volume pricing, custom blends

---

## Daily Workflow (Using Free Tier)

### Morning (30 min)
1. Check overnight responses
2. Update contact status (Contacted → Responded)
3. Create deals for sample requests
4. Schedule follow-up tasks

### Outreach Block (1-2 hours)
1. Pick 10-20 Tier A contacts from "Not Contacted" list
2. Research each (5 min per contact - website, crops, notes)
3. Personalize Template 1 for each
4. Send emails via HubSpot (tracks opens/clicks automatically)
5. Create follow-up task for Day 3

### Afternoon (30 min)
1. Make calls to Tier A contacts who opened email
2. Log call outcomes in HubSpot
3. Send sample offers to interested contacts
4. Update deal stages

### End of Day (15 min)
1. Review metrics (emails sent, responses, deals created)
2. Plan tomorrow's outreach targets
3. Clear overdue tasks

---

## Upgrade Triggers

**When to upgrade to HubSpot Starter ($20/mo):**
- ✅ Sending >50 emails/week manually (automation saves time)
- ✅ Managing >20 active deals (sequences help)
- ✅ Need A/B testing on email templates
- ✅ Want automated follow-up sequences

**What you get:**
- Email sequences (set-and-forget follow-ups)
- Basic automation (auto-create tasks, deals)
- Remove HubSpot branding
- Better reporting

---

## Next Steps

- [ ] Create HubSpot Free account
- [ ] Set up custom properties (15 min)
- [ ] Build deal pipeline stages (10 min)
- [ ] Export Tier A leads from SQLite (5 min)
- [ ] Clean export data (30 min)
- [ ] Import to HubSpot (15 min)
- [ ] Create segmented lists (10 min)
- [ ] Set up email templates (30 min)
- [ ] Start daily outreach workflow

**Total setup time:** ~2 hours

---

*CRM is a tool, not a strategy. Focus on high-quality outreach to Tier A contacts first. Don't over-engineer the system.*
