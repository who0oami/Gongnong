import csv
import re
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data"

WORD_CSV_PATH = DATA_DIR / "word3000_mapping.csv"
SEN_CSV_PATH = DATA_DIR / "sen_sentence_mapping.csv"
EMOTION_CSV_PATH = DATA_DIR / "감정단어_매핑결과_대체어포함.csv"

CODE_PATTERN = re.compile(r"(WORD\d+|SEN\d+)")


def _extract_code(raw_code: str) -> str | None:
    """코드 컬럼에 'SEN0280(표지판 보다 찾다)' 처럼 부가 설명이 붙은 경우가 있어
    WORD/SEN 코드 부분만 뽑아낸다."""
    if not raw_code:
        return None

    match = CODE_PATTERN.search(raw_code)

    return match.group(1) if match else None


def _load_word_map() -> dict[str, str]:
    """word3000_mapping.csv: word -> word_id (동일 단어가 여러 행에 있으면 먼저 나온 것을 사용)"""
    word_map: dict[str, str] = {}

    with open(WORD_CSV_PATH, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)

        for row in reader:
            word = (row.get("word") or "").strip()
            word_id = (row.get("word_id") or "").strip()

            if not word or not word_id:
                continue

            if word not in word_map:
                word_map[word] = word_id

    return word_map


def _load_sen_token_map() -> dict[str, str]:
    """SEN 문장 전체 표현 -> 코드. 문장 일부를 개별 단어 자산으로 쓰지 않는다."""
    token_map: dict[str, str] = {}

    with open(SEN_CSV_PATH, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)

        for row in reader:
            sen_id = (row.get("sen_id") or "").strip()
            sentence = row.get("sentence") or ""

            if not sen_id or not sentence:
                continue

            label = " ".join(sentence.split())
            if label and label not in token_map:
                token_map[label] = sen_id

    return token_map


def _load_emotion_maps() -> tuple[dict[str, tuple[str, str]], dict[str, tuple[str, str]]]:
    """감정단어_매핑결과_대체어포함.csv에서 두 개의 맵을 만든다.

    - found_map: gloss -> (발견단어, 코드)  ("발견단어"가 채워진 행만)
    - alt_map:   gloss -> (대체어, 코드)    ("대체어"가 채워진 행만, 코드는 대체어 옆의 빈 이름 컬럼)

    같은 gloss가 여러 행에 걸쳐 있으면 먼저 나온 것을 사용한다.
    """
    found_map: dict[str, tuple[str, str]] = {}
    alt_map: dict[str, tuple[str, str]] = {}

    with open(EMOTION_CSV_PATH, encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f)
        next(reader, None)  # header (빈 이름 컬럼 포함, 인덱스로 직접 접근)

        for row in reader:
            if len(row) < 7:
                row = row + [""] * (7 - len(row))

            group_raw, _status, found_word, found_code, _blank1, alt_word, alt_code = row[:7]

            group_words = [w.strip() for w in group_raw.split("/") if w.strip()]

            found_word = found_word.strip()
            found_code = _extract_code(found_code.strip())

            alt_word = alt_word.strip()
            alt_code = _extract_code(alt_code.strip())

            for word in group_words:
                if found_word and found_code and word not in found_map:
                    found_map[word] = (found_word, found_code)

                if alt_word and alt_code and word not in alt_map:
                    alt_map[word] = (alt_word, alt_code)

    return found_map, alt_map


_WORD_MAP = _load_word_map()
_SEN_TOKEN_MAP = _load_sen_token_map()
_EMOTION_FOUND_MAP, _EMOTION_ALT_MAP = _load_emotion_maps()

# LLM이 사전형 정규화를 지시받아도 문장 끝 gloss에 조사를 남기는 경우가 있어
# (예: "학교에" -> vocabulary는 "학교"), 흔한 조사만 제거해 재시도한다. 어미/활용
# 분석기는 쓰지 않으므로 실제 조사가 아닌 마지막 글자가 우연히 겹치는 경우도
# 있을 수 있다 (예: "이가" -> "이"). 길이가 더 긴 조사부터 시도해 오탐을 줄인다.
_JOSA_SUFFIXES = sorted(
    [
        "이라고", "이라는", "라고", "라는", "에서", "에게", "으로", "처럼", "만큼",
        "부터", "까지", "이랑", "랑", "께", "은", "는", "이", "가", "을", "를",
        "의", "에", "와", "과", "도", "만", "로",
    ],
    key=len,
    reverse=True,
)

