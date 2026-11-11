# Ad Account

> For the complete documentation index, see [llms.txt](/llms.txt). Markdown versions of documentation pages are available by appending `.md` to the page URL.

## Update account brand metadata

Update account names or the advertiser icon. Send at least one field.

Changing the legal or public brand name pauses ad delivery until the account
passes review.

This operation must be enabled for the ad account. If it returns `403`, contact
your OpenAI partner representative.

`POST /ad_account/brand`

| Field             | Type   | Required | Notes                                                     |
| ----------------- | ------ | -------- | --------------------------------------------------------- |
| `legal_name`      | string | No       | Legal business name.                                      |
| `account_name`    | string | No       | Internal name shown in Ads Manager.                       |
| `brand_name`      | string | No       | Public advertiser name shown in ads.                      |
| `name`            | string | No       | Legacy field that sets all three names to the same value. |
| `favicon_file_id` | string | No       | File ID uploaded with `purpose: "account_favicon"`.       |

Use `legal_name`, `account_name`, or `brand_name` to update names independently.
Omitted names remain unchanged.

Legacy `name` sets all three names to the same value, replacing any separate
values. Combining `name` with an individual name field returns `422`.

Names must contain 2–1000 characters after trimming and cannot contain `<` or `>`.
The API rejects `null` and blank names.

To change only the name shown in ads:

```bash
curl -X POST "https://api.ads.openai.com/v1/ad_account/brand" \
  -H "Authorization: Bearer $OPENAI_ADS_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "brand_name": "Acme"
  }'
```

