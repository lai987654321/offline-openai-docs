# Troubleshooting

> For the complete documentation index, see [llms.txt](/llms.txt). Markdown versions of documentation pages are available by appending `.md` to the page URL.

## Serving Issues

When ads are not serving, inspect explicit serving issues before changing bids or recreating resources. A resource can be active and still be blocked by another requirement.

### Request serving details

```bash
curl -G "https://api.ads.openai.com/v1/ads/ad_123" \
  -H "Authorization: Bearer ${OPENAI_ADS_API_KEY}" \
  --data-urlencode 'include[]=serving_issues'
```

The same include is available on campaign and ad-group retrieval and list endpoints:

```bash
curl -G "https://api.ads.openai.com/v1/ad_groups" \
  -H "Authorization: Bearer ${OPENAI_ADS_API_KEY}" \
  --data-urlencode 'campaign_id=cmpn_123' \
  --data-urlencode 'include[]=serving_issues'
```

Inspect the returned issue details and the resource they apply to. Fix the underlying cause, then retrieve the resource again to check whether the issue remains.

### Check the hierarchy

1. **Account:** Is it active? Are brand and applicable account reviews complete? Is a spend limit exhausted?
1. **Campaign:** Is it active and within its schedule? Does it have available budget? Is targeting valid?
1. **Ad group:** Is it active? Is bidding compatible with the objective? For product feeds, does the product set contain eligible products?
1. **Ad:** Is it active and approved? Are the creative and landing page accessible?

An ad's status alone does not describe the entire hierarchy. A paused campaign can prevent an active ad from serving.

### If there is no explicit issue

An empty `serving_issues` array is not a promise of impressions. The campaign may have limited eligible opportunities, restrictive targeting, uncompetitive bids, or a small usable product set.

Compare reporting over a suitable interval rather than repeatedly checking a few minutes of activity.

## Statuses & Reviews

Status and review fields answer different questions. Status reflects whether a resource is enabled; review fields describe approval checks.

| Field                              | Meaning                                                     |
| ---------------------------------- | ----------------------------------------------------------- |
| Campaign, ad-group, or ad `status` | Configured state, such as `active`, `paused`, or `archived` |
| Ad `review_status` / `review`      | Creative review outcome and returned details                |
| Account `review`                   | Advertiser brand review                                     |
| Account `account_integrity_review` | Separate account review information when present            |

### Inspect an ad

```bash
curl -G "https://api.ads.openai.com/v1/ads/ad_123" \
  -H "Authorization: Bearer ${OPENAI_ADS_API_KEY}" \
  --data-urlencode 'include[]=serving_issues'
```

An ad with `status: "active"` and `review_status: "in_review"` is enabled but has not completed review. An approved ad can still be prevented from serving by a paused parent or another delivery condition.

### Understand review outcomes

- `in_review`: The relevant review is pending.
- `approved`: The relevant review passed.
- `rejected`: Inspect the returned reason and correct the relevant issue.

### Changes that affect review

Editing ad creative creates a new submitted version and triggers another creative review. Editing account branding can start a new brand review. Save the current response after updating so you know which configuration you are inspecting.

### Change configured status

Campaigns, ad groups, and ads have `/activate`, `/pause`, and `/archive` endpoints. For example:

```bash
curl -X POST "https://api.ads.openai.com/v1/ads/ad_123/pause" \
  -H "Authorization: Bearer ${OPENAI_ADS_API_KEY}"
```

Changing status does not approve a rejected creative or finish a pending review. Correct review issues through the appropriate creative or account workflow.

## Low Delivery & Bid Warnings

Investigate low delivery by checking eligibility, available opportunities, and bidding separately. Increasing a bid will not resolve a paused campaign, exhausted account limit, or rejected ad.

### 1. Rule out explicit blockers

