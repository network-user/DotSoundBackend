# Admin Panel — Threat Model & Security Layers

## Layered defense

The admin panel uses a defense-in-depth approach. An attacker has
to defeat every layer below to take over the admin surface.

1. **Public client gating.** The admin code chunk is only loaded
   for users whose backend manifest has `adminBundleUrl` filled.
   Non-admins receive 404 from
   [`SecureStaticMiddleware`](../../app/middlewares/secure_static.py)
   when they try to fetch `mini_app/assets/secure/admin-bundle.js`.
2. **HMAC bundle URL.** Even authorized admins see a URL signed
   with `JWT_SECRET` and bound to their `user_id` + expiry.
3. **CSRF (double-submit).** Every state-changing request to
   `/api/v1/admin/*` must carry both the `admin_csrf` cookie and a
   matching `X-Admin-CSRF` header. Cookie has `SameSite=Strict`
   and (in production) `Secure`.
4. **Strict CSP** on every admin response (see
   [`AdminSecurityMiddleware`](../../app/middlewares/admin_security.py)):
   `default-src 'self'; script-src 'self'; frame-ancestors 'none'`,
   `Referrer-Policy: no-referrer`, `X-Frame-Options: DENY`,
   `Permissions-Policy` blocks camera/mic/geo, and HSTS preload in
   production.
5. **Aggressive rate-limit.** `/auth/login`, `/auth/init/*`,
   `/auth/refresh`, `/auth/devices/*` are all capped via
   `slowapi+Redis` (5/min for login, 3/min for init).
6. **Admin TOTP.** A separate secret from the email 2FA secret,
   encrypted at rest with `TOTP_ENCRYPTION_KEY`. Five failed
   attempts within `ADMIN_LOGIN_ATTEMPT_WINDOW_SECONDS` lock the
   account for `ADMIN_LOCKOUT_TTL_SECONDS`.
7. **Device binding.** Login from a new fingerprint requires
   `email_code + TOTP` confirmation through the
   `/auth/devices/confirm` flow. Trust expires after
   `ADMIN_DEVICE_TRUST_TTL_SECONDS`.
8. **Short admin sessions.** Access JWT is `scope=admin` and lives
   only `ADMIN_SESSION_TTL_SECONDS` (15 min). Refresh is in an
   `httpOnly`, `Secure`, `SameSite=Strict` cookie scoped to
   `/api/v1/admin/auth` and rotated on every refresh.
9. **Step-up auth.** All "dangerous actions"
   (`ADMIN_DANGEROUS_ACTIONS`) need a fresh TOTP code via
   `/auth/step-up`. The marker lives in Redis for
   `ADMIN_STEP_UP_TTL_SECONDS` (3-5 min) and is keyed per
   `(user_id, action)`.
10. **Granular capabilities.** Even with `is_admin=true`, every
    sensitive endpoint is gated by `require_capability(name)` on
    top of `require_admin_session`.
11. **Per-action audit log.** Every state-changing call writes a
    row to `admin_actions_log` with `user_id`, `action`,
    `target_type/id`, `ip`, `meta` (PII redacted).
12. **Real-time Telegram alerts.** Critical events are pushed to
    a dedicated chat via DotSoundBot (see contract below).
13. **PrivateCore boundaries.** All TTLs, thresholds and decision
    functions live in
    `dotsound_private_core.services.admin_security_policy`.
    Backend never hardcodes these values; the entire admin flow
    pulls them from PrivateCore.

## Threat scenarios

| Threat | Mitigation |
|---|---|
| Stolen user JWT | `scope=admin` is required on the admin path; user JWT is `scope=user`. |
| Stolen admin JWT | Short TTL (15 min); session can be revoked from Settings; Telegram alert on new device. |
| Session hijack via XSS | Strict CSP; `script-src 'self'` (no inline). |
| CSRF | Double-submit cookie/header on every mutating call. |
| Brute-force TOTP | Rate-limit + lockout + Telegram alert. |
| New-device takeover | Email-code + fresh TOTP both required. |
| Privilege escalation by an admin | Capability checks on every endpoint + audit log + step-up + Telegram alert on grant/revoke. |
| Bundle leak to non-admins | Admin chunk is `mini_app/assets/secure/*`, signed URL, 404 for everyone else. |
| Log/PII leak | `_sentry_pii_filter`, `redact_admin_payload`, `ADMIN_PII_KEYS` redact lists. |
| Container compromise of `backend` | Docker socket mounted read-only, no shell endpoint, all "run task" calls go through whitelist + step-up. |

## Telegram alert contract (Backend → Bot)

Backend calls the bot's internal HTTP endpoint:

```
POST {BOT_INTERNAL_URL}/internal/admin-alert
Headers:
  X-Internal-Secret: {BOT_INTERNAL_SECRET}
  Content-Type: application/json
Body:
  {
    "chat_id": "<ADMIN_TELEGRAM_ALERT_CHAT_ID>",
    "event_type": "new_device_login" | "lockout"
                  | "admin_role_granted"
                  | "admin_role_revoked"
                  | "admin_capability_granted"
                  | "user_banned"
                  | ...,
    "severity": "info" | "warning" | "critical",
    "title": "...",
    "details": "...",
    "user_id": int | null,
    "ip": str | null,
    "ua": str | null,
    "ts": ISO8601
  }
```

The bot is expected to:

1. Validate `X-Internal-Secret` (constant-time compare).
2. Check `chat_id` against an allowlist (the admin chat).
3. Forward as a Markdown message to the chat.
4. Never echo the secret back; never log the secret.

Backend never knows the chat token; the bot never knows the
admin's TOTP secret. Communication uses the existing internal
secret machinery (`BOT_INTERNAL_SECRET`).

## What is **not** implemented yet

- mTLS at reverse proxy (planned via optional
  `docs/admin/nginx-example.conf`).
- WebAuthn/Passkey as a second factor.
- Hardware-backed TOTP (e.g. YubiKey HOTP).

These remain on the roadmap and are listed in `TODO.md` under
"Admin Panel".
