# Claude Policy Adapter

Follow `docs/ai-boundary-policy.md` as mandatory rules.
Architecture: Telegram-style (open client + open transport + private core).

Route handlers (`api/v1/`) must not contain direct DB queries.
Business rules and security constants must come from `dotsound_private_core`.
If a requested change may cross public/private boundaries and the
intent is unclear, stop and request explicit confirmation.

## Black-box rule for PrivateCore (HARD RULE)

`dotsound_private_core` is an opaque dependency. Nothing in this
repository — code, comments, log strings, docstrings, docs, tests,
commit messages, pyproject extras names, env-var names defined by
backend — may name the internal implementation of PrivateCore.

This includes, but is not limited to: specific external providers
PrivateCore might call, specific ML or scraping libraries it might
use, model-size or model-family names, stage or tier labels that
describe the internal cascade, algorithmic technique names.

Use opaque language: "lyrics provider", "internal stage",
"audio-based fallback", "internal assets". Env vars that configure
PrivateCore must be defined and documented **only** inside PrivateCore
(its own `.env` / `.env.example`) and read there; backend must not
mention them by name. Stage labels that cross the backend↔frontend
boundary must be opaque.

If you see a leak while working on something else, fix it.

