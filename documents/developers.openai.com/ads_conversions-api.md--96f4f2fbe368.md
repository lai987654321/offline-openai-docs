# Conversions API

> For the complete documentation index, see [llms.txt](/llms.txt). Markdown versions of documentation pages are available by appending `.md` to the page URL.

Conversions API (CAPI) sends conversion events directly from your server to OpenAI—for example, when your backend confirms a purchase. It complements the [Measurement Pixel](https://developers.openai.com/ads/measurement-pixel), which sends events from a visitor’s browser.

Use both to combine browser activity with confirmed backend conversions. CAPI helps you:

- Measure conversions without depending solely on browser event delivery.
- Improve matching with [supported customer identifiers](#send-user-data).
- Control event delivery and retries from your server.

When both integrations report the same conversion, [deduplicate browser and server events](#deduplicate-browser-and-server-events) using the same event ID and Pixel ID. Follow the attribution guidance below to forward available click and browser references. Start with a key conversion, such as a purchase, then follow the setup instructions.

## Send events

We recommend sending all conversion events, not just those with an `oppref`,
  to incorporate view-through conversions in your campaign's performance
  metrics.

Send events to the Conversions API from your server only.

```bash
curl -X POST "https://bzr.openai.com/v1/events?pid=<PIXEL-ID>" \
  -H "Authorization: Bearer <API-KEY>" \
  -H "Content-Type: application/json" \
  --data '{
    "validate_only": false,
    "events": []
  }'
```

You can provision a Pixel ID and Conversions API key from the conversions tab in Ads Manager. Approved API partners can use the Ads API key associated with a client account to provision both resources with the [conversion setup endpoints](https://developers.openai.com/ads/api-reference/conversion-setup).

| Value                | Required | Description                                              |
| -------------------- | -------- | -------------------------------------------------------- |
| `pid`                | Yes      | Your Pixel ID.                                           |
| `validate_only`      | No       | Validates events without saving them when `true`.        |
| `integration_source` | No       | Stable identifier for the integration sending the batch. |
| `events`             | Yes      | The events to send.                                      |

The API accepts batches of up to 1,000 events. If one event in the batch fails,
the full batch fails.

For app lifecycle events, use the Pixel ID from an existing web data source.
Send `app_installed` and `app_opened` from your server with `action_source`
set to `mobile_app`. Native mobile SDK setup and mobile data sources are not
currently supported.

## Web-event attribution reporting

Web events support click-through attribution and, when available for your
account, view-through attribution. Click-through attribution uses the applicable
configured click window. View-through conversions use a fixed one-day window
after an eligible ad impression. Whether view-through reporting is available
does not depend on your configured click window. If a conversion is eligible
for both, the click takes precedence.

View-through attribution does not use a separate request or event field. Ads
Manager reports view-through conversions as a separate, campaign-level metric.
They are not included in `Conversions`, which remains the click-through
conversion total. CPA, post-click CVR, bidding, billing, and conversion
optimization also remain click-through-based. App lifecycle events and mobile
measurement integrations remain click-through-based.

## Identify partner integrations

If you send events on behalf of advertisers, include `integration_source` at
the top level of every Conversions API request. Mobile measurement partners
and other integrations should use the same stable identifier on every request,
such as `acme_measurement` or `example_analytics`. The value applies to every
event in the batch.

For example, a measurement partner can identify itself when sending an app
install event:

```json
{
  "integration_source": "acme_measurement",
  "events": [
    {
      "id": "app_installed_123",
      "type": "app_installed",
      "timestamp_ms": <TIMESTAMP_MS>,
      "action_source": "mobile_app",
      "data": {
        "type": "customer_action"
      }
    }
  ]
}
```

Replace `<TIMESTAMP_MS>` with the event timestamp in milliseconds.

Use 1–64 ASCII characters. Start with a letter or digit, and use only letters,
digits, periods (`.`), underscores (`_`), or hyphens (`-`). The API trims
whitespace and converts the value to lowercase before validation.

Use `integration_source` to identify the integration sending the request. This
field does not affect authentication or authorization.

## Event structure

Each event includes the event metadata and a `data` object.

```json
{
  "id": "order_12345",
  "type": "order_created",
  "timestamp_ms": 1773892800000,
  "oppref": "oppref_abc",
  "source_url": "https://shop.example.com/checkout/confirmation",
  "action_source": "web",
  "user": {
    "obref": "123e4567-e89b-42d3-a456-426614174000",
    "emails_sha256": [
      "b4c9a289323b21a01c3e940f150eb9b8c542587f1abfd8f0e1cc1ffc5e475514"
    ],
    "external_ids_sha256": [
      "18f69bcd2f9cc9c38195e722b2a5590429840ea5090971d2256e026926e55fa1"
    ],
    "countries": ["US"],
    "cities": ["San Francisco"],
    "postal_codes": ["94107"],
    "ip_address": "203.0.113.1",
    "user_agent": "Mozilla/5.0"
  },
  "data": {
    "type": "contents"
  }
}
```

| Field               | Required | Description                                                                                                                                                                                                                                                                                  |
| ------------------- | -------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `id`                | Yes      | A non-empty string that identifies the event. Reuse the same ID when retrying or sending the same conversion through another integration.                                                                                                                                                    |
| `type`              | Yes      | Use `appointment_scheduled`, `checkout_started`, `contents_viewed`, `custom`, `items_added`, `lead_created`, `order_created`, `page_viewed`, `registration_completed`, `subscription_created`, or `trial_started`. Native app events also support `app_installed` and `app_opened`.          |
| `timestamp_ms`      | Yes      | Event time as an integer Unix timestamp in milliseconds. The timestamp must be within the last 7 days and no more than 10 minutes in the future.                                                                                                                                             |
| `custom_event_name` | Depends  | Required when `type` is `custom`. Use 1–64 letters, digits, underscores, or hyphens; start and end with a letter or digit. The name cannot match a standard event name. The API converts it to lowercase.                                                                                    |
| `oppref`            | No       | An opaque, OpenAI-provided attribution identifier. Pass the original string without modification.                                                                                                                                                                                            |
| `source_url`        | Depends  | Required for web events when `action_source` is `web`; optional for native app events. Use a URL with a scheme and host, such as `https://shop.example.com/checkout`.                                                                                                                        |
| `action_source`     | Depends  | Use `web`, `mobile_app`, `offline`, `physical_store`, `phone_call`, `email`, or `other`. The value must be `mobile_app` for `app_installed` and `app_opened` events.                                                                                                                         |
| `user`              | No       | An object containing optional conversion-matching fields. See [Send user data](#send-user-data).                                                                                                                                                                                             |
| `opt_out`           | No       | Use `true` to opt the event out of future user-level personalization, or `false` for the default behavior. For clarity, OpenAI does not currently use data collected via the Conversions API for user-level personalization. If we do so in the future, we will respect this opt-out toggle. |
| `data`              | Yes      | An object describing the conversion. Its `type` field must match the data shape required for the event name (see [Supported Events](https://developers.openai.com/ads/supported-events)) and use one of the event data shapes below.                                                                                      |

See [Supported Events](https://developers.openai.com/ads/supported-events) for event names and data shapes.

Unlike the pixel, the API does not capture `oppref` for you. Capture the value
yourself and pass it with the server event when it is available to support click
matching. View-through attribution does not require a separate request or
event field.

### Event data

Each `events[].data` object supports the following fields. The available fields
depend on its `type`.

| Field                     | Required | Description                                                                                                                                                                   |
| ------------------------- | -------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `type`                    | Yes      | Use `contents`, `customer_action`, `plan_enrollment`, or `custom`, as required by the event type. The `app_installed` and `app_opened` event types require `customer_action`. |
| `amount`                  | No       | The event-level monetary value as an integer in the currency's standard minor unit. For example, use `4200` for $42.00 with `currency: "USD"`.                                |
| `currency`                | Depends  | Required when `amount` is present. Use a valid three-letter ISO 4217 currency code, such as `USD`, `EUR`, or `JPY`; the API converts values to uppercase.                     |
| `contents`                | No       | An array of item objects. Available when `data.type` is `contents`, `plan_enrollment`, or `custom`; not available for `customer_action`.                                      |
| `contents[].id`           | No       | A string containing your internal product, item, or content identifier.                                                                                                       |
| `contents[].group_id`     | No       | A string identifying the product group or parent item.                                                                                                                        |
| `contents[].name`         | No       | A string containing the item's display name.                                                                                                                                  |
| `contents[].content_type` | No       | A string describing the item category, such as `product`, `plan`, or `page`.                                                                                                  |
| `contents[].quantity`     | No       | The item quantity as an integer.                                                                                                                                              |
| `contents[].amount`       | No       | The per-unit price as an integer in the currency's standard minor unit. Supply `contents[].quantity` separately.                                                              |
| `contents[].currency`     | No       | A valid three-letter ISO 4217 currency code for the item, such as `USD`, `EUR`, or `JPY`.                                                                                     |
| `contents[].variant_dict` | No       | An object whose keys and values are strings, such as `{"size": "medium", "color": "blue"}`.                                                                                   |
| `plan_id`                 | No       | A string identifying your subscription or trial plan. Available when `data.type` is `plan_enrollment` or `custom`.                                                            |

Use `contents[].amount` for the price of one unit and the event-level `amount`
for the value of the whole event. See
[Item and event amounts](https://developers.openai.com/ads/supported-events#item-and-event-amounts) for an
example with `quantity: 2`.

## Send user data

Add an optional `user` object to each event to improve conversion matching. The
object is event-scoped, so put it inside each entry in `events`, not at the
request root.

Every field in the `user` object is optional. Include only the fields you have
for the user.

### Normalize identifiers before hashing

Normalize each identifier as follows:

- Email address: trim leading and trailing whitespace and convert the value to
  lowercase.
- Phone number: keep the country calling code. Remove all whitespace,
  parentheses, periods, and hyphens, then remove a leading `+` and any
  leading zeroes. Hash the resulting 8–15 digits. For example,
  `+1 (415) 555-2671` becomes `14155552671`.
- External ID: trim leading and trailing whitespace. Preserve case and all
  other characters.
- First and last name: convert the value to lowercase and remove all whitespace
  and ASCII punctuation. Apart from converting to lowercase, preserve non-ASCII characters;
  don't strip accents or transliterate. For example, `O'Connor` becomes
  `oconnor`, and `José` becomes `josé`.

The normalized value is the exact string to encode and hash:

| Identifier   | Input               | Normalized value |
| ------------ | ------------------- | ---------------- |
| Phone number | `+1 (415) 555-2671` | `14155552671`    |
| First name   | `Mary Jane`         | `maryjane`       |
| Last name    | `O'Connor`          | `oconnor`        |
| First name   | `José`              | `josé`           |

Encode each normalized value as UTF-8, compute its SHA-256 digest, and send the
digest as a lowercase, 64-character hexadecimal string. Don't send raw email
addresses, phone numbers, external IDs, first names, or last names. Send
geographic values as raw strings.

### User object example

Place this object inside an event at `events[].user`:

```json
{
  "obref": "123e4567-e89b-42d3-a456-426614174000",
  "phone_numbers_sha256": [
    "758fbf68945f21c416814c539ab578876c8d98fb69e6da692def92cd52417fe0"
  ],
  "emails_sha256": [
    "b4c9a289323b21a01c3e940f150eb9b8c542587f1abfd8f0e1cc1ffc5e475514"
  ],
  "external_ids_sha256": [
    "18f69bcd2f9cc9c38195e722b2a5590429840ea5090971d2256e026926e55fa1"
  ],
  "first_names_sha256": [
    "fdee430d40bd57deeac186cd9790033d0f06f909a8806e7ce6e717ab7c7d5029"
  ],
  "last_names_sha256": [
    "fb1e7ec987523d2cb9e022cec1d6ae7c99dc46edfae4fe51254025fe4bea571f"
  ],
  "regions": ["California"],
  "postal_codes": ["94107"],
  "cities": ["San Francisco"],
  "countries": ["US"],
  "android_advertising_id": "38400000-8cf0-11bd-b23e-10b96e40000d",
  "ip_address": "203.0.113.1",
  "user_agent": "Mozilla/5.0"
}
```

Use the plural list fields below. Each submitted list must contain at most three
values. When you supply both singular and plural forms, each merged field must
contain at most three unique values. Exceeding either limit returns HTTP 400;
the API does not truncate values.

| Field                    | Type           | Description                                                                                                                    |
| ------------------------ | -------------- | ------------------------------------------------------------------------------------------------------------------------------ |
| `phone_numbers_sha256`   | `list[string]` | SHA-256 hashes of 8–15 digits after removing a leading `+`, leading zeroes, whitespace, parentheses, periods, and hyphens.     |
| `emails_sha256`          | `list[string]` | SHA-256 hashes of normalized email addresses.                                                                                  |
| `external_ids_sha256`    | `list[string]` | SHA-256 hashes of stable, pseudonymous customer identifiers from your system.                                                  |
| `first_names_sha256`     | `list[string]` | SHA-256 hashes of lowercase first names after removing whitespace and ASCII punctuation; non-ASCII characters are preserved.   |
| `last_names_sha256`      | `list[string]` | SHA-256 hashes of lowercase last names after removing whitespace and ASCII punctuation; non-ASCII characters are preserved.    |
| `regions`                | `list[string]` | Raw region values. The API trims whitespace, converts values to lowercase, and limits each normalized value to 128 characters. |
| `postal_codes`           | `list[string]` | Raw postal or ZIP codes. Use letters, numbers, spaces, or hyphens; each normalized value can contain up to 32 characters.      |
| `cities`                 | `list[string]` | Raw city names. The API trims whitespace, converts values to lowercase, and limits each normalized value to 128 characters.    |
| `countries`              | `list[string]` | Raw two-letter country codes, such as `US`.                                                                                    |
| `android_advertising_id` | `string`       | Raw Android Google Advertising ID (GAID) in UUID format. Available only through the Conversions API.                           |
| `obref`                  | `string`       | Opaque browser reference from the Pixel's `__obref` cookie. Pass it without hashing.                                           |
| `ip_address`             | `string`       | Valid IPv4 or IPv6 address of the user's device that generated the event. Send without hashing.                                |
| `user_agent`             | `string`       | Non-empty user agent string from the client that generated the event.                                                          |

`android_advertising_id` supports Android GAID only; IDFA is not supported. You
can send a GAID with any `action_source`. The API ignores all-zero advertising
IDs without rejecting the event.

For hybrid Pixel and Conversions API integrations, read the `__obref`
first-party cookie in the browser, send it to your server, and include it
unchanged as `events[].user.obref` when available. Send a non-blank string.
Before collecting or forwarding the cookie, follow your site's measurement
consent requirements. If the user revokes consent, stop sending it. Unlike
`oppref`, which is an event-level field, `obref` belongs inside `user`.

## Example event

```bash
curl -X POST "https://bzr.openai.com/v1/events?pid=<PIXEL-ID>" \
  -H "Authorization: Bearer <API-KEY>" \
  -H "Content-Type: application/json" \
  --data '{
    "validate_only": false,
    "events": [
      {
        "id": "order_12345",
        "type": "order_created",
        "timestamp_ms": 1773892800000,
        "oppref": "oppref_abc",
        "source_url": "https://shop.example.com/checkout/confirmation",
        "action_source": "web",
        "user": {
          "obref": "123e4567-e89b-42d3-a456-426614174000",
          "emails_sha256": [
            "b4c9a289323b21a01c3e940f150eb9b8c542587f1abfd8f0e1cc1ffc5e475514"
          ],
          "external_ids_sha256": [
            "18f69bcd2f9cc9c38195e722b2a5590429840ea5090971d2256e026926e55fa1"
          ],
          "countries": ["US"],
          "cities": ["San Francisco"],
          "postal_codes": ["94107"],
          "ip_address": "203.0.113.1",
          "user_agent": "Mozilla/5.0"
        },
        "data": {
          "type": "contents",
          "amount": 2599,
          "currency": "USD",
          "contents": [
            {
              "id": "sku_123",
              "name": "Starter bundle",
              "content_type": "product",
              "quantity": 1
            }
          ]
        }
      }
    ]
  }'
```

## App lifecycle events

App lifecycle events use the `customer_action` data shape and require
`action_source` to be `mobile_app`.

### App installed

```json
{
  "id": "app_installed_123",
  "type": "app_installed",
  "timestamp_ms": <TIMESTAMP_MS>,
  "action_source": "mobile_app",
  "data": {
    "type": "customer_action"
  }
}
```

### App opened

```json
{
  "id": "app_opened_123",
  "type": "app_opened",
  "timestamp_ms": <TIMESTAMP_MS>,
  "action_source": "mobile_app",
  "data": {
    "type": "customer_action"
  }
}
```

## Deduplicate browser and server events

If you send the same conversion from the pixel and the Conversions API, reuse
the same value as the API `id` and pixel `event_id`. Send both events with the
same Pixel ID. For custom events, use the same `custom_event_name` on both sides
as well. For deduplication, OpenAI uses your Pixel ID, `event_name`, and `id`. OpenAI uses
the first event it receives for a matching key and ignores later duplicates.