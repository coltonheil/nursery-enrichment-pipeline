# Phase 1 Setup Checklist
**Goal:** Complete Composio + Instantly.ai OAuth setup before Phase 1 implementation

---

## ✅ Prerequisites (DONE)

- [x] Composio SDK installed (`composio-core==0.7.21`)
- [x] Instantly API key saved to `.env`
- [x] InstantlyComposioClient wrapper created
- [x] Connection scripts created
- [x] Test scripts created

---

## 🔧 Setup Steps (TO DO)

### 1. Get Composio API Key

**Action:** Visit https://app.composio.dev/settings

**Steps:**
1. Create account (if needed)
2. Go to Settings → API Keys
3. Create new API key
4. Copy the key

**Add to `.env`:**
```bash
# Add this line to .env file
COMPOSIO_API_KEY=your_composio_key_here
```

---

### 2. Connect Instantly to Composio

**Run:**
```bash
cd ~/clawd/projects/nursery-enrichment-pipeline
source venv/bin/activate
python scripts/connect_instantly.py
```

**What it does:**
- Uses your Instantly API key (already in `.env`)
- Creates OAuth connection via Composio
- Saves `COMPOSIO_INSTANTLY_ACCOUNT_ID` to `.env`

**Expected output:**
```
✅ Connected successfully!
   Account ID: conn_abc123...
💾 Saved account ID to .env
```

---

### 3. Test the Connection

**Run:**
```bash
python scripts/test_instantly_connection.py
```

**What it checks:**
- Composio client initialization
- Account info fetch
- Campaign listing

**Expected output:**
```
✅ Found X campaigns:
   1. Campaign Name
      ID: camp_abc123
      Status: active

✅ Connection test PASSED!
🎯 Ready for Phase 1 implementation!
```

---

### 4. Create Test Campaign (Optional)

**Run:**
```bash
python scripts/create_test_campaign.py
```

**What it does:**
- Creates a test campaign in Instantly
- Adds a dummy lead
- Validates full write permissions

**Expected output:**
```
✅ Campaign created!
   ID: camp_test123
✅ Test lead added!
```

*(You can delete this test campaign afterward)*

---

## ✅ Verification Checklist

Before proceeding to Phase 1 implementation:

- [ ] `.env` contains `COMPOSIO_API_KEY`
- [ ] `.env` contains `COMPOSIO_INSTANTLY_ACCOUNT_ID`
- [ ] `test_instantly_connection.py` runs successfully
- [ ] Can list existing campaigns (or see "No campaigns yet")
- [ ] `InstantlyComposioClient` imports without errors
- [ ] (Optional) Test campaign created and test lead added

---

## 📁 Files Created

### Core Client
- `instantly_composio_client.py` - Main wrapper class (9.4 KB)

### Setup Scripts
- `scripts/connect_instantly.py` - OAuth connection setup (3 KB)
- `scripts/test_instantly_connection.py` - Connection validation (2.9 KB)
- `scripts/create_test_campaign.py` - Test campaign creation (2.8 KB)

### Documentation
- `COMPOSIO_INSTANTLY_SETUP.md` - Original setup guide
- `PHASE_1_SETUP_CHECKLIST.md` - This checklist

---

## 🚨 Troubleshooting

### Error: "COMPOSIO_API_KEY not found"
- Add your Composio API key to `.env`
- Get it from: https://app.composio.dev/settings

### Error: "Connection failed"
- Check that Instantly API key is valid
- Verify it's not base64-wrapped twice
- Try logging into Instantly.ai to confirm account is active

### Error: "Failed to list campaigns"
- Check Composio connection at: https://app.composio.dev/apps/instantly
- Verify account is connected
- Try disconnecting and reconnecting

### No campaigns listed
- This is fine if you haven't created any yet
- You'll create your first campaign in Phase 1

---

## 🎯 After Setup is Complete

**You're ready for Phase 1 when:**
1. All verification checklist items are checked
2. `test_instantly_connection.py` runs without errors
3. `.env` has all required keys

**Next step:**
- Move to Phase 1 implementation
- Create production campaign
- Export first batch of Tier A leads
- Test end-to-end flow

---

## 📞 Need Help?

**Composio docs:** https://docs.composio.dev/toolkits/instantly  
**Instantly API docs:** https://developer.instantly.ai  
**Our setup guide:** `COMPOSIO_INSTANTLY_SETUP.md`

---

*Checklist created: 2026-01-29*  
*Ready for Phase 1: [ TBD ]*
