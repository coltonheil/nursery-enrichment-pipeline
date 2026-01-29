# CRM Setup & Tracking Framework

> **⚠️ DRAFT - Needs Nursery Pipeline Customization**
> 
> This CRM guide was migrated from `wormco-sales` workstream (2026-01-29). Core recommendations (HubSpot Free) still apply.
> 
> **TODO:** Customize for nursery enrichment pipeline:
> - Update deal properties (product types, order volumes, delivery regions)
> - Adapt pipeline stages to nursery sales cycle (lead → quote → order → delivery → reorder)
> - Configure reporting metrics for 9K Wisconsin lead database
> - Integrate with existing enrichment data (Tier A/B/C scoring, contact extraction)
> 
> ---

*Migrated: 2026-01-29*

---

## Executive Summary

**Recommended**: Start with **HubSpot Free CRM** or **Pipedrive** for MVP. Upgrade to paid tier when pipeline > 50 active deals.

---

## CRM Requirements (Worm Sales)

### Must-Have Features
1. **Pipeline stages** tracking (Lead → Closed/Won)
2. **Contact/account management**
3. **Activity logging** (calls, emails, meetings)
4. **Deal value tracking** (revenue forecasting)
5. **Email integration** (Gmail/Outlook sync)
6. **Mobile access** (iOS/Android app)

### Nice-to-Have
- Email sequences/automation
- Sales reporting/dashboards
- Integration with marketing tools
- Custom fields (industry, worm species interest, etc.)

---

## CRM Platform Comparison

### 1. HubSpot CRM (Free)

**Pros:**
- ✅ **100% free** (unlimited users, contacts, deals)
- ✅ **Excellent UI/UX** (easiest to learn)
- ✅ **Email tracking** (open/click notifications)
- ✅ **Gmail/Outlook integration**
- ✅ **Mobile app** (excellent)
- ✅ **Generous free tier** (no credit card required)

**Cons:**
- ❌ **Upsell heavy** (lots of paid features temptation)
- ❌ **Email sequences** require paid ($45/month)
- ❌ **Reporting** limited on free tier

**Pricing:**
- **Free**: $0 (full CRM)
- **Starter**: $45/month (email sequences, automation)
- **Professional**: $450/month (advanced automation, custom reporting)

**Best for**: Startups, teams new to CRM, tight budgets

---

### 2. Pipedrive

**Pros:**
- ✅ **Sales-focused** (built for pipeline management)
- ✅ **Visual pipeline** (drag-and-drop deals)
- ✅ **Email integration** (Gmail, Outlook)
- ✅ **Activity reminders** (never miss a follow-up)
- ✅ **Affordable** ($14/user/month)
- ✅ **Clean interface**

**Cons:**
- ❌ **No free tier** (14-day trial only)
- ❌ **Limited marketing features** (focused on sales only)
- ❌ **Email sequences** require higher tier

**Pricing:**
- **Essential**: $14/user/month (billed annually)
- **Advanced**: $29/user/month (email sync, automation)
- **Professional**: $59/user/month (revenue forecasts, custom reports)

**Best for**: Sales-first teams, visual pipeline management

---

### 3. Zoho CRM

**Pros:**
- ✅ **Free tier** (up to 3 users)
- ✅ **Feature-rich** (even on free tier)
- ✅ **Email integration**
- ✅ **Affordable paid tiers** ($14/user/month)
- ✅ **Customizable**

**Cons:**
- ❌ **Clunky UI** (dated design)
- ❌ **Steeper learning curve**
- ❌ **Free tier limits** (3 users max)

**Pricing:**
- **Free**: $0 (up to 3 users)
- **Standard**: $14/user/month
- **Professional**: $23/user/month (workflow automation)

**Best for**: Small teams (≤3), budget-conscious

---

### 4. Salesforce Essentials

**Pros:**
- ✅ **Industry standard** (powerful, scalable)
- ✅ **Massive app ecosystem** (AppExchange)
- ✅ **Enterprise-ready**

**Cons:**
- ❌ **Expensive** ($25/user/month minimum)
- ❌ **Overkill** for small sales teams
- ❌ **Complex** (requires training/admin)

**Pricing:**
- **Essentials**: $25/user/month (up to 10 users)
- **Professional**: $75/user/month
- **Enterprise**: $150/user/month

**Best for**: Enterprise, existing Salesforce ecosystem

---

### 5. Airtable (Alternative)

**Pros:**
- ✅ **Flexible** (spreadsheet + database hybrid)
- ✅ **Free tier** (generous limits)
- ✅ **Custom views** (kanban, calendar, grid)
- ✅ **Automations** (on paid tier)

**Cons:**
- ❌ **Not built for sales** (requires setup)
- ❌ **No native email integration**
- ❌ **Manual tracking** (no auto-logging)

**Pricing:**
- **Free**: $0 (1,200 records, 2GB)
- **Plus**: $10/user/month (5,000 records, automations)

**Best for**: Tech-savvy teams, custom workflows

---

## Recommendation for WormCo

### Phase 1: MVP (0-3 months)
**Platform**: **HubSpot Free CRM**

**Rationale:**
- Zero cost to start
- Easy setup (1-2 hours)
- Email tracking out of the box
- Mobile app for on-the-go updates
- No credit card required

