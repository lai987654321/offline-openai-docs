# In your ChatGPT plugin

> For the complete documentation index, see [llms.txt](/llms.txt). Markdown versions of documentation pages are available by appending `.md` to the page URL.

Sign in with ChatGPT is currently available to selected commercial partners
  through a limited trial. To join the waitlist, contact your OpenAI
  representative.

Add Sign in with ChatGPT to let users sign in to your connector with their
ChatGPT account. They start the flow by selecting **Continue with ChatGPT** in
ChatGPT's plugin modal.

When a user starts this flow, ChatGPT begins your connector's OAuth flow. Your
application validates the OpenAI ID token, then completes connector
authorization.



> Illustration: A ChatGPT plugin page with a centered Connect Acme modal. ChatGPT and partner icons appear above the description, Plan projects and move work forward. The modal offers Sign in with Acme and a primary Continue with ChatGPT button, while the plugin page remains visible behind it.



## Understand the two flows

This integration contains two independent OAuth transactions. The outer
transaction authorizes your connector for ChatGPT. The inner transaction signs the user
in with ChatGPT and validates the OpenAI ID token. Keep their state, PKCE values, callbacks,
authorization codes, and credentials separate.

| Transaction                | OAuth client     | Authorization server | Result                                                                |
| -------------------------- | ---------------- | -------------------- | --------------------------------------------------------------------- |
| Outer: Connect your plugin | ChatGPT          | Your application     | Your connector authorization code, returned to ChatGPT.               |
| Inner: Sign in the user    | Your application | OpenAI               | An OpenAI authorization code, exchanged and verified by your backend. |

