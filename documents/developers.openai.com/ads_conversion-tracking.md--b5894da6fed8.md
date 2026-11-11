# Conversion Tracking

> For the complete documentation index, see [llms.txt](/llms.txt). Markdown versions of documentation pages are available by appending `.md` to the page URL.

Use conversion tracking to measure actions people take after interacting with your ads, such as purchases, registrations, or lead submissions. Send events from your website or server, define which actions count as conversions, and connect them to your campaigns.

Management requests use an ad account-scoped Advertiser API key, `${OPENAI_ADS_API_KEY}`. Server-side event requests use a separate Conversions API key, `${OPENAI_CONVERSIONS_API_KEY}`. Keep both keys on your server. See [Authentication](https://developers.openai.com/ads/api-reference/authentication) for Advertiser API request conventions.

Examples use a website purchase in USD and sample IDs such as `cds_123`, `ces_123`, and `cmpn_123`. Replace sample IDs with those returned by your requests and use the currency appropriate to the transaction.

Conversion tracking connects activity on your site to your advertising:

- **A data source** receives events from your website or server.
- **A conversion event setting** defines which event from that source counts as a conversion, such as a completed purchase.
- **A campaign** uses the attached event setting for conversion reporting and, when configured, optimization.

For example, your website sends an `order_created` event when a customer completes a purchase. You create a conversion event setting for purchases and attach it to the campaigns you want to measure.

**Choose how to send events**

| Integration       | Where events are sent  | When to use it                                                                                   |
| ----------------- | ---------------------- | ------------------------------------------------------------------------------------------------ |
| Measurement Pixel | The customer's browser | Measure actions that happen on your website.                                                     |
| Conversions API   | Your server            | Send actions recorded by your server, such as confirmed orders.                                  |
| Both              | Browser and server     | Measure the same actions through both integrations, with shared event IDs to prevent duplicates. |

Both integrations use a **Pixel ID** to identify the data source. A server-only integration still needs a Pixel ID, but does not require installing the browser Pixel.

When using both integrations for the same website, reuse the data source. For the same conversion, send the same event name and event ID through both integrations so OpenAI can recognize the duplicate.

## Pixel Setup

Use the Measurement Pixel to send events from your website. Create a data source, install the Pixel with its Pixel ID, and send an event when the action occurs.

### 1. Create a data source

```bash
curl -X POST "https://api.ads.openai.com/v1/conversions/pixels" \
  -H "Authorization: Bearer ${OPENAI_ADS_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Acme website",
    "client_type": "web"
  }'
```

Save the returned `pixel_id` for sending events and `id` for creating conversion event settings. These identify the same source for different operations:

| Value      | Used for                                                                                                            |
| ---------- | ------------------------------------------------------------------------------------------------------------------- |
| `pixel_id` | Initializing the Pixel, sending server events, and checking recent events. Use it as `${PIXEL_ID}` in the examples. |
| `id`       | Selecting the source when creating a conversion event setting. Use it in place of `cds_123`.                        |

If you already have a source for this website, retrieve and reuse it:

```bash
curl "https://api.ads.openai.com/v1/conversions/pixels" \
  -H "Authorization: Bearer ${OPENAI_ADS_API_KEY}"
```

### 2. Install the Pixel

Add the installation snippet from the [Measurement Pixel guide](https://developers.openai.com/ads/measurement-pixel#install-the-measurement-pixel) to the pages where you want to measure events. Set `pixelId` to the value returned when you created the source. No API key is needed in the browser.

Where measurement requires consent, configure the [Pixel's consent controls](https://developers.openai.com/ads/measurement-pixel#control-measurement-consent) before initialization.

### 3. Send a purchase event

After installing and initializing the Pixel, call `measure` when a purchase completes:

```typescript
oaiq(
  "measure",
  "order_created",
  {
    type: "contents",
    amount: 8900,
    currency: "USD",
  },
  { event_id: "order_12345" }
);
```


This example records an $89.00 purchase. Event amounts use the currency's standard minor unit: `8900` for USD 89.00, or `8900` for JPY 8,900.

Use the actual order ID or another unique event ID. Keep it the same if you also send this purchase from your server. Confirm receipt using Monitoring Events.

For other actions and their event data, see [Supported Events](https://developers.openai.com/ads/supported-events).

## Conversions API Setup

Use the Conversions API to send events from your server. You need a data source's Pixel ID and a Conversions API key for the same ad account.

Create or retrieve a source using the endpoints in Pixel Setup. If you only send server events, you can skip browser installation.

### 1. Create a Conversions API key

Use your Advertiser API key to provision a key for sending events:

```bash
curl -X POST "https://api.ads.openai.com/v1/conversions/api_keys" \
  -H "Authorization: Bearer ${OPENAI_ADS_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Acme server events"
  }'
```

Store the returned `api_key` securely and use it as `${OPENAI_CONVERSIONS_API_KEY}`. This key authenticates event requests to `bzr.openai.com`; continue using your Advertiser API key for setup and management requests to `api.ads.openai.com`.

### 2. Send an event

The following example sends a test purchase with the current timestamp. Set `${PIXEL_ID}` and `${OPENAI_CONVERSIONS_API_KEY}` before running it. In your integration, use the actual time the action occurred, in Unix milliseconds.

```bash
EVENT_TIMESTAMP_MS="$(date +%s)000"

curl -X POST "https://bzr.openai.com/v1/events?pid=${PIXEL_ID}" \
  -H "Authorization: Bearer ${OPENAI_CONVERSIONS_API_KEY}" \
  -H "Content-Type: application/json" \
  -d @- <<JSON
{
  "events": [
    {
      "id": "order_12345",
      "type": "order_created",
      "timestamp_ms": ${EVENT_TIMESTAMP_MS},
      "action_source": "web",
      "source_url": "https://shop.example.com/checkout/confirmation",
      "data": {
        "type": "contents",
        "amount": 8900,
        "currency": "USD"
      }
    }
  ]
}
JSON
```

Use a unique ID for each action and reuse it when retrying the same event. The purchase amount follows the same minor-unit convention as the Pixel example.

To validate a request without saving events, add `"validate_only": true` at the request's top level. Validation-only requests do not appear in event monitoring.

### 3. Include matching information

When an ad click supplies an `oppref` identifier, capture it and include the original value as `oppref` on the server event. The Conversions API does not capture this value automatically.

You can also include supported customer information to improve matching. Follow the [Conversions API user-data guidance](https://developers.openai.com/ads/conversions-api#send-user-data) for normalization and hashing before sending identifiers.

### Use the Pixel and Conversions API together

For a purchase sent through both integrations, use:

- The same Pixel ID.
- The same event name, such as `order_created`.
- The same event ID: Pixel `event_id` and Conversions API `id`.

The examples use `order_12345` in both places. For custom events, also use the same `custom_event_name`. These shared values allow deduplication, so the same action is not counted twice.

See the [Conversions API reference](https://developers.openai.com/ads/conversions-api) for batching, supported event fields, and request validation rules.

## Conversion Events

Create a conversion event setting to define an action you want to measure for campaigns. For standard events, you can also use the setting as the optimization goal for a conversion-optimized campaign.

Sending an event and creating a setting are separate steps: a setting selects an event from a source; it does not send events itself.

Use a standard event when one describes the action. For example, use `order_created` for a purchase or `lead_created` for a lead submission. Use a custom event for an action that has no suitable standard event.

### Define a standard conversion event

This setting measures purchases from the Acme website:

```bash
curl -X POST "https://api.ads.openai.com/v1/conversions/event_settings" \
  -H "Authorization: Bearer ${OPENAI_ADS_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Acme purchases",
    "event_type": "order_created",
    "attribution_window_days": 30,
    "source_ids": ["cds_123"]
  }'
```

Use the source's `id` in `source_ids`, not its `pixel_id`. Select one source per setting.

The example uses a 30-day click attribution window: the time after an eligible ad click during which a conversion can be credited to it. Use `30` for this setup.

Save the returned setting `id` and use it in place of `ces_123` when connecting campaigns.

### Define a custom conversion event

Send the custom event through your integration before checking that it arrives. For example, after initializing the Pixel:

```typescript
oaiq(
  "measure",
  "custom",
  { type: "custom" },
  {
    custom_event_name: "quote_requested",
    event_id: "quote_12345",
  }
);
```


Create a setting with the same custom event name:

```bash
curl -X POST "https://api.ads.openai.com/v1/conversions/event_settings" \
  -H "Authorization: Bearer ${OPENAI_ADS_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Acme quote requests",
    "event_type": "custom",
    "custom_event_name": "quote_requested",
    "attribution_window_days": 30,
    "source_ids": ["cds_123"]
  }'
```

Save this setting's `id` as well; the campaign example below uses `ces_456`. Keep the custom event name consistent across event sending and the setting.

See [Supported Events](https://developers.openai.com/ads/supported-events) for event names and data shapes, and the [Conversion Setup reference](https://developers.openai.com/ads/api-reference/conversion-setup) for setting fields.

## Monitoring Events

Use recent events to confirm that your Pixel or server integration is sending data to the intended source. Check soon after triggering an action on your website or sending a server event.

```bash
curl -G "https://api.ads.openai.com/v1/conversions/events" \
  -H "Authorization: Bearer ${OPENAI_ADS_API_KEY}" \
  --data-urlencode "pid=${PIXEL_ID}" \
  --data-urlencode "limit=50"
```

This endpoint returns a sample of recent events from roughly the last 15 minutes. It is useful for testing and troubleshooting; use Insights for attributed conversion reporting and historical results.

Check that the event type, source, and integration channel match your test. Browser events use `pixel_sdk`; server events use `server_to_server`.

## Connecting Events to Campaigns

Attach conversion event settings to a campaign to measure its outcomes. Clicks and impressions campaigns can track conversions without changing their objective. A conversion-optimized campaign uses its selected conversion event as the optimization goal.

### 1. Find the event setting

List the settings in your account:

```bash
curl "https://api.ads.openai.com/v1/conversions/event_settings" \
  -H "Authorization: Bearer ${OPENAI_ADS_API_KEY}"
```

Choose the setting for the intended action and source. Use the setting's `id` in `conversion_event_setting_ids`.

### 2. Attach it when creating a campaign

This example creates a paused clicks campaign that tracks purchases. It uses a US target and a daily budget of USD 50.00 for an account billed in USD. Choose the targeting and budget appropriate to your account.

```bash
curl -X POST "https://api.ads.openai.com/v1/campaigns" \
  -H "Authorization: Bearer ${OPENAI_ADS_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Acme website campaign",
    "status": "paused",
    "bidding_type": "clicks",
    "conversion_event_setting_ids": ["ces_123"],
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

Campaign budgets use micros: one million micros equals one unit of the account currency. Event amounts use minor units, as shown in the purchase examples.

### Add events to an existing campaign

For a clicks or impressions campaign, retrieve its current configuration before changing the attached settings:

```bash
curl "https://api.ads.openai.com/v1/campaigns/cmpn_123" \
  -H "Authorization: Bearer ${OPENAI_ADS_API_KEY}"
```

Send the complete list of settings you want to keep. This example retains purchases and adds quote requests:

```bash
curl -X POST "https://api.ads.openai.com/v1/campaigns/cmpn_123" \
  -H "Authorization: Bearer ${OPENAI_ADS_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "conversion_event_setting_ids": ["ces_123", "ces_456"]
  }'
```

Updating `conversion_event_setting_ids` replaces the list. Include any existing settings you want to retain.

### Optimize for conversions

To create a conversion-optimized campaign, set `bidding_type` to `conversions` and attach exactly one active standard conversion event setting at creation. Custom events cannot be used for conversion optimization.

The campaign objective cannot be changed after creation. For a conversion-optimized campaign, the selected event setting also cannot be changed after creation. Choose the action before creating the campaign.

For the full bidding setup, see [Conversion-Optimized Campaigns](https://developers.openai.com/ads/conversion-optimized-campaigns).