"""Generate release guide HTML pages for GitHub Pages."""

from __future__ import annotations

import html
from pathlib import Path
from typing import Final, Tuple

from automation.asset_urls import APP_CHANNEL_YAMLS, app_manifest_url, robot_manifest_url
from automation.flex_urls import FLEX_EXTERNAL, FLEX_INTERNAL, FLEX_ROBOT_PREFIX
from automation.ot2_urls import OT2_EXTERNAL, OT2_INTERNAL, OT2_ROBOT_PREFIX
from automation.site_nav import GUIDE_NAV, render_site_header, robot_name_html, site_nav_css

GUIDE_PAGES: Final[Tuple[str, ...]] = tuple(item.filename for item in GUIDE_NAV)


def _manifest_authority_note() -> str:
    """Short note on which published manifests are authoritative."""
    return """
    <p class="note">
      Robot <code>releases.json</code> is the source of truth for on-robot updates.
      Desktop app updates use channel YAMLs (<code>latest.yml</code>, prerelease YAMLs) via
      electron-updater; those YAMLs are authoritative.
      App <code>releases.json</code> is parsed by a CloudFront edge function to pick the latest stable
      semver from production and route <code>latest*</code> requests accordingly.
    </p>
    """


def _tooling_model_section() -> str:
    """Explain advisory robot-stack scripts (matches README and workspace rules)."""
    return """
    <h2>Robot-stack tooling</h2>
    <p><code>just go</code>, <code>just track-builds</code>, <code>just invalidate-cloudfront</code>,
    and <code>just verify-release-assets</code> are <strong>advisory</strong>: they sync local clones under
    this workspace, print tables and analysis, and emit copy-paste commands. A human (or agent) runs
    <code>git tag -a</code> and <code>git push</code> elsewhere. CloudFront invalidation runs only when
    the operator passes <code>--execute</code> to <code>just invalidate-cloudfront</code>. Nothing here
    pushes tags or triggers CI by itself.</p>
    <p><code>robot-stack-infra</code> is always cloned for reference; it is not included in release
    tagging tables.</p>
    <p>Plan a release non-interactively, for example:</p>
    <pre>just go --non-interactive --skip-assumptions --path flex --release-type external --stability stable</pre>
    """


def _default_branches_table(path: str) -> str:
    """Render default branches for one robot path."""
    if path == "flex":
        rows = """
        <tr><td><code>opentrons</code></td><td><code>edge</code></td></tr>
        <tr><td><code>oe-core</code></td><td><code>main</code></td></tr>
        <tr><td><code>ot3-firmware</code></td><td><code>main</code></td></tr>"""
    else:
        rows = """
        <tr><td><code>opentrons-ot2</code></td><td><code>edge</code></td></tr>
        <tr><td><code>buildroot</code></td><td><code>opentrons-develop</code></td></tr>"""
    return f"""
    <table>
      <thead><tr><th>Repo</th><th>Default branch</th></tr></thead>
      <tbody>{rows}</tbody>
    </table>
    """


def _release_branch_section(path: str, channel: str) -> str:
    """Describe which git branch go tags for this path and channel."""
    branches = _default_branches_table(path)
    if path == "flex" and channel == "external":
        return f"""
    <h2>Release branch</h2>
    <p>Flex <strong>external</strong> defaults to isolation branches
    <code>chore_release-&lt;version&gt;</code> (for example <code>chore_release-9.1.0</code>, without a
    <code>v</code> prefix in the branch name) when that branch exists on the remote after
    <code>just go</code> syncs repos. Otherwise <code>go</code> uses each repo&apos;s default branch.
    Override with <code>--app-branch</code> and <code>--stack-branch REPO=BRANCH</code> when a flavor
    ships from a different branch (for example <code>chore_release-10.0.0-beta</code>).
    Suggested tag commands include <code>git checkout &lt;release-branch&gt;</code> before
    <code>git tag -a</code> when that branch is not the repo default.</p>
    {branches}
    <p>Default version inference: highest <code>chore_release-X.Y.Z</code> on <code>opentrons</code>,
    with fallback to the latest merged <code>v*</code> tag base.</p>
    """
    if path == "flex":
        return f"""
    <h2>Release branch</h2>
    <p>Flex <strong>internal</strong> defaults to each repo&apos;s default branch
    (<code>opentrons</code>: <code>edge</code>; <code>oe-core</code> / <code>ot3-firmware</code>:
    <code>main</code>). Override with <code>--app-branch</code> and
    <code>--stack-branch REPO=BRANCH</code> when a release flavor ships from a named branch.</p>
    {branches}
    <p>Default version inference: highest <code>ot3@X.Y.Z</code> base in the app repo tag catalog.</p>
    """
    return f"""
    <h2>Release branch</h2>
    <p>OT-2 <strong>{html.escape(channel)}</strong> tags <strong>default-branch HEAD</strong>. No
    <code>chore_release</code> branch is used.</p>
    {branches}
    """


