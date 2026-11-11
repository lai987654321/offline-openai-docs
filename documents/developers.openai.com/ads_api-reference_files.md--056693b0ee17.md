# Files

> For the complete documentation index, see [llms.txt](/llms.txt). Markdown versions of documentation pages are available by appending `.md` to the page URL.

## Upload from an image URL

Upload a remote image with JSON and receive a reusable `file_id`.

`POST /upload`

```bash
curl -X POST "https://api.ads.openai.com/v1/upload" \
  -H "Authorization: Bearer $OPENAI_ADS_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "image_url": "https://example.com/assets/workspace-planner-card.png"
  }'
```

```json
{
  "file_id": "file_901"
}
```

## Upload a binary file

The same endpoint also accepts `multipart/form-data` with a binary file.

```bash
curl -X POST "https://api.ads.openai.com/v1/upload" \
  -H "Authorization: Bearer $OPENAI_ADS_API_KEY" \
  -F "file=@workspace-planner-card.png"
```

## Upload a custom audience file

Upload a UTF-8 CSV or TXT customer list with the dedicated `POST /uploads`
endpoint. Set `purpose` to `custom_audience` and save the returned `file_id`:

```bash
curl -X POST "https://api.ads.openai.com/v1/uploads" \
  -H "Authorization: Bearer $OPENAI_ADS_API_KEY" \
  -F "file=@audience.csv;type=text/csv" \
  -F "purpose=custom_audience"
```

Use the file ID, original filename, MIME type, and exact file size to
[create a custom audience](https://developers.openai.com/ads/custom-audiences#create-the-custom-audience).
You can also use an uploaded file to
[add, remove, or replace audience members](https://developers.openai.com/ads/custom-audiences#add-or-remove-using-a-file).
CSV files can combine email, phone, GAID, and hashed identifier columns when the
audience request sets `identifier_resolution` to `auto`. See
[audience file requirements](https://developers.openai.com/ads/custom-audiences#prepare-an-audience-file).

## Upload an account `favicon`

Set `purpose` to `account_favicon` when you upload an image for account brand
review. The image must be at least 128 × 128 pixels.

The API can resolve an icon from the client's website:

```bash
curl -X POST "https://api.ads.openai.com/v1/upload" \
  -H "Authorization: Bearer $OPENAI_ADS_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "image_url": "https://www.acme.example",
    "purpose": "account_favicon"
  }'
```

To upload a local image, send `purpose` as a multipart form field:

```bash
curl -X POST "https://api.ads.openai.com/v1/upload" \
  -H "Authorization: Bearer $OPENAI_ADS_API_KEY" \
  -F "purpose=account_favicon" \
  -F "file=@acme-favicon.png"
```

Assign the returned `file_id` with
[`POST /ad_account/brand`](https://developers.openai.com/ads/api-reference/ad-account#update-account-brand-metadata).

## Use the uploaded file in an ad

Pass the returned `file_id` when you create or update an ad creative.

For an ad with multiple images, upload each image separately under the same
ad account and pass the returned IDs in `creative.file_ids`. Use 4–6 distinct
square (1:1) images in display order. See
[Create an ad with multiple images](https://developers.openai.com/ads/campaign-management#create-an-ad-with-multiple-images)
for requirements and a complete example.

`POST /ads`

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