**Setup:**
1. Sign up at hubspot.com
2. Import contacts from existing sources
3. Configure pipeline stages (see below)
4. Integrate Gmail/Outlook
5. Train team (30 min onboarding)

### Phase 2: Evaluate (3-6 months)
- If HubSpot meets needs → Stay on Free tier
- If email sequences needed → Upgrade to HubSpot Starter ($45/month)
- If sales-focused features lacking → Migrate to Pipedrive ($14/user/month)

---

## Pipeline Configuration (WormCo-Specific)

### Proposed Stages

| Stage | Description | Success Criteria |
|-------|-------------|------------------|
| **Lead** | Initial contact identified | Name, company, contact info |
| **Qualified** | Interest confirmed, budget fit | Discovery call completed |
| **Demo Scheduled** | Product demo booked | Meeting on calendar |
| **Proposal Sent** | Quote/proposal delivered | Document sent, received |
| **Negotiation** | Terms being discussed | Active back-and-forth |
| **Closed Won** | Deal signed! 🎉 | Contract signed, payment terms set |
| **Closed Lost** | Deal fell through | Reason logged |

### Deal Properties (Custom Fields)

- **Deal Value** (USD)
- **Expected Close Date**
- **Worm Species** (Red Wigglers, European Nightcrawlers, etc.)
- **Use Case** (Composting, Fishing, Agriculture, Research)
- **Quantity Needed** (lbs per month)
- **Lead Source** (Website, Referral, Cold Outreach, Trade Show)
- **Competitor** (if known)
- **Decision Maker** (Name, Title)
- **Next Action** (Call, Email, Demo, Proposal)

---

## Activity Tracking

### Required Activities to Log
1. **Calls** (with notes, duration)
2. **Emails** (auto-tracked via integration)
3. **Meetings** (demo, discovery, negotiation)
4. **Tasks** (follow-ups, send proposal, etc.)

### Activity Goals (Weekly)
- **Outbound calls**: 20-30/week
- **Emails sent**: 50-75/week
- **Demos booked**: 3-5/week
- **Proposals sent**: 2-3/week

---

## Reporting Dashboard (Initial Metrics)

### Key Metrics to Track
1. **Pipeline Value** (total $ in pipeline)
2. **Win Rate** (% of deals closed won)
3. **Average Deal Size** ($)
4. **Sales Cycle Length** (days from Lead → Closed Won)
5. **Conversion Rates** (by stage)
6. **Activity Metrics** (calls, emails, meetings per week)

### Reporting Cadence
- **Daily**: Pipeline review (morning standup)
- **Weekly**: Activity metrics, stage movement
- **Monthly**: Win rate, revenue forecast, lost deal analysis

---

## Implementation Checklist

### Week 1: Setup
- [ ] Sign up for HubSpot Free CRM
- [ ] Configure pipeline stages
- [ ] Add custom deal properties
- [ ] Integrate email (Gmail/Outlook)
- [ ] Import existing contacts (if any)
- [ ] Set up mobile app

### Week 2: Training & Launch
- [ ] Train team on CRM (30-60 min session)
- [ ] Create first 5 deals in pipeline
- [ ] Set activity goals (calls, emails)
- [ ] Schedule weekly pipeline review meeting
- [ ] Document CRM process (this file!)

### Week 3-4: Optimization
- [ ] Review initial usage (are deals being tracked?)
- [ ] Adjust pipeline stages if needed
- [ ] Set up email templates (via HubSpot or separate)
- [ ] Create reporting dashboard

---

## Best Practices

### 1. Update Daily
- Log all customer interactions same day
- Update deal stages immediately after calls/meetings
- Set next tasks before ending each interaction

### 2. Keep Clean Data
- Standardize company names (avoid duplicates)
- Use tags consistently
- Archive/delete old/duplicate contacts

### 3. Use Reminders
- Set follow-up tasks with due dates
- Enable email/mobile notifications
- Never let a deal sit >3 days without action

### 4. Review Weekly
- Pipeline review meeting (30 min)
- Identify stuck deals (>14 days in one stage)
- Adjust forecasts based on stage movement

---

## Integration Recommendations

### Now (MVP)
- **Email**: Gmail or Outlook (built-in)
- **Calendar**: Google Calendar or Outlook Calendar (auto-sync)

### Later (If Needed)
- **Marketing**: Mailchimp or Klaviyo (for nurture campaigns)
- **Accounting**: QuickBooks or Xero (invoice tracking)
- **Slack**: CRM notifications in Slack channel

---

## Cost Projection (Year 1)

| Scenario | Platform | Cost/Month | Cost/Year |
|----------|----------|------------|-----------|
| **Free Tier** | HubSpot Free | $0 | $0 |
| **Paid (1 user)** | Pipedrive Essential | $14 | $168 |
| **Paid (2 users)** | HubSpot Starter | $45 | $540 |

**Recommendation**: Start free, upgrade when revenue > $10K/month

---

## Next Steps

1. **Decision**: Approve HubSpot Free as MVP CRM
2. **Setup**: Complete Week 1 checklist (1-2 hours)
3. **Import**: Gather existing contact list (if any)
4. **Training**: Schedule 30-min team onboarding

---

**Questions for decision:**
- Who will be primary CRM admin?
- Do we have existing contacts to import?
- What's the target launch date for first deals in CRM?

