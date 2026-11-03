# Event operations

## Before participants arrive

1. Verify backups cover MariaDB and uploads, including plugin tables, and
   rehearse restoring into a disposable database. CTFd exports include plugin
   tables, but the matching plugin code/migrations must also be available.
2. Create and test every challenge in the native CTFd editor. Configure
   hints, files, flag validation and attempt limits there. Keep real answers
   in CTFd's database, never this repository or image builds.
3. In `/quest/admin`, assign challenges to rooms in the required order. A
   challenge belongs to one room. The room editor manages Requirements;
   native editing of challenge content remains available.
4. Add room logos/artwork using theme asset URLs. Selected local web assets
   can be packaged under `branding/`; source/provenance belongs in
   `branding/sources.json`. Keep raw internal catalogue archives private.
5. Configure the event name, scheduled start/end, roster-release time and
   prize clock origins. The UI uses the organizer's browser local timezone;
   persistence and API timestamps use UTC. Leaving roster release empty
   publishes assignments immediately, so set it before assigning if needed.
6. Register participants, then preview and commit random balanced allocation.
   Existing teams are preserved. Adjust names and memberships in draft;
   explain the shared room clock and prize rules to the teams.
7. Open `/quest/stage` on the projector. Choose overview, room, overall or
   awards from the organizer Projector tab. Verify 1080p output and long team
   names on the actual beamer; full-screen overview uses two panels of 25.
8. Configure SMTP before relying on password reset/email verification. It is
   an event deployment setting; no mail credentials belong in this repo.

## During the event

- Start the event through Open Tech Quest, not the native CTFd time settings.
  Native time/mode changes are guarded because they would bypass history.
- A team starts a room before viewing challenge content. Any teammate can
  do that once; the start survives navigation, reconnects and container rolls.
- Different rooms may run simultaneously. A browser clock is only a display;
  server-side starts and native solve timestamps decide awards.
- Use Pause/Resume for interruptions. Recorded pause intervals are excluded
  from active elapsed time. Players cannot stop their own clocks.
- The progress/time of the last solved milestone is used for incomplete
  rooms. It does not grow while the team is stuck. Zero solves is ineligible.
- Names, membership, room order and prize policy are fixed once the event
  opens. Native destructive writes that would silently rewrite event solve
  history are blocked. Normal challenge description/flag/hint authoring stays
  available; consider the effect of content changes on all teams.
- Explain organizer corrections/exclusions in the supplied reason field.
  Corrections adjust room elapsed times, not native solve timestamps; they
  do not change overall award timing. All such actions are audited.

## Closing and prizes

Close the event to record the cutoff, review per-room and overall standings,
then publish final results. Publication stores an immutable snapshot for
the public/projector presentation. Exports include the room and overall
award rows. Exact ties remain shared, not decided by an arbitrary database ID.

Unpublish/reopen requires an organizer reason. Reopening returns to paused;
resume explicitly when participants are ready. The closed interruption is
accounted for as pause time. Preserve original solve history and audit logs.

## Deployment and rollback

CI builds from the exact pinned CTFd base with the plugin and static frontend.
Runtime credentials arrive through environment Secret references. The image
contains neither participant data nor production credentials.

The first GHCR package publication requires making the package public once
in GitHub's package settings. Verify an anonymous pull before changing GitOps.
Pin the tested tag and digest in both CTFd init and application containers;
Argo handles the rollout. MariaDB, Redis, uploads and logs retain their PVCs.

Plugin migrations run before request serving. Take a database/uploads backup
before an upgrade and retain the previously working image reference. Rolling
back code alone does not reverse database schema changes: check migration
compatibility first, or restore the matching private backup with the event
closed. Never delete/recreate the namespace or its PVCs as an upgrade step.

The initial migration from stock CTFd is intentionally refused when individual
solves exist; ownership must be migrated explicitly. A fresh instance with
no individual solves safely switches to native team mode. Administrator
accounts are preserved and do not need team membership.

## Public display and privacy

The projector API contains team display names and aggregate competition
results. It excludes participant email addresses, submitted answers, session
tokens and administrator capabilities. Before roster release, public team
information is withheld. Failed refreshes retain the last view and show a
connection warning; they do not invent new progress or times.
