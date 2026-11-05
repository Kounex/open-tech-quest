# Event operations

## Before participants arrive

1. Verify backups cover MariaDB and uploads, including plugin tables, and
   rehearse restoring into a disposable database. CTFd exports include plugin
   tables, but the matching plugin code/migrations must also be available.
2. Ask maintainers to register normal accounts, then use **Organize → Users**
   to grant **Challenge maintainer**. These staff accounts are excluded from
   attendance, allocation and play. Only full administrators manage roles.
3. In **Organize → Rooms**, rename/add/remove unused rooms and create standard
   flag challenges with Markdown descriptions, accepted flags and answer-check
   previews. Set the required order; each challenge belongs to one room and
   Requirements update automatically. Remove the organizer demo before real
   authoring. Keep answers in CTFd’s database, never Git or image builds. Native
   challenge editing remains available to administrators for files/hints and
   advanced settings. See [maintainers.md](maintainers.md) for lifecycle rules.
4. Add room logos/artwork using theme asset URLs. Selected local web assets
   can be packaged under `branding/`; source/provenance belongs in
   `branding/sources.json`. Keep raw internal catalogue archives private.
   Room introductions support Markdown: headings, emphasis, lists, links,
   images, tables and code blocks. Expand **Preview introduction** to check
   formatting before **Save room**. Preview and participant views use the
   same sanitized renderer. Use the plain-text subtitle for the lobby card.
   Each theme includes an illustrated room header and matching lobby image.
   Leave **Hero image URL** blank to use it, or supply a local asset URL for
   a custom scene. Product icons stay separate from the room illustration.
5. Configure the event name, scheduled start/end, roster-release time and
   prize clock origins. The UI uses the organizer's browser local timezone;
   persistence and API timestamps use UTC. Leaving roster release empty
   publishes assignments immediately, so set it before assigning if needed.
6. Ask participants to register their own account through **Register**. In
   **Teams**, set the maximum team size (default five), preview random allocation,
   then apply it. These are provisional groups. Set roster release beforehand if
   assignments should remain hidden until a specific time. Each person logs in
   and waits until the organizers open **Attendance check-in**. Confirming
   presence then records attendance without starting room or event timers. Follow the attendance workflow below before opening.
7. Open `/quest/stage` on the projector. Choose overview, room, overall or
   awards from the organizer Projector tab. Verify 1080p output and long team
   names on the actual beamer; full-screen overview uses two panels of 25.
8. Configure SMTP before relying on password reset/email verification. It is
   an event deployment setting; no mail credentials belong in this repo.

## Event-day sequence and late arrivals

Open registration in the morning and attendance capture when actual presence
should be confirmed. Signed-in, returning and newly registered users receive
the same explicit prompt while capture is open. At cutoff close registration
and capture. If provisional random allocation has not been performed, Preview /
Apply initial allocation while still in Team preparation. Then **Move to
attendance review → Preview attendance optimization → Apply reviewed groups**.
Only checked-in eligible people enter final grouping. Participants confirm their
team names; organizers **Finalize rosters**, then **Start event**. Closing the
windows alone does not allocate or finalize teams.

After finalization, organizers may open a **late-only attendance window** for
unassigned newcomers and reopen registration if needed. A newcomer registers /
logs in and confirms their own presence. In Teams, select checked-in late
arrivals and admit them into a named team with room, or create an additional
team with an agreed final name and recorded reason. Existing members and clocks
remain fixed. New teams start rooms explicitly and use the preconfigured timing
policies. Close the windows when done; cutoff/closed/published events refuse
admission. See [late-admission.md](late-admission.md).

## Managing account roles and access

Use **Organize → Users** to grant room access or **Return to participant** after
an accidental promotion. Actual role changes clear attendance and unused
provisional team membership; the account must follow the current check-in and
roster process again. Full administrators remain managed in native CTFd.

**Delete account** removes an unused participant/maintainer account after explicit
confirmation. It is disabled for recorded competition activity and frozen team
membership so teammates’ solves, clocks and prizes cannot be silently changed.
Unused provisional members can be removed before optimization; captain ownership
is repaired and team records are retained. Authored challenges remain intact.

Use **Ban account** to revoke access and exclude that user’s solves from counted
team progress while retaining all history for investigation. Teammates can
re-solve affected challenges; **Unban account** restores eligible retained solves
without duplicate credit and never creates attendance or team assignment.
Published contribution changes require unpublishing first. These operations and
native administration use the same lifecycle rules and invalidate outstanding
allocation reviews; preview again when asked. See [user-lifecycle.md](user-lifecycle.md).

