# Open Tech Quest

A team escape-room experience built on CTFd: individually themed rooms,
sequential challenges, shared progress, room timing, prize standings and
a projector overview for 50 teams.

CTFd remains responsible for accounts, teams, challenge validation, hints
and solves. This application adds the event experience through a plugin,
without maintaining a fork of CTFd's core.

## What it includes

- Five individually themed rooms: OpenShift, Ansible, RHEL, Security and AI.
- An ordered challenge path per room, enforced at API and attachment access.
- One account per person, with shared team starts and solves across devices.
- Personal check-in, configurable team size, attendance-based roster optimization
  and one-time team naming, with reviewed changes before finalization.
- Persistent server-side clocks, organizer pauses and closing cutoffs.
- Room prizes by progress then elapsed time; overall prizes by distinct solves
  then elapsed event time. Genuine ties retain the same rank.
- A projector overview for 50 named teams, focused standings and awards views.
- Admin-only user management, reversible maintainer roles and safe account deletion.
- Auditable bans, legitimate teammate re-solves and consistent award timing.
- Controlled late check-in/admission without reshuffling or restarting clocks.
- Integrated standard challenge/flag authoring and customizable room creation/removal.
- Organizer controls for public registration, room composition, themes, team allocation,
  roster release, exclusions, time corrections, CSV exports and publication.

The first installation creates an event in **draft** with five empty default rooms.
Rename, add or remove unused rooms from Organize; custom rooms have neutral
themes and optional branded assets.
It does not create participants, competition challenges or flags. Organizers
can explicitly load and remove a self-contained demo from the Event tab: five
challenges per room, hints and rich Markdown room introductions. The demo stays
in draft and must be removed before starting the competition.

## Run locally

Docker or Podman with a Compose provider is required:

```sh
./scripts/dev.sh
```

The helper generates a private local session key in ignored `.env`, builds
the application and exposes it only at `http://127.0.0.1:8000`. Complete the
native CTFd setup wizard to create your administrator. Then visit `/quest/admin`.

Author standard flag challenges in **Organize → Rooms**, with Markdown descriptions,
accepted flags, answer-check previews and ordered prerequisite chains. Native
`/admin/challenges` remains available to administrators for additional content
features. In **Organize → Users**, promote registered accounts to Challenge
maintainer; they see only Rooms and do not enter attendance or team allocation.
See [staff and room management](docs/maintainers.md). Configure prize timing and
teams before starting.

Native self-service team joining is replaced by organizer allocation. After
registration, participants confirm attendance in the quest lobby. Organizers
allocate provisional teams, optimize confirmed attendance, then open final naming.
Any member can claim the unique team name once. Rosters are finalized before
competition start. See the [onboarding contract](docs/onboarding.md).

## Development and verification

```sh
cd web
npm ci
npm run check
npm run format:check
npm run build
```

The container build runs the same frontend production build. Python integration
tests run inside the pinned CTFd image, against SQLite and MariaDB in CI.
See [tests/README.md](tests/README.md) for commands, coverage and the explicitly
opt-in, disposable 50-team browser fixture. The fixture is never included in
the production image.

## Images and deployment

GitHub Actions publishes tested, versioned images to
`ghcr.io/open-tech-quest/ctfd-plugin`. Releases use semantic version tags, never
`latest`. CI checks the frontend, runs both database test suites, and starts
the final image before publication. Dependabot tracks packages and pinned
base images; upgrades of the underlying CTFd line require an explicit review.

The deployed event uses Argo CD manifests in
[Kounex/ocp-gitops](https://github.com/Kounex/ocp-gitops/tree/main/manifests/apps/ctfd).
Database credentials, Redis credentials and the CTFd session signing key come
from Doppler through External Secrets. No organizer API token is embedded in
the browser. Player actions use native CTFd sessions and CSRF protection.

See [operations](docs/operations.md), [the product contract](docs/design.md),
[release verification](docs/onboarding-validation.md) and [delivery plan](docs/implementation.md).

This is an independent event application, not an official Red Hat product.
Red Hat and product marks retain their respective owners' rights. Runtime
credentials and participant data must never be committed or built into images.

Application code is [MIT licensed](LICENSE). Fonts and brand assets have
separate notices and provenance under [branding/](branding/README.md).
