# Account security notification

> For the complete documentation index, see [llms.txt](/llms.txt). Markdown versions of documentation pages are available by appending `.md` to the page URL.

Account security notifications use the OpenID Connect (OIDC) Back-Channel Logout
protocol. OpenAI sends your backend a signed Logout Token to request user or
session logout. Your app must validate the token and end the sessions it identifies.

1. **OpenAI** sends a signed request.
2. **Your server** verifies the token.
3. **Your app** ends matching sessions.

## User and session logout

Notifications can request user logout or session logout. Check `sub` and `sid`
to determine which sessions to end.

| Scope          | Claims                        | Sessions to end                                              |
| -------------- | ----------------------------- | ------------------------------------------------------------ |
| User logout    | `sub`, without `sid`          | All of the user's app sessions, across browsers and devices. |
| Session logout | `sid`, with an optional `sub` | Only the sessions associated with that `sid`.                |

## What the token contains

A Logout Token is a signed JSON Web Token (JWT). Its claims identify your app
and the user or session to sign out. The server-to-server request doesn't include
a browser cookie.

This decoded example targets one session. A user logout has the same format
with `sub` and no `sid`. The IDs and timestamps are illustrative.

Header:

```json
{
  "alg": "RS256",
  "kid": "example-signing-key",
  "typ": "logout+jwt"
}
```

Payload:

```json
{
  "iss": "https://auth.openai.com",
  "aud": "oaiapp_EXAMPLE",
  "sub": "example-openai-subject",
  "sid": "example-openai-session",
  "iat": 1791442800,
  "exp": 1791442920,
  "jti": "unique-logout-token-id",
  "events": {
    "http://schemas.openid.net/event/backchannel-logout": {}
  }
}
```

| Claim         | Description                                                                               |
| ------------- | ----------------------------------------------------------------------------------------- |
| `iss`         | The OpenAI issuer that signed the token.                                                  |
| `aud`         | Your application's OpenAI client ID.                                                      |
| `sub`         | The user's subject from sign-in. Required for user logout and optional with `sid`.        |
| `sid`         | The session identifier from sign-in. Limits logout to matching sessions.                  |
| `iat` / `exp` | Issuance and expiration times in Unix seconds. The maximum token lifetime is 120 seconds. |
| `jti`         | A unique token ID for replay detection.                                                   |
| `events`      | The logout instruction. The event value is an empty object.                               |

A Logout Token is only an instruction to end sessions. It can't be used to sign
in or access account data. It contains no `nonce`, email address, conversation
content, or reason for the security action.

## 1. Create your endpoint

Create a public HTTPS endpoint that accepts POST requests. OpenAI sends the
signed token in the `logout_token` form field:

```http
POST /oidc/automatic-logout HTTP/1.1
Host: partner.example.com
Content-Type: application/x-www-form-urlencoded

logout_token=<signed-JWT>
```

Parse the body as form data and require exactly one nonempty `logout_token`.
Your endpoint must accept requests without a browser login or redirect.

## 2. Verify the token and end sessions

Verify the token's signature, issuer, audience, expiry, and logout event before
ending sessions. At sign-in, store the verified issuer, client ID, and `sub` with
the user's local account. Store the verified ID token's `sid` with the app
session when provided.

- **With `sid`:** Find sessions by issuer, client ID, and `sid`. If `sub` is also present, check that the sessions belong to that user. An unknown `sid` must not trigger user logout.
- **Without `sid`:** Find the user by issuer, client ID, and `sub`, and end all their app sessions.

Revoke matching sessions and credentials that can renew them. Enforce revocation
on every server that accepts sessions.

<details>
  <summary>Example: Validate a Logout Token in Python</summary>

Install `PyJWT[crypto]` to validate both logout scopes using production
settings. This example allows five seconds of clock tolerance.

Fetch signing keys from the configured OpenAI JWKS endpoint
(`https://auth.openai.com/.well-known/jwks.json`) and support key rotation.
Never use a key URL supplied in the token. For staging, use
`https://auth.api.openai.org` as the issuer and
`https://auth.api.openai.org/.well-known/jwks.json` as its JWKS endpoint.

