"""Verify live app and robot assets for a robot-stack release tag."""

from __future__ import annotations

import argparse
import sys

from rich.console import Console

from automation.release_asset_verification import run_verify_release_assets_cli

console = Console(log_time=False)


def build_parser() -> argparse.ArgumentParser:
    """Configure CLI arguments."""
    parser = argparse.ArgumentParser(
        description="Verify live S3/CloudFront assets for an OT-2 or Flex release tag.",
    )
    parser.add_argument(
        "--path",
        choices=["flex", "ot2"],
        default=None,
        help="Robot release path (default: infer from tag, else flex).",
    )
    parser.add_argument(
        "--tag",
        help="Release tag, e.g. internal@26.5.2701, v8.5.0, or ot3@8.5.0.",
    )
    parser.add_argument(
        "--release-type",
        choices=["internal", "external"],
        help="Add the channel prefix when --tag is given without one.",
    )
    parser.add_argument(
        "--non-interactive",
        action="store_true",
        help="Do not prompt; require --tag (and --release-type when the tag has no prefix).",
    )
    return parser


def main() -> None:
    """CLI entrypoint."""
    parser = build_parser()
    args = parser.parse_args()

    try:
        report = run_verify_release_assets_cli(
            tag=args.tag,
            path=args.path,
            release_type=args.release_type,
            non_interactive=args.non_interactive,
            output=console,
        )
    except ValueError as err:
        console.print(f"[red]{err}[/]")
        sys.exit(1)

    if not report.passed:
        sys.exit(1)


if __name__ == "__main__":
    main()
