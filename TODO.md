# DotSound Public Showcase TODO

This is the public-safe tracker for the source-available Backend
showcase. Internal operational backlog, incident notes, private policy
work, and release coordination live outside the public repository.

## Completed For Showcase Publication

- [x] Backend, Bot, and ComputeWorker documentation now states the
  source-available showcase scope.
- [x] The closed `DotSoundPrivateCore` dependency is documented as an
  architectural boundary, not as bundled source.
- [x] Backend `docs/` was reduced to a curated public set.
- [x] Internal transition notes, redesign work plans, deployment
  runbooks, archived legal audits, and source-specific internal reviews
  were removed from public docs.
- [x] Legal and boundary docs were rewritten to avoid operator-specific
  details and private implementation internals.
- [x] CI docs no longer claim that full lint, type, and test gates are
  green for public checkouts.
- [x] A full-history high-confidence credential pattern scan over the
  three public repositories found no matches.
- [x] Mobile glass contrast improved for mini-player and track-card
  sheet readability.

## Remaining Before Changing Repository Visibility

- [ ] Run an official `gitleaks detect` pass when the binary is
  available in the environment.
- [ ] Do a final README, LICENSE, and NOTICE review in Backend, Bot, and
  ComputeWorker.
- [ ] Confirm that `DotSoundPrivateCore` stays private and has no public
  remote or stale fork.
- [ ] Confirm that public CI runs only honest guardrails for the
  showcase state.
- [ ] Set GitHub visibility manually for the selected public
  repositories only.

## Public Follow-Ups

- [x] Moderate public SEO baseline: robots/sitemap/llms, Open Graph +
  JSON-LD in Mini App shell, root file routes (nginx + FastAPI),
  runtime titles on public profile/artist/legal screens.
- [x] SEO follow-up: 1200x630 `og-default.png` + runtime `noindex`
  guard for private Mini App routes (library/upload/admin/etc.).
- [x] Guest-accessible `/legal/*` before auth: AuthScreen / onboarding
  legal links no longer bounce to the login gate.
- [ ] Add a compact architecture diagram for the public transport +
  private rules model.
- [ ] Add a short "How to read this repository" section for reviewers.
- [ ] Keep future TODO entries public-safe: no operator data, no
  production runbooks, no private policy details, and no local
  environment values.
