# Product and implementation contract

## Intent

Open Tech Quest is the team challenge experience for the Red Hat Hands-On
Day in Darmstadt. Each person logs into their own account, teams share
progress, and teammates may work in different rooms simultaneously.
The five default rooms are OpenShift, Ansible, RHEL, Security, and AI. Room
managers can rename them, add custom rooms and safely remove unused rooms.
See [maintainers.md](maintainers.md) for staff permissions and authoring.

The participant experience replaces the flat challenge board. Each room
contains an ordered chain of native CTFd challenges. CTFd Requirements
enforce that chain; the plugin additionally enforces room start and asset
access. Room managers author standard flag challenges in Organize; native
administration remains available to full administrators.

## Design direction

- Product: a team challenge event across five Red Hat topic rooms.
- Character: approachable, focused, competitive.
- World: Open Tech Quest's actual indigo/white/red/cyan identity, Red Hat
  Display and Text typography, technical learning and collaboration.
- Moments: individually composed room artwork and the shared progress map.
- Signature: the same ordered challenge path across rooms and standings.

Use neutral white/gray app surfaces, an indigo event masthead, red actions,
and cyan for progression. Use 4px spacing, type weights 400/500 with 600
sparingly, tabular figures, sentence case, accessible focus and contrast.
No gradients, glow, invented product logos, emoji decorations, or fake stats.
Use approved/public product assets with provenance and stable local URLs.
Private catalogue source archives and session credentials stay out of Git.

Each room gets its own transparent product-topic illustration and asset
slots. OpenShift shows container orchestration; Ansible shows playbook fan-out;
RHEL shows the Linux terminal and services; Security shows protected workloads;
AI shows model inference. Crisp technical editorial artwork shares a red,
charcoal and cyan palette. Exact official product icons and names
appear in the card title or room heading only. Artwork has no duplicate
identity strip; product marks are never approximated by image generation. PNG and WebP
exports must retain genuine alpha transparency, and their containers have no
background fill. Theme changes do not change room identity.
Theme asset URLs are optional: a deliberate typography/content composition
must work before an organizer supplies artwork; never show placeholder boxes.

Motion is part of the product: navigation underline transitions, restrained
room entry, newly available steps, solve feedback and completion. Use one
ease-out curve, short 120–220ms feedback, at most 300–400ms transitions.
Respect prefers-reduced-motion. No looping decoration, layout animation,
scroll parallax, or constantly shuffling projector rows.

## Timing and awards

Defaults, visible to admins before opening the event:

- Room clock: explicit Start room, recorded atomically server-side before
  content release. One start per team/room; it continues across navigation,
  devices, and work in another room. Players cannot pause/reset it.
- Room ranking: longest consecutively solved prefix descending, then active
  elapsed time from room start to that prefix's last solve ascending.
  A completed room outranks all incomplete ones. No solves means no prize
  eligibility, not a zero-time winner. Genuine ties share a rank.
- Overall ranking: distinct mapped challenge solves descending, then active
  elapsed event time from the common event start to the last qualifying
  solve ascending. Do not sum overlapping room times. Support configurable
  team-first-room origin as an explicit alternative before the event opens.
- Room origin may alternatively be the common event start, configured before
  opening. Defaults are assumptions from the design discussion, not hidden.
- Clocks exclude organizer-recorded pause intervals; a boolean CTFd pause
  alone is not an adequate historical record. Store all timestamps in UTC.
- Only solves at/before the closing cutoff count. The time at a milestone
  does not keep increasing while a team is stuck. No client-supplied time.
- Excluded teams are omitted from prizes/public standings. Corrections need
  an admin reason and audit entry, without altering original CTFd timestamps.
- Publishing results stores a final snapshot. Subsequent database edits do
  not silently change announced winners. Unpublish/reopen requires explicit
  organizer action and audit trail; it must never be an accidental reset.

## Lifecycle and configuration

