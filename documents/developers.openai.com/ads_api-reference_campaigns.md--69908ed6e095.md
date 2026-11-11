# Campaigns

> For the complete documentation index, see [llms.txt](/llms.txt). Markdown versions of documentation pages are available by appending `.md` to the page URL.

## List campaigns

List campaigns in the current ad account.

`GET /campaigns`

| Parameter | Type    | Required | Notes                              |
| --------- | ------- | -------- | ---------------------------------- |
| `limit`   | integer | No       | Between `1` and `500`. Default 20. |
| `after`   | string  | No       | Cursor for the next page.          |
| `before`  | string  | No       | Cursor for the previous page.      |
| `order`   | string  | No       | `asc` or `desc`.                   |

```bash
curl -X GET "https://api.ads.openai.com/v1/campaigns?limit=20&order=desc" \
  -H "Authorization: Bearer $OPENAI_ADS_API_KEY"
```

```json
{
  "object": "list",
  "data": [
    {
      "id": "cmpn_101",
      "created_at": 1735689600,
      "status": "active",
      "bidding_type": "impressions",
      "budget": {
        "lifetime_spend_limit_micros": 25000000
      },
      "conversion_event_setting_ids": [],
      "description": "Promote the new productivity bundle.",
      "end_time": 1738368000,
      "mode": null,
      "name": "Spring launch",
      "start_time": 1735689600,
      "targeting": {},
      "updated_at": 1735776000
    }
  ],
  "first_id": "cmpn_101",
  "last_id": "cmpn_101",
  "has_more": false
}
```

## Create a campaign

Create a campaign for the current ad account. The Ads belonging to a campaign will only show between the defined start and end time, and only in the locations specified in campaign targeting.

