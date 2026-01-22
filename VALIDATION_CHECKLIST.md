# Pre-Launch Validation Checklist - Phase 10

This checklist ensures the nursery enrichment pipeline is production-ready before processing real leads.

## Scoring Accuracy

### ICP Qualification
- [ ] Primary ICP leads (container/greenhouse production) correctly identified
- [ ] Secondary ICP leads (wholesalers/retailers) correctly identified
- [ ] Tertiary ICP leads (organic field farms) correctly identified
- [ ] Disqualified leads (landscapers, lawn care, retail-only) correctly filtered

### Tier Distribution
- [ ] Pull 20 random Tier A leads - manually review, target 85%+ accuracy
- [ ] Pull 20 random Tier B leads - verify they meet qualification criteria
- [ ] Pull 20 random Tier C leads - confirm they are low priority but not disqualified
- [ ] Pull 20 random Tier U leads - confirm they are truly disqualified
- [ ] Verify all 23 sample requesters would score Tier A or B

### Geographic Scoring
- [ ] Wisconsin leads get +25 bonus (local)
- [ ] Regional states (IL, MN, IA, MI) get +20 bonus
- [ ] Near states (IN, OH, MO, NE, KY) get +10 bonus
- [ ] Mid-distance states get 0 (neutral)
- [ ] Far states (TX, CA, FL, WA, OR) get -5 penalty
- [ ] Spot-check 5 leads per tier for correct geo scoring

## Pipeline Functionality

### Full Pipeline Execution
- [ ] Full pipeline completes without errors on 10 test leads
- [ ] Full pipeline completes without errors on 50 production leads
- [ ] All 4 steps execute in order (Google Places → Scrape → AI → Score)
- [ ] Progress tracking updates correctly throughout execution

### Error Handling
- [ ] Failed leads marked correctly in database
- [ ] Error messages logged to pipeline_runs table
- [ ] Retry logic triggers on transient failures (3 attempts with exponential backoff)
- [ ] Pipeline continues after individual lead failures
- [ ] Stop functionality works correctly

### Resume Capability
- [ ] Pipeline runs tracked in pipeline_runs table
- [ ] Status updates correctly (running/completed/failed/stopped)
- [ ] Completed/failed lead counts accurate
- [ ] Error logs persisted for debugging

## Frontend - Lead Cards

### Display & Layout
- [ ] Lead cards render correctly in card view
- [ ] Score breakdown displays all signals with correct points
- [ ] Tier badge shows correct color (green=A, blue=B, orange=C, gray=U)
- [ ] ICP badge shows correct type and color
- [ ] Geographic score displays correctly
- [ ] Top 6 signals shown with checkmarks/crosses

### Interactivity
- [ ] "Mark Reviewed" button works and persists state
- [ ] "Full Details" button opens modal with complete lead info
- [ ] "Website" button opens business website in new tab
- [ ] "Maps" button opens Google Maps location
- [ ] View toggle switches between table and card view
- [ ] View preference persists in localStorage

## Frontend - Keyboard Shortcuts (Phase 7)

### Navigation
- [ ] Press `j` to move to next lead
- [ ] Press `k` to move to previous lead
- [ ] Current lead highlighted with blue border
- [ ] Scrolls lead into view automatically

### Actions
- [ ] Press `a` to set tier A (with visual feedback)
- [ ] Press `b` to set tier B
- [ ] Press `c` to set tier C
- [ ] Press `u` to set tier U
- [ ] Press `r` to mark as reviewed
- [ ] Press `x` to toggle selection
- [ ] Press `o` to open website
- [ ] Press `?` to show help dialog

### Feedback
- [ ] Toast notifications appear for all actions
- [ ] Tier badge updates immediately after tier change
- [ ] Card styling updates after tier override
- [ ] Auto-advance to next lead after tier assignment
- [ ] Keyboard shortcuts hint visible at bottom left

## Frontend - Dashboard (Phase 8)

