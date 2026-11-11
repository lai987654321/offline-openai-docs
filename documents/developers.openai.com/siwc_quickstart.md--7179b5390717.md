# Quickstart

> For the complete documentation index, see [llms.txt](/llms.txt). Markdown versions of documentation pages are available by appending `.md` to the page URL.

Sign in with ChatGPT lets users sign in to your app with their ChatGPT account
and, when eligible, use their ChatGPT plan for AI requests. It supports sign-in
and optional ChatGPT plan usage:

- **For users:** Sign in with an existing ChatGPT account. Eligible ChatGPT Plus
  and Pro users can use their ChatGPT plan for AI requests in participating apps
  and manage app usage and access in ChatGPT settings.
- **For partner apps:** Offer a familiar sign-in option on your website or in your
  ChatGPT plugin. Apps approved for ChatGPT plan usage can also complete eligible
  AI requests with usage included in the user's ChatGPT plan or available credits.
- **For open-source developers:** Let users run AI workloads in your tools with
  their ChatGPT plan, without requiring them to provide an API key. The
  open-source sign-in flow registers your client and issues OAuth credentials for
  eligible Responses API requests, without a client secret or partner API key.

Sign in with ChatGPT is currently available to selected commercial partners
through a limited trial. ChatGPT plan usage is available to all open-source
partners and selected private clients.

## Choose an integration




| Start here                                                                    | What it is                                                                                                   |
| ----------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------ |
| [Sign-in on your website](https://developers.openai.com/siwc/website)                                      | ChatGPT users bring their identity into your product to sign up or sign in with an account they already use. |
| [Sign-in for your ChatGPT plugin](https://developers.openai.com/siwc/chatgpt-plugin)                       | Users sign in to your app through ChatGPT with less OAuth friction.                                          |
| [ChatGPT plan usage in your open-source app](https://developers.openai.com/siwc/token-sharing-open-source) | Eligible ChatGPT Plus and Pro users can use their ChatGPT plan for AI requests in your product.              |




## Make sign-in recognizable

Label the action **Continue with ChatGPT**. Place it with your other sign-in
options, give it comparable visual prominence, and use approved OpenAI branding.

Returning users should find the same sign-in method on subsequent visits. If
someone already has an account, provide a clear way to confirm and link it. When
your product requires enterprise single sign-on, guide the person to that
existing sign-in experience.

## Understand scopes

With the appropriate identity scopes, your application can receive a stable
account identifier and a person's name, email address, and
profile picture. Identity scopes don't grant access to ChatGPT conversations or
OpenAI API resources.

Using a ChatGPT plan requires separate Responses API scopes that the user must
authorize. It doesn't grant access to the user's API key or conversations. Follow
the [open-source sign-in guide](https://developers.openai.com/siwc/token-sharing-open-source/sign-in) for its
authorization and request contract.

## Follow the sign-in flow

Identity-only clients request `openid profile email` to receive an ID token for
sign-in. Clients that use ChatGPT plans also request scopes for Responses API
access. If the user grants those scopes, the token response includes an access
token for eligible inference requests.

1. Your application starts an OpenID Connect sign-in with PKCE.
2. The person authenticates and consents with OpenAI.
3. OpenAI returns an authorization code to your registered callback.
4. Your backend exchanges the code and verifies the OpenAI ID token.
5. Your application identifies or creates a local account and issues its own session.

For a plugin, your application also returns a connector authorization code to
ChatGPT. The connector's permissions and credentials remain separate from the
OpenAI identity token.

Your application owns account creation, enterprise sign-in policy, sessions,
  authorization, and connector access. Sign in with ChatGPT supplies the
  verified OpenAI identity used by those application flows.