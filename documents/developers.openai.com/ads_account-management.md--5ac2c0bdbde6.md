# Account Management

> For the complete documentation index, see [llms.txt](/llms.txt). Markdown versions of documentation pages are available by appending `.md` to the page URL.

## Account Details & Branding

An ad account owns campaigns, creative assets, feeds, audiences, and conversion sources. Its brand name and advertiser icon identify the advertiser in ads.

### Retrieve account details

```bash
curl -G "https://api.ads.openai.com/v1/ad_account" \
  -H "Authorization: Bearer ${OPENAI_ADS_API_KEY}"
```

Check your advertiser ID, names, URL, currency, timezone, configured status, and returned reviews. Currency and timezone are creation-time choices and cannot be edited through the branding update.

The account has three names with different purposes:

| Field          | Purpose                             |
| -------------- | ----------------------------------- |
| `legal_name`   | Legal business name                 |
| `account_name` | Internal name shown in Ads Manager  |
| `brand_name`   | Public advertiser name shown in ads |

The response also includes `name`, which matches `legal_name`.

### Upload an advertiser icon

```bash
curl -X POST "https://api.ads.openai.com/v1/upload" \
  -H "Authorization: Bearer ${OPENAI_ADS_API_KEY}" \
  -F "file=@/path/to/favicon.png" \
  -F "purpose=account_favicon"
```

Use JPEG, PNG, or WebP with dimensions of at least 256 × 256 pixels. Save the returned `file_id`.

### Apply branding

Changing the legal or public brand name pauses ad delivery until the account
passes review.

```bash
curl -X POST "https://api.ads.openai.com/v1/ad_account/brand" \
  -H "Authorization: Bearer ${OPENAI_ADS_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "brand_name": "Acme",
    "url": "https://example.com",
    "favicon_file_id": "file_123"
  }'
```

Replace the sample URL with your actual website and `file_123` with the uploaded
icon's file ID.

Use `legal_name`, `account_name`, or `brand_name` to update names independently.
Omitted names remain unchanged. Legacy `name` sets all three names to the same
value; don't combine it with the individual name fields.

See the [API reference](https://developers.openai.com/ads/api-reference/ad-account#update-account-brand-metadata)
for field requirements and errors.

### Check review after updating

Retrieve the account again. Brand changes can trigger review. The returned `preview_url` is a preview of the advertiser icon, not a permanent asset URL. Do not store it as your application's durable source of truth for the branding file.

## Account Statuses & Reviews

An account's configured status and its reviews are separate. Check both when onboarding or investigating account-wide delivery problems.

### Retrieve current state

```bash
curl -G "https://api.ads.openai.com/v1/ad_account" \
  -H "Authorization: Bearer ${OPENAI_ADS_API_KEY}"
```

| Field                                    | What it tells you                                          |
| ---------------------------------------- | ---------------------------------------------------------- |
| `status`                                 | Whether the account is configured as active or paused      |
| `review.status`                          | Brand-review state                                         |
| `review.reason`                          | Returned reason for a brand-review issue, when available   |
| `account_integrity_review.review.status` | Separate account-review state, when the object is returned |

The response can omit account-integrity review information when no corresponding state is available. Do not interpret an omitted object as an explicit approval or rejection.

### Approved branding is one requirement

An active account with approved branding can still have another outstanding account review, an exhausted spend limit, or campaign-level delivery issues. Inspect the returned account-review fields.

## Activating & Pausing

Pause your account to stop delivery across its campaigns. Activate it to allow eligible campaigns to deliver again.

Use account controls when the change should apply to the entire account. For a narrower change, pause the relevant campaign, ad group, or ad instead.

### Pause the account

```bash
curl -X POST "https://api.ads.openai.com/v1/ad_account/pause" \
  -H "Authorization: Bearer ${OPENAI_ADS_API_KEY}"
```

Confirm that the returned account status is `paused`.

### Activate the account

```bash
curl -X POST "https://api.ads.openai.com/v1/ad_account/activate" \
  -H "Authorization: Bearer ${OPENAI_ADS_API_KEY}"
```

Confirm the returned status and inspect the account's reviews. Activation permits delivery only when the other conditions are satisfied.

### What activation does not establish

Account activation does not mean that every campaign is active, every ad is approved, or every budget has available capacity. Check child resource statuses, schedules, reviews, and spending controls before expecting traffic.

Similarly, do not infer that child resource statuses were rewritten after an account pause. Retrieve the campaign, ad group, or ad if your application needs its current configured state.

## Spend Limits

An account spend-limit window caps total spending across the account's campaigns during a date range. Campaign budgets continue to apply independently.

Spend-limit windows are available only to some accounts.

### Create a window

```bash
curl -X POST "https://api.ads.openai.com/v1/ad_account/spend_limit_windows" \
  -H "Authorization: Bearer ${OPENAI_ADS_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "start_date": "2026-10-01",
    "end_date": "2026-11-01",
    "amount_micros": 10000000000,
    "name": "October account limit",
    "io_id": "IO-123"
  }'
```

The example is 10,000 currency units. Choose your intended amount and dates before submitting it. `start_date` is inclusive and `end_date` is exclusive, interpreted in the ad account's timezone.

Save the returned `window_id`. The response also describes whether the window can be edited or deleted.

### List windows

```bash
curl -G "https://api.ads.openai.com/v1/ad_account/spend_limit_windows" \
  -H "Authorization: Bearer ${OPENAI_ADS_API_KEY}"
```

Inspect active and scheduled windows before creating another one. Windows cannot overlap, and you can schedule up to 60 future windows.

### Update a window

```bash
curl -X POST "https://api.ads.openai.com/v1/ad_account/spend_limit_windows/slw_123" \
  -H "Authorization: Bearer ${OPENAI_ADS_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "amount_micros": 12000000000
  }'
```

Send only the fields you intend to change. An active window's start date cannot be changed. The amount cannot be reduced below spending that has already occurred. Completed windows cannot be edited or deleted.

### Delete a window

```bash
curl -X POST "https://api.ads.openai.com/v1/ad_account/spend_limit_windows/slw_123/delete" \
  -H "Authorization: Bearer ${OPENAI_ADS_API_KEY}"
```

Deleting or increasing an exhausted active limit can allow delivery to resume if no other requirement blocks it. Review the intended account-wide spending effect before making that change.

### Account limits versus campaign budgets

An account limit does not allocate a budget to each campaign. A campaign can have budget remaining while the account's active limit is exhausted. Conversely, removing an account limit does not remove the campaigns' own budgets.

The example endpoints manage date-window limits. If your integration also uses another account spending control, inspect it separately; do not assume that deleting a window removes every account-level control.