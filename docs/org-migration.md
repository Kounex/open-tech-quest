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
