"""Conservative checks for known gloss errors, not a Korean semantic parser."""
import re
from collections import Counter

# Long expressions first: negative obligation must not become generic absence.
_MODAL = re.compile(
    r"필요(?:가|는|도)?\s*없|불필요|"
    r"지\s*말|지\s*마|(?<![가-힣])말다|면\s*안\s*(?:돼|되)|금지|"
    r"도\s*(?:돼|되)|허락|허용|"
    r"(?:할\s*)?수\s*없|(?<![가-힣])못(?=\s|하|해|했|한다|$)|불가능|"
    r"(?:할\s*)?수\s*있|(?<![가-힣])가능(?=하다|해|$)|"
    r"않|아니(?:라|다|에|었|야|요|오)|없|(?<![가-힣])안(?=\s|돼|되|해|하|했|$)"
)


def _modalities(text):
    found = []
    for match in _MODAL.finditer(text):
        token = re.sub(r"\s+", "", match.group())
        if token.startswith(('필요', '불필요')): kind = 'unnecessary'
        elif token.startswith(('지말', '지마', '말다', '면안', '금지')): kind = 'prohibited'
        elif token.startswith(('도돼', '도되', '허락', '허용')): kind = 'permitted'
        elif token.startswith(('할수없', '수없', '못', '불가능')): kind = 'unable'
        elif token.startswith(('할수있', '수있', '가능')): kind = 'able'
        else: kind = 'negative'
        found.append(kind)
    return found


def validation_issues(source: str, glosses: list[str]) -> list[str]:
    output = ' '.join(glosses)
    issues = []
    # Matching direction words is only a lexical check, not a spatial-relation proof.
    directions = ('왼쪽', '오른쪽', '아래', '위쪽', '앞쪽', '뒤쪽', '안쪽', '바깥쪽')
    def direction_sequence(text):
        return re.findall('|'.join(directions) + r'|(?<![가-힣])(?:위|앞|뒤|밖)(?=으로|로|에서|에|을|은|이|\s|$)', text)
    if direction_sequence(source) != direction_sequence(output):
        issues.append('direction_changed')
    def numbers(text):
        return Counter(re.findall(r'(?<![0-9])[0-9]+(?:[./][0-9]+)?', text))
    if numbers(source) != numbers(output):
        issues.append('quantity_changed')
    source_modes, output_modes = _modalities(source), _modalities(output)
    if source_modes != output_modes:
        issues.append('modality_changed')
    # Check directly observable -지 말다/-지 않다 scope, without rejecting
    # every sentence that contains a conjunction. Other constructions remain
    # outside this limited check; passing is not semantic certification.
    for match in re.finditer(r"([가-힣]+?)지\s*(말|마|않)", source):
        stem, operator = match.groups()
        marker = r"(?:금지|말다|말|마)" if operator in ("말", "마") else r"(?:않다|않|안)"
        pattern = r"(?<![가-힣])" + re.escape(stem) + r"(?:다|지)?\s*" + marker
        if not re.search(pattern, output):
            issues.append('negation_target_changed')
            break
    malformed = {'와다', '해다', '돼다', '하지마다'}
    if any(token in malformed and token not in source for token in glosses):
        issues.append('malformed_dictionary_form')
    if source.strip() and not glosses:
        issues.append('empty_output')
    return issues


def normalize_observed_forms(source: str, glosses: list[str]) -> list[str]:
    """Repair only observed malformed forms with a supporting source conjugation."""
    repairs = {
        '와다': ('오다', r'(?<![가-힣])(?:와|왔)(?:요|서|도|다|어요|습니다|고|$)'),
        '해다': ('하다', r'(?<![가-힣])(?:해|했)(?:요|서|도|다|어요|습니다|고|$)'),
        '돼다': ('되다', r'(?<![가-힣])(?:돼|됐)(?:요|서|도|다|어요|습니다|고|$)'),
    }
    result = []
    for token in glosses:
        repair = repairs.get(token)
        if repair and token not in source and re.search(repair[1], source):
            token = repair[0]
        result.append(token)
    return result
