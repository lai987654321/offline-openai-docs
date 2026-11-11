# Targeting

> For the complete documentation index, see [llms.txt](/llms.txt). Markdown versions of documentation pages are available by appending `.md` to the page URL.

## Inclusion & Exclusion

Campaign targeting determines who is eligible to receive the campaign's ads. Geographic, platform, and audience settings work together; matching one setting does not override the others.

You may configure both inclusion and exclusion targeting on the same campaign. Exclusions take precedence when someone belongs to both an included audience and an excluded audience. The same audience ID cannot appear in both lists in one campaign.

### Configure inclusion and exclusion

This example targets US users in one audience while excluding a second audience:

```bash
curl -X POST "https://api.ads.openai.com/v1/campaigns/cmpn_123" \
  -H "Authorization: Bearer ${OPENAI_ADS_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "targeting": {
      "locations": {
        "countries": [
          "US"
        ]
      },
      "custom_audiences": {
        "ids": [
          "caud_123"
        ]
      },
      "excluded_custom_audiences": {
        "ids": [
          "caud_456"
        ]
      }
    }
  }'
```

Before sending the update, retrieve the campaign and preserve any other geographic, audience, or platform settings you want to keep. In particular, geographic and audience updates can replace existing targeting criteria.

### Inclusion is different from a bid multiplier

Including an audience restricts eligibility to matching users. An audience bid multiplier adjusts a fixed bid for matching users while leaving nonmembers eligible under the campaign's targeting. For example, a campaign with a multiplier for existing customers can still reach new customers. A campaign that includes only the existing-customer audience cannot.




## Geographic Targeting

