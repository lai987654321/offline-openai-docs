# Supported Events

> For the complete documentation index, see [llms.txt](/llms.txt). Markdown versions of documentation pages are available by appending `.md` to the page URL.

## Supported event names

| Event name               | Data type         | Use for                                                            |
| ------------------------ | ----------------- | ------------------------------------------------------------------ |
| `app_installed`          | `customer_action` | A user installs an app.                                            |
| `app_opened`             | `customer_action` | A user opens an app.                                               |
| `appointment_scheduled`  | `customer_action` | A user books a meeting, demo, or consultation.                     |
| `checkout_started`       | `contents`        | A user starts checkout.                                            |
| `contents_viewed`        | `contents`        | A user views a product, listing, article, or other content unit.   |
| `custom`                 | `custom`          | A user-defined event that is not covered by the standard taxonomy. |
| `items_added`            | `contents`        | A user adds one or more items to a cart, bundle, or selection.     |
| `lead_created`           | `customer_action` | A user submits a lead form or requests contact.                    |
| `order_created`          | `contents`        | A purchase is completed.                                           |
| `page_viewed`            | `contents`        | A user lands on or views an important page.                        |
| `registration_completed` | `customer_action` | A user finishes an account or event registration flow.             |
| `subscription_created`   | `plan_enrollment` | A paid subscription starts.                                        |
| `trial_started`          | `plan_enrollment` | A free trial starts.                                               |

`app_installed` and `app_opened` are available through the Conversions API
only. Send them with `action_source` set to `mobile_app`. They are not
supported by the JavaScript Pixel currently. For Android app events, include
`events[].user.android_advertising_id` when available. IDFA is not supported.

Use `page_viewed` for page loads. Use `contents_viewed` when a user views a
specific product or content item, including interactions that happen after the
page has loaded.

## Event data shapes

All event data objects must include a `type` field that matches the event you
send. If you include an `amount`, also include a `currency`. Send monetary
values as integers in the standard ISO 4217 minor unit for the currency code
you provide, for example `12999` for $129.99 with `currency: "USD"`.

### `contents`

| Field      | Required | Type               | Notes                                                             |
| ---------- | -------- | ------------------ | ----------------------------------------------------------------- |
| `type`     | Yes      | string             | Must be `contents`.                                               |
| `amount`   | No       | integer            | Event-level monetary value in the currency's standard minor unit. |
| `currency` | Depends  | string             | Required when `amount` is present.                                |
| `contents` | No       | array of `Content` | Items associated with the event.                                  |

### `customer_action`

| Field      | Required | Type    | Notes                                                             |
| ---------- | -------- | ------- | ----------------------------------------------------------------- |
| `type`     | Yes      | string  | Must be `customer_action`.                                        |
| `amount`   | No       | integer | Event-level monetary value in the currency's standard minor unit. |
| `currency` | Depends  | string  | Required when `amount` is present.                                |

### `plan_enrollment`

| Field      | Required | Type               | Notes                                                             |
| ---------- | -------- | ------------------ | ----------------------------------------------------------------- |
| `type`     | Yes      | string             | Must be `plan_enrollment`.                                        |
| `plan_id`  | No       | string             | Your internal plan identifier.                                    |
| `amount`   | No       | integer            | Event-level monetary value in the currency's standard minor unit. |
| `currency` | Depends  | string             | Required when `amount` is present.                                |
| `contents` | No       | array of `Content` | Optional plan-related items.                                      |

### `custom`

| Field      | Required | Type               | Notes                                                             |
| ---------- | -------- | ------------------ | ----------------------------------------------------------------- |
| `type`     | Yes      | string             | Must be `custom`.                                                 |
| `plan_id`  | No       | string             | Optional plan identifier.                                         |
| `amount`   | No       | integer            | Event-level monetary value in the currency's standard minor unit. |
| `currency` | Depends  | string             | Required when `amount` is present.                                |
| `contents` | No       | array of `Content` | Optional items associated with the custom event.                  |

### `Content`

Use only these fields in each `contents[]` item. Fields marked as Conversions API
only are not supported by the JavaScript Pixel.

| Field          | Required | Type    | Notes                                                                                                                             |
| -------------- | -------- | ------- | --------------------------------------------------------------------------------------------------------------------------------- |
| `id`           | No       | string  | Your internal item identifier.                                                                                                    |
| `group_id`     | No       | string  | Conversions API only. Your product group or parent item identifier.                                                               |
| `name`         | No       | string  | Human-readable item name.                                                                                                         |
| `content_type` | No       | string  | Optional non-empty category such as `product`, `plan`, or `page`.                                                                 |
| `quantity`     | No       | integer | Quantity of the item. Use integers, not strings.                                                                                  |
| `amount`       | No       | integer | Per-unit price in the currency's standard minor unit. Supply `quantity` separately.                                               |
| `currency`     | No       | string  | Include when you send an item-level `amount`, or rely on the event-level `currency` when one currency applies to the whole event. |
| `variant_dict` | No       | object  | Conversions API only. An object with string keys and values, such as `{"size": "medium", "color": "blue"}`.                       |

Use lowercase letters, numbers, underscores, or dashes in
`custom_event_name`. Keep the name between 1 and 64 characters, and do not
reuse one of the built-in event names.

### Item and event amounts

The Measurement Pixel and Conversions API use the same amount semantics.
`contents[].amount` is the price of one unit. The event-level `amount`
represents the value of the whole event.

For example, two units at TRY 799.00 each use item `amount: 79900` and
`quantity: 2`. For an `order_created` event containing only those units with no
other adjustments, send this event data:

```json
{
  "type": "contents",
  "amount": 159800,
  "currency": "TRY",
  "contents": [
    {
      "id": "SKU24680",
      "quantity": 2,
      "amount": 79900,
      "currency": "TRY"
    }
  ]
}
```

Here, `79900` means 79,900 minor units, or TRY 799.00, per unit. The event value
is `2 × 79900 = 159800` minor units, or TRY 1,598.00.

If TRY 799.00 is the total for both units, send item `amount: 39950` with
`quantity: 2` instead.