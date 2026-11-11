# Best practices

> For the complete documentation index, see [llms.txt](/llms.txt). Markdown versions of documentation pages are available by appending `.md` to the page URL.

Onboarding product feeds in ChatGPT is currently available to approved
  partners. To apply for access, fill out this form 
  [here](https://chatgpt.com/merchants)

## Content quality

### Write factual descriptions

- Use concise, factual copy that helps users understand products.
- Plain text and bullet-style text are both acceptable.

### Use optional fields intentionally

- Optional fields like `description.html`, `description.markdown`, `categories.taxonomy`, and `seller.links` can improve answer quality but are not required for ingestion.
- If an optional field requires brittle transforms, omit it until data quality is stable.

### Keep URL values valid and encoded

- Ensure `url`, `media.url`, and seller link URLs are valid and encoded.
- Encode spaces and unsafe characters (for example, use `%20` for spaces).





## Seller and policy

### Keep attribution and policy links consistent

- Set `seller.name` to the seller users should see in listing context.
- Use durable, public URLs in `seller.links`.
- Reuse supported `Link.type` values consistently across your catalog.





## Variants

### Model variants at row level

- Use a stable product `id` for the parent product and a unique variant `id` for each purchasable option.
- Keep `title`, `url`, `description`, `media`, `availability`, and `price` variant-specific when those values differ by variant.
- Populate `variant_options` with the user-facing option dimensions, such as color or size.
- Use product-level `media` only when the assets apply across every variant.





## Attribution

### Track post-launch performance explicitly

- Add feed attribution parameters to `url` (for example `utm_medium=feed`) when you need feed-specific click tracking.
- Keep your internal tracking parameters consistent across snapshots.