# 5K Lead Run - Goal KPIs
**Date:** 2026-01-27  
**Batch Size:** 5,000 leads  
**Optimizations:** Email Hunter v2 with 3-layer fallback

---

## 🎯 Goal KPIs (Targets)

### Primary KPIs (Success Metrics)

| Metric | Target | Stretch Goal | Baseline (Current) |
|--------|--------|--------------|-------------------|
| **Tier A Count** | 105+ | 125+ | 191 (2.1% of 9K) |
| **Tier B Count** | 255+ | 300+ | 465 (5.1% of 9K) |
| **High-Value (A+B)** | 360+ | 425+ | 656 (7.2% of 9K) |
| **A+B Email Coverage** | 85% | 90%+ | 76.8% (before opt) |
| **Personal Email Rate** | 305+ A+B leads | 360+ | ~250 estimated |

### Secondary KPIs (Quality Metrics)

| Metric | Target | Notes |
|--------|--------|-------|
| **Pattern Inference Rate** | 70%+ | % of emails from pattern (not generic) |
| **Brave Search Contribution** | 5-10% | Additional emails found via Brave |
| **Generic Fallback Usage** | 100% | All valid domains covered |
| **Pipeline Completion Rate** | 95%+ | % of leads fully processed |
| **Enrichment Success Rate** | 90%+ | % with Google Places + Gemini data |

### Efficiency KPIs (Performance Metrics)

| Metric | Target | Notes |
|--------|--------|-------|
| **Processing Speed** | 12-20 leads/min | Average throughput |
| **Total Time** | 4-6 hours | For 5,000 leads |
| **API Cost** | $60-70 | Google Places + Gemini + Brave |
| **Failed Lead Rate** | <5% | Leads that error out |

---

## 📊 Checkpoint Schedule (Every 500 Leads)

**Checkpoints:** 500, 1000, 1500, 2000, 2500, 3000, 3500, 4000, 4500, 5000

**Report at each checkpoint:**
1. **Progress:** Leads processed, time elapsed, ETA
2. **Tiers:** A/B/C/U counts and percentages
3. **Emails:** Total with email, confidence breakdown, method breakdown
4. **vs KPIs:** On track / behind / ahead
5. **Issues:** Errors, failures, bottlenecks

---

## 🎨 Success Criteria

**Minimum Success:**
- ✅ 350+ Tier A+B leads (7% rate)
- ✅ 80%+ email coverage on A+B
- ✅ 90%+ pipeline completion rate
- ✅ <6 hours total time

**Target Success:**
- ✅ 360+ Tier A+B leads (7.2% rate)
- ✅ 85%+ email coverage on A+B
- ✅ 95%+ pipeline completion rate
- ✅ <5 hours total time

**Stretch Success:**
- ✅ 425+ Tier A+B leads (8.5% rate)
- ✅ 90%+ email coverage on A+B
- ✅ 98%+ pipeline completion rate
- ✅ <4 hours total time

---

## 📈 Tracking Metrics

### Tier Distribution (Cumulative)

Track at each checkpoint:
- Count of A, B, C, U
- Percentage of total processed
- Compare to baseline (2.1% A, 5.1% B)

### Email Coverage (Cumulative)

Track at each checkpoint:
- Total with personal email
- Total with generic fallback
- Email confidence distribution (70%+, 40-70%, <40%)
- Method breakdown (pattern, Brave, generic)

### Pipeline Health (Real-Time)

Monitor continuously:
- Current step and progress
- Errors per stage
- API rate limit warnings
- Processing speed (leads/min)

---

## 🚨 Alert Thresholds

**Trigger immediate alert if:**
- Tier A+B rate drops below 6% (300 leads at 5K)
- Email coverage drops below 75%
- Pipeline completion rate below 85%
- Processing speed below 10 leads/min
- API errors > 10% of requests

---

## 📝 Example Checkpoint Report

```
═══════════════════════════════════════════════════════════════
CHECKPOINT: 1,000 LEADS PROCESSED
Time: 45 minutes | ETA: 3h 15m remaining
═══════════════════════════════════════════════════════════════

TIER DISTRIBUTION:
  Tier A:    21 (2.1%) | Target: 2.1% ✅ ON TRACK
  Tier B:    53 (5.3%) | Target: 5.1% ✅ AHEAD
  Tier C:   107 (10.7%)
  Tier U:   819 (81.9%)
  High-Value: 74 (7.4%) | Target: 7.2% ✅ AHEAD

EMAIL COVERAGE:
  With Personal Email: 63/74 A+B (85%) | Target: 85% ✅ ON TRACK
  Pattern Inference: 58 (78% of found)
  Brave Search: 3 (4% of found)
  Generic Fallback: 74 (100%)
  Avg Confidence: 72%

PIPELINE HEALTH:
  Enrichment Success: 947/1000 (94.7%) ✅
  Failed Leads: 53 (5.3%) ✅
  Processing Speed: 22 leads/min ✅
  Current Step: ai_enrichment

ISSUES:
  - 32 domains with no MX records (expected)
  - 21 scraping timeouts (within limits)
  - 0 critical errors

STATUS: ✅ ALL KPIS ON TRACK
═══════════════════════════════════════════════════════════════
```

---

## 🎯 Final Report (At 5,000 Leads)

**Include:**
1. Total tier distribution vs targets
2. Email coverage vs target (85%+)
3. Cost breakdown (actual vs budget)
4. Time elapsed (actual vs target)
5. Top 10 highest-scoring leads preview
6. Recommendations for next steps

---

**Ready to start monitoring!** 🚀
