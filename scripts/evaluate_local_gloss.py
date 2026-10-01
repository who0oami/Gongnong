"""Evaluate saved caption CSV rows through the actual local gloss service."""
import argparse
import csv
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from services.local_llm_gloss_service import convert_to_gloss_local, LocalGlossConversionError
from audit_gloss_assets import evaluate, read_catalog


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--captions", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--base-url", default="http://127.0.0.1:11434")
    parser.add_argument("--model", default="qwen2.5:3b")
    args = parser.parse_args()
    if args.limit < 1:
        parser.error("--limit must be positive")
    if args.output.exists():
        parser.error("Choose a new --output directory")
    with args.captions.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if "sentence" not in (reader.fieldnames or []):
            parser.error("Caption CSV requires a sentence column")
        selected = []
        for row in reader:
            if row["sentence"].strip():
                selected.append(row)
                if len(selected) == args.limit:
                    break
    os.environ["OLLAMA_BASE_URL"] = args.base_url
    os.environ["OLLAMA_GLOSS_MODEL"] = args.model
    args.output.mkdir(parents=True)
    cases, failures = [], []
    catalog = read_catalog()
    with (args.output / "attempts.jsonl").open("x", encoding="utf-8") as handle:
        for row in selected:
            case = {"source_id": row.get("source_id"), "input": row["sentence"]}
            try:
                case["glosses"] = convert_to_gloss_local(case["input"])
                case["matches"] = evaluate([case], catalog)
                case["semantic_review"] = "pending: negation, quantity, time, additions and source-caption errors"
                cases.append(case)
            except LocalGlossConversionError as exc:
                case["error"] = str(exc)
                failures.append(case)
            handle.write(json.dumps(case, ensure_ascii=False) + "\n")
            handle.flush()
            print(f"{len(cases) + len(failures)}/{len(selected)} processed", flush=True)
            # Avoid repeating a connection failure for every caption.
            if failures and not cases:
                break
    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "captions": str(args.captions), "model": args.model,
        "selected": len(selected), "succeeded": len(cases), "failed": len(failures),
        "unattempted": len(selected) - len(cases) - len(failures),
        "cases": cases, "failures": failures,
        "limitations": "Raw captions; subtitle correction and demo overrides bypassed. Code coverage is not translation accuracy. Human semantic and video review pending.",
    }
    (args.output / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    (args.output / "cases.json").write_text(json.dumps(cases, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Succeeded: {len(cases)}, failed: {len(failures)}")
    return 1 if failures or not cases else 0


if __name__ == "__main__":
    raise SystemExit(main())