Retrieve [Serving Issues](#serving-issues) and check statuses, reviews, campaign schedule, budgets, and account spend limits. For product feeds, confirm that the ad group's filters select ads-eligible products.

### 2. Inspect the low-bid warning

When low-bid diagnostics are available for your integration, use:

```bash
curl -G "https://api.ads.openai.com/v1/ad_groups/adgrp_123" \
  -H "Authorization: Bearer ${OPENAI_ADS_API_KEY}" \
  --data-urlencode 'include[]=bid_too_low'
```

When exposed, a response with `bid_too_low: true` warns that the bid may be too low for reliable delivery. The warning is guidance, not a serving restriction.

Warnings are not raised for inactive ad groups or within 24 hours of an ad-group update. Updating an individual ad does not reset that window. Absence of the warning is therefore not proof that the bid is competitive.

### 3. Check combined targeting

Inspect geography, platform, included audiences, and exclusions together. A large audience upload can still leave a small eligible population after matching and exclusions.

Context hints supply context rather than hard keyword eligibility. Use explicit targeting fields when investigating geographic or audience restrictions.

### 4. Review the strategy

For fixed bidding, check the currency and micros conversion, then assess the chosen bid. For Maximize Results, verify daily budget and objective compatibility; adding `max_bid_micros` is not a supported adjustment.

### 5. Measure after changes

Record what changed and when. Compare the same reporting scope and timezone over an appropriate interval, allowing for data freshness. Avoid changing several settings at once if you need to identify which change improved delivery.

## Feed & Conversion Issues

### Feed diagnostics

| Code                            | What to check                                                                                                   |
| ------------------------------- | --------------------------------------------------------------------------------------------------------------- |
| `missing_required_column`       | Compare the file's columns with the product file schema and add the missing required column.                    |
| `invalid_value`                 | Check the reported field's formatting and allowed values. For example, verify price amounts and currency codes. |
| `unsupported_file_type`         | Check that the uploaded files use a supported format. This walkthrough uses CSV.                                |
| `invalid_sftp_directory_layout` | Place feed files directly in the SFTP root and remove nested folders.                                           |

For upload status and row counts, see [Monitoring Uploads](https://developers.openai.com/ads/product-feeds#monitoring-uploads).

### Conversion events

Use recent events to confirm that your Pixel or server integration is sending data to the intended source. Check soon after triggering an action on your website or sending a server event.

```bash
curl -G "https://api.ads.openai.com/v1/conversions/events" \
  -H "Authorization: Bearer ${OPENAI_ADS_API_KEY}" \
  --data-urlencode "pid=${PIXEL_ID}" \
  --data-urlencode "limit=50"
```

This endpoint returns a sample of recent events from roughly the last 15 minutes. It is useful for testing and troubleshooting; use Insights for attributed conversion reporting and historical results.

Check that the event type, source, and integration channel match your test. Browser events use `pixel_sdk`; server events use `server_to_server`.

## API Errors

When a request fails, inspect the HTTP status and returned details before retrying. Keep enough context to distinguish an invalid request from a temporary failure.

### First checks

| Problem                | What to inspect                                                                 |
| ---------------------- | ------------------------------------------------------------------------------- |
| Authentication failure | Correct key type and bearer header                                              |
| Access denied          | Account ID, key access, and feature availability                                |
| Validation error       | Required fields, allowed values, amounts, parent IDs, and incompatible settings |
| Resource not found     | Exact ID, selected account, and resource type                                   |
| Conflict               | Idempotency-key reuse with a different body or an outdated revision             |
| Request too large      | Endpoint-specific size or operation-count limit                                 |
| Rate limited           | Returned retry guidance and the applicable shared limits                        |

### Match the endpoint's contract

Campaign, ad-group, and ad updates use `POST`. Product delta updates use `PATCH`. Image uploads use `/v1/upload`; custom-audience file uploads use `/v1/uploads`.

Bulk operation inputs are not identical to single-resource request bodies. Conversion event submission also uses a separate host and a CAPI key.

### Retry deliberately

Correct validation failures before resubmitting. For a network-uncertain supported create request, retry with the original `Idempotency-Key` and body. A new key can create a second resource.

For temporary failures, use bounded retries with increasing delays and follow retry guidance returned by the service. Bulk-operation results include `retryable` and can include `retry_after_seconds`; inspect each failed operation before deciding what to retry.