def _tag_need_section() -> str:
    """Shared explanation of when go recommends a new tag (matches go.py)."""
    return """
    <h2>When does <code>just go</code> say a new tag is needed?</h2>
    <p>For each repo, <code>automation/go.py</code> uses the <strong>release branch</strong> described
    above and the coordinated stack tag for the selected stability lane. It compares branch tip commit
    to whether that coordinated tag already points at HEAD.</p>
    <div class="panel">
      <p><strong>New tag needed</strong> when the coordinated tag for this release is missing on the
      branch or branch HEAD has moved since that tag.</p>
      <p><strong>No new tag needed</strong> when branch HEAD already matches the coordinated tag.</p>
    </div>
    <p>Flex app tag numbers come from the <strong>app monorepo tag catalog</strong>
    (<code>opentrons</code> or <code>opentrons-ot2</code>). At one semver base, stable, alpha, and beta
    are <strong>independent lanes</strong> (for example <code>ot3@4.0.0-alpha.3</code> and
    <code>ot3@4.0.0-beta.0</code> can coexist). Change logs compare against the prior tag in the
    <strong>same lane</strong> on the release branch.</p>
    <p>Tags must be annotated (<code>git tag -a … -m 'chore(release): …'</code>).
    When the release branch differs from the repo default, tag blocks print
    <code>git checkout &lt;release-branch&gt;</code> first.</p>
    <p>Pushing a tag triggers CI builds in the tagged repo. The app monorepo tag drives app
    artifacts; stack repo tags drive robot OS and firmware builds.</p>
    """


def _page_css() -> str:
    """Return shared stylesheet for guide pages."""
    # site_nav_css must come first so @import is not ignored (CSS requires @import at the top).
    return (
        site_nav_css()
        + """
    :root {
      color-scheme: light dark;
      --bg: #0f1419;
      --panel: #1a222d;
      --text: #e7ecf3;
      --muted: #9aa7b8;
      --accent: #60a5fa;
      --border: #2b3645;
      --code-bg: #111820;
    }
    @media (prefers-color-scheme: light) {
      :root {
        --bg: #f6f8fb;
        --panel: #ffffff;
        --text: #1f2937;
        --muted: #6b7280;
        --accent: #2563eb;
        --border: #d1d5db;
        --code-bg: #f3f4f6;
      }
    }
    body {
      margin: 0;
      font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif;
      background: var(--bg);
      color: var(--text);
      line-height: 1.6;
    }
    main {
      max-width: 860px;
      margin: 0 auto;
      padding: 2rem 1.25rem 4rem;
    }
    h1 { margin-top: 0; line-height: 1.25; }
    h2 {
      margin-top: 2.25rem;
      padding-top: 0.5rem;
      border-top: 1px solid var(--border);
    }
    h3 { margin-top: 1.5rem; }
    p, li { color: var(--text); }
    .lede { color: var(--muted); font-size: 1.05rem; }
    .note { color: var(--muted); font-size: 0.95rem; }
    """
        + """
    table {
      width: 100%;
      border-collapse: collapse;
      margin: 1rem 0;
      font-size: 0.95rem;
    }
    th, td {
      border: 1px solid var(--border);
      padding: 0.55rem 0.75rem;
      text-align: left;
      vertical-align: top;
    }
    th { background: var(--panel); }
    code {
      font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
      font-size: 0.9em;
      background: var(--code-bg);
      padding: 0.1em 0.35em;
      border-radius: 4px;
    }
    pre {
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 1rem;
      overflow-x: auto;
      font-size: 0.88rem;
    }
    a { color: var(--accent); }
    ul { padding-left: 1.25rem; }
    .panel {
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 1rem 1.25rem;
      margin: 1rem 0;
    }
    .alpha-beta {
      background: var(--panel);
      border: 1px solid var(--accent);
      border-radius: 10px;
      padding: 1.25rem 1.5rem;
      margin-top: 2.5rem;
    }
    .alpha-beta h2 {
      margin-top: 0;
      border-top: none;
      padding-top: 0;
    }
    """
    )


def _wrap_page(filename: str, title: str, body: str, *, robot_name: str = "") -> str:
    """Wrap guide body HTML in a full document."""
    document_title = f"{robot_name} {title}" if robot_name else title
    if robot_name:
        heading = f"<h1>{robot_name_html(robot_name)} {html.escape(title)}</h1>"
    else:
        heading = f"<h1>{html.escape(title)}</h1>"
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(document_title)}</title>
  <style>{_page_css()}</style>
</head>
<body>
  {render_site_header(filename)}
  <main>
    {heading}
    {body}
  </main>
