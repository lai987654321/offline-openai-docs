# Insights

> For the complete documentation index, see [llms.txt](/llms.txt). Markdown versions of documentation pages are available by appending `.md` to the page URL.

## Endpoints

Use one of the four `GET` endpoints for general delivery insights. Each returns
the same top-level response shape, with IDs, metadata, and metrics appropriate
to its scope.

- `GET /ad_account/insights`
- `GET /campaigns/{campaign_id}/insights`
- `GET /ad_groups/{ad_group_id}/insights`
- `GET /ads/{ad_id}/insights`

Use `POST /conversions/insights` for goal conversion totals and optional attributed event details.

## Conversion insights

Use `POST /v1/conversions/insights` to retrieve campaign goal conversion counts and, optionally, attributed standard and custom event metrics. Goal counts include click-through and view-through conversions within the selected reporting windows. Events do not need to be campaign goals to appear in the optional event details.

### Request body

| Field                                  | Values and behavior                                                                                                                                                                                                                                                                                                          |
| -------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `aggregation_level`                    | Required. `campaign`, `ad_group`, or `ad`.                                                                                                                                                                                                                                                                                   |
| `time_ranges`                          | Required array containing exactly one JSON-encoded time-range object. Use full days in the account's timezone, with an exclusive end, covering at most 365 days.                                                                                                                                                             |
| `time_granularity`                     | `none` (default) for period totals, or `daily`.                                                                                                                                                                                                                                                                              |
| `entity_ids`                           | Nonempty list of entity IDs at the selected aggregation level. Required when `group_by_entity` is `true`; omit when `group_by_entity` is `false` to report across the account.                                                                                                                                               |
| `group_by_entity`                      | Defaults to `true`. Set to `false` to combine the selected entities for each date or breakdown, using the ad account ID as `entity_id`.                                                                                                                                                                                      |
| `breakdown`                            | `country`, `device`, or `null` (default).                                                                                                                                                                                                                                                                                    |
| `attribution_time_basis`               | `ad_event_time` (default) groups and filters by the attributed ad interaction's date; `conversion_time` uses the conversion date and has limited non-goal event coverage.                                                                                                                                                    |
| `attribution_window_days`              | Click window: `7`, `14`, or `30`. Omitted or `null` defaults to `30`.                                                                                                                                                                                                                                                        |
| `view_through_attribution_window_days` | View window: `0` to exclude views, or `1` for one day. Omitted or `null` defaults to `1`.                                                                                                                                                                                                                                    |
| `include`                              | Omit or send `[]` for summary rows only. Send `["attributed_events"]` to add nested event details without changing the reporting clock, windows, or metric values for matching summary rows.                                                                                                                                 |
| `event_names`                          | Optional selector requiring `include: ["attributed_events"]`. Omit for all events, or provide 1–500 names containing at least one non-whitespace character of up to 256 characters each. Names match exactly, and the API removes duplicates. This filters nested details only; goal counts and summary sales are unchanged. |
| `include_zero_rows`                    | Defaults to `true`. With the event expansion and `false`, retain rows with a nonzero goal count, summary sales amount, or selected event count. A sales-bearing row remains present even when its selected event details are empty.                                                                                          |

The click and view defaults apply independently. These options select the report's attribution windows; they do not change campaign conversion goals or optimization settings. If an outcome is eligible for both click-through and view-through attribution, the click takes precedence.

An `event_names` entry must be configured in the account's conversion event settings, including archived settings, or present in its published received-event history. Validation covers the account independently of the requested entities and dates. Newly received events without conversion settings can be selected after their history is published; retained history is not an all-time event registry. A recognized event can have no attributed activity in the requested report.

Unknown names, an empty `event_names` array, `null`, or an event selector without the expansion return HTTP 400. Unsupported reporting windows also return HTTP 400.

### Response

The response contains `object: "list"`, `data`, `count`, and `account_currency`. `count` is the number of summary rows in `data`, not the number of conversions or nested events.

