# robot-stack

Python tooling to plan Opentrons robot releases across the multi-repo stack (Flex and OT-2): which repos need tags, what each tag should look like, where CI runs after you push, how to invalidate CloudFront when builds finish, and how to verify published assets for a tag.

## Recommended workflow (Cursor)

Open this repo in [Cursor](https://cursor.com) and start a chat along these lines:

> I need to do a new release for **Flex** (or **OT-2**). It will be **internal** or **external**, and **stable**, **alpha**, or **beta**.

Workspace rules in `.cursor/rules/` teach the agent how to run the scripts below. It syncs local clones, writes a reviewable plan file (`.build/plans/<app-tag>.plan.yaml`), and points you at `just apply-release-plan` for tag pushes. **Nothing is pushed automatically** except when you explicitly run `just apply-release-plan --yes`; CloudFront invalidation runs only when you pass `--execute` to `just invalidate-cloudfront`.

Prompt Cursor as above and it will walk you through the full release in order, running the advisory scripts and printing what to do next at each stage:

1. **Plan tags** — runs `just go-plan` to write `.build/plans/<app-tag>.plan.yaml` for review (agents should use this instead of printing raw git commands).
2. **Review plan** — inspect branch, `head_commit`, and checksum in the plan file.
3. **Push tags** — run `just apply-release-plan --plan ... --dry-run` then `--yes`. Apply refuses stale plans when origin branch tips drift; regenerate with `just go-plan` if needed.
4. **Validate coordinated tags (Flex)** — `just apply-release-plan` runs `just validate-release-tags` after creating the app tag locally and before pushing it. You can also run validate standalone when tagging manually.
5. **Track builds** — runs `just track-builds` after the app tag is pushed to surface app, kickoff, and robot OS workflow runs.
6. **Verify builds** — wait for CI to finish.
7. **Invalidate CDN** — runs `just invalidate-cloudfront --execute --wait` to submit CloudFront invalidation and poll until it completes (omit `--execute` to print the AWS command only).
8. **Verify assets** — runs `just verify-release-assets` to check manifests, updater YAMLs, and artifact URLs for the tag.

### TODO: release checklists

Generate a **release checklist** for each run (tag plan, commands run, build links, invalidation, sign-off). Checklists will be committed in this repository and published on [GitHub Pages](https://opentrons.github.io/robot-stack/) alongside asset inventories and release guides, with an index page listing past releases.

The sections below document the same commands for interactive or scripted use without Cursor.

**Live asset inventories and release guides:** [opentrons.github.io/robot-stack](https://opentrons.github.io/robot-stack/)

**Regenerate that site:** run the [Publish asset inventory to GitHub Pages](https://github.com/Opentrons/robot-stack/actions/workflows/asset-inventory-pages.yml) workflow (`workflow_dispatch` on `main`, or push to `main`).

## Setup

The only external dependency is [uv](https://docs.astral.sh/uv/).

Instead of make, use [just](https://github.com/casey/just). The VS Code justfile helper is [vscode-just](https://github.com/nefrob/vscode-just).

## How

- see the possible commands
  - `uv run just`
- format the justfile
  - `uv run just fmt`
- format and lint Python
  - `uv run just fix`
- sync repos and inspect release state
  - `uv run just go` (interactive tables and suggested commands)
  - `uv run just go-plan --path flex --release-type internal --stability beta --version v4.0.0` (agent default: plan file only)
- apply a reviewed release plan (after dry-run)
  - `uv run just apply-release-plan --plan .build/plans/ot3@4.0.0-beta.0.plan.yaml --dry-run`
  - `uv run just apply-release-plan --plan .build/plans/ot3@4.0.0-beta.0.plan.yaml --yes`
- verify a coordinated Flex tag exists in all three stack repos (before pushing the app tag)
  - `uv run just validate-release-tags --tag ot3@4.0.0-beta.0`
- find GitHub Actions runs after pushing an app tag
  - `uv run just track-builds --path ot2 --tag internal@26.5.2801 --wait`
- invalidate CloudFront after builds finish (or print the AWS command only without `--execute`)
  - `uv run just invalidate-cloudfront --path ot2 --tag internal@26.5.2601 --execute --wait`
- verify live manifests and artifacts for a release tag
  - `uv run just verify-release-assets --path ot2 --tag internal@26.5.2601`

## Release Paths

`just go` runs `automation/go.py`, an interactive release helper. It supports two robot paths; **Flex is the default**.

| Path | Repos | App repo | Version scheme |
|---|---|---|---|
| **Flex** | `opentrons`, `oe-core`, `ot3-firmware` | `opentrons` | Coordinated `ot3@` / `v*` tags on all three repos (see below) |
| **OT-2** | `opentrons-ot2`, `buildroot` | `opentrons-ot2` | Calendar semver for app + internal; buildroot external uses its own `vX.Y.Z` line |

`robot-stack-infra` is always cloned and pulled for both paths as a reference repo. It is not included in release tables or tagging.

**Default release branches:** Flex **external** prefers `chore_release-<version>` when that branch exists on the remote. Flex **internal** and OT-2 default to each repo's default branch (`edge` / `main` / `opentrons-develop`).

**Branch overrides** (any path/channel):

```bash
just go ... --app-branch edge --stack-branch oe-core=main --stack-branch ot3-firmware=main
```

When the release branch differs from the repo default, the plan file includes a `checkout` step before tagging.

### Release plan apply statuses

`just apply-release-plan` classifies each repo before tagging:

| Status | Meaning |
|---|---|
| `pending` | Branch tip matches plan, tags not on origin yet. Ready to tag. |
| `applied` | All planned tags already exist on origin at the planned commit. Safe to skip (resume). |
| `drifted` | Tags not pushed yet, but `origin/<branch>` moved since the plan was generated. Blocked; regenerate with `just go-plan`. |
| `conflict` | Tag exists on origin but points at the wrong commit. Blocked; manual fix required. |

Plans include a `head_commit_checksum` for staleness detection. Apply resumes safely after partial tag pushes when already-applied repos match origin.

### Tag push order

Push annotated tags in this order. Stack repos first, app monorepo last.

| Path | Order |
|---|---|
| **Flex** | `ot3-firmware` (if needed) → `oe-core` (if needed) → `opentrons` (app, always last) |
| **OT-2** | `buildroot` (if needed) → `opentrons-ot2` (app, always last) |

### Flex semver (coordinated tags)

Flex releases use coordinated stack tags on `opentrons` and `oe-core`. `ot3-firmware` uses the same `ot3@*` tag internally; for external releases, semver `v*` stack tags map to `ex*` on firmware (see [oe-core PR #329](https://github.com/Opentrons/oe-core/pull/329)). Do not place semver `v*` coordination tags on `ot3-firmware`: they break cmake `git describe --match=v*`.

Every firmware release commit needs a coordination tag (`ot3@*` or `ex*`). Add a new integer **`vN` version tag** only when that commit does not already have one; `vN` must be globally unique across the firmware repo. CI checks out the coordination tag; cmake reads the co-located `vN`.

Tag-based CI in `oe-core` (`build-refs`) resolves only the expected tag on each repo; missing tags fail instead of falling back to latest or default branch.

In `just go`, Flex uses **stable**, **alpha**, or **beta** stability (legacy `unstable` maps to `alpha`). OT-2 tagging is unchanged.

At a given semver base, **alpha and beta are independent release flavors** with separate counters. For example `ot3@4.0.0-alpha.3` and `ot3@4.0.0-beta.0` can coexist. Tag numbering reads the app monorepo catalog (`opentrons` for Flex). Change logs compare against the prior tag in the **same lane** on the release branch.

| Repo | Internal | External |
|---|---|---|
| `opentrons` (app) | `ot3@X.Y.Z`, `ot3@X.Y.Z-alpha.N`, `ot3@X.Y.Z-beta.N` | `vX.Y.Z`, `vX.Y.Z-alpha.N`, `vX.Y.Z-beta.N` |
| `oe-core` (robot OS) | same stack tag as app | same stack tag as app |
| `ot3-firmware` | same `ot3@*` tag as app + integer `vN` | `exX.Y.Z…` (from `vX.Y.Z…`) + integer `vN` |

**External firmware example** (stack `v9.1.0-alpha.7`):

```bash
# ot3-firmware only:
git tag -a v70 -m "Flex firmware v70"
git tag -a ex9.1.0-alpha.7 -m "Coordinated release marker"
git push origin v70 ex9.1.0-alpha.7

# opentrons / oe-core:
git tag -a v9.1.0-alpha.7 -m "Coordinated release marker"
git push origin v9.1.0-alpha.7
```

**Internal firmware example** (stack `ot3@4.0.0-beta.0`): same `ot3@*` on all three repos plus `vN` on firmware.

**Internal release flavors** (same `X.Y.Z` base; lanes are independent, not a promote-alpha-to-beta ladder):

| Lane | Stability in `go` | Tag example | Typical use |
|---|---|---|---|
| VM isolation | `beta` | `ot3@4.0.0-beta.0` | Beta app channel |
| CRS | `alpha` | `ot3@4.0.0-alpha.4` | Alpha app channel; can follow beta on the same base |

When **both** beta and alpha channels need fresh builds in the **same cycle**, publish desktop builds **beta first, then alpha**:

1. **Beta publish** overwrites `beta.yml` and `alpha.yml` (alpha-channel users temporarily see the beta build).
2. **Alpha publish** restores `alpha.yml` only; `beta.yml` stays on the beta build.

Tag push order can differ from publish order. YAML pointers follow the **last desktop build publish**, not which tag was created first. If beta publishes without a follow-up alpha, alpha-channel users keep seeing the beta build even when alpha artifacts remain in `releases.json` (for example internal Flex `4.0.0-alpha.4` tagged before `4.0.0-beta.1`, but `alpha.yml` now points at beta.1). Configured in `opentrons/app-shell/electron-builder.config.js` via `generateUpdatesFilesForAllChannels: true`. See [release channel hierarchy](https://opentrons.github.io/robot-stack/release-channel-hierarchy.html).

Before pushing the app tag, run `just validate-release-tags --tag <app-tag>` (or let `just apply-release-plan` run it after creating the tag locally). `go` prints this in the Next steps panel.

**Example (4.0.0 internal alpha):**

```bash
just go-plan --path flex --release-type internal --stability alpha --version v4.0.0 --app-branch edge --stack-branch oe-core=main --stack-branch ot3-firmware=main
just apply-release-plan --plan .build/plans/ot3@4.0.0-alpha.5.plan.yaml --dry-run
just apply-release-plan --plan .build/plans/ot3@4.0.0-alpha.5.plan.yaml --yes
```

### Track release builds

After pushing the app tag, locate CI with `just track-builds`:

```bash
just track-builds --path ot2 --tag internal@26.5.2801 --wait
```

The script finds app, kickoff, and robot OS workflow runs and prints a Rich table plus a Slack copy block with two links (`app` and `ot2` or `flex`). With `--wait`, it polls every 15 seconds until all three workflow runs appear (default timeout 15 minutes).

After builds finish, invalidate CloudFront and wait for completion:

```bash
just invalidate-cloudfront --path ot2 --tag internal@26.5.2601 --execute --wait
```

Then verify the tag's manifests, updater YAMLs, and artifact URLs:

```bash
just verify-release-assets --path ot2 --tag internal@26.5.2601
```

Omit `--execute` on `invalidate-cloudfront` to print the `aws cloudfront create-invalidation` command without running it. For broader manifest browsing, use `just ot2-assets` / `just flex-assets` or `just assets-pages`.

## OT-2 calendar semver

OT-2 uses semver-shaped versions so electron-updater and robot update checks work. **Internal and external channels use different patch schemes.** Internal app and robot OS share the same version string. External app uses calendar semver; external buildroot uses an independent traditional semver line (for example `v1.19.9`).

Calendar components use **US Eastern** (`America/New_York`):

| Component | Meaning |
|---|---|
| **Major (YY)** | Two-digit year (`2026` → `26`) |
| **Minor (M)** | Month, no leading zero (`June` → `6`) |

### Internal (`internal@`)

Patch encodes **day + same-day build** as `DNN = day * 100 + build_num` (build 1–99 per day).

| Example | Meaning |
|---|---|
| `internal@26.5.2601` | First stable internal build on May 26, 2026 |
| `internal@26.5.2602-alpha` | Second alpha internal build that day |
| `internal@26.5.101` | First stable internal build on May 1, 2026 |

Same-day follow-ups increment the build number in the patch (`2601` → `2602`).

### External (`v`)

**App (`opentrons-ot2`):** patch **N** is the monthly **stable** build counter, **starting at 0**. Alpha and beta builds use numbered prereleases on the same `YY.M.N` base (`v26.6.0-alpha.0`, `v26.6.0-beta.0`). Because `v26.6.0` outranks `v26.6.0-alpha.N`, the first stable release in a month can share `N=0` with prior alphas on that base. **N** increments only for a second stable release in the same month. At most 10 stable external releases per month (`N` = 0–9).

| Example | Meaning |
|---|---|
| `v26.6.0-alpha.0` | First alpha in June 2026 |
| `v26.6.0-alpha.1` | Another alpha QA cycle on the same base |
| `v26.6.0` | First stable external release that month (same `N=0` as the alphas) |
| `v26.6.1-alpha.0` | New alpha cycle after `v26.6.0` stable |
| `v26.6.1` | Second stable external release in June |

External alpha and beta app builds use standard semver prerelease numbering (`-alpha.0`, `-alpha.1`, `-beta.0`, …) on the monthly **YY.M.N** base for that build line. Prerelease numbers increment on a fixed base. After `v26.6.0` stable, the next alpha is `v26.6.1-alpha.0`, not `v26.6.0-alpha.0`.

**Robot OS (`buildroot`):** external stable tags follow the repo's independent traditional semver line, for example `v1.19.9` → `v1.19.10`. They do not use the app calendar version.

### Summary

| Channel | Repo | Stable | Alpha | Beta |
|---|---|---|---|---|
| External | `opentrons-ot2` | `v26.6.0` | `v26.6.0-alpha.0` | `v26.6.0-beta.0` |
| External | `buildroot` | `v1.19.10` | patch bump on traditional line | patch bump on traditional line |
| Internal | both | `internal@26.5.2601` | `internal@26.5.2601-alpha` | `internal@26.5.2601-beta` |

Implementation lives in `automation/go.py` and `opentrons-ot2/scripts/ot2_calendar_semver.py`.
