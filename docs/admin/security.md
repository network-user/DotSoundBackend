# Admin Panel Security Overview

This document is a public-safe overview of the admin security design.
It is not a production runbook.

## Layers

- Admin code is separated from the regular Mini App bundle.
- Admin endpoints require admin-scoped authentication.
- State-changing requests use CSRF protection.
- Capabilities gate every sensitive endpoint.
- Step-up authentication protects dangerous actions.
- Admin sessions are short-lived and refresh through a restricted path.
- Device trust is tracked separately from ordinary user login state.
- Security-relevant actions are written to audit logs.
- Critical events can be forwarded through the Bot integration.
- PrivateCore owns sensitive thresholds and decision functions.

## Threat Coverage

| Threat | Mitigation |
|---|---|
| Stolen user token | Admin scope is required separately |
| Stolen admin session | Short session lifetime and revocation |
| CSRF | Double-submit cookie/header pattern |
| XSS impact | Strict admin CSP and no inline scripts |
| Brute force | Rate limiting, lockout, and alerts |
| Privilege escalation | Capability checks, step-up, and audit log |
| Non-admin bundle access | Signed admin bundle URL and backend checks |
| Log/PII leak | Redaction before audit/log forwarding |

## Not Published Here

- Sensitive policy values and private decision details.
- Real alert destinations.
- Production reverse-proxy configuration.
- First-admin bootstrap and recovery runbooks.
- PrivateCore module internals.
