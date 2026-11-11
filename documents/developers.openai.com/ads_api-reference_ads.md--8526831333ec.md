# Ads

> For the complete documentation index, see [llms.txt](/llms.txt). Markdown versions of documentation pages are available by appending `.md` to the page URL.

## List ads

List ads for an ad group.

`GET /ads`

| Parameter     | Type    | Required | Notes                              |
| ------------- | ------- | -------- | ---------------------------------- |
| `ad_group_id` | string  | Yes      | Parent ad group ID.                |
| `limit`       | integer | No       | Between `1` and `500`. Default 20. |
| `after`       | string  | No       | Cursor for the next page.          |
| `before`      | string  | No       | Cursor for the previous page.      |
| `order`       | string  | No       | `asc` or `desc`.                   |

```bash
curl -X GET "https://api.ads.openai.com/v1/ads?ad_group_id=adgrp_301&limit=10" \
  -H "Authorization: Bearer $OPENAI_ADS_API_KEY"
```

```json
{
  "object": "list",
  "data": [
    {
      "id": "ad_501",
      "name": "Planner launch card",
      "created_at": 1735689800,
      "updated_at": 1735776200,
      "creative": {
        "type": "chat_card",
        "title": "Try the new workspace planner",
        "body": "Coordinate tasks, docs, and meetings in one place.",
        "file_id": "file_901",
        "image_url": "https://cdn.openai.com/ads/file_901.png",
        "target_url": "https://example.com/workspace-planner"
      },
      "status": "active",
      "review_status": "approved"
    }
  ],
  "first_id": "ad_501",
  "last_id": "ad_501",
  "has_more": false
}
```

## Create an ad

Create an ad for an ad group.

`POST /ads`

