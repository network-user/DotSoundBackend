# DotSound Legal Package

Status: pre-release legal alignment for a source-available engineering
showcase.

This file is a public-safe index for legal and compliance documents in
the repository. It is not legal advice and it does not replace review by
a qualified lawyer before a real public product launch.

## Publication Scope

This repository may be visible for code reading and architecture review.
It is not an open-source license grant and it is not a production
deployment guide. The license and `NOTICE` define the allowed use.

Operational details, personal data of the operator, private deployment
notes, and internal legal plans are intentionally excluded from this
public-facing index.

## Product Assumptions

- DotSound is a music platform with user-generated content.
- UGC uploads can store audio in project-controlled infrastructure.
  Public texts must not claim that the service never stores audio.
- External-source tracks, licensed tracks, and UGC tracks are treated as
  separate product/legal modes.
- Own playback over third-party stream URLs is treated as high-risk and
  requires legal review before public launch or scale-up.
- Chat/comment functionality is treated as a regulated feature and must
  be reviewed separately before it is enabled publicly.

## Documents

- `docs/legal/USER_AGREEMENT.md` — draft user agreement.
- `docs/legal/PRIVACY_POLICY.md` — draft privacy policy.
- `docs/legal/COPYRIGHT_POLICY.md` — rightsholder notice and takedown
  flow.
- `docs/legal/UPLOAD_RULES.md` — upload rules and UGC restrictions.
- `docs/legal/LEGAL_TEXTS.md` — canonical product text for upload,
  complaints, legal views, and track cards.
- `docs/legal/SOURCE_TERMS_CHECKLIST.md` — checklist for external-source
  integrations before launch.

## Account And Content Deletion

Account deletion and track deletion use a soft-delete plus grace-period
model. After the grace period, scheduled jobs remove or detach related
records and external assets according to backend lifecycle services and
private policy decisions.

Public product copy must clearly distinguish between deleting an account,
deleting uploaded content, and removing local device caches.

## Local Offline Cache

The Mini App can cache eligible tracks on the user's device through
browser storage. Backend and PrivateCore decide whether a response is
eligible for offline caching; the client must not cache external-source
or third-party stream content without an explicit allow signal.

## External Processing

Any optional third-party processing tier for uploaded audio must remain
disabled by default until:

1. The data transfer is disclosed in the privacy policy and user
   agreement.
2. User consent and subprocessors are reviewed.
3. Budget, kill-switch, and audit logging are configured.

## Before A Real Public Launch

- Replace draft legal texts with lawyer-reviewed documents.
- Publish the legal/privacy contact in product surfaces.
- Confirm personal-data processing, retention, subprocessors, and
  localization requirements.
- Review terms for every external source and keep `UGC`, `licensed`,
  and `external-source` flows distinct in code and UI.
