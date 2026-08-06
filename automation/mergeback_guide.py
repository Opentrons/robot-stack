"""Mergeback instructions for GitHub Pages (from Confluence RPDO docs)."""

from __future__ import annotations

from automation.release_guides import _wrap_page

CONFLUENCE_MERGE_MAGIC = (
    "https://opentrons.atlassian.net/wiki/spaces/RPDO/pages/5608374299/Git+merge+magic"
)
CONFLUENCE_MERGEBACK_FF = (
    "https://opentrons.atlassian.net/wiki/spaces/RPDO/pages/5176787721/"
    "How+to+do+a+mergeback+and+fast-forward"
)

MERGEBACK_PAGE = "mergeback-guide.html"


def _guide_css() -> str:
    """Extra styles for the mergeback guide."""
    return """
    .callout {
      background: var(--panel);
      border: 1px solid var(--border);
      border-left: 4px solid var(--accent);
      border-radius: 8px;
      padding: 0.9rem 1.1rem;
      margin: 1rem 0 1.5rem;
    }
    .callout-warn {
      border-left-color: #f59e0b;
    }
    .callout-danger {
      border-left-color: #ef4444;
    }
    .steps {
      counter-reset: merge-step;
      list-style: none;
      padding-left: 0;
    }
    .steps > li {
      counter-increment: merge-step;
      margin: 1.25rem 0;
      padding-left: 2.25rem;
      position: relative;
    }
    .steps > li::before {
      content: counter(merge-step);
      position: absolute;
      left: 0;
      top: 0.05rem;
      width: 1.5rem;
      height: 1.5rem;
      border-radius: 50%;
      background: var(--accent);
      color: #fff;
      font-size: 0.8rem;
      font-weight: 700;
      display: flex;
      align-items: center;
      justify-content: center;
    }
    .history-sample {
      font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
      font-size: 0.82rem;
      line-height: 1.35;
      white-space: pre;
      overflow-x: auto;
    }
    """


