# Instantly.ai Integration Vision
**Goal:** Seamless lead flow from enrichment pipeline → Instantly.ai campaigns

---

## 🎯 Current State vs. Desired State

### Current Manual Flow
```
1. Pipeline enriches leads → tiers assigned
2. Export CSV from V2 interface
3. Download CSV file
4. Log into Instantly.ai
5. Upload CSV to campaign manually
6. Map columns
7. Start campaign
```
**Pain Points:** 6+ manual steps, prone to errors, no tracking, can't track which leads were sent when

### Desired Automated Flow
```
1. Pipeline enriches leads → tiers assigned
2. Review leads in "Outreach Queue" (staging area)
3. One-click "Send to Instantly" 
4. Leads auto-routed to correct campaign (Tier A → Premium, Tier B → Standard)
5. Status tracked in pipeline database
6. Optional: Sync responses back to pipeline
```
**Benefits:** 1-2 clicks, automatic, tracked, no CSV files, no duplicate sends

---

## 🏗️ Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                    Nursery Enrichment Pipeline                   │
│                                                                  │
│  ┌──────────────┐   ┌──────────────┐   ┌──────────────┐       │
│  │   Import     │ → │   Enrich     │ → │   Scoring    │       │
│  │   Leads      │   │   (Google,   │   │   & Tiering  │       │
│  │              │   │    AI, Web)  │   │              │       │
│  └──────────────┘   └──────────────┘   └──────────────┘       │
│                                              │                  │
│                                              ▼                  │
│                                    ┌──────────────────┐         │
│                                    │  Outreach Queue  │         │
│                                    │  (Staging Area)  │         │
│                                    │                  │         │
│                                    │  - Review leads  │         │
│                                    │  - Edit fields   │         │
│                                    │  - Batch approve │         │
│                                    └──────────────────┘         │
│                                              │                  │
│                                              ▼                  │
│                                    ┌──────────────────┐         │
│                                    │  Instantly Sync  │         │
│                                    │   Controller     │         │
│                                    │                  │         │
│                                    │  - Route by tier │         │
│                                    │  - Deduplicate   │         │
│                                    │  - Track status  │         │
│                                    └──────────────────┘         │
│                                              │                  │
└──────────────────────────────────────────────┼──────────────────┘
                                               │
                                               ▼ API
                                    ┌──────────────────┐
                                    │  Instantly.ai    │
                                    │                  │
                                    │  Campaign A      │
                                    │  (Tier A leads)  │
                                    │                  │
                                    │  Campaign B      │
                                    │  (Tier B leads)  │
                                    └──────────────────┘
                                               │
                                               ▼ Webhooks (optional)
                                    ┌──────────────────┐
                                    │  Response Sync   │
                                    │                  │
                                    │  - Opened        │
                                    │  - Replied       │
                                    │  - Bounced       │
                                    └──────────────────┘
```

---

## 📋 Phase 1: Core Integration (MVP)

### What We're Building
**Goal:** Replace CSV export with one-click Instantly send

### New Components

#### 1. Database Schema
```sql
-- Track which leads were sent to Instantly
CREATE TABLE instantly_syncs (
    id INTEGER PRIMARY KEY,
    lead_id INTEGER NOT NULL,
    campaign_id TEXT NOT NULL,
    instantly_lead_id TEXT,  -- ID from Instantly API
    sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status TEXT,  -- 'pending', 'sent', 'failed'
    error_message TEXT,
    FOREIGN KEY (lead_id) REFERENCES leads(id)
);