Phases: draft -> live <-> paused -> closed -> published.
Start records the event origin (or uses configured scheduled start); close
records cutoff. Prize policy, room membership/order and allocation are
editable only in draft. Presentation/theme fields may change independently.

Default install creates five empty room records and draft event settings.
It must not populate real challenges or flags. User mode is teams when the
plugin is enabled on a fresh instance; refuse silent conversion if existing
individual solves would change ownership. Preserve existing admin accounts.

An explicit organizer demo load may populate otherwise unmapped rooms in
draft: 25 self-contained sample challenges, free hints and Markdown room
introductions. Durable batch ownership records exactly what was created and
the prior room copy. Removal preserves unrelated real content and later
introduction edits, refuses activity-history deletion, and is transactional.
A loaded demo blocks competition start; organizers preview it in draft.
No participants, teams or progress are generated by this feature.

Participant onboarding uses personal native CTFd accounts, a persisted team-size
limit (default five), random provisional allocation and personal readiness.
Organizers close check-in, review a deterministic attendance optimization, apply
it, then let any member claim the final unique team name once. Finalization locks
the roster before competition start. Late arrivals remain visible for reasoned
manual placement before finalization. Readiness never starts a competition clock.
Attendance capture is a separate, default-off organizer window. Signed-in
participants are prompted automatically when it opens; early registration does
not record presence. New confirmation is rejected while capture is closed.
See [attendance-window.md](attendance-window.md) for prompting, migration and
lifecycle rules.
See [onboarding.md](onboarding.md) for the complete lifecycle, additive API seam,
privacy and stale-preview/concurrency guarantees. Native self-service team routes
and native administrator writes cannot bypass the roster lifecycle.

Public account registration is an independent organizer control backed by
CTFd's native registration setting. Closing it blocks new self-signups,
including an already-loaded form; existing accounts still sign in and confirm
attendance. Native HTTP configuration writes cannot bypass the audited quest
control. See [registration.md](registration.md).

## API contract

All endpoints use `/api/v1/quest`. JSON responses follow CTFd's
`{"success": true, "data": ...}` envelope. Errors return a human-readable
`error` string and appropriate 400/401/403/404/409 status. Use the existing
session and CTFd CSRF checks. No administrator token in the browser.

### Common shapes

`Event`: `name`, `status`, `start_at`, `end_at`, `paused_at`,
`rosters_release_at`, `room_clock` (explicit/event), `overall_clock`
(event/team), `server_now`, `results_published`.

`Viewer`: `authenticated`, `id`, `name`, `team_id`, `team_name`, `admin`,
`role` (guest/participant/maintainer/administrator), `can_manage_rooms`,
`can_manage_users`. Maintainers are staff, excluded from participant onboarding.

`Room`: `id`, `slug`, `name`, `subtitle`, `description`, `position`,
`theme` (accent, logo_url, hero_url, layout), `steps`, `progress`.
`Step`: `id`, `title`, `position`, `state` (locked/available/solved),
`solved_at`; no description, files, answer or hint in locked metadata.
`Progress`: `solved`, `total`, `started_at`, `elapsed_ms`,
`milestone_elapsed_ms`, `status` (not_started/active/complete).

`Standings`: `event`, `rooms`, `teams`, `room_leaders`, `as_of`.
`StandingTeam`: `id`, `name`, `rank`, `total`, `overall_elapsed_ms`,
`room_progress` (room_id, solved, total, milestone_elapsed_ms, rank, complete).
Public standings expose team display names and aggregate results only.

### Participant and projector

- GET `/bootstrap`: `{event, viewer, rooms, registration}`; safe lobby metadata for guests.
- GET `/rooms`: Room array for the current viewer.
- GET `/rooms/<slug>`: Room for current viewer.
- POST `/rooms/<slug>/start`: Room; idempotent for teammates, requires team,
  live event and CTF time. Start response must not race first content access.
