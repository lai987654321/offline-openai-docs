# UI/UX guidelines

> For the complete documentation index, see [llms.txt](/llms.txt). Markdown versions of documentation pages are available by appending `.md` to the page URL.

Help users understand when your app uses their ChatGPT plan, where to manage usage, and what to do when they reach a limit. Use these guidelines for ChatGPT plan usage and the approved [sign-in button formats](https://developers.openai.com/siwc/website).




## Confirm ChatGPT plan use after the first sign-in

Show a welcome modal only the first time a user signs in to your app with ChatGPT plan usage enabled. Do not show it again on later sign-ins. Explain that eligible AI requests in your app will use their ChatGPT plan and that they can manage usage in ChatGPT settings. Let them dismiss the message and continue.

Use a clear confirmation, such as **You're using your ChatGPT plan**, with a **Got it** action.



> Illustration: First-sign-in confirmation: the ChatGPT logo appears above You're using your ChatGPT plan. The message explains that eligible usage in the app uses the ChatGPT plan and can be managed in ChatGPT settings. A primary Got it button dismisses the modal in the partner app.






## Offer ChatGPT plan use in settings

Offer users the option to use their ChatGPT plan during onboarding or billing, and keep it available later in settings. Use **Continue with ChatGPT** when the action starts the sign-in flow.

Explain that users can use their ChatGPT plan in your app. Distinguish ChatGPT plan usage from your app's own subscription or charges.



> Illustration: Settings card: Use your ChatGPT plan. The description says Complete eligible AI requests in this app with usage included in your ChatGPT plan or credits balance. A black Continue with ChatGPT button includes the ChatGPT logo.



## Link to ChatGPT usage

On your app's usage page, place a **Manage usage** link near the usage summary. Open [ChatGPT usage settings](https://chatgpt.com/settings/usage) so users can review usage and update settings for their plan or your app.



> Illustration: Partner usage summary: ChatGPT plan usage over the last 30 days, with placeholders for Total, Peak per day, and Active days. A callout immediately below the summary says View and manage your ChatGPT usage and provides a Manage usage link to ChatGPT usage settings.



## Show when the ChatGPT plan is in use

When requests use the user's ChatGPT plan, display **Using ChatGPT plan** near the composer or model selector. Include a **Manage usage** link to [ChatGPT usage settings](https://chatgpt.com/settings/usage), where users can review usage and adjust limits.



> Illustration: An open Model speed menu appears above a message composer. It lists Instant, Medium with a checkmark, and High, each with a distinct brain icon. Fast mode is switched on beside Uses your plan or credits faster. A blue row at the bottom shows the ChatGPT logo, Using ChatGPT plan, and a Manage usage button linking to ChatGPT usage settings. The composer contains an attachment button, Start chatting or describe a task..., the selected Medium model speed, and a microphone button.



## Offer options when users reach a usage limit

When your app receives a usage-limit error, direct the user to ChatGPT usage settings. The limit may apply to their ChatGPT plan or specifically to your app.

- Make **Manage usage** the primary action. Open [ChatGPT usage settings](https://chatgpt.com/settings/usage) so the user can review the applicable limit.
- If your app offers its own credits, present an option to buy them as a secondary action.

Use a modal or a compact message for this state. Keep the ChatGPT identity visible in the compact version, and preserve the same action hierarchy in both.



> Illustration: Two examples of the same usage-limit state: a centered modal and a compact card with a ChatGPT header. Both say Usage limit reached and direct users to review their plan or app limit in ChatGPT settings. Both show Manage usage as the primary action and Buy app credits as an optional secondary action.






## Invite existing users to sign in with ChatGPT

Show a banner to users who signed in with another method, such as Google. Explain that they can use their ChatGPT plan in your app, and use **Continue with ChatGPT** as the action.

Lead users to the sign-in flow from settings. If your integration requires a new sign-in, guide them to sign out and sign back in with ChatGPT.



> Illustration: A banner for existing users has a New badge, the message Use your ChatGPT plan in this app, and a black Continue with ChatGPT button.






## Make eligible app plans clear


**Your app must clearly show which of its plans support ChatGPT plan usage.** Make this information visible on your pricing or plan-comparison page.

Include **Use your ChatGPT plan** in the feature list for each supported plan. Link **Learn more** to the [OpenAI Help Center](https://help.openai.com) for guidance on ChatGPT plan usage. Use your app's plan names and eligibility rules; the names, prices, and features below are illustrative.



> Illustration: Example partner pricing comparison with three cards: Free at $0 per month, Pro at $20 per month, and Enterprise with Contact sales. Free has Your current plan and features for explanations, short chats, image generation, and limited memory. Pro has Upgrade to Pro and lists Use your ChatGPT plan with an inline learn more link, followed by in-depth topics, longer chats and uploads, more images, more memory, and planning and tasks. Enterprise lists complex problems, chats over multiple sessions, faster image creation, memory of goals and conversations, agent mode, and projects. These names, prices, and features illustrate a partner app's pricing page.