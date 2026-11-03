# Open Tech Quest

Public repository `Kounex/open-tech-quest`. A CTFd 3.8.9 plugin and a React
participant/admin/projector application for the Red Hat Hands-On Day.

Read `docs/design.md` and `docs/implementation.md` before changing behavior.
They define the shared API, prize rules, event lifecycle, and design direction.

## Rules

- Never commit credentials, participant exports, browser state, internal
  catalogue archives, real flags, or database dumps. Runtime secrets come
  from Doppler through the existing CTFd ExternalSecret in `Kounex/ocp-gitops`.
- Keep CTFd responsible for users, teams, challenges, flags, hints, and solves.
  Add features through the plugin; do not fork CTFd's core.
- All timing, authorization, and prize calculation is server-side. A room
  starts once per team, before challenge content is revealed. Never accept
  client-supplied timestamps or award a second solve for a teammate.
- UI and projector consume the same standings calculation. Do not count
  points as solved challenges. Preserve genuine ties.
- The event starts in draft. Startup never seeds sample event content.
  Organizer-authorized demo load/unload is an explicit admin-only draft action,
  with durable ownership tracking and preservation of real content. A loaded
  demo must be removed before competition start. It never creates participants,
  teams or progress. Bulk participant/progress fixtures remain isolated tests.
- Theme changes must preserve room IDs, memberships, starts, and solves.
- Every finished unit is committed and pushed. Every release runs backend
  integration tests, frontend checks/build, and container smoke tests.
- CI publishes versioned images to `ghcr.io/kounex/open-tech-quest`; GitOps
  pins a tested tag and digest. No secrets in image build arguments/layers.
- Independent frontend/backend work and independent review are appropriate
  for this project; assign disjoint file ownership and follow review-bar.

## Layout

- `plugin/open_tech_quest/`: Python plugin, models, migrations, API and shell.
- `web/`: React/TypeScript frontend; Vite output is copied to plugin assets.
- `tests/`: integration tests, run inside the pinned CTFd image.
- `docs/`: public specification and operations documentation.
- `Dockerfile`: pinned upstream CTFd plus built app/plugin; UID 1001.

## Related repositories

Fleet context: `~/agent/it-env` (pull before any read, run skill installer
after pull). GitOps clone on this Mac: `~/development/k8s/ocp-gitops`.
Current app: namespace `ctfd`, Argo Application `ctfd-app`, URL
`https://otq.apps.ocp.kounex.com`.
