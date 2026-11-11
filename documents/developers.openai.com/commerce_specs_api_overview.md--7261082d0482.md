# Overview

> For the complete documentation index, see [llms.txt](/llms.txt). Markdown versions of documentation pages are available by appending `.md` to the page URL.

The API lets you manage product feed data through three API surfaces:

- [Feeds](https://developers.openai.com/commerce/specs/api/feeds) creates product feeds and retrieves feed
  metadata.
- [Products](https://developers.openai.com/commerce/specs/api/products) retrieves products for a feed.
- [Promotions](https://developers.openai.com/commerce/specs/api/promotions) lets you retrieve, create, or
  update individual promotions for a feed.

To update your product catalog, [upload a feed file over SFTP](https://developers.openai.com/commerce/specs/file-upload/overview).

## REST endpoints

All API endpoints use the same request and response headers. See the Feeds,
Products, and Promotions references for each endpoint's request and response bodies.

### Request headers

| Field             | Description                                               | Example Value                                   |
| :---------------- | :-------------------------------------------------------- | :---------------------------------------------- |
| `Authorization`   | API key used to make requests                             | `Bearer api_key_123`                            |
| `Accept-Language` | The preferred locale for content like messages and errors | `en-US`                                         |
| `User-Agent`      | Information about the client making this request          | `ChatGPT/2.0 (Mac OS X 15.0.1; arm64; build 0)` |
| `Idempotency-Key` | Key used to ensure requests are idempotent                | `idempotency_key_123`                           |
| `Request-Id`      | Unique key for each request for tracing purposes          | `request_id_123`                                |
| `Content-Type`    | Type of request content                                   | `application/json`                              |
| `Timestamp`       | Formatted as an RFC 3339 string                           | `2025-09-25T10:30:00Z`                          |
| `API-Version`     | API version                                               | `2025-09-12`                                    |

### Response headers

| Field             | Description                           | Example Value         |
| :---------------- | :------------------------------------ | :-------------------- |
| `Idempotency-Key` | Idempotency key passed in the request | `idempotency_key_123` |
| `Request-Id`      | Request ID passed in the request      | `request_id_123`      |