# Controlled late admission after roster finalization

Approved 2026-11-05: allow administrators to admit checked-in newcomers into an
existing team with space, or create an additional team, without moving existing
players or resetting clocks. Registration remains independently controllable.
Participants always confirm their own attendance; registration never implies it.

## Window and eligibility

Keep the ordinary preparation/review/naming/finalization workflow. After roster
finalization, attendance capture may reopen for **unassigned newcomers only** in
draft, live or paused events. Already-confirmed people are not prompted again;
assigned members never enter this late-only capture. Closed/published events
cannot open late capture or admit anyone. Staff and banned accounts stay excluded.

AttendanceWindow adds `late_only:boolean`. The UI labels late capture explicitly.
Use the same generation/polling/modal resource, focus refresh and server-side
window enforcement; opening this window never alters registration or roster phase.
New confirmations in finalized phase are marked late. No new account can start
or read challenges until it is assigned through the organizer action. Competition
start still requires capture closed; after start an explicit late window can open.
History-free newcomers who confirm after finalization can wait unassigned across
Start, provided capture is closed and the existing attended rosters are valid.
They cannot play until admitted; they do not delay everyone else’s start.

## Administration

Admin onboarding summary adds
`late_admission:{allowed:boolean,reason:string|null,fingerprint:string|null}`.
Allowed requires finalized phase and event status draft/live/paused. Fingerprint
uses the existing incarnation-bound roster fingerprint, recomputed under lock.
The Teams view shows ready unassigned late arrivals and current team capacity.

POST `/api/v1/quest/admin/onboarding/admit` accepts exactly:

- `{user_ids:[...],team_id:number,reason:string,fingerprint:string}`; or
- `{user_ids:[...],new_team_name:string,reason:string,fingerprint:string}`.

Return updated onboarding summary. Require current native administrator session,
CSRF, shared event write lock and fresh persisted authority/session after waits.
All selected users must exist, be eligible, ready, unassigned, and have no own
competition history. Validate the current account incarnations via fingerprint.
Reject duplicates, stale plans, insufficient capacity and any attempt to move an
already-assigned participant. Preserve all existing memberships, team names and
activity. Failed or concurrent duplicate requests cannot partially admit anyone
or create a second team; refresh reveals an already-completed placement.

Existing target teams must be visible, non-banned, named/locked and within saved
capacity including all existing members. New teams must have an agreed unique
non-placeholder display name, be within capacity, and receive native captain
ownership. Record their final name lock through the actual administrator actor;
do not falsely attribute an admin action to a participant. The confirmation
explains that this is their final team name and placement, not a rebalance.

Audit reason, actual actor, joined-at timestamp, user/team IDs and whether a new
team was created. Clear affected native caches. Admission does not create a solve,
start, pause, cutoff, timing correction or readiness timestamp. It never resets
the event or an existing room start. Do not broaden native team APIs or personal
join/rename routes; this is a dedicated, reasoned administrative exception only.
Initial allocation/optimizer remain locked after finalization.

## Timing and participation

New members of an existing team share that team's existing progress and starts;
their arrival does not award or reattribute any past solve. Banned contributors
remain excluded. A new team has no progress or starts and explicitly starts each
room before accessing content. Common-event and team-first-room clock origins
follow the policy configured before start; no arrival-based clock exceptions.
Recovery solves, pauses, cutoffs and award snapshots continue to use the same
authoritative projection. Late membership cannot make a disqualified solve count.

Keep deletion/promotion restrictions and frozen participant movement intact.
Admission invalidates other outstanding roster/admission fingerprints. Bans still
retain history; an admitted user with shared team activity cannot be hard-deleted.

## Event-day controls

Morning: open registration. Afternoon: open attendance capture; existing signed-in
and newly registered participants receive the same explicit readiness prompt.
At cutoff: close registration and capture. If random provisional grouping has not
been done, Preview/Apply initial allocation during team preparation. Then Move to
attendance review → Preview attendance optimization → Apply reviewed groups →
participant name confirmation → Finalize rosters → Start event.

For a late arrival: reopen registration if needed; open late attendance capture;
newcomer registers/logs in and confirms; admin admits with a reason into a team
with space or an agreed named additional team. Close those windows when done.
No automatic reshuffle of competing teams is performed.

Verify all phases, staff/banned/history/assigned-user exclusion, closed-window
rejection, unchanged clocks/scores, capacity and concurrent admission, fresh/stale
fingerprints including ID reuse, named additional team, native-route restrictions,
paused admission with play still paused, close/cutoff refusal, and actual browser
signup → late popup → reasoned placement → shared team play on SQLite/MariaDB.

## Actual browser acceptance

In an already-live finalized event, a new registration received the late-only
readiness dialog immediately. Before explicit confirmation it had no attendance
or room-start permission. After self-confirmation, capture was closed and an
admin admitted it with a reason into the existing named team. The signed-in
browser acquired that team automatically; the original team's complete standing,
progress and award times remained byte-for-byte equivalent as data.

A second newcomer registered while capture was closed, saw no readiness button
or dialog, and received the prompt automatically when late capture reopened.
After self-confirmation, an admin created an agreed final named team. It had no
progress or starts, started its room explicitly and earned a normal native solve.
It used the common event overall origin and its explicit room origin, while the
existing team's rank and times stayed unchanged. Closing both windows and an
application restart preserved memberships, raw original solves, recovery history
and original award times. No production accounts or records were used for QA.
