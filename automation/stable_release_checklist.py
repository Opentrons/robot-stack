"""Stable release extra-steps checklists for Flex and OT-2 GitHub Pages."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Literal

from automation.release_guides import _wrap_page
from automation.site_nav import robot_name_html

CONFLUENCE_CHECKLIST = "https://opentrons.atlassian.net/wiki/spaces/RBARM/pages/6391365919/Release+Checklist+Template+v3"
CONFLUENCE_MERGEBACK = "https://opentrons.atlassian.net/wiki/spaces/RPDO/pages/5608374299/Git+merge+magic"
MERGEBACK_GUIDE_PAGE = "mergeback-guide.html"

ReleasePath = Literal["flex", "ot2"]


@dataclass(frozen=True)
class RepoStep:
    """One stack repo that participates in stable FF merge and mergeback."""

    name: str
    role: str
    url: str
    mergeback_into: str
    mergeback_note: str
    isolation_always: bool = False


@dataclass(frozen=True)
class StableChecklistFlavor:
    """Path-specific stable checklist content."""

    path: ReleasePath
    filename: str
    storage_key: str
    app_repo: str
    github_releases_url: str
    example_tag: str
    include_pypi: bool
    sibling_filename: str
    sibling_label: str
    repos: tuple[RepoStep, ...]


FLEX_STABLE: Final[StableChecklistFlavor] = StableChecklistFlavor(
    path="flex",
    filename="flex-stable-checklist.html",
    storage_key="robot-stack-flex-stable-checklist-v1",
    app_repo="opentrons",
    github_releases_url="https://github.com/Opentrons/opentrons/releases",
    example_tag="v10.0.0",
    include_pypi=True,
    sibling_filename="ot2-stable-checklist.html",
    sibling_label="OT-2 stable checklist",
    repos=(
        RepoStep(
            "ot3-firmware",
            "Flex firmware",
            "https://github.com/Opentrons/ot3-firmware",
            "main",
            "Pass off. Do not squash via the GitHub UI.",
            isolation_always=False,
        ),
        RepoStep(
            "oe-core",
            "Flex robot OS",
            "https://github.com/Opentrons/oe-core",
            "main",
            "Pass off. Do not squash via the GitHub UI.",
            isolation_always=False,
        ),
        RepoStep(
            "opentrons",
            "Flex app monorepo",
            "https://github.com/Opentrons/opentrons",
            "edge",
            "Pass off (edge is busy; easier in-office). Confirm someone owns the mergeback.",
            isolation_always=True,
        ),
    ),
)

OT2_STABLE: Final[StableChecklistFlavor] = StableChecklistFlavor(
    path="ot2",
    filename="ot2-stable-checklist.html",
    storage_key="robot-stack-ot2-stable-checklist-v1",
    app_repo="opentrons-ot2",
    github_releases_url="https://github.com/Opentrons/opentrons-ot2/releases",
    example_tag="v26.6.0",
    include_pypi=False,
    sibling_filename="flex-stable-checklist.html",
    sibling_label="Flex stable checklist",
    repos=(
        RepoStep(
            "buildroot",
            "OT-2 robot OS",
            "https://github.com/Opentrons/buildroot",
            "opentrons-develop",
            "Pass off. Do not squash via the GitHub UI.",
            isolation_always=False,
        ),
        RepoStep(
            "opentrons-ot2",
            "OT-2 app monorepo",
            "https://github.com/Opentrons/opentrons-ot2",
            "edge",
            "Pass off (edge is busy; easier in-office). Confirm someone owns the mergeback.",
            isolation_always=True,
        ),
    ),
)

STABLE_CHECKLIST_FLAVORS: Final[tuple[StableChecklistFlavor, ...]] = (FLEX_STABLE, OT2_STABLE)


def _checklist_css() -> str:
    """Styles for interactive stable-release checklist items."""
    return """
    .callout {
      background: var(--panel);
      border: 1px solid var(--border);
      border-left: 4px solid var(--accent);
      border-radius: 8px;
      padding: 0.9rem 1.1rem;
      margin: 1rem 0 1.5rem;
    }
    .callout-handoff {
      border-left-color: #f59e0b;
    }
    .checklist-form {
      display: flex;
      flex-direction: column;
      gap: 0.65rem;
      margin: 1rem 0 1.5rem;
    }
    .check-item {
      display: grid;
      grid-template-columns: 1.4rem 1fr;
      gap: 0.65rem;
      align-items: start;
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 0.75rem 0.9rem;
    }
    .check-item input[type="checkbox"] {
      margin-top: 0.3rem;
      width: 1.05rem;
      height: 1.05rem;
      accent-color: var(--accent);
    }
    .check-item label {
      cursor: pointer;
    }
    .check-item.done label {
      color: var(--muted);
      text-decoration: line-through;
    }
    .check-meta {
      display: block;
      color: var(--muted);
      font-size: 0.9rem;
      margin-top: 0.25rem;
      text-decoration: none;
    }
    .check-item.done .check-meta {
      text-decoration: none;
    }
    .repo-table code { white-space: nowrap; }
    .toolbar {
      display: flex;
      flex-wrap: wrap;
      gap: 0.5rem;
      align-items: center;
      margin: 0.5rem 0 1.25rem;
    }
    .toolbar button {
      background: var(--panel);
      color: var(--text);
      border: 1px solid var(--border);
      border-radius: 6px;
      padding: 0.4rem 0.75rem;
      cursor: pointer;
      font-size: 0.9rem;
    }
    .toolbar button:hover {
      border-color: var(--accent);
      color: var(--accent);
    }
    .toolbar .sibling-link {
      font-size: 0.9rem;
    }
    """


def _ff_merge_commands() -> str:
    """Render the approved ff-only merge sequence from the Confluence template."""
    return """
    <pre>git switch chore_release-${version}
