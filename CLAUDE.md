# Claude Policy Adapter

Follow `docs/ai-boundary-policy.md` as mandatory rules.
Architecture: Telegram-style (open client + open transport + private core).

Route handlers (`api/v1/`) must not contain direct DB queries.
Business rules and security constants must come from `dotsound_private_core`.
If a requested change may cross public/private boundaries and the
intent is unclear, stop and request explicit confirmation.

