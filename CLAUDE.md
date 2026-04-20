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

### Source attribution exceptions (narrow)

See `docs/ai-boundary-policy.md` → "Source Attribution Exception".
Three explicitly authorized exceptions permit naming an external
provider:

1. Artist enrichment — `source_profiles[].source_name`, `source_page_url`.
2. Lyrics provider attribution — user-facing `source_name` in the
   lyrics panel, and a feature-flag env-var name (e.g.
   `LYRICS_PROVIDER_NAME`) read by the backend adapter only to
   forward to PrivateCore as a selector.
3. Track-info provider attribution — same pattern as (2) for the
   track-info panel.

These exceptions permit **public labels and env-flag names only**.
Internal stage names, scoring weights, fallback ordering, rate
limits, prompts, and any other pipeline internals remain strictly
opaque and live inside PrivateCore.

## Secrets & .env (HARD RULE)

`.env` and other secret files (see
`.cursor/rules/secrets-and-env.mdc` for the full list) are
**off-limits** to the agent unless the user explicitly grants
per-session, per-file permission.

The agent MUST NOT:
- read, search, write, patch, restore, copy, delete, or otherwise
  touch any secret file;
- print or quote contents of secret files anywhere
  (chat replies, commit messages, logs, PR descriptions,
  subagent prompts, terminal output);
- pipe secret files into external tools that would surface them.

Allowed without asking:
- `*.example`, `*.sample`, `*.template` env templates;
- talking about variable **names** in the abstract;
- referencing secret files by **path** in config (e.g. listing
  `env_file: - .env` in `docker-compose.yml`).

If a value is needed, the agent MUST stop and ask the user to
either paste the value into chat or grant explicit permission to
read a specific file. Permission does not carry over between
sessions or files.

