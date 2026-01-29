# Instantly API V2 - Campaign Creation Notes

## Base URL
```
https://api.instantly.ai/api/v2/campaigns
```

## Authentication
Bearer token in Authorization header:
```
Authorization: Bearer <YOUR_INSTANTLY_API_KEY>
```

## Create Campaign Endpoint

**POST** `/api/v2/campaigns`

### Required Fields

```json
{
  "name": "Campaign Name",
  "campaign_schedule": {
    "schedules": [
      {
        "name": "Schedule Name",
        "timing": {
          "from": "09:00",
          "to": "17:00"
        },
        "days": {
          "0": false,  // Sunday
          "1": true,   // Monday
          "2": true,   // Tuesday
          "3": true,   // Wednesday
          "4": true,   // Thursday
          "5": true,   // Friday
          "6": false   // Saturday
        },
        "timezone": "America/Chicago"
      }
    ]
  }
}
```

### Optional But Important Fields

```json
{
  "daily_max_leads": 0,              // Set to 0 = paused (don't send)
  "stop_on_reply": true,             // Stop when lead replies
  "open_tracking": true,             // Track email opens
  "link_tracking": true,             // Track link clicks
  "stop_on_auto_reply": true,        // Stop on out-of-office
  "stop_for_company": false,         // Stop entire domain on reply
  "email_gap": 60,                   // Minutes between emails
  "random_wait_max": 120,            // Random delay (minutes)
  "text_only": false,                // Send as plain text
  "first_email_text_only": true,     // First email plain text (more personal)
  "daily_limit": null,               // Daily send limit per account
  "prioritize_new_leads": true,      // Send to new leads first
  "insert_unsubscribe_header": true, // Add unsubscribe header
  "sequences": []                    // Email sequence steps (see below)
}
```

### Timezone Options (relevant ones)
- `"America/Chicago"` - Central Time
- `"America/New_York"` - Eastern Time
- `"America/Los_Angeles"` - Pacific Time
- `"America/Denver"` - Mountain Time

### Campaign Status Values
- `0` = Draft
- `1` = Active
- `2` = Paused
- `3` = Completed
- `4` = Running Subsequences
- `-99` = Account Suspended
- `-1` = Accounts Unhealthy
- `-2` = Bounce Protect

## Email Sequences Structure

```json
{
  "sequences": [
    {
      "steps": [
        {
          "step_number": 1,
          "variants": [
            {
              "subject": "Email Subject Line",
              "body": "Email body with {{variables}}"
            }
          ],
          "wait_time_days": 0
        },
        {
          "step_number": 2,
          "variants": [
            {
              "subject": "Follow-up Subject",
              "body": "Follow-up email body"
            }
          ],
          "wait_time_days": 3
        }
      ]
    }
  ]
}
```

### Available Variables
- `{{first_name}}` - Lead's first name
- `{{last_name}}` - Lead's last name
- `{{company_name}}` - Company name
- `{{email}}` - Lead's email
- Custom variables you define

## Example Complete Request

```json
{
  "name": "Premium Nurseries - Worm Casting Samples",
  "campaign_schedule": {
    "schedules": [
      {
        "name": "Weekday Business Hours",
        "timing": {
          "from": "09:00",
          "to": "17:00"
        },
        "days": {
          "0": false,
          "1": true,
          "2": true,
          "3": true,
          "4": true,
          "5": true,
          "6": false
        },
        "timezone": "America/Chicago"
      }
    ]
  },
  "daily_max_leads": 0,
  "stop_on_reply": true,
  "open_tracking": true,
  "link_tracking": true,
  "stop_on_auto_reply": true,
  "first_email_text_only": true,
  "insert_unsubscribe_header": true,
  "sequences": [
    {
      "steps": [
        {
          "step_number": 1,
          "variants": [
            {
              "subject": "Free Worm Casting Sample for {{company_name}}?",
              "body": "Hi {{first_name}},\n\nI noticed {{company_name}} in {{city}} and thought you might be interested in trying our premium worm castings.\n\nWe're offering free samples to select nurseries. Would you be interested in receiving a sample to test with your plants?\n\nIf yes, just reply with your mailing address and I'll get a sample out to you this week.\n\nBest,\n[Your Name]"
            }
          ],
          "wait_time_days": 0
        },
        {
          "step_number": 2,
          "variants": [
            {
              "subject": "Re: Free sample for {{company_name}}",
              "body": "Hi {{first_name}},\n\nJust wanted to follow up - would you like a free sample of our worm castings?\n\nNo strings attached, just want to get feedback from quality nurseries like {{company_name}}.\n\nLet me know your mailing address and I'll send one out.\n\nThanks,\n[Your Name]"
            }
          ],
          "wait_time_days": 3
        }
      ]
    }
  ]
}
```

## Response Format

```json
{
  "id": "019bd5b4-7fcb-7c7e-82f1-6d189f9fe7f0",
  "name": "Campaign Name",
  "status": 2,
  "campaign_schedule": {...},
  "sequences": [...],
  "timestamp_created": "2026-01-19T10:02:14.859Z",
  "timestamp_updated": "2026-01-19T10:02:14.859Z",
  ...
}
```

## Implementation Notes

1. **Use Instantly API V2 directly** (not Composio) for campaign creation
   - Composio SDK has bugs with nested objects
   - Direct HTTP POST to `https://api.instantly.ai/api/v2/campaigns` works perfectly

2. **Paused campaigns**: Set `daily_max_leads: 0` to prevent sending during warmup

3. **Email copy**: Store templates in code or allow user to customize via UI

4. **Variables**: Use snake_case custom variables (e.g., `{{business_type}}`, `{{tier}}`)

5. **Sequences**: Even though it's an array, only first element is used

6. **Timezone**: Always specify explicitly (don't rely on defaults)

## Testing

Use the Instantly API directly with curl:
```bash
curl -X POST https://api.instantly.ai/api/v2/campaigns \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{...}'
```
