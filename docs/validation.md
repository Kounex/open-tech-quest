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

## Account moderation and controlled late admission — 2026-11-05

Release **0.1.14**, source
[`28aac6c`](https://github.com/Kounex/open-tech-quest/commit/28aac6cc855ade7f7bf0b61436f8277f24abc7b9),
passed [release CI](https://github.com/Kounex/open-tech-quest/actions/runs/42051966151):
143 cases on each of SQLite and MariaDB, with three skips per dialect;
frontend check/build; empty-install runtime smoke; and the publication test target.
The first full run exposed one older fixture that attempted Start without an
attended assigned team. The fixture now supplies real participant attendance;
the runtime guard remains intact. Independent review found no outstanding issues.

The anonymous GHCR pull and OCI labels verified the exact tested revision.
Both initialization and runtime use:

```text
ghcr.io/kounex/open-tech-quest:0.1.14@sha256:352c1f8918052b33cf4735bd54887f8c8fc1d682c7a0c7f31ba8f48dea32d123
```

Actual disposable browser upgrade journeys covered identity-bound role changes
and deletion, captain repair, stale previews and reused account IDs; banning,
native evidence retention, wrong/correct teammate recovery, original/recovered
award timing and unbanning; and post-start self-registration/check-in followed
by reasoned admission into an existing or additional named team. Existing team
standings and clocks remained unchanged during admission. Restart preserved
native submissions, recovery evidence, attendance and memberships. Users and
Teams accessibility scans reported zero violations or incomplete checks; Users
fit a 390px viewport without document-wide overflow. Details are recorded in
[user lifecycle](user-lifecycle.md), [contribution moderation](contribution-moderation.md)
and [late admission](late-admission.md).

All 37 GitOps kustomizations passed build/schema validation; GitOps
[`f959349`](https://github.com/Kounex/ocp-gitops/commit/f95934952cb2faecf9871ac9bf44178ad524736b)
also passed [repository CI](https://github.com/Kounex/ocp-gitops/actions/runs/42053529573).
Argo reported Synced / Healthy at that revision and the deployment completed
with both containers pinned above. MariaDB/Redis remained running, all three
PVCs remained Bound and the Doppler ExternalSecret remained Ready.

Read-only authenticated production checks verified the new capabilities,
private/no-store user responses and byte-identical built frontend assets.
The saved baseline remained unchanged: draft/check-in phase, public registration,
attendance closed at generation zero, five rooms, 25 demo challenges, one native
administrator and no participants, teams or readiness records. No production
user was deleted, demoted, banned or admitted for verification. The private
SQL/uploads backup taken before this upgrade is
`/root/ocp-backups/ctfd/pre-account-moderation-late-20261105T145950Z/`.
Restore matching plugin code with the database: older code cannot interpret the
new native `quest_recovery` submission subtype.

## Attendance-first team formation — 2026-11-05

Release **0.1.15**, source
[`6592c67`](https://github.com/Kounex/open-tech-quest/commit/6592c67a8aca06980fedbd82fe7edd380d4d57e9),
passed [release CI](https://github.com/Kounex/open-tech-quest/actions/runs/42070881719):
150 cases on each database, with three skips per dialect; frontend check/build;
runtime empty-install smoke; and publication tests. The first full run caught
one older fixture inserting duplicate team-name metadata after an organizer
correction. It now reuses the actual row and asserts the administrator's
provenance; runtime behavior was unchanged. Independent review has no outstanding
findings. See [attendance-first acceptance](attendance-first.md) for actual
registration/attendance/grouping, both naming modes, event starts, native shared
solve, restart, accessibility and mobile verification.

The anonymous GHCR pull and OCI labels verified the exact tested revision.
Initialization and runtime are both pinned to:

```text
ghcr.io/kounex/open-tech-quest:0.1.15@sha256:7327e4279f8989129ba3c375911ec8c60d45b291791620e09cf56caf9d4605e2
```

All 37 GitOps kustomizations passed build/schema validation. GitOps
[`083e903`](https://github.com/Kounex/ocp-gitops/commit/083e90376ce0ab8df00b6915049b2783acad3c43)
passed [repository CI](https://github.com/Kounex/ocp-gitops/actions/runs/42072726292).
Argo reported Synced / Healthy at that revision and deployment rollout completed.
All three PVCs remained Bound and the Doppler ExternalSecret remained Ready.

Read-only authenticated checks confirmed `allow_team_naming:false`, unchanged
event/content/account/attendance/team data and byte-identical built frontend
assets. An administrator explicitly closed registration before the rollout;
the audit timestamp established this and that setting was preserved. Production
remains draft/check-in with five rooms, 25 demo challenges, attendance closed at
generation zero, one native administrator and no participants, teams or readiness
records. No production grouping or naming actions were used for QA.
Private pre-upgrade SQL/uploads backup:
`/root/ocp-backups/ctfd/pre-attendance-first-20261105T163847Z/`.
