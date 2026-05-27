"""Generate release guide HTML pages for GitHub Pages."""

from __future__ import annotations

import html
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Tuple

from automation.asset_urls import APP_CHANNEL_YAMLS, app_manifest_url, app_yaml_url, robot_manifest_url
from automation.flex_urls import FLEX_EXTERNAL, FLEX_INTERNAL, FLEX_ROBOT_PREFIX
from automation.ot2_urls import OT2_EXTERNAL, OT2_INTERNAL, OT2_ROBOT_PREFIX

GUIDE_PAGES: Final[Tuple[str, ...]] = (
    "flex-external.html",
    "flex-internal.html",
    "ot2-external.html",
    "ot2-internal.html",
)


@dataclass(frozen=True)
class GuideLink:
    """One guide page in the site nav."""

    filename: str
    title: str


GUIDE_NAV: Final[Tuple[GuideLink, ...]] = (
    GuideLink("flex-external.html", "Flex external"),
    GuideLink("flex-internal.html", "Flex internal"),
    GuideLink("ot2-external.html", "OT-2 external"),
    GuideLink("ot2-internal.html", "OT-2 internal"),
)


def _page_css() -> str:
    """Return shared stylesheet for guide pages."""
    return """
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
    nav.guide-nav {
      display: flex;
      flex-wrap: wrap;
      gap: 0.5rem 1rem;
      margin: 1.25rem 0 2rem;
      padding: 0.75rem 1rem;
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 10px;
      font-size: 0.95rem;
    }
    nav.guide-nav a { color: var(--accent); text-decoration: none; }
    nav.guide-nav a:hover { text-decoration: underline; }
    nav.guide-nav a[aria-current="page"] { font-weight: 700; color: var(--text); }
    nav.guide-nav .home { margin-right: 0.5rem; }
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


def _render_nav(current: str) -> str:
    """Render guide navigation links."""
    links = ['<a class="home" href="index.html">Home</a>']
    for item in GUIDE_NAV:
        if item.filename == current:
            links.append(f'<a href="{html.escape(item.filename)}" aria-current="page">{html.escape(item.title)}</a>')
        else:
            links.append(f'<a href="{html.escape(item.filename)}">{html.escape(item.title)}</a>')
    return f'<nav class="guide-nav" aria-label="Release guides">{"".join(links)}</nav>'


def _wrap_page(filename: str, title: str, body: str) -> str:
    """Wrap guide body HTML in a full document."""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(title)}</title>
  <style>{_page_css()}</style>
</head>
<body>
  <main>
    {_render_nav(filename)}
    <h1>{html.escape(title)}</h1>
    {body}
  </main>
</body>
</html>
"""