For location, platform, and custom audience targeting, see [Campaign Targeting](https://developers.openai.com/ads/campaign-targeting).

For the limited Hotel beta, use `feed_selection` with `inventory_type: "hotel"` and `schema_profile: "hotel_property_v1"`; omit `mode` and `product_feed_id`. Hotel campaigns require Clicks with manual CPC bidding and audience targeting for the entire United States. Omitted Hotel targeting defaults to the United States. See [Create Hotel ads](https://developers.openai.com/ads/hotel-feeds#create-hotel-ads) for the complete request and current restrictions.

### Defaults

If you omit `start_time`, the campaign has no delayed start. Delivery still requires active objects and the usual eligibility checks. Except for Hotel campaigns, omitting location targeting lets the campaign target all available locations.

Omitting `targeting.platforms` or setting it to `null` adds no platform restriction.

Note that time and currency fields will respect your account-set timezone and currency defaults.

`POST /campaigns`

| Field                                     | Type     | Required | Notes                                                                                     |
| ----------------------------------------- | -------- | -------- | ----------------------------------------------------------------------------------------- |
| `name`                                    | string   | Yes      | `3` to `1000` chars and must include a non-space character.                               |
| `description`                             | string   | No       | Campaign description.                                                                     |
| `start_time`                              | integer  | No       | Unix timestamp between `946684800` and `4102444800`.                                      |
| `end_time`                                | integer  | No       | Unix timestamp between `946684800` and `4102444800`.                                      |
| `status`                                  | string   | Yes      | `active` or `paused`.                                                                     |
| `budget.lifetime_spend_limit_micros`      | integer  | Yes      | Minimum `1000000`.                                                                        |
| `mode`                                    | string   | No       | Set to `product_feed` to create a [product-feed campaign](https://developers.openai.com/ads/product-feeds).            |
| `bidding_type`                            | string   | No       | `impressions`, `clicks`, or `conversions`. Defaults to `impressions`.                     |
| `conversion_event_setting_ids`            | string[] | No       | For `conversions`, exactly one active standard event setting ID from this account.        |
| `targeting.locations.include`             | object[] | No       | Included location IDs.                                                                    |
| `targeting.platforms.included`            | string[] | No       | ChatGPT platforms. See [Platform Targeting](https://developers.openai.com/ads/platform-targeting) for accepted values. |
| `targeting.custom_audiences.ids`          | string[] | No       | Ready audience IDs eligible for inclusion.                                                |
| `targeting.excluded_custom_audiences.ids` | string[] | No       | Ready audience IDs eligible for exclusion, including small audiences.                     |

See [Custom Audiences](https://developers.openai.com/ads/custom-audiences#include-or-exclude-audiences-in-a-campaign)
for audience matching, exclusions, and minimum-size requirements.

Check audiences with `GET /custom_audiences?intended_use=inclusion` or
`intended_use=exclusion` before using them. A ready small or empty audience can
be excluded, but it isn't automatically eligible for inclusion. If you include
and exclude audiences, the remaining population must still meet the minimum.
For an exclusion-only campaign, omit `targeting.custom_audiences`.

```bash
curl -X POST "https://api.ads.openai.com/v1/campaigns" \
  -H "Authorization: Bearer $OPENAI_ADS_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Spring launch",
    "description": "Promote the new productivity bundle.",
    "start_time": 1735689600,
    "end_time": 1738368000,
    "status": "active",
    "budget": {
      "lifetime_spend_limit_micros": 25000000
    },
    "targeting": {
      "locations": {
        "include": [{ "id": "2000043" }, { "id": "3000194" }]
      }
    }
  }'
```

```json
{
  "id": "cmpn_101",
  "created_at": 1735689600,
  "updated_at": 1735689600,
  "name": "Spring launch",
  "description": "Promote the new productivity bundle.",
  "status": "active",
  "start_time": 1735689600,
  "end_time": 1738368000,
  "budget": {
    "lifetime_spend_limit_micros": 25000000
  },
  "bidding_type": "impressions",
  "targeting": {
    "locations": {
      "include": [
        {
          "id": "2000043",
          "type": "region",
          "country_code": "US",
          "name": "California",
          "region_code": "US-CA"
        },
        {
          "id": "3000194",
          "type": "market",
          "country_code": "US",
          "name": "San Francisco - Oakland - San Jose",
          "region_code": null
        }
      ]
    }
  }
}
```

### Create a conversion-optimized campaign

To use oCPC, set `bidding_type` to `conversions` and pass exactly one active
standard conversion event setting from the current ad account. The event
setting must connect to one active conversion source. Custom event settings
cannot be optimization goals.

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

Conversion bidding must be enabled for the ad account. Product-feed campaigns
can use oCPC during the open beta. Use the same endpoint, set `mode` to
`product_feed`, and include the linked `product_feed_id`. You cannot change the
campaign objective or selected conversion event after creation. For the complete
setup flow, including the required ad-group bid configuration, see
[Conversion-Optimized Campaigns](https://developers.openai.com/ads/conversion-optimized-campaigns),
[Product Feeds](https://developers.openai.com/ads/product-feeds), and [API Partner
Setup](https://developers.openai.com/ads/api-partner-setup).

## Retrieve a campaign

Fetch one campaign by ID.

`GET /campaigns/{campaign_id}`

```bash
curl -X GET "https://api.ads.openai.com/v1/campaigns/cmpn_101" \
  -H "Authorization: Bearer $OPENAI_ADS_API_KEY"
```

## Update a campaign

Update a campaign with `POST`, not `PATCH` or `PUT`.

`POST /campaigns/{campaign_id}`

All fields are optional on update. If you include `budget`, send the full
budget object. `description`, `start_time`, `end_time`, and `targeting` can be
set to `null` to clear them. `status` accepts `active`, `paused`, or
`archived`. You cannot update `bidding_type`. For a conversion-optimized
campaign, you also cannot update `conversion_event_setting_ids`.

Omitting `targeting.platforms` preserves the existing platform selection.
Provide `targeting.platforms.included` to replace it, or set
`targeting.platforms` to `null` to clear only the platform restriction. Empty
platform objects and empty `included` arrays return HTTP `400`. See
[Update or clear platform targeting](https://developers.openai.com/ads/platform-targeting#update-or-clear-platform-targeting)
for an example.

Audience eligibility is validated again when you save targeting. A concurrent
membership update can return `409 custom_audience_mutation_conflict` without
applying the campaign edit. Wait for the audience operation to finish, retrieve
the current settings, and retry the intended edit if it is still appropriate.

```bash
curl -X POST "https://api.ads.openai.com/v1/campaigns/cmpn_101" \
  -H "Authorization: Bearer $OPENAI_ADS_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "description": "Updated launch window and budget.",
    "status": "paused",
    "budget": {
      "lifetime_spend_limit_micros": 30000000
    }
  }'
```

## Change state with dedicated actions

The Ads API also exposes explicit state transitions. Each endpoint returns the
updated campaign object. Paused campaigns won't deliver ads to customers. Only archive objects you have no further use for, as archiving isn't reversible.

- `POST /campaigns/{campaign_id}/activate`
- `POST /campaigns/{campaign_id}/pause`
- `POST /campaigns/{campaign_id}/archive`

```bash
curl -X POST "https://api.ads.openai.com/v1/campaigns/cmpn_101/pause" \
  -H "Authorization: Bearer $OPENAI_ADS_API_KEY"
```

```json
{
  "id": "cmpn_101",
  "created_at": 1735689600,
  "updated_at": 1735862400,
  "name": "Spring launch",
  "description": "Promote the new productivity bundle.",
  "status": "paused",
  "start_time": 1735689600,
  "end_time": 1738368000,
  "budget": {
    "lifetime_spend_limit_micros": 25000000
  },
  "bidding_type": "impressions"
}
```