</body>
</html>
"""


def _tag_push_order_section(robot: str) -> str:
    """Explain annotated tag push order for one robot path."""
    if robot == "flex":
        rows = """
        <tr><td>1</td><td><code>ot3-firmware</code></td><td>Firmware, if a new tag is needed</td></tr>
        <tr><td>2</td><td><code>oe-core</code></td><td>Robot OS, if a new tag is needed</td></tr>
        <tr><td>3</td><td><code>opentrons</code></td><td>App monorepo, always last</td></tr>"""
        path_label = "Flex"
    else:
        rows = """
        <tr><td>1</td><td><code>buildroot</code></td><td>Robot OS, if a new tag is needed</td></tr>
        <tr><td>2</td><td><code>opentrons-ot2</code></td><td>App monorepo, always last</td></tr>"""
        path_label = "OT-2"
    return f"""
    <h2>Tag push order</h2>
    <p>Push annotated tags in this order. Dependent stack repos first, app monorepo last.
    <code>just go</code> prints this reminder at the end of a release run.</p>
    <table>
      <thead><tr><th>Step</th><th>Repo</th><th>Notes</th></tr></thead>
      <tbody>{rows}</tbody>
    </table>
    <p>{path_label} stack repos only get a new tag when their release branch tip is ahead of the
    latest channel tag on that branch.</p>
    """


def _track_builds_section(robot: str, example_tag: str, slack_robot_label: str) -> str:
    """Explain just track-builds for one robot path."""
    path_flag = html.escape(robot)
    tag = html.escape(example_tag)
    slack_label = html.escape(slack_robot_label)
    robot_repo = "buildroot" if robot == "ot2" else "oe-core"
    return f"""
    <h2>Track release builds</h2>
    <p>After pushing the app tag, run (non-interactive form):</p>
    <pre>just track-builds --non-interactive --path {path_flag} --tag {tag} --wait</pre>
    <p><code>automation/track_builds.py</code> locates GitHub Actions runs for:</p>
    <ol>
      <li>App workflow on the monorepo (<code>App test, build, and deploy</code>)</li>
      <li>Kickoff cross-repo dispatch (<code>{"Start OT-2 build" if robot == "ot2" else "Start Flex build"}</code>)</li>
      <li>Robot OS build in <code>{robot_repo}</code></li>
    </ol>
    <p>The Rich table lists key jobs (deploy, desktop builds, dispatch spawn, robot image build).
    The Slack copy block includes only two links:</p>
    <pre>{"OT-2" if robot == "ot2" else "Flex"} release `{tag}`

