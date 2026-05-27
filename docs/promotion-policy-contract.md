# Promotion Policy Boundary

Backend owns the public transport and storage for editorial promotions.
PrivateCore owns the ranking and mixing decisions.

## Backend Responsibilities

- Store promotion records and event rows.
- Expose admin CRUD for choosing what can be promoted.
- Filter unavailable entities through ordinary DB state.
- Record impressions and clicks.
- Call the private policy adapter when a surface needs ordering or
  feed mixing decisions.
- Fall back to pass-through behavior when the private policy is not
  available in a showcase checkout.

## PrivateCore Responsibilities

- Decide ordering, spacing, dedupe, diversification, fatigue, and
  personalization.
- Own all scoring, ranking, and frequency-cap decisions.
- Keep thresholds, weights, and tie-break details outside the public
  repository.

## Public Contract Shape

The public Backend adapter passes plain promotion views and user context
into PrivateCore and receives an ordered or mixed list back. Backend
does not inspect the reasoning behind that decision.

## Non-Disclosure Rule

Do not publish sensitive ranking, routing, or private tuning details in
this repository.
