"""Plan expired bookkeeping cleanup; --apply is an explicit operator-only DB transaction."""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from app.database import SessionLocal
from app.maintenance import apply_bookkeeping, plan


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Remove expired rate buckets/sessions only; requires operator DELETE grants",
    )
    args = parser.parse_args()
    try:
        with SessionLocal() as db:
            print(
                json.dumps(apply_bookkeeping(db) if args.apply else plan(db), indent=2)
            )
    except Exception as error:  # noqa: BLE001 - operator boundary never emits SQL or credentials
        print(
            json.dumps(
                {
                    "status": "FAILED",
                    "error_type": type(error).__name__,
                    "detail": "Maintenance unavailable; inspect operator access without printing credentials",
                }
            )
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