Upload the advertiser icon with the [file endpoint](https://developers.openai.com/ads/api-reference/files#upload-an-account-favicon),
then assign it to the account:

```bash
curl -X POST "https://api.ads.openai.com/v1/ad_account/brand" \
  -H "Authorization: Bearer $OPENAI_ADS_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "favicon_file_id": "file_123"
  }'
```

Returns the updated account in the same format as `GET /ad_account`.

The API may save changes before returning `503`. Retrieve the account to check
its values, then retry the same request.

## Get ad account metadata

Fetch metadata for the current ad account.

`GET /ad_account`

This endpoint takes no request body or query parameters.

```bash
curl -X GET "https://api.ads.openai.com/v1/ad_account" \
  -H "Authorization: Bearer $OPENAI_ADS_API_KEY"
```

```json
{
  "id": "adacct_123",
  "name": "Acme LLC",
  "legal_name": "Acme LLC",
  "account_name": "Acme US campaigns",
  "brand_name": "Acme",
  "url": "https://www.acme.example",
  "preview_url": null,
  "status": "active",
  "timezone": "UTC",
  "currency_code": "USD",
  "review": {
    "status": "approved"
  }
}
```

The response includes:

- `id` for the ad account
- `name` for the legal business name, retained for compatibility
- `legal_name` for the same legal business name
- `account_name` for the internal name shown in Ads Manager
- `brand_name` for the public advertiser name shown in ads
- `url` for the primary destination
- `preview_url` for the advertiser icon preview URL when one is available
- `status` when an account status is available
- `timezone` for the ad account timezone
- `currency_code` for the account currency
- `review` for the account's brand review status

`legal_name`, `account_name`, and `brand_name` are optional response fields.
Unset account and brand names default to the legal name.

## Account spending limits

Set a shared spending limit across all campaigns in an ad account. Choose a
date range limit for a total allowance over a fixed period, or a daily limit
for an allowance that renews each day. Campaign budgets still apply; account
limits do not allocate spend between campaigns or pace delivery.

> **Note:** Account spending limits are available only for ad accounts on
> postpaid invoice billing. Existing daily limits can still be viewed and removed
> if the account's billing changes. All requests in this section, including reads,
> require permission to manage billing for the account.

Both types use the account currency and timezone:

- Amounts are nonnegative integers in micros: `100000000` is 100 currency units.
  Use the currency's smallest unit, such as multiples of `10000` micros for USD.
  The maximum is 1 billion currency units (`1000000000000000` micros).
- Dates use `YYYY-MM-DD`. Limits start at midnight on the start date and end
  at midnight on the end date, in the account timezone. The end date is excluded.
- Daily and date range limits cannot overlap. Existing scheduled limits are
  not removed when you create a daily limit.
- Daily allowances do not carry over or change with daylight saving time.
  The account timezone cannot change while a daily limit exists.

Limits apply to billable ad spend, not taxes or the total invoice. Delivery
can take time to stop after a limit is reached. Amount edits take effect on
save and retain counted spend; a decrease below recorded spend is rejected.
Edits are not retroactive: delayed charges use the limit effective when the
event occurred, and concurrent billing can add spend while an edit is saved.
A lower limit cannot undo spend already billed.

## List account spending limits

`GET /ad_account/spend_limit_windows`

Read the configuration before making changes. This endpoint takes no request
body or query parameters. Use the [account's Ads API key](https://developers.openai.com/ads/api-reference/authentication).

```bash
curl "https://api.ads.openai.com/v1/ad_account/spend_limit_windows" \
  -H "Authorization: Bearer $OPENAI_ADS_API_KEY"
```

The response has `object: "list"` and these fields:

| Field                       | Description                                                                                                            |
| --------------------------- | ---------------------------------------------------------------------------------------------------------------------- |
| `data`                      | Date range limits, ordered by start date. Daily limits are not in this array.                                          |
| `daily_limit`               | The active or upcoming daily limit, or `null` when none exists.                                                        |
| `revision`                  | Configuration revision to send as `expected_revision` in daily mutations. Use `0` only if the field is absent.         |
| `earliest_daily_start_date` | Earliest allowed start date for a new daily limit. It is never today. The full period must also avoid existing limits. |
| `earliest_dated_start_date` | Additional start-date floor for new or rescheduled date range limits after a daily limit, or `null` when none applies. |
| `can_create_daily_limit`    | Whether you can create a new daily limit. `false` while one exists does not prevent editing it.                        |
| `evaluated_at`              | Configuration evaluation time, not the freshness of spend data.                                                        |

Each date range limit includes `window_id`, `start_date`, `end_date`,
`amount_micros`, `name`, `io_id`, and `status` (`upcoming`, `active`, or
`completed`). Use `can_edit`, `can_edit_start_date`, and `can_delete` to determine
which changes are available. `spent_micros` is included for the active window
when available; an omitted value does not mean zero spend.

The `daily_limit` object includes `amount_micros`, `start_date`, `end_date`
(`null` for no end date), `timezone`, and `status` (`upcoming` or `active`).
It also includes:

| Field              | Description                                                                                             |
| ------------------ | ------------------------------------------------------------------------------------------------------- |
| `spent_micros`     | Spend counted toward today's allowance; `null` if unavailable or not active.                            |
| `remaining_micros` | Today's remaining allowance; `null` if unavailable or not active.                                       |
| `spend_as_of`      | Spend counter update time in ISO 8601 format, or `null` if unavailable.                                 |
| `next_reset`       | Next midnight with a fresh allowance, in ISO 8601 format; `null` before activation or on the final day. |

## Create a date range limit

`POST /ad_account/spend_limit_windows`

| Field           | Type           | Required | Notes                                                                                         |
| --------------- | -------------- | -------- | --------------------------------------------------------------------------------------------- |
| `start_date`    | string         | Yes      | Today or later in the account timezone; also honor `earliest_dated_start_date` when returned. |
| `end_date`      | string         | Yes      | Exclusive end date, after `start_date`.                                                       |
| `amount_micros` | integer        | Yes      | Total allowance for the entire period.                                                        |
| `name`          | string or null | No       | Optional label, up to 256 characters.                                                         |
| `io_id`         | string or null | No       | Optional insertion order reference, up to 256 characters.                                     |

For a USD account, this example sets a $1,000 total allowance for October 1–7.
Replace the dates with a valid period that does not overlap another limit.

```bash
curl -X POST "https://api.ads.openai.com/v1/ad_account/spend_limit_windows" \
  -H "Authorization: Bearer $OPENAI_ADS_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "start_date": "2026-10-01",
    "end_date": "2026-10-08",
    "amount_micros": 1000000000,
    "name": "October promotion"
  }'
```

The response is the created date range limit object, including its `window_id`.
You can schedule up to 60 future date range limits.

## Update a date range limit

`POST /ad_account/spend_limit_windows/{window_id}`

Send at least one field from the create request. Omitted fields retain their
values; send `null` to clear `name` or `io_id`. Dates and amounts cannot be
`null`. Date range mutations do not require `expected_revision`.

Only upcoming limits can change their start date. An active limit's end date
must remain in the future. Completed limits cannot be edited.

For example, to change the total allowance to $1,500 for a USD account, send:

```json
{
  "amount_micros": 1500000000
}
```

The response is the updated date range limit object.

## Delete a date range limit

`POST /ad_account/spend_limit_windows/{window_id}/delete`

No request body is required. You can delete active or upcoming limits, but not
completed limits. Deletion takes effect on save and does not erase historical
spend.

```json
{
  "window_id": "slw_123",
  "object": "ad_account_spend_limit_window.deleted",
  "deleted": true
}
```

## Set a daily limit

`POST /ad_account/daily_spend_limit`

Use this endpoint to create or update a daily allowance. It repeats until
removed or until its optional end date. New daily limits start tomorrow or
later; use `earliest_daily_start_date` from the list response.

| Field               | Type           | Required | Notes                                                                                                                                                                                               |
| ------------------- | -------------- | -------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `amount_micros`     | integer        | Yes      | Allowance for each day. Required even when only changing the end date.                                                                                                                              |
| `expected_revision` | integer        | Yes      | `revision` from the latest list response.                                                                                                                                                           |
| `start_date`        | string         | No       | First allowed day. On first creation, defaults to `earliest_daily_start_date`. Required when creating a new limit after removal or expiry. Omit when editing; an existing start date cannot change. |
| `end_date`          | string or null | No       | Exclusive end date, after the start date and in the future. Omit to retain an existing end date; send `null` for no end date.                                                                       |

For a USD account, this example creates a $100 daily allowance with no end date.
Replace the illustrative revision and start date with values from the latest
list response, and check for overlaps before submitting.

```bash
curl -X POST "https://api.ads.openai.com/v1/ad_account/daily_spend_limit" \
  -H "Authorization: Bearer $OPENAI_ADS_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "amount_micros": 100000000,
    "expected_revision": 12,
    "start_date": "2026-10-01",
    "end_date": null
  }'
```

For an amount edit, send `amount_micros` and the latest `expected_revision`;
omit `start_date`. Both increases and decreases take effect on save, subject
to the [edit rules](#account-spending-limits).

The response contains `spend_limits`, with the same fields as the list response.
Read `spend_limits.daily_limit` for the saved limit and
`spend_limits.revision` for the new revision.

## Remove a daily limit

`POST /ad_account/daily_spend_limit/delete`

Send `expected_revision` from the latest list response:

```json
{
  "expected_revision": 13
}
```

Removal takes effect on save and retains historical accounting for delayed
charges. The response contains the updated list under `spend_limits`, with
`daily_limit: null`.

## Handle spending limit errors

| Status | Action                                                                                                                                                                          |
| ------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `400`  | Correct missing or malformed request fields, including invalid calendar dates or dates outside the supported range of `2000-01-01` through `2100-01-01`.                        |
| `409`  | Refresh the list and reconcile a stale revision or configuration conflict before resubmitting the change.                                                                       |
| `422`  | Correct the amount, date ordering, overlapping limits, or a change to a completed date range limit. A decrease below recorded spend returns `budget_window_amount_below_spend`. |
| `503`  | Refresh before retrying a daily mutation: the change may have succeeded even if its response could not be loaded.                                                               |