The inner transaction uses the [website sign-in flow](https://developers.openai.com/siwc/website). After
verifying the OpenAI ID token, your application identifies or creates a local
account and resumes the saved outer transaction.

## 1. Accept ChatGPT's authorization request

ChatGPT initiates a connector authorization request to your endpoint:

```text
GET /oauth/authorize?
  response_type=code
  &client_id=CHATGPT_CONNECTOR_CLIENT_ID
  &redirect_uri=REGISTERED_CHATGPT_CALLBACK
  &scope=REQUESTED_CONNECTOR_SCOPES
  &state=CHATGPT_GENERATED_STATE
  &code_challenge=CHATGPT_PKCE_CHALLENGE
  &code_challenge_method=S256
  &resource=CONNECTOR_RESOURCE
  &login_hint=USER_EMAIL_HINT
  &target_flow=chatgpt_siwc
```

Validate the registered ChatGPT connector client, exact redirect URI, supported
scopes, and outer PKCE challenge. Validate `resource` when your connector
implements resource indicators.

`target_flow=chatgpt_siwc` indicates a Sign in with ChatGPT-enabled connector
experience. Use `login_hint`, which contains the user's email, to suggest an
account or route to enterprise SSO.

When the hint matches an existing authenticated session and enterprise sign-in
requirements are satisfied, continue to connector consent without showing another
account selector. If the accounts differ, let the user choose. The hint does not verify the user's identity.

## 2. Save the outer connector transaction

Persist the validated connector request before starting inner sign-in. The
example below uses an application-owned registry of the connector client,
callback, scopes, and resource.

```javascript
export function saveConnectorTransaction(browserSessionId, requestUrl) {
  const params = requestUrl.searchParams;
  const scope = (params.get("scope") ?? "").split(" ").filter(Boolean);
  const codeChallenge = params.get("code_challenge") ?? "";
  if (
    params.get("response_type") !== "code" ||
    params.get("client_id") !== registeredConnector.clientId ||
    params.get("redirect_uri") !== registeredConnector.redirectUri ||
    params.get("code_challenge_method") !== "S256" ||
    !/^[A-Za-z0-9_-]{43}$/.test(codeChallenge) ||
    !params.get("state") ||
    scope.some((value) => !registeredConnector.scopes.has(value)) ||
    params.get("resource") !== registeredConnector.resource
  ) {
    throw new Error("The connector authorization request is invalid.");
  }

  const transaction = {
    id: randomValue(),
    browserSessionId,
    clientId: registeredConnector.clientId,
    redirectUri: registeredConnector.redirectUri,
    state: params.get("state"),
    codeChallenge,
    codeChallengeMethod: "S256",
    scope: scope.join(" "),
    resource: registeredConnector.resource,
    loginHint: params.get("login_hint"),
    targetFlow: params.get("target_flow"),
    expiresAt: Date.now() + 10 * 60 * 1000,
  };
  transactions.set(transaction.id, transaction);
  return transaction;
}
```


Bind the transaction to a server-generated browser session, set a short lifetime,
and protect the session identifier with an `HttpOnly`, `Secure` cookie. Use your
production session store instead of the example's in-memory map.

## 3. Choose the account experience

Use `target_flow`, the existing first-party session, and `login_hint` to select
the next experience. Check enterprise policy before continuing authorization.

```javascript
export function chooseAccountExperience(currentUser, connector, enterpriseSso) {
  const loginHint = connector.loginHint;
  if (enterpriseSso) {
    return { action: "enterprise-sign-in", returnTo: connector.id };
  }
  if (currentUser && (!loginHint || currentUser.email === loginHint)) {
    return { action: "connector-consent", userId: currentUser.id };
  }
  if (currentUser && loginHint) {
    return { action: "account-selector", suggestedEmail: loginHint };
  }
  if (connector.targetFlow !== "chatgpt_siwc") {
    return { action: "application-sign-in", returnTo: connector.id };
  }
  return { action: "sign-in-with-chatgpt", returnTo: connector.id };
}
```


Use the returned action to show the account selector, start your existing
application or enterprise sign-in, show connector consent, or start Sign in with ChatGPT.
Label the sign-in action **Continue with ChatGPT**.

- If the active account and hint differ, let the person choose the account.
- Honor enterprise-managed domains, mandatory SSO, organization access, and account-provisioning rules.
- Avoid exposing whether an email address or enterprise domain has an account through publicly distinguishable errors.
- If you offer manual linking, explain how the person can sign in and connect the existing account.

## 4. Reuse website sign-in

Start the complete [website sign-in flow](https://developers.openai.com/siwc/website) with its own values:

- A new OpenAI sign-in `state`.
- A new PKCE verifier and S256 challenge.
- A new OpenAI nonce.
- Your registered OpenAI client ID and callback URI.
- The identity scopes `openid profile email`.

A client's registered scopes define the maximum that it may request; they aren't
granted automatically. Requesting `openid profile email` is an identity-only
authorization.

Verify the inner state, exchange the OpenAI code on your backend, and verify the
OpenAI ID token before identifying or linking the local account. Resume the
browser's saved connector transaction after establishing the local session.

## 5. Return your connector authorization code

After authenticating the user and completing your connector's consent and access
checks, issue an authorization code for your connector. The code must be
short-lived, single-use, and bound to the original connector request.

```javascript
export function completeConnectorAuthorization(
  transactionId,
  browserSessionId,
  authenticatedUser,
  consentGranted
) {
  const connector = transactions.get(transactionId);
  if (
    !connector ||
    connector.browserSessionId !== browserSessionId ||
    connector.expiresAt <= Date.now() ||
    !authenticatedUser
  ) {
    throw new Error("The connector transaction could not be verified.");
  }
  transactions.delete(transactionId);

  const callback = new URL(connector.redirectUri);
  callback.searchParams.set("state", connector.state);
  if (!consentGranted) {
    callback.searchParams.set("error", "access_denied");
    return callback.toString();
  }

  const connectorCode = randomValue();
  authorizationCodes.set(connectorCode, {
    userId: authenticatedUser.id,
    clientId: connector.clientId,
    redirectUri: connector.redirectUri,
    codeChallenge: connector.codeChallenge,
    scope: connector.scope,
    resource: connector.resource,
    expiresAt: Date.now() + 60 * 1000,
  });
  callback.searchParams.set("code", connectorCode);
  return callback.toString();
}
```


Redirect the browser to the returned callback URL. Pass `authenticatedUser` only
from a verified application session and `consentGranted` only after your
connector's consent and access checks. In production, consume transactions and
codes atomically in shared storage.

If the user denies access or authorization fails, return an appropriate OAuth
error to the validated, registered connector callback with the original state.
Don't redirect to a callback until you've validated it.

## 6. Complete connector token exchange

ChatGPT redeems your connector authorization code at your connector token
endpoint. That endpoint must:

1. Validate the connector client.
2. Validate the authorization code, original connector redirect URI, and expiration.
3. Verify the outer `code_verifier` against the stored connector `code_challenge`.
4. Enforce the granted connector scopes and resource audience.
5. Issue only the application-owned connector tokens required for the integration.
6. Store and revoke connector credentials according to your existing security policy.

## Handle common integration problems

### The plugin opens the wrong account

Compare the hint to the current session for user experience only. Offer an
account selector instead of silently replacing a session or trusting an
unverified email.

### Enterprise SSO is required

Route the person through the existing enterprise identity provider. Resume the
saved outer request only after your application establishes a valid local
session.

### ChatGPT rejects the callback

Confirm that the redirect URI exactly matches the registered ChatGPT connector
callback. Return the original outer `state` and a connector authorization code.
Don't send an OpenAI code or ID token to ChatGPT as the connector result.

### PKCE verification fails

Check which transaction the verifier belongs to. The OpenAI verifier redeems the
inner OpenAI code; the ChatGPT verifier redeems your outer connector code.

### A returning user can't reconnect

Keep account-linking and reconnection paths available. If an existing account
must be linked manually, show actionable steps instead of an unexplained
conflict or generic error.

## Enable Continue with ChatGPT

After completing your implementation, contact your OpenAI representative on the
partnerships team to enable **Continue with ChatGPT** in your ChatGPT plugin's
modal.

## Test before launch

- Validate the connector's registered client, callback, scopes, and PKCE challenge.
- Confirm `target_flow=chatgpt_siwc` selects the expected experience.
- Test existing-account, switched-account, new-account, and enterprise SSO paths.
- Confirm the connector token endpoint verifies its own outer PKCE challenge.
- Keep the inner OpenAI code, ID token, and verifier out of the outer flow.
- Check that expired or reused connector transactions and authorization codes are rejected.
- Return denial errors only to the validated callback, with the original state.