def _tag_need_section() -> str:
    """Shared explanation of when go recommends a new tag."""
    return """
    <h2>When does <code>just go</code> say a new tag is needed?</h2>
    <p>For each repo, <code>automation/go.py</code> checks out
    <code>chore_release-&lt;version&gt;</code> when that branch exists on the remote.
    It finds the newest <strong>annotated</strong> tag on that branch for the selected channel
    (sorted by creator date, merged into the branch).</p>
    <div class="panel">
      <p><strong>New tag needed</strong> when the branch tip commit is not the same commit as
      that latest channel tag.</p>
      <p><strong>No new tag needed</strong> when branch HEAD already matches the latest channel tag.</p>
    </div>
    <p>Tags must be annotated (<code>git tag -a … -m 'chore(release): …'</code>) so
    <code>git tag -l --sort=-creatordate</code> reflects real release order.</p>
    <p>Pushing a tag triggers CI builds in the tagged repo. The app monorepo tag drives app
    artifacts; stack repo tags drive robot OS and firmware builds.</p>
    """


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
    Robot OS and firmware use their own tag lines in
    <a href="https://github.com/Opentrons/oe-core">oe-core</a> and
    <a href="https://github.com/Opentrons/ot3-firmware">ot3-firmware</a>.</p>

    <h2>Stack repos</h2>
    <table>
      <thead><tr><th>Repo</th><th>Role</th><th>External tag pattern</th></tr></thead>
      <tbody>
        <tr><td><code>opentrons</code></td><td>App (taggable)</td><td><code>vX.Y.Z</code>, alpha <code>vX.Y.Z-alpha.N</code></td></tr>
        <tr><td><code>oe-core</code></td><td>Flex robot OS</td><td><code>v0.X.Y</code> (independent semver line)</td></tr>
        <tr><td><code>ot3-firmware</code></td><td>Flex firmware</td><td><code>vN</code> integer counter</td></tr>
      </tbody>
    </table>

    <h2>Release branch</h2>
    <p>During a cycle, isolation branches are named <code>chore_release-&lt;version&gt;</code>
    (for example <code>chore_release-v9.1.0</code>) in each repo that participates in the release.</p>

    {_tag_need_section()}

    <h2>How the next tag is chosen</h2>
    <h3>App (<code>opentrons</code>)</h3>
    <ul>
      <li><strong>Stable:</strong> tag is exactly the base version, e.g. <code>v9.1.0</code>,
      if that tag does not already exist on the branch.</li>
      <li><strong>Alpha (unstable in <code>go</code>):</strong> find tags matching
      <code>v9.1.0-alpha.*</code> on the branch and increment <code>N</code>
      (first alpha is <code>v9.1.0-alpha.0</code>).</li>
    </ul>

    <h3>Robot OS (<code>oe-core</code>)</h3>
    <p>oe-core external versions are <em>not</em> the same as the app semver. Tags look like
    <code>v0.10.0</code> and often reference the robot-stack version in the tag message.</p>
    <p>When a new external tag is needed, <code>go</code> bumps the patch of the newest
    <code>v*</code> tag merged into the release branch (e.g. <code>v0.10.0</code> → <code>v0.10.1</code>).</p>

    <h3>Firmware (<code>ot3-firmware</code>)</h3>
    <p>External tags are simple integers: <code>v69</code>, <code>v70</code>, …</p>
    <p>When a new tag is needed, <code>go</code> takes the highest <code>vN</code> number merged
    into the branch and suggests <code>v(N+1)</code>.</p>

    <h2>Where to find published releases</h2>
    <p>External Flex artifacts live on <code>{html.escape(FLEX_EXTERNAL.app_host)}</code>.</p>
    <table>
      <thead><tr><th>Artifact</th><th>URL</th></tr></thead>
      <tbody>
        <tr><td>App manifest (informational)</td>
            <td><a href="{html.escape(app_json)}"><code>{html.escape(app_json)}</code></a></td></tr>
        <tr><td>Flex robot OS manifest</td>
            <td><a href="{html.escape(robot_json)}"><code>{html.escape(robot_json)}</code></a></td></tr>
      </tbody>
    </table>
    <p>Electron-updater channel YAMLs (authoritative for app update prompts):</p>
    {_yaml_links(FLEX_EXTERNAL.app_host)}
    <p>See also the live inventory: <a href="flex-assets.html">Flex release assets</a>.</p>

    <div class="alpha-beta">
      <h2>Alpha and beta on Flex external</h2>
      <p>In <code>just go</code>, choose <strong>Release type: external</strong> and
      <strong>Stability: unstable</strong> for alpha QA builds.</p>
      <table>
        <thead><tr><th>Stability</th><th>App tag example</th><th>Typical app YAML</th></tr></thead>
        <tbody>
          <tr><td>Stable</td><td><code>v9.1.0</code></td><td><code>latest.yml</code> (+ mac/linux)</td></tr>
          <tr><td>Alpha</td><td><code>v9.1.0-alpha.0</code>, <code>v9.1.0-alpha.1</code>, …</td><td><code>alpha.yml</code> (+ mac/linux)</td></tr>
          <tr><td>Beta</td><td><code>v9.1.0-beta.0</code> (manual; not computed by <code>go</code> today)</td><td><code>beta.yml</code> (+ mac/linux)</td></tr>
        </tbody>
      </table>
      <p>Alpha tags increment <code>.N</code> on a fixed base version during QA on
      <code>chore_release-*</code>. Beta follows the same semver prerelease pattern with a
      <code>-beta.N</code> suffix. Stable external releases drop the prerelease segment entirely.</p>
      <p>oe-core and ot3-firmware do not mirror the app alpha suffix; they use their own
      external tag schemes above when their release branches move ahead of the latest channel tag.</p>
    </div>
    """
    return _wrap_page("flex-external.html", "Flex external releases", body)


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
        <tr><td><code>opentrons</code></td><td>App (taggable)</td><td><code>ot3@X.Y.Z</code>, alpha <code>ot3@X.Y.Z-alpha.N</code></td></tr>
        <tr><td><code>oe-core</code></td><td>Flex robot OS</td><td><code>internal@X.Y.Z</code>, alpha <code>internal@X.Y.Z-alpha.N</code></td></tr>
        <tr><td><code>ot3-firmware</code></td><td>Flex firmware</td><td><code>internal@vN</code> integer counter</td></tr>
      </tbody>
    </table>

    <h2>Release branch</h2>
    <p>Same isolation branch convention: <code>chore_release-&lt;version&gt;</code>.</p>

    {_tag_need_section()}

    <h2>How the next tag is chosen</h2>
    <h3>App (<code>opentrons</code>)</h3>
    <ul>
      <li><strong>Stable:</strong> <code>ot3@X.Y.Z</code> if not already on the branch.</li>
      <li><strong>Alpha (unstable):</strong> increment <code>ot3@X.Y.Z-alpha.N</code> from existing tags on the branch.</li>
    </ul>

    <h3>Robot OS (<code>oe-core</code>)</h3>
    <p>Internal tags use the <code>internal@</code> prefix without a leading <code>v</code>.
    The base version (e.g. <code>3.0.0</code>) comes from the newest <code>internal@</code> tag on the branch.</p>
    <ul>
      <li><strong>Alpha (unstable):</strong> <code>internal@3.0.0-alpha.N</code>, increment <code>N</code>.</li>
      <li><strong>Stable:</strong> <code>internal@3.0.0</code>, or patch bump if that exact tag already exists.</li>
    </ul>

    <h3>Firmware (<code>ot3-firmware</code>)</h3>
    <p>Internal tags look like <code>internal@v26</code>, <code>internal@v27</code>.
    When needed, <code>go</code> suggests one higher than the max merged tag number.</p>

    <h2>Where to find published releases</h2>
    <p>Internal Flex artifacts live on <code>{html.escape(FLEX_INTERNAL.app_host)}</code>.</p>
    <table>
      <thead><tr><th>Artifact</th><th>URL</th></tr></thead>
      <tbody>
        <tr><td>App manifest (informational)</td>
            <td><a href="{html.escape(app_json)}"><code>{html.escape(app_json)}</code></a></td></tr>
        <tr><td>Flex robot OS manifest</td>
            <td><a href="{html.escape(robot_json)}"><code>{html.escape(robot_json)}</code></a></td></tr>
      </tbody>
    </table>
    <p>Electron-updater YAMLs for internal app builds use the same filenames under the internal host:</p>
    {_yaml_links(FLEX_INTERNAL.app_host)}
    <p>See also: <a href="flex-assets.html">Flex release assets</a>.</p>

    <div class="alpha-beta">
      <h2>Alpha and beta on Flex internal</h2>
      <p>In <code>just go</code>, choose <strong>Release type: internal</strong> and
      <strong>Stability: unstable</strong> for internal alpha builds.</p>
      <table>
        <thead><tr><th>Stability</th><th>App tag example</th><th>oe-core example</th></tr></thead>
        <tbody>
          <tr><td>Stable internal</td><td><code>ot3@8.5.0</code> (uncommon)</td><td><code>internal@3.0.0</code></td></tr>
          <tr><td>Alpha</td><td><code>ot3@8.5.0-alpha.0</code></td><td><code>internal@3.0.0-alpha.0</code></td></tr>
          <tr><td>Beta</td><td><code>ot3@8.5.0-beta.0</code> (manual)</td><td><code>internal@3.0.0-beta.0</code> (manual)</td></tr>
        </tbody>
      </table>
      <p>Internal alpha uses the same <code>-alpha.N</code> increment rules as external, but with
      the <code>ot3@</code> and <code>internal@</code> prefixes. Beta prereleases follow
      <code>-beta.N</code> when you create them manually; <code>go</code> today focuses on stable
      vs alpha for Flex.</p>
    </div>
    """
    return _wrap_page("flex-internal.html", "Flex internal releases", body)


