# Frontend Exposure Policy

## Principle

Frontend Mini App code is public and observable by design.

## Allowed In Frontend

- User interface logic.
- Presentation state and UX behavior.
- Public API request orchestration.

## Forbidden In Frontend

- Secrets and internal service tokens.
- Privileged internal endpoint contracts.
- Risk/scoring/anti-abuse decision logic.
- Production-only administrative control paths.

## Enforcement Rules

- Security-sensitive decisions must run on backend/private core.
- Frontend must never rely on hidden security through obscurity.
- Any uncertain case must be reviewed before merge.

