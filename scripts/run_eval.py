import argparse
import json
from uuid import UUID

from claimagent import db, harness, runner
from claimagent.config import REPORTS_DIR, VALID_SPLITS, VALID_VERSIONS
from claimagent.provider import OpenAIProvider


def compare_runs(id_a: str, id_b: str) -> None:
    with db.connect() as conn:
        result = harness.compare(db.get_run(conn, UUID(id_a)), db.get_run(conn, UUID(id_b)))
    path = REPORTS_DIR / "comparison-development.md"
    path.write_text(harness.render_comparison(result), encoding="utf-8", newline="\n")
    print(json.dumps(result["deltas"], indent=2), f"\nwritten {path}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", choices=VALID_VERSIONS)
    parser.add_argument("--split", choices=VALID_SPLITS)
    parser.add_argument("--compare", nargs=2, metavar=("RUN_A", "RUN_B"))
    args = parser.parse_args()
    if args.compare:
        return compare_runs(*args.compare)
    if not (args.version and args.split):
        parser.error("--version and --split are required")
    run_id = runner.run_split(args.version, args.split, OpenAIProvider(),
                              out_dir=REPORTS_DIR / f"{args.split}-{args.version}")
    with db.connect() as conn:
        run = db.get_run(conn, UUID(run_id))
    print(f"run_id {run_id} status {run['status']}\ncounts {json.dumps(run['counts'])}\n"
          f"metrics {json.dumps(run['metrics'])}")


if __name__ == "__main__":
    main()
