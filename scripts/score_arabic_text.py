#!/usr/bin/env python3
"""
humanizer-ar mechanical scanner.

Scores Arabic text for statistical and orthographic markers associated with
LLM-generated Arabic (grounded in Al-Shaibani & Ahmed 2025's stylometric
findings) plus a phrase catalog of common Arabic AI-writing cliches.

This is a diagnostic aid, not a verdict. See references/patterns.md and the
"AI Text Detectors and the Misclassification of Slightly Polished Arabic Text"
caution: automated Arabic AI-detectors have real false-positive rates on
lightly-edited human text. Treat every flag as "worth a human look", not proof.
"""
import re
import sys
import statistics
from typing import Any

# ---------------------------------------------------------------------------
# Pattern catalog (mirrors references/patterns.md)
# ---------------------------------------------------------------------------

BANNED_PHRASES = [
    "تجدر الإشارة إلى", "تجدر الإشارة الى", "من الجدير بالذكر", "علاوة على ذلك",
    "بالإضافة إلى ذلك", "بالاضافة الى ذلك", "في هذا السياق", "في ضوء ما سبق",
    "انطلاقا مما سبق", "انطلاقاً مما سبق", "في نهاية المطاف", "وفي الختام",
    "وختاما", "وختاماً", "دون شك", "بلا شك", "يعد بمثابة", "يُعد بمثابة",
    "يشكل شاهدا", "يشكل شاهداً", "يعد شاهدا", "حجر الزاوية", "نقلة نوعية",
    "يفتح آفاقا", "يفتح آفاقاً", "في عالم يتسم", "في ظل التطورات المتسارعة",
    "نابض بالحياة", "لا يقتصر", "ليس فقط", "سؤال رائع", "اتمنى ان يكون هذا مفيدا",
    "أتمنى أن يكون هذا مفيدا", "أتمنى أن يكون هذا مفيداً", "كمساعد ذكاء اصطناعي",
    "لا يسعني الجزم", "مما يسلط الضوء", "مما يعكس", "مما يؤكد على",
    "وهو ما يبرز", "يرى الخبراء", "يعتقد الخبراء", "يعتقد المختصون",
    "تشير الدراسات إلى", "تشير الدراسات الى", "من المعروف أن", "من المعروف ان",
    "يجمع كثير من", "محطة فارقة", "علامة فارقة",
]

# adjectives/fillers whose overuse (not mere presence) is the tell
FILLER_ADJECTIVES = ["ريادي", "رائد", "مبتكر", "استثنائي", "فريد من نوعه", "حيوي", "محوري"]

TATWEEL = "ـ"
DIACRITICS = "ًٌٍَُِّْٰ"
WESTERN_DIGITS = set("0123456789")
EASTERN_DIGITS = set("٠١٢٣٤٥٦٧٨٩")
AR_STOPWORDS = {
    "في", "من", "إلى", "الى", "على", "عن", "مع", "هذا", "هذه", "ذلك", "التي",
    "الذي", "أن", "ان", "إن", "و", "أو", "او", "ثم", "قد", "لا", "ما", "هو",
    "هي", "كان", "كانت", "بين", "كل", "بعض", "غير", "حتى", "لم", "لن", "قد",
    "له", "لها", "لهم", "بها", "به", "منه", "منها", "عليه", "عليها", "كما",
}


def strip_diacritics(text: str) -> str:
    return "".join(ch for ch in text if ch not in DIACRITICS)


def split_sentences(text: str) -> list[str]:
    text = re.sub(r"\s+", " ", text).strip()
    parts = re.split(r"(?<=[.!?؟؛])\s+", text)
    return [p for p in parts if p.strip()]


def tokenize_words(text: str) -> list[str]:
    text = strip_diacritics(text)
    text = text.replace(TATWEEL, "")
    return re.findall(r"[ء-ي]+", text)


def check_phrases(text: str) -> list[tuple[str, int]]:
    hits = []
    for phrase in BANNED_PHRASES:
        n = text.count(phrase)
        if n:
            hits.append((phrase, n))
    return hits


def check_filler_adjectives(text: str) -> list[tuple[str, int]]:
    hits = []
    for adj in FILLER_ADJECTIVES:
        n = len(re.findall(re.escape(adj), text))
        if n:
            hits.append((adj, n))
    return hits


