# Admin Panel — Acceptance Testing Checklist

Run this checklist locally before tagging a release that touches
admin code. Every item maps to one or more automated tests under
`tests/admin/` and `tests/observability/`; the checklist exists so
a human verifies they fire end-to-end against a real stack.

## Prerequisites

```bash
make migrate
make admin-dev          # backend + infra
make observability-up   # optional but exercises Loki/Prometheus probes
cd frontend && npm run dev
```

A regular user with `is_admin=true` ready
(see [onboarding.md](onboarding.md)).

## A. Onboarding & first login

- [ ] First-time admin sees the QR + secret screen.
- [ ] Wrong code is rejected with a friendly error.
- [ ] Correct code lands on the dashboard with backup codes shown
      once.
- [ ] After reload, `/admin` shows the dashboard, not the QR.

## B. Login from a known device

- [ ] After logout, opening `/admin` shows the TOTP-only screen.
- [ ] Correct code grants a 15-minute session.
- [ ] Refresh succeeds when access token expires (or after 15 min
      manual wait); admin stays signed in.

## C. New device approval

- [ ] Opening the app from a different browser triggers the
      device-approval flow.
- [ ] Email code arrives (check `MailHog` if used, or Resend
      dashboard).
- [ ] Telegram bot receives an alert about the pending device.
- [ ] After confirming `email_code + TOTP`, dashboard loads.

## D. Step-up gating

- [ ] Trying to ban a user without step-up shows the StepUpDialog.
- [ ] Wrong step-up code is rejected.
- [ ] Correct code allows the action; second action within 5 min
      goes through without the dialog.
- [ ] After 5 min, the dialog reappears.

## E. Brute-force lockout

- [ ] Five wrong TOTP codes lock the account.
- [ ] Telegram alert fires for the lockout.
- [ ] A second admin with `security.release_lockout` can release
      the lock through the UI.

## F. Audit log

- [ ] Visiting **Audit** shows recent actions with `user_id`,
      `action`, `target_type/id`, `ip`, `meta`.
- [ ] Sensitive fields (codes, tokens, passwords) are redacted in
      `meta`.
- [ ] CSV export downloads after a step-up TOTP is provided.

## G. Live logs (requires Loki)

- [ ] Logs page shows entries within ~5 seconds of a backend log
      line being emitted.
- [ ] `level` and `container` filters narrow the stream.
- [ ] Pause/resume buttons stop and restart polling.

## H. Container health

- [ ] Containers page shows green/yellow/red pills matching
      `docker ps`.
- [ ] Stopping a non-critical container (e.g. `loki`) flips its
      pill to red within ~10 seconds.

## I. Feature flags

- [ ] Creating a flag through the Settings UI requires step-up.
- [ ] Toggling the flag on/off works and is reflected in the
      table.
- [ ] The flag value is visible via
      `GET /api/v1/admin/system/feature-flags`.

## J. Bundle hygiene (security)

- [ ] `npm run build` exits 0 without `[bundle-hygiene]` errors.
- [ ] `[admin-bundle] check passed` is in the build log.
- [ ] Manually fetching `mini_app/assets/secure/admin-bundle.js`
      without the signed `?t=...&u=...` returns **404**.

## K. CSRF

- [ ] Removing the `admin_csrf` cookie before a `POST` results in
      `403`.
- [ ] Mismatched header/cookie also results in `403`.

## L. Observability probes

- [ ] `/api/v1/health/deep` lists `db`, `redis`, `s3`, `taskiq`,
      `loki`, `prometheus` (last two only when configured).
- [ ] `/metrics` is reachable from `127.0.0.1` only.
- [ ] Grafana dashboard "DotSound Backend Overview" loads with
      live RPS / error / latency panels.

## M. Logout

- [ ] Sign-out clears the refresh cookie and the in-memory token.
- [ ] Reusing the old refresh cookie returns `401`.