git pull
git checkout release
git pull
# merge only if fast-forward is possible
git merge --ff-only chore_release-${version}
git push origin release</pre>
    <p class="note">Open or use a PR from <code>chore_release-*</code> into <code>release</code>,
    get approval, then run the ff-only merge locally. Do <strong>not</strong> merge with the
    GitHub UI (squash / merge commit can break the release history).</p>
    """


def _check_item(item_id: str, title: str, meta: str = "") -> str:
    """One checkbox row; meta is trusted HTML."""
    meta_html = f'<span class="check-meta">{meta}</span>' if meta else ""
    return f"""
    <div class="check-item" data-check-id="{item_id}">
      <input type="checkbox" id="{item_id}" />
      <label for="{item_id}">{title}{meta_html}</label>
    </div>
    """


def _ff_merge_meta(repo: RepoStep) -> str:
    """Per-repo note about whether chore_release isolation is expected."""
    if repo.isolation_always:
        return (
            f"{repo.role}. App monorepo always uses <code>chore_release-*</code> "
            "isolation for external stables; FF into <code>release</code> before tagging."
        )
    return (
        f"{repo.role}. Only if this cycle used a <code>chore_release-*</code> isolation "
        "branch here. Many releases tag from the default branch instead; skip when no "
        "isolation branch exists."
    )


def _ff_merge_checklist(flavor: StableChecklistFlavor) -> str:
    """Checkboxes for per-repo ff-only merges into release."""
    items = [
        _check_item(
            f"ff-{repo.name}",
            f"FF-only merge <code>chore_release-*</code> → <code>release</code> in "
            f'<a href="{repo.url}"><code>{repo.name}</code></a>',
            _ff_merge_meta(repo),
        )
        for repo in flavor.repos
    ]
    return f'<div class="checklist-form">{"".join(items)}</div>'


def _isolation_caveat(flavor: StableChecklistFlavor) -> str:
    """Explain that chore_release FF only applies when isolation was used."""
    app = flavor.app_repo
    if flavor.path == "flex":
        stack = "<code>oe-core</code> and <code>ot3-firmware</code>"
    else:
        stack = "<code>buildroot</code>"
    return f"""
    <div class="callout callout-handoff">
      <p><strong>Isolation caveat.</strong> Merging <code>chore_release-*</code> into
      <code>release</code> only applies when that repo used an isolation branch for this cycle.
      The app monorepo (<code>{app}</code>) always has <code>chore_release-*</code> for external
      stables. {stack} do <strong>not</strong> necessarily isolate every release; when they ship
      from the default branch (or already sit on <code>release</code> without a chore branch),
      skip the FF step for that repo.</p>
    </div>
    """


def _post_publish_checklist(flavor: StableChecklistFlavor) -> str:
    """GitHub release and download checks; PyPI only for Flex."""
    items = [
        _check_item(
            "github-latest",
            f"Publish the GitHub Release as latest on <code>{flavor.app_repo}</code>",
            f'<a href="{flavor.github_releases_url}">{flavor.app_repo}/releases</a>. '
            "Confirm the homepage shows this release as latest.",
        ),
    ]
    if flavor.include_pypi:
        items.append(
            _check_item(
                "pypi",
                "Validate PyPI for the <code>opentrons</code> package",
                '<a href="https://pypi.org/project/opentrons/">pypi.org/project/opentrons</a> shows the new version.',
            )
        )
    items.append(
        _check_item(
            "ot-app-downloads",
            'Validate <a href="https://opentrons.com/ot-app">opentrons.com/ot-app</a> downloads',
            "Confirm the site serves the correct desktop installers for this stable version.",
        )
    )
    return f'<div class="checklist-form">{"".join(items)}</div>'


def _mergeback_checklist(flavor: StableChecklistFlavor) -> str:
    """Handoff checkboxes: ensure mergebacks are owned, not necessarily done by the releaser."""
    items = [
        _check_item(
            f"mergeback-{repo.name}",
            f"Mergeback owned for <code>{repo.name}</code>: <code>release</code> → <code>{repo.mergeback_into}</code>",
            repo.mergeback_note,
        )
        for repo in flavor.repos
    ]
    return f'<div class="checklist-form">{"".join(items)}</div>'


def _repo_table(flavor: StableChecklistFlavor) -> str:
    """Summary table of repos for this path."""
    rows = "".join(
        (
            f"<tr><td><code>{repo.name}</code></td><td>{repo.role}</td>"
            f"<td>{'Always (monorepo)' if repo.isolation_always else 'Only if isolated this cycle'}</td>"
            f"<td><code>release</code></td><td><code>{repo.mergeback_into}</code></td></tr>"
        )
        for repo in flavor.repos
    )
    return f"""
    <table class="repo-table">
      <thead><tr><th>Repo</th><th>Role</th><th>chore_release isolation</th>
      <th>Stable FF into</th><th>Mergeback into</th></tr></thead>
      <tbody>{rows}</tbody>
    </table>
    """


def _tooling_callout(flavor: StableChecklistFlavor) -> str:
    """Remind operators of the shared advisory tooling for this path."""
    path = flavor.path
    tag = flavor.example_tag
    return f"""
    <div class="callout">
      <p>Plan and push tags with <code>just go-plan --path {path}</code> /
      <code>just apply-release-plan</code>, then
      <code>just track-builds --path {path} --tag {tag} --wait</code>, wait for CI,
      <code>just invalidate-cloudfront --path {path} --tag {tag} --execute --wait</code>, and
      <code>just verify-release-assets --path {path} --tag {tag}</code>. Those steps live on the
      path guides; this checklist assumes they are done (or in progress) before the checks below.</p>
    </div>
    """


def _persistence_script(storage_key: str) -> str:
    """Persist checkbox state in localStorage for one flavor page."""
    return f"""
