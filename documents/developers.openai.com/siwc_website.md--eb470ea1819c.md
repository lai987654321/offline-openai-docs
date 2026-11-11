# On your website

> For the complete documentation index, see [llms.txt](/llms.txt). Markdown versions of documentation pages are available by appending `.md` to the page URL.

Sign in with ChatGPT is currently available to selected commercial partners
  through a limited trial. To join the waitlist, contact your OpenAI
  representative.

Add **Continue with ChatGPT** to your website using the OAuth 2.0 Authorization
Code flow with PKCE and OpenID Connect. Your backend exchanges the authorization
code, verifies the OpenAI ID token, associates the verified issuer, client ID, and
subject (`sub`) with an application account, and creates its own session.



> Illustration: A partner website sign-in modal titled Sign in to Acme. A work email field and Sign in with email button appear above a separate Sign in with ChatGPT button with the ChatGPT logo and an account avatar. Terms and Privacy Policy appear at the bottom of the modal.



Choose one of these four button formats for your app's sign-in page.



> Illustration: Four ChatGPT sign-in button formats: Continue with ChatGPT on black or white, and Sign in with ChatGPT on black or white. Each button includes the ChatGPT logo.



## Before you begin

[Request an OAuth client](https://developers.openai.com/siwc/request-client-id). You need:

- An OpenAI client ID, typically beginning with `oaiapp_`.
- An exact registered callback URL for each environment.
- The OpenAI issuer and corresponding authorization, token, and JWKS endpoints.
- Your registered token-endpoint authentication method and, for a confidential client, its client secret.
- A backend that can hold short-lived transaction state and create secure application sessions.

OpenAI publishes its production OpenID Connect discovery document at
`https://auth.openai.com/.well-known/openid-configuration`. Load the `issuer`,
`authorization_endpoint`, `token_endpoint`, and `jwks_uri` values from that
document. The production configuration in this example is:

```text
Issuer: https://auth.openai.com
Authorization endpoint: https://auth.openai.com/api/accounts/authorize
Token endpoint: https://auth.openai.com/api/accounts/oauth/token
JWKS URI: https://auth.openai.com/.well-known/jwks.json
Client ID: oaiapp_example
Redirect URI: https://example.com/auth/openai/callback
```

Replace the illustrative client ID and redirect URI with the values supplied for
your application. Require the ID token's `iss` claim to exactly match the issuer
returned by discovery.

OpenAI supports both public and confidential clients. For a confidential client,
store `OPENAI_CLIENT_SECRET` in your server-side secret manager. Public clients
don't receive or use a client secret. This guide covers
identity scopes; [ChatGPT plan usage in open-source apps](https://developers.openai.com/siwc/token-sharing-open-source/sign-in)
has a separate authorization and registration flow.

Use a maintained OAuth or OpenID Connect library when possible. The Node.js
  examples below show the backend operations with Node's `crypto` module and
  `jose` for JWT verification. Wire them to your application routes and session
  store. The sample's in-memory maps illustrate storage; production storage must
  expire transactions and support atomic, one-time consumption across instances.

## 1. Add the sign-in button

Point the button to your application's sign-in route. In this example, implement
`/auth/openai` on your backend to create a sign-in transaction and redirect the
browser to OpenAI's authorization endpoint. The following steps show how to
generate PKCE values and exchange tokens on the backend.

```html
<a
  href="/auth/openai"
  data-oai-siwc-button
  data-oai-siwc-button-client="oaiapp_example"
>
  Continue with ChatGPT
</a>
```

Add the `data-oai-siwc-button` HTML attribute to each Sign in with ChatGPT
  button or link on your page to help OpenAI verify your integration and
  troubleshoot sign-in issues. Add the attribute directly to the clickable
  element without a value. Optionally set `data-oai-siwc-button-client` to the
  OAuth client ID used by that button or link.

Keep the button discoverable for new and returning users. Use approved OpenAI
branding and assets, with a clear, accessible label such as **Continue with
ChatGPT**.

## 2. Create a one-time sign-in transaction

Generate a fresh `state`, PKCE verifier, S256 challenge, and nonce on your backend.
Bind the transaction to a server-generated browser session identifier.

Include the following optional query parameters on the initial OpenAI
authorization URL to help troubleshoot sign-in issues. Use opaque IDs that you
can match to your application's logs. These IDs do not expose the underlying
session or device data to OpenAI.

Store these values with the sign-in transaction so you can add them to the
authorization URL in the next step. The example passes `deviceToken`,
`loginSessionId`, and `loginStartedAtMs` in the `signInMetadata` object.

```javascript
export function createSignInTransaction(browserSessionId, signInMetadata = {}) {
  const state = randomValue();
  const codeVerifier = randomValue(64);
  const codeChallenge = crypto
    .createHash("sha256")
    .update(codeVerifier)
    .digest("base64url");
  const nonce = randomValue();
  const transaction = {
    state,
    codeVerifier,
    codeChallenge,
    nonce,
    signInMetadata,
    redirectUri,
    expiresAt: Date.now() + 10 * 60 * 1000,
  };

  transactions.set(browserSessionId, transaction);
  return transaction;
}

export function startSignIn(browserSessionId, deviceToken, loginSessionId) {
  return createSignInTransaction(browserSessionId, {
    deviceToken,
    loginSessionId,
    loginStartedAtMs: Date.now(),
  });
}
```


The example expires transactions after 10 minutes. Store the browser session
identifier in an `HttpOnly`, `Secure`, `SameSite=Lax` cookie. Keep the verifier and
other transaction values server-side.

## 3. Redirect to OpenAI

Build the authorization URL on your backend, then redirect the browser to it.
Include the optional sign-in signals below to help troubleshoot sign-in issues.
They help you and OpenAI match an authorization request to your app's device
and login session logs and identify when the user started signing in. This makes
it easier to investigate a specific sign-in attempt together.

| Parameter                 | Type    | Description                                                                                                              |
| ------------------------- | ------- | ------------------------------------------------------------------------------------------------------------------------ |
| `ext_device_token`        | String  | An opaque identifier assigned by your app to the device. Reuse it for sign-in attempts from the same device.             |
| `ext_login_session_id`    | String  | An opaque identifier for the app's login session, used to match the sign-in request to your session logs.                |
| `ext_login_started_at_ms` | Integer | The Unix timestamp in milliseconds when the user starts signing in to your app. OpenAI ignores values that aren't valid. |

The example adds these parameters when the transaction contains their values.
Send them in the authorization request, not the token exchange.

```javascript
export function buildAuthorizationUrl(transaction) {
  const authorizationUrl = new URL(authorizationEndpoint);
  const params = new URLSearchParams({
    client_id: clientId,
    redirect_uri: transaction.redirectUri,
    response_type: "code",
    scope: "openid profile email",
    state: transaction.state,
    code_challenge: transaction.codeChallenge,
    code_challenge_method: "S256",
    nonce: transaction.nonce,
  });
  const { deviceToken, loginSessionId, loginStartedAtMs } =
    transaction.signInMetadata;
  if (deviceToken != null) params.set("ext_device_token", deviceToken);
  if (loginSessionId != null) {
    params.set("ext_login_session_id", loginSessionId);
  }
  if (loginStartedAtMs != null) {
    params.set("ext_login_started_at_ms", String(loginStartedAtMs));
  }
  authorizationUrl.search = params.toString();

  return authorizationUrl.toString();
}
```


These scopes apply to identity sign-in:

| Scope     | Permission                                                           |
| --------- | -------------------------------------------------------------------- |
| `openid`  | Request an OpenID Connect identity token.                            |
| `profile` | Receive available profile claims, such as a name or profile picture. |
| `email`   | Receive available email and email-verification claims.               |

## 4. Handle the callback and verify state

Recover and consume the original transaction. Verify its expiration and returned
`state`, and check authorization errors before processing a code. Pass the
callback URL from the current request and the session identifier from the
browser's secure cookie.

```javascript
export function consumeSignInTransaction(browserSessionId, callbackUrl) {
  const transaction = transactions.get(browserSessionId);
  transactions.delete(browserSessionId);

  const returnedState = callbackUrl.searchParams.get("state");
  if (
    !transaction ||
    transaction.expiresAt <= Date.now() ||
    returnedState !== transaction.state
  ) {
    throw new Error("Sign-in could not be verified.");
  }

  if (callbackUrl.searchParams.has("error")) {
    throw new Error("Sign-in could not be completed.");
  }

  const code = callbackUrl.searchParams.get("code");
  if (!code) {
    throw new Error("The callback did not contain an authorization code.");
  }

  return { code, transaction };
}
```


A missing, expired, reused, or mismatched transaction ends sign-in. Never redeem a
code from an unverified callback. Clear temporary browser state on success and
failure, and show an actionable sign-in error without exposing credentials.

## 5. Exchange the authorization code

Call the OpenAI token endpoint from your backend using the original redirect URI
and PKCE verifier. Use the token-endpoint authentication method provisioned for
your client.

### Public client

An identity-only public client requests `openid`, `profile`, and `email`. It
authenticates at the token endpoint with `none` and doesn't send a client secret.

```javascript
export async function exchangePublicClientCode(code, transaction) {
  const body = new URLSearchParams({
    grant_type: "authorization_code",
    code,
    redirect_uri: transaction.redirectUri,
    client_id: clientId,
    code_verifier: transaction.codeVerifier,
  });

  return fetch(tokenEndpoint, {
    method: "POST",
    headers: {
      accept: "application/json",
      "content-type": "application/x-www-form-urlencoded",
    },
    body,
  });
}
```


### Confidential client

If OpenAI provisioned a confidential client with `client_secret_basic`, use its
client secret to authenticate the backend token request. Keep PKCE in this flow.

```javascript
export async function exchangeConfidentialClientCode(code, transaction) {
  const clientSecret = process.env.OPENAI_CLIENT_SECRET;
  if (!clientSecret) {
    throw new Error("The confidential client requires its client secret.");
  }

  const encodeFormComponent = (value) =>
    new URLSearchParams({ value }).toString().slice("value=".length);
  const basicAuthorization = Buffer.from(
    `${encodeFormComponent(clientId)}:${encodeFormComponent(clientSecret)}`
  ).toString("base64");

  return fetch(tokenEndpoint, {
    method: "POST",
    headers: {
      accept: "application/json",
      "content-type": "application/x-www-form-urlencoded",
      authorization: `Basic ${basicAuthorization}`,
    },
    body: new URLSearchParams({
      grant_type: "authorization_code",
      code,
      redirect_uri: transaction.redirectUri,
      client_id: clientId,
      code_verifier: transaction.codeVerifier,
    }),
  });
}
```


Send the secret only through the HTTP Basic authorization header. Don't add it to
the form body. A missing or invalid secret causes the request to fail; OpenAI
doesn't fall back to public-client authentication. Never expose the secret in
client-side code, logs, URLs, agent output, or source control.

### Validate the token response

After either request, check the response before using the returned ID token.

```javascript
export async function readIdentityToken(tokenResponse) {
  if (!tokenResponse.ok) {
    const requestId =
      tokenResponse.headers.get("openai-request-id") ??
      tokenResponse.headers.get("x-request-id");
    console.error("OpenAI token exchange failed", {
      status: tokenResponse.status,
      requestId,
    });
    throw new Error("OpenAI token exchange failed.");
  }

  const tokens = await tokenResponse.json();
  if (typeof tokens.id_token !== "string") {
    throw new Error("The token response did not contain an ID token.");
  }
  return tokens.id_token;
}
```


For standard identity-only sign-in, the required artifact is `id_token`. Don't
require an OpenAI `access_token` or `refresh_token`; they aren't part of the
standard identity-only client contract.

## 6. Verify the ID token

Verify the JWT signature against the issuer's JWKS before trusting identity
claims. Check the issuer, audience, expiration, and original nonce. The example's
`jwks` value uses `createRemoteJWKSet` from `jose` with the discovery document's
`jwks_uri`.

```javascript
export async function verifyOpenAiIdentity(idToken, expectedNonce) {
  const { payload } = await jwtVerify(idToken, jwks, {
    issuer,
    audience: clientId,
    requiredClaims: ["sub", "exp", "iat"],
    clockTolerance: 5,
  });

  if (payload.nonce !== expectedNonce) {
    throw new Error("The ID token nonce did not match.");
  }
  if (typeof payload.sub !== "string" || !payload.sub) {
    throw new Error("The ID token did not contain a subject.");
  }
  if (
    payload.sid !== undefined &&
    (typeof payload.sid !== "string" || !payload.sid.trim())
  ) {
    throw new Error("The ID token contained an invalid session identifier.");
  }

  return payload;
}
```


Use a maintained JWT library, allow only a small clock-skew tolerance, cache JWKS
responsibly, and refresh keys when an unfamiliar `kid` appears. This example
always sends a nonce and requires the same value in the ID token.

### Sample ID token

Here is an example of a decoded ID token:

```json
{
  "iss": "https://auth.openai.com",
  "sub": "Bo0QaQ2FivlsFyUOPhtpz7lZvG486y5QLLXmeNeR2N1QBo1TsroPxQ",
  "aud": ["oaiapp_EHBV7pzdMtehZ7j6Ypgyje-F"],
  "nonce": "DAkt1BdJ869SA4mFj92yRKUtj_4OKQJV",
  "auth_time": 1769045114,
  "email": "alex.morgan@example.com",
  "email_verified": false,
  "name": "Alex Morgan",
  "sid": "sid_i8EACl9LcyfQ4x57YfBHonV1P3K--tH_qDYUalZ0I0albTB2c6-Btl5hFWQ",
  "https://api.openai.com/auth": {
    "per_user_salt": "X-QSrbN76aI"
  },
  "iat": 1769045118,
  "exp": 1769048718,
  "jti": "eca69a1bcc0b1489898eeb63acf33340",
  "at_hash": "3bigLYzG30QQKOaO4N1Pkw"
}
```

| Field                         | What it means                                                                                                                   |
| ----------------------------- | ------------------------------------------------------------------------------------------------------------------------------- |
| `iss`                         | **Issuer:** the OpenAI auth server that issued the token.                                                                       |
| `sub`                         | **User ID:** identifies the OpenAI user to your app.                                                                            |
| `aud`                         | **Audience:** the client ID of the app that should receive this token.                                                          |
| `nonce`                       | **Sign-in request reference:** matches the value your app sent when starting sign-in.                                           |
| `auth_time`                   | **Authentication time:** when the user authenticated, in Unix seconds.                                                          |
| `email`                       | The user's email address.                                                                                                       |
| `email_verified`              | Whether OpenAI has verified the email address.                                                                                  |
| `name`                        | The user's display name.                                                                                                        |
| `sid`                         | **OpenAI session reference:** an opaque ID, separate from the partner-provided `ext_login_session_id`.                          |
| `https://api.openai.com/auth` | A container for OpenAI-specific fields.                                                                                         |
| `per_user_salt`               | A nested field in `https://api.openai.com/auth` that OpenAI uses to generate anonymous identifiers. Treat this value as opaque. |
| `iat`                         | **Issued at:** when OpenAI created the token, in Unix seconds.                                                                  |
| `exp`                         | **Expires at:** when the token expires, in Unix seconds.                                                                        |
| `jti`                         | **Token ID:** uniquely identifies this token.                                                                                   |
| `at_hash`                     | **Access-token hash:** checks that an accompanying access token matches this ID token, if OpenAI issues one.                    |

## 7. Find, create, or link the local account

Use the verified OpenAI `sub` as the stable external identity. Include the issuer
and client to prevent collisions across providers and environments.

```javascript
export function externalIdentityFor(identity) {
  return {
    provider: "openai",
    issuer,
    clientId,
    subject: identity.sub,
    email: identity.email ?? null,
    name: identity.name ?? null,
    picture: identity.picture ?? null,
  };
}
```


Apply an explicit account-linking policy:

1. If the OpenAI subject is already linked, sign in to the linked local account.
2. If a signed-in user adds ChatGPT as a sign-in method, or their email matches an existing account, provide a way to confirm and link the accounts. An email match alone isn't proof of account ownership.
3. If no account exists, allow account creation according to your product, onboarding, and enterprise policies.

## 8. Create your application session

After verification and account resolution, issue your own first-party session.
The helper below receives your HTTP response, the resolved local user, and the
verified ID-token claims. It stores the issuer, client ID, subject, and optional
`sid` with the app session so you can identify sessions affected by an
[account security notification](https://developers.openai.com/siwc/account-security-notification).

```javascript
export function createApplicationSession(response, localUser, identity) {
  const sessionId = randomValue();
  sessions.set(sessionId, {
    userId: localUser.id,
    openai: {
      issuer: identity.iss,
      clientId,
      subject: identity.sub,
      sid: identity.sid ?? null,
    },
    expiresAt: Date.now() + 8 * 60 * 60 * 1000,
  });

  response.setHeader(
    "Set-Cookie",
    `__Host-session=${sessionId}; Path=/; HttpOnly; Secure; SameSite=Lax; Max-Age=28800`
  );
  response.writeHead(302, { Location: "/app" });
  response.end();
}
```


Use an `HttpOnly`, `Secure`, `SameSite=Lax` session cookie. Don't return an ID token,
PKCE verifier, authorization code, or client secret to browser JavaScript. Clear
the temporary sign-in cookie after completing the transaction.

Retain only the identity mapping and user information your application needs.
Avoid storing raw OpenAI ID tokens after verification unless a separately
documented requirement demands it.

## Test before launch

- Confirm the registered callback and requested `redirect_uri` match exactly.
- Generate fresh state, PKCE values, and a nonce for every sign-in.
- Check that missing, expired, reused, and mismatched transaction state is rejected.
- Exchange the code with the original verifier and registered client authentication method.
- Check that a confidential token request with a missing or invalid secret fails.
- Check that an ID token with an invalid signature, issuer, audience, expiration, or nonce is rejected.
- Clear temporary authorization state after success and failure.
- Confirm that signing out clears only the first-party application session.

Next, reuse this flow [in your ChatGPT plugin](https://developers.openai.com/siwc/chatgpt-plugin).