| Summary field                                           | Meaning                                                                                                                                                                           |
| ------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `entity_id`                                             | Entity ID, or the ad account ID when `group_by_entity` is `false`.                                                                                                                |
| `date`, `country`, `device`                             | Present when applicable to the requested daily granularity or breakdown.                                                                                                          |
| `conversions`                                           | Goal conversions from clicks plus views within the selected windows.                                                                                                              |
| `click_through_conversions`, `view_through_conversions` | Goal counts by attribution type. The view count is zero when the view window is `0`.                                                                                              |
| `order_created_attributed_sales`                        | Attributed purchase value across goal and non-goal `order_created` events, returned as an unrounded decimal string or `null` when unavailable.                                    |
| `order_created_attributed_sales_currency`               | Currency for summary sales.                                                                                                                                                       |
| `attributed_events`                                     | Present only when requested in `include`. Contains event metrics for the summary row's entity, date, and breakdown. An empty array means no matching event details were returned. |

Each nested event includes `entity_id`, `event_name`, `event_kind` (`standard` or `custom`), `attributed_event_count`, `attributed_event_value_amount`, `attributed_event_value_count`, and `attributed_event_value_currency`. Event counts include goal and non-goal activity. Reporting event rows also provide click/view counts and `conversion_event_setting_breakdowns` for matched campaign goals; applicable date and segment fields identify the reporting scope. Unavailable event amounts and currencies are `null`.

Non-goal-only rows can have positive event counts or sales and zero `conversions`. A recognized but inactive event selection can yield `attributed_events: []` on a retained summary row. Empty event details do not confirm that historical data has finished processing.

Responses are limited to 2,000 summary rows and, when expanded, 2,000 event rows in total. Each event's goal-setting breakdown is also limited to 2,000 entries. Exceeding a limit returns HTTP 413 rather than a partial result. This endpoint has no pagination cursor: reduce the entity list, split the report into non-overlapping date ranges, or select fewer event names when event details exceed the limit.

### Campaign example

This request returns campaign goal totals for September 1–7, 2026, in an account using `America/New_York`. It uses the default ad-event time basis and 30-day click / 1-day view windows.

```bash
curl -sS -X POST "https://api.ads.openai.com/v1/conversions/insights" \
  -H "Authorization: Bearer $OPENAI_ADS_API_KEY" \
  -H "Content-Type: application/json" \
  --data '{
    "aggregation_level": "campaign",
    "time_ranges": ["{\"type\":\"unix_range\",\"start\":\"1788235200\",\"end\":\"1788840000\"}"],
    "entity_ids": ["cmpn_123"]
  }'
```

Replace the sample campaign ID with your own. This illustrative response has 7 click-through and 3 view-through goal conversions, for a total of 10:

```json
{
  "object": "list",
  "account_currency": "USD",
  "data": [
    {
      "entity_id": "cmpn_123",
      "conversions": 10,
      "click_through_conversions": 7,
      "view_through_conversions": 3,
      "order_created_attributed_sales": "0",
      "order_created_attributed_sales_currency": "USD"
    }
  ],
  "count": 1
}
```

