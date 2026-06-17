"""Flex coordinated tagging and release sequencing documentation for GitHub Pages."""

from __future__ import annotations

import html
from typing import Final, Tuple

from automation.release_guides import _wrap_page

# One flavor: pipeline × stability with example tags per repo.
TagFlavor: Final = Tuple[str, str, str, str, str, str]
# pipeline (internal|external), stability, app_tag, oecore_tag, fw_coord_tag, fw_int_tag

TAG_FLAVORS: Final[Tuple[TagFlavor, ...]] = (
    (
        "internal",
        "stable",
        "ot3@8.5.0",
        "ot3@8.5.0",
        "ot3@8.5.0",
        "v70",
    ),
    (
        "internal",
        "beta",
        "ot3@8.5.0-beta.1",
        "ot3@8.5.0-beta.1",
        "ot3@8.5.0-beta.1",
        "v70",
    ),
    (
        "internal",
        "alpha",
        "ot3@8.5.0-alpha.4",
        "ot3@8.5.0-alpha.4",
        "ot3@8.5.0-alpha.4",
        "v70",
    ),
    (
        "external",
        "stable",
        "v10.0.0",
        "v10.0.0",
        "ex10.0.0",
        "v70",
    ),
    (
        "external",
        "beta",
        "v10.0.0-beta.1",
        "v10.0.0-beta.1",
        "ex10.0.0-beta.1",
        "v70",
    ),
    (
        "external",
        "alpha",
        "v10.0.0-alpha.2",
        "v10.0.0-alpha.2",
        "ex10.0.0-alpha.2",
        "v70",
    ),
)


def _strategy_diagram_css() -> str:
    """Extra stylesheet for coordinated-tag and sequencing diagrams."""
    return """
    .tag-grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 1.25rem;
      margin: 1.5rem 0 2rem;
    }
    @media (max-width: 720px) {
      .tag-grid { grid-template-columns: 1fr; }
    }
    .tag-card {
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 1rem 1rem 0.75rem;
      display: flex;
      flex-direction: column;
      gap: 0.5rem;
    }
    .tag-card header {
      display: flex;
      flex-wrap: wrap;
      gap: 0.4rem;
      align-items: center;
      margin-bottom: 0.35rem;
    }
    .pill {
      display: inline-block;
      font-size: 0.72rem;
      font-weight: 700;
      letter-spacing: 0.04em;
      text-transform: uppercase;
      padding: 0.2rem 0.55rem;
      border-radius: 999px;
      border: 1px solid var(--border);
    }
    .pill-channel-internal { background: #1e3a5f; color: #bfdbfe; border-color: #3b82f6; }
    .pill-channel-external { background: #3b2f1e; color: #fde68a; border-color: #d97706; }
    .pill-stable { background: #14532d; color: #bbf7d0; border-color: #22c55e; }
    .pill-beta { background: #4c1d95; color: #ddd6fe; border-color: #8b5cf6; }
    .pill-alpha { background: #713f12; color: #fde68a; border-color: #f59e0b; }
    @media (prefers-color-scheme: light) {
      .pill-channel-internal { background: #dbeafe; color: #1e40af; }
      .pill-channel-external { background: #fef3c7; color: #92400e; }
      .pill-stable { background: #dcfce7; color: #166534; }
      .pill-beta { background: #ede9fe; color: #5b21b6; }
      .pill-alpha { background: #fef3c7; color: #92400e; }
    }
    .flow-diagram {
      width: 100%;
      height: auto;
      display: block;
    }
    .flow-diagram text {
      font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
      font-size: 11px;
      fill: var(--text);
    }
    .flow-diagram .repo-label {
      font-family: ui-sans-serif, system-ui, sans-serif;
      font-size: 10px;
      font-weight: 600;
      fill: var(--muted);
    }
    .flow-diagram .box-app { fill: #1d4ed8; }
    .flow-diagram .box-os { fill: #047857; }
    .flow-diagram .box-fw-coord { fill: #7c3aed; }
    .flow-diagram .box-fw-int { fill: #b45309; }
    .flow-diagram .arrow { stroke: var(--muted); stroke-width: 1.5; fill: none; }
    @media (prefers-color-scheme: light) {
      .flow-diagram .box-app { fill: #2563eb; }
      .flow-diagram .box-os { fill: #059669; }
      .flow-diagram .box-fw-coord { fill: #7c3aed; }
      .flow-diagram .box-fw-int { fill: #d97706; }
    }
    .flow-diagram .tag-on-box { fill: #fff; font-size: 10px; }
    .legend {
      display: flex;
      flex-wrap: wrap;
      gap: 1rem 1.5rem;
      margin: 1rem 0 2rem;
      font-size: 0.9rem;
    }
    .legend-item { display: flex; align-items: center; gap: 0.45rem; }
    .legend-swatch {
      width: 1rem;
      height: 1rem;
      border-radius: 3px;
      flex-shrink: 0;
    }
    .seq-diagram {
      width: 100%;
      max-width: 820px;
      height: auto;
      margin: 1.25rem 0;
      display: block;
    }
    .seq-diagram text {
      font-family: ui-sans-serif, system-ui, sans-serif;
      font-size: 12px;
      fill: var(--text);
    }
    .seq-diagram .mono {
      font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
      font-size: 11px;
    }
    .seq-diagram .lane { fill: var(--panel); stroke: var(--border); }
    .seq-diagram .step-beta { fill: #5b21b6; }
    .seq-diagram .step-alpha { fill: #b45309; }
    .seq-diagram .step-warn { fill: #991b1b; }
    .seq-diagram .step-ok { fill: #166534; }
    .seq-diagram .step-label { fill: #fff; font-weight: 600; font-size: 11px; }
    .yaml-cascade {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 1rem;
      margin: 1.25rem 0 2rem;
    }
    @media (max-width: 640px) {
      .yaml-cascade { grid-template-columns: 1fr; }
    }
    .yaml-card {
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 1rem;
      text-align: center;
    }
    .yaml-card h3 { margin: 0 0 0.75rem; font-size: 1rem; }
    .yaml-card ul {
      list-style: none;
      padding: 0;
      margin: 0;
      font-size: 0.9rem;
    }
    .yaml-card li {
      padding: 0.35rem 0;
      border-top: 1px solid var(--border);
    }
    .yaml-card li:first-child { border-top: none; }
    .yaml-written { color: var(--accent); font-weight: 600; }
    .yaml-muted { color: var(--muted); }
    .checklist { counter-reset: step; list-style: none; padding-left: 0; }
    .checklist li {
      counter-increment: step;
      margin: 0.75rem 0;
      padding-left: 2rem;
      position: relative;
    }
    .checklist li::before {
      content: counter(step);
      position: absolute;
      left: 0;
      top: 0.1rem;
      width: 1.35rem;
      height: 1.35rem;
      border-radius: 50%;
      background: var(--accent);
      color: #fff;
      font-size: 0.75rem;
      font-weight: 700;
      display: flex;
      align-items: center;
      justify-content: center;
    }
    """


