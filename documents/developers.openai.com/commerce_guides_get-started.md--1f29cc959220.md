# Get Started

> For the complete documentation index, see [llms.txt](/llms.txt). Markdown versions of documentation pages are available by appending `.md` to the page URL.

Onboarding product feeds in ChatGPT is currently available to approved
  partners. To apply for access, fill out this form 
  [here](https://chatgpt.com/merchants)

## Overview

Start your ACP integration by sharing a structured product feed with OpenAI. Product feeds give ChatGPT the catalog data it needs to index your products, understand core attributes, and present accurate product information in shopping experiences.

Start with product feeds when you want to:

- Make your catalog understandable to ChatGPT.
- Share up-to-date product data, including titles, descriptions, images, price, and availability.
- Establish a clear integration path based on a documented schema and delivery model.

## Integration path

Use this sequence to stand up your integration with ACP:

1. **Review** the [file upload guide](https://developers.openai.com/commerce/specs/file-upload/overview) and [product file schema](https://developers.openai.com/commerce/specs/file-upload/products).
2. **Validate** the required fields for every record.
3. **Upload** your catalog over SFTP.
4. **Keep** the feed current by overwriting the same file or shard set with your latest snapshot. We recommend uploading a full snapshot at least once a day.

To submit promotions, use the [Promotions API](https://developers.openai.com/commerce/specs/api/promotions).

## Prohibited products policy

To keep ChatGPT a safe place for everyone, we only allow products and services that are legal, safe, and appropriate for a general audience. Prohibited products include, but are not limited to, those that involve adult content, age-restricted products (for example, alcohol, nicotine, gambling), harmful or dangerous materials, weapons, prescription-only medications, unlicensed financial products, legally restricted goods, illegal activities, or deceptive practices.

Merchants are responsible for ensuring their products and content do not violate these restrictions or any applicable law. OpenAI may take corrective actions such as removing a product or banning a seller from being surfaced in ChatGPT if these policies are violated.

## Best practices

Review integration [best practices](https://developers.openai.com/commerce/guides/best-practices) for guidance.