def check_diacritics(text: str) -> dict[str, Any]:
    """Report diacritic density as an informational stat only.

    IMPORTANT: standard Arabic orthography legitimately carries diacritics in
    very common, non-AI-related cases: tanween-fatha on a final alef (e.g.
    تقريبا/technically spelled تقريبًا, شكرًا, فعلاً), an initial damma marking
    the passive voice on some imperfect verbs (تُستخدم vs تستخدم), and shadda
    used to disambiguate a geminated consonant. A first version of this check
    flagged any text with partial diacritic coverage as "inconsistent
    tashkeel" -- that fired on ~8-9% of words in BOTH a deliberately AI-cliche
    sample and a clean human sample during testing, because that 5-10% rate
    from tanween/passive-voice marking is exactly what normal human Arabic
    looks like. There is no reliable threshold in the literature for what
    diacritic density indicates machine generation, so this function no
    longer flags anything -- it only reports the number for a human reviewer
    to judge in context (e.g. near-total, unexplained vocalization of a
    non-poetic/non-Quranic passage would be worth a manual look).
    """
    words = re.findall(r"[ء-يً-ْ]+", text)
    words_with_diac = sum(1 for w in words if any(c in DIACRITICS for c in w))
    total_words = len(words)
    if total_words == 0:
        return {"pct_diacritized_words": 0.0, "flag": False}
    pct = words_with_diac / total_words * 100
    return {"pct_diacritized_words": round(pct, 2), "flag": False}


def check_tatweel(text: str) -> dict[str, Any]:
    """Count decorative/unjustified tatweel (kashida) elongation.

    Excludes ه + ـ (e.g. "1443هـ") -- the standard Hijri-calendar-year
    abbreviation, equivalent to "AD"/"BC" in English. This is completely
    standard Arabic orthography, not decorative stretching, and a naive
    tatweel count flagged it as suspicious on real, genuinely dated formal
    text during testing.
    """
    hijri_marker = len(re.findall(r"ه" + TATWEEL + r"(?=\s|$|[،.,؛؟!])", text))
    n = text.count(TATWEEL) - hijri_marker
    return {"count": n, "flag": n > 0}


def check_mixed_digits(text: str) -> dict[str, Any]:
    has_western = any(c in WESTERN_DIGITS for c in text)
    has_eastern = any(c in EASTERN_DIGITS for c in text)
    return {"has_western": has_western, "has_eastern": has_eastern, "flag": has_western and has_eastern}


def check_foreign_punctuation(text: str) -> dict[str, Any]:
    em_dash = text.count("—")
    curly_quotes = len(re.findall(r"[“”‘’]", text))
    return {"em_dash": em_dash, "curly_quotes": curly_quotes, "flag": (em_dash + curly_quotes) > 0}


def check_run_on_sentences(sentences: list[str], formal: bool = False) -> list[dict[str, Any]]:
    """Flag sentences that are long AND rely heavily on repeated و-conjunction
    instead of being split into separate sentences.

    CALIBRATION NOTE (found via testing against a long-form, formally
    structured Arabic writing sample): general/marketing/conversational
    Arabic prose treats a 35-word, 3-و-join sentence as unusually long.
    Formal, long-form Arabic writing does not -- in a formally structured
    sample used to test this script, the MEDIAN sentence length was 35 words,
    with a 90th percentile of 50 words and up to 9 و-joins in a single
    normal sentence. A 35-word threshold flagged roughly half of all
    sentences in that sample, which is useless as a signal. Pass
    formal=True (or --formal on the CLI) for formal, long-form register
    text, which uses a threshold set above what that formal sample exhibits
    at its 90th percentile, so only genuine outliers get flagged.
    """
    if formal:
        threshold_words, min_waw = 65, 8
    else:
        threshold_words, min_waw = 35, 3
    flagged = []
    for s in sentences:
        word_count = len(s.split())
        waw_joins = len(re.findall(r"\sو[ء-ي]", s))
        if word_count >= threshold_words and waw_joins >= min_waw:
            flagged.append({"sentence": s[:80] + ("..." if len(s) > 80 else ""), "words": word_count, "waw_joins": waw_joins})
    return flagged