See [Report goal and non-goal events](https://developers.openai.com/ads/reporting#report-goal-and-non-goal-events) for a complete event-expansion request and response.

## Terminology

| Term                             | Values                                                                                                                                                                                                                                                                                                                                                                                              | Meaning                                                                                                                                                                                                                                                                                                                                                                                                     |
| -------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `{aggregation_level}`            | `ad_account`, `campaign`, `ad_group`, `ad`                                                                                                                                                                                                                                                                                                                                                          | Public row entities. The endpoint sets scope; `aggregation_level` chooses the row entity inside that scope.                                                                                                                                                                                                                                                                                                 |
| `time_granularity`               | `hourly`, `daily`, `monthly`, `none`                                                                                                                                                                                                                                                                                                                                                                | Bucket size. `none` returns one bucket for the full requested window.                                                                                                                                                                                                                                                                                                                                       |
| `segments[]`                     | `product`, `country`, `device`, `platform`                                                                                                                                                                                                                                                                                                                                                          | Optional extra breakdown dimension. `{segment}` below means the requested segment value.                                                                                                                                                                                                                                                                                                                    |
| `{entity}`                       | The row `{aggregation_level}` or requested `{segment}`                                                                                                                                                                                                                                                                                                                                              | Entity named in `override_segment_group_order[]`. Use it when requesting grouped metrics in a segmented request.                                                                                                                                                                                                                                                                                            |
| `{metric}`                       | `impressions`, `clicks`, `spend`, `ctr`, `cpc`, `cpm`                                                                                                                                                                                                                                                                                                                                               | Aggregated numeric fields.                                                                                                                                                                                                                                                                                                                                                                                  |
| `{aggregation_level}.id`         | `ad_account.id`, `campaign.id`, `ad_group.id`, `ad.id`                                                                                                                                                                                                                                                                                                                                              | Canonical aggregation-level ID fields. They are valid when that aggregation level is present in the row.                                                                                                                                                                                                                                                                                                    |
| `{aggregation_level}.{metric}`   | `campaign.impressions`, `ad.clicks`, `ad_group.spend`                                                                                                                                                                                                                                                                                                                                               | Metric for the row aggregation level. For default rows, use `{aggregation_level}.{metric}`. In segmented requests, grouped metrics can name the entity or segment in `override_segment_group_order[]`.                                                                                                                                                                                                      |
| `{aggregation_level}.{metadata}` | `ad_account.name`, `ad_account.url`, `ad_account.budget.lifetime`, `ad_account.budget.daily`; `campaign.name`, `campaign.description`, `campaign.status`, `campaign.start_time`, `campaign.end_time`, `campaign.budget.lifetime`, `campaign.budget.daily`; `ad_group.name`, `ad_group.description`, `ad_group.status`; `ad.title`, `ad.copy`, `ad.link`, `ad.name`, `ad.status`, `ad.review_status` | Canonical aggregation-level metadata fields. They are valid when that aggregation level is present in the row.                                                                                                                                                                                                                                                                                              |
| `{segment}.{metric}`             | `product.impressions`, `country.clicks`, `device.spend`, `platform.impressions`                                                                                                                                                                                                                                                                                                                     | Metric for the requested segment group. Valid only when the matching `segments[]` value is present.                                                                                                                                                                                                                                                                                                         |
| `{segment}.{metadata}`           | `product.feed_id`, `product.item_id`, `product.title`, `product.description`, `product.body`, `product.target_url`, `product.image_url`, `product.brand`, `product.seller_name`, `product.price`, `product.availability`; `country.name`; `device.type`                                                                                                                                             | Canonical segment metadata fields. Valid only when the matching `segments[]` value is present.                                                                                                                                                                                                                                                                                                              |
| `platform`                       | See [Platform breakdown](#platform-breakdown).                                                                                                                                                                                                                                                                                                                                                      | Canonical platform field. Valid only with `segments[]=platform`.                                                                                                                                                                                                                                                                                                                                            |
| `metadata.{field}`               | `metadata.readable_time`, `metadata.timezone`                                                                                                                                                                                                                                                                                                                                                       | Report metadata. The response returns flat keys such as `readable_time` and `timezone`.                                                                                                                                                                                                                                                                                                                     |
| `{product}.{id}`                 | `product.feed_id`, `product.item_id`, `product.feed_item_id`                                                                                                                                                                                                                                                                                                                                        | Use `product.feed_id` and `product.item_id` to project identity. Use `product.feed_item_id` only in `filters[]` for an exact feed/item pair.                                                                                                                                                                                                                                                                |
| `filters[].operator`             | `IN`, `GREATER_THAN`, `LESS_THAN`                                                                                                                                                                                                                                                                                                                                                                   | Filter operators. `IN` is for equality-style filters. `GREATER_THAN` and `LESS_THAN` are for numeric thresholds.                                                                                                                                                                                                                                                                                            |
| `sort[].direction`               | `asc`, `desc`                                                                                                                                                                                                                                                                                                                                                                                       | Sort order.                                                                                                                                                                                                                                                                                                                                                                                                 |
| `sort[].field`                   | `{aggregation_level}.{metric}`; `{entity}.{metric}` for a segmented request; `{aggregation_level}.id`; sortable `{aggregation_level}.{metadata}`; sortable `{segment}.{metadata}`                                                                                                                                                                                                                   | Canonical sort keys. The field must be valid for the current row shape.                                                                                                                                                                                                                                                                                                                                     |
| `includes[]`                     | `zero_impression_items`, `zero_impression_products`                                                                                                                                                                                                                                                                                                                                                 | Optional zero-row expansions. See [Includes](#includes) for when each value works.                                                                                                                                                                                                                                                                                                                          |
| `time_ranges[].type`             | `unix_range`, `hour_range`, `date_range`                                                                                                                                                                                                                                                                                                                                                            | Time-range object type. `unix_range` uses `start` and `end` Unix seconds. `hour_range` uses local `since` and `until` values in `YYYY-MM-DDTHH`. `date_range` uses local `since` and inclusive `until` values in `YYYY-MM-DD`; `until` normalizes to the following local midnight. `hour_range` and `date_range` can include an IANA time zone in `timezone`; otherwise, they use the ad account time zone. |

## Request parameters

All query parameters are optional.

| Parameter                              | Type       | Value shape                          | Rules                                                                                                                                                                                                                                |
| -------------------------------------- | ---------- | ------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `attribution_window_days`              | `integer`  | `7`, `14`, or `30`                   | Click window in days. Defaults to `30`.                                                                                                                                                                                              |
| `view_through_attribution_window_days` | `integer`  | `0` or `1`                           | View window in days. Defaults to `1`; `0` excludes views.                                                                                                                                                                            |
| `attribution_time_basis`               | `string`   | `ad_event_time` or `conversion_time` | Defaults to `ad_event_time`: filter and group attribution by ad interaction date. `conversion_time` uses conversion date.                                                                                                            |
| `time_granularity`                     | `string`   | One `time_granularity` value         | Default `daily`. See [Terminology](#terminology) for bucket behavior.                                                                                                                                                                |
| `aggregation_level`                    | `string`   | One public `{aggregation_level}`     | Set the row entity inside the endpoint scope. Each endpoint supports its own entity level and lower levels in the hierarchy `ad_account` > `campaign` > `ad_group` > `ad`.                                                           |
| `time_ranges`                          | `string[]` | One JSON-encoded time-range object   | Restrict the report window. Include at least one bound. Bounds must be within the past 5 years and cannot be in the future. The API normalizes them to valid full-hour boundaries.                                                   |
| `fields`                               | `string[]` | Repeated canonical field names       | Project selected fields; this changes returned columns, not row grouping. When omitted, the `fields` parameter defaults to `impressions`, includes `readable_time` for bucketed results, and includes the row entity's default name. |
| `filters`                              | `string[]` | JSON-encoded filter objects          | Restrict which rows survive. See [Filters](#filters).                                                                                                                                                                                |
| `sort`                                 | `string[]` | JSON-encoded sort objects            | Order rows before pagination. See [Sorts](#sorts).                                                                                                                                                                                   |
| `segments`                             | `string[]` | At most one `{segment}`              | Add one extra breakdown dimension. See [Segments](#segments).                                                                                                                                                                        |
| `override_segment_group_order`         | `string[]` | Row entity plus requested segment    | Change grouped metric meaning by reordering groups. See [Segments](#segments).                                                                                                                                                       |
| `includes`                             | `string[]` | At most one include value            | Expand results with supported zero rows. See [Includes](#includes).                                                                                                                                                                  |
| `limit`                                | `integer`  | `1` through `2000`                   | Default `20`. Caps rows returned in one page after filters and sorting are applied.                                                                                                                                                  |
| `before`                               | `string`   | Previous-page cursor                 | Page backward through the current row order. Send only one cursor at a time; use the previous page's `first_id`.                                                                                                                     |
| `after`                                | `string`   | Next-page cursor                     | Page forward through the current row order. Send only one cursor at a time; use the previous page's `last_id`.                                                                                                                       |

Attribution defaults apply independently. The settings affect conversion and sales metrics and their derived rates, without changing delivery metrics or campaign goals. GET `conversions` includes click-through plus view-through goal conversions; `post_click_cvr` uses only click-through conversions. For matching totals with [conversion insights](#conversion-insights), use the same entities, dates, windows, and time basis.

Requests for conversion or sales metrics must use full days in the account's timezone and span at most 365 days, including period totals. Hotel Insights rejects explicit attribution settings.

`fields[]` uses canonical names, but many response fields serialize as flat
wire keys, such as `campaign.id` to `campaign_id`,
`metadata.readable_time` to `readable_time`, and `product.feed_id` to
`product_feed_id`.

### Filters

| Parameter            | Value shape                                                | Rules                                                                                                                                                                                                    | Example                                                        |
| -------------------- | ---------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------- |
| `filters[]`          | JSON-encoded objects with `field`, `operator`, `value`     | Repeat `filters[]` to combine filters with `AND`.                                                                                                                                                        | `{"field":"campaign.id","operator":"IN","value":["cmpn_101"]}` |
| `filters[].field`    | One canonical field name from [Terminology](#terminology)  | The field must be valid for the current row shape. Use `product.feed_item_id` only for an exact feed/item pair filter with JSON-string `IN` values shaped like `{"feed_id":"feed_1","item_id":"sku_1"}`. | `campaign.id` or `ad.clicks`                                   |
| `filters[].operator` | `IN`, `GREATER_THAN`, `LESS_THAN`                          | Use `IN` for resource, segment, or metadata equality. Use `GREATER_THAN` or `LESS_THAN` for numeric metadata or grouped metric thresholds.                                                               | `IN` or `GREATER_THAN`                                         |
| `filters[].value`    | An array of strings or a number, depending on the operator | The value shape must match the operator.                                                                                                                                                                 | `["cmpn_101"]` or `10`                                         |

### Sorts

| Parameter          | Value shape                                             | Rules                                           | Example                                    |
| ------------------ | ------------------------------------------------------- | ----------------------------------------------- | ------------------------------------------ |
| `sort[]`           | JSON-encoded objects                                    | Repeat `sort[]` with `field` and `direction`.   | `{"field":"ad.clicks","direction":"desc"}` |
| `sort[].field`     | One canonical sort key from [Terminology](#terminology) | Use a sort key valid for the current row shape. | `ad.clicks` or `product.title`             |
| `sort[].direction` | One `sort[].direction` value                            | Use `asc` or `desc`.                            | `desc`                                     |

### Segments

#### Segment rules

| Parameter                        | Rules                                                                                   |
| -------------------------------- | --------------------------------------------------------------------------------------- |
| `segments[]`                     | Add one optional breakdown dimension for enabled ad accounts.                           |
| `time_granularity`               | Segmented requests support `none`, `daily`, and `monthly`.                              |
| Segment fields                   | Request fields only for the selected segment.                                           |
| `override_segment_group_order[]` | Include the row's `aggregation_level` and the requested segment exactly once, in order. |

#### Product example

| Goal                 | Request shape                                                                                             |
| -------------------- | --------------------------------------------------------------------------------------------------------- |
| Product breakdown    | Add `segments[]=product` to an `ad_account`, `campaign`, `ad_group`, or `ad` aggregation level.           |
| Product fields       | Project `product.*` fields from [Terminology](#terminology).                                              |
| Product-first rows   | Set `override_segment_group_order[]=product`, then `override_segment_group_order[]=<aggregation_level>`.  |
| Zero-impression rows | Add `includes[]=zero_impression_products`; see [Includes](#includes) for required order and availability. |

#### Platform breakdown

Add `segments[]=platform` to split delivery metrics by ChatGPT app or web
browser. Include `fields[]=platform` to return the platform value in each row.
Platform is a separate dimension from the `device` breakdown.

| Response value | Platform         |
| -------------- | ---------------- |
| `android_app`  | Android app      |
| `android_web`  | Android web      |
| `desktop_web`  | Desktop web      |
| `ios_app`      | iOS app          |
| `ios_web`      | iOS web          |
| `web`          | Web              |
| `unknown`      | Unknown platform |

Historical `web` rows keep combined web totals. They aren't split
retroactively into Android web, Desktop web, or iOS web rows.
The `web` value also includes web clients that aren't classified as Android web,
Desktop web, or iOS web.

The `unknown` value includes activity with missing or unrecognized client
information. Windows and macOS app activity currently appears under `unknown`.

A `platform` filter with `IN` and `web` includes all web platforms: `web`,
`android_web`, `desktop_web`, and `ios_web`. For example:

```json
{ "field": "platform", "operator": "IN", "value": ["web"] }
```

Use `android_web`, `desktop_web`, or `ios_web` to filter to specific web
platforms. These filters don't include historical `web` rows. Platform segments
support delivery metrics; conversions aren't supported.

To choose where a campaign can deliver, see
[Platform Targeting](https://developers.openai.com/ads/platform-targeting).

### Includes

`includes[]` expands the result set with supported zero-metric rows. It does
not change endpoint scope or `aggregation_level`.

| Include                    | Works when                                                                                                                                                                                                                                         | Adds                                                                       |
| -------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------- |
| `zero_impression_items`    | Default entity grouping only: do not send `segments[]`.                                                                                                                                                                                            | Entity rows that had zero impressions in the requested window.             |
| `zero_impression_products` | Product reporting only: the ad account has product segments and zero-impression products enabled, `segments[]=product`, `override_segment_group_order[]=product` first, and any `filters[]` use only product fields, entity ID fields, or metrics. | Configured product rows that had zero impressions in the requested window. |

## Examples



### Daily campaign totals across an ad account



This request scopes to one ad account, groups rows by campaign, and returns one
bucket per day. Because `aggregation_level=campaign`, each data row has a
`campaign_id` instead of an `ad_id`.

```bash
curl -sS -G "https://api.ads.openai.com/v1/ad_account/insights" \
  -H "Authorization: Bearer $OPENAI_ADS_API_KEY" \
  --data-urlencode 'time_granularity=daily' \
  --data-urlencode 'aggregation_level=campaign' \
  --data-urlencode 'fields[]=metadata.readable_time' \
  --data-urlencode 'fields[]=campaign.id' \
  --data-urlencode 'fields[]=campaign.name' \
  --data-urlencode 'fields[]=campaign.clicks' \
  --data-urlencode 'fields[]=campaign.impressions' \
  --data-urlencode 'fields[]=campaign.spend' \
  --data-urlencode 'time_ranges[]={"type":"unix_range","start":1777075200,"end":1777248000}'
```

Representative response:

```json
{
  "object": "list",
  "data": [
    {
      "id": "start=1777075200:end=1777161600:entity_id=cmpn_101",
      "start_time": 1777075200,
      "end_time": 1777161600,
      "readable_time": "2026-04-25",
      "campaign_id": "cmpn_101",
      "campaign_name": "Spring launch",
      "impressions": 1200,
      "clicks": 36,
      "spend": 18.42
    },
    {
      "id": "start=1777161600:end=1777248000:entity_id=cmpn_101",
      "start_time": 1777161600,
      "end_time": 1777248000,
      "readable_time": "2026-04-26",
      "campaign_id": "cmpn_101",
      "campaign_name": "Spring launch",
      "impressions": 980,
      "clicks": 29,
      "spend": 14.86
    }
  ],
  "count": 2,
  "first_id": "start=1777075200:end=1777161600:entity_id=cmpn_101",
  "last_id": "start=1777161600:end=1777248000:entity_id=cmpn_101",
  "has_more": false
}
```







### Change aggregation level from campaigns to ads



This uses the same ad-account scope as the previous example, but changes
`aggregation_level` from `campaign` to `ad`. The result now has one row per ad
per day, so campaign totals can fan out into multiple ad rows.

```bash
curl -sS -G "https://api.ads.openai.com/v1/ad_account/insights" \
  -H "Authorization: Bearer $OPENAI_ADS_API_KEY" \
  --data-urlencode 'time_granularity=daily' \
  --data-urlencode 'aggregation_level=ad' \
  --data-urlencode 'fields[]=metadata.readable_time' \
  --data-urlencode 'fields[]=campaign.id' \
  --data-urlencode 'fields[]=ad.id' \
  --data-urlencode 'fields[]=ad.name' \
  --data-urlencode 'fields[]=ad.clicks' \
  --data-urlencode 'fields[]=ad.impressions' \
  --data-urlencode 'time_ranges[]={"type":"unix_range","start":1777075200,"end":1777161600}'
```

Representative response:

```json
{
  "object": "list",
  "data": [
    {
      "id": "start=1777075200:end=1777161600:entity_id=ad_501",
      "start_time": 1777075200,
      "end_time": 1777161600,
      "readable_time": "2026-04-25",
      "campaign_id": "cmpn_101",
      "ad_id": "ad_501",
      "ad_name": "Blue shoes",
      "impressions": 700,
      "clicks": 22
    },
    {
      "id": "start=1777075200:end=1777161600:entity_id=ad_502",
      "start_time": 1777075200,
      "end_time": 1777161600,
      "readable_time": "2026-04-25",
      "campaign_id": "cmpn_101",
      "ad_id": "ad_502",
      "ad_name": "Red shoes",
      "impressions": 500,
      "clicks": 14
    }
  ],
  "count": 2,
  "first_id": "start=1777075200:end=1777161600:entity_id=ad_501",
  "last_id": "start=1777075200:end=1777161600:entity_id=ad_502",
  "has_more": false
}
```







### Filter, sort, and limit to the top ad in a campaign



`filters[]` removes rows that do not match `campaign.id`. `sort[]` ranks the
remaining ads by clicks, and `limit=1` keeps only the top row on the page.

```bash
curl -sS -G "https://api.ads.openai.com/v1/ad_account/insights" \
  -H "Authorization: Bearer $OPENAI_ADS_API_KEY" \
  --data-urlencode 'time_granularity=none' \
  --data-urlencode 'aggregation_level=ad' \
  --data-urlencode 'filters[]={"field":"campaign.id","operator":"IN","value":["cmpn_101"]}' \
  --data-urlencode 'sort[]={"field":"ad.clicks","direction":"desc"}' \
  --data-urlencode 'limit=1' \
  --data-urlencode 'fields[]=campaign.id' \
  --data-urlencode 'fields[]=ad.id' \
  --data-urlencode 'fields[]=ad.name' \
  --data-urlencode 'fields[]=ad.clicks' \
  --data-urlencode 'fields[]=ad.impressions' \
  --data-urlencode 'time_ranges[]={"type":"unix_range","start":1777075200,"end":1777680000}'
```

Representative response:

```json
{
  "object": "list",
  "data": [
    {
      "id": "start=1777075200:end=1777680000:entity_id=ad_501:sort=clicks.desc:sort_values=126",
      "start_time": 1777075200,
      "end_time": 1777680000,
      "campaign_id": "cmpn_101",
      "ad_id": "ad_501",
      "ad_name": "Blue shoes",
      "impressions": 4200,
      "clicks": 126
    }
  ],
  "count": 1,
  "first_id": "start=1777075200:end=1777680000:entity_id=ad_501:sort=clicks.desc:sort_values=126",
  "last_id": "start=1777075200:end=1777680000:entity_id=ad_501:sort=clicks.desc:sort_values=126",
  "has_more": true
}
```







### Product-segmented daily insights including zero-impression products



For ad accounts with segmented insights and zero-impression product expansion
enabled, use a product segment when you need product rows within the selected
entity level. This request groups products first, then the ad account, so the
response can include one configured product row even when that product had zero
impressions.

Synthetic zero-product rows omit unavailable metric fields from the response.

```bash
curl -sS -G "https://api.ads.openai.com/v1/ad_account/insights" \
  -H "Authorization: Bearer $OPENAI_ADS_API_KEY" \
  --data-urlencode 'time_granularity=daily' \
  --data-urlencode 'aggregation_level=ad_account' \
  --data-urlencode 'segments[]=product' \
  --data-urlencode 'override_segment_group_order[]=product' \
  --data-urlencode 'override_segment_group_order[]=ad_account' \
  --data-urlencode 'includes[]=zero_impression_products' \
  --data-urlencode 'fields[]=product.feed_id' \
  --data-urlencode 'fields[]=product.item_id' \
  --data-urlencode 'fields[]=product.title' \
  --data-urlencode 'fields[]=product.impressions' \
  --data-urlencode 'fields[]=product.clicks' \
  --data-urlencode 'time_ranges[]={"type":"unix_range","start":1777075200,"end":1777161600}'
```

Representative response:

```json
{
  "object": "list",
  "data": [
    {
      "id": "start=1777075200:end=1777161600:entity_id=v2ad_account_id%3Dadacct_123%7Cproduct_feed_id%3Dfeed_1%7Citem_id%3Dsku_1",
      "start_time": 1777075200,
      "end_time": 1777161600,
      "product_feed_id": "feed_1",
      "item_id": "sku_1",
      "product_title": "Blue shoes",
      "product_impressions": 240,
      "product_clicks": 9
    },
    {
      "id": "start=1777075200:end=1777161600:entity_id=v2ad_account_id%3D%3Cnull%3E%7Cproduct_feed_id%3Dfeed_1%7Citem_id%3Dsku_2",
      "start_time": 1777075200,
      "end_time": 1777161600,
      "product_feed_id": "feed_1",
      "item_id": "sku_2",
      "product_title": "Green shoes"
    }
  ],
  "count": 2,
  "first_id": "start=1777075200:end=1777161600:entity_id=v2ad_account_id%3Dadacct_123%7Cproduct_feed_id%3Dfeed_1%7Citem_id%3Dsku_1",
  "last_id": "start=1777075200:end=1777161600:entity_id=v2ad_account_id%3D%3Cnull%3E%7Cproduct_feed_id%3Dfeed_1%7Citem_id%3Dsku_2",
  "has_more": false
}
```