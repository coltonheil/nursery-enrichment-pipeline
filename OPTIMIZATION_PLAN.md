# Email Hunter Optimization Plan
**Date:** 2026-01-27  
**Status:** Implementation Ready

---

## Executive Summary

**Current Performance:**
- 76.8% email find rate (116/151 leads)
- All emails from pattern inference (109) or scraping (7)
- 35 failures: 23 no-MX domains, 12 name parsing bugs

**Target After Optimization:**
- 90%+ email find rate
- 3-layer fallback: Pattern → Brave Search → Generic
- Fix all 12 recoverable leads

---

## Three-Layer Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                EMAIL HUNTER PIPELINE (v2)                   │
└─────────────────────────────────────────────────────────────┘

Layer 1: Pattern Inference + MX Validation
├─ Parse name (improved edge case handling)
├─ Generate email patterns
├─ Validate MX records
└─ Result: 70-80% find rate (CURRENT)

        ↓ (if no email found)

Layer 2: Brave Search Fallback  
├─ Search: "{name}" "{business}" email contact
├─ Extract emails from snippets
├─ Prioritize domain-matching emails
└─ Result: +10-15% additional finds (NEW)

        ↓ (if still no email)

Layer 3: Generic Email Fallback
├─ Store info@domain, contact@domain
├─ Flag as generic (low confidence)
└─ Result: 100% coverage for valid domains (NEW)
```

---

## Phase 1: Fix Name Parsing Bugs (HIGHEST PRIORITY)

### Problem
Pattern generator fails on:
- Single names: "Joe" → joe.joe@domain ❌
- Couples: "Wayne and Michelle" → wayne.michelle@ ❌
- Prefixes: "a.k.a. ATTN: CYNTHIA" → aka.descamps@ ❌

### Solution
Update `enrichment/email_patterns.py`:

```python
def normalize_name(name: str) -> Dict[str, str]:
    """Parse name with edge case handling."""
    
    # Remove noise
    noise_patterns = [
        r'\ba\.k\.a\.\s*',  # "a.k.a."
        r'\bATTN:\s*',      # "ATTN:"
        r'\bfamily\b',      # "family"
    ]
    for pattern in noise_patterns:
        name = re.sub(pattern, '', name, flags=re.IGNORECASE)
    
    # Handle couples: "Wayne and Michelle" → try "Wayne"
    if ' and ' in name.lower():
        parts = re.split(r'\s+and\s+', name, flags=re.IGNORECASE)
        name = parts[0].strip()  # Use first name only
    
    # Split and clean
    words = name.strip().split()
    words = [w for w in words if w.lower() not in ['mr', 'mrs', 'ms', 'dr', 'jr', 'sr']]
    
    # Single name handling
    if len(words) == 1:
        return {
            'first': words[0].lower(),
            'last': None,  # Signal: only generate first-name patterns
            'f': words[0][0].lower(),
            'l': None
        }
    
    # Normal two+ name handling
    first = words[0].lower()
    last = words[-1].lower()
    
    return {
        'first': first,
        'last': last,
        'f': first[0],
        'l': last[0]
    }
```

**Impact:** Fixes 12 recoverable leads (+8% find rate)

---

## Phase 2: Integrate Brave Search Fallback

### Current State
`enrichment/email_web_search.py` exists but isn't called in main pipeline

### Integration Points

#### Update 1: email_hunter.py
Enable Brave search by default when pattern fails:

```python
def hunt_email(
    owner_name: str,
    business_name: str,
    website: Optional[str] = None,
    enable_web_search: bool = True,  # ← Change default to True
    verify_mx: bool = True
) -> EmailHuntResult:
    # ... existing pattern logic ...
    
    # If no email from patterns AND domain is valid, try Brave
    if not result.email and result.domain_valid:
        result = _hunt_via_web_search(owner_name, business_name, result)
    
    # If STILL no email (no MX or search failed), add generic fallback
    if not result.email and domain:
        result.email = f"info@{domain}"
        result.confidence = 20
        result.method = 'generic_fallback'
    
    return result