| Field                 | Type     | Required            | Notes                                                                                                                                                     |
| --------------------- | -------- | ------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `ad_group_id`         | string   | Yes                 | Parent ad group ID.                                                                                                                                       |
| `name`                | string   | Yes                 | `3` to `1000` chars and must include a non-space character. Used for organization, is not shown to end users.                                             |
| `creative.type`       | string   | Yes                 | `chat_card` or `product_ad_template`. See [Product Feeds](https://developers.openai.com/ads/product-feeds).                                                                            |
| `creative.title`      | string   | Yes                 | `3` to `50` chars.                                                                                                                                        |
| `creative.body`       | string   | Yes                 | Maximum `100` chars.                                                                                                                                      |
| `creative.price`      | string   | No                  | Price text or `{{product.price}}` for a product-ad template.                                                                                              |
| `creative.target_url` | string   | For `chat_card`     | Destination URL. A product-ad template receives it from the selected feed item.                                                                           |
| `creative.file_id`    | string   | For one image       | File returned by `POST /upload`. Don't combine with `creative.file_ids`. A product-ad template receives its image from the selected feed item.            |
| `creative.file_ids`   | string[] | For multiple images | Ordered array of 4–6 distinct square-image file IDs returned by `POST /upload`. Requires `chat_card` and an account enabled for ads with multiple images. |
| `status`              | string   | Yes                 | `active` or `paused`.                                                                                                                                     |

```bash
curl -X POST "https://api.ads.openai.com/v1/ads" \
  -H "Authorization: Bearer $OPENAI_ADS_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "ad_group_id": "adgrp_301",
    "name": "Planner launch card",
    "status": "active",
    "creative": {
      "type": "chat_card",
      "title": "Try the new workspace planner",
      "body": "Coordinate tasks, docs, and meetings in one place.",
      "target_url": "https://example.com/workspace-planner",
      "file_id": "file_901"
    }
  }'
```

### Ads with multiple images

Upload each image with `POST /upload`, then use `creative.file_ids` to attach
the returned file IDs to one ad. The title, body, and destination URL apply to
every image. The files and ad group must belong to the same account.

Use a standard Reach, Clicks, or Conversions campaign. Use fixed bidding unless
your account is also enabled for multiple images with automatic bidding.
Don't include `file_id`, `image_crop`,
`price`, or `business_agent_id` with `file_ids`.

See [Create an ad with multiple images](https://developers.openai.com/ads/campaign-management#create-an-ad-with-multiple-images)
for the upload and creation workflow.

### Product-ad templates

A product-feed ad group can contain at most one non-archived
`product_ad_template` ad. Product-ad templates receive their image and
destination URL from the selected feed item, so they don't require
`creative.file_id` or `creative.target_url`.

Follow the [product feeds guide](https://developers.openai.com/ads/product-feeds) for the complete campaign,
product-set, and template workflow.

## Retrieve an ad

Fetch one ad by ID.

The response for an ad with multiple images includes `creative.type: "chat_card"`
and an ordered
`creative.images` array. Each item contains `item_id`, `file_id`, and `image_url`.
The `file_id` and `image_url` fields can be `null`. This endpoint resolves image
URLs.

`GET /ads/{ad_id}`

```bash
curl -X GET "https://api.ads.openai.com/v1/ads/ad_501" \
  -H "Authorization: Bearer $OPENAI_ADS_API_KEY"
```

## Update an ad

Update an ad with `POST`.

`POST /ads/{ad_id}`

All fields are optional on update. If you include `creative`, send its required
`type`, `title`, and `body` fields. A single-image creative also needs its
image and destination fields. `status` accepts `active`, `paused`, or `archived`.

For an ad with multiple images, omitting `creative.file_ids` preserves the
images; an explicit array replaces them. Omitting `creative.target_url`
preserves the saved destination; an explicit value applies to every image.
Don't send a singular `creative.file_id` for an ad with multiple images.
Create a new ad to switch an existing single-image ad to multiple images.

```bash
curl -X POST "https://api.ads.openai.com/v1/ads/ad_501" \
  -H "Authorization: Bearer $OPENAI_ADS_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Planner launch card v2",
    "status": "paused",
    "creative": {
      "type": "chat_card",
      "title": "Plan work faster",
      "body": "Bring tasks, docs, and meetings together.",
      "target_url": "https://example.com/workspace-planner",
      "file_id": "file_901"
    }
  }'
```

## Review status

Every returned ad object includes `review_status`, which can be:

- `in_review`
- `rejected`
- `approved`

If your ad has been rejected, it violates one of our [ads policies](https://openai.com/policies/ad-policies/). Please edit your ad for it to be re-reviewed.

## Preview an ad

Preview an existing ad by ID. The preview expires 24 hours after creation.

The response contains iframe HTML in `data[0].body`. A paused, submitted ad can be previewed; a draft-only ad can't. Identical requests can reuse a saved snapshot without resetting its expiration.

Native Hotel previews are available to approved pilot accounts. They select one review-approved property matching the ad group's saved Hotel Set and render a Hotel card. The request takes no property ID or filter overrides. See [Preview a Hotel ad](https://developers.openai.com/ads/hotel-feeds#preview-a-hotel-ad) for the response and eligibility requirements.

`POST /ads/{ad_id}/preview`

```bash
curl -X POST "https://api.ads.openai.com/v1/ads/ad_501/preview" \
  -H "Authorization: Bearer $OPENAI_ADS_API_KEY"
```

## Change state with dedicated actions

The Ads API also exposes explicit state transitions. Paused ads won't deliver to customers. Only archive objects you have no further use for, as archiving isn't reversible.

- `POST /ads/{ad_id}/activate`
- `POST /ads/{ad_id}/pause`
- `POST /ads/{ad_id}/archive`

```bash
curl -X POST "https://api.ads.openai.com/v1/ads/ad_501/pause" \
  -H "Authorization: Bearer $OPENAI_ADS_API_KEY"
```

```json
{
  "id": "ad_501",
  "name": "Planner launch card",
  "created_at": 1735689800,
  "updated_at": 1736035200,
  "creative": {
    "type": "chat_card",
    "title": "Try the new workspace planner",
    "body": "Coordinate tasks, docs, and meetings in one place.",
    "file_id": "file_901",
    "image_url": "https://cdn.openai.com/ads/file_901.png",
    "target_url": "https://example.com/workspace-planner"
  },
  "status": "paused",
  "review_status": "approved"
}
```