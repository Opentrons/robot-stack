from rich.console import Console
from rich.prompt import Prompt

console = Console()
# Release Automation Checklist
#
# 1. What is the next https://github.com/Opentrons/opentrons tag we need?
#    - Name this page with the “Robot Stack” release version:
#      • vX.X.X           stable
#      • vX.X.X-*.X       alpha or beta (we don’t use beta much)
#      • ot3@X.X.X        stable internal (rare)
#      • ot3@X.X.X-*.X    alpha or beta internal

# ask the user if this is an internal or external release?
release_type = Prompt.ask(
    "[bold]Is this an internal (ot3@) or external (v*) release?[/bold]", choices=["internal", "external"], default="external"
)

console.print(f"Selected release type: [bold]{release_type}[/bold]")

# find the latest tag that has been published
# we will look at all sources
# https://builds.opentrons.com/app/alpha.yml
# https://builds.opentrons.com/app/alpha-mac.yml
# https://builds.opentrons.com/app/alpha-linux.yml

# https://builds.opentrons.com/app/beta.yml
# https://builds.opentrons.com/app/beta-mac.yml
# https://builds.opentrons.com/app/beta-linux.yml

# https://builds.opentrons.com/app/latest.yml
# https://builds.opentrons.com/app/latest-mac.yml
# https://builds.opentrons.com/app/latest-linux.yml

# release
# https://builds.opentrons.com/app/releases.json - app - informational, yml are authoritative.
# https://s3.us-east-1.amazonaws.com/builds.opentrons.com/app/releases.json - direct
# https://builds.opentrons.com/ot3-oe/releases.json - Flex
# https://builds.opentrons.com/ot2-br/releases.json - OT2
# Internal
# https://ot3-development.builds.opentrons.com/app/releases.json - app - informational, yml are authoritative.
# https://s3.us-east-1.amazonaws.com/ot3-development.builds.opentrons.com/app/releases.json
# https://ot3-development.builds.opentrons.com/ot3-oe/releases.json - Flex
# https://ot3-development.builds.opentrons.com/ot2-br/releases.json - OT2 (edited)

# is there a build currently running that will update a release

# 2. Are release notes merged?
#    • api/release‑notes‑internal.md         (robot internal)
#    • app-shell/build/release‑notes‑internal.md  (app internal)
#    • api/release‑notes.md
#    • app-shell/build/release‑notes.md


# 3. Any changes to https://github.com/Opentrons/opentrons-modules?
#    → Requires module tag(s) + buildroot & oe-core updates
#
# 4. Version tag(s) for the changed module(s)
#
# 5. Validate no tags greater than the proper version have been created
#
# 6. PR for buildroot setting the module version merged into correct branch?
#
# 7. PR for oe-core setting the module version merged into correct branch?
#
# 9. Any changes to https://github.com/Opentrons/buildroot?
#
# 10. Version tag for buildroot repo:
#     - external: vX.X.X
#     - internal stable: internal@vX.X.X
#     - internal alpha/beta: internal@vX.X.X-*.X
#
# 11. Validate no tags greater than the proper buildroot version exist
#
# 12. Create and push buildroot tag
#
# 13. Any changes to https://github.com/Opentrons/ot3-firmware?
#
# 14. Version tag for ot3-firmware:
#     • vX
#     • internal@vX
#
# 15. Validate no tags greater than the proper firmware version exist
#
# 16. Create and push firmware tag
#
# 17. Any changes to https://github.com/Opentrons/oe-core?
#
# 18. Version tag for oe-core:
#     • vX.X.X
#     • internal@X.X.X
#
# 19. Validate no tags greater than the proper oe-core version exist
#
# 20. Create and push oe-core tag
#
# 21. Any open PRs into the chore_release branch or the branch you’re tagging?
#     https://github.com/Opentrons/opentrons/pulls?q=is%3Apr+is%3Aopen+base%3Achore_release-8.1.0
#
# 22. Is this a stable release?
#     • Merge to release branch first, then tag (see RELEASING.md)
#
# 24. Create and push opentrons tag
#
# 25. Find the build jobs for app, Flex, and OT2 and share in the release channel
#     - If using non‑HEAD tags, cancel auto‑builds in oe‑core/buildroot
#       and trigger workflow dispatch with correct tag refs
#
# 26. Validate oe-core build(job) resolved correct versions
#
# 27. Validate buildroot build(job) resolved correct versions
#
# 28. Validate all three releases.json files
#
# 29. Validate all three YAML files:
#     • https://builds.opentrons.com/app/{alpha|beta|latest}.yml
#     • platform‑specific (mac, linux) variants
#
# 30. Invalidate CloudFront
#
# 31. Validate app sees new version & release notes on update
#
# 32. App and robot update successfully
#
# 33. App and robot downgrade successfully
#
# 34. Validate https://github.com/Opentrons/opentrons release page & “latest” flag
#
# 35. Validate https://pypi.org/project/opentrons/
#
# 36. Validate https://opentrons.com/ot-app downloads correct versions
#
# 37. If stable release → merge edge back into monorepo
#
# 38. If stable release → merge chore_release branch into release on oe-core
#
# 39. If stable release → merge chore_release branch into release on buildroot
#
# 40. If stable release → merge chore_release branch into release on ot3-firmware
