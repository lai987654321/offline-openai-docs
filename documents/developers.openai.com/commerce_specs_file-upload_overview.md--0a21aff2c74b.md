# Overview

> For the complete documentation index, see [llms.txt](/llms.txt). Markdown versions of documentation pages are available by appending `.md` to the page URL.

Use this guide to move from first sample to production feed delivery with
minimal back-and-forth, and use the
[products spec](https://developers.openai.com/commerce/specs/file-upload/products) for full schema and field
definitions.

If you upload a product feed through Ads Manager, use the [Ads product feeds
guide](https://developers.openai.com/ads/product-feeds#use-the-correct-feed-schema) for the additional Ads
eligibility requirement before you upload.

## Feed model and delivery

### Supported feed type

- **Full snapshot feed**: a complete catalog export treated as the source of truth.
- **Recommended cadence**: at least daily.

### Delivery and file requirements

| Topic              | Guidance                                                                                                                                           |
| :-------------------------------------------------------- | :------------------------------------------------------------------------------------------------------------------------------------------------- |
| Delivery model     | Push feeds to OpenAI via SFTP.                                                                                                                     |
| Formats            | Prefer `parquet` (ideally with `ztsd` compression). `jsonl.gz`, `csv.gz`, and `tsv.gz` are also supported.                                         |
| Encoding           | UTF-8                                                                                                                                              |
| Filename stability | Use a stable file name. Keep the same file name on every update and overwrite it with the latest snapshot instead of creating a new name each run. |
| Update behavior    | If you use multiple shard files, keep that shard set stable and replace the same shard files on each update.                                       |
| Shard sizing       | Up to 500k items per shard is recommended; target shard files under ~500MB                                                                         |

### Watch common ingestion failures

- Missing required fields
- Outdated or non-spec field names
- Malformed field values

### Understand product retention and removal

A product is not deleted immediately when missing from a processed snapshot.
OpenAI retains its most recently processed record for up to 14 days.
This protects products from disappearing because a shard is temporarily missing
or delayed.

- To make a product ineligible for search the next time OpenAI processes a snapshot, set
  `is_eligible_search=false`.
- To remove a product by omission, leave it out of every shard in later full
  snapshots. The retained record expires within 14 days.

### Operate as a snapshot pipeline

- Publish full snapshots on a predictable cadence (at least daily).

### Update multi-file feeds

The SFTP root directory represents your entire catalog. You do not need to send
a completion marker. After uploads stop changing for a short time, OpenAI
processes every file in the root directory.

- Reuse the same shard filenames and overwrite them in place.
- Upload all shards without long pauses. If processing starts before every shard
  arrives, OpenAI processes the complete root directory again after the remaining
  shards arrive and uploads stop changing.
- OpenAI matches products by `item_id`, not by filename, so moving a product between
  shards does not reset it. When possible, use a deterministic rule based on
  `item_id` for predictable shard assignment.
- If multiple brand feeds share one location, use clear brand-prefixed names.

### Validate in phases

- Start with a small sample (around 100 items).
- Include all required fields in every sample row.
- Run QA on the first full snapshot.
- Move to steady-state automation once validation is clean.