## Opening and closing registration

Use **Organize → Event → Public registration** to open or close new account
signups. The displayed state comes from CTFd's own registration setting and
survives restarts. Changes are confirmed and audited. Closing signup also blocks
an already-loaded registration form from creating a new account.

Existing accounts can still sign in and check in where attendance is open.
Registration, attendance check-in and competition start are separate controls.
Reopening signup after roster finalization does not change the competing teams;
new accounts remain unassigned. See [registration.md](registration.md).

## Attendance and final teams

Keep **Attendance check-in** off while collecting registrations before the event.
The two controls are separate: registration creates accounts; attendance records
that someone is present and taking part. Capture starts off on installation and
upgrade. It never starts event or room timers.

1. In **Teams**, set maximum team size (default five) and allocate the pool into
   random provisional groups. Set roster release beforehand if assignments
   should remain private. Early registrants wait with no ready confirmation.
2. At the venue, open **Attendance check-in** from **Event** or **Teams**.
   Unconfirmed participants on active Quest pages get an automatic dialog within
   five seconds. Returning from a background tab checks immediately. Someone
   registering or logging in during capture sees it immediately. They explicitly
   press **I'm ready to quest**; opening the dialog never checks anyone in.
3. Close attendance when the capture window ends. Old/stale pages cannot add
   confirmations afterwards. Existing confirmations and timestamps stay recorded.
   Use the team-preparation action to review attendance, then **Preview attendance
   optimization**. Inspect sizes, individual moves, missing-user removals and any
   unavoidable small-team warning. Capacity is a hard maximum; the optimizer
   preserves groups where possible and avoids a tiny last team.
4. Apply the reviewed plan. Changed attendance, memberships, settings or an
   intervening attendance opening make the plan stale. Accounts are retained
   when absent users are unassigned. Automatic reshuffling ends at naming.
5. Any ready member confirms the team's final unique name once. The first
   confirmation wins across devices. Generated Team NN names must change.
6. For late arrivals, explicitly reopen **Attendance check-in** in review or
   naming. New confirmations appear in the ready, unassigned queue. Place them
   with a reason in a group with capacity, or create an additional team. Close
   capture again before reviewing/applying a plan or finalizing rosters.
7. Finalize when capture is closed, every ready participant is assigned and
   active teams are named. Membership then stays fixed. Start the competition
   separately in Event after authoring real challenges and removing any demo.
   Participants still explicitly start each room's clock.

Participants may dismiss an opening's prompt with **Not yet** and use its visible
check-in action later. Reopening can prompt still-unconfirmed people again;
already-confirmed people are not asked again. Account settings pages show a notice
linking to Quest without abandoning unsaved edits. For this upgrade, ask
participants with existing open pages to refresh once to load the new attendance
UI; future window changes need no manual refresh. Most older Quest pages also
receive an automatic refresh notice, while the older Stage view cannot display
that notice. See
[attendance-window.md](attendance-window.md) for the full delivery rules.

The organizer view shows names, email, readiness and team membership with search
and filters. Participants see only their own released team names/readiness;
emails remain organizer-only. Native self-service membership and name writes
cannot bypass allocation. Registering after finalization does not join a team.
Configure CTFd SMTP for password reset/email verification when needed.

## Preview with demo content

In `/quest/admin`, open **Event → Demo content → Load demo content**.
Confirm the action to populate all five rooms with 25 clearly marked practice
challenges, free hints and rich Markdown introductions. The examples provide
all information needed to solve them without a live cluster or external lab.
No participant accounts, teams, room starts or solves are created.

Loading requires draft status and no existing room challenge mappings. Existing
unmapped native challenges remain intact. The import records the exact IDs it
creates and snapshots original room introductions/subtitles. **Preview the
rooms** opens the full experience; organizer accounts can inspect challenge
content and hints while participants still see draft/preparation notices.

Use **Remove demo content** before starting the actual competition. Removal
only deletes tracked demo content, restores original room text where it still
matches the demo, and keeps subsequent organizer edits and unrelated real
content. Removal refuses to erase demo attempt/start history. Competition
start is blocked while a demo is loaded, preventing an accidental transition
that would make cleanup unsafe. Load/removal operations are audited.

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
