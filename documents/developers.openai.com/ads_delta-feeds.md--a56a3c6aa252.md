# Delta Feeds API

> For the complete documentation index, see [llms.txt](/llms.txt). Markdown versions of documentation pages are available by appending `.md` to the page URL.

The Delta Feeds API updates availability, titles, and prices for existing
variants in a linked product feed. Send only the products that changed instead
of uploading your entire catalog again.

Access to the Delta Feeds API is enabled per ad account. If a request returns
  `403` with `product_feed_api_disabled` or `product_feed_delta_api_disabled`,
  contact your OpenAI account team to confirm access.

## Before you begin

You need:

- An Ads API key from the ad account's **Settings** tab in
  [Ads Manager](https://ads.openai.com).
- A product feed linked to that ad account and its feed ID.
- An initial catalog already uploaded to the feed.
- The existing parent product and variant identifiers from that catalog.

The endpoint updates existing feed variants. It doesn't create feeds, upload
full catalogs, or add products that aren't already in the feed. See
[Product Feeds](https://developers.openai.com/ads/product-feeds) to set up the initial catalog.

## Update product variants

Send a `PATCH` request with each changed product and its affected variants.
You can update a variant's price, availability, or both.

`PATCH /feeds/{feed_id}/products`

```bash
curl -X PATCH \
  "https://api.ads.openai.com/v1/feeds/product_feed_123/products" \
  -H "Authorization: Bearer $OPENAI_ADS_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "products": [
      {
        "id": "running-shoe-001",
        "variants": [
          {
            "id": "running-shoe-001-black-9",
            "availability": {
              "available": false
            }
          },
          {
            "id": "running-shoe-001-white-9",
            "title": "Running shoe - white, size 9",
            "price": {
              "amount": 8999,
              "currency": "USD"
            },
            "availability": {
              "status": "in_stock"
            }
          }
        ]
      }
    ]
  }'
```

The API returns `200 OK` with the feed ID and an acceptance result:

```json
{
  "id": "product_feed_123",
  "accepted": true
}
```

`accepted: true` means the update was accepted by feed processing. It doesn't
mean downstream indexing, ad eligibility, or serving has already updated. Check
the `accepted` value before treating the request as successful.

### Request fields

| Field                                | Type     | Required | Description                                                                                           |
| ------------------------------------ | -------- | -------- | ----------------------------------------------------------------------------------------------------- |
| `products`                           | object[] | Yes      | One or more existing products to update.                                                              |
| `products[].id`                      | string   | Yes      | The parent product identifier from the existing catalog.                                              |
| `products[].variants`                | object[] | Yes      | One or more existing variants of the parent product.                                                  |
| `products[].variants[].id`           | string   | Yes      | The existing variant or item identifier from the catalog.                                             |
| `products[].variants[].title`        | string   | No       | Updated title for this variant.                                                                       |
| `products[].variants[].price`        | object   | No       | Updated price for this variant.                                                                       |
| `price.amount`                       | integer  | Yes      | Nonnegative price in minor units (`8999` means `$89.99` in `USD`).                                    |
| `price.currency`                     | string   | Yes      | Supported three-letter currency code, such as `USD`.                                                  |
| `products[].variants[].availability` | object   | No       | Updated availability for this variant.                                                                |
| `availability.available`             | boolean  | No       | `true` maps to `in_stock`; `false` maps to `out_of_stock`.                                            |
| `availability.status`                | string   | No       | Explicit availability, such as `in_stock` or `out_of_stock`. Overrides `available` when both are set. |

Both `products` and every `variants` array must contain at least one item.
Product and variant IDs must be nonempty. Don't include the same variant more
than once in a request.

Send the feed ID in the URL, the parent product ID in `products[].id`, and the
variant ID in `products[].variants[].id`. Don't send `shop_id`,
`scoped_offer_id`, or `target_country`; feed ownership, product identity, and
supported countries are resolved from the linked feed.

## Understand how changes are applied

The initial feed upload supplies the full product record. A delta request
changes only the specified fields on existing variants and preserves the
remaining catalog data.

After feed processing accepts an update, downstream systems apply the change
asynchronously. An out-of-stock product stops qualifying for delivery after the
change propagates. Marking a product in stock doesn't guarantee that it will
serve: the product, campaign, ad group, and ad must still meet normal
[serving requirements](https://developers.openai.com/ads/product-feeds#understand-serving-eligibility).

There is no completion timestamp or downstream processing result in the
acceptance response. Use your normal feed and campaign monitoring to verify the
result.

## Handle common errors

| Status | Cause                                                                                                      | Action                                                                                        |
| ------ | ---------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------- |
| `400`  | A required field is missing, a product or variant list is empty, or the request includes an unknown field. | Verify the request body and send only supported fields.                                       |
| `401`  | The Ads API key is missing or invalid.                                                                     | Use an active Ads API key in the `Authorization: Bearer` header.                              |
| `403`  | Feed API access is disabled or the account lacks permission to manage feed data.                           | Check account permissions and ask your OpenAI account team to confirm Delta Feeds API access. |
| `404`  | The feed doesn't exist or isn't linked to the ad account associated with the API key.                      | Confirm the feed ID and use the API key for the account that owns the feed.                   |

If the error code is `product_feed_api_disabled` or
`product_feed_delta_api_disabled`, access hasn't been enabled for the account.
Don't retry unchanged requests until access or the underlying request issue is
resolved.

## Next steps

- [Set up a product feed and product-feed campaign](https://developers.openai.com/ads/product-feeds).
- [Review Advertiser API authentication](https://developers.openai.com/ads/api-reference/authentication).
- [Understand Advertiser API access and limits](https://developers.openai.com/ads/api-overview).