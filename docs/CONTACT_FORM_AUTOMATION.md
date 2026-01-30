# Contact Form Automation System

Automated contact form submission system for reaching leads without email addresses.

## Overview

This system automates the process of submitting personalized messages through contact forms on nursery/greenhouse websites. It uses Playwright with stealth settings to simulate human-like behavior and avoid bot detection.

## Features

- **Human-like Behavior**: Variable typing speed, occasional typos with corrections, natural mouse movements
- **Form Detection**: Auto-detects field types (name, email, phone, message, etc.)
- **CAPTCHA Detection**: Identifies protected forms and routes to manual queue
- **Template System**: 3 message variants with A/B tracking
- **Rate Limiting**: Business hours only, random intervals, daily limits
- **Resume Capability**: Tracks progress, can resume interrupted campaigns
- **Screenshot Capture**: Before/after screenshots for verification

## Installation

```bash
# Install Python dependencies
pip install playwright playwright-stealth

# Install browser
playwright install chromium
```

## Quick Start

### Check Campaign Status
```bash
cd ~/clawd/projects/nursery-enrichment-pipeline
python scripts/run_form_campaign.py --status
```

### Test Single Submission (Dry Run)
```bash
python scripts/run_form_campaign.py --single --dry-run
```

### Run Batch of Submissions
```bash
# Submit 5 forms
python scripts/run_form_campaign.py --batch 5

# Dry run (fill but don't submit)
python scripts/run_form_campaign.py --batch 5 --dry-run
```

### Run Continuous Campaign
```bash
# Will run during business hours, pause overnight
python scripts/run_form_campaign.py --continuous
```

## Configuration

### Rate Limits
- **Daily submissions**: 30-40 (configurable)
- **Interval between submissions**: 30-90 minutes (random)
- **Business hours**: 8 AM - 6 PM Central Time
- **Work days**: Monday - Friday

### Message Templates

Located in `templates/contact_form/`:

1. **Template A** (`template_a.txt`): Direct offer approach
   - Best for: Wholesale operations
   
2. **Template B** (`template_b.txt`): Problem-solution approach
   - Best for: Operations with known crops
   
3. **Template C** (`template_c.txt`): Regional/local angle
   - Best for: Default/general use

Templates support variables:
- `{{business_name}}` - Company name
- `{{city}}` - City
- `{{state}}` - State abbreviation
- `{{tracking_id}}` - Unique tracking ID (e.g., REF-A042)

### Reply Email
All submissions use: `colton@sweetleafsoil.com`

Tracking IDs in messages (e.g., `[REF-A042]`) allow matching replies to specific leads.

## Scripts Reference

### `run_form_campaign.py` - Main Runner

```bash
# Options
--status          Show campaign status
--single          Process one lead
--lead-id ID      Process specific lead
--batch N         Process N leads
--continuous      Run continuously
--dry-run         Fill forms but don't submit
--headless        Run browser invisibly
--daily-min N     Minimum daily submissions (default: 30)
--daily-max N     Maximum daily submissions (default: 40)
```

### `manual_queue.py` - Handle Failed Forms

```bash
# List forms needing manual review
python scripts/manual_queue.py --list

# List failed submissions
python scripts/manual_queue.py --list-failed

# Skip a lead
python scripts/manual_queue.py --skip 123 --reason "No form found"

# Reset lead to pending
python scripts/manual_queue.py --reset 123

# Create custom field mapping
python scripts/manual_queue.py --map 123

# Retry with saved mapping
python scripts/manual_queue.py --retry 123 --dry-run

# Bulk reset all failed
python scripts/manual_queue.py --bulk-reset failed
```

### `form_detector.py` - Form Analysis

Automatically detects:
- Field types (name, email, phone, company, subject, message)
- Form builders (Wix, Squarespace, WordPress, etc.)
- CAPTCHA protection (reCAPTCHA, hCaptcha, Turnstile)
- Honeypot fields (to leave empty)

### `human_behavior.py` - Behavior Simulation