```

#### Update 2: Check Brave API Key
Validate config before running pipeline:

```bash
# Check if Brave API key exists
grep BRAVE_API_KEY projects/nursery-enrichment-pipeline/.env
```

If missing, get free tier key: https://brave.com/search/api/

**Free tier:** 2,000 searches/month (enough for 2K leads)

---

## Phase 3: Always Store Generic Email

### Problem
Database has `generic_email` column but it's never populated

### Solution
Update email hunter to ALWAYS store generic email as fallback:

```python
def hunt_email(...):
    # ... after domain extraction ...
    
    # Always store generic email for valid domains
    if domain and result.domain_valid:
        result.generic_email = f"info@{domain}"
        result.contact_form = f"https://{domain}/contact"  # Assumption
    
    # Continue with pattern inference...
    # If pattern found, primary email = pattern, generic stays as backup
    # If pattern NOT found, try Brave search
    # If search fails, fall back to generic as primary
```

**Impact:** 100% email coverage for all valid domains

---

## Phase 4: Improve Email Extraction Regex

### Problem
Scraper misses obfuscated emails:
- "jonein78 9 @centuryt el .net" (spaces)
- HTML entities: `john&#64;domain.com`

### Solution
Update `enrichment/email_web_search.py`:

```python
def extract_emails_from_text(text: str, target_domain: Optional[str] = None) -> List[str]:
    """Extract with obfuscation handling."""
    
    # Standard regex
    emails = EMAIL_PATTERN.findall(text)
    
    # Deobfuscate spaced emails: "user @ domain . com"
    spaced_pattern = r'([a-zA-Z0-9._%+-]+)\s*@\s*([a-zA-Z0-9.-]+)\s*\.\s*([a-zA-Z]{2,})'
    for match in re.finditer(spaced_pattern, text):
        email = f"{match.group(1)}@{match.group(2)}.{match.group(3)}"
        emails.append(email.replace(' ', ''))
    
    # Decode HTML entities
    text = text.replace('&#64;', '@').replace('&#46;', '.')
    emails.extend(EMAIL_PATTERN.findall(text))
    
    # Rest of existing filtering...
```

**Impact:** +3-5 additional emails from scraping

---

## Implementation Order

### Week 1: Critical Fixes
1. ✅ Fix name parsing bugs (2 hours)
2. ✅ Enable generic email fallback (30 mins)
3. ✅ Test on 10 failed leads

### Week 2: Brave Integration
4. ✅ Get Brave API key (5 mins)
5. ✅ Test web search on 5 no-MX leads
6. ✅ Integrate into pipeline (1 hour)
7. ✅ Test full pipeline on 20 mixed leads

### Week 3: Polish
8. ✅ Improve email regex (2 hours)
9. ✅ Add confidence boosting logic
10. ✅ Re-run pipeline on all 9K leads

---

## Testing Strategy

### Unit Tests
```bash
cd projects/nursery-enrichment-pipeline
python -m pytest enrichment/tests/test_email_patterns.py
python -m pytest enrichment/tests/test_email_hunter.py
```

### Integration Test
Run on 50 previously failed leads:
```python
# Test script
failed_leads = get_leads_with_no_email()[:50]
results = hunt_emails_batch(failed_leads, enable_web_search=True)
print(summarize_results(results))
```

### Success Criteria
- [ ] Find rate increases from 76.8% → 90%+
- [ ] No false positives (invalid email formats)
- [ ] Brave search costs <$5 for 1000 leads
- [ ] Generic fallback available for all valid domains

---

## Cost Projections

### Current (Pattern Only)
- $0.00/lead (free MX validation)

### With Brave Search (2000/month free)
- Brave API: $0.00 for first 2K searches/month
- After 2K: ~$0.005/search
- Expected usage: 10-20% of leads need search
- **Cost for 1000 leads:** ~$0.50-1.00/month

### ROI
At $5-50 potential value per lead, adding 10% more emails = +100 leads × $5 = **$500 value for $1 cost**

---

## Next Steps

**User Decision Points:**
1. ✅ Get Brave API key from https://brave.com/search/api/
2. ✅ Choose test batch: re-run failed 151 leads OR run fresh 500?
3. ✅ Set email confidence threshold for export (recommend: 50%+)

**Agent Actions:**
1. Implement name parsing fixes
2. Integrate Brave search
3. Add generic email fallback
4. Test on sample batch
5. Report results

---

**Ready to implement?** Say "go" and I'll start with Phase 1 (name parsing fixes).
