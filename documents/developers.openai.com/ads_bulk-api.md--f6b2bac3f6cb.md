# Bulk API

> For the complete documentation index, see [llms.txt](/llms.txt). Markdown versions of documentation pages are available by appending `.md` to the page URL.

The Bulk API creates or updates campaigns, ad groups, and ads in a single
asynchronous job. Submit up to 1,000 operations, poll the job, and inspect the
result of each operation.

The Bulk API is in limited preview and is enabled per ad account. It isn't
  included in the downloadable OpenAPI spec. If a bulk endpoint returns `404`,
  contact your OpenAI account team to confirm access for the account associated
  with your Ads API key.

## Submit a bulk job

Create a campaign, ad group, and ad in one request. The example creates paused
resources so you can verify them before delivery starts.

`POST /bulk_mutation_jobs`

```bash
curl -X POST "https://api.ads.openai.com/v1/bulk_mutation_jobs" \
  -H "Authorization: Bearer $OPENAI_ADS_API_KEY" \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: spring-launch-job-001" \
  -d '{
    "validate_only": false,
    "partial_failure": true,
    "operations": [
      {
        "operation_id": "create-campaign",
        "type": "campaign.create",
        "idempotency_key": "campaign-spring-launch",
        "input": {
          "name": "Spring launch",
          "max_budget_micros": 100000000,
          "billing_event_type": "impression",
          "budget_type": "lifetime",
          "status": "paused"
        }
      },
      {
        "operation_id": "create-ad-group",
        "type": "ad_group.create",
        "idempotency_key": "ad-group-prospecting",
        "input": {
          "campaign_idempotency_key": "campaign-spring-launch",
          "name": "Prospecting",
          "context_hints": ["shoes", "spring fashion"],
          "status": "paused"
        }
      },
      {
        "operation_id": "create-ad",
        "type": "ad.create",
        "idempotency_key": "ad-prospecting-1",
        "input": {
          "campaign_idempotency_key": "campaign-spring-launch",
          "ad_group_idempotency_key": "ad-group-prospecting",
          "title": "Fresh shoes",
          "body": "Find your next pair",
          "target_url": "https://example.com/shoes",
          "source_image_url": "https://developers.openai.com/showcase/openai-imagegen-demo.png",
          "status": "paused"
        }
      }
    ]
  }'
```

The API returns `202 Accepted` with a job ID:

```json
{
  "id": "blkmtnjob_6a2b773d47b481908aa6078025a64ad3",
  "status": "pending",
  "operation_count": 3,
  "created_at": 1784304000,
  "completed_at": null
}
```