-- Campaign configuration
CREATE TABLE instantly_campaigns (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    instantly_campaign_id TEXT NOT NULL,
    tier_filter TEXT,  -- 'A', 'B', 'A,B', etc.
    is_active BOOLEAN DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### 2. API Integration (`instantly_client.py`)
```python
class InstantlyClient:
    def __init__(self, api_key):
        self.api_key = api_key
        self.base_url = "https://api.instantly.ai/api/v1"
    
    def add_lead_to_campaign(self, campaign_id, lead_data):
        """
        Add a single lead to an Instantly campaign
        
        Args:
            campaign_id: Instantly campaign ID
            lead_data: {
                'email': 'owner@nursery.com',
                'first_name': 'John',
                'last_name': 'Smith',
                'company_name': 'ABC Nursery',
                'personalization': {...},  # Custom fields
            }
        
        Returns:
            {'success': True, 'lead_id': '...'}
        """
        ...
    
    def add_leads_batch(self, campaign_id, leads):
        """Batch add up to 100 leads at once"""
        ...
    
    def get_campaign_stats(self, campaign_id):
        """Get campaign statistics"""
        ...
```

#### 3. New Routes (`app.py`)
```python
@app.route('/api/instantly/send', methods=['POST'])
def send_to_instantly():
    """
    Send selected leads to Instantly campaign
    
    Request body:
    {
        'lead_ids': [1, 2, 3, ...],
        'campaign_id': 'camp_abc123',
        'tier_routing': true  // auto-route by tier
    }
    
    Returns:
    {
        'success': true,
        'sent': 45,
        'failed': 2,
        'errors': [...]
    }
    """
    ...

@app.route('/api/instantly/campaigns')
def get_instantly_campaigns():
    """List configured Instantly campaigns"""
    ...

@app.route('/api/instantly/status/<lead_id>')
def get_instantly_status(lead_id):
    """Check if lead was sent to Instantly and status"""
    ...
```

#### 4. V2 Export UI Updates
Add button alongside CSV export:
```html
<!-- In export_v2.html -->
<div class="flex gap-3">
    <!-- Existing CSV/Excel export -->
    <button id="export-csv-btn" class="btn-primary">
        📥 Export CSV
    </button>
    
    <!-- NEW: Send to Instantly -->
    <button id="send-instantly-btn" class="btn-success">
        🚀 Send to Instantly
        <span class="badge">1168 leads</span>
    </button>
</div>

<!-- Modal for campaign selection -->
<div id="instantly-modal" class="modal">
    <h3>Send to Instantly.ai</h3>
    <p>Select campaign for 1168 leads:</p>
    
    <select id="campaign-select">
        <option value="auto">Auto-route by tier</option>
        <option value="camp_tier_a">Premium Campaign (Tier A)</option>
        <option value="camp_tier_b">Standard Campaign (Tier B)</option>
    </select>
    
    <div class="preview">
        <h4>Preview (first 5 leads)</h4>
        <!-- Show lead preview with fields that will be sent -->
    </div>
    
    <button onclick="confirmSendToInstantly()">
        Confirm & Send
    </button>
</div>
```

### Configuration
```python
# config.py or environment variables
INSTANTLY_API_KEY = "your_api_key_here"

# Campaign mappings
INSTANTLY_CAMPAIGNS = {
    'tier_a': {
        'id': 'camp_abc123',
        'name': 'Premium Nurseries Campaign'
    },
    'tier_b': {
        'id': 'camp_def456',
        'name': 'Standard Nurseries Campaign'
    }
}
```

---

## 📋 Phase 2: Staging Area (Outreach Queue)

### What We're Building
**Goal:** Review and approve leads before sending to Instantly

### New Components

#### 1. Outreach Queue Table
```sql
CREATE TABLE outreach_queue (
    id INTEGER PRIMARY KEY,
    lead_id INTEGER NOT NULL,
    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status TEXT DEFAULT 'pending',  -- 'pending', 'approved', 'rejected', 'sent'
    assigned_campaign TEXT,
    notes TEXT,
    approved_by TEXT,
    approved_at TIMESTAMP,
    FOREIGN KEY (lead_id) REFERENCES leads(id)
);
```

#### 2. New V2 Page: `/v2/outreach-queue`
```
┌────────────────────────────────────────────────────────┐
│  Outreach Queue (45 leads pending)                     │
│                                                        │
│  [ Filter: All | Tier A | Tier B ]  [ Bulk Actions ▼ ]│
│                                                        │
│  ┌──────────────────────────────────────────────────┐ │
│  │ ✓  ABC Nursery                    Tier A         │ │
│  │    John Smith • owner@abc.com                    │ │
│  │    📧 Personal email  📞 Phone verified          │ │
│  │    Campaign: Premium Nurseries                   │ │
│  │    [ View Details ] [ Edit ] [ Remove ]          │ │
│  └──────────────────────────────────────────────────┘ │
│                                                        │
│  ┌──────────────────────────────────────────────────┐ │
│  │ ✓  XYZ Garden Center                 Tier B      │ │
│  │    Jane Doe • info@xyz.com                       │ │
│  │    📧 Generic email  ⚠️ No phone                 │ │
│  │    Campaign: Standard Nurseries                  │ │
│  │    [ View Details ] [ Edit ] [ Remove ]          │ │
│  └──────────────────────────────────────────────────┘ │
│                                                        │
│  [ Select All ]  [ Approve Selected (45) ]            │
│                                                        │
│  [ 🚀 Send 45 Approved to Instantly ]                 │
└────────────────────────────────────────────────────────┘
```

#### 3. Workflow
```
Pipeline Enrichment → [Add to Queue] → Outreach Queue
                                              │
                                              ▼
                                    [Review & Edit]
                                              │
                                              ▼
                                      [Bulk Approve]
                                              │
                                              ▼
                                   [Send to Instantly]
                                              │
                                              ▼
                                    Track in instantly_syncs
```

### Benefits
- **Quality control:** Review before sending
- **Edit fields:** Fix contact names, emails before sending
- **Batch operations:** Approve 100+ leads at once
- **Campaign override:** Change default campaign routing
- **Notes:** Add context for each lead

---

## 📋 Phase 3: Advanced Features (Optional)

### 3.1 Bi-Directional Sync
**Goal:** Track campaign performance in pipeline

#### Webhook Listener
```python
@app.route('/webhooks/instantly', methods=['POST'])
def instantly_webhook():
    """
    Handle events from Instantly:
    - Email opened
    - Email replied
    - Email bounced
    - Lead unsubscribed
    
    Update lead status in database
    """
    event = request.json
    
    if event['type'] == 'email.opened':
        # Update lead: email_opened = True, opened_at = ...
        ...
    
    elif event['type'] == 'email.replied':
        # Update lead: replied = True, reply_text = ...
        # Maybe move to "Hot Leads" queue
        ...
    
    elif event['type'] == 'email.bounced':
        # Mark email as invalid, don't send future campaigns
        ...
```

#### New Database Fields
```sql
ALTER TABLE leads ADD COLUMN instantly_opened BOOLEAN DEFAULT 0;
ALTER TABLE leads ADD COLUMN instantly_replied BOOLEAN DEFAULT 0;
ALTER TABLE leads ADD COLUMN instantly_bounced BOOLEAN DEFAULT 0;
ALTER TABLE leads ADD COLUMN last_contacted_at TIMESTAMP;
```

#### Dashboard Widget
```
┌────────────────────────────────────┐
│  Campaign Performance              │
│                                    │
│  Sent:     1,168 leads             │
│  Opened:   456 (39%)               │
│  Replied:  23 (2%)                 │
│  Bounced:  12 (1%)                 │
│                                    │
│  🔥 Hot Leads (replied): 23        │
│  [ View Hot Leads → ]              │
└────────────────────────────────────┘
```

### 3.2 Smart Deduplication
**Goal:** Never send the same lead twice

```python
def can_send_to_instantly(lead_id, campaign_id):
    """
    Check if lead can be sent to campaign
    
    Rules:
    - Not sent to this campaign in last 90 days
    - Not in any active campaign currently
    - Email hasn't bounced
    - Not unsubscribed
    """
    ...
```

### 3.3 Scheduled Sends
**Goal:** Drip-feed leads into campaigns over time

```python
@app.route('/api/instantly/schedule', methods=['POST'])
def schedule_instantly_send():
    """
    Schedule batch sends
    
    {
        'lead_ids': [1, 2, 3, ...],
        'campaign_id': 'camp_abc',
        'schedule': {
            'start_date': '2026-02-01',
            'leads_per_day': 50,
            'days_of_week': [1, 2, 3, 4, 5]  // Mon-Fri only
        }
    }
    """
    ...
```

---

## 🛠️ Implementation Plan

### Phase 1: Core Integration (Week 1)
**Estimated Time:** 8-12 hours

- [ ] Create database tables (`instantly_syncs`, `instantly_campaigns`)
- [ ] Build `InstantlyClient` class with API methods
- [ ] Create `/api/instantly/send` endpoint
- [ ] Add "Send to Instantly" button to V2 Export page
- [ ] Build campaign selection modal
- [ ] Test with small batch (5-10 leads)
- [ ] Add error handling and logging

**Deliverable:** One-click send from Export page to Instantly

### Phase 2: Staging Area (Week 2)
**Estimated Time:** 12-16 hours

- [ ] Create `outreach_queue` table
- [ ] Build `/v2/outreach-queue` page
- [ ] Add "Add to Queue" button to Export page
- [ ] Build review/edit UI
- [ ] Implement bulk approve
- [ ] Add "Send Queue to Instantly" flow
- [ ] Test with real campaigns

**Deliverable:** Full staging workflow with review step

### Phase 3: Advanced (Optional, Week 3+)
**Estimated Time:** 8-12 hours

- [ ] Set up Instantly webhooks
- [ ] Build webhook listener endpoint
- [ ] Add campaign performance tracking
- [ ] Create "Hot Leads" dashboard widget
- [ ] Implement scheduled sends
- [ ] Add deduplication logic

**Deliverable:** Full bi-directional sync and advanced features

---

## 🔧 Technical Requirements

### API Access
- **Instantly API Key** (from Instantly dashboard)
- **Campaign IDs** for each tier
- **Webhook URL** (if doing bi-directional sync)

### Dependencies
```bash
pip install requests  # For API calls
pip install APScheduler  # For scheduled sends (Phase 3)
```

### Configuration
```python
# .env file
INSTANTLY_API_KEY=your_api_key
INSTANTLY_TIER_A_CAMPAIGN=camp_abc123
INSTANTLY_TIER_B_CAMPAIGN=camp_def456
INSTANTLY_WEBHOOK_SECRET=your_webhook_secret
```

---

## 📊 Success Metrics

### Phase 1 Success
- ✅ Send 100+ leads to Instantly with one click
- ✅ Zero CSV exports needed
- ✅ All leads tracked in database
- ✅ <1% error rate on sends

### Phase 2 Success
- ✅ Review queue used for 100% of sends
- ✅ Average approval time <5 minutes for 100 leads
- ✅ Zero duplicate sends
- ✅ Campaign routing accuracy 99%+

### Phase 3 Success
- ✅ Track open rates in dashboard
- ✅ "Hot leads" flagged within 1 hour of reply
- ✅ Scheduled sends running automatically
- ✅ Bounce rate <2%

---

## 🚫 What We're NOT Building (Avoiding Overbuild)

### Out of Scope
- ❌ Full CRM functionality (use Instantly for that)
- ❌ Email template management (Instantly handles this)
- ❌ A/B testing campaigns (Instantly feature)
- ❌ Custom email scheduling per lead (Instantly feature)
- ❌ Email warmup management (Instantly feature)
- ❌ Inbox rotation logic (Instantly feature)

### Why Not?
Instantly.ai is already excellent at these things. We're building a **connector**, not replacing Instantly. Our value-add is:
1. **Enrichment** (which Instantly doesn't do)
2. **Smart routing** (tier-based campaign assignment)
3. **Staging/review** (quality control before send)
4. **Tracking** (which leads were sent when)

---

## 🎯 Recommended Starting Point

### Minimum Viable Integration (4-6 hours)
Just Phase 1, but simplified:

```python
# Single endpoint, single campaign, no modal
@app.route('/api/instantly/send-tier-a', methods=['POST'])
def send_tier_a_to_instantly():
    """Send all Tier A leads to Premium campaign"""
    tier_a_leads = get_leads_by_tier('A')
    client = InstantlyClient(INSTANTLY_API_KEY)
    
    results = client.add_leads_batch(
        campaign_id=INSTANTLY_TIER_A_CAMPAIGN,
        leads=format_leads_for_instantly(tier_a_leads)
    )
    
    # Log to instantly_syncs table
    for lead, result in zip(tier_a_leads, results):
        log_instantly_sync(lead['id'], result)
    
    return jsonify(results)
```

**Test this first**, validate it works, then add UI, modal, campaign selection, etc.

---

## 💡 Best Practices

### 1. Start Small
- Send 5-10 test leads first
- Verify they appear in Instantly correctly
- Check field mapping is correct
- Then scale to 100, 500, 1000+

### 2. Error Handling
```python
try:
    result = client.add_lead_to_campaign(campaign_id, lead_data)
except InstantlyAPIError as e:
    # Log error, don't crash
    log_error(lead_id, str(e))
    # Maybe retry later
    add_to_retry_queue(lead_id)
```

### 3. Rate Limiting
- Instantly API has rate limits
- Batch sends (100 leads at a time)
- Add delays between large batches
- Use queue for async processing if sending 1000+

### 4. Data Privacy
- Don't log full email addresses in public logs
- Secure API keys (never commit to git)
- GDPR: Track consent status, allow opt-out

---

## 📚 Resources

### Instantly.ai API Docs
- [API Documentation](https://developer.instantly.ai/)
- [Authentication](https://developer.instantly.ai/authentication)
- [Add Leads to Campaign](https://developer.instantly.ai/campaigns/add-leads)
- [Webhooks](https://developer.instantly.ai/webhooks)

### Example Request
```bash
curl -X POST https://api.instantly.ai/api/v1/lead/add \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "campaign_id": "camp_abc123",
    "leads": [
      {
        "email": "john@nursery.com",
        "first_name": "John",
        "last_name": "Smith",
        "company_name": "ABC Nursery",
        "variables": {
          "business_type": "Garden Center",
          "city": "Austin",
          "tier": "A"
        }
      }
    ]
  }'
```

---

## ✅ Decision Points

### Before Starting
1. **Do we need staging area?** (Phase 2)
   - Yes if: You want to review/edit before sending
   - No if: You trust the enrichment, want fully automated

2. **Do we need bi-directional sync?** (Phase 3)
   - Yes if: You want to track opens/replies in pipeline
   - No if: You'll just use Instantly dashboard for stats

3. **Campaign strategy?**
   - Option A: One campaign, all leads mixed
   - Option B: Two campaigns (Tier A premium, Tier B standard)
   - Option C: Many campaigns (by tier, state, business type, etc.)

### My Recommendation
**Start with Phase 1 (MVP)** - 8 hours of work:
- Two campaigns (Tier A → Premium, Tier B → Standard)
- Auto-routing based on tier
- No staging area (just send)
- Track in database (no webhooks yet)

**Test for 1-2 weeks**, then decide if you need Phase 2/3.

---

## 🏁 Next Steps

1. **Get Instantly API Key**
   - Log into Instantly.ai
   - Go to Settings → API
   - Generate API key

2. **Get Campaign IDs**
   - Create two campaigns (or use existing)
   - Note the campaign IDs

3. **Set Up Dev Environment**
   - Add API key to `.env` file
   - Install dependencies

4. **Build & Test**
   - Create `instantly_client.py`
   - Test API connection with 1 lead
   - Build UI button
   - Test with 5-10 leads
   - Scale to production

Ready to start building! 🚀