Simulates human patterns:
- **Typing**: 80-150ms per character with variance
- **Typos**: 10% of fields get a typo that's corrected
- **Mouse**: Bezier curves, not straight lines
- **Scrolling**: Variable speed, pauses to "read"
- **Delays**: Different timing for different field types

## Database Schema

The system tracks submissions in the `leads` table:

```sql
-- Existing columns used
contact_form_url TEXT    -- URL of the contact form
has_contact_form BOOLEAN -- Whether lead has a form

-- New columns added
form_template_variant TEXT      -- 'A', 'B', or 'C'
form_submitted_at TIMESTAMP     -- When submission was made
form_submission_status TEXT     -- pending/submitted/failed/manual_review/skipped
form_tracking_id TEXT           -- e.g., 'REF-A042'
form_error TEXT                 -- Error message if failed
```

### Status Values
- `pending` - Not yet processed
- `submitted` - Successfully submitted
- `failed` - Submission failed
- `manual_review` - Needs human intervention (CAPTCHA, etc.)
- `skipped` - Manually marked to skip
- `dry_run` - Tested but not submitted

## Workflow

### Daily Operation

1. **Morning (8-9 AM)**
   - Check reply inbox for overnight responses
   - Review manual queue from yesterday
   - Start campaign: `python scripts/run_form_campaign.py --continuous`

2. **Midday Check**
   - Monitor progress (~15-20 submissions by noon)
   - Handle any manual queue items

3. **End of Day (5-6 PM)**
   - Campaign auto-pauses after business hours
   - Review day's submissions in database
   - Check for replies

### Manual Queue Handling

When a form can't be auto-submitted (CAPTCHA, unusual structure):

1. View the queue: `python scripts/manual_queue.py --list`
2. Open the URL in browser, inspect the form
3. Either:
   - Create custom field mapping: `--map ID`
   - Skip if no form: `--skip ID --reason "reason"`
4. Retry with mapping: `--retry ID`

## Files and Directories

```
nursery-enrichment-pipeline/
├── scripts/
│   ├── form_detector.py      # Form field detection
│   ├── form_submitter.py     # Main submission engine
│   ├── human_behavior.py     # Human-like behavior patterns
│   ├── run_form_campaign.py  # Campaign runner CLI
│   └── manual_queue.py       # Manual review queue CLI
├── templates/
│   └── contact_form/
│       ├── template_a.txt    # Direct offer template
│       ├── template_b.txt    # Problem-solution template
│       └── template_c.txt    # Regional angle template
├── data/
│   ├── leads.db              # SQLite database
│   ├── form_screenshots/     # Submission screenshots
│   └── form_mappings.json    # Custom field mappings
├── logs/
│   └── form_campaign.log     # Campaign activity log
└── docs/
    └── CONTACT_FORM_AUTOMATION.md  # This file
```

## Safety Features

1. **Never submits without verification** - Form must be detected correctly
2. **Rate limiting** - Conservative pace to avoid detection
3. **Business hours only** - Submits when humans would
4. **Screenshot capture** - Visual proof of submissions
5. **Dry-run mode** - Test without submitting
6. **Manual queue** - Problematic forms get human review
7. **Honeypot detection** - Avoids bot traps

## Troubleshooting

### Form not detected correctly
1. Use `--dry-run` to see what's detected
2. Check screenshot in `data/form_screenshots/`
3. Create custom mapping: `python scripts/manual_queue.py --map ID`

### CAPTCHA blocking
1. Form goes to manual queue automatically
2. Review manually: open URL, solve CAPTCHA
3. Create mapping and retry, or skip

### Rate limited by website
1. Campaign automatically slows down
2. Check logs for error messages
3. May need to skip site

### Browser crashes
1. Campaign can resume - progress is tracked
2. Run `--status` to see current state
3. Resume with `--continuous`

## Expected Results

- **Success rate**: 85-90% auto-submission
- **Manual review**: 10-15% of forms
- **Response rate**: 5-15% (historical average)
- **Timeline**: ~1 week for 221 leads at 30-40/day
