"""Draft an occupant candidate for every pending, undrafted worksheet row.

    uv run --group agent python scripts/research_occupants.py
    uv run --group agent python scripts/research_occupants.py --limit 5
    uv run --group agent python scripts/research_occupants.py --redraft

Needs an Anthropic credential: ANTHROPIC_API_KEY, or an `ant auth login`
profile, which the SDK picks up on its own.

By default this only touches rows that are pending AND have no candidate
drafted yet, so re-running it is cheap and never discards research. --redraft
re-researches every pending, unreviewed row, drafted or not.

It writes three columns and no status. Promotion into data/occupants.csv is a
separate, human step: mark a row `verified`, initial it, then run
scripts/promote_occupants.py.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import anthropic

from shave import occupant_agent, occupant_worksheet


def pending_rows(path: Path, redraft: bool) -> list[dict]:
    """Rows a re-run may touch: pending, not initialled by anyone, and either
    undrafted or explicitly being redrafted."""
    return [
        row
        for row in occupant_worksheet._read(path).values()
        if (row.get("status") or "").strip().lower() == "pending"
        and not (row.get("reviewer") or "").strip()
        and (redraft or not (row.get("candidate_occupant") or "").strip())
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=0,
                        help="stop after this many rows; 0 means all")
    parser.add_argument("--redraft", action="store_true",
                        help="also re-research rows that already have a candidate")
    parser.add_argument("--path", default=str(occupant_worksheet.CANDIDATES_PATH))
    args = parser.parse_args()

    path = Path(args.path)
    todo = pending_rows(path, args.redraft)
    if args.limit:
        todo = todo[: args.limit]
    if not todo:
        print("nothing pending to research", file=sys.stderr)
        return 0

    client = anthropic.Anthropic()
    findings: dict[str, dict] = {}
    failed: list[str] = []
    for i, row in enumerate(todo, start=1):
        label = f"[{i}/{len(todo)}] {row['town']} {row['site_addr']}"
        try:
            found = occupant_agent.research(client, row)
        except occupant_agent.OccupantAgentError as exc:
            # One bad row must not cost the rest of the run. It stays pending
            # and undrafted, which is what it already was.
            failed.append(row["loc_id"])
            print(f"{label}: FAILED {exc}", file=sys.stderr)
            continue
        findings[row["loc_id"]] = found
        print(f"{label}: {found['candidate_occupant'] or '(no confident match)'}",
              file=sys.stderr)

    written = occupant_worksheet.update_research(path, findings)
    named = sum(1 for f in findings.values() if f["candidate_occupant"])
    print(f"\ndrafted {written} row(s) into {path}", file=sys.stderr)
    print(f"  {named} with a name, {len(findings) - named} with no confident match",
          file=sys.stderr)
    if failed:
        print(f"  {len(failed)} failed and stay pending: {', '.join(failed)}",
              file=sys.stderr)
    print("\nNothing is published yet. Review each row, set status to verified or "
          "rejected, initial the reviewer column, then run "
          "scripts/promote_occupants.py.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
