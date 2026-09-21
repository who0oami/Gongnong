import unittest
from unittest.mock import patch

from services import gloss_matcher


class GlossMatcherTest(unittest.TestCase):
    def setUp(self):
        word_map = {"고민": "WORD0001", "학교": "WORD0002", "알다": "WORD0003"}
        sen_token_map = {"천천히": "SEN0009"}
        emotion_found_map = {"슬프다": ("슬프다", "WORD0009")}
        emotion_alt_map = {"기쁨": ("기쁘다", "WORD0100")}

        patches = [
            patch.dict(gloss_matcher._WORD_MAP, word_map, clear=True),
            patch.dict(gloss_matcher._SEN_TOKEN_MAP, sen_token_map, clear=True),
            patch.dict(gloss_matcher._EMOTION_FOUND_MAP, emotion_found_map, clear=True),
            patch.dict(gloss_matcher._EMOTION_ALT_MAP, emotion_alt_map, clear=True),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)

    def test_exact_word_match(self):
        result = gloss_matcher._match_single_gloss("고민")
        self.assertEqual(
            result,
            {
                "gloss": "고민",
                "matched": True,
                "matched_word": "고민",
                "source": "WORD",
                "code": "WORD0001",
                "match_type": "exact",
            },
        )

    def test_exact_sen_token_match(self):
        result = gloss_matcher._match_single_gloss("천천히")
        self.assertEqual(result["source"], "SEN")
        self.assertEqual(result["code"], "SEN0009")
        self.assertEqual(result["match_type"], "exact")

    def test_exact_emotion_found_and_alt_match(self):
        found = gloss_matcher._match_single_gloss("슬프다")
        self.assertEqual(found["source"], "SYNONYM_FOUND")

        alt = gloss_matcher._match_single_gloss("기쁨")
        self.assertEqual(alt["source"], "SYNONYM_ALTERNATIVE")

    def test_josa_suffix_is_stripped_when_exact_lookup_fails(self):
        result = gloss_matcher._match_single_gloss("학교에서")
        self.assertTrue(result["matched"])
        self.assertEqual(result["match_type"], "normalized")
        self.assertEqual(result["matched_word"], "학교")
        self.assertEqual(result["code"], "WORD0002")

    def test_josa_stripping_tries_longest_suffix_first(self):
        with patch.dict(gloss_matcher._WORD_MAP, {"학교": "WORD0002", "학교이": "WORD0999"}):
            result = gloss_matcher._match_single_gloss("학교이라는")
            self.assertEqual(result["matched_word"], "학교")
        self.assertEqual(
            list(gloss_matcher._strip_josa_candidates("학교이라는")),
            ["학교", "학교이", "학교이라"],
        )

    def test_josa_stripping_does_not_fire_when_exact_match_already_succeeds(self):
        with patch.dict(gloss_matcher._WORD_MAP, {"학교가": "WORD0999"}):
            result = gloss_matcher._match_single_gloss("학교가")
        self.assertEqual(result["match_type"], "exact")
        self.assertEqual(result["code"], "WORD0999")

    def test_similar_spelling_with_unrelated_meaning_is_not_silently_matched(self):
        # "않다" (negation) and "알다" (to know) differ by a single jamo and
        # would score highly under naive character-similarity fuzzy matching,
        # but they are unrelated signs. No fuzzy tier means this correctly
        # falls through to "no match" instead of substituting the wrong sign.
        result = gloss_matcher._match_single_gloss("않다")
        self.assertFalse(result["matched"])

    def test_no_match_returns_unmatched_result(self):
        result = gloss_matcher._match_single_gloss("완전히다른단어")
        self.assertEqual(
            result,
            {
                "gloss": "완전히다른단어",
                "matched": False,
                "matched_word": None,
                "source": None,
                "code": None,
                "match_type": None,
            },
        )

    def test_build_display_sequence_still_returns_avatar_and_caption_items(self):
        sequence = gloss_matcher.build_display_sequence(["고민", "완전히다른단어"])
        self.assertEqual(
            sequence,
            [
                {"type": "avatar", "gloss": "고민", "code": "WORD0001", "source": "WORD"},
                {"type": "caption", "text": "완전히다른단어"},
            ],
        )


class SentenceAssetTest(unittest.TestCase):
    def test_real_csv_does_not_index_sentence_fragments(self):
        mapping = gloss_matcher._load_sen_token_map()
        self.assertNotEqual(mapping.get("우산"), "SEN1298")
        self.assertEqual(mapping["우산 잃어버리다"], "SEN1298")
        self.assertNotEqual(mapping.get("오늘"), "SEN0253")
        self.assertEqual(mapping["오늘 하루 수고"], "SEN0253")

    def test_real_sentence_sequence_plays_once(self):
        result = gloss_matcher.build_display_sequence(["우산", "잃어버리다"])
        self.assertEqual(result, [{"type": "avatar", "gloss": "우산 잃어버리다",
                                  "code": "SEN1298", "source": "SEN"}])

    def test_partial_reordered_and_extended_sequences_do_not_select_sentence(self):
        for tokens in (["우산"], ["잃어버리다", "우산"], ["우산", "잃어버리다", "않다"]):
            with self.subTest(tokens=tokens):
                self.assertNotIn("SEN1298", [m["code"] for m in gloss_matcher.match_gloss_sequence(tokens)])

    def test_emotion_alias_cannot_point_to_sentence_fragment(self):
        self.assertFalse(gloss_matcher._valid_synonym_asset("보다", "SEN0280"))
        self.assertTrue(gloss_matcher._valid_synonym_asset("표지판 보다 찾다", "SEN0280"))
        with patch.dict(gloss_matcher._WORD_MAP, {}, clear=True), patch.dict(
            gloss_matcher._EMOTION_ALT_MAP, {"검증표현": ("보다", "SEN0280")}, clear=True
        ):
            self.assertFalse(gloss_matcher._match_single_gloss("검증표현")["matched"])

    def test_all_real_sen_keys_are_full_csv_labels(self):
        import csv
        with gloss_matcher.SEN_CSV_PATH.open(encoding="utf-8-sig", newline="") as handle:
            labels = {" ".join(row["sentence"].split()) for row in csv.DictReader(handle)}
        self.assertEqual(set(gloss_matcher._load_sen_token_map()), labels)


if __name__ == "__main__":
    unittest.main()
