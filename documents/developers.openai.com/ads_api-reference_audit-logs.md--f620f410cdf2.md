# Audit Logs

> For the complete documentation index, see [llms.txt](/llms.txt). Markdown versions of documentation pages are available by appending `.md` to the page URL.

## List audit logs

Review changes to campaigns, ad groups, ads, and other resources in the ad
account associated with your Ads API key.

`GET /audit_logs`

Use [Ads API-key authentication](https://developers.openai.com/ads/api-reference/authentication). This
endpoint does not accept Ads OAuth access tokens.

### Query parameters

| Parameter     | Type    | Required | Notes                                                                |
| ------------- | ------- | -------- | -------------------------------------------------------------------- |
| `limit`       | integer | No       | Between `1` and `100`. Default `50`.                                 |
| `after`       | string  | No       | Audit-log ID to use as the cursor for the next page.                 |
| `before`      | string  | No       | Audit-log ID to use as the cursor for the previous page.             |
| `order`       | string  | No       | `asc` or `desc`. Default `desc`.                                     |
| `campaign_id` | string  | No       | Include changes to the campaign and its ad groups and ads.           |
| `ad_group_id` | string  | No       | Include changes to the ad group and its ads.                         |
| `ad_id`       | string  | No       | Include changes to the ad.                                           |
| `actor_id`    | string  | No       | Include changes made by this actor, not changes affecting this user. |
| `start_time`  | integer | No       | Inclusive start time as a Unix timestamp in seconds.                 |
| `end_time`    | integer | No       | Inclusive end time as a Unix timestamp in seconds.                   |

Use resource IDs returned by the API, without a partition prefix, for
`campaign_id`, `ad_group_id`, and `ad_id`. When you provide multiple filters,
only entries that match all of them are returned. Time filters accept values
from `946684800` through `4102444800`.

### Example request

List up to 50 changes for a campaign and its ad groups and ads. Replace
`cmpn_123` with your campaign ID.

```bash
curl -G "https://api.ads.openai.com/v1/audit_logs" \
  -H "Authorization: Bearer $OPENAI_ADS_API_KEY" \
  --data-urlencode "campaign_id=cmpn_123" \
  --data-urlencode "limit=50" \
  --data-urlencode "order=desc"
```

### Example response

This example shows a campaign name change. Values are illustrative.

```json
{
  "object": "list",
  "data": [
    {
      "id": "alog_123",
      "audit_log_type": "update_campaign",
      "obj_type": "Campaign",
      "obj_id": "cmpn_123",
      "item_name": "Spring launch",
      "actor_type": "sofa",
      "actor_id": "user_123",
      "campaign_id": "cmpn_123",
      "ad_group_id": null,
      "changes": {
        "obj_type": "Campaign",
        "name": {
          "before": "Previous campaign name",
          "after": "Spring launch"
        }
      },
      "hierarchy_info": {
        "obj_type": "Campaign"
      },
      "ts": 1772409600
    }
  ],
  "first_id": "alog_123",
  "last_id": "alog_123",
  "has_more": false
}
```

## Response fields

The response contains the current page in `data`, its cursor boundaries in
`first_id` and `last_id`, and `has_more`. It does not include `total_count`.

| Field            | Type            | Notes                                                                  |
| ---------------- | --------------- | ---------------------------------------------------------------------- |
| `id`             | string          | Audit-log ID. Use this value for pagination.                           |
| `audit_log_type` | string          | Type of recorded change.                                               |
| `obj_type`       | string          | Type of resource that changed.                                         |
| `obj_id`         | string          | ID of the resource that changed, without a partition prefix.           |
| `item_name`      | string or null  | Resource display name when available.                                  |
| `actor_type`     | string          | Type of actor that made the change.                                    |
| `actor_id`       | string or null  | ID of the actor that made the change, when available.                  |
| `campaign_id`    | string or null  | Campaign associated with the change, when applicable.                  |
| `ad_group_id`    | string or null  | Ad group associated with the change, when applicable.                  |
| `changes`        | JSON            | Change details. The structure depends on the recorded event.           |
| `hierarchy_info` | JSON            | Related resource details. The structure depends on the recorded event. |
| `ts`             | integer or null | Event time as a Unix timestamp in seconds, when available.             |

## Pagination

Pass `last_id` as `after` to request the next page, or `first_id` as `before`
to request the previous page. The `has_more` value indicates whether more
results exist in the requested direction: forward for `after`, backward for
`before`. On the first page, it indicates whether a next page exists. Keep the
same filters and `order` when moving between pages.

Use audit-log IDs, not resource IDs, as cursors. Do not send `after` and
`before` together. An invalid cursor returns HTTP `400` with the message
"Invalid pagination cursor."