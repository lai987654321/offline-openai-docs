# Product Feeds

> For the complete documentation index, see [llms.txt](/llms.txt). Markdown versions of documentation pages are available by appending `.md` to the page URL.

Use product feeds to create ads from your catalog. Upload your product data, select the products an ad group can use, and create an ad template that fills in product details when an ad is shown.

For hotel properties, use the separate [Hotel property feed guide (limited beta)](https://developers.openai.com/ads/hotel-feeds).

Examples use an ad account-scoped Advertiser API key, `${OPENAI_ADS_API_KEY}`, and sample IDs such as `fd_123`, `cmpn_123`, `adgrp_123`, and `ad_123`. Replace these with the IDs returned by your requests. Keep the API key on your server. See [Authentication](https://developers.openai.com/ads/api-reference/authentication) for request conventions.

The examples use a US catalog with USD prices. Use the countries, product information, and currency appropriate to your catalog and ad account.






## Feed Setup & Ingestion

Create a feed in your ad account, configure SFTP access, and upload your catalog. SFTP is the file-transfer connection used to send product files to the feed.




### Before you start

You will need:

- An ad account and an Advertiser API key with permission to manage its feeds.
- Product feed API access for the account.
- A catalog that follows the [OpenAI product file schema](https://developers.openai.com/commerce/specs/file-upload/products).
- Publicly accessible product pages and product images.
- An SFTP client or an application that can upload files over SFTP.

If feed access is unavailable, contact your OpenAI account team before continuing.

### 1. Create a feed

Create a feed with a name and the countries your catalog supports.

```bash
curl -X POST "https://api.ads.openai.com/v1/feeds" \
  -H "Authorization: Bearer ${OPENAI_ADS_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Acme spring catalog",
    "countries": ["US"]
  }'
```

Save the returned `feed_id` and use it in place of `fd_123` below.

### 2. Configure SFTP access

Use password authentication or an SSH public key.

#### Password authentication

```bash
curl -X POST "https://api.ads.openai.com/v1/feeds/fd_123/sftp_access" \
  -H "Authorization: Bearer ${OPENAI_ADS_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "authentication_method": "password"
  }'
```

Use the returned connection URI and password to connect your SFTP client. Store the password securely. Generating a new password replaces the previous one.

#### SSH-key authentication

Send your public key as `ssh_public_key`. Replace the example value with the complete contents of your public-key file.

```bash
curl -X POST "https://api.ads.openai.com/v1/feeds/fd_123/sftp_access" \
  -H "Authorization: Bearer ${OPENAI_ADS_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "authentication_method": "ssh_key",
    "ssh_public_key": "YOUR_SSH_PUBLIC_KEY"
  }'
```

Configure your SFTP client with the corresponding private key.




### 3. Prepare the product file

Create a UTF-8 CSV with one row per product item or variant. Keep product identifiers stable between uploads.

The following example shows a two-product catalog. Replace the example URLs with your real product and image URLs before uploading it.

```text
item_id,title,description,url,brand,image_url,price,availability,seller_name,seller_url,return_policy,target_countries,store_country,is_eligible_search,is_eligible_checkout,is_ads_eligible
SKU-001,Trail Running Shoe,Lightweight trail shoe for daily runs,https://example.com/products/sku-001,Acme,https://example.com/images/sku-001.jpg,89.00 USD,in_stock,Acme,https://example.com,https://example.com/returns,US,US,true,false,true
SKU-002,Waterproof Shell,Packable waterproof jacket,https://example.com/products/sku-002,Acme,https://example.com/images/sku-002.jpg,149.00 USD,in_stock,Acme,https://example.com,https://example.com/returns,US,US,true,false,true
```

Include every base field marked `Required` in the product file schema. Set `is_ads_eligible` to `true` for products you want processed for ads, and keep their prices and availability current. Product pages and images must be publicly accessible HTTPS URLs.

For required fields, optional attributes, and variant grouping, follow the [product file schema](https://developers.openai.com/commerce/specs/file-upload/products).

### 4. Upload the file

Connect to the returned SFTP location and upload your CSV. For example, after connecting with your SFTP client, upload a local file named `catalog.csv`:

```text
put /path/to/catalog.csv catalog.csv
```

Place feed files directly in the SFTP root, without nested folders. If you split a catalog across files, the files should collectively represent the catalog, with each product appearing once.

Processing is asynchronous. A successful file transfer confirms that the file was uploaded; use Monitoring Uploads to check ingestion and identify problems.

### Retrieve your feeds

List the feeds in your account. Request `product_count` to include the current count of ingested products marked as eligible for ads.

```bash
curl -G "https://api.ads.openai.com/v1/feeds" \
  -H "Authorization: Bearer ${OPENAI_ADS_API_KEY}" \
  --data-urlencode 'include[]=product_count'
```

The count can remain zero while the initial upload is processing.

### Manage SFTP access

Use these endpoints with no request body to pause or reactivate SFTP access:

| Action                 | Endpoint                                        |
| ---------------------- | ----------------------------------------------- |
| Pause SFTP access      | `POST /v1/feeds/{feed_id}/sftp_access/pause`    |
| Reactivate SFTP access | `POST /v1/feeds/{feed_id}/sftp_access/activate` |

To pause ad delivery, use the campaign, ad group, or ad pause endpoint. SFTP access controls the upload connection.

## Monitoring Uploads

Use upload history to check whether a product file was processed, how many rows were accepted or rejected, and which problems need attention.

### Retrieve upload history

```bash
curl -G "https://api.ads.openai.com/v1/feeds/uploads" \
  -H "Authorization: Bearer ${OPENAI_ADS_API_KEY}"
```

Find the upload for your feed and check its status and diagnostics. This abbreviated upload record shows rejected rows:

```json
{
  "feed_id": "fd_123",
  "upload_id": "sftp_upload_123",
  "status": "completed_with_errors",
  "rows_accepted": 1245,
  "rows_rejected": 3,
  "rows_ads_eligible": 1245,
  "diagnostics": [
    {
      "code": "invalid_value",
      "severity": "warning",
      "field": "price",
      "rows_affected": 3
    }
  ]
}
```

This example reports invalid prices in three rows. Correct those values in your catalog and upload it again.

### Understand upload statuses

| Status                               | What to do                                                                                                |
| ------------------------------------ | --------------------------------------------------------------------------------------------------------- |
| `scanning`, `received`, `processing` | Processing is still underway. Check again for a terminal status and available counts.                     |
| `completed`                          | Processing completed. Check counts and inspect the products you intend to advertise.                      |
| `completed_with_errors`              | Some data was processed, but errors remain. Review diagnostics and rejected rows.                         |
| `skipped`                            | The upload was not processed. Check the source files and upload history before assuming products changed. |
| `failed`                             | Processing failed. Review diagnostics and correct the issue before uploading again.                       |

A completed upload does not establish that every product can serve. Product data, availability, reviews, product filters, and campaign eligibility still apply.

Upload counts describe one upload and can differ from the feed's current product count.

### Resolve diagnostics

| Code                            | What to check                                                                                                   |
| ------------------------------- | --------------------------------------------------------------------------------------------------------------- |
| `missing_required_column`       | Compare the file's columns with the product file schema and add the missing required column.                    |
| `invalid_value`                 | Check the reported field's formatting and allowed values. For example, verify price amounts and currency codes. |
| `unsupported_file_type`         | Check that the uploaded files use a supported format. This walkthrough uses CSV.                                |
| `invalid_sftp_directory_layout` | Place feed files directly in the SFTP root and remove nested folders.                                           |

## Updating Feeds & Delta API

Keep the feed current as prices, stock, and product details change. Choose an update method based on what changed.

| Change                                                      | Method                              |
| ----------------------------------------------------------- | ----------------------------------- |
| Change an existing item's title, price, or availability     | Delta API                           |
| Add new products                                            | Upload an updated catalog over SFTP |
| Change other product fields, such as images or descriptions | Upload an updated catalog over SFTP |
| Refresh the complete catalog                                | Upload an updated catalog over SFTP |

### Replace the catalog with each full upload

For eligible product feeds, you can enable catalog replacement. Each future full upload must include every product you want to keep. OpenAI deletes products missing from it within a day. This setting applies to full uploads, not partial Delta API updates.

```bash
curl -X PATCH "https://api.ads.openai.com/v1/feeds/fd_123/settings" \
  -H "Authorization: Bearer ${OPENAI_ADS_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{"is_full_refresh": true}'
```

Use `GET /v1/feeds/fd_123/settings` to check the current setting. To stop pending cleanup, send the same PATCH request with `is_full_refresh` set to `false`. This does not restore products already deleted. Omitting `is_full_refresh` leaves the setting unchanged.

### Update existing products with the Delta API

You need an existing feed, an initial catalog that has been processed, and the product and variant identifiers from that catalog. The account must have access to manage feed data.

Send only the fields that changed. This example lowers one product's price to $79.99 USD and marks another product out of stock:

```bash
curl -X PATCH "https://api.ads.openai.com/v1/feeds/fd_123/products" \
  -H "Authorization: Bearer ${OPENAI_ADS_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "products": [
      {
        "id": "SKU-001",
        "variants": [
          {
            "id": "SKU-001",
            "price": {
              "amount": 7999,
              "currency": "USD"
            }
          }
        ]
      },
      {
        "id": "SKU-002",
        "variants": [
          {
            "id": "SKU-002",
            "availability": {
              "status": "out_of_stock"
            }
          }
        ]
      }
    ]
  }'
```

Example response:

```json
{
  "id": "fd_123",
  "accepted": true
}
```

An `accepted: true` response confirms submission. Changes apply asynchronously, so allow time for product data and serving eligibility to update. See the [Delta Feeds API](https://developers.openai.com/ads/delta-feeds) for the full request and response details.

### Use the correct identifiers

| Field                      | Value                                                                        |
| -------------------------- | ---------------------------------------------------------------------------- |
| Feed ID in the URL         | The `feed_id` returned when the feed was created.                            |
| `products[].id`            | The catalog's `group_id` when variants are grouped; otherwise the `item_id`. |
| `products[].variants[].id` | The individual variant's `item_id`.                                          |

The CSV example without variant grouping uses `SKU-001` as both the product ID and variant ID. Use your catalog's identifiers when making updates.

### Price and availability formats

The price format in the API differs from the CSV format:

| Surface                   | Example                               | Meaning                                           |
| ------------------------- | ------------------------------------- | ------------------------------------------------- |
| CSV `price`               | `79.99 USD`                           | Major currency units and a currency code.         |
| Delta API `price`         | `{"amount": 7999, "currency": "USD"}` | Integer minor currency units and a currency code. |
| Campaign budgets and bids | `50000000` micros                     | 50 major currency units.                          |

For JPY, which has no decimal subdivision, a delta `amount` of `7999` represents ¥7,999. Do not use campaign budget micros for product prices.

Use `status: "out_of_stock"` to mark an item unavailable, and `status: "in_stock"` when it becomes available again.

An out-of-stock product stops qualifying for delivery after the change propagates. Returning it to stock makes it eligible for consideration once processing completes and the other serving requirements are met.

### Update the catalog over SFTP

Upload an updated catalog to the same SFTP location used during setup.

1. Keep the identifiers of existing products unchanged.
1. Include your complete current catalog, including products you want to mark out of stock.
1. Replace the existing file or files and remove outdated files. Reusing the same filenames makes recurring uploads easier to manage.
1. If the catalog spans multiple files, include each product once across the files.
1. Check upload history and inspect the resulting products.

To stop serving an unavailable product, explicitly set `availability` to `out_of_stock`. When it becomes available again, submit `in_stock` with its current details.

Keep your source catalog consistent with changes sent through the Delta API so later uploads contain the intended values. Use [product queries](#product-sets--filters) to inspect titles and prices after processing.

### Archive an unused feed

Archive a feed when it is no longer needed:

```bash
curl -X POST "https://api.ads.openai.com/v1/feeds/fd_123/archive" \
  -H "Authorization: Bearer ${OPENAI_ADS_API_KEY}"
```

A feed cannot be archived while it is attached to a non-archived campaign or ad group. Archive those resources first; pausing them is not sufficient.




## Product Sets & Filters

A product set selects which products an ad group can use from its campaign's feed. Use filters to select a brand, category, price range, or another supported attribute.

The campaign owns the feed selection. An ad group inherits that feed. If you omit `product_set`, the ad group uses the campaign's feed without additional product filters.

### Preview matching products

The generic `POST /feeds/{feed_id}/items/query` also supports Product and Hotel inventory. It excludes deleted, expired, and ads-ineligible items without requiring review approval. See [item queries and pagination](https://developers.openai.com/ads/hotel-feeds#query-hotel-items). The Product-specific query in this section retains its existing behavior; the two queries can return different results.

Before creating or updating an ad group, query the feed with the filters you plan to use. This request selects Acme products priced at 100 major currency units or less:

```bash
curl -X POST "https://api.ads.openai.com/v1/feeds/fd_123/products/query" \
  -H "Authorization: Bearer ${OPENAI_ADS_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "filters": [
      {
        "field": "brand",
        "operator": "in",
        "values": ["Acme"]
      },
      {
        "field": "price",
        "operator": "lte",
        "values": ["100"]
      }
    ],
    "limit": 20
  }'
```

Each product must satisfy the filters together. In the sample USD catalog, this selects the $89 trail shoe and excludes the $149 jacket. To inspect the feed without additional filters, send `"filters": []`.

Example response, with product fields abbreviated:

```json
{
  "object": "list",
  "data": [
    {
      "item_id": "SKU-001",
      "brand": "Acme",
      "title": "Trail Running Shoe",
      "price": "89.00 USD"
    }
  ],
  "total_count": 2,
  "matched_count": 1
}
```

Review the matching products before saving the filters. Matching a filter does not guarantee that a product will receive impressions.

### Choose fields and operators

Each filter contains a `field`, an `operator`, and a `values` array. Send values as strings, including numeric values such as `"100"` or `"4.5"`.

You can select products by attributes such as brand, category, price, and item ID. For example, use `in` to select specific brands or `lte` to set an upper price bound, as shown above. Feed-defined metadata can also be used through `ads_metadata.<field>` when supported by your integration.

See the [Ad Groups reference](https://developers.openai.com/ads/api-reference/ad-groups) for supported filter fields, operators, and validation rules.

To organize your catalog with custom labels, add the labels inside each product's `ads_metadata` using keys supported by your integration. Then apply filters on those fields in the ad group's `product_set`. Different ad groups can select different subsets of the same catalog.

For example, set `custom_label_0` to `WA` inside a product's `ads_metadata`, then filter on `ads_metadata.custom_label_0` to select products carrying that label. This selects eligible products; the label itself does not restrict delivery to users in Washington. Configure user-location targeting through [campaign targeting](https://developers.openai.com/ads/campaign-targeting#product-feed-campaigns).

### Apply the product set

Use the same filters in the ad group's `product_set`. The `product_feed_id` must match the campaign's feed.

For a new ad group, include this object in the create request shown in Product Feed Campaigns. For an existing ad group, update it with the complete desired product set:

```bash
curl -X POST "https://api.ads.openai.com/v1/ad_groups/adgrp_123" \
  -H "Authorization: Bearer ${OPENAI_ADS_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "product_set": {
      "product_feed_id": "fd_123",
      "filters": [
        {
          "field": "brand",
          "operator": "in",
          "values": ["Acme"]
        },
        {
          "field": "price",
          "operator": "lte",
          "values": ["100"]
        }
      ]
    }
  }'
```

Treat the filters in an update as the complete desired list. Include filters you want to keep. To remove product filters, send the same `product_feed_id` with `"filters": []`.

Retrieve the ad group to confirm the saved product selection.

### If no products match

Query with an empty filter list first. If products appear, add your filters one at a time to find the condition excluding the expected products. If the unfiltered result is empty, check upload history.

Catalog updates can change which products satisfy a filter. Review the selection after changes to prices, brands, categories, or other filtered attributes.




## Product Feed Campaigns

Create a campaign linked to your feed, an ad group with a product selection, and a product-ad template. The template uses product text, prices, images, and destination URLs from the feed.

| Level    | What you configure                                        |
| -------- | --------------------------------------------------------- |
| Campaign | Product feed, objective, budget, schedule, and targeting. |
| Ad group | Bid configuration and optional product filters.           |
| Ad       | Product-ad template.                                      |

### Before you start

You will need a feed belonging to the same ad account as the campaign. Confirm that ingestion has completed for the products you intend to use and that your [product filters](#product-sets--filters) match them.

This example creates a clicks campaign with a fixed bid. The $50 daily budget and $2 maximum bid are illustrative amounts for a USD account. Use amounts appropriate to your account's currency and advertising plan.

Campaigns, ad groups, and ads are created paused so you can inspect them before activation. Reuse each creation request's `Idempotency-Key` only when retrying that same request; use a new key for a new resource.

### 1. Create the campaign

Set `mode` to `product_feed` and `product_feed_id` to your feed ID. New product-feed campaigns support geographic targeting and exclusions only at country level. Follow the [campaign targeting guide](https://developers.openai.com/ads/campaign-targeting#product-feed-campaigns) to configure these settings.

```bash
curl -X POST "https://api.ads.openai.com/v1/campaigns" \
  -H "Authorization: Bearer ${OPENAI_ADS_API_KEY}" \
  -H "Idempotency-Key: product-feed-campaign-001" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Spring catalog campaign",
    "status": "paused",
    "mode": "product_feed",
    "product_feed_id": "fd_123",
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

Save the returned campaign `id` and use it in place of `cmpn_123` below.

The campaign's mode, objective, and linked feed cannot be changed after creation. Choose them before creating the campaign. Geographic targeting options for product-feed campaigns can differ from other campaign types; use the targeting options available to your account.

For campaign fields and lifecycle operations, see the [Campaigns reference](https://developers.openai.com/ads/api-reference/campaigns).

### 2. Create the ad group

Set a fixed click bid and attach the filters you previewed. This example selects Acme products priced at 100 major currency units or less.

```bash
curl -X POST "https://api.ads.openai.com/v1/ad_groups" \
  -H "Authorization: Bearer ${OPENAI_ADS_API_KEY}" \
  -H "Idempotency-Key: product-feed-ad-group-001" \
  -H "Content-Type: application/json" \
  -d '{
    "campaign_id": "cmpn_123",
    "name": "Acme products up to 100",
    "status": "paused",
    "bidding_config": {
      "billing_event_type": "click",
      "strategy": "fixed_bid",
      "max_bid_micros": 2000000
    },
    "product_set": {
      "product_feed_id": "fd_123",
      "filters": [
        {
          "field": "brand",
          "operator": "in",
          "values": ["Acme"]
        },
        {
          "field": "price",
          "operator": "lte",
          "values": ["100"]
        }
      ]
    }
  }'
```

Save the returned ad-group `id` and use it in place of `adgrp_123` below.

Omit `product_set` if you want to use the campaign's feed without additional product filters. If you supply it, its feed ID must match the campaign's feed.




### 3. Create the product-ad template

Create an ad with `creative.type` set to `product_ad_template`:

```bash
curl -X POST "https://api.ads.openai.com/v1/ads" \
  -H "Authorization: Bearer ${OPENAI_ADS_API_KEY}" \
  -H "Idempotency-Key: product-feed-ad-001" \
  -H "Content-Type: application/json" \
  -d '{
    "ad_group_id": "adgrp_123",
    "name": "Acme product template",
    "status": "paused",
    "creative": {
      "type": "product_ad_template",
      "title": "{{product.title}}",
      "body": "{{product.body}}",
      "price": "{{product.price}}"
    }
  }'
```

Save the returned ad `id` and use it in place of `ad_123` below.

The template uses these macros:

| Macro               | Value supplied from the product |
| ------------------- | ------------------------------- |
| `{{brand}}`         | Brand.                          |
| `{{product.title}}` | Title.                          |
| `{{product.body}}`  | Description text.               |
| `{{product.price}}` | Price.                          |

Use the body and price macros as shown in the example. You can combine supported macros with text in the title, such as `{{brand}}: {{product.title}}`. See the [Ads reference](https://developers.openai.com/ads/api-reference/ads) for template requirements.

The selected product supplies the image and destination URL, so this example does not upload a separate creative image or set a `target_url`. Each product-feed ad group can contain at most one non-archived product-ad template.

To add tracking parameters to product URLs, use account tracking settings or `landing_page_configuration` on the campaign, ad group, or ad. Individual products have no separate configurable ad entity; the ad's tracking settings apply to their destinations. See [tracking parameters](https://developers.openai.com/ads/campaign-management#tracking-parameters) for parameter precedence, Legacy behavior, examples, and migration guidance.

### 4. Inspect before activation

Check:

- The account's status and reviews.
- The campaign's feed, objective, budget, and targeting.
- The ad group's bid configuration and matching products.
- Product titles, descriptions, prices, images, and destination URLs.
- The ad's review status and any serving issues.

Request serving issues when retrieving the ad:

```bash
curl -G "https://api.ads.openai.com/v1/ads/ad_123" \
  -H "Authorization: Bearer ${OPENAI_ADS_API_KEY}" \
  --data-urlencode 'include[]=serving_issues'
```

You can also request serving issues when retrieving the campaign or ad group.

### 5. Activate when ready

Activate the ad, ad group, and campaign:

```bash
curl -X POST "https://api.ads.openai.com/v1/ads/ad_123/activate" \
  -H "Authorization: Bearer ${OPENAI_ADS_API_KEY}"
```

```bash
curl -X POST "https://api.ads.openai.com/v1/ad_groups/adgrp_123/activate" \
  -H "Authorization: Bearer ${OPENAI_ADS_API_KEY}"
```

```bash
curl -X POST "https://api.ads.openai.com/v1/campaigns/cmpn_123/activate" \
  -H "Authorization: Bearer ${OPENAI_ADS_API_KEY}"
```

Confirm each response reports `status: "active"`. Delivery can begin once reviews, product availability, budget, and other serving requirements are satisfied.

<span
  id="optimize-a-product-feed-campaign-for-conversions"
  className="scroll-mt-[110px]"
/>

### Use other objectives and bid strategies

Product-feed campaigns can use impressions, clicks, or conversions objectives. Conversion-optimized campaigns are billed per click and require exactly one active standard conversion event setting to be attached when the campaign is created. See [Conversion-Optimized Campaigns](https://developers.openai.com/ads/conversion-optimized-campaigns) for setup requirements.

Maximize Results availability depends on the account and campaign configuration. Review its requirements before choosing it for a product-feed campaign.






### Monitor delivery

Use product-segmented Insights to see which products received impressions and clicks. See the [Insights reference](https://developers.openai.com/ads/api-reference/insights) for reporting examples.

If delivery does not begin, check serving issues and confirm that available products match the ad group's filters.