def _wrap_strategy_page(filename: str, title: str, body: str) -> str:
    """Wrap strategy doc body with guide styles plus diagram CSS."""
    base = _wrap_page(filename, title, body)
    extra = f"<style>{_strategy_diagram_css()}</style>"
    return base.replace("</head>", f"{extra}</head>", 1)


def _pipeline_pill(pipeline: str) -> str:
    label = "Internal pipeline" if pipeline == "internal" else "External pipeline"
    css = "pill-channel-internal" if pipeline == "internal" else "pill-channel-external"
    return f'<span class="pill {css}">{html.escape(label)}</span>'


def _stability_pill(stability: str) -> str:
    return f'<span class="pill pill-{html.escape(stability)}">{html.escape(stability)}</span>'


def _flow_svg(app_tag: str, oecore_tag: str, fw_coord: str, fw_int: str) -> str:
    """Render coordinated tags top-to-bottom in tag push order (firmware, oe-core, app)."""
    app = html.escape(app_tag)
    oecore = html.escape(oecore_tag)
    fw_c = html.escape(fw_coord)
    fw_i = html.escape(fw_int)
    same_stack = app_tag == oecore_tag == fw_coord
    stack_note = "same tag on all three" if same_stack else "stack tag maps to ex* on firmware"
    return f"""
    <svg class="flow-diagram" viewBox="0 0 280 210" role="img"
         aria-label="Tag push order: {fw_c}, {fw_i}, {oecore}, {app}">
      <title>Coordinated release tags (tag push order)</title>
      <rect class="box-fw-coord" x="20" y="8" width="240" height="36" rx="6"/>
      <text class="repo-label" x="140" y="22" text-anchor="middle">ot3-firmware coordination</text>
      <text class="tag-on-box" x="140" y="36" text-anchor="middle">{fw_c}</text>
      <path class="arrow" d="M140 44 v8"/>
      <polygon fill="var(--muted)" points="140,56 136,48 144,48"/>
      <rect class="box-fw-int" x="70" y="58" width="140" height="32" rx="6"/>
      <text class="repo-label" x="140" y="70" text-anchor="middle">integer version (same commit)</text>
      <text class="tag-on-box" x="140" y="84" text-anchor="middle">{fw_i}</text>
      <path class="arrow" d="M140 90 v10"/>
      <polygon fill="var(--muted)" points="140,104 136,96 144,96"/>
      <rect class="box-os" x="40" y="106" width="200" height="36" rx="6"/>
      <text class="repo-label" x="140" y="120" text-anchor="middle">oe-core (robot OS)</text>
      <text class="tag-on-box" x="140" y="134" text-anchor="middle">{oecore}</text>
      <path class="arrow" d="M140 142 v10"/>
      <polygon fill="var(--muted)" points="140,156 136,148 144,148"/>
      <rect class="box-app" x="40" y="158" width="200" height="36" rx="6"/>
      <text class="repo-label" x="140" y="172" text-anchor="middle">opentrons (app)</text>
      <text class="tag-on-box" x="140" y="186" text-anchor="middle">{app}</text>
      <text class="repo-label" x="140" y="206" text-anchor="middle" font-size="9">{html.escape(stack_note)}</text>
    </svg>
    """


