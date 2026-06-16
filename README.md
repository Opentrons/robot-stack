# robot-stack

Python tooling to plan Opentrons robot releases across the multi-repo stack (Flex and OT-2): which repos need tags, what each tag should look like, where CI runs after you push, and which CloudFront invalidation to run when builds finish.

## Recommended workflow (Cursor)

Open this repo in [Cursor](https://cursor.com) and start a chat along these lines:

> I need to do a new release for **Flex** (or **OT-2**). It will be **internal** or **external**, and **stable**, **alpha**, or **beta**.

Workspace rules in `.cursor/rules/` teach the agent how to run the scripts below. It will sync local clones, print release analysis, and suggest copy-paste `git tag` / `git push` commands. **Nothing is pushed or invalidated automatically**; review the output, confirm you agree, then run the printed steps yourself.

Prompt Cursor as above and it will walk you through the full release in order, running the advisory scripts and printing what to do next at each stage:

1. **Plan tags** — runs `just go` to show what needs tags and the tag shape per repo.
2. **Push tags** — prints `git tag` / `git push` commands for you to run (stack repos first, app last).
3. **Validate coordinated tags (Flex)** — runs `just validate-release-tags` to confirm the same tag exists in `opentrons`, `oe-core`, and `ot3-firmware` before you push the app tag.
4. **Track builds** — runs `just track-builds` after the app tag is pushed to surface app, kickoff, and robot OS workflow runs.
5. **Verify builds** — reminds you to wait for CI and spot-check manifests if needed.
6. **Invalidate CDN** — runs `just invalidate-cloudfront` to print the exact `aws cloudfront create-invalidation` command (distribution and paths) for your tag and channel.

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
  - `uv run just go`
  - non-interactive example: `uv run just go --non-interactive --skip-assumptions --path flex --release-type internal --stability beta --version v4.0.0`
- verify a coordinated Flex tag exists in all three stack repos (before pushing the app tag)
  - `uv run just validate-release-tags --tag ot3@4.0.0-beta.0`
- find GitHub Actions runs after pushing an app tag
  - `uv run just track-builds --path ot2 --tag internal@26.5.2801 --wait`
- print a CloudFront invalidation command after builds finish
  - `uv run just invalidate-cloudfront --path ot2 --tag internal@26.5.2801`

## Release Paths

`just go` runs `automation/go.py`, an interactive release helper. It supports two robot paths; **Flex is the default**.

| Path | Repos | App repo | Version scheme |
|---|---|---|---|
| **Flex** | `opentrons`, `oe-core`, `ot3-firmware` | `opentrons` | Coordinated `ot3@` / `v*` tags on all three repos (see below) |
| **OT-2** | `opentrons-ot2`, `buildroot` | `opentrons-ot2` | Calendar semver for app + internal; buildroot external uses its own `vX.Y.Z` line |

`robot-stack-infra` is always cloned and pulled for both paths as a reference repo. It is not included in release tables or tagging.

Each repo uses isolation branches named `chore_release-<version>` during a **Flex external** release cycle. Flex **internal** and all **OT-2** releases tag default-branch HEAD instead (`edge` / `opentrons-develop` / `main`).

For **Flex external** releases, `just go` prints `git checkout chore_release-<version>` before each suggested `git tag -a` command. Run that checkout in each repo before creating and pushing tags.

### Tag push order

Push annotated tags in this order. Stack repos first, app monorepo last.

| Path | Order |
|---|---|
| **Flex** | `ot3-firmware` (if needed) → `oe-core` (if needed) → `opentrons` (app, always last) |
| **OT-2** | `buildroot` (if needed) → `opentrons-ot2` (app, always last) |

### Flex semver (coordinated tags)

Flex releases use the **same tag** on `opentrons`, `oe-core`, and `ot3-firmware`. The tag identifies which commit participated in that release, even when a stack repo did not change. Tag-based CI in `oe-core` (`build-refs`) resolves only that exact tag on each repo; missing tags fail instead of falling back to latest or default branch.

In `just go`, Flex uses **stable**, **alpha**, or **beta** stability (legacy `unstable` maps to `alpha`). OT-2 tagging is unchanged.

| Repo | Internal | External |
|---|---|---|
| `opentrons` (app) | `ot3@X.Y.Z`, `ot3@X.Y.Z-alpha.N`, `ot3@X.Y.Z-beta.N` | `vX.Y.Z`, `vX.Y.Z-alpha.N`, `vX.Y.Z-beta.N` |
| `oe-core` (robot OS) | same coordinated tag as app | same coordinated tag as app |
| `ot3-firmware` | same coordinated tag as app | same coordinated tag as app |

**Internal prerelease trains** (same `X.Y.Z` base, different stability suffix):

| Train | Stability in `go` | Tag example | Typical use |
|---|---|---|---|
| VM isolation | `beta` | `ot3@4.0.0-beta.0` | Beta app channel; ship first when adopting coordinated tagging |
| CRS | `alpha` | `ot3@4.0.0-alpha.4` | Alpha app channel; follow beta on the same base when both trains are active |

Pair beta then alpha when both channels need updates in the same cycle: beta desktop builds overwrite alpha updater YAML metadata (`generateUpdatesFilesForAllChannels`).

Before pushing the app tag, run `just validate-release-tags --tag <app-tag>`. `go` prints this in the Next steps panel.

**Example (June 2026):** recent internal alphas used base `4.0.0` (`ot3@4.0.0-alpha.3` is the latest). The first coordinated internal release on that line is **`ot3@4.0.0-beta.0`** on all three repos.

```bash
just go --non-interactive --skip-assumptions --path flex --release-type internal --stability beta --version v4.0.0
just validate-release-tags --tag ot3@4.0.0-beta.0
```

### Track release builds

After pushing the app tag, locate CI with `just track-builds`:

```bash
just track-builds --path ot2 --tag internal@26.5.2801 --wait
```

The script finds app, kickoff, and robot OS workflow runs and prints a Rich table plus a Slack copy block with two links (`app` and `ot2` or `flex`). With `--wait`, it polls every 15 seconds until all three workflow runs appear (default timeout 15 minutes).

After builds finish, print a CloudFront invalidation command with `just invalidate-cloudfront --path ot2 --tag internal@26.5.2801`.

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

**App (`opentrons-ot2`):** patch **N** is the monthly build counter, **starting at 0**. Each external release in the month (stable, alpha, or beta) gets the next **N** slot. At most 10 external releases per month (`N` = 0–9).

| Example | Meaning |
|---|---|
| `v26.6.0` | First external app release in June 2026 |
| `v26.6.1-alpha.0` | Second external build that month (first alpha on base `26.6.1`) |
| `v26.6.1-alpha.1` | Another alpha QA cycle on the same base |
| `v26.6.2` | Third external build that month (stable) |

External alpha and beta app builds use standard semver prerelease numbering (`-alpha.0`, `-alpha.1`, `-beta.0`, …) on the monthly **YY.M.N** base for that build. Prerelease numbers increment on a fixed base; starting a new build in the month bumps **N**.

**Robot OS (`buildroot`):** external stable tags follow the repo's independent traditional semver line, for example `v1.19.9` → `v1.19.10`. They do not use the app calendar version.

### Summary

| Channel | Repo | Stable | Alpha | Beta |
|---|---|---|---|---|
| External | `opentrons-ot2` | `v26.6.0` | `v26.6.1-alpha.0` | `v26.6.1-beta.0` |
| External | `buildroot` | `v1.19.10` | patch bump on traditional line | patch bump on traditional line |
| Internal | both | `internal@26.5.2601` | `internal@26.5.2601-alpha` | `internal@26.5.2601-beta` |

Implementation lives in `automation/go.py` and `opentrons-ot2/scripts/ot2_calendar_semver.py`.