```python
import math
import time

import jwt
from jwt import PyJWKClient

ISSUER = "https://auth.openai.com"
CLIENT_ID = "oaiapp_example"
CLOCK_TOLERANCE = 5  # Example: allow five seconds of clock skew.
LOGOUT_EVENT = "http://schemas.openid.net/event/backchannel-logout"
jwks = PyJWKClient("https://auth.openai.com/.well-known/jwks.json", timeout=5)


def nonempty_string(value):
    return isinstance(value, str) and bool(value.strip())


def numeric_date(value):
    return type(value) is int or (type(value) is float and math.isfinite(value))


def verify_logout_token(logout_token):
    header = jwt.get_unverified_header(logout_token)
    if (
        header.get("alg") != "RS256"
        or header.get("typ") != "logout+jwt"
        or not nonempty_string(header.get("kid"))
    ):
        raise jwt.InvalidTokenError("Invalid Logout Token header")

    # Read keys only from the configured JWKS URL, then verify the signature.
    signing_key = jwks.get_signing_key(header["kid"])
    claims = jwt.decode(
        logout_token,
        signing_key.key,
        algorithms=["RS256"],
        issuer=ISSUER,
        audience=CLIENT_ID,
        options={
            "require": ["iss", "aud", "iat", "exp", "jti", "events"],
            # Check time claims below without coercing strings or booleans.
            "verify_iat": False,
            "verify_exp": False,
            "verify_nbf": False,
        },
    )

    now = time.time()
    issued_at, expires_at = claims["iat"], claims["exp"]
    not_before = claims.get("nbf", now)
    events = claims["events"]
    if (
        not numeric_date(issued_at)
        or not numeric_date(expires_at)
        or not now - 120 - CLOCK_TOLERANCE <= issued_at <= now + CLOCK_TOLERANCE
        or not issued_at < expires_at <= issued_at + 120
        or expires_at <= now - CLOCK_TOLERANCE
        or not numeric_date(not_before)
        or not_before > now + CLOCK_TOLERANCE
        or not ("sub" in claims or "sid" in claims)
        or ("sub" in claims and not nonempty_string(claims["sub"]))
        or ("sid" in claims and not nonempty_string(claims["sid"]))
        or not nonempty_string(claims["jti"])
        or not isinstance(events, dict)
        or events.get(LOGOUT_EVENT) != {}
        or "nonce" in claims
    ):
        raise jwt.InvalidTokenError("Invalid Logout Token")

    return claims
```


After validation, use the returned claims to select and revoke sessions. In your
endpoint, parse the form body, handle duplicate requests, and return HTTP
responses. Catch
`jwt.InvalidTokenError` for invalid tokens. An unknown signing key can raise
`jwt.PyJWKClientError`; distinguish an unknown key in a successfully fetched key
set from a failure to fetch keys or a storage failure. Treat both failures as
server errors.

</details>

### Return a response

Return an HTTP status code to indicate the outcome of processing the notification.

| Status         | When to return it                                                                    |
| -------------- | ------------------------------------------------------------------------------------ |
| `200` or `204` | Logout is complete, the token was already processed, or no matching sessions remain. |
| `400`          | The token is invalid. Leave sessions unchanged.                                      |
| `503`          | A temporary server failure prevents validation or logout.                            |

## 3. Configure your endpoint

Configure your endpoint in OpenAI Platform to receive account security notifications.

1. In [OpenAI Platform](https://platform.openai.com/), select **OAuth apps** in the sidebar, select your client, and open **Security notifications**.
2. Select **Add logout endpoint** and enter your endpoint URL.
3. Select **Save endpoint**.
4. Select **Enable automatic logout** and confirm the action.
5. Check that **Automatic logout** shows **On** and the saved endpoint URL is correct.

If either change requires review, submit it and publish it after approval before
continuing. Existing settings stay active until publication. Saving the endpoint
alone doesn't enable production notifications.

If **Security notifications** is unavailable, contact OpenAI about access.

## 4. Test your integration

Use **Test endpoint** to send a signed Logout Token to your saved endpoint. The
test checks delivery; it doesn't verify that your app logs users out or enable
production notifications.

1. In **Security notifications**, select **Test endpoint**.
2. Enter any `sub` value in **Test user ID** and select **Send test**.
3. Confirm your endpoint returns `200` or `204`.

Test notifications automatically add `test-` to the `sub` value. For example,
`user-123` becomes `test-user-123`. To test logout for an existing user, validate
the Logout Token, then remove the leading `test-` from the received `sub` before
looking up the user and ending their sessions. Only remove this prefix when
processing test notifications.