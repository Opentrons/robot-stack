"""Print CloudFront invalidation commands for a robot-stack release tag."""

from __future__ import annotations

import argparse
import sys

from rich.console import Console

from automation.cloudfront_invalidation import (
    ROBOT_STACK_PROD_PROFILE,
    print_cloudfront_invalidation,
    resolve_release_tag,
)

console = Console(log_time=False)


def build_parser() -> argparse.ArgumentParser:
    """Configure CLI arguments."""
    parser = argparse.ArgumentParser(
        description="Print CloudFront invalidation command for an OT-2 or Flex release tag.",
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
        "--aws-profile",
        default=ROBOT_STACK_PROD_PROFILE,
        help=f"AWS profile for CloudFront lookup (default: {ROBOT_STACK_PROD_PROFILE}).",
    )
    parser.add_argument(
        "--skip-cloudfront-lookup",
        action="store_true",
        help="Do not call AWS to resolve CloudFront distribution IDs.",
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
        path_name, tag = resolve_release_tag(
            args.tag,
            path=args.path,
            release_type=args.release_type,
            non_interactive=args.non_interactive,
        )
    except ValueError as err:
        console.print(f"[red]{err}[/]")
        sys.exit(1)

    print_cloudfront_invalidation(
        path_name,
        tag,
        profile=args.aws_profile,
        lookup_distribution_id=not args.skip_cloudfront_lookup,
        output=console,
    )


if __name__ == "__main__":
    main()
