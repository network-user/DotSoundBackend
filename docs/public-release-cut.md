# Public Showcase Cut

This document defines the intended public shape of the
source-available Backend repository.

## Included

- API route wiring, schemas, models, migrations, and repositories.
- Non-sensitive service orchestration and app bootstrap.
- Frontend Mini App source.
- Public worker/API contracts.
- Design, architecture, legal draft, and boundary documentation that is
  safe for public reading.

## Excluded

- PrivateCore source and module inventory.
- Production deployment runbooks.
- Internal transition notes, agent instructions, redesign work plans, and
  archived audits.
- Operator-specific legal details and private contact data.
- Sensitive routing, policy tuning, and ranking details.
- Secret files and local environment files.

## Pre-Publish Checklist

- [x] Repository states source-available showcase scope.
- [x] PrivateCore is documented as a closed dependency.
- [x] Public docs avoid internal plans and operator-specific details.
- [x] CI does not claim a green full lint/type/test gate.
- [x] Public guardrails and secret scanning are documented.
- [ ] GitHub visibility set to Public manually for the selected public
  repositories only.
- [ ] PrivateCore remains private.