def render_mergeback_guide_page() -> str:
    """Render mergeback instructions adapted from Confluence for robot-stack repos."""
    body = f"""
    <p class="lede">How to merge a release isolation branch back into the default branch
    without destroying history. Do <strong>not</strong> use GitHub&apos;s squash or merge buttons
    to land the result; push the merge commit from the CLI after review.</p>

    <p class="note">Adapted from Confluence:
    <a href="{CONFLUENCE_MERGE_MAGIC}">Git merge magic</a> (canonical procedure) and
    <a href="{CONFLUENCE_MERGEBACK_FF}">How to do a mergeback and fast-forward</a>.
    Stable checklists:
    <a href="flex-stable-checklist.html">Flex</a> ·
    <a href="ot2-stable-checklist.html">OT-2</a>.</p>

    <h2>Which branches?</h2>
    <p>Robot-stack stable releases usually need two different git operations. Do not confuse them:</p>
    <table>
      <thead><tr><th>When</th><th>Operation</th><th>From</th><th>Into</th></tr></thead>
      <tbody>
        <tr>
          <td>Before tagging stable</td>
          <td>Fast-forward only</td>
          <td><code>chore_release-*</code></td>
          <td><code>release</code></td>
        </tr>
        <tr>
          <td>After stable ships (handoff)</td>
          <td>Real merge (mergeback)</td>
          <td><code>release</code> (or still <code>chore_release-*</code> mid-cycle)</td>
          <td>Default branch</td>
        </tr>
      </tbody>
    </table>
    <p>This page is the <strong>mergeback</strong> procedure (second row). FF-only steps live on the
    stable checklists.</p>

    <h3>Default mergeback targets</h3>
    <table>
      <thead><tr><th>Repo</th><th>Typical source</th><th>Mergeback into</th></tr></thead>
      <tbody>
        <tr><td><code>opentrons</code></td><td><code>release</code></td><td><code>edge</code></td></tr>
        <tr><td><code>opentrons-ot2</code></td><td><code>release</code></td><td><code>edge</code></td></tr>
        <tr><td><code>oe-core</code></td><td><code>release</code></td><td><code>main</code></td></tr>
        <tr><td><code>ot3-firmware</code></td><td><code>release</code></td><td><code>main</code></td></tr>
        <tr><td><code>buildroot</code></td><td><code>release</code></td><td><code>opentrons-develop</code></td></tr>
      </tbody>
    </table>
    <p class="note">Examples below use <code>release</code> → <code>edge</code> on
    <code>opentrons</code>. Substitute the source and target for the repo you are merging.</p>

    <h2>Check whether a mergeback is needed</h2>
    <p>Use a GitHub compare URL (three-dot compare of target...source):</p>
    <pre>https://github.com/Opentrons/opentrons/compare/edge...release
https://github.com/Opentrons/oe-core/compare/main...release
https://github.com/Opentrons/buildroot/compare/opentrons-develop...release</pre>
    <p>If the compare is empty, nothing unique remains on the release branch.</p>

    <h2>Mergeback procedure</h2>
    <div class="callout callout-danger">
      <p><strong>Never squash.</strong> Squash-and-merge collapses the release history into one
      commit on the default branch and permanently damages the graph. After PR approval, push the
      merge commit from your machine.</p>
    </div>

    <ol class="steps">
      <li>
        <p><strong>Fetch so local refs match GitHub</strong></p>
        <pre>git fetch --prune-tags --force</pre>
        <p class="note"><code>--prune-tags --force</code> updates local tags that were moved or
        deleted on GitHub. Without that, your local tag view can diverge from origin.</p>
      </li>
      <li>
        <p><strong>Create a merge branch from the remote default branch</strong></p>
        <pre>git checkout -b merge-release-into-edge origin/edge</pre>
        <p class="note">Use <code>origin/edge</code> (or <code>origin/main</code> /
        <code>origin/opentrons-develop</code>), not your local default branch, so you do not pick up
        stale local commits.</p>
      </li>
      <li>
        <p><strong>Merge the release branch</strong></p>
        <pre>git merge origin/release</pre>
        <p>Mid-cycle mergebacks from an isolation branch look the same with a different source:</p>
        <pre>git merge origin/chore_release-1.2.3</pre>
      </li>
      <li>
        <p><strong>Resolve conflicts if needed</strong></p>
        <p>Git stops in merge mode when files conflict. Edit each conflicted file, then:</p>
        <pre>git add path/to/file.py
git merge --continue</pre>
        <p>Change the default merge title to something like:</p>
        <pre>chore(release): Merge back 'release' into 'edge'</pre>
        <p>Uncomment the conflicted-file list in the commit template so reviewers can see what you
        touched. To abandon and start over:</p>
        <pre>git merge --abort</pre>
      </li>
      <li>
        <p><strong>Confirm the history graph</strong></p>
        <pre>git log --graph --oneline</pre>
        <p>It should look like a real merge (two parents), not a linear squash:</p>
        <pre class="history-sample">*   xxx123 Merge back 'release' into 'edge'
|\\
| * xxx456 Change that lived on release
| * xxx789 Another release commit
|/
* | xxx012 A change that landed on edge meanwhile
* | xxx345 Another edge commit
|/
* xxx678 Common ancestor</pre>
      </li>
      <li>
        <p><strong>Push the merge branch and open a PR</strong></p>
        <pre>git push --set-upstream origin HEAD:merge-release-into-edge</pre>
        <p>Open a PR into the default branch. Ask reviewers to check conflict resolutions, not just
        the diff size.</p>
      </li>
      <li>
        <p><strong>Land by pushing to the default branch (CLI)</strong></p>
        <pre># Still on merge-release-into-edge after approval
git push origin HEAD:edge</pre>
        <p>GitHub closes the PR when the default branch advances. Delete the temporary merge branch
        afterward.</p>
      </li>
    </ol>

    <h2>Default branch moved before you could land</h2>
    <div class="callout callout-warn">
      <p>This is common on busy <code>edge</code> branches while CI runs. Do
      <strong>not</strong> merge the default branch into your merge branch. That creates a permanent
      &ldquo;Merge edge into merge-…&rdquo; commit and makes the default branch the second parent,
      which confuses history forever.</p>
    </div>
    <p>Instead, redo the merge with a clean history while reusing your conflict resolutions:</p>
    <ol class="steps">
      <li>
        <p><strong>Temporarily merge the new default tip into your merge branch</strong>
        (ugly history on purpose; this is only a content workspace):</p>
        <pre>git fetch --prune-tags --force
git merge origin/edge</pre>
      </li>
      <li>
        <p><strong>Start a fresh merge branch from the new default tip</strong></p>
        <pre>git checkout -b merge-release-into-edge-take2 origin/edge
git merge origin/release</pre>
        <p>Conflicts reappear. You already resolved them on the first merge branch.</p>
      </li>
      <li>
        <p><strong>Copy resolved file contents from the first merge branch</strong></p>
        <pre># On merge-release-into-edge-take2
git checkout merge-release-into-edge -- '**'</pre>
      </li>
      <li>
        <p><strong>Finish the clean merge</strong></p>
        <pre>git merge --continue</pre>
        <p>Use the same chore commit title. Confirm contents and history:</p>
        <pre>git diff merge-release-into-edge
git log --graph --oneline</pre>
      </li>
      <li>
        <p><strong>Force-update the PR branch and land</strong></p>
        <pre>git push --set-upstream origin HEAD:merge-release-into-edge --force
git push origin HEAD:edge</pre>
      </li>
    </ol>
    <p class="note">Older shorthand (from the fast-forward doc): rename the old merge branch to a
    backup, recreate from <code>origin/&lt;default&gt;</code>, merge again, and
    <code>git push -f</code> the PR branch. Same idea; prefer the content-copy shortcut above when
    conflicts were painful.</p>

    <h2>Fixing a bad conflict resolution after the merge commit</h2>
    <pre>git commit --amend
git push --force</pre>
    <p class="note">Only amend when the merge commit has not been landed on the protected default
    branch yet (still on the temporary PR branch).</p>

    <h2>Related: fast-forward <code>chore_release-*</code> into <code>release</code></h2>
    <p>Stable tagging expects <code>release</code> to be a fast-forward of the isolation branch
    <strong>when that repo used isolation</strong>. The app monorepo always has
    <code>chore_release-*</code> for external stables;
    <code>oe-core</code>, <code>ot3-firmware</code>, and <code>buildroot</code> do not necessarily
    isolate every release. Open a PR for approval, then merge locally only in repos that have the
    chore branch:</p>
    <pre>git switch chore_release-${{version}}
git pull
git checkout release
git pull
git merge --ff-only chore_release-${{version}}
git push origin release</pre>
    <p><code>--ff-only</code> fails if <code>release</code> diverged. See the
    <a href="flex-stable-checklist.html">Flex</a> and
    <a href="ot2-stable-checklist.html">OT-2</a> stable checklists.</p>

    <h2>Appendix: inspect edits inside a merge commit</h2>
    <pre>git show --diff-merges=r &lt;merge-sha&gt;</pre>
    <p>Highlights lines that differ from a clean automatic merge (useful when reviewing conflict
    resolutions).</p>
    """
    page = _wrap_page(MERGEBACK_PAGE, "Mergeback guide", body)
    extra = f"<style>{_guide_css()}</style>"
    return page.replace("</head>", f"{extra}</head>", 1)
