# Email Hunter Evaluation
*Analysis Date: 2026-01-27*

## Current State Analysis

### What's Working

| Metric | Value | Notes |
|--------|-------|-------|
| Total processed | 151 leads | Tier A+B batch |
| Emails found | 116 (76.8%) | Personal emails attached to leads |
| Pattern inference | 109 emails | 72% of total, all at 41% confidence |
| Scraped from text | 7 emails | 4.6% - underperforming |
| No email | 35 (23.2%) | 23 domains w/o MX + other failures |

**The pattern inference approach is doing the heavy lifting.** MX validation is working correctly to reject patterns for domains that can't receive email.

### What's NOT Working

1. **Name parsing bugs** - Couples/co-owners parsed incorrectly
2. **Scraping underperforms** - Only 7 emails from website text (should be more)
3. **No generic email fallback** - Field exists but isn't being populated
4. **Single confidence score** - All patterns at 41% regardless of quality

---

## Root Cause Analysis

### Why 23 Leads Got No Email (Actually 35 total failures)

Breakdown of failed leads:

| Cause | Count | Example | Recoverable? |
|-------|-------|---------|--------------|
| **No MX records** | ~20 | wiroses.com, philslawn.com | ❌ Domain can't receive email |
| **Single first name only** | 7 | "Al", "Phil", "Teri" | ⚠️ Try first-name-only patterns |
| **Couple w/o shared surname** | 5 | "Wayne and Michelle" | ⚠️ Try first-name patterns for each |
| **Mismatched website** | 3 | Business ≠ website domain | ❌ Wrong context |

**Key insight:** 12 leads (single names + couples) are recoverable with better pattern generation. The 20+ with no MX are truly unrecoverable without finding alternate email addresses.

### Why Scraping Only Found 7 Emails

Examined website_text for failed leads:

1. **No emails in text** - Many small businesses use contact forms, not published emails
2. **Obfuscated emails** - Found "jonein78 9 @centuryt el .net" (spaces in email) - regex misses these
3. **Instagram handles parsed as potential emails** - "@northwind_perennial" flagged incorrectly
4. **JavaScript-rendered emails** - Static scrape can't capture dynamically loaded content

**The 7 scraped emails are mostly Gmail addresses** (generic) - which shows we ARE finding emails, just not personal ones.

### Pattern Parsing Bugs Found

```python
# Current buggy parsing:
"Wayne and Michelle"      → wayne.michelle@domain.com  # ❌ Michelle = last name?
"Ben and Maddy"          → ben.maddy@domain.com       # ❌ Same bug
"Joe"                    → joe.joe@domain.com         # ❌ Duplicated name
"Bachhuber family"       → bachhuber.family@...       # ❌ "family" as last name
"a.k.a. ATTN: CYNTHIA"   → aka.descamps@...           # ❌ "aka" as first name
```

---

## Top 3 Improvement Levers (80/20)

### 1. Fix Name Parsing for Edge Cases
**What:** Update `normalize_name()` to handle:
- Single names → only generate first-name patterns (joe@, phil@)
- Couples without surname → try both first names separately
- "a.k.a. ATTN:" prefixes → strip them
- "family" suffix → strip it

**Expected Impact:** +5-10 recoverable emails (fixing 12 leads with parsing issues)

**Effort:** Low (2-3 hours) - modify `email_patterns.py` only

```python
# Proposed fix for single names:
if len(cleaned_words) == 1:
    first = cleaned_words[0].lower()
    # Only generate first-name patterns, not first.last
    return {'first': first, 'last': None, ...}

# In generate_email_patterns, skip patterns that need last name when last is None
```

### 2. Improve Email Extraction from Website Text
**What:** Enhance `_extract_emails_from_text()` to:
- Handle obfuscated emails with spaces: `john @ domain . com`
- Handle HTML entity encoding: `john&#64;domain.com`
- Look for `mailto:` links in raw HTML (not just text)
- Filter out social media handles (@ followed by no dot = not email)

**Expected Impact:** +3-5 emails (based on manual review of failed extractions)

**Effort:** Low-Medium (3-4 hours) - modify regex patterns

```python
# Improved regex to catch obfuscated emails:
patterns = [
    r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}',  # Standard
    r'[a-zA-Z0-9._%+-]+\s*@\s*[a-zA-Z0-9.-]+\s*\.\s*[a-zA-Z]{2,}',  # Spaced
    r'mailto:([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})',  # mailto links
]
```

### 3. Always Capture Generic Email as Fallback
**What:** Ensure `generic_email` and `contact_form_url` are ALWAYS stored when found, even if we find a personal email. Currently these fields are NULL for all 151 leads.

**Why:** A generic email (info@, sales@) is still useful for:
- Validation (send test, see if forwarded to owner)
- Fallback if personal email bounces
- Multi-touch campaigns

**Expected Impact:** +15-25 fallback emails available for leads with no personal email

**Effort:** Very Low (30 mins) - database update logic exists, just not executing

```python
# Fix in email_hunter.py - ensure generic email saved even when personal found:
if email_type == 'generic':
    result['generic_email'] = email  # Store it regardless
    # ... continue searching for personal email
```

---

## What NOT to Do Yet

### ❌ Add paid API verification (NeverBounce/ZeroBounce)
- Current patterns are MX-validated - adding API won't increase find rate
- At $0.003-0.01/email, 100+ leads = $0.30-1.00 with marginal improvement
- **Wait until:** You have a specific deliverability problem to solve

### ❌ Implement SMTP verification
- Many servers block/greylist verification attempts
- Risk of IP reputation damage
- High false negative rate

### ❌ Scrape contact pages dynamically (Puppeteer/Playwright)
- High complexity vs reward for 7 additional emails
- Many small nursery sites use contact forms, not emails
- **Wait until:** You've exhausted other free improvements

### ❌ Add Hunter.io/Apollo API lookups
- Costly at $0.02/lookup
- These B2B tools have poor coverage for small family nurseries
- **Wait until:** You've verified pattern emails are bouncing at high rates

---

## Quick Wins Summary

| Fix | Impact | Effort | Priority |
|-----|--------|--------|----------|
| Store generic emails as fallback | +15-25 leads | 30 min | 🔴 Do now |
| Fix single-name pattern bug | +7 leads | 1 hour | 🔴 Do now |
| Fix couple parsing bug | +5 leads | 2 hours | 🟡 Soon |
| Improve email regex | +3-5 leads | 3 hours | 🟡 Soon |

**Total recoverable with fixes: +30-40 additional emails** (from current 116 → ~146-156)

That would push Tier A+B email coverage from **76.8% → 95%+**

---

## Appendix: Sample Data Issues

### Pattern emails with bugs (sample):
```
wayne.michelle@kinninatives.com     # ❌ Wayne and Michelle
julie.kim@countylinemarket.com      # ❌ Julie & Kim  
joe.joe@joescountrycorner.com       # ❌ Joe (single name)
erik.danielle@millcreekgardencenter.com  # ❌ Erik and Danielle
bachhuber.family@lovefoodfarm.com   # ❌ Bachhuber family
```

### Domains without MX records (sample):
```
wiroses.com           # ❌ No email possible
anderagreenhouse.com  # ❌ No email possible
sweetwatercreekseeds.com  # ❌ No email possible
philslawn.com         # ❌ No email possible
```

### Website text with extractable emails we missed:
```
"jonein78 9 @centuryt el .net"  # ✓ Could extract with deobfuscation
```
