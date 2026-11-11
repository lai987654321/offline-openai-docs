# Bidding & Budgets

> For the complete documentation index, see [llms.txt](/llms.txt). Markdown versions of documentation pages are available by appending `.md` to the page URL.

Choose your campaign objective and budget, then configure how its ad groups bid.

Use the request conventions in [Overview](https://developers.openai.com/ads/api-overview). Examples use an ad account-scoped API key in `${OPENAI_ADS_API_KEY}` and sample IDs such as `cmpn_123` and `adgrp_123`. Replace these IDs with values returned by your requests. If you use a partner key, also include `OpenAI-Ad-Account: ${AD_ACCOUNT_ID}` on requests for the selected account.

Budget and bid examples use illustrative USD amounts. Use values appropriate to your account's currency and advertising plan. New resources are created paused so you can finish setup before enabling delivery.

## Choosing a Bid Strategy

Choose a strategy based on the control you need over bids and the outcome your campaign optimizes for.

| Strategy             | Use when                                                                 | Compatible objectives            | Budget            | Bid amount               |
| -------------------- | ------------------------------------------------------------------------ | -------------------------------- | ----------------- | ------------------------ |
| Fixed bid            | You want to set and adjust the bid yourself                              | Impressions, clicks, conversions | Daily or lifetime | Provide `max_bid_micros` |
| Maximize clicks      | You want OpenAI to adjust bids to seek more clicks from your budget      | Clicks                           | Daily             | Omit `max_bid_micros`    |
| Maximize conversions | You want OpenAI to adjust bids to seek more conversions from your budget | Conversions                      | Daily             | Omit `max_bid_micros`    |

**Maximize Results** is the name for the `maximize_clicks` and `maximize_conversions` strategies. Both are available for standard and product-feed campaigns.

### Campaign Objectives & Billing

Your campaign objective determines the outcome to optimize for. The billing event determines what you pay for.

| Setting            | Configured on | What it controls                                             |
| ------------------ | ------------- | ------------------------------------------------------------ |
| Campaign objective | Campaign      | The outcome to optimize for                                  |
| Campaign budget    | Campaign      | The daily or lifetime spending limit shared by its ad groups |
| Billing event      | Ad group      | Whether you pay for impressions or clicks                    |
| Bid strategy       | Ad group      | Whether you set bids or let OpenAI adjust them               |

#### Choose an objective

Use the following combinations of campaign objective and ad-group billing and bidding parameters:

| Campaign objective (`bidding_type`) | Billing event (`bidding_config.billing_event_type`) | Bid strategy (`bidding_config.strategy`) |
| ----------------------------------- | --------------------------------------------------- | ---------------------------------------- |
| `impressions`                       | `impression`                                        | `fixed_bid`                              |
| `clicks`                            | `click`                                             | `fixed_bid`                              |
| `clicks`                            | `click`                                             | `maximize_clicks`                        |
| `conversions`                       | `click`                                             | `fixed_bid`                              |
| `conversions`                       | `click`                                             | `maximize_conversions`                   |

#### Set up a conversion objective

To optimize for actions such as purchases or sign-ups, OpenAI needs conversion events from your site. Set up [conversion tracking](https://developers.openai.com/ads/api-reference/conversion-setup), then select one active standard conversion event setting from the same ad account as the campaign. Custom events cannot be optimization goals.

Conversion campaigns optimize for the selected action and bill for valid clicks.

The following example creates a paused conversion campaign with an illustrative $200 daily budget for a USD account:

```bash
curl -X POST "https://api.ads.openai.com/v1/campaigns" \
  -H "Authorization: Bearer ${OPENAI_ADS_API_KEY}" \
  -H "Idempotency-Key: conversion-campaign-001" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Trail shoe purchases",
    "status": "paused",
    "bidding_type": "conversions",
    "conversion_event_setting_ids": ["ces_123"],
    "budget": {
      "daily_spend_limit_micros": 200000000
    },
    "targeting": {
      "locations": {
        "countries": ["US"]
      }
    }
  }'
```

Replace `ces_123` with your conversion event setting ID and the sample country with your target locations. Save the returned campaign ID to create its ad groups.

### Check compatibility before creating an ad group

- Match the strategy to the campaign objective: `maximize_clicks` for `clicks`, or `maximize_conversions` for `conversions`.
- Use `billing_event_type: "click"` for both Maximize Results strategies.
- Use a daily campaign budget for Maximize Results.
- Include `max_bid_micros` for `fixed_bid`; omit it for Maximize Results.
- Use audience bid multipliers only with `fixed_bid`.

Set `strategy` explicitly so the request expresses your intended behavior.

## Fixed Bids

Use `fixed_bid` to supply the bid for an ad group. All ads in the group share its bidding configuration.

### Understand bid amounts

`max_bid_micros` uses the same currency scaling as campaign budgets: one major currency unit equals `1000000` micros. Multiply the bid amount by `1,000,000` and send the result as an integer. For example, a $2.50 click bid in a USD account is `2500000`.

For impression bidding, the API expects a bid **per impression**. If you work with CPM (cost per thousand impressions), divide by `1,000` first. A $60 CPM bid is $0.06 per impression, so send `60000` micros: `60 ÷ 1,000 × 1,000,000 = 60000`.

Bid limits and permitted monetary precision depend on the account currency and campaign objective.

### Create an ad group with a fixed bid

First create a campaign with a compatible objective and budget. The following example uses an existing clicks campaign and an illustrative $2 click bid:

```bash
curl -X POST "https://api.ads.openai.com/v1/ad_groups" \
  -H "Authorization: Bearer ${OPENAI_ADS_API_KEY}" \
  -H "Idempotency-Key: fixed-bid-ad-group-001" \
  -H "Content-Type: application/json" \
  -d '{
    "campaign_id": "cmpn_123",
    "name": "Trail running",
    "status": "paused",
    "bidding_config": {
      "billing_event_type": "click",
      "strategy": "fixed_bid",
      "max_bid_micros": 2000000
    }
  }'
```

Save the returned ad-group `id`. Confirm that `bidding_config` contains the requested billing event, strategy, and amount.

### Update a fixed bid

Send the desired configuration to the ad-group update endpoint. This example changes a clicks ad group's bid to $3 for a USD account:

```bash
curl -X POST "https://api.ads.openai.com/v1/ad_groups/adgrp_123" \
  -H "Authorization: Bearer ${OPENAI_ADS_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "bidding_config": {
      "billing_event_type": "click",
      "strategy": "fixed_bid",
      "max_bid_micros": 3000000
    }
  }'
```

### Check delivery guidance

Request bidding guidance and serving issues when reviewing delivery:

```bash
curl -G "https://api.ads.openai.com/v1/ad_groups/adgrp_123" \
  -H "Authorization: Bearer ${OPENAI_ADS_API_KEY}" \
  --data-urlencode 'include[]=bid_too_low' \
  --data-urlencode 'include[]=serving_issues'
```

`bid_too_low: true` indicates that the bid may be too low for reliable delivery. It is guidance, not a serving restriction. Inspect `serving_issues` for reported delivery blockers before deciding whether to change the bid.

See the [Ad Groups API reference](https://developers.openai.com/ads/api-reference/ad-groups) for request and response fields.

## Maximize Results

Use Maximize Results to let OpenAI adjust bids toward clicks or conversions using your daily campaign budget. Both strategies are available for standard and product-feed campaigns.

The API exposes two strategies:

| Campaign `bidding_type` | Ad-group `strategy`    | Optimization outcome                     |
| ----------------------- | ---------------------- | ---------------------------------------- |
| `clicks`                | `maximize_clicks`      | Clicks                                   |
| `conversions`           | `maximize_conversions` | The campaign's selected conversion event |

Both strategies use `billing_event_type: "click"`.

### Prerequisites

- Use a campaign with a daily budget.
- For conversions, configure exactly one active standard conversion event setting on the campaign.
- Omit `max_bid_micros` and do not configure audience bid multipliers.
- Include an `Idempotency-Key` when creating the ad group. It is required for Maximize Results.

### Create an ad group that maximizes clicks

Use the ID of a clicks campaign with a daily budget, such as the campaign from Your First Campaign:

```bash
curl -X POST "https://api.ads.openai.com/v1/ad_groups" \
  -H "Authorization: Bearer ${OPENAI_ADS_API_KEY}" \
  -H "Idempotency-Key: maximize-clicks-ad-group-001" \
  -H "Content-Type: application/json" \
  -d '{
    "campaign_id": "cmpn_123",
    "name": "Trail running clicks",
    "status": "paused",
    "bidding_config": {
      "billing_event_type": "click",
      "strategy": "maximize_clicks"
    }
  }'
```

Save the returned ad-group ID and confirm the returned `bidding_config.strategy`. If you retry the same creation, reuse the same `Idempotency-Key` and request body. Use a new key for a different ad group.

### Create an ad group that maximizes conversions

Use the same creation endpoint with the ID of your conversion campaign and this `bidding_config` object:

```json
{
  "billing_event_type": "click",
  "strategy": "maximize_conversions"
}
```

Supply a new `Idempotency-Key` for the new ad group. Confirm that the parent campaign has the intended event setting and a daily budget.

## Changing Bid Strategies

Update an ad group's `bidding_config` to switch between a fixed bid and Maximize Results. The new strategy must match the parent campaign's objective and budget.

### Inspect the current configuration

Retrieve the campaign and ad group before making the change:

```bash
curl -G "https://api.ads.openai.com/v1/campaigns/cmpn_123" \
  -H "Authorization: Bearer ${OPENAI_ADS_API_KEY}"
```

```bash
curl -G "https://api.ads.openai.com/v1/ad_groups/adgrp_123" \
  -H "Authorization: Bearer ${OPENAI_ADS_API_KEY}"
```

Check the campaign objective, budget type, and the ad group's current bid and audience multipliers.

| Change                            | Required configuration                                                                         |
| --------------------------------- | ---------------------------------------------------------------------------------------------- |
| Fixed bid to Maximize clicks      | Clicks campaign, daily budget, `strategy: "maximize_clicks"`, no `max_bid_micros`              |
| Fixed bid to Maximize conversions | Conversions campaign, daily budget, `strategy: "maximize_conversions"`, no `max_bid_micros`    |
| Maximize Results to fixed bid     | `strategy: "fixed_bid"` and an explicit `max_bid_micros` appropriate to the campaign objective |

### Switch to Maximize Results

This example switches a clicks ad group to `maximize_clicks` and explicitly clears audience bid multipliers:

```bash
curl -X POST "https://api.ads.openai.com/v1/ad_groups/adgrp_123" \
  -H "Authorization: Bearer ${OPENAI_ADS_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "bidding_config": {
      "billing_event_type": "click",
      "strategy": "maximize_clicks",
      "custom_audience_bid_multipliers": []
    }
  }'
```

If the campaign uses a lifetime budget, first switch it to a daily budget and confirm the response. Then update the ad group. Switching budget types changes the spending limit that applies to every ad group in the campaign.

### Switch back to a fixed bid

Supply the new bid explicitly. This example sets a $2 click bid for a USD clicks campaign:

```bash
curl -X POST "https://api.ads.openai.com/v1/ad_groups/adgrp_123" \
  -H "Authorization: Bearer ${OPENAI_ADS_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "bidding_config": {
      "billing_event_type": "click",
      "strategy": "fixed_bid",
      "max_bid_micros": 2000000
    }
  }'
```

Previously removed audience multipliers must be included again if you want to restore them.

### Verify the change

Inspect the returned `bidding_config` and retrieve the ad group again if needed. Confirm the strategy, billing event, bid amount where applicable, and audience multipliers.

The campaign keeps its existing objective and, for conversion campaigns, its selected event. Create a new campaign to change either. Switching between `fixed_bid` and Maximize Results changes how the ad group bids within that objective.

## Campaign Budgets

Set a budget on the campaign to control spending across its ad groups. Use separate campaigns when you need separate budgets.

### Choose a budget type

| Budget type | Field                         | Use when                                                               |
| ----------- | ----------------------------- | ---------------------------------------------------------------------- |
| Daily       | `daily_spend_limit_micros`    | You want a daily spending limit or plan to use Maximize Results        |
| Lifetime    | `lifetime_spend_limit_micros` | You want a total spending limit for the campaign and use fixed bidding |

Provide exactly one budget field. A campaign cannot have both a daily and a lifetime budget.

### Understand micros

Budget amounts are integers expressed in **micros**, where one micro is one millionth of a major unit of the account's currency. Multiply an amount by `1,000,000` to convert it to micros; divide by `1,000,000` to read it back.

For a USD account:

- $1.00 = `1000000` micros.
- $2.50 = `2500000` micros.
- $50.00 = `50000000` micros.

The same scaling applies to other account currencies. Send the integer micros value in the request, without a currency symbol or thousands separators.

Daily minimums depend on the account currency. Requests below the applicable minimum return an error with the required amount.

### Create a campaign with a daily budget

The following example creates a paused clicks campaign with an illustrative $50 daily budget:

```bash
curl -X POST "https://api.ads.openai.com/v1/campaigns" \
  -H "Authorization: Bearer ${OPENAI_ADS_API_KEY}" \
  -H "Idempotency-Key: daily-budget-campaign-001" \
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
        "countries": ["US"]
      }
    }
  }'
```

Save the returned campaign ID. Confirm the budget in the response before adding ad groups.

For a lifetime budget, use the following `budget` object in the creation request:

```json
{
  "lifetime_spend_limit_micros": 500000000
}
```

This sets a $500 total campaign budget for a USD account.

### Update a budget amount

Send the new amount to the campaign update endpoint.

```bash
curl -X POST "https://api.ads.openai.com/v1/campaigns/cmpn_123" \
  -H "Authorization: Bearer ${OPENAI_ADS_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "budget": {
      "daily_spend_limit_micros": 75000000
    }
  }'
```

For a USD account, this sets the daily budget to $75. It does not add $75 to the previous budget.

For a lifetime budget, send `lifetime_spend_limit_micros` with the new total. You cannot reduce a lifetime budget below the amount the campaign has already spent.

When reducing a daily budget, also review the fixed bids and audience multipliers on its ad groups. The API can reject a budget that is below an ad group's effective bid.

### Switch from a lifetime budget to a daily budget

For an existing lifetime-budget campaign, this request sets a $75 daily budget in a USD account:

```bash
curl -X POST "https://api.ads.openai.com/v1/campaigns/cmpn_123" \
  -H "Authorization: Bearer ${OPENAI_ADS_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "budget": {
      "daily_spend_limit_micros": 75000000
    }
  }'
```

You cannot switch a daily budget back to a lifetime budget through a campaign update. Create a new campaign if you need a lifetime budget instead.

### Verify the budget and delivery

Retrieve the campaign to confirm its budget and inspect reported serving issues:

```bash
curl -G "https://api.ads.openai.com/v1/campaigns/cmpn_123" \
  -H "Authorization: Bearer ${OPENAI_ADS_API_KEY}" \
  --data-urlencode 'include[]=serving_issues'
```

Check that `budget` contains the intended budget type and amount. Use Insights to monitor spend after activation.

Campaign budgets and ad account spend limits apply independently. Raising a campaign budget does not override an exhausted account spend limit. Delivery also depends on the campaign schedule, resource statuses, reviews, targeting, and available inventory.

See the [Campaigns API reference](https://developers.openai.com/ads/api-reference/campaigns) for budget fields and the [Ad Account API reference](https://developers.openai.com/ads/api-reference/ad-account) for account controls.

## Account Budgets

An account spend-limit window caps total spending across the account's campaigns during a date range. Campaign budgets continue to apply independently.

Spend-limit windows are available only to some accounts.

An account limit does not allocate a budget to each campaign. A campaign can have budget remaining while the account's active limit is exhausted. Conversely, removing an account limit does not remove the campaigns' own budgets.

See [Spend Limits](https://developers.openai.com/ads/account-management#spend-limits) to create, inspect, update, or delete account spend-limit windows.