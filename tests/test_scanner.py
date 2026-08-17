#!/usr/bin/env python3
"""
Regression tests for scripts/score_arabic_text.py.

Zero dependencies (stdlib only), matching the rest of this repo. Run with:
    python3 tests/test_scanner.py

These tests encode calibration findings from real testing, not assumptions:
- A clean human sample must score ~0 violations/100 words.
- A deliberately AI-cliche-dense sample must score clearly higher.
- A long-form, formally structured Arabic sample must NOT be swamped with
  run-on-sentence false positives when scored in --formal mode. It
  legitimately was, before this was found and fixed -- see the
  check_run_on_sentences docstring and patterns.md pattern #18.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import score_arabic_text as sat  # noqa: E402

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")

failures = []
total_checks = 0


def check(name, condition, detail=""):
    global total_checks
    total_checks += 1
    status = "PASS" if condition else "FAIL"
    print(f"[{status}] {name} {detail}")
    if not condition:
        failures.append(name)


def read(fname):
    with open(os.path.join(FIXTURES, fname), encoding="utf-8") as f:
        return f.read()


def main():
    bad = read("bad_ai_sample.txt")
    good = read("good_human_sample.txt")
    formal_sample = read("synthetic_formal_sample.txt")

    bad_words = sat.tokenize_words(bad)
    good_words = sat.tokenize_words(good)
    formal_words = sat.tokenize_words(formal_sample)

    bad_sentences = sat.split_sentences(bad)
    good_sentences = sat.split_sentences(good)
    formal_sentences = sat.split_sentences(formal_sample)

    # --- 1. Clean human text should score near zero ---
    good_phrase_hits = sum(n for _, n in sat.check_phrases(good))
    good_filler_hits = sum(n for _, n in sat.check_filler_adjectives(good))
    good_runons = sat.check_run_on_sentences(good_sentences, formal=False)
    check("clean human sample has zero banned-phrase hits", good_phrase_hits == 0, f"(got {good_phrase_hits})")
    check("clean human sample has zero filler-adjective hits", good_filler_hits == 0, f"(got {good_filler_hits})")
    check("clean human sample has zero run-on flags (general mode)", len(good_runons) == 0, f"(got {len(good_runons)})")

    # --- 2. AI-cliche-dense text should score clearly higher ---
    bad_phrase_hits = sum(n for _, n in sat.check_phrases(bad))
    check("AI-cliche sample has multiple banned-phrase hits", bad_phrase_hits >= 8, f"(got {bad_phrase_hits})")
    bad_punct = sat.check_foreign_punctuation(bad)
    check("AI-cliche sample's em dash is detected", bad_punct["em_dash"] >= 1, f"(got {bad_punct['em_dash']})")

    # --- 3. Diacritics check must NOT flag either synthetic sample (regression for the fixed bug) ---
    good_diac = sat.check_diacritics(good)
    bad_diac = sat.check_diacritics(bad)
    check("diacritics check never flags (informational-only fix)", good_diac["flag"] is False and bad_diac["flag"] is False)

    # --- 4. Formal-register sample: general mode legitimately over-flags run-ons (known, documented limitation) ---
    # Calibration note: this proportion (found on a long-form, formally structured Arabic
    # sample during development) is what motivated adding --formal mode in the first place.
    formal_runons_general = sat.check_run_on_sentences(formal_sentences, formal=False)
    general_flag_rate = len(formal_runons_general) / len(formal_sentences)
    check(
        "general-mode run-on check over-fires on formal-register Arabic (documented limitation)",
        general_flag_rate >= 0.3,
        f"(got {len(formal_runons_general)}/{len(formal_sentences)} = {round(general_flag_rate*100)}% "
        f"-- this is WHY --formal mode exists)",
    )

    # --- 5. Formal-register sample: --formal mode must suppress that false-positive flood ---
    formal_runons_formal = sat.check_run_on_sentences(formal_sentences, formal=True)
    check(
        "formal-mode run-on check suppresses the false-positive flood",
        len(formal_runons_formal) == 0,
        f"(got {len(formal_runons_formal)} of {len(formal_sentences)} sentences)",
    )

    # --- 6. Formal-register sample: overall violation rate in formal mode should be low (low false-positive rate) ---
    # Note: FILLER_ADJECTIVES contains single common words (e.g. استثنائي, حيوي) that have
    # legitimate literal uses ("exceptional case", "vital activity") outside AI-puffery
    # phrasing, so an occasional single incidental hit on ordinary formal text is expected
    # and is not itself a bug -- the bar here is "clearly low", not "exactly zero". A
    # systematic flood (like the run-on false-positive this suite regression-tests above)
    # would be the real problem.
    formal_phrase_hits = sum(n for _, n in sat.check_phrases(formal_sample))
    formal_filler_hits = sum(n for _, n in sat.check_filler_adjectives(formal_sample))
    formal_violations = formal_phrase_hits + formal_filler_hits + len(formal_runons_formal)
    rate = formal_violations / len(formal_words) * 100
    check(
        "formal-register sample scores a low violation rate in formal mode",
        rate < 1.0,
        f"(got {round(rate, 2)} violations/100 words)",
    )

    # --- 7. Tatweel check must not flag the standard Hijri-year abbreviation (regression) ---
    # Found via testing on real dated formal Arabic text: "1443هـ" was flagged as
    # decorative tatweel/kashida when it's actually the standard AH-calendar marker.
    hijri_text = "صدر القرار عام 1443هـ الموافق 2022م، وتم تطبيقه عام 1444هـ لاحقًا."
    hijri_tatweel = sat.check_tatweel(hijri_text)
    check(
        "tatweel check does not flag the Hijri-year abbreviation (هـ)",
        hijri_tatweel["count"] == 0 and hijri_tatweel["flag"] is False,
        f"(got count={hijri_tatweel['count']}, flag={hijri_tatweel['flag']})",
    )
    real_tatweel_text = "وهذا امتداد غير مبرر في الكلمة ـــــ لأغراض التنضيد فقط."
    real_tatweel = sat.check_tatweel(real_tatweel_text)
    check(
        "tatweel check still flags genuine decorative elongation",
        real_tatweel["count"] > 0 and real_tatweel["flag"] is True,
        f"(got count={real_tatweel['count']}, flag={real_tatweel['flag']})",
    )

    # --- 8. Light-verb calque check (regression for the fixed VSO/prefix-attachment bug) ---
    # The first version of this regex matched zero real sentences, including its own
    # worked example in patterns.md #26, because it missed that ب- attaches as a bound
    # prefix (بإجراء, not "ب إجراء") and that Arabic VSO order puts the subject between
    # the verb and بـ ("قامت الشركة بإجراء..."). Locking in the fix plus the deliberate
    # precision tradeoff (curated verbal-noun list, not "verb + any ب-word").
    light_verb_hit = sat.check_light_verb_overuse(
        "قامت الشركة بإجراء دراسة شاملة حول احتياجات العملاء."
    )
    check(
        "light-verb check catches the calque construction (قامت...بإجراء)",
        light_verb_hit["count"] >= 1 and light_verb_hit["flag"] is True,
        f"(got {light_verb_hit})",
    )
    light_verb_clean = sat.check_light_verb_overuse("درست الشركة احتياجات العملاء بشكل شامل.")
    check(
        "light-verb check does not flag the direct-verb rewrite",
        light_verb_clean["count"] == 0 and light_verb_clean["flag"] is False,
        f"(got {light_verb_clean})",
    )
    light_verb_real_verb = sat.check_light_verb_overuse("قام الرجل بسرعة ليفتح الباب.")
    check(
        "light-verb check does not flag قام used as a real verb + adverb (قام بسرعة)",
        light_verb_real_verb["count"] == 0,
        f"(got {light_verb_real_verb})",
    )

    # --- 9. Vocabulary stats sanity: all fixtures should compute without error ---
    bad_vocab = sat.vocabulary_stats(bad_words)
    good_vocab = sat.vocabulary_stats(good_words)
    check(
        "vocabulary_stats runs without error on all fixtures",
        all(v["total"] > 0 for v in (bad_vocab, good_vocab, sat.vocabulary_stats(formal_words))),
    )

    print(f"\n{total_checks - len(failures)}/{total_checks} checks passed.")
    if failures:
        print("FAILED:", failures)
        sys.exit(1)


if __name__ == "__main__":
    main()