<script>
(function () {{
  const STORAGE_KEY = "{storage_key}";
  const form = document.getElementById("stable-checklist");
  if (!form) return;

  function load() {{
    let saved = {{}};
    try {{
      saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || "{{}}") || {{}};
    }} catch (e) {{
      saved = {{}};
    }}
    form.querySelectorAll('input[type="checkbox"]').forEach((box) => {{
      box.checked = Boolean(saved[box.id]);
      box.closest(".check-item")?.classList.toggle("done", box.checked);
    }});
  }}

  function save() {{
    const saved = {{}};
    form.querySelectorAll('input[type="checkbox"]').forEach((box) => {{
      saved[box.id] = box.checked;
    }});
    localStorage.setItem(STORAGE_KEY, JSON.stringify(saved));
  }}

  form.addEventListener("change", (event) => {{
    const target = event.target;
    if (!(target instanceof HTMLInputElement) || target.type !== "checkbox") return;
    target.closest(".check-item")?.classList.toggle("done", target.checked);
    save();
  }});

  document.getElementById("clear-checklist")?.addEventListener("click", () => {{
    form.querySelectorAll('input[type="checkbox"]').forEach((box) => {{
      box.checked = false;
      box.closest(".check-item")?.classList.remove("done");
    }});
    localStorage.removeItem(STORAGE_KEY);
  }});

  load();
}})();
</script>
"""


def _post_publish_heading(flavor: StableChecklistFlavor) -> str:
    """Section title for post-publish checks."""
    if flavor.include_pypi:
        return "3. GitHub Release, PyPI, and downloads"
    return "3. GitHub Release and downloads"


def render_stable_checklist_page(flavor: StableChecklistFlavor) -> str:
    """Render one path-specific stable-release extras checklist."""
    robot = "Flex" if flavor.path == "flex" else "OT-2"
    body = f"""
    <p class="lede">Extra steps for an <strong>external stable</strong>
    {robot_name_html(robot)} release (<code>{flavor.example_tag}</code>-style),
    on top of the usual
    <code>just go-plan</code> → apply → track → invalidate → verify flow.
    Alpha and beta releases skip this page.</p>

    <p class="note">Source of truth for the broader template:
    <a href="{CONFLUENCE_CHECKLIST}">Release Checklist Template v3</a> (RBARM).
    Sibling path: <a href="{flavor.sibling_filename}">{flavor.sibling_label}</a>.</p>

    <div class="toolbar">
      <button type="button" id="clear-checklist">Clear saved checkmarks</button>
      <a class="sibling-link" href="{flavor.sibling_filename}">{flavor.sibling_label}</a>
    </div>

    <form id="stable-checklist" data-path="{flavor.path}">
      <h2>1. Fast-forward <code>chore_release-*</code> into <code>release</code></h2>
      <div class="callout">
        <p>Before tagging a stable release, ff-only merge the isolation branch into
        <code>release</code> in each {robot} repo that <strong>actually used</strong>
        <code>chore_release-*</code> this cycle. Get PR approval first; then merge locally with
        <code>--ff-only</code>.</p>
      </div>
      {_isolation_caveat(flavor)}
      {_ff_merge_commands()}
      {_ff_merge_checklist(flavor)}
      <p class="note">Check the monorepo FF every external stable. For stack repos, check only when
      a <code>chore_release-*</code> isolation branch exists for this cycle; otherwise skip.</p>

      <h2>2. Finish the normal release tooling</h2>
      {_tooling_callout(flavor)}

      <h2>{_post_publish_heading(flavor)}</h2>
      {_post_publish_checklist(flavor)}

      <h2>4. Mergebacks (hand off)</h2>
      <div class="callout callout-handoff">
        <p><strong>Do not own mergebacks by default.</strong> Confirm each mergeback has an owner
        and is tracked to completion. Prefer a real merge (not squash) per the
        <a href="{MERGEBACK_GUIDE_PAGE}">mergeback guide</a>
        (from <a href="{CONFLUENCE_MERGEBACK}">Git merge magic</a>).</p>
      </div>
      {_mergeback_checklist(flavor)}
    </form>

    <h2>Repos involved</h2>
    {_repo_table(flavor)}
    {_persistence_script(flavor.storage_key)}
    """
    page = _wrap_page(flavor.filename, "stable release checklist", body, robot_name=robot)
    extra = f"<style>{_checklist_css()}</style>"
    return page.replace("</head>", f"{extra}</head>", 1)


def render_flex_stable_checklist_page() -> str:
    """Render the Flex stable-release extras checklist."""
    return render_stable_checklist_page(FLEX_STABLE)


def render_ot2_stable_checklist_page() -> str:
    """Render the OT-2 stable-release extras checklist."""
    return render_stable_checklist_page(OT2_STABLE)
