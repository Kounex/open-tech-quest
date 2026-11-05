# Organization migration

Requested 2026-11-05: transfer the existing public repository from
`Kounex/open-tech-quest` to **open-tech-quest/ctfd-plugin**, retaining its repository
identity, complete Git history, tags, issues, pull requests, releases and license.
Publish subsequent images at **ghcr.io/open-tech-quest/ctfd-plugin**. Continue the
existing semantic version sequence and native CTFd/plugin compatibility.

## Preflight and cutover

- Verify the destination owner/admin membership, available repository/package
  names, repository and organization Actions access, existing workflow token
  permissions, repository secrets/variables, hooks and branch policies.
- Preserve a Git bundle and repository/release/tag metadata locally. Keep the
  existing public GHCR images and live GitOps digest available throughout.
- Prepare portable repository-owner image publishing, correct OCI source labels,
  workflow naming/self-dispatch and current documentation references. Run the
  complete PR quality/build gate with image pushing disabled before transfer.
- Transfer the existing repository with its new owner/name. Verify the same
  repository ID, refs, releases, visibility, admin access, Actions permissions,
  pending PR and old-URL redirects. Update the local Git remote explicitly.
- Merge the validated migration through the new repository. The complete release
  gate must publish a versioned image using only its repository GITHUB_TOKEN with
  packages:write. Verify source/revision/version OCI labels and anonymous pull.
  GitHub's new GHCR package requires a one-time public-visibility setting.
- Pin that exact image tag and digest for initialization and runtime in the
  existing Kounex/ocp-gitops deployment. Validate all kustomizations, push and let
  Argo sync. Verify its revision, health, rollout, PVCs, ExternalSecret, live
  authentication/assets and preserved event data using read-only checks.
- Update active source/image links, fleet catalogue/documentation and other
  existing clone remotes. Historical image digests remain historical references;
  do not invent new registry paths for old package versions. Record the verified
  release and rollback reference after cutover.

No application URL, CTFd plugin/module identifier, asset path, database table,
namespace, service, account or event identifier needs renaming. Existing Doppler
secrets remain in the deployment; they are not copied into GitHub or CI. Production
registration, attendance, users, teams, progress and clocks must remain intact.

## Verified completion — 2026-11-05

The transfer retained repository ID `1444206634`, all 16 existing tags, all 15
existing release IDs, previous pull requests, admin access, public visibility
and Actions/token permissions. The old GitHub URL redirects to the new repository.
The local Git remote and active documentation links now use the organization.
No application, frontend, branding, test or script source changed from 0.1.15.

[Migration PR #3](https://github.com/open-tech-quest/ctfd-plugin/pull/3) passed
the complete [pre-transfer build-only gate](https://github.com/open-tech-quest/ctfd-plugin/actions/runs/42078547377).
After transfer, merge source `0b367861f9645030d97619021c2edb119b5cff2b` passed
[organization release CI](https://github.com/open-tech-quest/ctfd-plugin/actions/runs/42080318727):
150 cases per SQLite/MariaDB, with three skips per dialect, plus frontend,
empty-install runtime and publication checks. CI used GITHUB_TOKEN to publish
the image, tag and [0.1.16 release](https://github.com/open-tech-quest/ctfd-plugin/releases/tag/v0.1.16).
Dependabot also ran successfully after transfer; the renamed publishing workflow
and its self-dispatch remain active.

The organization package is now public. Anonymous manifest/config reads verified
source, revision and version labels; a full linux/amd64 Podman pull with an empty
credentials file succeeded for:

```text
ghcr.io/open-tech-quest/ctfd-plugin:0.1.16@sha256:e3c482115fbd99609068177a8f9fbc9f0c645744f9199fb5733c5eb2ce8bea6d
```

All 37 GitOps kustomizations passed validation and independent review confirmed
the rendered init/runtime pins and unchanged operational configuration. GitOps
[`2127628`](https://github.com/Kounex/ocp-gitops/commit/212762883f46624dadd2afbebe0bf0267e882406)
passed [repository CI](https://github.com/Kounex/ocp-gitops/actions/runs/42085978018).
Argo reported Synced / Healthy at that revision; the deployment completed on the
organization image, MariaDB/Redis stayed running, all three PVCs remained Bound
and the Doppler ExternalSecret remained Ready. Renovate's image discovery is
namespace-generic; the fleet monitor follows OCI source labels.

Read-only authenticated live checks verified byte-identical built frontend
assets and unchanged event/content/account/attendance/team data. Production stayed
draft/check-in, registration and attendance closed, naming disabled, five rooms,
25 demo challenges, one native administrator and no participants/teams/readiness.
No production grouping, naming or challenge-submission action was used for QA.
Private pre-cutover SQL/uploads backup:
`/root/ocp-backups/ctfd/pre-org-migration-20261105T175403Z/`.
The prior public 0.1.15 image remains available at its original personal registry
path and digest for rollback; historical registry references were preserved.
