# Measurement Pixel

> For the complete documentation index, see [llms.txt](/llms.txt). Markdown versions of documentation pages are available by appending `.md` to the page URL.

The ChatGPT Ads Measurement Pixel is a browser SDK for measuring website events
that can be attributed to ads in ChatGPT. Add the script to your site, initialize
it with your Pixel ID, and call `oaiq("measure", ...)` when a conversion happens.

If a page needs to measure conversions for more than one Pixel ID, see
[Configure more than one Pixel ID](https://developers.openai.com/ads/multiple-pixels).

## Attribution reporting

The same events support click-through attribution and, when available for your
account, view-through attribution. Click-through attribution uses the applicable
configured click window. View-through conversions use a fixed one-day window
after an eligible ad impression. Whether view-through reporting is available
does not depend on your configured click window. If a conversion is eligible
for both, the click takes precedence.

View-through reporting requires no changes to your Pixel integration or event
payload. Ads Manager reports view-through conversions as a separate,
campaign-level metric. They are not included in `Conversions`, which remains
the click-through conversion total. CPA, post-click CVR, bidding, billing, and
conversion optimization also remain click-through-based.

## Install the Measurement Pixel

Add the following snippet to the `<head>` section every page where you want to capture
conversions. Put the script near the top of your `<head>` to ensure early conversions aren't lost while other content loads.

```html
<script>
  (function (w, d, s, u) {
    if (w.oaiq) return;
    var q = function () {
      q.q.push(arguments);
    };
    q.q = [];
    w.oaiq = q;
    var js = d.createElement(s);
    js.async = true;
    js.src = u;
    var f = d.getElementsByTagName(s)[0];
    f.parentNode.insertBefore(js, f);
  })(window, document, "script", "https://bzrcdn.openai.com/sdk/oaiq.min.js");

  oaiq("init", {
    pixelId: "<YOUR-PIXEL-ID>",
  });
</script>
```


`pixelId` is required. Create a new Pixel ID in the conversions tab of Ads Manager. `debug` is optional and logs SDK activity to the browser
console while you test your integration.

## Control measurement consent

If consent is required to track conversion events, use the Pixel's consent
feature. Set consent before initializing the Pixel:

```typescript
oaiq("consent", false);
oaiq("init", {
  pixelId: "<YOUR-PIXEL-ID>",
});

// Call this after the user grants measurement consent.
oaiq("consent", true);
```


The Pixel initializes consent to `true` by default unless you set it to `false`
or the Pixel finds a stored denial. When consent is `false`, the Pixel doesn't
send measurement-event pings. Setting it to `true` allows future measurement
events; blocked events aren't replayed.

## Configure a content security policy

If your site enforces a Content Security Policy (CSP), merge these sources into
your existing policy:

| Directive     | Source                      | Purpose                                      |
| ------------- | --------------------------- | -------------------------------------------- |
| `script-src`  | `https://bzrcdn.openai.com` | Load the Measurement Pixel SDK.              |
| `connect-src` | `https://bzr.openai.com`    | Send events with `fetch` or `sendBeacon`.    |
| `connect-src` | `https://bzrcdn.openai.com` | Fetch per-pixel configuration.               |
| `img-src`     | `https://bzr.openai.com`    | Send events with the image request fallback. |

For example, a policy that otherwise allows only same-origin resources and uses
a nonce would include:

```http
Content-Security-Policy: default-src 'self'; script-src 'self' 'nonce-<NONCE>' https://bzrcdn.openai.com; connect-src 'self' https://bzr.openai.com https://bzrcdn.openai.com; img-src 'self' https://bzr.openai.com;
```

Replace `<NONCE>` with a fresh nonce for each response and add the same value to
the installation snippet's opening tag: `<script nonce="<NONCE>">`. You can use
your site's existing hash-based CSP mechanism instead. Don't add `'unsafe-inline'`
solely for the Measurement Pixel. If your policy defines `script-src-elem`, add
the CDN source and your nonce or hash source to that directive as well.

## Send user data

Add an optional `user` object to `oaiq("init", ...)` to improve conversion
matching. User data is request-scoped, so don't add it to individual
`oaiq("measure", ...)` calls.

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
addresses, phone numbers, external IDs, first names, or last names.

```typescript
oaiq("init", {
  user: {
    email_sha256:
      "b4c9a289323b21a01c3e940f150eb9b8c542587f1abfd8f0e1cc1ffc5e475514",
    phone_number_sha256:
      "758fbf68945f21c416814c539ab578876c8d98fb69e6da692def92cd52417fe0",
    external_id_sha256:
      "73d83a078369bb4f0971b317aa7797a91cf5c0df1b62161c2e47d75c33ab5b6e",
    first_name_sha256:
      "fdee430d40bd57deeac186cd9790033d0f06f909a8806e7ce6e717ab7c7d5029",
    last_name_sha256:
      "fb1e7ec987523d2cb9e022cec1d6ae7c99dc46edfae4fe51254025fe4bea571f",
    country: "US",
    city: "San Francisco",
    region: "California",
    postal_code: "94107",
  },
});
```


If these values are available when the installation snippet runs, you can
instead include the same `user` object in the initial `oaiq("init", ...)` call
with your Pixel ID.

| Field                 | Description                                                                                                                   |
| --------------------- | ----------------------------------------------------------------------------------------------------------------------------- |
| `email_sha256`        | SHA-256 hash of the email address after trimming whitespace and converting it to lowercase.                                   |
| `phone_number_sha256` | SHA-256 hash of 8–15 digits after removing a leading `+`, leading zeroes, whitespace, parentheses, periods, and hyphens.      |
| `external_id_sha256`  | SHA-256 hash of a stable, pseudonymous customer identifier from your system.                                                  |
| `first_name_sha256`   | SHA-256 hash of the lowercase first name after removing whitespace and ASCII punctuation; non-ASCII characters are preserved. |
| `last_name_sha256`    | SHA-256 hash of the lowercase last name after removing whitespace and ASCII punctuation; non-ASCII characters are preserved.  |
| `country`             | Two-letter ISO 3166-1 country code, such as `US`.                                                                             |
| `city`                | City name, with a maximum of 128 characters. OpenAI trims whitespace and converts it to lowercase.                            |
| `region`              | State, province, or region, with a maximum of 128 characters.                                                                 |
| `postal_code`         | Postal or ZIP code. Use letters, numbers, spaces, or hyphens, with a maximum of 32 characters.                                |

If user data becomes available after the first `init` call, such as after login,
call `init` again with the complete `user` object. When a page initializes only
one pixel, you can omit `pixelId` after the first successful initialization. If
a page initializes more than one pixel, always include the intended `pixelId`
when updating user data.

## Automatic advanced matching

Automatic advanced matching improves website conversion measurement by helping
match more conversions to your ads when a click identifier is unavailable.

When enabled, the OpenAI Pixel automatically detects supported customer
information from your website. The Pixel normalizes and securely hashes this
information in the browser using SHA-256 before including it with conversion
events. Raw customer information is not sent to OpenAI through automatic
advanced matching.

You do not need to manually pass customer information or make any changes to
your Pixel implementation.

## Send events

The Measurement Pixel does not support `app_installed` or `app_opened`.

Send these events server-side through the
[Conversions API](https://developers.openai.com/ads/conversions-api).
Use a standard event whenever one matches the action you want to measure.

Use a standard event whenever one matches the action you want to measure. For
example, send `order_created` when a purchase is completed:

```typescript
oaiq("measure", "order_created", {
  type: "contents",
  amount: 2599,
  currency: "USD",
});
```


A `measure` call accepts up to four arguments, in this order:

| Argument   | Required | What to send                                                                                      |
| ---------- | -------- | ------------------------------------------------------------------------------------------------- |
| Command    | Yes      | The command `"measure"`.                                                                          |
| Event name | Yes      | A [supported event name](https://developers.openai.com/ads/supported-events), such as `order_created`, or `"custom"`.          |
| Event data | Yes      | An object whose `type` matches the event's [data shape](https://developers.openai.com/ads/supported-events#event-data-shapes). |
| Options    | Depends  | Optional for standard events. Required for custom events to pass `custom_event_name`.             |

The event name describes what happened. The event data object's `type` selects
the shape of the accompanying data. For example, `order_created` uses the
`contents` data type.

The options object supports these fields:

| Field               | When to use it                                                                                                                                                                                                                                                                      |
| ------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `event_id`          | Set a unique ID to identify the same event sent from the browser and server.                                                                                                                                                                                                        |
| `custom_event_name` | Name a custom event. This field is required for custom events and isn't supported for standard ones.                                                                                                                                                                                |
| `opt_out`           | Set to `true` to opt out the event from future user-level personalization. Defaults to `false`. For clarity, OpenAI does not currently use data collected via the measurement pixel for user-level personalization. If we do so in the future, we will respect this opt-out toggle. |

### Send a custom event

Use a custom event only when none of the standard event names describe the
action. This is the smallest valid custom event:

```typescript
oaiq(
  "measure",
  "custom",
  { type: "custom" },
  { custom_event_name: "quote_requested" }
);
```


The three custom-event values serve different purposes:

- `"custom"` in the second position identifies this as a custom event.
- `{ type: "custom" }` selects the custom event data shape.
- `custom_event_name` gives the event its descriptive name.

You can add `plan_id`, `amount`, `currency`, or `contents` to the event data
object. Add `event_id` to the options object when you need browser and server
deduplication.

Custom event names must:

- Be 1 to 64 characters long.
- Contain only letters, numbers, underscores, or dashes.
- Start and end with a letter or number.
- Not match a standard event name.

Use lowercase names for consistency.

## Standard event examples

Use these examples as templates for common measurement patterns.

### Page and content views

```typescript
oaiq("measure", "page_viewed", {
  type: "contents",
  contents: [
    {
      id: "pricing",
      name: "Pricing page",
      content_type: "page",
    },
  ],
});

oaiq("measure", "contents_viewed", {
  type: "contents",
  contents: [
    {
      id: "sku_123",
      name: "Starter bundle",
      content_type: "product",
    },
  ],
});
```


### Commerce flow

Use the `contents` data shape for `items_added`, `checkout_started`, and
`order_created`.

```typescript
oaiq("measure", "items_added", {
  type: "contents",
  amount: 2599,
  currency: "USD",
  contents: [
    {
      id: "sku_123",
      name: "Starter bundle",
      content_type: "product",
      quantity: 1,
      amount: 2599,
      currency: "USD",
    },
  ],
});

oaiq("measure", "checkout_started", {
  type: "contents",
  amount: 2599,
  currency: "USD",
  contents: [
    {
      id: "sku_123",
      name: "Starter bundle",
      content_type: "product",
      quantity: 1,
    },
  ],
});

oaiq("measure", "order_created", {
  type: "contents",
  amount: 2599,
  currency: "USD",
  contents: [
    {
      id: "sku_123",
      name: "Starter bundle",
      content_type: "product",
      quantity: 1,
    },
  ],
});
```


### Lead generation and registration

Use the `customer_action` data shape for `lead_created`,
`registration_completed`, and `appointment_scheduled`.

```typescript
oaiq("measure", "lead_created", {
  type: "customer_action",
});

oaiq("measure", "registration_completed", {
  type: "customer_action",
});

oaiq("measure", "appointment_scheduled", {
  type: "customer_action",
  amount: 5000,
  currency: "USD",
});
```


### Subscription and trial events

Use the `plan_enrollment` data shape for `subscription_created` and
`trial_started`.

```typescript
oaiq("measure", "subscription_created", {
  type: "plan_enrollment",
  plan_id: "pro_monthly",
  amount: 2000,
  currency: "USD",
});

oaiq("measure", "trial_started", {
  type: "plan_enrollment",
  plan_id: "pro_trial",
});
```


## Deduplicate browser and server events

If you send the same conversion from both the Measurement Pixel and a
server-side integration, reuse the same `event_id` in both places.

```typescript
oaiq(
  "measure",
  "order_created",
  {
    type: "contents",
    amount: 2599,
    currency: "USD",
  },
  {
    event_id: "order_12345",
  }
);
```


When you need deduplication across browser and server events, generate the
`event_id` yourself and reuse it on the same pixel and server-sent event. For
custom events, keep the same `custom_event_name` on both sides as well.
Duplicate-event matching uses your Pixel ID, the event name, and `event_id`. For
custom events, `custom_event_name` replaces the standard event name in that
match. OpenAI uses the first event it receives for a matching key and ignores
later duplicates.

## Test your Pixel in Ads Manager

Use a Pixel test session in Ads Manager to inspect events received while you test
your website. The filtered Event Stream shows events from your selected Pixel and
test session, helping you check event names and details without sorting through
unrelated traffic.

1. In Ads Manager, go to **Conversions** > **Data Source**.
2. Open the three-dot menu for your Web Pixel and select **Test**.
3. Enter a page URL where that Pixel is installed, then select **Start testing**.
4. Take actions on the website that opens, then return to **Event Stream** in Ads
   Manager. Events from the session have a **Test** label. Select an event to
   inspect its details.

Test labeling lasts up to 30 minutes and applies to the selected Pixel in the
opened tab on the same website origin. Other domains and subdomains do not
automatically join the session.

At higher test-event volumes, Event Stream may show only a sample of events.
Events may also be delayed. Testing uses your existing consent settings, and test
events still count in normal analytics.

Select **Exit test view** to return to the ordinary Event Stream. This does not end
test labeling on your website.

## What the SDK handles automatically

The Pixel handles several transport details for you:

- It captures `oppref` from the landing page URL, which is a privacy-preserving identifier
- It stores `oppref` in a first-party `__oppref` cookie so later page views can
  reuse it.
- It adds the current page origin as `source_url`.
- It timestamps each event and batches closely grouped `measure` calls.
- When automatic advanced matching is enabled, it detects supported customer
  information from your website, securely hashes it using SHA-256, and includes
  the resulting SHA-256 hash with conversion events.

No manual configuration of these details is necessary when using the pixel.

## Cookie expiry

When measurement consent is granted, the Pixel uses these first-party cookies
on your website:

| Cookie     | Expiry                                     |
| ---------- | ------------------------------------------ |
| `__oppref` | 30 days after the Pixel writes the cookie. |
| `__obref`  | 365 days after creation.                   |

- `__oppref` stores the `oppref` attribution identifier from the landing page URL.
  Each time the Pixel captures a non-empty `oppref` URL parameter, including the
  same value again, it resets the cookie's expiry to 30 days. Reading the stored
  cookie on a visit without that parameter does not extend its expiry.
- `__obref` stores a randomly generated browser reference for your website. The
  Pixel reuses a valid stored reference without extending its expiry. If the
  cookie is missing or invalid, the Pixel creates a new reference with a new
  365-day expiry.

These are the lifetimes requested by the Pixel. Browser restrictions or clearing
cookies can shorten them. Calling `oaiq("consent", false)` removes both cookies;
see [Control measurement consent](https://developers.openai.com/ads/measurement-pixel#control-measurement-consent).

Cookie expiry is separate from conversion attribution windows and conversion-data
retention. The durations above describe browser cookie storage only.

## Troubleshooting

- Use [Test Pixel in Ads Manager](#test-your-pixel-in-ads-manager) to inspect sampled
  events from your test session.
- Keep `debug: true` while testing so you can inspect Pixel activity in the
  browser console.
- Use integer values for `amount` and `quantity`.
- Use only the documented fields inside `contents[]`.
- Always use the pixel on the browser. Do not call the server conversions API directly from page code.