# SoundCloud Terms Review for DotSound

Status: internal only

Version: 2026-04-15

## Current DotSound model

At the time of this review DotSound:

- imports SoundCloud metadata into local `Track` rows;
- marks such tracks as `catalog_type = external_reference`;
- marks playback mode as `access_mode = third_party_stream`;
- does not store the external audio file in DotSound storage;
- may request a stream URL from SoundCloud and play it inside the
  DotSound player.

## Why this matters

This is not the safest `link-out only` model. It is a higher-risk MVP
mode because DotSound still creates its own playback experience over a
third-party source.

## High-risk points from prior review

Based on the previously collected SoundCloud API Terms excerpts, the
main risk areas are:

- creation of an alternative on-demand listening service;
- aggregation and streaming of SoundCloud user content in a separate
  app/service;
- persistent storage or caching of user content;
- insufficient attribution or missing backlink to the original track;
- any expansion toward ripping, copying, offline access, or source
  obfuscation.

## Current compliance direction

The current codebase reduces some risk by:

- keeping source attribution;
- storing provenance fields on `Track`;
- avoiding persistent storage of the external audio file itself;
- documenting that current playback mode is high-risk and not equivalent
  to safe `source-first`.

## Not yet solved

The following remains unresolved and must be treated as residual risk:

- whether current `third_party_stream` playback is allowed by
  SoundCloud's Terms for this exact product shape;
- whether current UI/UX still looks too much like an independent music
  service built on top of SoundCloud content;
- whether recommendation and catalog presentation create an
  unacceptable degree of aggregation.

## Pre-launch rule

If DotSound is shown publicly outside a narrow portfolio/demo context,
the project should either:

- move closer to `link-out` or official embed only; or
- complete a source-specific legal/product review and accept the
  remaining contractual risk explicitly.
