"""Keep an incomplete sign sequence from changing the meaning of a segment."""
from services.gloss_matcher import build_display_sequence
from services.clip_resolver import resolve_clip_path
from services.gloss_output_validation import _modalities


def caption_sequence(source_text: str) -> list[dict]:
    return [{"type": "caption", "text": source_text}]


def build_complete_display_sequence(source_text: str, glosses: list[str]) -> list[dict]:
    items = build_display_sequence(glosses)
    if not items:
        return caption_sequence(source_text)
    resolved = [
        {"type": "caption", "text": item["gloss"]}
        if item["type"] == "avatar" and resolve_clip_path(item["code"]) is None else item
        for item in items
    ]
    # Ordinary missing nouns must not suppress valid signs. A missing modality
    # in a negated segment is different: displaying an affirmative action alone
    # is unsafe, so retain the source for that limited fallback case.
    if any(item["type"] == "caption" and _modalities(item["text"]) for item in resolved):
        return caption_sequence(source_text)
    return resolved
