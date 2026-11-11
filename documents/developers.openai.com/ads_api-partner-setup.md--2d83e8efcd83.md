# API Partner Setup

> For the complete documentation index, see [llms.txt](/llms.txt). Markdown versions of documentation pages are available by appending `.md` to the page URL.

API partners can use the Ads API to configure measurement and campaign
resources for client accounts. Use the API key associated with the client ad
account for every request in this guide.

## Before you begin

You need:

- An Ads API key for the client ad account.
- Access to the client's website and brand assets.
- A server-side secret manager for the Ads API key and any Conversions API keys you create.

Send requests to `https://api.ads.openai.com/v1`. Store the account's Ads API
key in `OPENAI_ADS_API_KEY` for the examples in this guide.

Brand updates, pixel management, and Conversions API key creation must be
enabled for the client account. If a brand update returns `403`, or
`/conversions/pixels` or `/conversions/api_keys` returns `404` with `Not found`,
contact your OpenAI partner representative. A `Client data source not found`
response means an event setting references a source that does not exist in the
current ad account.

Conversion-optimized campaigns must also be enabled for the client account. If
campaign creation returns `403` with `Conversion bidding is not enabled`,
contact your OpenAI partner representative.

## 1. Confirm account access

Use `GET /ad_account` to verify that the key is associated with the intended
client account:

```bash
curl -X GET "https://api.ads.openai.com/v1/ad_account" \
  -H "Authorization: Bearer $OPENAI_ADS_API_KEY"
```

```json
{
  "id": "adacct_123",
  "name": "Acme Ads",
  "url": "https://www.acme.example",
  "preview_url": null,
  "status": "active",
  "timezone": "America/New_York",
  "currency_code": "USD",
  "review": {
    "status": "approved"
  }
}
```

Check the account name, URL, time zone, and currency before you create campaign
resources. Contact your OpenAI partner representative if the account details or
API access are incorrect.

<a id="2-add-a-brand-favicon"></a>

## 2. Add a brand icon

An account cannot serve ads until its brand review is approved. If
`review.reason` is `missing_favicon`, upload and assign a brand icon before you
create active campaign resources.

First, upload an image with `purpose` set to `account_favicon`. The image must be
at least 128 × 128 pixels. You can pass the client's website URL and let the API
resolve a suitable icon:

```bash
curl -X POST "https://api.ads.openai.com/v1/upload" \
  -H "Authorization: Bearer $OPENAI_ADS_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "image_url": "https://www.acme.example",
    "purpose": "account_favicon"
  }'
```

Save the returned `file_id`, then assign it to the account:

```bash
curl -X POST "https://api.ads.openai.com/v1/ad_account/brand" \
  -H "Authorization: Bearer $OPENAI_ADS_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "favicon_file_id": "file_123"
  }'
```

The brand update starts a review. Poll `GET /ad_account` until `review.status`
is `approved`. If the status is `rejected`, use `review.reason` to correct the
brand metadata before you activate a campaign.

## 3. Configure conversions

Create conversion resources before you instrument the client's site.

First, create a web pixel:

```bash
curl -X POST "https://api.ads.openai.com/v1/conversions/pixels" \
  -H "Authorization: Bearer $OPENAI_ADS_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Acme website",
    "client_type": "web"
  }'
```

Save both returned identifiers. Use `id` when you create an event setting and
use `pixel_id` when you send conversion events.

```json
{
  "id": "clidsrc_123",
  "client_type": "web",
  "name": "Acme website",
  "pixel_id": "134534..."
}
```

Web pixels created through the Ads API automatically use [automatic advanced
matching](https://developers.openai.com/ads/measurement-pixel#automatic-advanced-matching).

Next, create a server-side Conversions API key:

```bash
curl -X POST "https://api.ads.openai.com/v1/conversions/api_keys" \
  -H "Authorization: Bearer $OPENAI_ADS_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Acme production conversions"
  }'
```

Store the returned `api_key` in a server-side secret manager. Use this key only
to send conversion events; do not expose it in browser code.

Finally, define the conversion event you want to measure or optimize for:

```bash
curl -X POST "https://api.ads.openai.com/v1/conversions/event_settings" \
  -H "Authorization: Bearer $OPENAI_ADS_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Purchases",
    "event_type": "order_created",
    "attribution_window_days": 30,
    "source_ids": ["clidsrc_123"]
  }'
```

Save the returned event setting `id`. For endpoint fields and responses, see
[Conversion Setup](https://developers.openai.com/ads/api-reference/conversion-setup). To implement event
delivery, use the [JavaScript Pixel](https://developers.openai.com/ads/measurement-pixel), the
[Conversions API](https://developers.openai.com/ads/conversions-api), or both with shared event IDs for
deduplication.

When you send conversion events on behalf of a client, include the same
`integration_source` identifier on every request. See [Identify partner
integrations](https://developers.openai.com/ads/conversions-api#identify-partner-integrations) for the
request format and naming requirements.

## 4. Create campaigns and ads

Follow the [Quickstart](https://developers.openai.com/ads/api-quickstart) to create a campaign, ad
group, creative asset, and ad in the correct order. For partner setup, create
the campaign as `paused` instead of `active`, then activate it after all child
resources are ready.

To create a conversion-optimized campaign (oCPC), set `bidding_type` to
`conversions` and pass exactly one event setting ID. For the bidding model,
prerequisites, and reporting guidance, see [Conversion-Optimized
Campaigns](https://developers.openai.com/ads/conversion-optimized-campaigns).

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

The event setting must be active, belong to the current ad account, connect to
one active conversion source, and use an event from [Supported
Events](https://developers.openai.com/ads/supported-events), such as `order_created`, `lead_created`, or
`registration_completed`. Custom events cannot be optimization goals.
For product-feed campaigns in open beta, use the same campaign endpoint and add
`mode: "product_feed"` and the linked `product_feed_id`. You cannot change the
campaign objective or selected conversion event after creation.

Next, create each ad group with `billing_event_type` set to `click`. For an
oCPC campaign, `max_bid_micros` is the CPA bid; for example, `100000000` is a
$100.00 CPA bid for a USD account.

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

Create campaigns as `paused` while you add and validate their ad groups and ads.
Activate the campaign only after all child resources are ready.

## Next steps

- [Authentication](https://developers.openai.com/ads/api-reference/authentication)
- [Ad Account](https://developers.openai.com/ads/api-reference/ad-account)
- [Conversion Setup](https://developers.openai.com/ads/api-reference/conversion-setup)
- [Campaigns](https://developers.openai.com/ads/api-reference/campaigns)
- [Ad Groups](https://developers.openai.com/ads/api-reference/ad-groups)
- [Ads](https://developers.openai.com/ads/api-reference/ads)
- [Files](https://developers.openai.com/ads/api-reference/files)
- [Insights](https://developers.openai.com/ads/api-reference/insights)