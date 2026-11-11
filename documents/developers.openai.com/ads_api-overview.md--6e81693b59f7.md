# Overview

> For the complete documentation index, see [llms.txt](/llms.txt). Markdown versions of documentation pages are available by appending `.md` to the page URL.

Use the Advertiser API to create and manage campaigns, ad groups, ads, product feeds, conversion tracking, and reporting in your own application or for automating workflows.




## Getting Started

You will need an [ad account](https://ads.openai.com/) and an Advertiser API key. You can create your Advertiser API key within the [Settings page](https://ads.openai.com/settings) in Ads Manager. Store API keys securely on your server.

Examples throughout this guide will use a placeholder for the Advertiser API key and sample IDs such as `cmpn_123`, `adgrp_123`, and `ad_123` in requests. Replace these placeholders with real values returned by your requests.

API partners can follow [API Partner Setup](https://developers.openai.com/ads/api-partner-setup). For another end-to-end example, see the [Quickstart](https://developers.openai.com/ads/api-quickstart).

Use [Audit Logs](https://developers.openai.com/ads/api-reference/audit-logs) to review recorded changes to
resources in your ad account.

### Request conventions

Use the following base URL for API requests. Provide your API key in the Authorization header when making requests.

| Convention     | What to use                  |
| -------------- | ---------------------------- |
| Base URL       | `https://api.ads.openai.com` |
| Authentication | `Authorization: Bearer …`    |

On supported create endpoints, you may send an `Idempotency-Key`. Reuse that key and the same request when retrying the same creation; use a new key for a new resource. This prevents a network retry from creating a duplicate.

### Verify your API key

Retrieve your ad account to verify the key:

```bash
curl -G "https://api.ads.openai.com/v1/ad_account" \
  -H "Authorization: Bearer ${OPENAI_ADS_API_KEY}"
```

Confirm that the response contains information about your account. Inspect the currency, timezone, account status, and reviews before creating a campaign. An account marked `active` may still have an outstanding review.

### Next steps

Read through the [Campaign Structure](#campaign-structure) section and then follow the steps in [Your First Campaign](#your-first-campaign).






## Campaign Structure

An ad account contains campaigns. Each campaign contains ad groups, and each ad group contains ads. Configure each setting at the level that owns it. Use separate campaigns when you need separate budgets, objectives, or targeting. Use ad groups for different bid configurations, context hints, or product selections. Keep related creative variations together where those settings are shared.

```text
Ad account
└── Campaign
    └── Ad group
        └── Ad
```

| Level      | What you configure                                                                                                  | Example                       |
| ---------- | ------------------------------------------------------------------------------------------------------------------- | ----------------------------- |
| Ad account | Advertiser branding, currency, timezone, account access, spend limits                                               | Acme's US advertising account |
| Campaign   | Objective, budget, schedule, geographic and platform targeting, audience inclusion and exclusion, conversion events | US spring sales               |
| Ad group   | Bid strategy, context hints, audience bid multipliers, product set                                                  | Trail running products        |
| Ad         | Creative, image or product template, destination URL                                                                | A running-shoe ad             |

## Your First Campaign

Let's create a paused campaign, an ad group, and an ad. This example creates a clicks campaign with a fixed bid. The budget and bid are illustrative USD amounts. Use values appropriate to your account's currency and your advertising plan.

### 1. Create the campaign

```bash
curl -X POST "https://api.ads.openai.com/v1/campaigns" \
  -H "Authorization: Bearer ${OPENAI_ADS_API_KEY}" \
  -H "Idempotency-Key: first-campaign-001" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Spring launch",
    "status": "paused",
    "bidding_type": "clicks",
    "budget": {
      "daily_spend_limit_micros": 50000000
    },
    "targeting": {
      "locations": {
        "countries": [
          "US"
        ]
      }
    }
  }'
```

Save the returned `id`. Use it in place of `cmpn_123` below. The example daily budget is $50 for a USD account.

### 2. Create the ad group

```bash
curl -X POST "https://api.ads.openai.com/v1/ad_groups" \
  -H "Authorization: Bearer ${OPENAI_ADS_API_KEY}" \
  -H "Idempotency-Key: first-ad-group-001" \
  -H "Content-Type: application/json" \
  -d '{
    "campaign_id": "cmpn_123",
    "name": "Trail running",
    "status": "paused",
    "context_hints": [
      "Trail running shoes for rocky terrain"
    ],
    "bidding_config": {
      "billing_event_type": "click",
      "strategy": "fixed_bid",
      "max_bid_micros": 2000000
    }
  }'
```

Save the returned ad-group ID. The example maximum bid is $2 per click for a USD account.

### 3. Upload a creative image

```bash
curl -X POST "https://api.ads.openai.com/v1/upload" \
  -H "Authorization: Bearer ${OPENAI_ADS_API_KEY}" \
  -F "file=@/path/to/product-image.png"
```

Use an image at least 640 × 640 pixels. Save the returned `file_id`. You'll use this image in the ad.

### 4. Create the ad

```bash
curl -X POST "https://api.ads.openai.com/v1/ads" \
  -H "Authorization: Bearer ${OPENAI_ADS_API_KEY}" \
  -H "Idempotency-Key: first-ad-001" \
  -H "Content-Type: application/json" \
  -d '{
    "ad_group_id": "adgrp_123",
    "name": "Trail shoe launch",
    "status": "paused",
    "creative": {
      "type": "chat_card",
      "title": "Find your next trail shoe",
      "body": "Explore shoes made for your next outdoor run.",
      "target_url": "https://example.com/trail-shoes",
      "file_id": "file_123"
    }
  }'
```

Replace the `target_url` with your real, accessible landing page. Save the returned ad ID. Creating an ad submits its creative for review.

### 5. Preview and inspect

Check the creative, destination, review status, account reviews, targeting, and budget. A preview shows appearance; it does not confirm serving eligibility.

```bash
curl -X POST "https://api.ads.openai.com/v1/ads/ad_123/preview" \
  -H "Authorization: Bearer ${OPENAI_ADS_API_KEY}"
```

```bash
curl -G "https://api.ads.openai.com/v1/ads/ad_123" \
  -H "Authorization: Bearer ${OPENAI_ADS_API_KEY}" \
  --data-urlencode 'include[]=serving_issues'
```

### 6. Activate when ready

```bash
curl -X POST "https://api.ads.openai.com/v1/ads/ad_123/activate" \
  -H "Authorization: Bearer ${OPENAI_ADS_API_KEY}"
```

```bash
curl -X POST "https://api.ads.openai.com/v1/ad_groups/adgrp_123/activate" \
  -H "Authorization: Bearer ${OPENAI_ADS_API_KEY}"
```

```bash
curl -X POST "https://api.ads.openai.com/v1/campaigns/cmpn_123/activate" \
  -H "Authorization: Bearer ${OPENAI_ADS_API_KEY}"
```

Activation enables delivery when the remaining requirements are satisfied. Use Insights to monitor results and Serving Issues if delivery does not begin.

## Rate limits

The Advertiser API enforces limits by both ad account and IP address:

| Scope        | Limit                     |
| ------------ | ------------------------- |
| Per endpoint | 600 requests per minute   |
| Overall      | 1,200 requests per minute |

Requests must stay within both the ad-account and IP-address limits.

Bulk job creation has a separate limit of 10 requests per 10 seconds for each
ad account. See [Bulk API limits](https://developers.openai.com/ads/bulk-api#limits-and-retries).

## OpenAPI spec

[{"Download the OpenAPI spec"}](https://developers.openai.com/ads/openapi.json)

## Changelog

### October 26, 2026

- Enabled accounts can create ads with 4–6 square images by uploading each image and passing the returned file IDs in `creative.file_ids`. The images share one title, body, and destination URL, and are returned in `creative.images`. See [Create an ad with multiple images](https://developers.openai.com/ads/campaign-management#create-an-ad-with-multiple-images) for requirements and examples.

### September 30th, 2026

- Added selectable click/view attribution windows and time basis to all four GET Insights endpoints. Omitted settings now default independently to 30-day click, 1-day view, and ad-event time. Conversion totals include click-through plus view-through goal conversions and can differ from previous reports; impressions, clicks, and spend are unchanged. See [Understand attribution](https://developers.openai.com/ads/reporting#understand-attribution).

### September 10th, 2026

- Added granular web platform targeting with `desktop_web`, `ios_web`, and `android_web` in `targeting.platforms.included`. Target desktop, iOS, and Android browsers separately, or use `web` to include all web platforms. See [Platform Targeting](https://developers.openai.com/ads/platform-targeting). Platform breakdowns in [Insights](https://developers.openai.com/ads/api-reference/insights#platform-breakdown) also separate web platforms while preserving historical Web totals.

### September 9th, 2026

- Added [daily account spending limits](https://developers.openai.com/ads/api-reference/ad-account#set-a-daily-limit) for ad accounts on postpaid invoice billing. Set a shared allowance across campaigns that renews at midnight in the account timezone, with an optional end date. Existing date range limits remain available.

### August 25th, 2026

- Added custom audience Add, Remove, Replace, and Merge operations, automatic identifier matching, and support for small and empty exclusion-only audiences. See [Custom Audiences](https://developers.openai.com/ads/custom-audiences).

### August 19th, 2026

- Added phone, first name, last name, region, and postal code matching fields to the [JavaScript Pixel](https://developers.openai.com/ads/measurement-pixel).
- Added plural customer-information fields and Android GAID support to the [Conversions API](https://developers.openai.com/ads/conversions-api).

### July 16th, 2026

- Added support for passing the Pixel browser reference as `events[].user.obref` in [Conversions API](https://developers.openai.com/ads/conversions-api) requests.

### June 16th, 2026

- Added conversion-optimized campaign bidding with `bidding_type: "conversions"` and one standard conversion event setting.

### June 11th, 2026

- Added segmented insights for product, country, and device breakdowns, plus zero-impression product expansion.

### June 3rd, 2026

- Added location targeting support, including `/geo_lookup/search` and campaign `targeting.locations.include` for country, region, and market location IDs.
- Added conversion setup and reporting endpoints for API keys, pixels, event settings, and conversion insights.

### v1

- Published the initial API version.