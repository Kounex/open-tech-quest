# Organizer control of public registration

Participants use native CTFd personal accounts. Organizers can open or close
public self-registration from **Organize → Event → Public registration**.
The existing native `registration_visibility` setting is authoritative: public
means open, private means closed. Other native modes are displayed as closed
for local self-registration. Startup and deployment preserve the current value.
There is no additional setting, migration, credential or service.

The control is independent of check-in and competition phases. Closing public
registration blocks creation of new accounts through the native signup form,
including submissions from an already-open form. Existing users can still log
in, confirm attendance where check-in permits, and participate with their team.
Opening registration after rosters finalize does not assign new users to frozen
teams. Administrator account provisioning remains native administrator behavior.

## API and UI

- GET `/api/v1/quest/bootstrap` and `/admin/state` gain
  `registration: {enabled: boolean}` derived from the native setting.
- PATCH `/api/v1/quest/admin/registration` accepts exactly `{enabled: boolean}`,
  requires the existing administrator session and CSRF protection, and returns
  the registration state. Its write and audit entry commit together.
- Organizer registration-setting mutations serialize with native signup
  submissions through the existing event lock. Signup writes
  check the authoritative database value after the lock, so a stale native
  config cache cannot admit an account after registration closes.
- Native config cache invalidation follows commit; native administration reads
  the same setting. As with quest-controlled clock settings, native HTTP writes
  to this setting are refused with guidance to use the organizer control. This
  keeps one audited write path without copying native bulk-config logic. No
  duplicate state can drift.
- The organizer control displays current status, confirmation, errors and busy
  state. Public registration links are shown only when the bootstrap confirms
  registration is open; a closed notice directs existing users to sign in.

## Delivery and verification

This is a tier M feature: one implementation agent owns plugin/tests/frontend;
the parent reviews the complete diff and owns documentation, isolated real
browser checks and GitOps deployment. Reuse the native setting and existing
mutation transaction boundary; avoid changing account/password handling.

Focused tests cover administrator/CSRF checks, invalid values, cached prior
visibility, blocked GET and POST signup, reopening and successful native account
creation, persistence and independence from event/check-in state. Run the changed
cases during implementation; run the required full SQLite/MariaDB, frontend and
runtime gates once for the release. In an isolated instance, exercise the real
organizer control and separate signup session, including an already-loaded
form. Production verification is read-only and preserves its registration state.
