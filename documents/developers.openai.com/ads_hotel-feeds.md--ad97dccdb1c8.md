# Hotel property feeds (limited beta)

> For the complete documentation index, see [llms.txt](/llms.txt). Markdown versions of documentation pages are available by appending `.md` to the page URL.

**Limited beta:** Hotel property feeds are available only to approved pilot advertisers. This is not an open beta. Field definitions, validation rules, and supported capabilities may change during the beta.

Create a Hotel feed in Ads Manager or through the Ads API, then upload a full snapshot of your properties. Each row describes one property, not a room, offer, or dated stay. This is the `hotel_property_v1` format; don't use the [Product feed schema](https://developers.openai.com/commerce/specs/file-upload/products) for a Hotel feed.

After ingestion, [query the properties](#query-hotel-items), [create Hotel ads](#create-hotel-ads), and [request an ad preview](#preview-a-hotel-ad) through the public Ads API.

## Before you start

You need an ad account approved for the limited beta and permission to manage its feeds. SFTP setup also requires permission to manage feed credentials. Prepare a UTF-8 CSV or tab-delimited TXT file using the [submission format](#submission-format), and replace example URLs with your property pages and images.

We strongly recommend including a [starting price](#pricing-and-categorization) (`base_price`) and complete [guest ratings](#guest-ratings) whenever available. These details help people assess price and guest experience, making your ad more informative and compelling.

Choose a setup method:

| Method         | Create the feed                                                 | Send the file                                                            |
| -------------- | --------------------------------------------------------------- | ------------------------------------------------------------------------ |
| Ads Manager    | Select Hotels when creating a feed.                             | Upload CSV or TXT, configure a hosted URL, or connect over SFTP.         |
| Public Ads API | Create a feed with the Hotel inventory type and schema profile. | Configure SFTP access through the API, then transfer the file over SFTP. |

Hosted URL setup and browser file upload are Ads Manager workflows; their UI endpoints aren't part of the public API instructions here. If Hotel options aren't available for your account, contact your OpenAI account team.

## Create and upload in Ads Manager

1. Open Ads Manager and select the approved ad account.
2. Open **Feeds**, select **Create Feed**, and choose **Hotels** as the inventory type.
3. Enter a feed name, continue to the upload-method selection, and choose **Upload CSV or TXT**, **Hosted URL**, or **SFTP connection**.
4. Create the feed and complete the selected source setup:

   | Source            | Setup                                                                                                                                                                           |
   | ----------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
   | Upload CSV or TXT | Select your full-snapshot file, review the preview, and submit the upload.                                                                                                      |
   | Hosted URL        | Enter the HTTPS file URL and, if required, HTTP Basic authentication credentials. Save the URL, then start a manual fetch or configure an available automatic refresh schedule. |
   | SFTP connection   | Generate a password or configure an SSH public key. Connect an SFTP client using the displayed connection details and upload the file.                                          |

5. Check **Upload History** for processing status and row diagnostics. Fix rejected rows and upload a corrected full snapshot.

Use the existing feed's actions to upload or refresh later snapshots; don't create a new feed for every update. Keep `hotel_id` values stable.

## Create and upload through the Ads API

Use an ad account-scoped Advertiser API key with permission to manage the approved account's feeds. Keep it on your server and provide it through `OPENAI_ADS_API_KEY`. See [Authentication](https://developers.openai.com/ads/api-reference/authentication).

### 1. Create the Hotel feed

Set both `inventory_type` and `schema_profile` explicitly. Omitting the Hotel selectors doesn't create a Hotel feed.

```bash
curl -X POST "https://api.ads.openai.com/v1/feeds" \
  -H "Authorization: Bearer ${OPENAI_ADS_API_KEY}" \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: hotel-feed-setup-001" \
  -d '{
    "name": "Harbor House hotels",
    "inventory_type": "hotel",
    "schema_profile": "hotel_property_v1"
  }'
```

Replace the example `Idempotency-Key` with a unique value for this feed-creation operation. Reuse that key and the same request body when retrying the operation; use a new key when creating a different feed. Hotel feed creation requires this header.

Save the returned `feed_id`. Replace `fd_123` in the following request with that ID.

### 2. Configure SFTP access

To generate password credentials:

```bash
curl -X POST "https://api.ads.openai.com/v1/feeds/fd_123/sftp_access" \
  -H "Authorization: Bearer ${OPENAI_ADS_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "authentication_method": "password"
  }'
```

Use the returned `connection_uri` and `password` in your SFTP client. Store the password securely; generating another password replaces the previous one.

For SSH-key authentication, send this body to the same endpoint instead, replacing `YOUR_SSH_PUBLIC_KEY` with the contents of your public-key file:

```json
{
  "authentication_method": "ssh_key",
  "ssh_public_key": "YOUR_SSH_PUBLIC_KEY"
}
```

Use the corresponding private key in your SFTP client. Don't send the private key to the API.

Credential setup replaces the existing authentication method: choosing a password removes configured SSH keys, and choosing an SSH key disables password authentication. Update any existing upload automation when you change credentials.

### 3. Transfer the file and check processing

Connect to the returned SFTP location. From your SFTP client's prompt, upload your prepared full snapshot, for example:

```text
put /path/to/hotels.csv hotels.csv
```

Place the file directly in the SFTP root, not a nested folder. File transfer and ingestion are separate: a successful upload doesn't mean that every property was accepted or can serve in an ad. Check the Hotel feed's **Upload History** in Ads Manager for processing results and diagnostics.

### 4. List Hotel feeds and uploads

Specify `inventory_type=hotel` when listing feeds or upload history. Both lists default to Product inventory when you omit this parameter.

```bash
curl -G "https://api.ads.openai.com/v1/feeds" \
  -H "Authorization: Bearer ${OPENAI_ADS_API_KEY}" \
  --data-urlencode "inventory_type=hotel"

curl -G "https://api.ads.openai.com/v1/feeds/uploads" \
  -H "Authorization: Bearer ${OPENAI_ADS_API_KEY}" \
  --data-urlencode "inventory_type=hotel" \
  --data-urlencode "feed_id=fd_123"
```

The upload-history request returns uploads for that feed. Omit `feed_id` to list Hotel uploads across the account.

## Query Hotel items

Use `POST /v1/feeds/{feed_id}/items/query` to inspect properties and try the filters you plan to save in an ad group. This endpoint supports Product and Hotel feeds and returns each inventory type's native fields. The existing `/products/query` endpoint is Product-specific.

```bash
curl -X POST "https://api.ads.openai.com/v1/feeds/fd_123/items/query" \
  -H "Authorization: Bearer ${OPENAI_ADS_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "filters": [
      {"field": "country", "operator": "in", "values": ["US"]}
    ],
    "limit": 20
  }'
```

The query returns current, non-deleted, non-expired items that are eligible for ads and match the filters. Review approval isn't required. A returned item might still be unavailable for an ad preview or ad delivery.

Example response, with property fields abbreviated:

```json
{
  "object": "list",
  "feed_id": "fd_123",
  "inventory_type": "hotel",
  "schema_profile": "hotel_property_v1",
  "data": [
    {
      "item_id": "hotel_001",
      "hotel_id": "hotel_001",
      "name": "Harbor House Hotel",
      "base_price": "149.00 USD"
    }
  ],
  "total_count": 3,
  "matched_count": 1,
  "first_id": "hotel_001",
  "last_id": "hotel_001",
  "has_more": false
}
```

Hotel records also include native fields such as `url`, `images`, `location`, `guest_ratings`, and `ads_metadata`. The JSON response uses nested objects and arrays; the [submission format](#submission-format) describes the flattened columns used in uploaded CSV and TXT files.

`total_count` counts eligible items before applying your filters; `matched_count` counts those matching the filters. Both counts cover the full result, before pagination. `limit` defaults to `20` and accepts values from `1` through `500`. When `has_more` is `true`, repeat the request with the same filters and pass the returned `last_id` unchanged as `after`. For `hotel_property_v1`, `item_id` equals `hotel_id`; IDs are scoped to a feed.

### Choose Hotel Set filters

A Hotel Set selects the properties an ad group can use from its campaign's feed. Use the same filters in `items/query` and the ad group's `feed_set.filters`.

| Field                | Operators                                                 | Example `values`                                |
| -------------------- | --------------------------------------------------------- | ----------------------------------------------- |
| `country`            | `in`, `not_in`                                            | `["US"]`                                        |
| `region`             | `in`, `not_in`                                            | `["[\"US\",\"California\"]"]`                   |
| `city`               | `in`, `not_in`                                            | `["[\"US\",\"California\",\"San Francisco\"]"]` |
| `category`           | `in`, `not_in`, `contains`, `not_contains`, `starts_with` | `["Hotel & Hospitality"]`                       |
| `ads_metadata.<key>` | `in`, `not_in`, `contains`, `not_contains`, `starts_with` | `["waterfront"]`                                |

Region and city values are JSON-encoded location paths. For a city without a region, use `null` for the middle element, such as `["US",null,"Example City"]`, then encode that array as a string in `values`.

All filter clauses must match. For `in`, any value within the clause can match. Matching is case-insensitive. Missing fields don't match negative filters. Use each field at most once; `contains`, `not_contains`, and `starts_with` each take one value. Send `"filters": []` to select the whole eligible feed.

Hotel filters support the fields in this table, rather than Product-only fields such as `brand` or `price`. Filtering by `hotel_id` isn't supported; use `ads_metadata` labels to define property groups. These filters select properties, not the audience locations where your campaign can deliver.

## Create Hotel ads

Create a campaign that selects the Hotel feed, an ad group that selects a Hotel Set, and one ad template for that group. Replace `fd_123`, `cmpn_123`, `adgrp_123`, and `ad_123` with the IDs returned by your requests.

The examples create paused objects with a $100 lifetime budget and a $1 click bid for a USD account. Use amounts appropriate to your account's currency and advertising plan. Replace the example idempotency keys for new operations, and reuse each key only when retrying the same request body.

### 1. Create the campaign

Use `feed_selection` with the Hotel inventory type and schema profile. Don't combine it with the legacy `mode` or `product_feed_id` fields.

```bash
curl -X POST "https://api.ads.openai.com/v1/campaigns" \
  -H "Authorization: Bearer ${OPENAI_ADS_API_KEY}" \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: hotel-campaign-001" \
  -d '{
    "name": "Harbor House hotels",
    "status": "paused",
    "enable_dynamic_creative": false,
    "budget": {"lifetime_spend_limit_micros": 100000000},
    "bidding_type": "clicks",
    "objective": "clicks",
    "billing_event_type": "click",
    "feed_selection": {
      "feed_id": "fd_123",
      "inventory_type": "hotel",
      "schema_profile": "hotel_property_v1"
    }
  }'
```

Save the returned campaign `id`. Hotel campaigns currently support the Clicks objective with manual cost-per-click (CPC) bidding and audience targeting for the entire United States. Omitting targeting on creation selects the United States. Geographic exclusions, narrower audience locations, and restrictive platform targeting aren't supported. You can omit `start_time` and `end_time`, or send `null`, when you don't need a schedule.

### 2. Create the ad group

Use `feed_set` for a Hotel Set and keep its feed ID equal to the campaign's selected feed. Don't use `product_set` for Hotel inventory. This example reuses the `country` filter from the item query to select properties in the United States.

```bash
curl -X POST "https://api.ads.openai.com/v1/ad_groups" \
  -H "Authorization: Bearer ${OPENAI_ADS_API_KEY}" \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: hotel-ad-group-001" \
  -d '{
    "campaign_id": "cmpn_123",
    "name": "US hotels",
    "status": "paused",
    "bidding_config": {
      "billing_event_type": "click",
      "strategy": "fixed_bid",
      "max_bid_micros": 1000000
    },
    "feed_set": {
      "feed_id": "fd_123",
      "inventory_type": "hotel",
      "schema_profile": "hotel_property_v1",
      "filters": [
        {"field": "country", "operator": "in", "values": ["US"]}
      ]
    }
  }'
```

Save the returned ad group `id`. Hotel ad groups require `fixed_bid`; automated bidding isn't supported. Use an empty `filters` array to select the feed without additional property filters.

### 3. Create the ad template

Hotel ads use `product_ad_template` and the existing `{{product.*}}` template names. Set `body` to `{{product.body}}` and `price` to `{{product.price}}`. The selected property supplies the image and destination, so omit `creative.file_id` and `creative.target_url`.

```bash
curl -X POST "https://api.ads.openai.com/v1/ads" \
  -H "Authorization: Bearer ${OPENAI_ADS_API_KEY}" \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: hotel-ad-001" \
  -d '{
    "ad_group_id": "adgrp_123",
    "name": "US hotel ad",
    "status": "paused",
    "creative": {
      "type": "product_ad_template",
      "title": "Stay at {{product.title}}",
      "body": "{{product.body}}",
      "price": "{{product.price}}"
    }
  }'
```

Save the returned ad `id`. Each feed ad group supports one template ad. A paused, submitted ad can be previewed; a draft-only ad can't.

Pausing is an example choice, not a Hotel requirement. To create active objects, set `"status": "active"` in all three creation requests. To activate these paused examples later, use `POST /ads/{ad_id}/activate`, `POST /ad_groups/{ad_group_id}/activate`, and `POST /campaigns/{campaign_id}/activate`. Active status doesn't bypass review, account readiness, or other delivery requirements.

## Preview a Hotel ad

Call `POST /v1/ads/{ad_id}/preview` without a request body. The server selects one property matching the ad group's saved Hotel Set; you can't pass a property ID or different filters to this endpoint.

```bash
curl -X POST "https://api.ads.openai.com/v1/ads/ad_123/preview" \
  -H "Authorization: Bearer ${OPENAI_ADS_API_KEY}"
```

Embed the returned `data[0].body` HTML. For example:

```json
{
  "data": [
    {
      "body": "<iframe src=\"https://ads.openai.com/previews/adprev_123?token=PREVIEW_TOKEN\" width=\"390\" height=\"320\" scrolling=\"no\" style=\"border: none;\"></iframe>"
    }
  ]
}
```

Hotel previews require a current, active, ads-eligible, review-approved property matching the saved Hotel Set. If no such property is available, the request returns HTTP `422`, even if `items/query` returns records. The card shows the property's starting price and guest rating when present; missing optional values are omitted. Property stars aren't guest review scores.

The signed link allows viewing without signing in and expires 24 hours after the snapshot is created. Repeated requests can reuse a snapshot without resetting its expiration. Keep the link private, and request a new preview after changing the ad or feed data. A saved preview doesn't check stay-date availability or guarantee ad delivery.

## Submission format

Submit a full snapshot as UTF-8 CSV or tab-delimited TXT. Include the properties you intend to advertise in the pilot, and keep each `hotel_id` stable between uploads.

The format combines ordinary columns, flattened columns, and JSON-encoded cells:

| Value         | CSV or TXT representation                                                               |
| ------------- | --------------------------------------------------------------------------------------- |
| Scalar fields | Ordinary columns such as `hotel_id`, `name`, or `base_price`.                           |
| Images        | A JSON array in the `images` cell.                                                      |
| Location      | Flattened `location.*` columns, such as `location.address.city`.                        |
| Neighborhoods | A JSON array in the `location.neighborhoods` cell.                                      |
| Guest ratings | Indexed, flattened `guest_rating[n].*` columns. Use the singular `guest_rating` prefix. |
| Ads metadata  | A JSON object in the `ads_metadata` cell.                                               |

Don't submit top-level CSV columns named `location` or `guest_ratings`. Those names describe logical objects, not the accepted columns for CSV or TXT uploads. In CSV, enclose cells containing commas, quotation marks, or newlines in double quotation marks, and double each embedded quotation mark.

### Example CSV

This example includes all required columns and explicitly enables Ads processing for the property. Replace the fictional property data and URLs before uploading. Your landing pages and images must be publicly accessible.

```text
hotel_id,name,description,url,images,location.address.city,location.address.country_code,location.coordinates.latitude,location.coordinates.longitude,is_ads_eligible
hotel_001,Harbor House Hotel,A fictional waterfront hotel used to demonstrate the feed format.,https://example.com/hotels/hotel_001,"[{""url"":""https://placehold.co/800x600.jpg?text=Hotel+01"",""tags"":[""featured""]}]",San Francisco,US,37.789,-122.391,true
```

Download the [ten-property example CSV](https://developers.openai.com/ads/hotel-property-feed-v1-public-example.csv) for a sample that also includes brands, static prices, guest ratings, and categories. Its `example.com` landing pages and `placehold.co` images are placeholders, not properties to advertise.

## Identity and descriptive fields

Required fields must have valid, nonempty values on every row, including rows with `status` set to `archived`.

| Column            | Required | Type and rules                                                                                                                  |
| ----------------- | -------- | ------------------------------------------------------------------------------------------------------------------------------- |
| `hotel_id`        | Yes      | Stable, case-sensitive string; up to 100 characters.                                                                            |
| `name`            | Yes      | Display name; up to 150 characters. Must contain text, not only markup.                                                         |
| `description`     | Yes      | Static property description; up to 5,000 characters. Must contain text, not only markup.                                        |
| `url`             | Yes      | Absolute HTTP or HTTPS property landing-page URL; up to 2,048 characters. Embedded credentials aren't allowed.                  |
| `brand`           | No       | Hotel or chain brand; up to 70 characters. This is separate from the advertiser's display identity.                             |
| `status`          | No       | `active` or `archived`. Defaults to `active` when omitted.                                                                      |
| `is_ads_eligible` | No       | A boolean. Set `true` for properties to process for ads, or `false` to opt out. If omitted, uses the feed's configured default. |

Leading and trailing whitespace is removed from text values. Display text is Unicode-normalized. Required strings can't be empty or contain control characters. Blank optional scalar cells are treated as omitted.

Use `is_ads_eligible` in new files. The legacy `is_eligible_ads` field provides a fallback when the canonical field is absent; conflicting values reject the row. Eligibility doesn't guarantee ad delivery: the property must also satisfy review and serving requirements.

## Images

The `images` cell must contain a JSON array of 1–20 image objects. Invalid objects are removed if at least one valid image remains; a row with no valid image is rejected. Duplicate image URLs are removed, preserving order. The first remaining image is primary.

| JSON field | Required | Type and rules                                                                                 |
| ---------- | -------- | ---------------------------------------------------------------------------------------------- |
| `url`      | Yes      | Absolute HTTP or HTTPS image URL; up to 2,048 characters. Embedded credentials aren't allowed. |
| `tags`     | No       | Array of up to 20 strings, each 1–64 characters. Duplicate tags are removed, preserving order. |

The JSON value before CSV escaping looks like this:

```json
[
  {
    "url": "https://placehold.co/800x600.jpg?text=Hotel+01",
    "tags": ["featured"]
  }
]
```

## Location

Include all four required location columns. A single `location` JSON cell doesn't replace them. The country code describes the property's physical location, not the countries where you want to show ads.

| Column                           | Required | Type and rules                                                                                                      |
| -------------------------------- | -------- | ------------------------------------------------------------------------------------------------------------------- |
| `location.address.addr1`         | No       | Street address; up to 200 characters.                                                                               |
| `location.address.city`          | Yes      | Display city; up to 100 characters.                                                                                 |
| `location.address.region`        | No       | State, province, or region; up to 100 characters.                                                                   |
| `location.address.postal_code`   | No       | Postal code; up to 32 characters.                                                                                   |
| `location.address.country_code`  | Yes      | ISO 3166-1 alpha-2 country code, such as `US`. Normalized to uppercase.                                             |
| `location.coordinates.latitude`  | Yes      | Finite number from `-90` to `90`, inclusive.                                                                        |
| `location.coordinates.longitude` | Yes      | Finite number from `-180` to `180`, inclusive.                                                                      |
| `location.neighborhoods`         | No       | JSON array of up to 20 nonempty strings, each up to 100 characters. Duplicate values are removed, preserving order. |

For example, the neighborhood value before CSV escaping is `["Waterfront"]`. Neighborhoods are stored as property metadata.

## Pricing and categorization

These fields describe the property independently of travel dates. `base_price` is a static starting price, not a quote for a particular stay or a statement of room availability.

| Column         | Required | Type and rules                                                                                                                                                                         |
| -------------- | -------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `base_price`   | No       | Positive amount followed by an ISO 4217 currency code, such as `149.00 USD`; up to 64 characters. Currency is normalized to uppercase.                                                 |
| `star_rating`  | No       | Number from 1.0 to 5.0 in increments of 0.5.                                                                                                                                           |
| `category`     | No       | One scalar hotel category; up to 200 characters.                                                                                                                                       |
| `ads_metadata` | No       | JSON object with up to 50 string-valued entries. Nonempty keys can have up to 80 characters; nonempty values can have up to 200. Keys must be unique without regard to capitalization. |

For example, an `ads_metadata` value before CSV escaping is `{"custom_label_0":"waterfront"}`. Keep metadata inside this JSON object; a top-level `custom_label_0` column isn't part of the Hotel schema. Use [Hotel Set filters](#choose-hotel-set-filters) to select properties by these labels; property selection is separate from campaign audience targeting.

## Guest ratings

Guest ratings are optional. Supply up to 20 complete groups using zero-based `guest_rating[n].*` columns. Ratings are preserved in numeric index order. Every populated group must include all four fields; an entirely blank group is omitted.

| Column                                | Required within a populated group | Type and rules                                                    |
| ------------------------------------- | --------------------------------- | ----------------------------------------------------------------- |
| `guest_rating[n].rating_system`       | Yes                               | Rating-system identifier; up to 100 characters.                   |
| `guest_rating[n].score`               | Yes                               | Finite number from 0 to `max_score`, inclusive.                   |
| `guest_rating[n].max_score`           | Yes                               | Finite number greater than 0 and no greater than 100.             |
| `guest_rating[n].number_of_reviewers` | Yes                               | Whole-number count from 0 to 9,223,372,036,854,775,807 (2⁶³ − 1). |

For one rating, include these four columns and values:

```text
guest_rating[0].rating_system,guest_rating[0].score,guest_rating[0].max_score,guest_rating[0].number_of_reviewers
Example Reviews,8.8,10,425
```

This fragment isn't a complete feed row; combine these columns with the required property columns. Use `guest_rating[1].*` for a second rating. Don't put the ratings in a top-level `guest_ratings` JSON cell.

The legacy flattened alias `guest_rating[n].number_of_raters` is accepted for compatibility. Use `number_of_reviewers` in new files; conflicting alias values reject the row.

## Derived and unsupported fields

OpenAI derives these values from the record and registered feed. Don't supply them as overrides:

| Field            | Derived value                             |
| ---------------- | ----------------------------------------- |
| `item_id`        | The property's `hotel_id`.                |
| `inventory_type` | `hotel`.                                  |
| `schema_profile` | `hotel_property_v1`.                      |
| `feed_id`        | The registered feed receiving the upload. |

Undocumented top-level columns aren't ingested or used. Examples include `room_id`, `checkin_date`, `length_of_stay`, `sale_price`, `tax`, `fees`, `phone`, `applink`, `priority`, `margin_level`, `custom_label_*`, `custom_number_*`, and `internal_label`. Don't add undocumented keys inside image, location, or guest-rating objects.

This beta submission contract covers full snapshots only. Partial or incremental updates, the Delta Feed API, XML, room or offer entities, dynamic rates, and stay-date availability are outside its scope.

## Upload checklist

Before submitting a full snapshot:

- Include every required property field and all four required location columns.
- Encode `images`, `location.neighborhoods`, and `ads_metadata` as valid JSON cells.
- Use complete `guest_rating[n].*` groups, not a `guest_ratings` JSON cell.
- Replace sample URLs with publicly accessible property and image URLs.
- Set `is_ads_eligible` explicitly for the properties you intend to advertise.
- Treat `base_price` as a static starting price, not dated availability.

Check Upload History in Ads Manager after submitting the file. A completed file transfer doesn't mean every row was accepted or that an ad can serve. Review row diagnostics and resolve invalid values before submitting the next full snapshot.