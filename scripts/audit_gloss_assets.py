"""Read-only CSV, gloss and rendered-video audit; no model calls or file moves."""
import argparse
import csv
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from services import gloss_matcher as matcher
from services.local_llm_gloss_service import _SYSTEM_PROMPT

CODE = re.compile(r"(?<![A-Z0-9])(WORD[0-9]+|SEN[0-9]+)(?![A-Z0-9])", re.I)


def read_catalog():
    catalog = defaultdict(list)
    for path, id_key, text_key in (
        (matcher.WORD_CSV_PATH, "word_id", "word"),
        (matcher.SEN_CSV_PATH, "sen_id", "sentence"),
    ):
        with path.open(encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                catalog[row[id_key]].append({"text": row[text_key], "status": row.get("status", "")})
    return dict(catalog)


def inventory(folder, catalog):
    candidates = defaultdict(list)
    unclassified = []
    empty = []
    for path in sorted(folder.rglob("*")):
        if not path.is_file() or path.suffix.lower() != ".mp4":
            continue
        codes = set(code.upper() for code in CODE.findall(path.stem))
        if path.stat().st_size == 0:
            empty.append(str(path))
        if len(codes) != 1:
            unclassified.append(str(path))
            continue
        candidates[codes.pop()].append(str(path))
    return {
        "folder": str(folder),
        "candidates": dict(candidates),
        "missing_codes": sorted(set(catalog) - set(candidates)),
        "unknown_codes": sorted(set(candidates) - set(catalog)),
        "duplicate_candidates": {code: paths for code, paths in candidates.items() if len(paths) > 1},
        "unclassified_files": unclassified,
        "empty_files": empty,
        "backend_named_codes": sorted(code for code in catalog if (folder / (code + ".mp4")).is_file()),
    }


def evaluate(cases, catalog):
    rows = []
    for case in cases:
        for match in matcher.match_gloss_sequence(case["glosses"]):
            entries = catalog.get(match["code"], [])
            rows.append({
                "input": case.get("input"), **match,
                "asset_labels": [entry["text"] for entry in entries],
                "review_sentence_asset": bool(match["code"] and match["code"].startswith("SEN")),
                "backend_clip_exists": bool(match["code"] and (ROOT / "backend/static/videos" / (match["code"] + ".mp4")).is_file()),
            })
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--videos", type=Path, help="Final render folder; scanned recursively, never modified")
    parser.add_argument("--cases", type=Path, help='JSON list of {"input": "original text", "glosses": ["..."]} containing saved model outputs')
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.videos is not None and not args.videos.is_dir():
        parser.error("--videos must be an existing directory")
    if args.output.exists():
        parser.error("--output already exists; choose a new report path")
    cases = []
    sentence = None
    for line in _SYSTEM_PROMPT.splitlines():
        if line.startswith("입력: "):
            sentence = line.removeprefix("입력: ")
        elif line.startswith("출력: "):
            cases.append({"input": sentence, **json.loads(line.removeprefix("출력: "))})
    if args.cases:
        cases = json.loads(args.cases.read_text(encoding="utf-8-sig"))
    if not isinstance(cases, list) or any(not isinstance(case, dict) or not isinstance(case.get("glosses"), list) or any(not isinstance(token, str) for token in case["glosses"]) for case in cases):
        parser.error("cases must be a list of objects containing glosses as a list of strings")
    catalog = read_catalog()
    rows = evaluate(cases, catalog)
    summary = {
        "catalog_codes": len(catalog),
        "word_codes": sum(code.startswith("WORD") for code in catalog),
        "sen_codes": sum(code.startswith("SEN") for code in catalog),
        "gloss_count": len(rows),
        "match_types": dict(Counter(row["match_type"] or "unmatched" for row in rows)),
        "sentence_asset_review_count": sum(row["review_sentence_asset"] for row in rows),
    }
    report = {
        "summary": summary,
        "cases_source": str(args.cases) if args.cases else "system_prompt_examples (not live LLM outputs)",
        "matches": rows,
        "catalog": catalog,
        "videos": inventory(args.videos.resolve(), catalog) if args.videos else None,
        "limitations": "Code/file matches do not establish semantic correctness or playable video. Review SEN clips and render variants manually. No files are deployed.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2)
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
