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
- Persistent server-side clocks, organizer pauses and closing cutoffs.
- Room prizes by progress then elapsed time; overall prizes by distinct solves
  then elapsed event time. Genuine ties retain the same rank.
- A projector overview for 50 named teams, focused standings and awards views.
- Organizer controls for room composition, themes, balanced team allocation,
  roster release, exclusions, time corrections, CSV exports and publication.

The first installation creates an event in **draft** with five empty rooms.
It does not create participants, competition challenges or flags.

## Run locally

Docker or Podman with a Compose provider is required:

```sh
./scripts/dev.sh
```

The helper generates a private local session key in ignored `.env`, builds
the application and exposes it only at `http://127.0.0.1:8000`. Complete the
native CTFd setup wizard to create your administrator. Then visit `/quest/admin`.

Author challenges in native `/admin/challenges`, including descriptions,
flags, files and hints. In the quest organizer workspace, assign them to
rooms in the required order. Room settings keep CTFd Requirements and next
challenge links consistent. Configure prize timing and teams before starting.

Native self-service team joining is replaced by organizer allocation. After
registration, participants wait in the quest lobby for their assignment.
Team names and membership become fixed when the event opens.

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
`ghcr.io/kounex/open-tech-quest`. Releases use semantic version tags, never
`latest`. CI checks the frontend, runs both database test suites, and starts
the final image before publication. Dependabot tracks packages and pinned
base images; upgrades of the underlying CTFd line require an explicit review.

The deployed event uses Argo CD manifests in
[Kounex/ocp-gitops](https://github.com/Kounex/ocp-gitops/tree/main/manifests/apps/ctfd).
Database credentials, Redis credentials and the CTFd session signing key come
from Doppler through External Secrets. No organizer API token is embedded in
the browser. Player actions use native CTFd sessions and CSRF protection.

See [operations](docs/operations.md), [the product contract](docs/design.md)
and [delivery plan](docs/implementation.md).

This is an independent event application, not an official Red Hat product.
Red Hat and product marks retain their respective owners' rights. Runtime
credentials and participant data must never be committed or built into images.

Application code is [MIT licensed](LICENSE). Fonts and brand assets have
separate notices and provenance under [branding/](branding/README.md).