def _tag_flavor_card(flavor: TagFlavor) -> str:
    """Render one pipeline × stability tagging card."""
    pipeline, stability, app_tag, oecore_tag, fw_coord, fw_int = flavor
    return f"""
    <article class="tag-card">
      <header>
        {_pipeline_pill(pipeline)}
        {_stability_pill(stability)}
      </header>
      {_flow_svg(app_tag, oecore_tag, fw_coord, fw_int)}
    </article>
    """


def _updater_yaml_cascade() -> str:
    """Visual for which electron-updater YAML files each stability writes."""
    return """
    <div class="yaml-cascade">
      <div class="yaml-card">
        <h3>Stable release</h3>
        <ul>
          <li class="yaml-written"><code>latest.yml</code></li>
          <li class="yaml-written"><code>beta.yml</code></li>
          <li class="yaml-written"><code>alpha.yml</code></li>
        </ul>
      </div>
      <div class="yaml-card">
        <h3>Beta release</h3>
        <ul>
          <li class="yaml-muted"><code>latest.yml</code> (unchanged)</li>
          <li class="yaml-written"><code>beta.yml</code></li>
          <li class="yaml-written"><code>alpha.yml</code></li>
        </ul>
      </div>
      <div class="yaml-card">
        <h3>Alpha release</h3>
        <ul>
          <li class="yaml-muted"><code>latest.yml</code></li>
          <li class="yaml-muted"><code>beta.yml</code></li>
          <li class="yaml-written"><code>alpha.yml</code></li>
        </ul>
      </div>
    </div>
    """


def _paired_release_svg() -> str:
    """Timeline SVG for beta-then-alpha paired release (both pipelines)."""
    return """
    <svg class="seq-diagram" viewBox="0 0 760 220" role="img"
         aria-label="Paired beta then alpha release sequence">
      <title>Beta then alpha release sequence</title>
      <rect class="lane" x="8" y="8" width="744" height="52" rx="8"/>
      <text x="20" y="30" font-weight="700">1. Publish Beta</text>
      <text class="mono" x="20" y="48">e.g. ot3@8.5.0-beta.1 or v10.0.0-beta.1 (+ ex* on firmware)</text>
      <rect class="step-beta" x="520" y="18" width="220" height="32" rx="6"/>
      <text class="step-label" x="630" y="38" text-anchor="middle">Beta + Alpha YAML updated</text>

      <rect class="lane" x="8" y="72" width="744" height="52" rx="8"/>
      <text x="20" y="94" font-weight="700">2. Gap: Alpha temporarily on Beta</text>
      <text class="mono" x="20" y="112">Alpha users may receive the Beta build until step 3 completes</text>
      <rect class="step-warn" x="520" y="82" width="220" height="32" rx="6"/>
      <text class="step-label" x="630" y="102" text-anchor="middle">Risk if Alpha not restored</text>

      <rect class="lane" x="8" y="136" width="744" height="52" rx="8"/>
      <text x="20" y="158" font-weight="700">3. Publish Alpha</text>
      <text class="mono" x="20" y="176">e.g. ot3@8.5.0-alpha.N or v10.0.0-alpha.N (+ ex* on firmware)</text>
      <rect class="step-alpha" x="520" y="146" width="220" height="32" rx="6"/>
      <text class="step-label" x="630" y="166" text-anchor="middle">Alpha YAML restored</text>

      <rect class="lane" x="8" y="200" width="744" height="16" rx="4" fill="none" stroke="none"/>
      <rect class="step-ok" x="8" y="196" width="744" height="20" rx="6"/>
      <text class="step-label" x="380" y="210" text-anchor="middle">
        Complete: Beta and Alpha each point at the intended build
      </text>
    </svg>
    """