def render_ot2_external() -> str:
    """Render OT-2 external release guide body."""
    app_json = app_manifest_url(OT2_EXTERNAL)
    robot_json = robot_manifest_url(OT2_EXTERNAL, OT2_ROBOT_PREFIX)
    body = f"""
    <p class="lede">Customer-facing OT-2 releases. App and robot OS share the <strong>same version string</strong>
    across <a href="https://github.com/Opentrons/opentrons-ot2">opentrons-ot2</a> and
    <a href="https://github.com/Opentrons/buildroot">buildroot</a>.</p>

    <h2>Calendar semver (external)</h2>
    <p>Versions use US Eastern calendar components:</p>
    <table>
      <thead><tr><th>Part</th><th>Meaning</th><th>Example</th></tr></thead>
      <tbody>
        <tr><td>YY</td><td>Two-digit year</td><td><code>26</code> for 2026</td></tr>
        <tr><td>M</td><td>Month, no leading zero</td><td><code>6</code> for June</td></tr>
        <tr><td>N</td><td>Monthly stable counter, 0–9</td><td><code>0</code> = first stable that month</td></tr>
      </tbody>
    </table>
    <p>External tags use a <code>v</code> prefix: <code>v26.6.0</code>, <code>v26.6.1</code>, …</p>

    <h2>Stack repos</h2>
    <table>
      <thead><tr><th>Repo</th><th>Role</th><th>Tag pattern</th></tr></thead>
      <tbody>
        <tr><td><code>opentrons-ot2</code></td><td>App (taggable)</td><td><code>vYY.M.N</code> (+ alpha/beta prereleases)</td></tr>
        <tr><td><code>buildroot</code></td><td>OT-2 robot OS</td><td>Same version string as app</td></tr>
      </tbody>
    </table>

    <h2>Release branch</h2>
    <p><code>chore_release-&lt;version&gt;</code> where version is the calendar base, e.g.
    <code>chore_release-26.6.0</code> (no <code>v</code> prefix in the branch name).</p>

    {_tag_need_section()}

    <h2>How the next tag is chosen</h2>
    <p><code>go</code> prompts for a base calendar version (defaults to the current month in Eastern time).</p>
    <h3>Stable</h3>
    <p>Find stable external tags (<code>vYY.M.N</code> with no prerelease) for the same year and month.
    Increment <code>N</code>. More than 10 stable releases in one month (<code>N &gt; 9</code>) is treated as an error.</p>
    <h3>Alpha / beta</h3>
    <p>Prereleases stay on a fixed <code>YY.M.N</code> base. Increment the prerelease number:
    <code>v26.6.0-alpha.0</code>, <code>v26.6.0-alpha.1</code>, or <code>v26.6.0-beta.0</code>, etc.</p>
    <p><code>buildroot</code> uses the same next-tag logic and should receive the matching tag when its
    branch has commits since the latest channel tag.</p>

    <h2>Where to find published releases</h2>
    <p>External OT-2 artifacts live on <code>{html.escape(OT2_EXTERNAL.app_host)}</code>.</p>
    <table>
      <thead><tr><th>Artifact</th><th>URL</th></tr></thead>
      <tbody>
        <tr><td>App manifest</td>
            <td><a href="{html.escape(app_json)}"><code>{html.escape(app_json)}</code></a></td></tr>
        <tr><td>OT-2 robot OS manifest</td>
            <td><a href="{html.escape(robot_json)}"><code>{html.escape(robot_json)}</code></a></td></tr>
      </tbody>
    </table>
    <p>App update YAMLs:</p>
    <ul>
      <li><a href="{html.escape(app_yaml_url(OT2_EXTERNAL, "alpha.yml"))}"><code>alpha.yml</code></a></li>
      <li><a href="{html.escape(app_yaml_url(OT2_EXTERNAL, "beta.yml"))}"><code>beta.yml</code></a></li>
      <li><a href="{html.escape(app_yaml_url(OT2_EXTERNAL, "latest.yml"))}"><code>latest.yml</code></a></li>
    </ul>
    <p>See also: <a href="ot2-assets.html">OT-2 release assets</a>.</p>

    <div class="alpha-beta">
      <h2>Alpha and beta on OT-2 external</h2>
      <p>In <code>just go</code>, choose <strong>Release type: external</strong> and
      <strong>Stability: alpha</strong> or <strong>beta</strong>.</p>
      <table>
        <thead><tr><th>Stability</th><th>Tag example</th><th>Notes</th></tr></thead>
        <tbody>
          <tr><td>Stable</td><td><code>v26.6.0</code>, <code>v26.6.1</code></td><td>Monthly counter <code>N</code> bumps; app and buildroot match</td></tr>
          <tr><td>Alpha</td><td><code>v26.6.0-alpha.0</code>, <code>v26.6.0-alpha.1</code></td><td>Fixed base; increment prerelease number</td></tr>
          <tr><td>Beta</td><td><code>v26.6.0-beta.0</code></td><td>Same pattern as alpha with <code>-beta.N</code></td></tr>
        </tbody>
      </table>
      <p>Alpha and beta do <em>not</em> advance the monthly stable counter <code>N</code>.
      QA cycles reuse the same <code>YY.M.N</code> base until you ship a stable external release.</p>
    </div>
    """
    return _wrap_page("ot2-external.html", "OT-2 external releases", body)


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

    <h2>Release branch</h2>
    <p><code>chore_release-&lt;version&gt;</code> using the internal base version, e.g.
    <code>chore_release-26.5.2601</code>.</p>

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

    <h2>Where to find published releases</h2>
    <p>Internal OT-2 artifacts live on <code>{html.escape(OT2_INTERNAL.app_host)}</code>.</p>
    <table>
      <thead><tr><th>Artifact</th><th>URL</th></tr></thead>
      <tbody>
        <tr><td>App manifest</td>
            <td><a href="{html.escape(app_json)}"><code>{html.escape(app_json)}</code></a></td></tr>
        <tr><td>OT-2 robot OS manifest</td>
            <td><a href="{html.escape(robot_json)}"><code>{html.escape(robot_json)}</code></a></td></tr>
      </tbody>
    </table>
    <p>See also: <a href="ot2-assets.html">OT-2 release assets</a>.</p>

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
      (<code>-alpha.0</code>, <code>-alpha.1</code>) on a fixed monthly base, while internal uses
      unnumbered <code>-alpha</code> / <code>-beta</code> suffixes combined with the
      day/build patch scheme.</p>
    </div>
    """
    return _wrap_page("ot2-internal.html", "OT-2 internal releases", body)


def publish_release_guides(output_dir: Path) -> None:
    """Write all release guide HTML files under output_dir."""
    output_dir.mkdir(parents=True, exist_ok=True)
    pages = {
        "flex-external.html": render_flex_external(),
        "flex-internal.html": render_flex_internal(),
        "ot2-external.html": render_ot2_external(),
        "ot2-internal.html": render_ot2_internal(),
    }
    for filename, content in pages.items():
        path = output_dir / filename
        path.write_text(content, encoding="utf-8")
        print(f"Wrote {path.resolve()}")
