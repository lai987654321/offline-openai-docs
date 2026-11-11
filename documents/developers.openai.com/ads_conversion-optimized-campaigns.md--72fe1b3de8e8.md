# Conversion-Optimized Campaigns

> For the complete documentation index, see [llms.txt](/llms.txt). Markdown versions of documentation pages are available by appending `.md` to the page URL.

Use a conversion-optimized cost-per-click (oCPC) campaign when you want to
optimize delivery toward one tracked conversion event while continuing to pay
for valid clicks. In the Ads API, oCPC uses `bidding_type: "conversions"`.

oCPC is in open beta for both standard and product-feed campaigns. Use the
  same campaign and ad-group endpoints to optimize for conversions while
  continuing to pay per valid click.

Choose the campaign goal that matches the outcome you want:

| Goal                 | Best for                       | How you pay                         | What delivery optimizes for                                  |
| -------------------- | ------------------------------ | ----------------------------------- | ------------------------------------------------------------ |
| `impressions` (CPM)  | Reach and awareness            | Per 1,000 impressions               | Broad delivery at scale                                      |
| `clicks` (CPC)       | Engagement and traffic         | Per valid click                     | Clicks from people likely to engage                          |
| `conversions` (oCPC) | A tracked action after a click | Per valid click, not per conversion | Clicks more likely to lead to your selected conversion event |

## Before you begin

Before you create an oCPC campaign, make sure:

- The ad account supports conversion bidding. If campaign creation
  returns `403` with `Conversion bidding is not enabled`, contact your OpenAI
  partner representative.
- You have set up conversion tracking with the [JavaScript
  Pixel](https://developers.openai.com/ads/measurement-pixel), the [Conversions API](https://developers.openai.com/ads/conversions-api),
  or both. The Conversions API is a more reliable tracking source than the
  pixel alone.
- You have exactly one active [standard conversion
  event](https://developers.openai.com/ads/supported-events) to use as the optimization goal. Custom events
  cannot be oCPC optimization goals.
- The conversion event setting belongs to the current ad account and connects
  to one active conversion source.

Product-feed conversion bidding is available in open beta. Each oCPC campaign
uses one selected conversion event, and you cannot change the goal or event
after campaign creation.

## Create a conversion-optimized campaign

Create the campaign as `paused` while you add and check its ad groups and ads.

```bash
curl -X POST "https://api.ads.openai.com/v1/campaigns" \
  -H "Authorization: Bearer $OPENAI_ADS_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Acme purchases",
    "status": "paused",
    "budget": {
      "lifetime_spend_limit_micros": 250000000
    },
    "bidding_type": "conversions",
    "conversion_event_setting_ids": ["ces_123"]
  }'
```

Replace `ces_123` with the active conversion event setting ID that represents
your goal, such as `order_created`, `lead_created`, or
`registration_completed`. See [Conversion
Setup](https://developers.openai.com/ads/api-reference/conversion-setup) to create and manage event
settings.

For a product-feed campaign, use the same `POST /campaigns` endpoint. Include
`mode: "product_feed"`, the ID of a product feed linked to the ad account, and
the same conversion bidding fields:

```bash
curl -X POST "https://api.ads.openai.com/v1/campaigns" \
  -H "Authorization: Bearer $OPENAI_ADS_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Running shoes catalog purchases",
    "status": "paused",
    "mode": "product_feed",
    "product_feed_id": "product_feed_123",
    "budget": {
      "lifetime_spend_limit_micros": 250000000
    },
    "bidding_type": "conversions",
    "conversion_event_setting_ids": ["ces_123"]
  }'
```

Create each child ad group with `billing_event_type` set to `click`. For an
oCPC campaign, `max_bid_micros` is the CPA bid even though billing uses valid
clicks. For example, `100000000` is a $100.00 CPA bid for a USD account.

```bash
curl -X POST "https://api.ads.openai.com/v1/ad_groups" \
  -H "Authorization: Bearer $OPENAI_ADS_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "campaign_id": "cmpn_101",
    "name": "US English",
    "status": "active",
    "bidding_config": {
      "billing_event_type": "click",
      "max_bid_micros": 100000000
    }
  }'
```

For a product-feed campaign, the ad group automatically inherits the campaign's
product feed. Include `product_set` only when you want to specify product
filters; its `product_feed_id` must match the campaign's feed. See
[Product Feeds](https://developers.openai.com/ads/product-feeds) for the complete product-feed campaign,
ad-group, and product-ad template workflow.

Create ads as you normally would, then activate the campaign after all child
resources are ready. For the complete resource-creation sequence, see the
[Quickstart](https://developers.openai.com/ads/api-quickstart). For all campaign and ad-group fields, see
[Campaigns](https://developers.openai.com/ads/api-reference/campaigns) and [Ad
Groups](https://developers.openai.com/ads/api-reference/ad-groups).

## Understand delivery and billing

oCPC uses your selected conversion event together with ad quality, relevance,
click likelihood, and conversion likelihood to favor clicks that are more
likely to lead to that event. The CPA bid controls how the campaign competes
for those outcomes.

Billing does not change to pay per conversion. OpenAI charges you only when a
valid click occurs, and the auction determines the actual CPC. Treat the CPA
bid as an optimization input, not as a conversion charge.

## Review and improve performance

In Ads Manager, review impressions, clicks, conversions, spend, click-through
rate (CTR), and average CPC together. Because oCPC optimizes toward the
selected event, conversions are the primary outcome to review. You can
calculate cost per conversion by dividing spend by conversions.

Use the [Insights endpoints](https://developers.openai.com/ads/api-reference/insights) to retrieve delivery
metrics such as impressions, clicks, spend, CTR, and CPC.

To improve performance:

- Choose the standard conversion event that best represents your campaign goal.
- Keep conversion tracking healthy. Incomplete or incorrectly configured tracking can
  make reporting and optimization less effective.
- Use a conversion event with enough volume to evaluate performance.
- Align ad copy with user intent and the selected conversion goal.
- Review enough volume before making large changes to bids, budgets, or
  creative.

## Common questions

### Supported events

An oCPC campaign supports exactly one active standard conversion event setting.
Custom event settings are not supported as optimization goals. See [Supported
Events](https://developers.openai.com/ads/supported-events) for the standard event names.

### Changing an existing campaign

No. You cannot change an existing CPM or CPC campaign to oCPC. Create a new
campaign with `bidding_type: "conversions"`.

### Changing the selected conversion event

No. You cannot change the campaign goal or selected conversion event after
creation. Create a new campaign to optimize toward a different event.

### Billing

No. oCPC optimizes delivery toward the selected conversion event, but billing
still uses valid clicks.

### Product-feed campaigns

Yes. Product-feed oCPC is available in open beta. Set
`mode` to `product_feed`, include the linked `product_feed_id`, and set
`bidding_type` to `conversions` when creating the campaign. Create its ad group
with `billing_event_type: "click"`. The ad group inherits the campaign's feed;
include `product_set` only when you want to specify product filters.

## Next steps

- [Set up conversion measurement](https://developers.openai.com/ads/api-reference/conversion-setup)
- [Send browser events with the JavaScript Pixel](https://developers.openai.com/ads/measurement-pixel)
- [Send server-side events with the Conversions API](https://developers.openai.com/ads/conversions-api)
- [Create campaigns](https://developers.openai.com/ads/api-reference/campaigns)
- [Create ad groups](https://developers.openai.com/ads/api-reference/ad-groups)
- [Create product-feed campaigns](https://developers.openai.com/ads/product-feeds)
- [Query insights](https://developers.openai.com/ads/api-reference/insights)