- GET `/standings`: Standings, sanitized for public/projector use; before
  roster release omit private team information. Same ranking as admin view.
- GET `/session`: Viewer (optional alias of bootstrap viewer).
- Native `/api/v1/challenges/<id>` and `/attempt`, hints and unlock endpoints
  remain the source of challenge content/submission behavior. Apply plugin
  guards to mapped challenges, hint reads/unlocks and file downloads.

### Administrator

- GET `/admin/state`: `{event, rooms, available_challenges, teams,
  participants, audit, standings, projector, registration, onboarding, demo}`. Admin-only participants may
  include email; never include passwords, tokens, raw submitted flags.
- PATCH `/admin/event`: event configuration fields; validate times/policies.
- PATCH `/admin/registration`: `{enabled:boolean}`; control native public signup
  in any event phase. Both bootstrap and admin state include
  `registration:{enabled:boolean}` from the authoritative native setting.
- POST `/admin/event/action`: `{action: start|pause|resume|close|publish}`.
- PATCH `/admin/rooms/<slug>`: room metadata/theme and `challenge_ids`.
  Validate IDs, duplicates, cross-room reuse. Update native Requirements,
  next_id and position consistently; topology immutable after draft.
- POST `/admin/teams/allocate`: `{team_size, preview:true}` -> proposed
  `{groups:[{name,user_ids}]}`; commit with `{preview:false,groups:[...]}`.
  Validate the complete current eligible population at commit time.
- PATCH `/admin/teams/<id>`: `{name, excluded, reason}`; CTFd team rename,
  prize exclusion with reason. Membership updates only in draft.
- PATCH `/admin/projector`: `{view: overview|room|overall|awards, room_slug}`.
- GET `/projector`: public display configuration, no admin capability.
- GET `/admin/export`: CSV of per-room/overall award standings.
- POST `/admin/corrections`: `{team_id,room_slug,adjustment_ms,reason}`;
  bounded documented adjustments, audit and reject after publication.
- POST `/admin/demo`: `{action: load|unload}` -> demo status. Admin state
  includes `demo: {active,challenge_count,can_load,can_unload,reason}` with
  server-derived availability and an actionable disabled reason.

The frontend treats HTTP errors as errors even if a native endpoint uses
`success:true`. Submit status must distinguish correct, incorrect, already
solved, ratelimited, paused, authentication_required and partial.

## Application shell

Serve built assets from plugin static paths and a Jinja shell at `/quest`
and `/quest/<path>`. Inject only CSRF nonce and safe viewer bootstrap into
`window.QUEST_INIT`. SPA URLs: `/quest`, `/quest/rooms/<slug>`,
`/quest/standings`, `/quest/stage`, `/quest/admin`.
Redirect the native index and participant challenge board to `/quest`.
Keep native `/admin`, `/login`, `/register`, `/settings` and team management
reachable as appropriate, with event styling via a small supported theme or
shell styles. Never bypass native login/password handling.

## Runtime and verification

Build Vite assets and copy plugin into pinned `ctfd/ctfd:3.8.9` image.
Plugin schema uses CTFd's plugin migration support; persists in MariaDB.
Redis holds cache, not authoritative starts or ranking history.
Provide a runnable development setup with disposable SQLite or Compose.

Required integration coverage: two users sharing a team; other-team
isolation; early/locked challenge and known attachment URL denial; sequential
solves; duplicate teammate submissions; idempotent concurrent starts;
partial-room and total rankings; ties; pause/cutoff; final snapshot;
admin/CSRF/asset-URL validation; no demo data in production. Test DB behavior
on MariaDB in CI in addition to fast ranking unit tests.

Browser checks: lobby, individual room compositions, answer feedback,
admin lifecycle/allocation/room editing, stage at 50 named teams at 1080p,
mobile/keyboard/reduced motion. Test multiple device sessions and reconnects.
Run an isolated load check with 50 teams before claiming event capacity.