Set geographic targeting on the campaign. You can use country codes or supported location IDs returned by the geographic lookup endpoint. See [Location Targeting](https://developers.openai.com/ads/location-targeting) for more examples.




### Find a location ID

```bash
curl -G "https://api.ads.openai.com/v1/geo_lookup/search" \
  -H "Authorization: Bearer ${OPENAI_ADS_API_KEY}" \
  --data-urlencode 'q=California' \
  --data-urlencode 'limit=10'
```

Use the returned `id` when targeting the location. The name and other metadata help you choose the correct result, but the ID identifies the target.




### Target a country and exclude a region

```bash
curl -X POST "https://api.ads.openai.com/v1/campaigns/cmpn_123" \
  -H "Authorization: Bearer ${OPENAI_ADS_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "targeting": {
      "locations": {
        "countries": [
          "US"
        ]
      },
      "excluded_locations": {
        "include": [
          {
            "id": "2000043"
          }
        ]
      }
    }
  }'
```

The location ID here is the California example. Look up the locations you intend to use. Check the [geographic target catalog](https://ads.openai.com/assets/openai-geotargets.csv) for supported IDs.

### Country codes

Country codes use ISO 3166-1 alpha-2 format, such as `US`. A code's ISO validity does not mean it is available for advertising in your account; use supported advertising locations.

For a specific geographic inclusion, use `targeting.locations.include` with the desired location IDs. For exclusions, use `targeting.excluded_locations.countries` or `.include`.

### Preserve existing targeting

Read the campaign before changing geography. Include the complete intended geographic and audience configuration so an update does not remove restrictions you want to keep. Explicitly set platform targeting when changing it.

You can include up to 2,500 IDs in geographic inclusion and exclusion lists. Account availability and campaign mode can impose additional restrictions.

### Product-feed campaigns

New product-feed campaigns support geographic targeting and exclusions only at country level.

Campaign targeting determines which users are eligible to receive ads. To select which products an ad group can use, apply product filters, including supported custom labels in `ads_metadata`. See [Product Sets & Filters](https://developers.openai.com/ads/product-feeds#product-sets--filters). A product label does not itself restrict delivery to users in that location.

If the API accepts the configuration but delivery is low, consider the combined effect of geography, audiences, platform, bids, and available products.

## Platform Targeting

Use platform targeting to choose the ChatGPT surfaces where a campaign can deliver. Configure it on the campaign through `targeting.platforms.included`. See [Platform Targeting](https://developers.openai.com/ads/platform-targeting) for more examples.

Use these broad platform groups:

| Value         | Inventory                                     |
| ------------- | --------------------------------------------- |
| `ios_app`     | ChatGPT iOS app                               |
| `android_app` | ChatGPT Android app                           |
| `web`         | ChatGPT web, including desktop and mobile web |

### Target web

```bash
curl -X POST "https://api.ads.openai.com/v1/campaigns/cmpn_123" \
  -H "Authorization: Bearer ${OPENAI_ADS_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "targeting": {
      "platforms": {
        "included": [
          "web"
        ]
      }
    }
  }'
```

This selects the web group. It does not mean desktop-only traffic. An iPhone user visiting ChatGPT in a browser belongs to web inventory rather than the iOS app group.

### Target both mobile apps

```bash
curl -X POST "https://api.ads.openai.com/v1/campaigns/cmpn_123" \
  -H "Authorization: Bearer ${OPENAI_ADS_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "targeting": {
      "platforms": {
        "included": [
          "ios_app",
          "android_app"
        ]
      }
    }
  }'
```

Use a nonempty list. To express all three broad groups explicitly, include `ios_app`, `android_app`, and `web`. At creation, omitting platform targeting defaults to all platforms.

### Update behavior

The API handles a platform-only update separately from geographic and audience changes. The examples above change only the platform selection. If you also send geographic or audience fields, build the complete desired configuration for those fields.

Retrieve the campaign after updating and check the returned platform configuration.

## Custom Audiences

Custom audiences match your customer or prospect identifiers to users. Use ready audiences for campaign inclusion, exclusion, or fixed-bid multipliers.

See the [Custom Audiences guide](https://developers.openai.com/ads/custom-audiences) for identifier normalization, file formats, and additional operations.

### Create an audience from a file

Prepare a UTF-8 CSV with a header row. For example:

```text
email,phone_number
customer@example.com,+14155552671
```

Audience uploads support email, phone, their supported SHA-256 variants, and GAID identifiers. Use the audience-specific normalization rules before hashing; do not assume another API uses the same phone normalization. Files must be no larger than 500,000,000 bytes.

Upload the file using the plural `/v1/uploads` endpoint:

```bash
curl -X POST "https://api.ads.openai.com/v1/uploads" \
  -H "Authorization: Bearer ${OPENAI_ADS_API_KEY}" \
  -F "file=@/path/to/audience.csv;type=text/csv" \
  -F "purpose=custom_audience"
```

Save the file ID, filename, MIME type, and exact size. Substitute those values below:

```bash
curl -X POST "https://api.ads.openai.com/v1/custom_audiences" \
  -H "Authorization: Bearer ${OPENAI_ADS_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "High-value customers",
    "file_id": "oaisdmntci_123",
    "identifier_resolution": "auto",
    "filename": "audience.csv",
    "mimetype": "text/csv",
    "file_size": 123456
  }'
```

`identifier_resolution: "auto"` processes supported columns in a CSV. For a single-type TXT file, provide `identifier_type` and one identifier per line.

### Wait for readiness

```bash
curl -G "https://api.ads.openai.com/v1/custom_audiences/caud_123" \
  -H "Authorization: Bearer ${OPENAI_ADS_API_KEY}"
```

Wait for `status: "ready"`. Uploaded row counts do not equal matched-user counts. Inclusion and bid multipliers require at least 25,000 matched users; ready exclusion audiences have no minimum. Review any processing failure before using the audience.

You can create an empty audience with just `name` and optional `description`, then add members. Even an empty audience is processed asynchronously.

### Add or remove members

Update an existing audience without changing its ID or the campaigns and ad groups that reference it.

| Action                                     | Endpoint                                 | Input                                    |
| ------------------------------------------ | ---------------------------------------- | ---------------------------------------- |
| Add members while keeping existing members | `POST /v1/custom_audiences/{id}/add`     | Inline identifiers or an uploaded file   |
| Remove selected members                    | `POST /v1/custom_audiences/{id}/remove`  | Inline identifiers or an uploaded file   |
| Replace the complete membership list       | `POST /v1/custom_audiences/{id}/replace` | An uploaded file; see Replace membership |

Use a new `Idempotency-Key` for each new add, remove, replace, or merge request. When retrying the same submission, reuse its original key and request body. Resuming or canceling an accepted operation by ID does not require a key or request body.

#### Add members inline

For a small update, send identifiers directly in the request. Inline request bodies must not exceed 16 MiB.

```bash
curl -X POST "https://api.ads.openai.com/v1/custom_audiences/caud_123/add" \
  -H "Authorization: Bearer ${OPENAI_ADS_API_KEY}" \
  -H "Idempotency-Key: audience-add-inline-001" \
  -H "Content-Type: application/json" \
  -d '{
    "identifiers": [
      {
        "identifier_type": "email",
        "identifier": "customer@example.com"
      }
    ]
  }'
```

To remove members inline, send the same input structure to `/v1/custom_audiences/caud_123/remove`, with the identifiers to remove and a new `Idempotency-Key`.

#### Add members from a file

Use a file when you have a batch of members to add. This adds members to the existing audience; it does not replace the audience's complete membership list.

**1. Prepare the file.** Create a UTF-8 CSV with a header row and the identifiers you want to add. For example, save this as `audience-additions.csv`:

```text
email
new-customer-1@example.com
new-customer-2@example.com
```

Use the same supported identifier formats and file-size limit described in “Create an audience from a file.”

**2. Upload the file.** Replace the local path with your file's location:

```bash
curl -X POST "https://api.ads.openai.com/v1/uploads" \
  -H "Authorization: Bearer ${OPENAI_ADS_API_KEY}" \
  -F "file=@/path/to/audience-additions.csv;type=text/csv" \
  -F "purpose=custom_audience"
```

Save the `file_id` returned by the upload. Uploading the file alone does not update the audience.

**3. Add the uploaded members.** Replace `caud_123` with your existing audience ID and `oaisdmntci_456` with the returned file ID:

```bash
curl -X POST "https://api.ads.openai.com/v1/custom_audiences/caud_123/add" \
  -H "Authorization: Bearer ${OPENAI_ADS_API_KEY}" \
  -H "Idempotency-Key: audience-add-file-001" \
  -H "Content-Type: application/json" \
  -d '{
    "file_id": "oaisdmntci_456",
    "identifier_resolution": "auto"
  }'
```

For this file-based request, use `file_id` instead of an inline `identifiers` array. You do not need to resend `filename`, `mimetype`, or `file_size` in the membership-update request.

`identifier_resolution: "auto"` processes supported identifier columns in a CSV. For a single-type TXT file, use `identifier_type` instead, such as `"identifier_type": "email"`, and put one identifier on each line.

Example response:

```json
{
  "operation_id": "caudop_123",
  "custom_audience_id": "caud_123",
  "operation": "add",
  "status": "processing"
}
```

Save the returned `operation_id` and check completion as shown below.

#### Remove members from a file

Prepare and upload a file containing the identifiers you want to remove, using the same upload process. Then send its returned `file_id` to `/remove`:

```bash
curl -X POST "https://api.ads.openai.com/v1/custom_audiences/caud_123/remove" \
  -H "Authorization: Bearer ${OPENAI_ADS_API_KEY}" \
  -H "Idempotency-Key: audience-remove-file-001" \
  -H "Content-Type: application/json" \
  -d '{
    "file_id": "oaisdmntci_789",
    "identifier_resolution": "auto"
  }'
```

Replace `oaisdmntci_789` with the ID of your removal file. This removes the specified members; other members remain in the audience.

#### Check update completion

Add, remove, and replace requests return an operation rather than the updated audience. Use the returned `operation_id` to check its status:

```bash
curl -G "https://api.ads.openai.com/v1/custom_audiences/caud_123/operations/caudop_123" \
  -H "Authorization: Bearer ${OPENAI_ADS_API_KEY}"
```

Example completed response:

```json
{
  "operation_id": "caudop_123",
  "custom_audience_id": "caud_123",
  "operation": "add",
  "status": "succeeded"
}
```

While the operation is `processing`, check again until it completes. An accepted request does not mean the membership update has finished, even if the audience itself still has a status of `ready`. Review any operation failure before treating the update as complete.

You can optionally include the audience's current `membership_revision` as `expected_revision` in an add or remove request to prevent applying the update against a different membership revision. Replacement requires this field.

### Manage audience operations

List accepted operations to find an operation ID, then use that ID to check progress, resume an interrupted add or remove, or cancel it before membership changes begin. For OAuth, listing and polling require `ads.admin.all.read`; resuming and canceling require both `ads.admin.all.read` and `ads.admin.all.write`.

#### Find an operation ID

The operation list includes retained add, remove, replace, and merge operations. It does not include the initial audience creation request. For a merge, use the new audience ID:

```bash
curl -G "https://api.ads.openai.com/v1/custom_audiences/caud_123/operations" \
  -H "Authorization: Bearer ${OPENAI_ADS_API_KEY}" \
  --data-urlencode 'limit=20'
```

Set `limit` from 1 to 100. When `has_more` is `true`, pass `next_cursor` unchanged as `cursor` on the next request for the same audience and ad account. Continue until `has_more` is `false`, even if a page has an empty `data` array. The list returns operation IDs, audience IDs, operation types, and statuses; it does not return original inputs or idempotency keys.

#### Resume an add or remove

If polling returns `409 custom_audience_operation_recovery_required`, resume the interrupted operation using its original inputs and saved progress. Confirm its ID from the saved response or operation list, then send no request body or `Idempotency-Key` header:

```bash
curl -X POST "https://api.ads.openai.com/v1/custom_audiences/caud_123/operations/caudop_123/resume" \
  -H "Authorization: Bearer ${OPENAI_ADS_API_KEY}"
```

Poll the same operation afterward. Resume preserves its ID and accepted input. An operation that already succeeded or failed keeps that status; resuming it can finish cleanup without applying membership changes again.

Resume by ID supports add and remove only. Retry replace and merge requests with their original endpoint, body, and idempotency key. An interrupted add or remove may have partially applied changes, so do not submit a new operation or an inverse update to guess at recovery. See [Poll and recover membership operations](https://developers.openai.com/ads/custom-audiences#poll-and-recover-membership-operations).

#### Cancel an add or remove

Cancel an accepted add or remove before it starts applying membership changes. Send no request body or `Idempotency-Key` header:

```bash
curl -X POST "https://api.ads.openai.com/v1/custom_audiences/caud_123/operations/caudop_123/cancel" \
  -H "Authorization: Bearer ${OPENAI_ADS_API_KEY}"
```

A successful cancellation returns `status: "failed"`; there is no separate `canceled` status. Cleanup can continue asynchronously. Canceling again is safe, and resuming a canceled operation can finish cleanup without applying membership changes.

Cancellation returns `409 custom_audience_mutation_conflict` if an active operation has started applying changes or the operation already succeeded. A `processing` status alone does not guarantee that cancellation is possible. Failed operations stay failed, and cancellation does not undo changes already applied. Replace and merge operations cannot be canceled.

If cancellation returns `503 custom_audience_operation_unavailable`, retry cancellation for the same operation ID. The operation may have stopped even though scheduling cleanup failed. See [Cancel an Add or Remove](https://developers.openai.com/ads/custom-audiences#cancel-an-add-or-remove).

### Replace membership

Retrieve the audience's `membership_revision`, upload the replacement file, and submit:

```bash
curl -X POST "https://api.ads.openai.com/v1/custom_audiences/caud_123/replace" \
  -H "Authorization: Bearer ${OPENAI_ADS_API_KEY}" \
  -H "Idempotency-Key: audience-replace-001" \
  -H "Content-Type: application/json" \
  -d '{
    "file_id": "oaisdmntci_456",
    "identifier_resolution": "auto",
    "expected_revision": 2
  }'
```

Use the actual current revision. Replacement keeps the audience ID and the old membership remains in use while processing. Changes must preserve size requirements for campaigns or ad groups using the audience.

Use a new `Idempotency-Key` for each replacement and reuse its original key and request body for retries. To archive an unused audience, call `/v1/custom_audiences/{id}/archive`; audience archival cannot be undone.

### Audience readiness

Use ready audiences. Inclusion and bid multipliers require at least 25,000 matched users; exclusion audiences have no minimum matched count. When combining inclusion and exclusion, the remaining included audience must satisfy the required size.

Matched users are different from uploaded rows. Check the processed audience before applying it. See [Custom Audiences](#custom-audiences).

## Context Hints

Context hints provide additional information about the ads in an ad group. Use them to describe relevant products, use cases, or needs that the creative and landing page may not fully cover.

Hints are not exact-match keywords. They also do not replace explicit geographic, platform, or audience targeting.

### Write useful hints

Prefer specific context that helps explain the offering:

| Less useful          | More useful                                                                       |
| -------------------- | --------------------------------------------------------------------------------- |
| Shoes                | Lightweight trail running shoes for rocky terrain                                 |
| Outdoors             | Water-resistant footwear for wet-weather hiking                                   |
| California customers | Use geographic targeting for California; describe the product's use case in hints |

These examples illustrate writing style, not a guarantee that a particular conversation will trigger an ad.

### Set hints on an ad group

```bash
curl -X POST "https://api.ads.openai.com/v1/ad_groups/adgrp_123" \
  -H "Authorization: Bearer ${OPENAI_ADS_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "context_hints": [
      "Lightweight trail running shoes for rocky terrain",
      "Water-resistant footwear for wet-weather hiking"
    ]
  }'
```

An ad group can contain up to 2,000 hints. You do not need to fill the limit; include information that helps describe the ads accurately.

### Preserve or replace the list

Updating `context_hints` replaces the current list. To add one hint, retrieve the ad group, append the new hint to the existing list, and submit the complete intended list. Send an empty array to clear the list. Omit the field when you want to leave it unchanged.

Retrieve the ad group after the update and confirm the saved list. If you need to restrict delivery to a geographic area or audience, configure that restriction on the campaign separately.