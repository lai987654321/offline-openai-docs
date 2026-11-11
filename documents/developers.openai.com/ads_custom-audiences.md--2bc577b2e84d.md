# Custom Audiences

> For the complete documentation index, see [llms.txt](/llms.txt). Markdown versions of documentation pages are available by appending `.md` to the page URL.

Custom audiences let you use customer or prospect lists to control who can see
your ads. Create an audience from a file or start with an empty audience, then
add or remove customers as your list changes. You can also replace the full
list or merge existing audiences into a new audience.

Custom audiences are not supported for campaigns targeting the European
  Economic Area (EEA) or Switzerland, where personalized ads are not yet
  available.

Before you begin, create an Ads API key in the **Settings** tab of
[Ads Manager](https://ads.openai.com). Store the key as
`OPENAI_ADS_API_KEY` and send it as a bearer token. Each key can access only
the audiences associated with its ad account.

Only upload first-party audience data that you have the right to use for ads.
Don't upload broker-sourced data. Before uploading, confirm that your use
complies with required rights, notices, consents, permissions, legal bases, and
the [Ad Tools Terms](https://openai.com/policies/ad-tools-terms/), and get
privacy or legal approval for your use case.

All examples use the `https://api.ads.openai.com/v1` base URL. Replace the
example resource IDs with IDs from your account. For each new membership
operation, generate a unique `Idempotency-Key` and keep it with the original
request so you can retry safely.

## Choose an operation

Choose the operation that matches the change in your customer list:

| Goal    | Input                                          | Result                                            |
| ------- | ---------------------------------------------- | ------------------------------------------------- |
| Create  | Uploaded file, or a name without a file        | A new audience ID.                                |
| Add     | Inline identifiers or an uploaded file         | Add matched users to the same audience.           |
| Remove  | Inline identifiers or an uploaded file         | Remove matched users from the same audience.      |
| Replace | Uploaded file containing the full desired list | Replace membership while keeping the audience ID. |
| Merge   | 2 to 64 existing audience IDs                  | A new, independent union audience.                |

Use inline requests for small updates and files for bulk changes. Both are
asynchronous: accepting a request doesn't mean processing has finished.

Small audiences, including empty audiences, can be used for **exclusion** once
they are ready. Inclusion and bid adjustments still require enough matched
users. Check [eligibility for the intended use](#check-eligibility-for-the-intended-use)
before attaching an audience to a campaign or ad group.

## Prepare an audience file

Create a UTF-8 CSV or TXT file no larger than 500 MB (500,000,000 bytes).
A UTF-8 BOM is accepted. Use `text/csv` for CSV files and `text/plain` for TXT
files.

A TXT file contains one identifier per line, without a header, and uses the
`identifier_type` you specify in the request. A CSV file must include an
identifier header. These identifier formats are supported:

| Identifier type       | CSV header            | Format                                                                                |
| --------------------- | --------------------- | ------------------------------------------------------------------------------------- |
| `email`               | `email`               | An email address containing one `@`. The API trims it and converts it to lowercase.   |
| `phone`               | `phone_number`        | A phone number in E.164 format, including `+` and the country code.                   |
| `email_sha256`        | `email_sha256`        | The 64-character SHA-256 hexadecimal digest of the normalized email address.          |
| `phone_number_sha256` | `phone_number_sha256` | The 64-character SHA-256 hexadecimal digest of the normalized E.164 telephone number. |
| `gaid`                | `gaid`                | A nonzero, hyphenated Google Advertising ID. The API normalizes and hashes it.        |

For example, an email audience CSV can contain:

```text
email
alex@example.com
jamie@example.com
sam@example.com
```

Before hashing an email, trim surrounding whitespace and convert it to
lowercase. Before hashing a phone number, normalize it to E.164, including the
leading `+` and country code. Hash the UTF-8 value without a trailing newline
and send the 64-character hexadecimal digest, not Base64. Don't remove email
dots or plus tags.

GAID values must be raw, nonzero, hyphenated UUID values, such as
`38400000-8cf0-11bd-b23e-10b96e40000d`. The API trims surrounding whitespace,
converts them to lowercase, and hashes them internally. Don't hash GAID values before submitting them.

### Combine identifier types in one CSV

Set `identifier_resolution` to `auto` when creating or updating an audience
from a CSV that combines email, phone, GAID, and hashed identifiers:

```csv
email,phone_number,email_sha256,phone_number_sha256,gaid
alex@example.com,+12025550123,,,
,,057a0fff4c78ae3e14236c36b611061cbdd54ccd72a34b23f77d7a8c4bca4963,,
,,,1a2d415d4fef1dfafe57e0d98af15bbad8cc4bd8ca8ac66e89f2e0ef3941d500,
,,,,38400000-8cf0-11bd-b23e-10b96e40000d
```

Leave unused cells empty. Each populated identifier cell is a matching
candidate; a row doesn't require every identifier to match the same user.
OpenAI counts each matched user once, so different identifiers can represent
one audience member. Don't repeat a consumed identifier column in the header.

Use `identifier_resolution: "auto"` with file-based Create, Add, Remove, or
Replace. Without it, use a single identifier type and specify that type in
`identifier_type`; this single-type processing path accepts up to 5,000,000
identifiers. Automatic resolution supports larger files within the same
500 MB upload limit.

## Upload the audience file

Upload the CSV or TXT file to `POST /uploads`. Set the multipart `purpose` field
to `custom_audience`:

```bash
curl -X POST "https://api.ads.openai.com/v1/uploads" \
  -H "Authorization: Bearer $OPENAI_ADS_API_KEY" \
  -F "file=@audience.csv;type=text/csv" \
  -F "purpose=custom_audience"
```

The response contains the file ID:

```json
{
  "file_id": "oaisdmntci_123"
}
```

Save the `file_id`, the original filename, the file's MIME type, and the exact
file size in bytes. You must provide these values when you create an audience
from a file. Use the upload promptly; don't treat its file ID as permanent
storage.

## Create the custom audience

Send the uploaded file details to `POST /custom_audiences`:

```bash
curl -X POST "https://api.ads.openai.com/v1/custom_audiences" \
  -H "Authorization: Bearer $OPENAI_ADS_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "High-value customers",
    "description": "Customers eligible for the summer campaign",
    "file_id": "oaisdmntci_123",
    "identifier_type": "email",
    "filename": "audience.csv",
    "mimetype": "text/csv",
    "file_size": 123456
  }'
```

| Field                   | Required          | Description                                                        |
| ----------------------- | ----------------- | ------------------------------------------------------------------ |
| `name`                  | Yes               | Audience name containing at least three characters.                |
| `description`           | No                | A description of the audience.                                     |
| `file_id`               | For file creation | The file ID returned by `POST /uploads`.                           |
| `identifier_type`       | No                | `email`, `phone`, `email_sha256`, `phone_number_sha256`, `gaid`.   |
| `identifier_resolution` | No                | Set to `auto` for automatic resolution of CSV identifier columns.  |
| `filename`              | With `file_id`    | The uploaded filename, including its `.csv` or `.txt` extension.   |
| `mimetype`              | With `file_id`    | The uploaded file's MIME type, such as `text/csv` or `text/plain`. |
| `file_size`             | With `file_id`    | The exact file size in bytes, from `1` through `500000000`.        |

If you omit `identifier_type`, the API defaults to `email`. For a single-type
file, set the type explicitly. For a mixed-column CSV, add
`"identifier_resolution": "auto"` to the request.

The API returns the new audience and starts processing the uploaded file:

```json
{
  "id": "caud_123",
  "created_at": 1783962000,
  "updated_at": 1783962000,
  "name": "High-value customers",
  "description": "Customers eligible for the summer campaign",
  "status": "processing",
  "hash_spec_version": "custom_audience_join_hash_v1",
  "uploaded_identifier_count_range": "none",
  "matched_identifier_count_range": "none",
  "matched_user_count_range": "none",
  "invalid_identifier_count_range": "none",
  "membership_revision": 0
}
```

### Create an empty audience

To build a list incrementally, create an empty audience without uploading a
placeholder file:

```bash
curl -X POST "https://api.ads.openai.com/v1/custom_audiences" \
  -H "Authorization: Bearer $OPENAI_ADS_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Recent purchasers",
    "description": "Exclude recent purchasers from acquisition campaigns"
  }'
```

Omit `file_id`, `filename`, `mimetype`, `file_size`, and
`identifier_resolution`. Don't upload a zero-byte file. Save the returned
audience ID and wait for it to be `ready` before adding members or using it
for exclusion. An empty exclusion audience doesn't exclude anyone until
members are added.

Create returns an audience object, not a membership operation. Don't assume
it has the Add/Remove replay contract. If the creation response is lost,
check the account's audience list before creating another audience.

## Check processing status

Retrieve the audience with `GET /custom_audiences/{custom_audience_id}`:

```bash
curl "https://api.ads.openai.com/v1/custom_audiences/caud_123" \
  -H "Authorization: Bearer $OPENAI_ADS_API_KEY"
```

Check the audience periodically until preparation finishes. Processing time
depends on input size and the operation. `ready` means preparation succeeded;
it doesn't mean the audience is eligible for every use.

| Status                   | Meaning                                                                               |
| ------------------------ | ------------------------------------------------------------------------------------- |
| `upload_pending`         | The uploaded file is waiting for processing to begin.                                 |
| `processing`             | The file is being processed and the audience isn't ready to use.                      |
| `rockset_ingest_pending` | Processed identifiers are waiting to be ingested.                                     |
| `publishing`             | The audience is being prepared for targeting and bidding.                             |
| `ready`                  | Processing succeeded. Check eligibility for exclusion, inclusion, or bid adjustments. |
| `too_small`              | The audience didn't meet the size policy applied when it was processed.               |
| `failed`                 | Processing failed. Check the file format, identifier type, and file limits.           |
| `archived`               | The audience is archived and can no longer be used.                                   |

The response returns identifier and matched-user counts as privacy-preserving
ranges, such as `under_25k`, `25k_100k`, `100k_500k`, `500k_1m`,
`1m_5m`, and `5m_plus`. `under_25k` includes empty matched audiences.
For matched counts, `none` means a count isn't available, not that it is zero.
Exact matched counts and individual membership results aren't exposed.

For finer reporting at or above 100,000 matched users, pass
`matched_count_granularity=granular` to a list or retrieve request. Counts
remain privacy-preserving ranges above 5,000,000, with wider ranges used for
larger audiences. Don't use a count range to decide targeting eligibility.

## Update audience membership

List and retrieve responses include `membership_revision`. Read the audience
before a change and pass that value as `expected_revision`. It is optional for
Add and Remove, and required for Replace. The revision values in the examples
are illustrative; use the value you just read.

Wait for each operation to finish before submitting the next dependent change.
After success, retrieve the audience again for its current revision. Don't
assume every request changes membership or increments the revision.

### Add or remove inline identifiers

Add and remove operations accept exactly one uploaded `file_id` or an
`identifiers` array. Each inline identifier includes its own `identifier_type`:

```bash
curl -X POST "https://api.ads.openai.com/v1/custom_audiences/caud_123/add" \
  -H "Authorization: Bearer $OPENAI_ADS_API_KEY" \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: custom-audience-add-001" \
  -d '{
    "expected_revision": 0,
    "identifiers": [
      {
        "identifier_type": "email",
        "identifier": "new.customer@example.com"
      },
      {
        "identifier_type": "gaid",
        "identifier": "38400000-8cf0-11bd-b23e-10b96e40000d"
      }
    ]
  }'
```

Inline entries can mix all five supported identifier types. Each entry has
its own type and value. Don't also send `file_id`.

Use the same request shape with `/remove` to remove customers, with a fresh
revision and a new key for the Remove operation:

```bash
curl -X POST "https://api.ads.openai.com/v1/custom_audiences/caud_123/remove" \
  -H "Authorization: Bearer $OPENAI_ADS_API_KEY" \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: custom-audience-remove-001" \
  -d '{
    "expected_revision": 1,
    "identifiers": [
      {"identifier_type": "email", "identifier": "new.customer@example.com"}
    ]
  }'
```

Add doesn't duplicate a user who is already a member. Remove doesn't change
membership for an absent user or permanently prevent a later Add. Unmatched
identifiers can leave membership unchanged.

Batches of up to 10,000 inline identifiers use the small-update path. Larger
inline batches use file-based processing; 10,000 is not a hard item-count
limit. The entire Add/Remove request body must fit within 16 MiB
(16,777,216 bytes), or the API returns `413`. Prefer files for bulk updates.

### Add or remove using a file

Upload the delta file with `purpose=custom_audience`, then call `/add` or
`/remove` with its `file_id` instead of `identifiers`:

```bash
curl -X POST "https://api.ads.openai.com/v1/custom_audiences/caud_123/add" \
  -H "Authorization: Bearer $OPENAI_ADS_API_KEY" \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: custom-audience-file-add-001" \
  -d '{
    "file_id": "oaisdmntci_456",
    "identifier_resolution": "auto",
    "expected_revision": 2
  }'
```

This example accepts a CSV with mixed identifier columns. For a single-type
file, you can send `identifier_type` instead of `identifier_resolution`.
Add/Remove use the filename, MIME type, and size saved with the upload; don't send
those metadata fields in the mutation body.

An Add file contains only customers to add. A Remove file contains only
customers to remove; members omitted from the file remain in the audience.
Use Replace when the file is a full snapshot of the desired membership.

### Replace the full list

Upload the complete desired audience, read the current membership revision,
then submit the file and revision to `/replace`:

```bash
curl -X POST "https://api.ads.openai.com/v1/custom_audiences/caud_123/replace" \
  -H "Authorization: Bearer $OPENAI_ADS_API_KEY" \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: custom-audience-replace-001" \
  -d '{
    "file_id": "oaisdmntci_789",
    "identifier_resolution": "auto",
    "expected_revision": 3
  }'
```

Replace requires `file_id` and a nonnegative `expected_revision`; it doesn't
accept inline identifiers. The audience keeps its ID and existing campaign
and ad-group references. The current membership stays available while the
replacement is prepared, then the new membership is published.

The audience can still show `ready` during replacement. Poll the returned
operation to determine when the replacement finishes, rather than relying on
audience status alone. Don't emulate replacement by removing every member
and adding them back.

### Merge audiences into a new list

Merge combines 2 to 64 distinct, ready audiences in the same ad account,
counting each matched user once. Wait for pending source updates to finish before merging:

```bash
curl -X POST "https://api.ads.openai.com/v1/custom_audiences/merge" \
  -H "Authorization: Bearer $OPENAI_ADS_API_KEY" \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: custom-audience-merge-001" \
  -d '{
    "name": "All qualified customers",
    "custom_audience_ids": ["caud_source_1", "caud_source_2"]
  }'
```

The new audience is independent. The sources don't change, future source
updates don't propagate to the merged audience, and existing campaigns don't
automatically switch to the new ID. Poll the operation using the
`custom_audience_id` returned by Merge, not a source audience ID.

## Poll and recover membership operations

Use these endpoints for each membership change:

| Goal                      | Endpoint                                              | Required body fields           |
| ------------------------- | ----------------------------------------------------- | ------------------------------ |
| Add identifiers           | `POST /custom_audiences/{custom_audience_id}/add`     | `file_id` or `identifiers`     |
| Remove identifiers        | `POST /custom_audiences/{custom_audience_id}/remove`  | `file_id` or `identifiers`     |
| Replace all identifiers   | `POST /custom_audiences/{custom_audience_id}/replace` | `file_id`, `expected_revision` |
| Merge into a new audience | `POST /custom_audiences/merge`                        | `name`, `custom_audience_ids`  |

Each new Add, Remove, Replace, or Merge request requires an `Idempotency-Key`
header. Reuse the key only to retry the same operation; retries return or resume the first accepted
input. Don't change the file, identifiers, or revision under an existing key:
a repeated key can return the original operation without checking the new
body. Save the original request, key, audience ID, and operation ID securely.

The response contains a privacy-safe operation object:

```json
{
  "operation_id": "caudop_123",
  "custom_audience_id": "caud_123",
  "operation": "add",
  "status": "processing"
}
```

Poll `GET /custom_audiences/{custom_audience_id}/operations/{operation_id}`
until `status` is `succeeded` or `failed`. The response exposes only the
operation ID, audience ID, operation type, and status; it doesn't return raw
identifiers, matching counts, or individual membership outcomes.

```bash
curl \
  "https://api.ads.openai.com/v1/custom_audiences/caud_123/operations/caudop_123" \
  -H "Authorization: Bearer $OPENAI_ADS_API_KEY"
```

Handle these responses without starting duplicate work:

| Response                                            | What to do                                                                                                                                     |
| --------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------- |
| `processing`                                        | Continue polling with increasing delays.                                                                                                       |
| `succeeded`                                         | Retrieve the audience and its current revision before another change.                                                                          |
| `failed`                                            | Stop polling and reconcile the result before submitting another operation. Contact support with the operation ID if needed.                    |
| `409 custom_audience_operation_recovery_required`   | The Add/Remove was interrupted and may be partially applied. [Resume by operation ID](#resume-an-add-or-remove), then poll the same operation. |
| `503 custom_audience_operation_unavailable`         | Status is temporarily unavailable. Retry the status request with increasing delays; don't assume failure.                                      |
| `409 custom_audience_mutation_conflict`             | Wait for competing work, retrieve the current state, and reconsider the intended change.                                                       |
| `409 custom_audience_replacement_revision_conflict` | Refresh the audience revision before submitting a new replacement.                                                                             |
| `429`                                               | Back off and retry, retaining the original key for an accepted mutation.                                                                       |

For a lost submission response, retry the original endpoint, body, and key.
An interrupted Add/Remove may have changed some membership already. Don't
use a new key, replay the entire job as new work, or submit an inverse update
to guess at recovery. If recovery can't continue, contact support with the
operation ID and request ID, without sending raw identifiers.

### List operations for an audience

Use `GET /custom_audiences/{custom_audience_id}/operations` to find operation
IDs when you no longer have the original submission response. The list includes
retained Add, Remove, Replace, and Merge operations for that audience in your
authenticated ad account. It doesn't include the initial Create request. For
Merge, use the new audience ID, not a source audience ID.

```bash
curl --get \
  "https://api.ads.openai.com/v1/custom_audiences/caud_123/operations" \
  -H "Authorization: Bearer $OPENAI_ADS_API_KEY" \
  --data-urlencode "limit=20"
```

```json
{
  "object": "list",
  "data": [
    {
      "operation_id": "caudop_123",
      "custom_audience_id": "caud_123",
      "operation": "add",
      "status": "processing"
    }
  ],
  "has_more": false,
  "next_cursor": null
}
```

Set `limit` from 1 to 100. When `has_more` is `true`, pass `next_cursor`
unchanged as the `cursor` query parameter on the next request, using the same
ad account and audience. Continue until `has_more` is `false`, even if a page
has an empty `data` array. Each item has the same four fields as the status
response; the list doesn't return the original input or idempotency key.

### Resume an Add or Remove

Use `POST /custom_audiences/{custom_audience_id}/operations/{operation_id}/resume`
to recover an accepted Add or Remove using its original inputs and saved
progress. You don't need the original idempotency key or a request body.
Confirm the operation ID from your saved response or the operation list
before resuming it.

```bash
curl -X POST \
  "https://api.ads.openai.com/v1/custom_audiences/caud_123/operations/caudop_123/resume" \
  -H "Authorization: Bearer $OPENAI_ADS_API_KEY"
```

The response is the same operation object shown above. Poll that operation
until it reaches a terminal status. Resume preserves the operation ID and
accepted input; it doesn't create a new operation or replace the uploaded
file or identifiers. An operation that has already succeeded or failed keeps
its terminal status. Resuming it can finish pending cleanup, but doesn't
apply its membership changes again.

Resume by ID supports Add and Remove only. Replace and Merge retries still
use the original submission endpoint, body, and idempotency key.

### Cancel an Add or Remove

Use `POST /custom_audiences/{custom_audience_id}/operations/{operation_id}/cancel`
to stop an accepted Add or Remove before it starts applying membership
changes. Send no request body or `Idempotency-Key` header.

```bash
curl -X POST \
  "https://api.ads.openai.com/v1/custom_audiences/caud_123/operations/caudop_123/cancel" \
  -H "Authorization: Bearer $OPENAI_ADS_API_KEY"
```

A successful cancellation returns the operation with `status: "failed"`;
there is no separate `canceled` status. Cleanup can continue asynchronously.
Canceling again is safe, and resuming a canceled operation can finish cleanup
without applying its membership changes.

Cancellation returns `409 custom_audience_mutation_conflict` if an active
operation has started applying changes or the operation already succeeded.
A failed operation keeps its existing `failed` status; cancellation doesn't
undo any changes it made before failing. A `processing` status alone doesn't
guarantee that cancellation is still possible. Cancellation doesn't support
Replace or Merge.

If cancellation returns `503 custom_audience_operation_unavailable`, it may
have stopped the operation but failed to schedule cleanup. Retry cancellation
for the same operation ID; don't start a new submission to retry cancellation.

All operation requests require access to the audience's ad account. For OAuth,
listing and polling require `ads.admin.all.read`; resuming and canceling
require both `ads.admin.all.read` and `ads.admin.all.write`.

## Check eligibility for the intended use

Use-specific eligibility is separate from `status: "ready"`:

| Intended use     | Size requirement                                                                 |
| ---------------- | -------------------------------------------------------------------------------- |
| `exclusion`      | Ready small or empty audiences can be used. No minimum matched size is required. |
| `inclusion`      | The audience must meet the matched-user minimum.                                 |
| `bid_multiplier` | The audience must meet the matched-user minimum for bid adjustments.             |

For inclusion and bid adjustments, use 25,000 matched users as the public
planning threshold. Privacy safeguards can affect the exact boundary, and
uploading 25,000 identifiers doesn't guarantee enough matched users. Don't send an `exclusion_only` creation field: eligibility depends on how
you use the audience.

Request audiences eligible for the intended use:

```bash
curl -G "https://api.ads.openai.com/v1/custom_audiences" \
  -H "Authorization: Bearer $OPENAI_ADS_API_KEY" \
  --data-urlencode "intended_use=exclusion" \
  --data-urlencode "custom_audience_ids[]=caud_123"
```

Use `inclusion` or `bid_multiplier` to check those uses. Repeat
`custom_audience_ids[]` for multiple IDs, or omit it to list eligible
audiences in the account. The response contains only eligible audiences and
a `policy_revision` token.

To recheck the selection, send that `policy_revision` with the intended use
and the selected IDs. If the API returns
`409 custom_audience_policy_revision_mismatch`, refresh without the old
token and review the selection again. `policy_revision` is not
`membership_revision` or a campaign-write parameter. The server validates
eligibility again when you save campaign or ad-group settings.

## Include or exclude audiences in a campaign

Use ready audiences eligible for the intended use in the campaign's `targeting`
object. Add audience IDs to
`custom_audiences.ids` to include matched users or
`excluded_custom_audiences.ids` to exclude them:

```bash
curl -X POST "https://api.ads.openai.com/v1/campaigns" \
  -H "Authorization: Bearer $OPENAI_ADS_API_KEY" \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: custom-audience-campaign-001" \
  -d '{
    "name": "High-value customer campaign",
    "description": "Campaign targeting selected customer audiences",
    "status": "paused",
    "bidding_type": "clicks",
    "budget": {
      "lifetime_spend_limit_micros": 300000000
    },
    "targeting": {
      "locations": {
        "countries": ["US"]
      },
      "custom_audiences": {
        "ids": ["caud_123"]
      },
      "excluded_custom_audiences": {
        "ids": ["caud_456"]
      }
    }
  }'
```

Audience inclusion and exclusion work as follows:

- Include audiences to deliver only to users who belong to at least one
  included audience.
- Exclude audiences to prevent delivery to users who belong to an excluded
  audience.
- If you use both, exclusions take precedence and the remaining audience must
  still meet the minimum size requirement.
- Don't include and exclude the same audience in a campaign.

For an exclusion-only campaign, omit `custom_audiences` and provide only
`excluded_custom_audiences`. A small exclusion audience doesn't need to meet
the inclusion minimum. If you combine inclusion and exclusion, the remaining
eligible audience must still meet the minimum.

The same fields apply to `POST /campaigns/{campaign_id}`. Preserve the other
targeting settings you want to keep when updating the targeting object.

For the remaining campaign parameters, see
[Campaigns](https://developers.openai.com/ads/api-reference/campaigns).

## Adjust bids for an audience

Add `custom_audience_bid_multipliers` to an ad group's `bidding_config` to
raise or lower the maximum bid for a ready audience eligible for
`intended_use=bid_multiplier`. Small exclusion audiences aren't automatically
eligible for bid adjustments. Bid multipliers don't change which users are
eligible to see a campaign.

```bash
curl -X POST "https://api.ads.openai.com/v1/ad_groups" \
  -H "Authorization: Bearer $OPENAI_ADS_API_KEY" \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: custom-audience-ad-group-001" \
  -d '{
    "campaign_id": "cmpn_123",
    "name": "High-value customers",
    "description": "Higher bid for selected customers",
    "status": "paused",
    "bidding_config": {
      "billing_event_type": "click",
      "max_bid_micros": 7500000,
      "custom_audience_bid_multipliers": [
        {
          "custom_audience_id": "caud_123",
          "bid_multiplier_micros": 2000000
        }
      ]
    }
  }'
```

Multipliers are expressed in millionths:

| `bid_multiplier_micros` | Bid multiplier |
| ----------------------- | -------------- |
| `100000`                | 0.1×           |
| `1000000`               | 1×             |
| `2000000`               | 2×             |
| `10000000`              | 10×            |

The supported range is `100000` through `10000000`. If a user matches multiple
configured audiences, the highest matching multiplier applies. For the
remaining ad group parameters, see [Ad Groups](https://developers.openai.com/ads/api-reference/ad-groups).

## Handle targeting safeguards and conflicts

Membership changes must preserve the size requirements of campaigns and bid
adjustments that reference the audience. For example, removing users from an
inclusion audience or adding users to an exclusion audience can make a
campaign's remaining eligible population too small. The API can reject the
change; using a file instead of inline identifiers doesn't bypass this check.

A campaign or ad-group update can conflict with an in-progress membership
change. `409 custom_audience_mutation_conflict` means that targeting update
wasn't applied. Wait for the membership operation to finish, retrieve the
current settings, and retry the intended edit if it is still appropriate.

## List and archive audiences

List the custom audiences associated with your API key's ad account:

```bash
curl -G "https://api.ads.openai.com/v1/custom_audiences" \
  -H "Authorization: Bearer $OPENAI_ADS_API_KEY" \
  --data-urlencode "limit=20"
```

Use the membership operations above to update an audience. Archive an audience
only when you no longer need it:

```bash
curl -X POST \
  "https://api.ads.openai.com/v1/custom_audiences/caud_123/archive" \
  -H "Authorization: Bearer $OPENAI_ADS_API_KEY"
```

Archiving is permanent. An archived audience can't be restored or used in
campaign targeting or bid adjustments.