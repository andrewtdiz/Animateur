from __future__ import annotations

import argparse
import sys

from .compiler import RigSpecError, StaleGeneratedArtifactError, compile_repo


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python3 -m animateur_rig")
    subparsers = parser.add_subparsers(dest="command", required=True)

    compile_parser = subparsers.add_parser("compile", help="Generate checked-in rig artifacts.")
    compile_parser.add_argument(
        "--check",
        action="store_true",
        help="Fail if generated rig artifacts are stale instead of writing them.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "compile":
        try:
            paths = compile_repo(check=args.check)
        except (RigSpecError, StaleGeneratedArtifactError) as error:
            print(str(error), file=sys.stderr)
            return 1

        if args.check:
            print("Generated rig artifacts are current.")
        else:
            print("Generated rig artifacts updated:")
            for path in paths:
                print(f"- {path}")
        return 0

    parser.error(f"Unsupported command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