def vocabulary_stats(words: list[str]) -> dict[str, Any]:
    content_words = [w for w in words if w not in AR_STOPWORDS and len(w) > 1]
    if not content_words:
        return {"ttr": 0.0, "top5_share": 0.0, "unique": 0, "total": 0}
    total = len(content_words)
    unique = len(set(content_words))
    ttr = round(unique / total, 3)
    freq = {}
    for w in content_words:
        freq[w] = freq.get(w, 0) + 1
    top5 = sum(sorted(freq.values(), reverse=True)[:5])
    top5_share = round(top5 / total * 100, 2)
    return {"ttr": ttr, "top5_share": top5_share, "unique": unique, "total": total}


def score(text: str, label: str, formal: bool = False) -> dict[str, Any]:
    print(f"\n{'='*66}\n{label}{' [formal mode]' if formal else ''}\n{'='*66}")
    sentences = split_sentences(text)
    words = tokenize_words(text)
    lengths = [len(s.split()) for s in sentences]
    variance = round(statistics.pstdev(lengths), 2) if len(lengths) > 1 else 0.0

    phrase_hits = check_phrases(text)
    filler_hits = check_filler_adjectives(text)
    diac = check_diacritics(text)
    tatweel = check_tatweel(text)
    digits = check_mixed_digits(text)
    punct = check_foreign_punctuation(text)
    run_ons = check_run_on_sentences(sentences, formal=formal)
    vocab = vocabulary_stats(words)

    violations = (
        sum(n for _, n in phrase_hits)
        + sum(n for _, n in filler_hits)
        + (1 if diac["flag"] else 0)
        + (1 if tatweel["flag"] else 0)
        + (1 if digits["flag"] else 0)
        + (punct["em_dash"] + punct["curly_quotes"])
        + len(run_ons)
    )

    print(f"  Word count: {len(words)}, sentence count: {len(sentences)}")
    print(f"  Sentence-length std deviation: {variance}")
    print(f"  Vocabulary: {vocab['unique']} unique / {vocab['total']} content words, "
          f"TTR={vocab['ttr']}, top-5-word share={vocab['top5_share']}% "
          f"(higher share = more AI-like concentration per Al-Shaibani & Ahmed 2025)")
    print(f"  Banned phrase hits: {phrase_hits if phrase_hits else 'none'}")
    print(f"  Filler-adjective hits: {filler_hits if filler_hits else 'none'}")
    print(f"  Diacritics: {diac['pct_diacritized_words']}% of words carry a diacritic "
          f"(informational only -- see docstring, no reliable AI threshold exists)")
    print(f"  Tatweel/kashida uses: {tatweel['count']} {'[FLAG]' if tatweel['flag'] else ''}")
    print(f"  Mixed digit systems: {'[FLAG]' if digits['flag'] else 'no'} "
          f"(western={digits['has_western']}, eastern={digits['has_eastern']})")
    print(f"  Foreign punctuation: em-dash={punct['em_dash']}, curly-quotes={punct['curly_quotes']} "
          f"{'[FLAG]' if punct['flag'] else ''}")
    print(f"  Run-on sentences (long + heavy و-joining): {len(run_ons)}")
    for r in run_ons[:3]:
        print(f"    -> ({r['words']} words, {r['waw_joins']} و-joins) {r['sentence']}")
    print(f"  TOTAL VIOLATIONS: {violations}")
    if len(words) > 0:
        print(f"  Violations per 100 words: {round(violations / len(words) * 100, 2)}")

    return {
        "violations": violations,
        "words": len(words),
        "vocab": vocab,
        "sentence_variance": variance,
    }


if __name__ == "__main__":
    args = sys.argv[1:]
    formal = "--formal" in args
    paths = [a for a in args if a != "--formal"]
    if not paths:
        print("Usage: score_arabic_text.py [--formal] <file1.txt> [file2.txt ...]")
        print("  --formal: use higher run-on-sentence thresholds calibrated for")
        print("            formal, long-form Arabic register (see check_run_on_sentences docstring)")
        sys.exit(1)
    results = {}
    for path in paths:
        with open(path, encoding="utf-8") as f:
            text = f.read()
        results[path] = score(text, path, formal=formal)

    if len(results) > 1:
        print(f"\n{'='*66}\nSUMMARY\n{'='*66}")
        for path, r in results.items():
            rate = round(r["violations"] / r["words"] * 100, 2) if r["words"] else 0
            print(f"  {path}: {rate} violations/100 words, TTR={r['vocab']['ttr']}, "
                  f"top5-share={r['vocab']['top5_share']}%, sentence-variance={r['sentence_variance']}")
