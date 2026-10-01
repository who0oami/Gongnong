"""Source-grounded handling of a deliberately small set of Korean endings.

This is not a morphology analyzer. Uncertain verb inflections stay verbatim.
"""
import re

_PROHIBITION = re.compile(
    r"(?P<head>.*?)(?P<verb>[가-힣]+)지\s*"
    r"(?:(?P<link>말고)\s+(?P<tail>.+)|(?:마세요|말아\s*주세요|말아요|마라))",
    re.DOTALL,
)
_UNNECESSARY = re.compile(
    r"(?P<head>.*?)(?P<verb>[가-힣]+)\s+필요(?:가|는)?\s*"
    r"(?:없어요|없습니다|없다|없어)", re.DOTALL,
)


def source_grounded_glosses(text: str) -> list[str] | None:
    """Return source-preserving tokens, or None when the grammar is unsupported.

    Particles and positive verb endings are retained deliberately: downstream
    normalization can handle them; guessing stems would undo semantic fidelity.
    """
    if not re.fullmatch(r"[가-힣0-9\s,.!?]+", text):
        return None
    sentence = text.strip().rstrip('.!').strip()
    if not sentence or any(ch in sentence for ch in '.!?'):
        return None  # No questions, quotations, or multi-sentence flattening.
    match = _PROHIBITION.fullmatch(sentence)
    if match:
        head, verb, tail = match.group('head', 'verb', 'tail')
        # The verb must begin at an eojeol boundary, not inside a noun.
        if head and not head[-1].isspace():
            return None
        if tail:
            # Accept a terminal request or another supported prohibition only.
            nested = source_grounded_glosses(tail)
            if nested is None:
                if re.search(r'지(?:도|는)?\s*(?:마|말|않)', tail) or not re.search(r"(?:으세요|세요|주세요)$", tail):
                    return None
                nested = tail.split()
        else:
            nested = []
        return head.split() + [verb + '다 금지'] + nested
    match = _UNNECESSARY.fullmatch(sentence)
    if match:
        head, verb = match.group('head', 'verb')
        if head and not head[-1].isspace():
            return None
        # Retain adnominal form (갈, 먹을, 열) rather than guessing its lemma.
        return head.split() + [verb + ' 필요 없다']
    return None
