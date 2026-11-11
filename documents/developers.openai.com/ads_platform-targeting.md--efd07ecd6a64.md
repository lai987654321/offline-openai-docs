# Platform Targeting

> For the complete documentation index, see [llms.txt](/llms.txt). Markdown versions of documentation pages are available by appending `.md` to the page URL.

Use platform targeting to choose which ChatGPT apps and web browsers can show
your ads. For the other targeting options, see
[Campaign Targeting](https://developers.openai.com/ads/campaign-targeting).

## Supported platforms

Set `targeting.platforms.included` to choose the ChatGPT platforms where a
campaign can deliver. The API accepts these values:

| API value     | Platform    | Includes                                      |
| ------------- | ----------- | --------------------------------------------- |
| `android_app` | Android app | The native ChatGPT app on Android.            |
| `android_web` | Android web | ChatGPT in a web browser on Android.          |
| `desktop_web` | Desktop web | ChatGPT in a desktop web browser.             |
| `ios_app`     | iOS app     | The native ChatGPT app on iOS.                |
| `ios_web`     | iOS web     | ChatGPT in a web browser on iOS.              |
| `web`         | Web         | All web platforms, including mobile browsers. |

The existing `web` value continues to include all web platforms. Existing
campaigns that use `web` don't need to change. To target only specific web
platforms, use their individual values without `web`.

## Create a campaign for mobile browsers

This example creates a paused campaign that targets ChatGPT in Android and iOS
web browsers:

```bash
curl -X POST "https://api.ads.openai.com/v1/campaigns" \
  -H "Authorization: Bearer $OPENAI_ADS_API_KEY" \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: campaign-platform-targeting-example-1" \
  -d '{
    "name": "Mobile browser launch",
    "status": "paused",
    "budget": {
      "lifetime_spend_limit_micros": 25000000
    },
    "bidding_type": "clicks",
    "targeting": {
      "platforms": {
        "included": ["android_web", "ios_web"]
      }
    }
  }'
```

To also limit locations, include `targeting.locations` alongside
`targeting.platforms` in the same request. See
[Location Targeting](https://developers.openai.com/ads/location-targeting) for location IDs.

## Update or clear platform targeting

Use `POST /campaigns/{campaign_id}` with `targeting.platforms.included` to
replace the platform selection. A platform-only update preserves the campaign's
location and custom audience targeting.

On creation, omitting `targeting.platforms` or setting it to `null` adds no
platform restriction. On update, omitting `targeting.platforms` preserves the
existing selection. Set it to `null` to clear only the platform restriction:

```bash
curl -X POST "https://api.ads.openai.com/v1/campaigns/cmpn_101" \
  -H "Authorization: Bearer $OPENAI_ADS_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "targeting": {
      "platforms": null
    }
  }'
```

Don't use `{"platforms": {}}` or `{"platforms": {"included": []}}` to clear
the selection; both return HTTP `400`. The `included` array cannot be `null`.
Setting the entire `targeting` object to `null` also resets other targeting
criteria, so use `targeting.platforms: null` when you only want to clear platforms.