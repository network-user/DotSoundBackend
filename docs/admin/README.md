# Admin Panel

This public-safe overview describes the admin panel as an engineering
showcase. It intentionally omits production runbooks, secret generation,
deployment topology, sensitive policy values, and operator-specific
procedures.

## Scope

- Backend routes live under the admin API namespace.
- Frontend admin code is split from the main Mini App bundle.
- Admin access uses a separate admin session, granular capabilities,
  audit logging, and step-up authentication for sensitive actions.
- Observability screens can read metrics, logs, task state, and worker
  health when the corresponding infrastructure is configured.

## Sections

| Section | Purpose |
|---|---|
| Dashboard | High-level service status |
| Users | User lookup, moderation, capability management |
| Tracks | Track moderation and maintenance |
| Complaints | User complaints and rightsholder workflow |
| Artists | Artist metadata operations |
| Compute | Pull-based worker registration and job routing |
| Tasks | Background task visibility and controlled triggers |
| Logs | Runtime log inspection |
| Metrics | Metrics overview |
| Audit | Admin action history |
| Security | Lockouts, devices, and security events |
| Settings | Controlled system settings |

## Security Shape

- Admin endpoints require admin-scoped authentication.
- Capabilities are checked per endpoint.
- Sensitive operations require a fresh step-up challenge.
- State-changing operations are audited.
- Critical events can be forwarded through the Bot integration.
- PrivateCore owns sensitive policy decisions; Backend only applies
  those decisions to infrastructure state.

## Showcase Boundary

The public repository keeps the architecture and code structure visible,
but does not publish:

- first-admin bootstrap commands;
- production URLs or deployment topology;
- secret names beyond public `.env.example` documentation;
- private lockout/session thresholds;
- internal alert chat IDs or operational runbooks.
