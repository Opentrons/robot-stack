"""Flex coordinated tagging and release channel hierarchy documentation for GitHub Pages."""

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
    """Timeline SVG for beta-then-alpha updater YAML sequencing when both channels update."""
    return """
    <svg class="seq-diagram" viewBox="0 0 760 220" role="img"
         aria-label="Beta then alpha publish sequence for updater YAML">
      <title>Beta then alpha publish sequence</title>
      <rect class="lane" x="8" y="8" width="744" height="52" rx="8"/>
      <text x="20" y="30" font-weight="700">1. Publish a Beta desktop build</text>
      <text x="20" y="48" fill="var(--muted)">Beta channel users receive the new build</text>
      <rect class="step-beta" x="520" y="18" width="220" height="32" rx="6"/>
      <text class="step-label" x="630" y="38" text-anchor="middle">beta.yml + alpha.yml updated</text>

      <rect class="lane" x="8" y="72" width="744" height="52" rx="8"/>
      <text x="20" y="94" font-weight="700">2. Gap: Alpha channel temporarily on Beta</text>
      <text x="20" y="112" fill="var(--muted)">Alpha users may see the Beta build until step 3</text>
      <rect class="step-warn" x="520" y="82" width="220" height="32" rx="6"/>
      <text class="step-label" x="630" y="102" text-anchor="middle">Risk if Alpha not restored</text>

      <rect class="lane" x="8" y="136" width="744" height="52" rx="8"/>
      <text x="20" y="158" font-weight="700">3. Publish an Alpha desktop build</text>
      <text x="20" y="176" fill="var(--muted)">Alpha channel users receive the intended Alpha build</text>
      <rect class="step-alpha" x="520" y="146" width="220" height="32" rx="6"/>
      <text class="step-label" x="630" y="166" text-anchor="middle">alpha.yml restored</text>

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
    At one semver base, alpha and beta are <strong>independent lanes</strong> with separate counters.
    See also
    <a href="release-channel-hierarchy.html">Release channel hierarchy</a> for how alpha, beta, and
    stable updater channels interact on Flex and OT-2.</p>

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


def render_release_channel_hierarchy_page() -> str:
    """Render alpha/beta/stable channel hierarchy for Flex and OT-2 desktop updaters."""
    body = f"""
    <p class="lede">Opentrons desktop apps on <strong>Flex</strong> and <strong>OT-2</strong> use
    electron-updater with three stability channels: <strong>alpha</strong>, <strong>beta</strong>,
    and <strong>stable</strong> (<code>latest</code>). Each channel reads a YAML manifest on the
    build CDN (<code>alpha.yml</code>, <code>beta.yml</code>, <code>latest.yml</code>). This page
    explains the traditional release model those channels reflect, why the YAML files overwrite
    each other the way they do, and how we still ship different build flavors on alpha and beta
    in parallel.</p>

    <h2>The traditional release model</h2>
    <p>Most software teams treat prerelease quality as a <strong>hierarchy of confidence</strong>:</p>
    <ol>
      <li><strong>Alpha</strong> builds go to a small, controlled audience first. The goal is early
      feedback and shaking out obvious defects before wider exposure.</li>
      <li>When alpha builds reach enough stability, a <strong>beta</strong> build is published to a
      larger customer set. Beta is still prerelease, but it represents higher confidence than alpha.</li>
      <li>Testing continues. Teams may ship <strong>further alpha builds</strong> for narrow validation
      and <strong>further beta builds</strong> for broader soak testing until both channels meet their
      quality bars.</li>
      <li>When confidence is high enough, a <strong>stable</strong> release replaces prerelease
      channels for general availability.</li>
    </ol>
    <p>That ladder is why electron-updater exposes separate channel YAMLs and a setting
    (<code>generateUpdatesFilesForAllChannels</code>) that writes lower-stability metadata when a
    higher-stability build publishes: a stable release should be visible to everyone who opted into
    beta or alpha, and a beta release should not leave alpha users stranded on an older build when
    beta is strictly ahead.</p>

    <h2>How YAML overwrite preserves the hierarchy</h2>
    <p>When a desktop build publishes, electron-updater updates one or more YAML files on the CDN.
    Higher-stability publishes overwrite metadata for lower channels:</p>
    {_updater_yaml_cascade()}
    <p><strong>Key behavior:</strong> publishing a <strong>beta</strong> build updates both
    <code>beta.yml</code> and <code>alpha.yml</code>. Publishing an <strong>alpha</strong> build
    updates only <code>alpha.yml</code>. Publishing <strong>stable</strong> updates all three.</p>
    <p>This applies on every Opentrons app host that serves desktop updater YAMLs, including Flex
    internal (<code>ot3-development.builds.opentrons.com</code>), Flex external
    (<code>builds.opentrons.com</code>), OT-2 internal
    (<code>ot2-development.builds.opentrons.com</code>), and OT-2 external
    (<code>ot2.builds.opentrons.com</code>).</p>

    <h2>Parallel flavors, not only a straight ladder</h2>
    <div class="panel">
      <p>The hierarchy above describes <strong>who should receive which build</strong> through the
      updater. Our release process also needs <strong>flexibility</strong>: alpha and beta can carry
      <strong>different build flavors at the same time</strong>, not only a single line that always
      promotes alpha → beta → stable.</p>
      <p>Example: a beta build may target VM isolation validation while a separate alpha build targets
      CRS, both active during the same development cycle. That is normal. The updater hierarchy still
      applies to metadata on the CDN; it does not require every alpha to become the next beta before
      either channel moves forward.</p>
    </div>

    <h2>When both alpha and beta need fresh builds</h2>
    <p>If you intend to update <strong>both</strong> channels in the same release cycle, publish
    <strong>beta before alpha</strong>. A beta desktop publish overwrites <code>alpha.yml</code> with
    the beta build until an alpha publish restores alpha metadata to the intended alpha build.</p>
    <p>That ordering rule is about <strong>updater YAML only</strong>. It does not mean alpha must
    always precede beta in development, and it does not replace the traditional confidence ladder.
    It prevents alpha-channel users from staying on a beta build after you meant to ship a distinct
    alpha.</p>
    {_paired_release_svg()}

    <h2>Failure risk</h2>
    <div class="panel">
      <p>If a beta publish succeeds but the follow-up alpha publish fails or is skipped,
      <strong>alpha-channel users keep seeing the beta build</strong> until alpha metadata is
      restored. Treat a paired cycle as incomplete until:</p>
      <ul>
        <li>Beta artifacts and <code>beta.yml</code> point at the intended beta build</li>
        <li>Alpha artifacts and <code>alpha.yml</code> point at the intended alpha build</li>
        <li>You have verified both YAML URLs on the correct pipeline host</li>
      </ul>
    </div>

    <h2>Stable releases</h2>
    <p>A stable desktop publish updates <code>latest.yml</code>, <code>beta.yml</code>, and
    <code>alpha.yml</code>. Users on any prerelease channel who are eligible for stable will see the
    stable build through the same hierarchy. Plan stable only when alpha and beta validation for that
    cycle is complete.</p>

    <h2>Summary</h2>
    <ul>
      <li><strong>Traditional model:</strong> alpha (narrow) → beta (broader) → stable, with iteration
      on alpha and beta until confidence is high enough.</li>
      <li><strong>YAML cascade:</strong> electron-updater keeps lower channels aligned with higher
      stability publishes so the hierarchy is preserved on the CDN.</li>
      <li><strong>Parallel flavors:</strong> alpha and beta can represent different active build lines;
      the hierarchy governs updater metadata, not a single mandatory promotion path.</li>
      <li><strong>Paired cycle:</strong> when both channels need new builds, publish beta then alpha so
      <code>alpha.yml</code> ends on the correct build.</li>
      <li><strong>Flex and OT-2:</strong> same channel filenames and overwrite rules on internal and
      external app hosts.</li>
    </ul>
    """
    return _wrap_strategy_page(
        "release-channel-hierarchy.html",
        "Release channel hierarchy",
        body,
    )


def render_flex_release_sequencing_page() -> str:
    """Deprecated alias for :func:`render_release_channel_hierarchy_page`."""
    return render_release_channel_hierarchy_page()