def render_flex_coordinated_tags_page() -> str:
    """Render the six Flex release flavors and coordinated tag rules."""
    cards = "".join(_tag_flavor_card(flavor) for flavor in TAG_FLAVORS)
    body = f"""
    <p class="lede">Every Flex release uses <strong>coordinated tags</strong> across
    <code>opentrons</code>, <code>oe-core</code>, and <code>ot3-firmware</code>. The app tag is
    authoritative; robot OS matches it; firmware uses the same <code>ot3@*</code> tag internally or
    an <code>ex*</code> coordination tag externally, plus a colocated integer <code>vN</code> on the
    same commit.</p>

    <p>Six common flavors: the <strong>internal</strong> and <strong>external</strong> pipelines,
    each with <strong>stable</strong>, <strong>beta</strong>, or <strong>alpha</strong> stability.
    See also
    <a href="flex-release-sequencing.html">Flex release sequencing</a> for beta-then-alpha ordering.</p>

    <div class="legend">
      <div class="legend-item"><span class="legend-swatch" style="background:#7c3aed"></span>
        Firmware coordination tag</div>
      <div class="legend-item"><span class="legend-swatch" style="background:#d97706"></span>
        Firmware integer <code>vN</code></div>
      <div class="legend-item"><span class="legend-swatch" style="background:#059669"></span>
        Robot OS (<code>oe-core</code>)</div>
      <div class="legend-item"><span class="legend-swatch" style="background:#2563eb"></span>
        App (<code>opentrons</code>)</div>
    </div>

    <div class="tag-grid">
      {cards}
    </div>

    <h2>Rules (all flavors)</h2>
    <div class="panel">
      <ul>
        <li>The <code>opentrons</code> tag defines the coordinated release. Builds fail if a required
        tag is missing; there is no &ldquo;latest tag&rdquo; fallback
        (<a href="https://github.com/Opentrons/oe-core/pull/329">oe-core #329</a>).</li>
        <li><code>oe-core</code> always uses the same stack tag as the app.</li>
        <li><code>ot3-firmware</code> internal: same <code>ot3@*</code> as the app. External: map
        <code>v*</code> → <code>ex*</code> (never put semver <code>vX.Y.Z</code> on firmware; that
        collides with integer <code>vN</code> discovery).</li>
        <li>Every firmware release commit needs exactly one integer <code>vN</code> on the same commit.
        Reuse <code>vN</code> when the firmware commit did not change.</li>
        <li>A coordination tag on an unchanged commit is normal: it marks participation in that release,
        not necessarily new firmware code.</li>
      </ul>
    </div>

    <h2>Tag push order</h2>
    <p>When creating tags, push in this order: <code>ot3-firmware</code> (if needed),
    <code>oe-core</code> (if needed), <code>opentrons</code> (app, always last). Run
    <code>just validate-release-tags --tag &lt;app-tag&gt;</code> before pushing the app tag.</p>

    <h2>Verify locally</h2>
    <pre>just validate-release-tags --tag ot3@8.5.0-beta.1
just validate-release-tags --tag v10.0.0-alpha.2</pre>
    """
    return _wrap_strategy_page(
        "flex-coordinated-tags.html",
        "Flex coordinated tagging",
        body,
    )


