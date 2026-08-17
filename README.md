# humanizer-ar

A Claude Code skill that removes signs of AI-generated writing from **Arabic** text. Built from scratch for Arabic, not a translation of an English pattern list run through Google Translate. Pattern catalog and mechanical checks are MSA-focused, with a register-consistency check for dialect drift — see "Known limitations" below for what's not covered yet.

## Why this exists

The well-known `humanizer` skills for Claude Code ([blader/humanizer](https://github.com/blader/humanizer), [Aboudjem/humanizer-skill](https://github.com/Aboudjem/humanizer-skill)) are built on Wikipedia's "Signs of AI writing" guide, which documents *English* tells: em dash overuse, "stands as a testament," negative parallelism. None of that transfers cleanly to Arabic. Arabic AI-generated text has its own separate set of giveaways — different inflation phrases (يُعد بمثابة شاهد, نقلة نوعية), different connector cliches (تجدر الإشارة إلى, علاوة على ذلك), no em dash convention in the script at all, and orthographic-level tells (inconsistent diacritics, kashida, mixed digit systems) that have no English equivalent whatsoever.

This skill is grounded in four things instead of guesswork:

1. **Real stylometric research on Arabic LLM output**: [Al-Shaibani & Ahmed, "The Arabic AI Fingerprint" (2025)](https://arxiv.org/abs/2505.23276), which found that machine-generated Arabic concentrates disproportionately on its top-frequency words, has a much narrower long-tail vocabulary than human writing, and underuses domain-specific/technical terminology compared to human writers — plus [Khairallah & Zubiaga, "ALHD" (2025)](https://arxiv.org/abs/2510.03502), a 400K-sample benchmark dataset for Arabic human-vs-LLM text.
2. **Classical Arabic rhetoric (بلاغة/فصاحة)**, not just modern NLP. Patterns 21-25 are built on [Marathe (2022), *Creation of a Numerical Scoring System to Objectively Measure and Compare the Level of Rhetoric in Arabic Texts*](https://doi.org/10.5281/zenodo.15765533) — an MA dissertation (University of Exeter) that formalized 84 classical rhetorical devices across three domains, plus a documented negative-scoring "eloquence defects" category. The theoretical backbone for weighting sentence-structure over surface figures of speech is older and more foundational than that dissertation: al-Jurjani's (4th century AH) *نظرية النظم* (theory of composition), which argues eloquence lives in how words are structurally arranged relative to each other, not in isolated metaphors or embellishments.
3. **Arabic collocation research**: patterns 26-27 are grounded in Arabic collocation-extraction literature (Brashi's *Arabic Collocations: Implications for Translation*, tools like Musaheb) documenting that English-influenced Arabic substitutes light-verb calques (قام بإجراء) for the direct verb (أجرى), and literal collocation calques (أخذ قرارًا) for the real Arabic idiom (اتخذ قرارًا) — grammatically correct Arabic that simply isn't how the pairing actually forms natively.
4. **Direct observation** of actual output from GPT-4, Jais, ALLaM, Llama, and Claude on Arabic prompts, compared against natural Arabic writing across formal and informal registers.

## What's in the box

- `skills/humanizer-ar/SKILL.md` — the skill definition Claude Code loads
- `skills/humanizer-ar/references/patterns.md` — the full pattern catalog (27 patterns across content, linguistic, orthographic, statistical, classical-rhetoric, and collocation categories), each with real before/after examples
- `scripts/score_arabic_text.py` — a zero-*required*-dependency mechanical scanner that measures a text against the pattern catalog, plus real quantitative signals (vocabulary concentration, type-token ratio, sentence-length variance), and optional OSMAN/LIX readability scores (`pip install textstat`) using [El-Haj & Rayson's original implementation](https://github.com/drelhaj/OsmanReadability), not a reimplementation
- `tests/test_scanner.py` — a regression suite that encodes what testing this against real text actually found (see below)

## Install

Clone this repo, then symlink or copy the skill folder into your Claude Code skills directory:

```bash
git clone https://github.com/<your-username>/humanizer-ar.git
ln -s "$(pwd)/humanizer-ar/skills/humanizer-ar" ~/.claude/skills/humanizer-ar
```

Or copy `skills/humanizer-ar/` into any project-local `.claude/skills/` directory.

## Usage

Inside Claude Code:

```
/humanizer-ar
```

Or just ask Claude to humanize/review an Arabic draft — the skill's description makes it discoverable automatically.

The mechanical scanner also runs standalone, no Claude required:

```bash
python3 scripts/score_arabic_text.py path/to/text.txt
python3 scripts/score_arabic_text.py --formal path/to/document.txt
```

Use `--formal` for long-form, formally structured Arabic (reports, official correspondence, regulations) — see "What testing actually found" below for why this flag exists.

## What testing actually found

This wasn't shipped on the first pass. Before publishing, the scanner was stress-tested against a deliberately AI-cliche-dense synthetic sample, a clean human-written sample, and a long-form, formally structured Arabic sample. That testing caught two real design bugs that would otherwise have shipped:

1. **A diacritics check that flagged normal Arabic as suspicious.** The first version flagged any text with "inconsistent" partial diacritic coverage as an AI tell. Testing showed it fired at nearly the same rate (~8-9% of words) on *both* the AI-cliche sample and the clean human sample, because that rate is just... how Arabic works: tanween-fatha on a final alef (تقريبًا, شكرًا), the initial damma marking passive voice (تُستخدم vs تستخدم), and disambiguating shadda are all standard orthography, not AI artifacts. Fixed by making this check informational-only — it reports the number, it doesn't flag it.

2. **A run-on-sentence check that flagged half of all sentences in a formally structured Arabic sample.** The check for "long sentences joined by repeated و instead of periods" used a 35-word threshold, borrowed from the intuition that long compound sentences read as generated/unnatural. Testing against long-form, formally structured Arabic writing showed a **median sentence length of 35 words**, a 90th percentile of 50 words, and legitimate sentences with up to 9 و-joins. Long, heavily-conjoined sentences are the *norm* in formal, long-form Arabic register (reports, regulations, official correspondence), not an AI tell there. Fixed by adding a `--formal` mode with thresholds calibrated above what real formally structured prose exhibits at its 90th percentile.

3. **A tatweel/kashida check that flagged the standard Hijri-year abbreviation.** A real dated document ("...عام 1443هـ...") triggered 4 false "decorative elongation" flags, because the tatweel character is also the second half of the standard هـ ("AH", i.e. Hijri-calendar) abbreviation glyph — completely normal orthography, equivalent to writing "AD" after a year in English, not stretching for emphasis. Fixed by excluding the ه+tatweel-at-word-boundary pattern before counting.

The regression suite in `tests/test_scanner.py` encodes all three findings as permanent tests, so none regress silently. Run it with:

```bash
python3 tests/test_scanner.py
```

`tests/fixtures/synthetic_formal_sample.txt` is a synthetic, purpose-written sample with the same long-sentence profile used for that calibration test — no real third-party document is included in this repo.

## A note on limits

This is a diagnostic aid, not a verdict. [Almohaimeed et al. (2025)](https://arxiv.org/abs/2511.16690) document real false-positive problems with automated Arabic AI-text detectors on lightly-edited human writing. More strikingly: [Labib et al.'s 2026 AbjadGenEval ensemble system](https://aclanthology.org/2026.abjadnlp-1.62.pdf) — a fine-tuned AraBERT/BERT-arabic ensemble, not a simple heuristic scanner like this one — still misclassified **~38% of genuinely human-written Arabic as machine-generated** on the official shared-task test set (0.62 precision at 0.98 recall). If a purpose-trained transformer ensemble gets human Arabic wrong more than a third of the time, a phrase-matching heuristic scanner certainly can too. Treat every flag from this skill or its scanner as "worth a second look," never as proof.

## Known limitations

- **The run-on-sentence check (pattern #18) is the weakest signal in the catalog, and might point the wrong way.** It was built on the English-derived intuition that heavy و-conjunction chaining reads as AI-generated "narrative flow." Deeper research (August 2026) found a peer-reviewed linguistics paper — [Dickins (2017), *Languages in Contrast*](https://eprints.whiterose.ac.uk/id/eprint/110940/) — showing that dense interclausal coordination is a general feature of Arabic across nearly all registers, not a marker of anything in particular, AND documenting a *documented counter-phenomenon*: some English-influenced Arabic writers actually use noticeably *fewer* connectors, not more (citing Ahmad Murad's 2012 novel *الفيل الأزرق* as an example). No research establishes which direction, if any, real LLM-generated Arabic actually leans. This pattern stays in the catalog because removing it outright would be an overcorrection with equally little evidence behind it, but treat any flag from it as the lowest-confidence signal this tool produces — even outside `--formal` mode.
- **No dedicated research exists yet on Arabic AI-cliche phrases or punctuation habits (patterns #7, #12, #17).** Unlike the vocabulary-concentration findings (patterns #19-20), which are grounded in real published numbers, the banned-phrase list and the foreign-punctuation check remain built from direct observation, same as the original English Wikipedia "Signs of AI writing" list this whole approach is modeled on. Not a flaw unique to this skill — it reflects a genuine, current gap in the literature — but worth knowing which parts of the catalog rest on published data versus judgment calls.
- **Dialectal Arabic is not covered.** The pattern catalog, banned-phrase list, and every mechanical check are tuned for Modern Standard Arabic. [Alharthi (2025)](https://www.researchgate.net/publication/391615130) found that dedicated fine-tuned models (AraBERT, AraELECTRA) clearly outperform feature-based/pattern approaches specifically for detecting AI-generated *dialectal* Arabic — the linguistic ground truth for what's "natural" varies too much across Gulf, Levantine, Egyptian, and Maghrebi Arabic to encode reliably as a hand-built pattern list without native-speaker validation per dialect. Rather than ship a shallow, likely-wrong dialect catalog, this skill limits itself to a lighter, honest signal: flagging when text that was supposed to be dialectal keeps drifting back into standard MSA phrasing mid-passage (a real, documented AI tell — see SKILL.md step 4), without claiming to catch dialect-specific AI patterns within a given dialect itself.
- **OSMAN/LIX readability scores are a register signal, not an AI-detection signal.** See the `readability_stats()` docstring in `scripts/score_arabic_text.py` — a low score means "formal/complex," not "machine-generated."
- **The scanner is heuristic, not a classifier.** It has no false-positive/recall numbers of its own the way a trained model would, because it isn't one — it's a documented, testable, but fundamentally rule-based aid. See "A note on limits" above.

## Credits

Repo structure inspired by [`blader/humanizer`](https://github.com/blader/humanizer) and its Chinese variant `humanizer-zh`. The Arabic pattern catalog itself is original, not translated.

## License

MIT
