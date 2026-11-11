# Location Targeting

> For the complete documentation index, see [llms.txt](/llms.txt). Markdown versions of documentation pages are available by appending `.md` to the page URL.

Use location targeting to choose the countries, regions, or markets where your ads
can deliver. Look up the locations you want, copy their location IDs, then pass
those IDs when you create or update a campaign.

For the other targeting options, see [Campaign Targeting](https://developers.openai.com/ads/campaign-targeting).

If you do not provide location targeting, the campaign can target all available
locations.

## Available locations

Use `/geo_lookup/search` to find locations currently available for targeting.
The response returns the location `id`, display `name`, `canonical_name`,
`country_code`, `type`, `parent_id`, and `parent_country`, plus `region_code` when
available.

```bash
curl -G "https://api.ads.openai.com/v1/geo_lookup/search" \
  -H "Authorization: Bearer $OPENAI_ADS_API_KEY" \
  --data-urlencode "q=San Francisco" \
  --data-urlencode "limit=5"
```

```json
{
  "count": 1,
  "query": "San Francisco",
  "results": [
    {
      "id": "3000194",
      "type": "market",
      "canonical_name": "San Francisco - Oakland - San Jose, United States",
      "country_code": "US",
      "name": "San Francisco - Oakland - San Jose",
      "parent_id": null,
      "parent_country": "United States"
    }
  ]
}
```

You can also download the current location catalog as a CSV:

[{"Download OpenAI Ads locations"}](https://developers.openai.com/ads/openai-geotargets.csv)

## Campaign creation

Create a campaign with `targeting.locations.include`. Each item only needs the
location `id`; the API expands the saved campaign with the matching location
details.

```bash
curl -X POST "https://api.ads.openai.com/v1/campaigns" \
  -H "Authorization: Bearer $OPENAI_ADS_API_KEY" \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: campaign-targeting-example-1" \
  -d '{
    "name": "West Coast launch",
    "status": "paused",
    "budget": {
      "lifetime_spend_limit_micros": 25000000
    },
    "bidding_type": "clicks",
    "targeting": {
      "locations": {
        "include": [
          { "id": "2000043" },
          { "id": "3000194" },
          { "id": "3000001" }
        ]
      }
    }
  }'
```

In this example:

| Location ID | Meaning                                           | Category |
| ----------- | ------------------------------------------------- | -------- |
| `2000043`   | California, United States                         | region   |
| `3000194`   | San Francisco - Oakland - San Jose, United States | market   |
| `3000001`   | New York, United States                           | market   |

Use `status: "paused"` while you are validating campaign setup. Switch the
campaign to `active` when the campaign, ad groups, and ads are ready to serve.