def _valid_synonym_asset(label: str, code: str) -> bool:
    # CSV의 명시적 대체어는 유지하되, SEN 문장 일부만 가리키는 연결은 제외한다.
    if code.startswith("SEN"):
        return _SEN_TOKEN_MAP.get(" ".join(label.split())) == code
    return True


def _lookup_exact(token: str) -> dict | None:
    # 1. word3000_mapping.csv 직접 일치
    word_id = _WORD_MAP.get(token)
    if word_id:
        return {"matched_word": token, "source": "WORD", "code": word_id}

    # 2. SEN 전체 표현 일치 (단일 토큰 문장도 포함)
    sen_id = _SEN_TOKEN_MAP.get(token)
    if sen_id:
        return {"matched_word": token, "source": "SEN", "code": sen_id}

    # 3. 감정단어 매핑 - 발견단어
    found = _EMOTION_FOUND_MAP.get(token)
    if found and _valid_synonym_asset(*found):
        found_word, code = found
        return {"matched_word": found_word, "source": "SYNONYM_FOUND", "code": code}

    # 4. 감정단어 매핑 - 대체어
    alt = _EMOTION_ALT_MAP.get(token)
    if alt and _valid_synonym_asset(*alt):
        alt_word, code = alt
        return {"matched_word": alt_word, "source": "SYNONYM_ALTERNATIVE", "code": code}

    return None


def _strip_josa_candidates(token: str):
    for suffix in _JOSA_SUFFIXES:
        if token.endswith(suffix) and len(token) > len(suffix):
            yield token[: -len(suffix)]


def _match_single_gloss(gloss: str) -> dict:
    result = {
        "gloss": gloss,
        "matched": False,
        "matched_word": None,
        "source": None,
        "code": None,
        "match_type": None,
    }

    # 1. 완전 일치
    exact = _lookup_exact(gloss)
    if exact:
        result.update(matched=True, match_type="exact", **exact)
        return result

    # 2. 조사 제거 후 재일치
    for candidate in _strip_josa_candidates(gloss):
        normalized = _lookup_exact(candidate)
        if normalized:
            result.update(matched=True, match_type="normalized", **normalized)
            return result

    # 3. 매칭 실패
    #
    # 자모 단위 difflib 유사도로 문자열이 가까운 vocabulary 항목을 후보로
    # 대신 쓰는 방식도 시도했지만 채택하지 않았다: 한국어 동사는 "-다"/"-하다"
    # 어미를 공유하는 경우가 매우 흔해서, 어간이 전혀 다른 단어끼리도 (예:
    # "않다"->"알다", "사랑하다"->"상상하다") 오탐과 같은 수준의 유사도가
    # 나온다. 틀린 수어를 맞는 것처럼 보여주는 것은 캡션으로 대체하는 것보다
    # 나쁘므로, 형태소 분석기 없이는 이 이상의 후보 검색을 넣지 않는다.
    return result


def match_gloss_sequence(gloss_list: list[str]) -> list[dict]:
    # 하나의 입력 segment 전체가 SEN 표현과 일치할 때 클립을 한 번만 재생한다.
    # 부분 구간 탐색, 어순 변경, 조사 제거를 통한 문장 결합은 하지 않는다.
    phrase = " ".join(gloss_list)
    if len(gloss_list) > 1 and phrase in _SEN_TOKEN_MAP:
        return [{"gloss": phrase, "matched": True, "matched_word": phrase,
                 "source": "SEN", "code": _SEN_TOKEN_MAP[phrase], "match_type": "exact"}]
    return [_match_single_gloss(gloss) for gloss in gloss_list]


def build_display_sequence(gloss_list: list[str]) -> list[dict]:
    """Frontend에 전달할 화면 표시 순서를 만든다.

    매칭 성공한 gloss는 아바타 클립으로, 매칭 실패한 gloss는 원본 텍스트를
    그대로 보여주는 자막으로 변환한다.
    """
    matches = match_gloss_sequence(gloss_list)
    sequence: list[dict] = []

    for match in matches:
        if match["matched"]:
            sequence.append({
                "type": "avatar",
                "gloss": match["gloss"],
                "code": match["code"],
                "source": match["source"],
            })
        else:
            sequence.append({
                "type": "caption",
                "text": match["gloss"],
            })

    return sequence


if __name__ == "__main__":
    import json

    sample = match_gloss_sequence(["오늘", "슬프다", "미안", "기쁨"])
    print(json.dumps(sample, ensure_ascii=False, indent=2))

    display_sample = build_display_sequence(["오늘", "슬프다", "미안", "기쁨"])
    print(json.dumps(display_sample, ensure_ascii=False, indent=2))
