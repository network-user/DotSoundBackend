# Admin Onboarding

This public-safe note documents the product shape of admin onboarding
without exposing production bootstrap commands or operator procedures.

## Flow

1. A trusted existing user is marked as an administrator through an
   internal bootstrap procedure.
2. The admin opens the admin panel.
3. Backend requires TOTP setup, device binding, and an admin-scoped
   session before privileged sections become available.
4. Granular capabilities determine which admin sections are visible and
   which endpoints can be called.
5. Sensitive capability grants and destructive actions require step-up
   authentication and are written to the audit log.

## Recovery

Recovery paths exist for lost authenticators, expired sessions, trusted
device changes, and lockouts. The exact production recovery procedure is
kept outside the public showcase repository.

## Boundary

Do not publish:

- bootstrap SQL for the first administrator;
- generated secret commands;
- production admin slugs;
- real alert chat IDs;
- operator-specific recovery instructions.
