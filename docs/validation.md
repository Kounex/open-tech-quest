# Release verification — 2026-11-03

Open Tech Quest **0.1.2**, source `2373077`, was published by
[CI run 41633395583](https://github.com/Kounex/open-tech-quest/actions/runs/41633395583).
The public GHCR image was pulled anonymously before deployment. Its index digest:

```text
sha256:d2a5251b0a0c743d07736c3ea732060db9191d51b8a3b17af1e7eaa90dc1ab13
```

## Automated and isolated verification

- MariaDB: all 24 tests passed, including production-dialect migrations,
  microsecond timing, concurrent team starts and lifecycle serialization.
- SQLite: 22 passed, with the two MariaDB-specific concurrency cases skipped.
- Frontend TypeScript checks, formatting and production build passed.
- The actual runtime image started successfully with five empty draft rooms;
  no demo fixture is included in that image.
- Two independent browser sessions shared a team's solves and room start.
  Correct answers unlocked the next step on both devices; future content,
  hints and downloads remained protected through native API paths.
- Organizer allocation, room configuration, pause controls, hint preview and
  projector controls were exercised in a disposable event.
- Fifty named teams fit the projector overview at 1920×1080 without scrolling.
  A 390px participant viewport had no horizontal overflow or broken images.
- Reduced-motion preference disabled the navigation underline transition.
- Fifty-team standings tests bounded the common projection to 12 SQL queries.
  On the local disposable MariaDB setup, 60 summary requests at concurrency
  20 all succeeded, with p95 latency 193ms. This is a development measurement,
  not an event-network latency guarantee.

## Live rollout verification

GitOps commit `ebe3ba0` in
[Kounex/ocp-gitops](https://github.com/Kounex/ocp-gitops/commit/ebe3ba013e106c9b977489b2e1cdc19aaa5165b0)
pins the same image in initialization and runtime. Every repository
kustomization passed build/schema checks locally and in GitHub Actions.
Argo reported **Synced / Healthy** after rollout; MariaDB, Redis, all three
PVCs and the Doppler ExternalSecret remained healthy.

The live HTTPS root redirected to `/quest`; compiled frontend/branding assets,
registration, native authoring and organizer pages loaded. Existing organizer
credentials authenticated successfully. Session cookies were Secure and
HttpOnly, and anonymous organizer API access was denied. A read-only organizer
check confirmed draft status, all five rooms, and zero event challenges,
teams or participants. No event was started and no demo data was inserted.

The live lobby's automated axe WCAG A/AA scan reported zero violations. One
contrast item for a decorative non-text dot required manual review. These
checks do not replace keyboard/assistive-technology testing with participants
or readability checks on the actual venue projector.

## Organizer preparation

Follow [operations](operations.md) to author the real challenges, choose final
room assets, configure timing/roster release, allocate teams and rehearse the
event. Default room timing starts explicitly when a team enters; overall
timing uses the common event start. Pauses are excluded, partial rooms rank by
last qualifying milestone, and exact ties remain shared.

A private SQL/uploads backup was taken before migration. Scheduled off-cluster
backups and SMTP still need event-environment configuration before relying on
recovery or password-reset mail. No credentials or participant data are stored
in this repository.
