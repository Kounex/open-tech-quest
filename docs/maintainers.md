# Challenge maintainers and integrated authoring

Approved 2026-11-04: administrators manage all accounts in an admin-only Users
tab, promoting self-registered accounts to Challenge maintainer. Maintainers
see only Rooms in Organize and can configure all five rooms and author their
standard flag challenges there. Teams remains the attendance/roster workspace.
CTFd retains accounts, password handling, challenges, flags and grading.

## Authorization and staff lifecycle

Keep native user types unchanged. Add a plugin-owned, user-FK-cascading maintainer
grant table/migration; no grants on startup. Native admins remain administrators;
this feature never promotes/demotes a full administrator. Only admins can grant
or revoke maintainer access. Check the database on every privileged request so
revocation applies to open tabs and API requests. Existing CSRF/session rules apply.

Viewer adds `role: guest|participant|maintainer|administrator`,
`can_manage_rooms: boolean`, `can_manage_users: boolean`, retaining `admin`.
Regular participants, banned accounts and guests cannot call management APIs.
Maintainers cannot use native `/admin` or administrative native APIs, or read
quest admin state, users, email lists, teams, audit, corrections, event controls,
exports, projector controls, registration or attendance controls. They must not
receive those payloads even if tabs are hidden. Admins retain existing access.

Exclude maintainers from participant resources, attendance prompts and capture,
allocation pools, optimization, finalization counts, team naming, room starts,
native attempts/unlocks and award eligibility. Include grants in roster plan
fingerprints. Reject native team assignment of staff through existing guards.

Role writes serialize under the event lock. Promotion of an account on an unused
provisional team is allowed only while draft/preparation or attendance review
(`check_in`/`closed`); detach it without deleting the team or other users. Clear
its readiness on an actual role transition so role removal never resurrects old
attendance. Reject promotion if the account has competition activity, or its
assigned team has activity, or assigned rosters have already been optimized.
Unassigned inactive accounts may become staff later. Revocation always remains
available and leaves the account unassigned/unconfirmed; normal onboarding and
roster lifecycle still govern subsequent participation. Native administrators
are displayed read-only in Users; their management stays native CTFd.
Audit transitions without credentials/flag values and invalidate native user/
team caches. Hide staff from native public listings while granted, preserving
their previous hidden value for revocation. Preserve all existing event data.

## Shared API seam

Existing `/api/v1/quest` envelope and session/CSRF rules apply.

- GET `/admin/users` (admin only): `{users: ManagedUser[]}`.
- PATCH `/admin/users/<id>/role`: `{role: participant|maintainer, confirm:true}`
  returns ManagedUser. Idempotent same-role writes preserve readiness/history.
- `ManagedUser`: `{id,name,email,role,banned,team_id,team_name,ready_at,
  can_change_role,role_change_reason}`. Blocked actions explain why.
- GET `/manage/rooms` (admin/maintainer): `{event,rooms,available_challenges}`.
  Shape matches those fields of existing admin state, with admin room metadata.
  No participant, team, email, audit or flags in this overview.
- Existing PATCH `/admin/rooms/<slug>` admits room managers only; all other
  `/admin/*` routes retain native-admin authorization. Existing field validation
  and draft topology restrictions remain. Room writes are audited.

### Challenge editor

- GET `/manage/rooms/<slug>/challenges`: ChallengeWorkspace.
- POST same collection: `{name,description,state,flags}` creates a native
  standard challenge with fixed value 100, appends/maps it atomically and returns
  EditableChallenge. State is `hidden|visible`; flags is a nonempty array of
  `{content:string,case_insensitive:boolean}`. Empty descriptions allowed.
- PATCH `/manage/rooms/<slug>/challenges/<id>` accepts those same four fields
  (partial updates allowed); returns EditableChallenge.
- DELETE same item removes an unused challenge and rebuilds the chain atomically.
- POST `/manage/rooms/<slug>/challenges/<id>/preview`: `{submission:string}`
  returns `{status:correct|incorrect,message}` using native flag comparison,
  without starts, solves, fails, unlocks, prizes or participant submission logs.
- `ChallengeWorkspace`: `{challenges:EditableChallenge[],can_create,create_reason}`.
- `EditableChallenge`: `{id,name,description,state,type,flags,
  can_edit,edit_reason,can_delete,delete_reason}`. Flags use the same input shape.
  Unsupported existing types/flag logic are read-only with a clear reason and
  no destructive normalization; preserve existing files/hints/value on updates.

Authoring creates only standard/static/any-flag challenges. Exact case-sensitive
matching is default, with an explicit per-flag case-insensitive option. Validate
input strictly and bound names/descriptions/flag sizes; never echo secrets in
errors, logs, audits, Git or bootstrap. Challenge reads and flag previews require
room management permission; require actual room membership for every ID.

Create/update/delete only in Draft. Refuse modifying challenges with activity;
never erase solves/fails/history. Lock mutations of demo content while an active
demo batch exists, with instructions for an administrator to remove the demo
before real authoring. Do not silently unload demo content in production. Native
upstream admin challenge editing remains available subject to existing guards.
Ordering uses one shared helper to rebuild native requirements/next_id/positions
and QuestStep rows under the event lock. New authoring writes use one transaction;
do not call upstream helpers that commit halfway through challenge/flag mapping.

## Frontend and verification

Admin gets Users alongside existing tabs, searchable by name/email and filterable
by role. Show role, attendance, team, banned state and explicit confirmed role
change, explaining effects. Maintainer enters Organize directly at Rooms, with
no native admin link or other tabs. Shared room editing for both roles includes
new/edit/remove challenge forms, sanitized Markdown preview, static flags and
answer-check preview. Avoid resetting unsaved forms on polling. Reuse existing
visual language, accessible focus/labels/contrast and reduced-motion behavior.
Staff lobby should explain their role and link to Organize without attendance
or Start actions; ordinary participant journeys remain unchanged.

Backend owns plugin/tests, authoring owner owns its new module/helper and focused
tests, frontend owns web, parent owns docs/browser/release/GitOps. No concurrent
staging/commits: parent commits completed units. Review independently using
review-bar; findings need a concrete trigger, consequence, verified in-scope path.
Meaningful checks cover authorization/PII, native endpoint bypass, staff exclusion
everywhere, fresh/upgrade SQLite/MariaDB, stale role/readiness/optimization,
grant/revoke in held sessions, CRUD/flags/native participant solving, lifecycle
and activity locks, room isolation, no logged flag values, and actual admin/
maintainer/participant browser journeys before CI publication and GitOps rollout.
