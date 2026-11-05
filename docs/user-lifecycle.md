# Account demotion, deletion and access control

Approved 2026-11-05: verify accidental maintainer promotion can be reversed and
add account deletion in Organize → Users, checking the consequences throughout
attendance, allocation, optimization, team membership and native challenge play.
CTFd remains the account authority; no new identity provider or secret is needed.

## Decisions

- Retain Participant ↔ Challenge maintainer role control. Label the reverse
  action clearly as **Return to participant**. Full administrator roles remain
  managed in native CTFd; their rows stay read-only in the Quest Users view.
- Actual role transitions clear readiness and detach unused provisional team
  assignment, repairing captain ownership and preserving team records. Same-role
  retries change nothing. Demoted maintainers re-enter the participant pool
  unassigned/unconfirmed and must follow the current attendance/roster phase;
  they cannot self-join or bypass finalization. Staff still cannot participate.
- Add confirmed deletion of unused participant/maintainer accounts. Refuse self,
  personal competition activity or activity-bearing team membership, and refuse
  removal from optimized/finalized/started rosters. Unassigned inactive accounts
  may be deleted later; readiness alone is not competition history. Never erase
  solves, attempts, ratings, unlocks, awards, starts, naming history or published
  results to make a deletion succeed. Preserve authored challenges/flags/files.
- Draft/pre-optimization deletion removes attendance/grant/account metadata and
  detaches provisional membership, repairs the captain and retains the team.
  Clear credentials/tokens/session caches and invalidate proposal fingerprints.
  Already-deleted IDs must not delete a newly registered account through ID reuse.
- Add **Deactivate account / Reactivate account** using native `banned` status
  for participant/maintainer accounts. This denies access without erasing scores
  or membership history. Pre-optimization deactivation may detach only an unused
  provisional assignment and clears readiness. Later/activity-bearing membership
  and recorded readiness remain historical, with no automatic reshuffle.
  Reactivation never creates a ready record, grant or team assignment; normal
  phase rules apply. Keep maintainer grants while inactive so revocation of
  access never accidentally reclassifies staff solves or makes staff a player.
- Full administrator accounts are read-only in these new controls. Native CTFd
  operations must share the same safety policy: never self-delete/self-lock out,
  never remove/deactivate/demote the last usable admin, never erase history or
  frozen rosters. Native type changes must clean up participation eligibility
  and cannot bypass staff activity restrictions or revive old attendance.

## API

Existing session/CSRF/envelope rules apply. Every write takes the shared event
lock and then rechecks the actor's persisted admin/type/banned state. Check the
target and current team/activity under that same transaction. Native paths use
the same rules; no route may call an unconditional destructive upstream helper.

- `ManagedUser` adds `can_delete:boolean`, `delete_reason:string|null`,
  `can_set_active:boolean`, `access_reason:string|null`.
- DELETE `/admin/users/<id>` body `{confirm:true}` returns `{id,deleted:true}`.
- PATCH `/admin/users/<id>/access` body `{active:boolean,confirm:true}` returns
  the updated ManagedUser. Same-state retries are idempotent.
- Existing PATCH `/admin/users/<id>/role` keeps its contract; rejection reasons
  must match metadata displayed in Users.
- Sensitive account responses use `Cache-Control: private, no-store`.
- Audit IDs, action/role/access transitions and membership effects; no passwords,
  tokens, submitted flags or credential material. Preserve audit history.

Reject queued actions from actors demoted/banned/deleted while waiting. Reject
ready/start/attempt writes from targets deleted/deactivated or made staff while
waiting; no stale successful attendance or solve, and no deleted-object 500.
Role/access/delete changes invalidate reviewed allocation/optimization plans.
Account deletion never deletes a team record or another member's progress.

## UI and verification

Users shows clear promotion/demotion and access controls, a separate destructive
delete action, explicit effect confirmations and server-derived disabled reasons.
On failures retain the list and show the reason; after changes refresh both Users
and organizer state. Existing search/filter, accessibility and mobile layout stay.
No extra tabs or write capabilities for maintainers or participants.

Backend owns plugin and meaningful regression tests; frontend owns web; parent
owns docs, actual isolated browser journeys, CI, GitOps and fleet updates. Parent
stages/commits sequentially. Independent review follows review-bar: only concrete,
verified in-scope failures with real consequences; zero findings is valid.
Exercise unused/provisional/ready/captain/team-member/finalized/solved accounts,
demote/re-promote, delete/deactivate/reactivate, native bypasses, revoked sessions,
stale previews and wait-boundary races on SQLite/MariaDB. Verify a teammate's
solves/clock/rank remain intact when deleting is refused or access is revoked.
Production verification is read-only; never delete, demote or ban actual users
for QA. Back up privately before deploying the validated image through GitOps.