- app: &lt;app workflow run URL&gt;
- {slack_label}: &lt;robot OS workflow run URL&gt;</pre>
    <p><strong><code>--wait</code></strong> polls every 15 seconds until app, kickoff, and robot OS
    workflow runs all appear (default timeout 900 seconds). Polling checks workflow runs only; job
    details are fetched afterward with retries for transient GitHub 404s. Exit code <code>2</code> if
    a run is still missing after the timeout.</p>
    """


def _invalidate_cloudfront_section(robot: str, example_tag: str) -> str:
    """Explain just invalidate-cloudfront (manual step; CI does not invalidate)."""
    path_flag = html.escape(robot)
    tag = html.escape(example_tag)
    robot_prefix = "ot2-br" if robot == "ot2" else "ot3-oe"
    return f"""
    <h2>CloudFront invalidation</h2>
    <p>CI does <strong>not</strong> invalidate CloudFront automatically. After builds finish, run
    invalidation and wait for completion (omit <code>--execute</code> to print the AWS command only):</p>
    <pre>just invalidate-cloudfront --non-interactive --path {path_flag} --tag {tag} --execute --wait</pre>
    <p>Invalidates <code>/app/*</code> and <code>/{robot_prefix}/*</code> on the channel host.
    Uses AWS profile <code>robotics_robot_stack_prod-admin</code> when credentials allow distribution
    lookup; otherwise the script prints a lookup command and placeholder ID.</p>
    """


def _validate_assets_section(path: str) -> str:
    """Point to tag verification and live asset inventory pages."""
    if path == "flex":
        external_page = "flex-external-assets.html"
        internal_page = "flex-internal-assets.html"
        example_tag = "ot3@8.5.0"
    else:
        external_page = "ot2-external-assets.html"
        internal_page = "ot2-internal-assets.html"
        example_tag = "internal@26.5.2601"
    return f"""
    <h2>Validate published artifacts</h2>
    <p>Verify manifests, updater YAMLs, and artifact URLs for the release tag:</p>
    <pre>just verify-release-assets --non-interactive --path {html.escape(path)} --tag {html.escape(example_tag)}</pre>
    <p>Optionally regenerate live manifest inventories:</p>
    <pre>just assets-pages</pre>
    <p>Or per-platform reports: <code>just flex-assets</code> / <code>just ot2-assets</code>.
    Pages: <a href="{html.escape(external_page)}">external assets</a>,
    <a href="{html.escape(internal_page)}">internal assets</a>.</p>
    """


def _post_tag_workflow_sections(robot: str, example_tag: str, slack_robot_label: str) -> str:
    """Track builds, CloudFront invalidation, and asset validation."""
    return (
        _track_builds_section(robot, example_tag, slack_robot_label)
        + _invalidate_cloudfront_section(robot, example_tag)
        + _validate_assets_section(robot)
    )


def _yaml_links(channel_host: str) -> str:
    """Render electron-updater YAML links for a host."""
    items = []
    for name in APP_CHANNEL_YAMLS:
        url = f"https://{channel_host}/app/{name}"
        items.append(f'<li><a href="{html.escape(url)}"><code>{html.escape(name)}</code></a></li>')
    return f"<ul>{''.join(items)}</ul>"


def render_flex_external() -> str:
    """Render Flex external release guide body."""
    app_json = app_manifest_url(FLEX_EXTERNAL)
    robot_json = robot_manifest_url(FLEX_EXTERNAL, FLEX_ROBOT_PREFIX)
    body = f"""
    <p class="lede">Customer-facing Flex releases. App tags use a <code>v</code> prefix in
    <a href="https://github.com/Opentrons/opentrons">opentrons</a>.
    <a href="https://github.com/Opentrons/oe-core">oe-core</a> uses the same stack tag.
    <a href="https://github.com/Opentrons/ot3-firmware">ot3-firmware</a> uses an <code>ex*</code>
    coordination tag mapped from the stack <code>v*</code> tag, plus an integer <code>vN</code>
    version tag on the same commit.</p>

    <h2>Stack repos</h2>
    <table>
      <thead><tr><th>Repo</th><th>Role</th><th>External tag pattern</th></tr></thead>
      <tbody>
        <tr><td><code>opentrons</code></td><td>App (taggable)</td><td><code>vX.Y.Z</code>, alpha <code>vX.Y.Z-alpha.N</code>, beta <code>vX.Y.Z-beta.N</code></td></tr>
        <tr><td><code>oe-core</code></td><td>Flex robot OS</td><td>Same stack tag as app (e.g. <code>v10.0.0-beta.0</code>)</td></tr>
        <tr><td><code>ot3-firmware</code></td><td>Flex firmware</td><td><code>exX.Y.Z…</code> coordination tag + integer <code>vN</code> on same commit</td></tr>
      </tbody>
    </table>

    {_tooling_model_section()}

    {_release_branch_section("flex", "external")}

    {_tag_need_section()}

    <h2>How the next tag is chosen</h2>
    <h3>App (<code>opentrons</code>)</h3>
    <ul>
      <li><strong>Stable:</strong> tag is exactly the base version, e.g. <code>v9.1.0</code>,
      if that tag does not already exist on the branch.</li>
      <li><strong>Alpha:</strong> find tags matching
      <code>v9.1.0-alpha.*</code> on the branch and increment <code>N</code>
      (first alpha is <code>v9.1.0-alpha.0</code>).</li>
      <li><strong>Beta:</strong> increment <code>v9.1.0-beta.N</code> (VM isolation train).</li>
    </ul>

    <h3>Robot OS (<code>oe-core</code>)</h3>
    <p>Uses the same stack tag as the app (for example <code>v9.1.0-alpha.7</code>).</p>

    <h3>Firmware (<code>ot3-firmware</code>)</h3>
    <p>Dual-tag when the release commit does not already have an integer <code>vN</code> version tag.
    CI checks out the <code>ex*</code> coordination tag; cmake reads the co-located <code>vN</code>.
    Do not use semver <code>v*</code> as the firmware coordination tag.</p>
    <pre><code>git tag -a v70 -m "Flex firmware v70"
git tag -a ex9.1.0-alpha.7 -m "Coordinated release marker"
git push origin v70 ex9.1.0-alpha.7</code></pre>
    <p>Before pushing the app tag, run
    <code>just validate-release-tags --tag &lt;app-tag&gt;</code>.</p>

    {_tag_push_order_section("flex")}

    {_post_tag_workflow_sections("flex", "v9.1.0", "flex")}

    <h2>Where to find published releases</h2>
    <p>External Flex artifacts live on <code>{html.escape(FLEX_EXTERNAL.app_host)}</code>.</p>
    <table>
      <thead><tr><th>Artifact</th><th>URL</th></tr></thead>
      <tbody>
        <tr><td>App <code>releases.json</code></td>
            <td><a href="{html.escape(app_json)}"><code>{html.escape(app_json)}</code></a></td></tr>
        <tr><td>Robot <code>releases.json</code> (source of truth)</td>
            <td><a href="{html.escape(robot_json)}"><code>{html.escape(robot_json)}</code></a></td></tr>
      </tbody>
    </table>
    {_manifest_authority_note()}
    <p>Electron-updater channel YAMLs:</p>
    {_yaml_links(FLEX_EXTERNAL.app_host)}
    <p>See also the live inventory: <a href="flex-external-assets.html">Flex external assets</a>.</p>

    <div class="alpha-beta">
      <h2>Alpha and beta on Flex external</h2>
      <p>In <code>just go</code>, choose <strong>Release type: external</strong> and
      <strong>Stability: alpha</strong> or <strong>beta</strong> for prerelease QA builds.</p>
      <table>
        <thead><tr><th>Stability</th><th>App tag example</th><th>Typical app YAML</th></tr></thead>
        <tbody>
          <tr><td>Stable</td><td><code>v9.1.0</code></td><td><code>latest.yml</code> (+ mac/linux)</td></tr>
          <tr><td>Alpha</td><td><code>v9.1.0-alpha.0</code>, <code>v9.1.0-alpha.1</code>, …</td><td><code>alpha.yml</code> (+ mac/linux)</td></tr>
          <tr><td>Beta</td><td><code>v9.1.0-beta.0</code>, <code>v9.1.0-beta.1</code>, …</td><td><code>beta.yml</code> (+ mac/linux)</td></tr>
        </tbody>
      </table>
      <p>Alpha and beta are <strong>independent lanes</strong> at the same semver base; each
      increments its own <code>.N</code> from the app repo tag catalog. Compare ranges use the
      prior tag in the same lane merged into the release branch. Stable external releases drop the
      prerelease segment entirely.</p>
      <p><strong>Desktop updater YAML (publish order, not tag order):</strong> beta builds overwrite
      <code>beta.yml</code> and <code>alpha.yml</code>; alpha builds update <code>alpha.yml</code>
      only and do not change <code>beta.yml</code>. When both channels need fresh builds in one
      cycle, publish beta desktop builds first, then alpha to restore <code>alpha.yml</code>.</p>
      <p><code>oe-core</code> uses the same stack tag as the app.
      <code>ot3-firmware</code> uses <code>ex*</code> mapped from the stack tag (for example
      <code>v9.1.0-beta.0</code> → <code>ex9.1.0-beta.0</code>) plus integer <code>vN</code>.
      Validate with <code>just validate-release-tags --tag &lt;app-tag&gt;</code> before pushing
      the app tag. See <a href="flex-coordinated-tags.html">coordinated tagging</a> and
      <a href="release-channel-hierarchy.html">release channel hierarchy</a>.</p>
    </div>
    """
    return _wrap_page("flex-external.html", "external releases", body, robot_name="Flex")


def render_flex_internal() -> str:
    """Render Flex internal release guide body."""
    app_json = app_manifest_url(FLEX_INTERNAL)
    robot_json = robot_manifest_url(FLEX_INTERNAL, FLEX_ROBOT_PREFIX)
    body = f"""
    <p class="lede">Internal Flex builds for Opentrons staff and early validation.
    App tags use an <code>ot3@</code> prefix in
    <a href="https://github.com/Opentrons/opentrons">opentrons</a>.</p>

    <h2>Stack repos</h2>
    <table>
      <thead><tr><th>Repo</th><th>Role</th><th>Internal tag pattern</th></tr></thead>
      <tbody>
        <tr><td><code>opentrons</code></td><td>App (taggable)</td><td><code>ot3@X.Y.Z</code>, alpha <code>ot3@X.Y.Z-alpha.N</code>, beta <code>ot3@X.Y.Z-beta.N</code></td></tr>
        <tr><td><code>oe-core</code></td><td>Flex robot OS</td><td>Same coordinated tag as app (e.g. <code>ot3@X.Y.Z-beta.N</code>)</td></tr>
        <tr><td><code>ot3-firmware</code></td><td>Flex firmware</td><td>Same <code>ot3@*</code> as app + integer <code>vN</code> on same commit</td></tr>
      </tbody>
    </table>

    {_tooling_model_section()}

    {_release_branch_section("flex", "internal")}

    {_tag_need_section()}

    <h2>How the next tag is chosen</h2>
    <p>In <code>just go</code>, Flex uses <strong>Stability: stable</strong>,
    <strong>alpha</strong>, or <strong>beta</strong>.</p>
    <h3>App (<code>opentrons</code>)</h3>
    <ul>
      <li><strong>Stable:</strong> <code>ot3@X.Y.Z</code> if not already in the app repo; otherwise patch bump
      (e.g. <code>ot3@8.5.0</code> → <code>ot3@8.5.1</code>).</li>
      <li><strong>Alpha:</strong> increment <code>ot3@X.Y.Z-alpha.N</code> from existing alpha tags at that base
      in the app repo (first alpha is <code>ot3@8.5.0-alpha.0</code>).</li>
      <li><strong>Beta:</strong> increment <code>ot3@X.Y.Z-beta.N</code> from existing beta tags at that base.
      Alpha and beta are independent lanes: <code>ot3@4.0.0-alpha.3</code> and
      <code>ot3@4.0.0-beta.0</code> can coexist.</li>
      <li>Change logs compare against the prior tag in the <strong>same lane</strong> on the release branch.</li>
    </ul>

    <h3>Robot OS (<code>oe-core</code>)</h3>
    <p>Uses the same <code>ot3@*</code> stack tag as the app.</p>

    <h3>Firmware (<code>ot3-firmware</code>)</h3>
    <p>Tag the coordination marker on every release. Add a new integer <code>vN</code> only when
    the release commit does not already have one; <code>vN</code> must be globally unique in the
    firmware repo.</p>
    <pre><code>git tag -a v70 -m "Flex firmware v70"
git tag -a ot3@4.0.0-beta.0 -m "Coordinated release marker"
git push origin v70 ot3@4.0.0-beta.0</code></pre>
    <p>Before pushing the app tag, run
    <code>just validate-release-tags --tag &lt;app-tag&gt;</code>.</p>

    {_tag_push_order_section("flex")}

    {_post_tag_workflow_sections("flex", "ot3@8.5.0-alpha.0", "flex")}

    <h2>Where to find published releases</h2>
    <p>Internal Flex artifacts live on <code>{html.escape(FLEX_INTERNAL.app_host)}</code>.</p>
    <table>
      <thead><tr><th>Artifact</th><th>URL</th></tr></thead>
      <tbody>
        <tr><td>App <code>releases.json</code></td>
            <td><a href="{html.escape(app_json)}"><code>{html.escape(app_json)}</code></a></td></tr>
        <tr><td>Robot <code>releases.json</code> (source of truth)</td>
            <td><a href="{html.escape(robot_json)}"><code>{html.escape(robot_json)}</code></a></td></tr>
      </tbody>
    </table>
    {_manifest_authority_note()}
    <p>Electron-updater YAMLs for internal app builds use the same filenames under the internal host:</p>
    {_yaml_links(FLEX_INTERNAL.app_host)}
    <p>See also: <a href="flex-internal-assets.html">Flex internal assets</a>.</p>

    <div class="alpha-beta">
      <h2>Alpha and beta on Flex internal</h2>
      <p>In <code>just go</code>, choose <strong>Release type: internal</strong> and
      <strong>Stability: alpha</strong> or <strong>beta</strong>. At one semver base, alpha and beta
      are <strong>independent release flavors</strong> with separate counters, not a strict
      promote-alpha-to-beta ladder.</p>
      <p>Stack tags on <code>opentrons</code> and <code>oe-core</code> match the app.
      <code>ot3-firmware</code> uses the same <code>ot3@*</code> coordination tag plus integer
      <code>vN</code>. Validate with <code>just validate-release-tags --tag &lt;app-tag&gt;</code>.
      See <a href="flex-coordinated-tags.html">coordinated tagging</a> and
      <a href="release-channel-hierarchy.html">release channel hierarchy</a>.</p>
      <table>
        <thead><tr><th>Train</th><th>Stability</th><th>Tag example</th><th>Notes</th></tr></thead>
        <tbody>
          <tr><td>VM isolation</td><td>beta</td><td><code>ot3@4.0.0-beta.0</code></td><td>Beta app channel; beta counter at the base</td></tr>
          <tr><td>CRS</td><td>alpha</td><td><code>ot3@4.0.0-alpha.4</code></td><td>Alpha app channel; alpha counter at the base (can coexist with beta)</td></tr>
          <tr><td>Stable</td><td>stable</td><td><code>ot3@4.0.0</code></td><td>Same prompted base version</td></tr>
        </tbody>
      </table>
      <p>When both channels need updates in the <strong>same release cycle</strong>, publish desktop
      builds <strong>beta first, then alpha</strong>:</p>
      <ol>
        <li>Beta publish overwrites <code>beta.yml</code> and <code>alpha.yml</code> (alpha users
        temporarily see the beta build).</li>
        <li>Alpha publish restores <code>alpha.yml</code> only; <code>beta.yml</code> stays on beta.</li>
      </ol>
      <p>Git tag order can differ. YAML pointers follow the <strong>last desktop build
      publish</strong>. Beta without follow-up alpha leaves alpha-channel users on beta even when
      alpha artifacts remain in <code>releases.json</code> (for example
      <code>ot3@4.0.0-alpha.4</code> tagged before <code>ot3@4.0.0-beta.1</code>, but
      <code>alpha.yml</code> points at beta.1). See
      <a href="release-channel-hierarchy.html">release channel hierarchy</a> and
      <a href="flex-coordinated-tags.html">coordinated tagging reference</a>.</p>
      <p>Before pushing the app tag, run
      <code>just validate-release-tags --tag &lt;app-tag&gt;</code>.</p>
    </div>
    """
    return _wrap_page("flex-internal.html", "internal releases", body, robot_name="Flex")


def render_ot2_external() -> str:
    """Render OT-2 external release guide body."""
    app_json = app_manifest_url(OT2_EXTERNAL)
    robot_json = robot_manifest_url(OT2_EXTERNAL, OT2_ROBOT_PREFIX)
    body = f"""
    <p class="lede">Customer-facing OT-2 releases. The app uses calendar semver
    (<code>vYY.M.N</code>) in
    <a href="https://github.com/Opentrons/opentrons-ot2">opentrons-ot2</a>.
    Robot OS uses an independent traditional semver line (for example <code>v1.19.9</code>) in
    <a href="https://github.com/Opentrons/buildroot">buildroot</a>.</p>

    <h2>Calendar semver (external app)</h2>
    <p>Versions use US Eastern calendar components:</p>
    <table>
      <thead><tr><th>Part</th><th>Meaning</th><th>Example</th></tr></thead>
      <tbody>
        <tr><td>YY</td><td>Two-digit year</td><td><code>26</code> for 2026</td></tr>
        <tr><td>M</td><td>Month, no leading zero</td><td><code>6</code> for June</td></tr>
        <tr><td>N</td><td>Monthly build counter, 0–9</td><td><code>0</code> = first external build that month</td></tr>
      </tbody>
    </table>
    <p>External app tags use a <code>v</code> prefix: <code>v26.6.0</code>, <code>v26.6.1</code>, …</p>

    <h2>Stack repos</h2>
    <table>
      <thead><tr><th>Repo</th><th>Role</th><th>Tag pattern</th></tr></thead>
      <tbody>
        <tr><td><code>opentrons-ot2</code></td><td>App (taggable)</td><td><code>vYY.M.N</code> (+ alpha/beta prereleases)</td></tr>
        <tr><td><code>buildroot</code></td><td>OT-2 robot OS</td><td><code>vX.Y.Z</code> independent line (for example <code>v1.19.9</code>)</td></tr>
      </tbody>
    </table>

    {_tooling_model_section()}

    {_release_branch_section("ot2", "external")}

    {_tag_need_section()}

    <h2>How the next tag is chosen</h2>
    <p>In <code>just go</code>, OT-2 uses <strong>Stability: stable</strong>, <strong>alpha</strong>,
    or <strong>beta</strong>.</p>
    <p><code>go</code> infers the next calendar base from existing app tags on the release branch
    (defaults to the current month in Eastern time when no tags exist yet).</p>
    <h3>App stable</h3>
    <p>Patch <code>N</code> counts <strong>stable</strong> releases in the calendar month. If alpha or beta tags
    exist on a base but no stable tag yet (for example <code>v26.6.0-alpha.1</code>), the next stable reuses that
    base (<code>v26.6.0</code>) because stable outranks prereleases in semver. Otherwise bump <code>N</code> for the
    next stable in the month. More than 10 stable releases in one month (<code>N &gt; 9</code>) is treated as an error.</p>
    <h3>App alpha / beta</h3>
    <p>Alpha and beta use numbered prereleases on a monthly <code>YY.M.N</code> base. Increment
    <code>-alpha.N</code> or <code>-beta.N</code> on the same base during QA. After
    <code>v26.6.0</code> stable, start a new build line at the next <code>N</code>:
    <code>v26.6.1-alpha.0</code>, <code>v26.6.1-beta.0</code>, etc.</p>
    <h3>buildroot stable</h3>
    <p>Patch-bump from the latest merged traditional <code>v*</code> tag on
    <code>opentrons-develop</code> (for example <code>v1.19.9</code> → <code>v1.19.10</code>).
    Calendar app tags such as <code>v26.6.0</code> are ignored when choosing the next buildroot tag.</p>
    <p><code>buildroot</code> only receives a new tag when its branch is ahead of the latest traditional external tag.</p>

    {_tag_push_order_section("ot2")}

    {_post_tag_workflow_sections("ot2", "v26.6.0", "ot2")}

    <h2>Where to find published releases</h2>
    <p>External OT-2 artifacts live on <code>{html.escape(OT2_EXTERNAL.app_host)}</code>.</p>
    <table>
      <thead><tr><th>Artifact</th><th>URL</th></tr></thead>
      <tbody>
        <tr><td>App <code>releases.json</code></td>
            <td><a href="{html.escape(app_json)}"><code>{html.escape(app_json)}</code></a></td></tr>
        <tr><td>Robot <code>releases.json</code> (source of truth)</td>
            <td><a href="{html.escape(robot_json)}"><code>{html.escape(robot_json)}</code></a></td></tr>
      </tbody>
    </table>
    {_manifest_authority_note()}
    <p>Electron-updater channel YAMLs:</p>
    {_yaml_links(OT2_EXTERNAL.app_host)}
    <p>See also: <a href="ot2-external-assets.html">OT-2 external assets</a>.</p>

    <div class="alpha-beta">
      <h2>Alpha and beta on OT-2 external</h2>
      <p>In <code>just go</code>, choose <strong>Release type: external</strong> and
      <strong>Stability: alpha</strong> or <strong>beta</strong>.</p>
      <table>
        <thead><tr><th>Stability</th><th>Tag example</th><th>Notes</th></tr></thead>
        <tbody>
          <tr><td>Stable</td><td><code>v26.6.0</code>, <code>v26.6.1</code> (app)</td><td><code>N</code> bumps only for each stable release in the month; buildroot patch-bumps its own line (for example <code>v1.19.10</code>)</td></tr>
          <tr><td>Alpha</td><td><code>v26.6.0-alpha.0</code>, <code>v26.6.1-alpha.0</code></td><td>Same <code>N</code> as the build line; increment prerelease on the same base</td></tr>
          <tr><td>Beta</td><td><code>v26.6.0-beta.0</code></td><td>Same monthly <code>N</code> as alpha on that build line; increment <code>-beta.N</code> on the same base</td></tr>
        </tbody>
      </table>
      <p>Alpha and beta do not consume the stable <code>N</code> slot: <code>v26.6.0</code> stable can follow
      <code>v26.6.0-alpha.N</code> on the same base. After <code>v26.6.0</code> stable, the next alpha cycle is
      <code>v26.6.1-alpha.0</code>, not <code>v26.6.0-alpha.0</code>. QA cycles on the same base increment the
      prerelease number only. See <a href="release-channel-hierarchy.html">release channel hierarchy</a> for how alpha,
      beta, and stable updater YAMLs interact.</p>
    </div>
    """
    return _wrap_page("ot2-external.html", "external releases", body, robot_name="OT-2")


def render_ot2_internal() -> str:
    """Render OT-2 internal release guide body."""
    app_json = app_manifest_url(OT2_INTERNAL)
    robot_json = robot_manifest_url(OT2_INTERNAL, OT2_ROBOT_PREFIX)
    body = f"""
    <p class="lede">Internal OT-2 builds. App and robot OS share the same calendar version with an
    <code>internal@</code> tag prefix in both
    <a href="https://github.com/Opentrons/opentrons-ot2">opentrons-ot2</a> and
    <a href="https://github.com/Opentrons/buildroot">buildroot</a>.</p>

    <h2>Calendar semver (internal)</h2>
    <p>Same Eastern calendar year and month as external, but the patch encodes
    <strong>day + same-day build number</strong>:</p>
    <pre>DNN = day × 100 + build_num   (build_num is 1–99 per day)</pre>
    <p>Examples for May 26, 2026:</p>
    <table>
      <thead><tr><th>Tag</th><th>Meaning</th></tr></thead>
      <tbody>
        <tr><td><code>internal@26.5.2601</code></td><td>First stable internal build that day</td></tr>
        <tr><td><code>internal@26.5.2602</code></td><td>Second stable internal build same day</td></tr>
        <tr><td><code>internal@26.5.101</code></td><td>First stable internal build on May 1</td></tr>
      </tbody>
    </table>

    <h2>Stack repos</h2>
    <table>
      <thead><tr><th>Repo</th><th>Role</th><th>Tag pattern</th></tr></thead>
      <tbody>
        <tr><td><code>opentrons-ot2</code></td><td>App (taggable)</td><td><code>internal@YY.M.DNN</code></td></tr>
        <tr><td><code>buildroot</code></td><td>OT-2 robot OS</td><td>Same as app</td></tr>
      </tbody>
    </table>

    {_tooling_model_section()}

    {_release_branch_section("ot2", "internal")}

    {_tag_need_section()}

    <h2>How the next tag is chosen</h2>
    <p><code>go</code> defaults the base version to today’s Eastern date
    (<code>YY.M.DNN</code> with <code>build_num = 1</code>).</p>
    <h3>Stable internal</h3>
    <p>Collect tags for the same year, month, and day with no alpha/beta suffix.
    Set the next build number to <code>max(existing) + 1</code> (or <code>1</code> if none).</p>
    <h3>Alpha / beta internal</h3>
    <p>Same day and base patch, but tags gain a bare suffix: <code>-alpha</code> or <code>-beta</code>
    (not <code>-alpha.N</code>). Same-day rebuilds still increment <code>DNN</code> in the patch.</p>
    <p>Examples: <code>internal@26.5.2601-alpha</code>, <code>internal@26.5.2602-alpha</code>.</p>
    <p><code>buildroot</code> receives the matching tag when its branch is ahead of the latest internal tag.</p>

    {_tag_push_order_section("ot2")}

    {_post_tag_workflow_sections("ot2", "internal@26.5.2601", "ot2")}

    <h2>Where to find published releases</h2>
    <p>Internal OT-2 artifacts live on <code>{html.escape(OT2_INTERNAL.app_host)}</code>.</p>
    <table>
      <thead><tr><th>Artifact</th><th>URL</th></tr></thead>
      <tbody>
        <tr><td>App <code>releases.json</code></td>
            <td><a href="{html.escape(app_json)}"><code>{html.escape(app_json)}</code></a></td></tr>
        <tr><td>Robot <code>releases.json</code> (source of truth)</td>
            <td><a href="{html.escape(robot_json)}"><code>{html.escape(robot_json)}</code></a></td></tr>
      </tbody>
    </table>
    {_manifest_authority_note()}
    <p>Electron-updater YAMLs for internal app builds:</p>
    {_yaml_links(OT2_INTERNAL.app_host)}
    <p>See also: <a href="ot2-internal-assets.html">OT-2 internal assets</a>.</p>

    <div class="alpha-beta">
      <h2>Alpha and beta on OT-2 internal</h2>
      <p>In <code>just go</code>, choose <strong>Release type: internal</strong> and
      <strong>Stability: alpha</strong> or <strong>beta</strong>.</p>
      <table>
        <thead><tr><th>Stability</th><th>Tag example</th><th>Notes</th></tr></thead>
        <tbody>
          <tr><td>Stable</td><td><code>internal@26.5.2601</code></td><td>Same-day rebuilds bump <code>DNN</code></td></tr>
          <tr><td>Alpha</td><td><code>internal@26.5.2601-alpha</code></td><td>Bare <code>-alpha</code> suffix, not numbered</td></tr>
          <tr><td>Beta</td><td><code>internal@26.5.2601-beta</code></td><td>Bare <code>-beta</code> suffix</td></tr>
        </tbody>
      </table>
      <p>Internal alpha/beta differs from external OT-2: external uses numbered prereleases
      (<code>-alpha.0</code>, <code>-alpha.1</code>) on the monthly build base for that release, while internal uses
      unnumbered <code>-alpha</code> / <code>-beta</code> suffixes combined with the
      day/build patch scheme. See
      <a href="release-channel-hierarchy.html">release channel hierarchy</a> for updater channel
      behavior on Flex and OT-2.</p>
    </div>
    """
    return _wrap_page("ot2-internal.html", "internal releases", body, robot_name="OT-2")


def publish_release_guides(output_dir: Path) -> None:
    """Write all release guide HTML files under output_dir."""
    from automation.flex_release_strategy_docs import (
        render_flex_coordinated_tags_page,
        render_release_channel_hierarchy_page,
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    pages = {
        "flex-external.html": render_flex_external(),
        "flex-internal.html": render_flex_internal(),
        "ot2-external.html": render_ot2_external(),
        "ot2-internal.html": render_ot2_internal(),
        "flex-coordinated-tags.html": render_flex_coordinated_tags_page(),
        "release-channel-hierarchy.html": render_release_channel_hierarchy_page(),
    }
    for filename, content in pages.items():
        path = output_dir / filename
        path.write_text(content, encoding="utf-8")
        print(f"Wrote {path.resolve()}")
