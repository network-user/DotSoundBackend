# Bootstrapping the first admin

The admin panel uses a per-user TOTP plus device binding: the
backend will not let you do anything until both are set up. Here's
how to bring the very first admin online from a fresh database.

## 0. Prerequisites

- Backend running and reachable on port 8000.
- Frontend either running in dev (`npm run dev`) or built into
  `app/static/mini_app/` and served by FastAPI.
- A regular user account already exists (created via Telegram or
  email magic-link login).

## 1. Generate fresh secrets in `.env`

```bash
python -c "import secrets;print('ADMIN_JWT_SECRET=' + secrets.token_urlsafe(64))"
python -c "import secrets;print('ADMIN_CSRF_SECRET=' + secrets.token_urlsafe(32))"
python -c "import base64,os;print('TOTP_ENCRYPTION_KEY=' + base64.b64encode(os.urandom(32)).decode())"
```

(Re-using the email-2FA `TOTP_ENCRYPTION_KEY` is OK; the admin
secret is encrypted with the same key but stored in a different
column.)

## 2. Apply migrations

```bash
make migrate
```

Migration `0038_add_admin_auth.py` adds the four columns on
`users` and the three new tables (`admin_devices`,
`admin_sessions`, `admin_login_attempts`).

## 3. Set `is_admin=true` and grant the bootstrap capabilities

Connect to PostgreSQL and pick the user that should become the
first admin (use email or Telegram ID to identify):

```sql
-- Replace <USER_ID> with the actual id from the users table.
UPDATE users SET is_admin = true WHERE id = <USER_ID>;

INSERT INTO admin_capabilities (user_id, capability, granted_by, granted_at)
VALUES
  (<USER_ID>, 'settings.manage', <USER_ID>, NOW()),
  (<USER_ID>, 'users.manage', <USER_ID>, NOW()),
  (<USER_ID>, 'users.grant_admin', <USER_ID>, NOW()),
  (<USER_ID>, 'users.grant_capability', <USER_ID>, NOW()),
  (<USER_ID>, 'users.ban', <USER_ID>, NOW()),
  (<USER_ID>, 'tracks.manage', <USER_ID>, NOW()),
  (<USER_ID>, 'tracks.delete', <USER_ID>, NOW()),
  (<USER_ID>, 'complaints.moderate', <USER_ID>, NOW()),
  (<USER_ID>, 'audio_compute.manage', <USER_ID>, NOW()),
  (<USER_ID>, 'audio_compute.view_audit', <USER_ID>, NOW()),
  (<USER_ID>, 'metrics.view', <USER_ID>, NOW()),
  (<USER_ID>, 'logs.view', <USER_ID>, NOW()),
  (<USER_ID>, 'containers.view', <USER_ID>, NOW()),
  (<USER_ID>, 'tasks.manage', <USER_ID>, NOW()),
  (<USER_ID>, 'tasks.run', <USER_ID>, NOW()),
  (<USER_ID>, 'security.view', <USER_ID>, NOW()),
  (<USER_ID>, 'security.release_lockout', <USER_ID>, NOW()),
  (<USER_ID>, 'feature_flags.manage', <USER_ID>, NOW()),
  (<USER_ID>, 'audit.view', <USER_ID>, NOW()),
  (<USER_ID>, 'audit.export', <USER_ID>, NOW());
```

## 4. Sign in to the regular Mini App

Open `/mini_app/` and authenticate with your existing user
credentials. Make sure you can play tracks etc. — the regular
session must work first.

## 5. Open `/admin`

The frontend will detect `is_admin=true` and redirect through the
onboarding flow:

1. **AdminInit** displays a QR code and asks for the 6-digit code
   from your authenticator (Google Authenticator, 1Password,
   Bitwarden, Authy — anything that speaks the standard
   `otpauth://` URI).
2. After the code matches, the backend:
   - encrypts and stores `admin_totp_secret_encrypted`,
   - flips `admin_init=true` and `admin_totp_enabled=true`,
   - creates a trusted `admin_devices` row bound to the device
     fingerprint,
   - generates **10 single-use backup codes** that are shown
     **only once** — save them somewhere safe.
3. You're redirected to `/admin` with a 15-minute admin JWT.

## 6. Smoke-test critical flows

- Hover **Settings → Trusted devices** — the new device should
  appear with `trusted` status.
- **Security → Login attempts** — your successful login should be
  visible.
- **Audit log** — your last actions should appear.
- **Containers** — should show red/green pills for every infra
  container reachable through the Docker socket.
- **Logs** — pick `service=dotsound-backend`, last 15 minutes —
  you should see live entries (requires Loki up).

## 7. Grant capabilities to other admins

Once you're in, the rest happens through the UI:

1. **Users** — find the next admin candidate.
2. Apply **grant-admin** (step-up TOTP required).
3. Apply **grant-capability** for every module they need
   (step-up TOTP required for each grant).

A Telegram alert is dispatched on every grant via the bot endpoint
described in [security.md](security.md).

## 8. Recovery scenarios

- **Lost authenticator, but backup codes saved.** Use a backup
  code instead of TOTP at sign-in via `/auth/backup-code/use`.
  After login open Settings → 2FA → Regenerate backup codes (a new
  set is shown once).
- **Lost authenticator and no backup codes.** Re-enter PostgreSQL
  and clear `admin_init`, `admin_totp_enabled`,
  `admin_totp_secret_encrypted`, `admin_backup_codes_hash` for
  your user; the next visit to `/admin` will start onboarding from
  scratch.
- **Account locked out.** Another admin with
  `security.release_lockout` can release you via Security → Locked
  admins → Release. Otherwise wait for the lockout to expire.
