"""Manually backfill the SQLite lexical index from persistent Chroma data."""

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.services.lexical_backfill import backfill_chroma_to_lexical


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Copy existing Chroma document text and metadata into "
            "the persistent SQLite FTS5 lexical index."
        )
    )
    parser.add_argument(
        "--run",
        action="store_true",
        help="Explicitly execute the backfill. Without this flag, only show help.",
    )
    parser.add_argument(
        "--chroma-path",
        help="Chroma persistence directory. Defaults to application settings.",
    )
    parser.add_argument(
        "--lexical-path",
        help="Lexical SQLite database path. Defaults to the configured Chroma sibling.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=500,
        help="Number of Chroma metadata records read per discovery batch (default: 500).",
    )

    args = parser.parse_args()

    if not args.run:
        parser.print_help()
        print("\nNo changes made. Add --run to execute the backfill.")
        return 0

    if args.batch_size < 1:
        parser.error("--batch-size must be a positive integer")

    report = backfill_chroma_to_lexical(
        persist_directory=args.chroma_path,
        lexical_path=args.lexical_path,
        batch_size=args.batch_size,
    )

    print(json.dumps(report, indent=2))

    if report["collection_missing"]:
        print(
            "No Chroma collection found. No lexical entries were changed.",
            file=sys.stderr,
        )
        return 2

    if report["failed_documents"] or report["invalid_records"]:
        print(
            "Backfill completed with skipped or failed records. "
            "Review the report before relying on lexical retrieval.",
            file=sys.stderr,
        )
        return 1

    print("Lexical backfill completed successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
