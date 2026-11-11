# Products

> For the complete documentation index, see [llms.txt](/llms.txt). Markdown versions of documentation pages are available by appending `.md` to the page URL.

Use this reference for supported file uploads. Start with discovery data, then
add the fields required for your Ads or checkout integration.



<h2 id="feed-reference">Feed Reference</h2>

      Start with the required product fields and a minimal example. Optional
      fields describe variants, product attributes, shipping, and returns.
      Ads product feeds follow the [Ads product feeds
      guide](https://developers.openai.com/ads/product-feeds#use-the-correct-feed-schema). Checkout requires
      a separately enabled integration.



### Start with discovery

Submit one row per purchasable item or variant. Include the nine required
fields in [Basic product data](#basic-product-data), then add the optional data
that describes your products. Ads and checkout have separate requirements.

- [Basic product data](#basic-product-data) and [minimal example](#minimal-example)
- [Identity and variants](#variants)
- [Product attributes](#item-information), [images](#media), and [prices](#price--promotions)
- [Shipping](#fulfillment), [returns](#returns), and [reviews](#reviews-and-qa)
- [Markets](#geo-tagging), [Ads](#ads), and [checkout](#checkout)

#### Value conventions

These tables describe what to submit. Required fields must contain a value;
conditional requirements apply only to the stated use case. Format guidance is
not a guarantee that every invalid value will be rejected at upload.

For optional fields, omit an unknown value. Unless a row says otherwise, an
omitted field, JSON `null`, or an empty delimited cell supplies no value. Do not
use placeholder strings such as `null`, `unknown`, or `n/a`; `unknown` is valid
only where explicitly listed. An empty value does not mean zero or `false`.
For boolean fields, use JSON `true` or `false`, or the lowercase strings `true` and
`false` in delimited files. These values are not valid for other field types.

Use UTF-8 text and absolute HTTP or HTTPS URLs; prefer HTTPS. Product and image
URLs must be publicly accessible. Keep identifiers as strings to preserve
leading zeros. In CSV, quote a cell containing commas, quotes, or newlines, and
double each embedded quote. JSON objects in CSV or TSV cells must be serialized
as JSON. Use the [file upload guide](https://developers.openai.com/commerce/specs/file-upload/overview) for delivery.

### Basic product data

These fields are required for a useful discovery feed. Use a real brand and
seller name, not placeholders. Keep titles concise and descriptions in plain
text; aim for at most 150 and 5,000 characters, respectively.

| Attribute      | Data type      | Requirement | Description                                                                                                                                                                           | Example                                                         |
| :------------- | :------------- | :---------- | :------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | :-------------------------------------------------------------- |
| `item_id`      | String         | Required    | Stable ID, unique per item or variant within your feed. Never reuse it for a different item. See [identity rules](#variants).                                                         | `TRAIL-BLK-10`                                                  |
| `title`        | String         | Required    | Product name, including the selected variant when relevant.                                                                                                                           | `Trail running shoes — black, size 10`                          |
| `description`  | String         | Required    | Factual product description for this item.                                                                                                                                            | `Waterproof trail shoes with a rubber outsole and mesh lining.` |
| `url`          | String (URL)   | Required    | Product detail page for the item, with the variant selected when possible. Keep it stable.                                                                                            | `https://example.com/products/trail?color=black&size=10`        |
| `brand`        | String         | Required    | Product brand as shown on the product page.                                                                                                                                           | `Northline`                                                     |
| `seller_name`  | String         | Required    | Name of the seller supplying this offer. For marketplace offers, see [merchant information](#merchant-info).                                                                          | `Northline Outdoor`                                             |
| `image_url`    | String (URL)   | Required    | Main product image, showing this variant. Use a direct image URL, such as a JPEG or PNG.                                                                                              | `https://example.com/images/trail-black.jpg`                    |
| `availability` | String         | Required    | `in_stock`, `out_of_stock`, `pre_order`, `backorder`, or `unknown`. Omitted, empty, or unrecognized values reject the row. Use `unknown` explicitly when stock status is unavailable. | `in_stock`                                                      |
| `price`        | String (money) | Required    | Regular item price in major currency units. See [prices](#price--promotions).                                                                                                         | `79.99 USD`                                                     |

#### Minimal example

This JSONL record describes one item. Search defaults to enabled and checkout
to disabled. Ads defaults to disabled unless your feed has an Ads default configured.
Replace the example URLs with your public product and image URLs.
```jsonl
{"item_id":"MUG-350-BLUE","title":"Blue ceramic mug, 350 mL","description":"Dishwasher-safe glazed ceramic mug with a handle.","url":"https://example.com/products/mug-blue","brand":"Northline","seller_name":"Northline Home","image_url":"https://example.com/images/mug-blue.jpg","price":"18.00 USD","availability":"in_stock"}
```

Use an explicit availability value. `unknown` does not assert that the item is
in stock.

### OpenAI flags

| Attribute            | Data type | Requirement | Description                                                                                                                                        | Example |
| :------------------- | :-------- | :---------- | :------------------------------------------------------------------------------------------------------------------------------------------------- | :------ |
| `is_eligible_search` | boolean   | Optional    | `true` enables search eligibility; `false` disables it and checkout eligibility. Omitted or empty: `true`. Eligibility does not guarantee display. | `true`  |

### Variants

Use `item_id` for the specific item, `group_id` for its parent listing, and
`offer_id` for a seller's offer. Keep all three stable when price, stock, title,
or images change. **Never include price in an offer ID.**

For variants, send a separate row for each selection, with a distinct `item_id`,
the same `group_id`, `listing_has_variations=true`, and a `variant_dict` of the
selected options. The group ID must differ from each item ID. Use the same
option names across a group, and unique option combinations. Group only
variants of the same product as presented on your site. Each row carries its
own price, availability, URL, and images.

| Attribute                | Data type               | Requirement                         | Description                                                                                                                                                                                                 | Example                         |
| :----------------------- | :---------------------- | :---------------------------------- | :---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | :------------------------------ |
| `group_id`               | String                  | Conditionally required for variants | Stable parent-listing ID shared by all variants. Omitted or empty: uses `item_id`, which does not establish a variant group.                                                                                | `TRAIL`                         |
| `listing_has_variations` | boolean                 | Conditionally required for variants | Set `true` on every variant row. Omitted, empty, or `false`: no variant options are used.                                                                                                                   | `true`                          |
| `variant_dict`           | Object of string values | Conditionally required for variants | Map option names to the selected values. Requires `listing_has_variations=true` and `group_id` different from `item_id`; otherwise ignored. Use nonempty keys and values. An empty object means no options. | `{"color":"Black","size":"10"}` |
| `offer_id`               | String                  | Optional                            | Stable offer ID, unique within the feed. Use it to distinguish offers that share a product URL. Omitted or empty: no explicit offer ID; do not rely on this to distinguish multiple sellers at one URL.     | `northline-TRAIL-BLK-10`        |
| `gtin`                   | String                  | Optional                            | One assigned GTIN: exactly 8, 12, 13, or 14 digits, including a valid check digit. Preserve leading zeros; no spaces or dashes. Omit if unassigned.                                                         | `09506000134352`                |
| `mpn`                    | String                  | Optional                            | Manufacturer-assigned part number, preserving its punctuation and casing. Submit with `brand`; do not invent a value to replace a missing GTIN.                                                             | `NL-TRAIL-10-BLK`               |

A GTIN identifies the specific trade item, not the variant group. UPC-A is a
12-digit GTIN; an ISBN-13 can be submitted as a 13-digit GTIN. Do not submit an
ISBN-10. To check the final digit, start at the rightmost digit before it,
multiply alternate digits by 3 and 1, sum them, and choose the check digit that
makes the total divisible by 10. Validate identifiers before uploading.

#### Variant-group example

Both records belong to `TRAIL`. Each record selects one size and has a stable
offer ID. The JSON is expanded for readability; in your JSONL file, write each
complete record on one line.

Size 10 (`in_stock`):

```json
{
  "item_id": "TRAIL-BLK-10",
  "group_id": "TRAIL",
  "listing_has_variations": true,
  "variant_dict": {
    "color": "Black",
    "size": "10"
  },
  "offer_id": "northline-TRAIL-BLK-10",
  "title": "Trail running shoes — black, size 10",
  "description": "Waterproof trail shoes with a rubber outsole.",
  "url": "https://example.com/products/trail?color=black&size=10",
  "brand": "Northline",
  "seller_name": "Northline Outdoor",
  "image_url": "https://example.com/images/trail-black.jpg",
  "price": "79.99 USD",
  "availability": "in_stock"
}
```

Size 11 (`out_of_stock`):

```json
{
  "item_id": "TRAIL-BLK-11",
  "group_id": "TRAIL",
  "listing_has_variations": true,
  "variant_dict": {
    "color": "Black",
    "size": "11"
  },
  "offer_id": "northline-TRAIL-BLK-11",
  "title": "Trail running shoes — black, size 11",
  "description": "Waterproof trail shoes with a rubber outsole.",
  "url": "https://example.com/products/trail?color=black&size=11",
  "brand": "Northline",
  "seller_name": "Northline Outdoor",
  "image_url": "https://example.com/images/trail-black.jpg",
  "price": "79.99 USD",
  "availability": "out_of_stock"
}
```

### Item information

Keep top-level attributes consistent with the same options in `variant_dict`.
Neither representation reconciles conflicting values for you.

| Attribute          | Data type        | Requirement                                     | Description                                                                                                                                                                                                                  | Example                                                  |
| :----------------- | :--------------- | :---------------------------------------------- | :--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | :------------------------------------------------------- |
| `condition`        | String           | Optional                                        | Use `new`, `refurbished`, or `used`. Omitted or empty may be treated as `new`; always specify used or refurbished condition.                                                                                                 | `new`                                                    |
| `product_category` | String           | Optional                                        | Your category path, from broad to specific, separated by `>`.                                                                                                                                                                | `Apparel & Accessories > Shoes`                          |
| `material`         | String           | Optional                                        | Principal materials in the item.                                                                                                                                                                                             | `Leather and rubber`                                     |
| `color`            | String           | Optional                                        | Selected color, consistent with the product image.                                                                                                                                                                           | `Black`                                                  |
| `size`             | String           | Optional                                        | Selected size label; use `variant_dict` when size distinguishes variants. A sizing system requires the setup described in [additional supported data](#additional-supported-data).                                           | `10`                                                     |
| `gender`           | String           | Optional                                        | `male`, `female`, or `unisex`. Omitted, empty, or unrecognized: no gender supplied.                                                                                                                                          | `unisex`                                                 |
| `age_group`        | String           | Optional                                        | `newborn`, `infant`, `toddler`, `kids`, or `adult`. Omitted, empty, or unrecognized: no age group supplied. This is a product attribute, not a purchase-age restriction.                                                     | `adult`                                                  |
| `dimensions`       | Object           | Optional                                        | Positive decimal strings for at least two of `length`, `width`, and `height`, plus `unit`: `in`, `cm`, `ft`, `m`, or `mm`. No other keys. Overrides the separate dimension fields. Empty object is invalid; omit if unknown. | `{"length":"30","width":"20","height":"12","unit":"cm"}` |
| `length`           | String (decimal) | Optional                                        | Positive product length; requires `dimensions_unit`. Use with `width` or `height`. Ignored when structured `dimensions` is supplied.                                                                                         | `30`                                                     |
| `width`            | String (decimal) | Optional                                        | Positive product width; requires `dimensions_unit`. Use with `length` or `height`. Ignored when structured `dimensions` is supplied.                                                                                         | `20`                                                     |
| `height`           | String (decimal) | Optional                                        | Positive product height; requires `dimensions_unit`. Use with `length` or `width`. Ignored when structured `dimensions` is supplied.                                                                                         | `12`                                                     |
| `dimensions_unit`  | String           | Conditionally required with separate dimensions | `in`, `cm`, `ft`, `m`, or `mm`; one unit for all supplied axes. Omitted: no unit conversion or inference.                                                                                                                    | `cm`                                                     |
| `weight`           | String (decimal) | Optional                                        | Positive net product weight, without packaging. Requires `item_weight_unit`.                                                                                                                                                 | `0.75`                                                   |
| `item_weight_unit` | String           | Conditionally required with `weight`            | Use `g`, `kg`, `oz`, or `lb`. Omitted: no unit conversion or inference.                                                                                                                                                      | `kg`                                                     |

Use `dimensions` for new feeds. Supply the product's dimensions, not its
shipping package dimensions. Convert measurements before uploading; units are
not inferred from the market or sizing system. The separate dimension fields
remain supported for existing feeds.

### Media

| Attribute               | Data type                                       | Requirement | Description                                                                                                                                          | Example                                                                                     |
| :---------------------- | :---------------------------------------------- | :---------- | :--------------------------------------------------------------------------------------------------------------------------------------------------- | :------------------------------------------------------------------------------------------ |
| `additional_image_urls` | Array of URL strings, or comma-separated string | Optional    | Additional views of this item. Omitted, empty, or `[]`: no additional images. Invalid URLs are omitted. Percent-encode commas inside a URL as `%2C`. | `["https://example.com/images/trail-side.jpg","https://example.com/images/trail-sole.jpg"]` |

In a CSV cell, encode the same list as
`"https://example.com/images/trail-side.jpg,https://example.com/images/trail-sole.jpg"`.
Use an array in JSONL. Do not use spaces or semicolons as list separators.

### Price & promotions

Write money as `amount CURRENCY`, for example `79.99 USD`: a decimal amount in
major units, a space, and an uppercase three-letter ISO 4217 currency code.
`79.99 USD` means 79 dollars and 99 cents, not 7,999 dollars. Use a decimal point,
no thousands separators or exponent notation, and no more fractional digits
than the currency permits. For USD, use two decimal places. Do not round a
price into a different payable amount.

Use a positive regular price for discovery and the currency agreed for your
feed. Submit the current price; update the feed when a sale starts or ends.

| Attribute    | Data type      | Requirement | Description                                                                                                                                                                                       | Example     |
| :----------- | :------------- | :---------- | :------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | :---------- |
| `sale_price` | String (money) | Optional    | Current sale price: greater than zero, strictly less than `price`, and in the same currency. Omitted or empty: use `price`. A nonpositive, equal, higher, or different-currency sale is not used. | `59.99 USD` |

### Availability & inventory

Submit current stock status with each row. Use `pre_order` for an item offered
before release and `backorder` for an item temporarily awaiting stock. These
values do not schedule a future stock change. Update `availability` when the
item becomes available or sells out.

### Merchant info

| Attribute    | Data type    | Requirement | Description                                                                                                                                       | Example                                |
| :----------- | :----------- | :---------- | :------------------------------------------------------------------------------------------------------------------------------------------------ | :------------------------------------- |
| `seller_url` | String (URL) | Optional    | Seller's storefront or profile page. For a marketplace offer, use the specific seller's page. Omitted, empty, or invalid: no seller URL supplied. | `https://example.com/stores/northline` |

For a third-party seller, `seller_name` identifies that seller and
`marketplace_seller` identifies the marketplace where checkout occurs. The
latter requires [feed setup](#additional-supported-data). The OpenAI format
requires `seller_name` on each row. Do not assume registration supplies other
row fields.

### Fulfillment

Shipping support depends on your feed setup. Confirm which of these two
representations your integration accepts before supplying it. A shipping
amount describes a charge; it does not quote a checkout total or guarantee a
delivery date.

| Attribute        | Data type      | Requirement                            | Description                                                                                                                                                                                                                        | Example                 |
| :--------------- | :------------- | :------------------------------------- | :--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | :---------------------- |
| `shipping_price` | String (money) | Optional                               | OpenAI-format shipping charge, in the same currency as `price`. Use a nonnegative amount; zero means no charge. Omitted or empty means unknown, not free shipping. Confirm display support for your integration.                   | `5.00 USD`              |
| `shipping`       | String         | Optional; requires feed-specific setup | For integrations configured for shipping tuples: exactly `country:region:service_class:price`. Use a supported country, an optional region, a service name, and a nonnegative money amount. Omitted or empty: no shipping details. | `US::Standard:5.00 USD` |

The tuple form has four positions; keep the empty region position when it does
not apply. It is not a list of regional overrides. Handling-day and transit-day
suffixes are not part of this supported tuple. Do not send both representations
for the same charge. Adding a `shipping` column to a standard OpenAI-format feed
does not enable tuple support.

### Returns

Describe return acceptance separately from the policy URL and return window. A
return window is a duration, not a deadline date.

| Attribute                 | Data type    | Requirement | Description                                                                                                                                                                                                                                    | Example                       |
| :------------------------ | :----------- | :---------- | :--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | :---------------------------- |
| `accepts_returns`         | boolean      | Optional    | `true`: accepts returns. `false`: rejects returns. Omitted or empty: unspecified. A policy URL does not set or override this field.                                                                                                            | `true`                        |
| `return_deadline_in_days` | Integer      | Optional    | Positive whole number of days allowed for returns under your policy. Supply only with `accepts_returns=true`; it does not enable returns by itself. Omitted or empty: no window supplied. Use the policy to explain when the window starts.    | `30`                          |
| `return_policy`           | String (URL) | Optional    | Public policy for this item's returns or final-sale terms. A valid URL does not set or override `accepts_returns`. If you omit the field, leave it empty, or supply a value other than an HTTP or HTTPS URL, the parser omits the policy link. | `https://example.com/returns` |

For a final-sale item, send `accepts_returns=false` and omit the return window.
You can include a valid `return_policy` URL that explains the restriction.

### Reviews and Q&A

Use review aggregates for the product or variant represented by the row. The
count and rating must describe the same review population. If your product page
shares reviews across variants, use that same group aggregate on each variant;
do not sum it again across rows. Omit a rating when there are no reviews.

| Attribute      | Data type        | Requirement | Description                                                                                                                                                                                       | Example |
| :------------- | :--------------- | :---------- | :------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | :------ |
| `review_count` | Integer          | Optional    | Nonnegative whole number of product reviews. Zero means no reviews; omitted or empty means unknown. Exclude seller and store reviews.                                                             | `254`   |
| `star_rating`  | String (decimal) | Optional    | Average product rating on a 0–5 scale, to two decimal places. Pair it with the matching positive `review_count`. Omitted or empty: no rating supplied. A zero rating may be omitted from display. | `4.50`  |

Raw review entries and question-and-answer lists are not part of this discovery
contract. Store aggregates have a separate scope and require the setup in the
next section.

#### Additional supported data

These optional fields require an integration configured to carry them. Confirm
support during onboarding before relying on them; adding these columns alone
to a standard OpenAI-format upload does not enable them.

| Attribute            | Data type        | Requirement                                                               | Description                                                                                                                                                                                                                          | Example               |
| :------------------- | :--------------- | :------------------------------------------------------------------------ | :----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | :-------------------- |
| `marketplace_seller` | String           | Conditionally required for third-party marketplace offers; requires setup | Marketplace where checkout occurs. Keep distinct from the supplying `seller_name`. Omitted or empty: no marketplace identity supplied.                                                                                               | `Example Marketplace` |
| `size_system`        | String           | Optional; requires setup                                                  | Sizing convention for `size`: use `US`, `UK`, `EU`, `DE`, `FR`, `JP`, `CN`, `IT`, `BR`, `MEX`, or `AU`. These are sizing labels, not destination-country codes. Omitted or empty: no system supplied; no size conversion is implied. | `US`                  |
| `store_review_count` | Integer          | Optional; requires setup                                                  | Nonnegative store or seller review count. Use the same store and review population as `store_star_rating`; do not combine with product reviews. Zero: no reviews; omitted or empty: unknown.                                         | `2000`                |
| `store_star_rating`  | String (decimal) | Optional; requires setup                                                  | Average for that store's reviews on a 0–5 scale, to two decimal places. Pair with a positive `store_review_count`. Omitted or empty: no rating supplied. Zero can be treated as unrated.                                             | `4.70`                |
| `accepts_exchanges`  | boolean          | Optional; requires setup                                                  | `true`: exchanges accepted for this item; `false`: not accepted. Omitted or empty: unspecified. Supply consistently with your returns policy; exchange messaging may depend on accepted returns and a return window.                 | `false`               |
| `is_digital`         | boolean          | Optional; requires setup                                                  | `true`: digital item with no physical shipment; `false`: physical item. Omitted or empty: unspecified, so do not rely on omission for digital checkout.                                                                              | `false`               |

### Geo tagging

The standard OpenAI-format upload currently targets the US. Row-level market
columns do not change that default. Use additional markets only after OpenAI
confirms the integration and its allowed countries and currencies. A currency,
product URL, or sizing system does not select a destination market.

| Attribute          | Data type        | Requirement                     | Description                                                                                                                                                                                                                                             | Example  |
| :----------------- | :--------------- | :------------------------------ | :------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | :------- |
| `target_countries` | Array of strings | Optional; requires market setup | Destination countries. Use uppercase ISO 3166-1 alpha-2 codes configured for your feed; the shared format currently represents `US`, `CA`, and `MX`. Standard uploads use `["US"]` regardless of this column. Omitted or empty does not mean worldwide. | `["US"]` |
| `store_country`    | String           | Optional; requires market setup | Country of the seller's store. Standard uploads use `US` regardless of this column. It is not a regional price or stock override. Omitted or empty does not select another market.                                                                      | `US`     |

Confirm multi-country support for your integration; do not rely on list order
to choose a market.




### Ads

Ads feeds use the product data in this reference plus the [Ads product feeds
guide](https://developers.openai.com/ads/product-feeds#use-the-correct-feed-schema). These fields are not
required for discovery.

| Attribute         | Data type               | Requirement                               | Description                                                                                                                                                                                          | Example                       |
| :---------------- | :---------------------- | :---------------------------------------- | :--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | :---------------------------- |
| `is_ads_eligible` | boolean                 | Conditionally required for Ads processing | Set `true` for products Ads should process. `false` explicitly opts out in the OpenAI format. Omitted or empty: disabled unless a feed-level Ads default applies. Independent of search eligibility. | `true`                        |
| `ads_metadata`    | Object of string values | Optional for Ads                          | Product-filter metadata using keys configured for your Ads integration. Omitted, empty, or `{}`: no metadata. Do not invent targeting keys; confirm them during Ads setup.                           | `{"custom_label_0":"summer"}` |

### Checkout

Checkout requires a separately enabled integration. Setting an eligibility flag
does not complete checkout onboarding. Continue to provide accurate discovery
data and configure digital-item support when applicable.

| Attribute               | Data type    | Requirement                                 | Description                                                                                                                                                                              | Example                       |
| :---------------------- | :----------- | :------------------------------------------ | :--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | :---------------------------- |
| `is_eligible_checkout`  | boolean      | Conditionally required to opt into checkout | `true` opts in only when search eligibility is also `true` and checkout is enabled for the integration. Omitted, empty, or `false`: disabled. Search set to `false` overrides this flag. | `true`                        |
| `seller_privacy_policy` | String (URL) | Conditionally required for checkout         | Public privacy policy for the seller. Omitted, empty, or invalid: no policy URL supplied; it does not establish checkout readiness.                                                      | `https://example.com/privacy` |
| `seller_tos`            | String (URL) | Conditionally required for checkout         | Public terms of service for the seller. Omitted, empty, or invalid: no terms URL supplied; it does not establish checkout readiness.                                                     | `https://example.com/terms`   |

### Compatibility notes

Existing `Custom_variant1_category` / `Custom_variant1_option` pairs, and the
corresponding `2` and `3` pairs, remain accepted along with lowercase aliases.
Migrate each pair to one entry in `variant_dict`, with the category as the key
and the selected option as the value. An explicit `variant_dict` takes
precedence. Do not mix representations; an explicit empty map does not fall
back to the legacy pairs.

Existing aliases remain accepted: `id` or `sku` for `item_id`, `item_group_id`
for `group_id`, `enable_search` for `is_eligible_search`, `enable_checkout` for
`is_eligible_checkout`, `is_eligible_ads` for `is_ads_eligible`, and
`return_window` for `return_deadline_in_days`. Send only one name per value:
`item_id` wins over `id` and `sku`; `group_id` wins over `item_group_id`; the
`enable_` flags win over their `is_eligible_` names; `is_ads_eligible` wins over
its alias; and `return_window` wins over `return_deadline_in_days`.

Sale-window dates, expiration dates, and availability dates do not schedule
price or availability changes in this contract. Update current prices and
availability in your feed when they change. Do not rely on uploaded dates to
remove a product or display a pre-order date. Warning and age-restriction fields
do not establish purchase restrictions.