### Stats Display
- [ ] Pipeline progress shows all 6 stages with percentages
- [ ] Tier distribution bar chart renders correctly
- [ ] ICP type distribution shows all 4 types
- [ ] Geographic distribution table shows top 10 states
- [ ] Top 10 positive signals list populated
- [ ] All stats match actual database counts

### Performance
- [ ] Dashboard loads in <2 seconds
- [ ] No console errors on page load
- [ ] Charts animate smoothly on render

### Responsive Design
- [ ] Dashboard looks good on desktop (1920x1080)
- [ ] Dashboard looks good on tablet (768px)
- [ ] Dashboard looks good on mobile (375px)

## Export Functionality

### Instantly.ai CSV Format
- [ ] Export includes all required columns
- [ ] Email column populated for leads with email
- [ ] FirstName extracted from owner_name or business_name
- [ ] Company populated correctly
- [ ] City, State populated correctly
- [ ] CustomLine (personalized opener) included
- [ ] Tier visible in export metadata

### Filters
- [ ] Tier filter works (A only, A+B, all tiers)
- [ ] Email required filter works
- [ ] Reviewed status filter works
- [ ] Export file naming includes timestamp
- [ ] Export logged to exports table

## Performance Benchmarks

### Load Times
- [ ] Leads list page loads in <2 seconds (for 100 leads)
- [ ] Dashboard loads in <2 seconds
- [ ] Lead card modal opens in <500ms
- [ ] Export generates in <5 seconds (for 500 leads)

### Processing Speed
- [ ] Google Places enrichment: <3 seconds per lead
- [ ] Website scraping: <5 seconds per lead
- [ ] AI enrichment: <10 seconds per lead
- [ ] Scoring: <100ms per lead
- [ ] Full pipeline: <20 seconds per lead average

## Database Integrity

### Schema Validation
- [ ] All Phase 1-9 columns exist in leads table
- [ ] pipeline_runs table exists with correct schema
- [ ] processing_log table exists
- [ ] exports table exists
- [ ] All indexes created correctly

### Data Quality
- [ ] No NULL values in required fields (id, business_name, imported_at)
- [ ] All enriched leads have gemini_status = 'enriched'
- [ ] All scored leads have non-null score and tier
- [ ] tier_override takes precedence over calculated tier
- [ ] JSON fields (score_breakdown, scale_indicators, crops_grown) parse correctly

## Security & Environment

### Environment Variables
- [ ] GOOGLE_API_KEY loaded correctly
- [ ] GEMINI_API_KEY loaded correctly
- [ ] .env file in .gitignore
- [ ] No API keys hardcoded in source

### Data Privacy
- [ ] No sensitive data logged to console
- [ ] No PII exposed in error messages
- [ ] Database file excluded from git (.gitignore)

## Automated Tests (Phase 10)

### Test Suite Execution
- [ ] `pytest tests/test_scoring.py` passes all tests
- [ ] `pytest tests/test_geo.py` passes all tests
- [ ] No import errors or dependency issues
- [ ] All test classes execute successfully

### Coverage
- [ ] ICP qualification logic covered
- [ ] Scoring logic covered
- [ ] Geographic scoring covered
- [ ] State normalization covered
- [ ] Address extraction covered

## Documentation

### User Documentation
- [ ] README.md up to date with quick start
- [ ] CLAUDE.md has architecture overview
- [ ] Environment setup instructions clear
- [ ] Common commands documented

### Code Documentation
- [ ] Critical functions have docstrings
- [ ] Phase numbers documented in code comments
- [ ] Complex logic explained in comments
- [ ] Git commits describe changes clearly

## Final Checks

- [ ] All 10 phases completed and committed
- [ ] Git history shows progression through phases
- [ ] No uncommitted changes or WIP code
- [ ] Application starts without errors
- [ ] Can process 10 test leads end-to-end successfully

---

**Date Completed:** _________________

**Validated By:** _________________

**Notes:**
