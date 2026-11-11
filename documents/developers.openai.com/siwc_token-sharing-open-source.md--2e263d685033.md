# Overview

> For the complete documentation index, see [llms.txt](/llms.txt). Markdown versions of documentation pages are available by appending `.md` to the page URL.

## Introduction

ChatGPT plan usage is an optional capability within Sign in with ChatGPT. In addition to identity scopes, your open-source app can request permission to use the user’s ChatGPT plan for eligible Responses API requests. This does not grant access to their ChatGPT conversations or other account context.

_These docs explain ChatGPT plan usage for open-source and locally hosted apps. If you’re interested in offering it in a paid or remotely hosted app, complete the [interest form](https://openai.com/form/sign-in-with-chatgpt-interest/)._

The OAuth flow for OSS clients registers a **user-defined agent** during Sign in with ChatGPT. Before the first sign-in, choose and persist the required `ext_agent_host_id`.

## A client vs. an agent host

A client is the OAuth registration a user authorizes for your tool during Sign in with ChatGPT. In this dynamic-registration flow, each issued `client_id` is bound to the authenticated user and the workspace selected during registration. Its issued `client_id` identifies that registration, its security boundaries, and its ChatGPT plan usage settings.

An agent host is the environment where an instance of your tool runs, such as a laptop installation or a self-hosted VM. Your app defines what counts as one host and when its lifecycle begins and ends. Restarting the tool or signing in again does not by itself create a new host.

The client represents what the user authorizes and configures; the host represents where the app runs. A single client can have multiple hosts for the same user and workspace. For example, the same user’s laptop and self-hosted VM can use one issued `client_id` for that workspace to share ChatGPT plan usage settings and limits, while each has its own host ID. Send the stable, opaque `ext_agent_host_id` so ChatGPT plan usage can be associated with its host separately from the issued `client_id`. An issued `client_id` can be reused across different agent hosts for the same user and workspace, but each host must have its own distinct host identifier.



> Illustration: One ChatGPT user and workspace authorizes one issued client_id. The same client registration shares plan usage settings and limits across a laptop with host ID L and a self-hosted VM with host ID V. Each host has a distinct host ID.



In this illustration, two hosts for the same user and workspace share one client configuration while having their own unique host IDs.

**Host-ID:** Generate and persist a stable `ext_agent_host_id` for each host separately. Choose and persist the host ID before its first sign-in. Use an opaque value, not an email, user ID, or other user-identifying value. A host ID is not an authentication credential.

When choosing a host-ID format, prefer a JWK thumbprint URI derived from the public key in a public/private key pair using [RFC 9278](https://www.rfc-editor.org/rfc/rfc9278.html). Persist the `urn:ietf:params:oauth:jwk-thumbprint:…` value and reuse it as the host's `ext_agent_host_id`. This recommendation is optional; UUID-based host IDs remain supported.

A public-key-derived host ID is currently an identifier only. OpenAI does not verify possession of the private key as part of this flow.

For a UUID-based host ID, generate a [UUIDv4](https://www.rfc-editor.org/rfc/rfc9562.html#section-5.4) once per host, prefix its hyphenated string form with `urn:uuid:`, and persist the value for reuse across sign-ins. The accepted formats are:

| Format                                   | Guidance                                                                                              |
| ---------------------------------------- | ----------------------------------------------------------------------------------------------------- |
| `urn:ietf:params:oauth:jwk-thumbprint:…` | Recommended when choosing a host-ID format. Derive the URI from the host's public key using RFC 9278. |
| `urn:uuid:…`                             | Supported alternative. Generate a UUID and store its URI once for the host’s lifecycle.               |
| `did:key:<key>`                          | Use `did:key`, not another DID method.                                                                |

## From first launch to first inference

On first launch, your client prepares a host ID and opens the browser for sign-in, client registration, and consent to use the user’s ChatGPT plan. It exchanges the authorization code for OAuth tokens, validates the ID token and granted scopes, and stores the user’s basic account info and credentials. It then uses the access token to send a Responses API request and process the stream through completion. Later sign-ins reuse the saved client ID.



> Illustration: Your client chooses a ChatGPT account, persists or reuses the host ID, starts a listener, and generates fresh state, nonce, and PKCE. It opens OAuth in the system browser with a new registration or a saved client_id. OpenAI authorization completes required authentication or consent, then redirects through the browser to the loopback callback with code, state, and an issued client_id for new registration. Your client validates state, then exchanges the code at the OpenAI token endpoint using the issued or saved client_id and PKCE. It receives tokens and granted scopes, validates the ID token and scopes, and stores the user’s basic account info and credentials. It calls the Responses API with a bearer access token, store: false, and stream: true, then processes stream events through response.completed.



## Next steps

- [UI/UX guidelines](https://developers.openai.com/siwc/ui-ux-guidelines): Design the sign-in, usage, and plan-selection experience for ChatGPT plan usage.
- [Sign in](https://developers.openai.com/siwc/token-sharing-open-source/sign-in): Register your client, validate the ID token and ChatGPT plan permission, and save credentials.
- [Accounts and sessions](https://developers.openai.com/siwc/token-sharing-open-source/profiles-and-sessions): Manage ChatGPT accounts, refresh tokens, and protect credentials.
- [Models and inference](https://developers.openai.com/siwc/token-sharing-open-source/models-and-inference): List available models and stream a Responses API request through completion.
- [Codex app-server](https://developers.openai.com/siwc/token-sharing-open-source/codex-app-server): Configure Codex app-server to use an OAuth access token authorized for ChatGPT plan usage.
- [Self-hosted VMs](https://developers.openai.com/siwc/token-sharing-open-source/self-hosted-vms): Prepare a VM host ID and securely transfer the SIWC credentials associated with the selected ChatGPT account.
- [Token reference](https://developers.openai.com/siwc/token-sharing-open-source/token-reference): Look up token-response fields, token lifetimes, and access-token claims.
- [Errors and recovery](https://developers.openai.com/siwc/token-sharing-open-source/errors-and-recovery): Handle declined consent, request failures, and revoked sessions.
- [Preview limitations](https://developers.openai.com/siwc/token-sharing-open-source/preview-limitations): Review current Responses API requirements and Codex app-server limitations.