Use the Ads API key from the Settings tab in [Ads Manager](https://ads.openai.com).
Each key works with one ad account, so don't add an `OpenAI-Ad-Account` header
when using an API key.

### Request fields

| Field             | Type     | Required | Description                                                                                               |
| ----------------- | -------- | -------- | --------------------------------------------------------------------------------------------------------- |
| `operations`      | object[] | Yes      | Between `1` and `1,000` create or update operations.                                                      |
| `validate_only`   | boolean  | No       | Validates request fields and dependencies without changing ad resources when `true`. Defaults to `false`. |
| `partial_failure` | boolean  | No       | Continues independent operations after an error when `true`. Defaults to `true`.                          |

Set `partial_failure` to `false` to skip later operations after an operation
fails. This setting doesn't roll back operations that already completed.

Validation-only jobs don't guarantee that operations can complete successfully.
They don't check update-target existence, image fetching, entity limits, or
other write-time errors.

The optional `Idempotency-Key` header makes it safe to retry an uncertain
request with the same body. Reusing the header with a different body returns an
error. To rerun a `failed` or `partially_failed` job, submit the same body with
a new request-level key. Successful creates are reused.

## Supported operations

Each entry in `operations` must include a unique `operation_id`, an operation
`type`, and an `input` object. Create operations require a unique
`idempotency_key`. Update operations require `target_resource_id` and at least
one input field.

| Type              | Required input                                                                                            | Other supported input                                                                                         |
| ----------------- | --------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------- |
| `campaign.create` | `name`, `max_budget_micros`                                                                               | `billing_event_type`, `budget_type`, `status`, `target_countries`, `location_ids`                             |
| `campaign.update` | At least one supported field                                                                              | `name`, `description`, `status`, `max_budget_micros`, `budget_type`, `start_time`, `end_time`, `location_ids` |
| `ad_group.create` | `campaign_idempotency_key`, `name`                                                                        | `context_hints`, `exclusion_hints`, `max_bid_micros`, `max_cpm_bid_micros`, `status`                          |
| `ad_group.update` | At least one supported field                                                                              | `name`, `description`, `status`, `context_hints`, `exclusion_hints`, `max_bid_micros`, `max_cpm_bid_micros`   |
| `ad.create`       | `campaign_idempotency_key`, `ad_group_idempotency_key`, `title`, `body`, `target_url`, `source_image_url` | `status`                                                                                                      |
| `ad.update`       | At least one supported field                                                                              | `name`, `status`, `creative`                                                                                  |

Create operations can refer to parents created in the same job. Set
`campaign_idempotency_key` to the campaign operation's `idempotency_key`, and
set `ad_group_idempotency_key` to the ad group operation's `idempotency_key`.
The campaign reference on `ad.create` must match the campaign reference on
its parent `ad_group.create` operation.

You can mix create and update operations in one job. Updates can target only
resources that exist when you submit the job, so you can't update a resource
created in the same job. Update each resource only once in a job.

Create statuses are `active` or `paused`; update statuses also support
`archived`. `campaign.create` defaults to an impression-billed, lifetime,
paused campaign. Its budget must be at least `1000000` currency micros.

Ad-group bids must match the parent campaign's billing event. Provide only one
of `max_bid_micros` for clicks or `max_cpm_bid_micros` for impressions; CPM
requires account access. Campaign and ad-group names allow `3` to `1,000`
characters. Ad titles allow `3` to `50`, bodies allow up to `100`, and URLs
allow up to `2,048` characters. Campaigns support up to `2,500` location IDs,
and ad groups support up to `2,000` context hints. See
[Location Targeting](https://developers.openai.com/ads/location-targeting) for location IDs.

When updating an ad creative, include `title`, `body`, `target_url`, and
`file_id`. For example, pause an existing ad:

```json
{
  "operations": [
    {
      "operation_id": "pause-ad",
      "type": "ad.update",
      "target_resource_id": "ad_501",
      "input": {
        "status": "paused"
      }
    }
  ]
}
```

## Retrieve a job

Poll the job ID returned by the create request until the job reaches a
terminal status.

`GET /bulk_mutation_jobs/{job_id}`

```bash
curl -X GET \
  "https://api.ads.openai.com/v1/bulk_mutation_jobs/blkmtnjob_6a2b773d47b481908aa6078025a64ad3" \
  -H "Authorization: Bearer $OPENAI_ADS_API_KEY"
```

| Status             | Meaning                                                                      |
| ------------------ | ---------------------------------------------------------------------------- |
| `pending`          | The job is waiting to run.                                                   |
| `in_progress`      | The job is processing operations.                                            |
| `completed`        | All operations completed successfully.                                       |
| `partially_failed` | At least one operation succeeded and another returned `failed` or `skipped`. |
| `failed`           | No operations succeeded. Inspect the operation results for details.          |

`completed`, `partially_failed`, and `failed` are terminal statuses.

## List operation results

Retrieve the result of each operation after submitting a job.

`GET /bulk_mutation_jobs/{job_id}/operations`

Set `limit` to between `1` and `100` results per page. It defaults to `100`.

```bash
curl -X GET \
  "https://api.ads.openai.com/v1/bulk_mutation_jobs/blkmtnjob_6a2b773d47b481908aa6078025a64ad3/operations?limit=100" \
  -H "Authorization: Bearer $OPENAI_ADS_API_KEY"
```

```json
{
  "object": "list",
  "data": [
    {
      "operation_id": "create-ad",
      "type": "ad.create",
      "status": "created",
      "resource_id": "ad_501",
      "submitted_version_id": "adver_501",
      "error_code": null,
      "error": null,
      "retryable": null,
      "retry_after_seconds": null
    }
  ],
  "has_more": false,
  "complete": true,
  "error": null
}
```

Use `has_more` and the last returned `operation_id` to request the next page
with `after`. Pagination cursors are only available after `complete` is `true`.
While a job is running, the endpoint can return an incomplete snapshot of the
results collected so far.

Each operation result includes its `operation_id`, `type`, status, and error
fields that can be `null`. `failed` results can populate `error_code`, `error`,
`retryable`, and `retry_after_seconds`. The top-level `error` field describes a
job-level error when present. `submitted_version_id` is `null` for campaign
and ad-group creates.

| Status      | Meaning                                                                               |
| ----------- | ------------------------------------------------------------------------------------- |
| `created`   | The create operation succeeded.                                                       |
| `updated`   | The update operation succeeded.                                                       |
| `validated` | The operation passed request and dependency validation in a validation-only job.      |
| `failed`    | The operation returned an error. Use the retry fields for next steps.                 |
| `skipped`   | The operation didn't run because a dependency or earlier operation returned an error. |

## Limits and retries

Bulk jobs have the following default limits:

| Limit                               | Value                          |
| ----------------------------------- | ------------------------------ |
| Operations per job                  | `1,000`                        |
| Request body size                   | `16 MiB`                       |
| Serialized operation size           | `512 KiB`                      |
| Create requests per ad account      | `10` requests per `10` seconds |
| Operation results per page          | `100`                          |
| Self-serve campaigns per ad account | `5,000` non-archived campaigns |
| Self-serve ad groups per ad account | `5,000` non-archived ad groups |
| Self-serve ads per ad account       | `5,000` active or paused ads   |

Keep `operation_id` and create-operation `idempotency_key` values unique
within a job. Each value can contain up to `255` characters. If a result's
`retryable` field is `true`, wait for `retry_after_seconds` when provided
before submitting the same body in a new job. Reuse the original
create-operation `idempotency_key` values when retrying that request.