def render_flex_release_sequencing_page() -> str:
    """Render beta/alpha pairing and app updater sequencing."""
    body = f"""
    <p class="lede">We support separate <strong>Beta</strong> and <strong>Alpha</strong> release trains
    that may ship different feature sets.</p>

    <div class="panel">
      <p><strong>Applies to both pipelines.</strong> The YAML override behavior below occurs on the
      <strong>internal stack</strong> (<code>ot3@*</code> tags,
      <code>ot3-development.builds.opentrons.com</code>) and the <strong>external stack</strong>
      (<code>v*</code> / <code>ex*</code> tags, <code>builds.opentrons.com</code>). Stability channels
      are <strong>stable</strong>, <strong>beta</strong>, and <strong>alpha</strong>; internal vs
      external is a pipeline distinction, not a channel.</p>
    </div>

    <h2>Why sequencing matters</h2>
    <p>Electron-updater YAML files (<code>latest.yml</code>, <code>beta.yml</code>,
    <code>alpha.yml</code>) form a hierarchy by stability. A higher-stability release overwrites
    metadata for lower stability channels:</p>
    {_updater_yaml_cascade()}
    <p><strong>Key behavior:</strong> publishing a <strong>Beta</strong> release updates both
    <code>beta.yml</code> and <code>alpha.yml</code>. A follow-up <strong>Alpha</strong> release is
    required to restore Alpha metadata to the intended Alpha build.</p>

    <h2>Decision 1: Coordinated release tags</h2>
    <p>Release builds no longer resolve &ldquo;latest&rdquo; <code>oe-core</code> or
    <code>ot3-firmware</code> tags. Each build uses explicit coordinated tags; missing tags fail the
    build rather than silently picking another commit
    (<a href="https://github.com/Opentrons/oe-core/pull/327">oe-core #327</a>,
    <a href="https://github.com/Opentrons/oe-core/pull/329">#329</a>).</p>
    <p>Visual reference:
    <a href="flex-coordinated-tags.html">Flex coordinated tagging (all six flavors)</a>.</p>

    <h2>Decision 2: Paired Beta and Alpha releases</h2>
    <p>Beta and Alpha are one coordinated operation. Ship <strong>Beta first</strong>, then
    <strong>Alpha</strong>. Do not announce the release complete until both are published and
    updater YAMLs are verified on the correct pipeline host.</p>

    <table>
      <thead><tr><th>Step</th><th>Stability</th><th>Internal pipeline</th><th>External pipeline</th></tr></thead>
      <tbody>
        <tr><td>1</td><td>Beta</td>
            <td><code>ot3@8.5.0-beta.1</code></td>
            <td><code>v10.0.0-beta.1</code> (+ <code>ex10.0.0-beta.1</code> on firmware)</td></tr>
        <tr><td>2</td><td>Alpha</td>
            <td><code>ot3@8.5.0-alpha.N</code></td>
            <td><code>v10.0.0-alpha.N</code> (+ <code>ex10.0.0-alpha.N</code> on firmware)</td></tr>
      </tbody>
    </table>
    <p>On the external pipeline, Beta may come from a feature branch; Alpha typically follows from
    <code>chore_release-10.0.0</code> on the main release line. Internal pipeline tags default-branch
    HEAD unless your process uses isolation branches.</p>
    {_paired_release_svg()}

    <h2>Failure risk</h2>
    <div class="panel">
      <p>If Beta succeeds but the follow-up Alpha fails, <strong>Alpha users keep seeing the Beta
      build</strong> until Alpha metadata is restored. Treat the pair as incomplete until:</p>
      <ul>
        <li>Beta artifacts and metadata are published</li>
        <li>Alpha artifacts and metadata are published</li>
        <li><code>beta.yml</code> resolves to the Beta release</li>
        <li><code>alpha.yml</code> resolves to the intended Alpha release</li>
        <li>GitHub Actions build summary shows coordinated app, oe-core, and firmware refs</li>
      </ul>
    </div>

    <h2>Operational checklist</h2>
    <h3>Before publishing</h3>
    <ol class="checklist">
      <li>Confirm intended commits in <code>opentrons</code>, <code>oe-core</code>, and
      <code>ot3-firmware</code>.</li>
      <li>Create coordinated tags in all required repos (firmware first, app last).</li>
      <li>Confirm firmware commit has exactly one integer <code>vN</code>; reuse if unchanged.</li>
      <li>Confirm pipeline (internal vs external) and stability (Beta vs Alpha) intent.</li>
      <li>Run <code>just validate-release-tags --tag &lt;app-tag&gt;</code> before pushing the app tag.</li>
    </ol>

    <h3>After publishing (each step of the pair)</h3>
    <ol class="checklist">
      <li><code>just track-builds --non-interactive --path flex --tag &lt;app-tag&gt; --wait</code></li>
      <li>Verify updater YAMLs on the correct pipeline host (external:
      <code>builds.opentrons.com</code>; internal:
      <code>ot3-development.builds.opentrons.com</code>).</li>
      <li>After both Beta and Alpha complete:
      <code>just invalidate-cloudfront --non-interactive --path flex --tag &lt;app-tag&gt;</code></li>
    </ol>

    <h2>Repeating the pattern</h2>
    <p>Additional Beta builds are allowed. <strong>Every new Beta requires a follow-up
    Alpha</strong> before the coordinated release is complete. Plan with
    <code>just go --path flex --release-type internal|external --stability beta|alpha</code>.</p>

    <h2>Summary</h2>
    <ul>
      <li><strong>Coordinated tags</strong> make release composition explicit and reproducible.</li>
      <li><strong>Beta then Alpha</strong> preserves separate Beta and Alpha trains without changing
      updater YAML generation or S3 upload behavior.</li>
    </ul>
    """
    return _wrap_strategy_page(
        "flex-release-sequencing.html",
        "Flex release sequencing",
        body,
    )
