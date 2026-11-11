# Conversion Setup

> For the complete documentation index, see [llms.txt](/llms.txt). Markdown versions of documentation pages are available by appending `.md` to the page URL.

Use the Ads API to configure conversion measurement for the current ad account.
These endpoints create the resources that the JavaScript Pixel and Conversions
API use to send events.

Pixel management and Conversions API key creation must be enabled for the ad
account. If `/conversions/pixels` or `/conversions/api_keys` returns `404` with
`Not found`, contact your OpenAI partner representative. A `Client data source
not found` response from event-setting creation means that `source_ids`
references a source that does not exist in the current ad account.

## Create a pixel

Create a web conversion source and its Pixel ID.

`POST /conversions/pixels`

| Field         | Type   | Required | Notes                                          |
| ------------- | ------ | -------- | ---------------------------------------------- |
| `name`        | string | Yes      | A descriptive name from 3 to 1,000 characters. |
| `client_type` | string | Yes      | Use `web`.                                     |

```bash
curl -X POST "https://api.ads.openai.com/v1/conversions/pixels" \
  -H "Authorization: Bearer $OPENAI_ADS_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Acme website",
    "client_type": "web"
  }'
```

```json
{
  "id": "clidsrc_123",
  "client_type": "web",
  "name": "Acme website",
  "pixel_id": "134534..."
}
```

Use `id` as a `source_ids` value when you create an event setting. Use
`pixel_id` to initialize the JavaScript Pixel and when you send Conversions API
events. Web pixels created by this endpoint automatically use [automatic
advanced matching](https://developers.openai.com/ads/measurement-pixel#automatic-advanced-matching).

## Check recent Pixel events

Use the conversion event stream while testing a [JavaScript Pixel](https://developers.openai.com/ads/measurement-pixel)
integration. It returns up to 50 conversion events received from the Pixel SDK
during the previous 15 minutes.

> **Note:** The conversion event stream is available only to enabled accounts.
> If this endpoint returns `404` with `Not found`, contact your OpenAI partner
> representative.

`GET /conversions/events`

| Parameter | Type   | Required | Notes                                |
| --------- | ------ | -------- | ------------------------------------ |
| `pid`     | string | Yes      | Pixel ID returned by pixel creation. |

```bash
curl -X GET "https://api.ads.openai.com/v1/conversions/events?pid=<PIXEL-ID>" \
  -H "Authorization: Bearer $OPENAI_ADS_API_KEY"
```

```json
{
  "object": "list",
  "data": [
    {
      "action_source": "web",
      "api_channel": "pixel_sdk",
      "custom_event_name": null,
      "data_source_id": "cds_123",
      "event_data_json": "{\"type\":\"customer_action\"}",
      "event_timestamp_ms": 1787082318902,
      "event_type": "registration_completed",
      "received_at_ms": 1787082320225
    }
  ]
}
```

Use this endpoint to confirm that recent browser events reached OpenAI, not for
attribution or reporting. Use conversion insights for attributed conversion
totals. If more than 50 events arrive during the window, the response includes
only the 50 most recent events.

## Create a Conversions API key

Create a key that can send server-side events for the current ad account.

`POST /conversions/api_keys`

| Field  | Type   | Required | Notes                                          |
| ------ | ------ | -------- | ---------------------------------------------- |
| `name` | string | Yes      | A descriptive name from 3 to 1,000 characters. |

```bash
curl -X POST "https://api.ads.openai.com/v1/conversions/api_keys" \
  -H "Authorization: Bearer $OPENAI_ADS_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Acme production conversions"
  }'
```

```json
{
  "name": "Acme production conversions",
  "api_key": "<CONVERSIONS_API_KEY>"
}
```

> **Caution:** Store the returned key in a server-side secret manager. Never
> place it in browser code, client-visible environment variables, logs, or
> source control.

## Create an event setting

Create a conversion definition and connect it to one conversion source.

`POST /conversions/event_settings`

| Field                     | Type     | Required | Notes                                                        |
| ------------------------- | -------- | -------- | ------------------------------------------------------------ |
| `name`                    | string   | Yes      | Display name for the conversion.                             |
| `event_type`              | string   | Yes      | A [supported event](https://developers.openai.com/ads/supported-events), or `custom`.     |
| `custom_event_name`       | string   | Depends  | Required when `event_type` is `custom`.                      |
| `attribution_window_days` | integer  | Yes      | Use `30`.                                                    |
| `source_ids`              | string[] | Yes      | Exactly one conversion source ID returned by pixel creation. |

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

```json
{
  "id": "ces_123",
  "name": "Purchases",
  "event_type": "order_created",
  "custom_event_name": null,
  "attribution_window_days": 30,
  "ad_account_id": "adacct_123",
  "source_ids": ["clidsrc_123"],
  "sources": [
    {
      "id": "clidsrc_123",
      "name": "Acme website"
    }
  ],
  "campaigns": [],
  "archived": false,
  "version": 1
}
```

## List event settings

List conversion definitions for the current ad account.

`GET /conversions/event_settings`

| Parameter | Type    | Required | Notes                         |
| --------- | ------- | -------- | ----------------------------- |
| `limit`   | integer | No       | Between `1` and `500`.        |
| `after`   | string  | No       | Cursor for the next page.     |
| `before`  | string  | No       | Cursor for the previous page. |
| `order`   | string  | No       | `asc` or `desc`.              |

```bash
curl -X GET "https://api.ads.openai.com/v1/conversions/event_settings?limit=20&order=desc" \
  -H "Authorization: Bearer $OPENAI_ADS_API_KEY"
```

## Send events

After setup, use the returned Pixel ID and Conversions API key to implement
[server-side event delivery](https://developers.openai.com/ads/conversions-api). For browser measurement,
use the [JavaScript Pixel](https://developers.openai.com/ads/measurement-pixel). If both sources send the
same event, use a shared event ID so OpenAI processes it only once.