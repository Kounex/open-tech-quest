# Bans, retained evidence and legitimate re-solves

Approved 2026-11-05: banning blocks account access and excludes that user's
challenge contributions from team progress and awards. It does not delete or
rewrite original attempts, solves, users, timestamps, memberships or flag evidence.
The user explicitly chose to let teammates re-solve affected challenges.

## Counted progress

The authoritative Quest projection considers native solves and plugin recovery
solves, filtered to eligible non-banned participants. Administrators and challenge
maintainers remain staff. Each mapped team/challenge counts at most once, using
its earliest qualifying eligible solve under existing start/pause/cutoff rules.
Room progress remains the longest consecutive solved prefix; losing an earlier
solve relocks subsequent steps until it is legitimately restored. Preserve other
teammates' later solves, even if they temporarily fall outside that prefix.
Overall totals remain distinct eligible challenge solves, not a sum of points.

Unbanning restores eligibility of retained contributions under the same rules.
An original solve and a recovery solve never produce two credits for one team/
challenge. Keep original room starts and clock history; banning or recovery does
not reset timers. A recovered milestone uses the actual recovery timestamp, so
invalidated progress does not preserve the cheater's faster qualifying time.
If a remaining consecutive prefix loses its last solve, its milestone is
recomputed from the last remaining eligible prefix; it does not keep the old
time or accrue extra time while a team is stuck. Overall milestone likewise
uses the last currently counted eligible challenge. Ranking compares counts
first, then rounded active milliseconds; equal count/time shares a rank.
The pinned runtime and production schema were checked: native solve dates,
event starts and room starts use MySQL DATETIME(6), matching recovery precision.
Changing a published contributor's eligibility requires explicit unpublication;
do not silently alter the announced snapshot. Same-state retries stay idempotent.

## Native engine integration

CTFd 3.8.9 enforces unique native solves per user/challenge and team/challenge.
Its existing-solve branch checks the submitted flag but responds already_solved.
Retaining evidence therefore requires a plugin-owned recovery record, rather
than deleting a native solve or changing its attribution/type/time.

Reuse the native attempt endpoint, challenge-class flag checker, attempt limits
and rate enforcement. A narrowly scoped supported challenge-class adapter may
capture the native result for a recovery request; a response hook records the
eligible recovery and changes already_solved to correct/incorrect only for this
case. Ordinary attempts and administrator previews keep native behavior.

Every successful recovery requires the current signed account/session, eligible
non-banned participant, current team, released rosters, started room, available
step, live/unpaused event, correct flag and current cutoff. Reacquire the shared
event lock after any native session close/commit, then recheck these conditions
and whether another teammate already restored the challenge. Do not grant a
correct response before its record commits. Serialize bans, native attempts and
recovery so no counted solve slips through after a ban. Failed recovery uses
native failure logging exactly once; retries and concurrent teammates cannot
create duplicate effective credit. Partial/rate/limit/auth failures retain their
native meaning and must never be converted into a solve.

Native prerequisite rows stay a superset of eligible progress because originals
are retained. The Quest guard must enforce the stricter effective prerequisite
chain on reads/attempts/files/hints; solved-only solutions and unlocks must also
use effective credit. No global native query or administrator-check monkeypatch.
The participant UI follows Quest step state even if native solved_by_me reflects
a retained historical record. Clear stale success feedback when counted progress
decreases. Public/projector/organizer/export use the same effective projection.

Recovery records retain protected submission evidence and actor/team/challenge/
timestamp references. Audit entries contain IDs and action metadata, never raw
flags or credentials. Native investigation/export plus matching plugin tables
must retain original and recovery history. Deleting a history-bearing account
remains refused, including an account with a recovery solve. Banned accounts stay
visible to administrators with their role and retained history.

## Validation

Meaningful cases on SQLite and MariaDB: one member's solve stops counting while
teammate solves survive; earlier-step relocking; correct/incorrect legitimate
recovery; native rate/max-attempt limits; concurrent teammate recovery; repeated
bans; unban deduplication/earliest time; paused/closed/cutoff and published guards;
fresh session/account-incarnation/role checks after waits; no lost native history;
recovery evidence blocks deletion/promotion; native solved-only content denial;
and ordinary native attempts/administrator previews unchanged. Actual browser
journeys must demonstrate ban → team progress change → re-solve → restored progress,
plus unban without duplicate credit and a published-results protection.
