# DotSoundBackend Private Core Dependency Policy

## Local Development

Use path dependency for fast iteration:

```toml
dotsound-private-core = { path = "../DotSoundPrivateCore", develop = true }
```

## CI/Production

Pin exact tag or commit:

```toml
dotsound-private-core = { git = "ssh://git@github.com/<owner>/DotSoundPrivateCore.git", tag = "v0.1.0" }
```

## Rules

- No floating references to `main` or `master`.
- Every upgrade requires changelog review and contract verification.

