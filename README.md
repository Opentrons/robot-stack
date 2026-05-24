# robot-stack

Tools to inspect, tag, and build Opentrons robots across the multi-repo software stack.

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

## Release Paths

`just go` runs `automation/go.py`, an interactive release helper. It supports two robot paths; **Flex is the default**.

| Path | Repos | App repo | Version scheme |
|---|---|---|---|
| **Flex** | `opentrons`, `oe-core`, `ot3-firmware` | `opentrons` | Semver (`v8.5.0`, alpha tags like `v8.5.0-alpha.6`) |
| **OT-2** | `opentrons-ot2`, `buildroot` | `opentrons-ot2` | Datever (`26.5.2401`) |

`robot-stack-infra` is always cloned and pulled for both paths as a reference repo. It is not included in release tables or tagging.

Each repo uses isolation branches named `chore_release-<version>` during a release cycle.

## OT-2 Datever

OT-2 releases do not share Flex semver. They use a date-based version: `YY.M.P`.

`P` encodes the calendar day and same-day release count:

```text
P = day * 100 + release_num
```

Patch width depends on the day:

| Day | Patch width | First release | Second release |
|---|---|---|---|
| 1-9 | 3 digits | `26.5.101` | `26.5.102` |
| 10-31 | 4 digits | `26.5.1001` | `26.5.1002` |
| 24 (example) | 4 digits | `26.5.2401` | `26.5.2402` |

- `release_num` runs from 1 to 99 for multiple releases on the same day
- External tags prefix with `v` (e.g. `v26.5.2401`)
- Internal tags prefix with `internal@` (e.g. `internal@26.5.2402`)

The fixed-width patch avoids ambiguity between single-digit and two-digit days (for example, day 1 `101` vs day 10 `1001`).

Implementation lives in `automation/go.py` (`encode_ot2_datever`, `decode_ot2_datever`).
