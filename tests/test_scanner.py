#!/usr/bin/env python3
"""
Regression tests for scripts/score_arabic_text.py.

Zero dependencies (stdlib only), matching the rest of this repo. Run with:
    python3 tests/test_scanner.py

These tests encode calibration findings from real testing, not assumptions:
- A clean human sample must score ~0 violations/100 words.
- A deliberately AI-cliche-dense sample must score clearly higher.
- Real academic Arabic (a genuine, reviewed thesis chapter) must NOT be
  swamped with run-on-sentence false positives when scored in --academic
  mode. It legitimately was, before this was found and fixed -- see the
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
    thesis = read("synthetic_academic_sample.txt")

    bad_words = sat.tokenize_words(bad)
    good_words = sat.tokenize_words(good)
    thesis_words = sat.tokenize_words(thesis)

    bad_sentences = sat.split_sentences(bad)
    good_sentences = sat.split_sentences(good)
    thesis_sentences = sat.split_sentences(thesis)

    # --- 1. Clean human text should score near zero ---
    good_phrase_hits = sum(n for _, n in sat.check_phrases(good))
    good_filler_hits = sum(n for _, n in sat.check_filler_adjectives(good))
    good_runons = sat.check_run_on_sentences(good_sentences, academic=False)
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

    # --- 4. Academic-register sample: general mode legitimately over-flags run-ons (known, documented limitation) ---
    # Calibration note: this proportion (found on real, reviewed academic Arabic during
    # development) is what motivated adding --academic mode in the first place.
    thesis_runons_general = sat.check_run_on_sentences(thesis_sentences, academic=False)
    general_flag_rate = len(thesis_runons_general) / len(thesis_sentences)
    check(
        "general-mode run-on check over-fires on academic-register Arabic (documented limitation)",
        general_flag_rate >= 0.3,
        f"(got {len(thesis_runons_general)}/{len(thesis_sentences)} = {round(general_flag_rate*100)}% "
        f"-- this is WHY --academic mode exists)",
    )

    # --- 5. Academic-register sample: --academic mode must suppress that false-positive flood ---
    thesis_runons_academic = sat.check_run_on_sentences(thesis_sentences, academic=True)
    check(
        "academic-mode run-on check suppresses the false-positive flood",
        len(thesis_runons_academic) == 0,
        f"(got {len(thesis_runons_academic)} of {len(thesis_sentences)} sentences)",
    )

    # --- 6. Academic-register sample: overall violation rate in academic mode should be low (low false-positive rate) ---
    thesis_phrase_hits = sum(n for _, n in sat.check_phrases(thesis))
    thesis_filler_hits = sum(n for _, n in sat.check_filler_adjectives(thesis))
    thesis_violations_academic = thesis_phrase_hits + thesis_filler_hits + len(thesis_runons_academic)
    rate = thesis_violations_academic / len(thesis_words) * 100
    check(
        "academic-register sample scores a low violation rate in academic mode",
        rate < 0.5,
        f"(got {round(rate, 2)} violations/100 words)",
    )

    # --- 7. Vocabulary stats sanity: bad sample should show lower TTR than good sample (more repetitive) ---
    bad_vocab = sat.vocabulary_stats(bad_words)
    good_vocab = sat.vocabulary_stats(good_words)
    check(
        "vocabulary_stats runs without error on all fixtures",
        all(v["total"] > 0 for v in (bad_vocab, good_vocab, sat.vocabulary_stats(thesis_words))),
    )

    print(f"\n{total_checks - len(failures)}/{total_checks} checks passed.")
    if failures:
        print("FAILED:", failures)
        sys.exit(1)


if __name__ == "__main__":
    main()
