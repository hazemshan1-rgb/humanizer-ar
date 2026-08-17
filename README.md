# humanizer-ar

A Claude Code skill that removes signs of AI-generated writing from **Arabic** text (MSA and dialectal). Built from scratch for Arabic, not a translation of an English pattern list run through Google Translate.

## Why this exists

The well-known `humanizer` skills for Claude Code ([blader/humanizer](https://github.com/blader/humanizer), [Aboudjem/humanizer-skill](https://github.com/Aboudjem/humanizer-skill)) are built on Wikipedia's "Signs of AI writing" guide, which documents *English* tells: em dash overuse, "stands as a testament," negative parallelism. None of that transfers cleanly to Arabic. Arabic AI-generated text has its own separate set of giveaways — different inflation phrases (يُعد بمثابة شاهد, نقلة نوعية), different connector cliches (تجدر الإشارة إلى, علاوة على ذلك), no em dash convention in the script at all, and orthographic-level tells (inconsistent diacritics, kashida, mixed digit systems) that have no English equivalent whatsoever.

This skill is grounded in two things instead of guesswork:

1. **Real stylometric research on Arabic LLM output**: [Al-Shaibani & Ahmed, "The Arabic AI Fingerprint" (2025)](https://arxiv.org/abs/2505.23276), which found that machine-generated Arabic concentrates disproportionately on its top-frequency words, has a much narrower long-tail vocabulary than human writing, and underuses domain-specific/technical terminology compared to human writers — plus [Khairallah & Zubiaga, "ALHD" (2025)](https://arxiv.org/abs/2510.03502), a 400K-sample benchmark dataset for Arabic human-vs-LLM text.
2. **Direct observation** of actual output from GPT-4, Jais, ALLaM, Llama, and Claude on Arabic prompts, compared against natural Arabic writing across formal and informal registers.

## What's in the box

- `skills/humanizer-ar/SKILL.md` — the skill definition Claude Code loads
- `skills/humanizer-ar/references/patterns.md` — the full pattern catalog (20 patterns across content, linguistic, orthographic, and statistical categories), each with real before/after examples
- `scripts/score_arabic_text.py` — a zero-dependency mechanical scanner that measures a text against the pattern catalog, plus real quantitative signals (vocabulary concentration, type-token ratio, sentence-length variance)
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

The regression suite in `tests/test_scanner.py` encodes both findings as permanent tests, so neither regresses silently. Run it with:

```bash
python3 tests/test_scanner.py
```

`tests/fixtures/synthetic_formal_sample.txt` is a synthetic, purpose-written sample with the same long-sentence profile used for that calibration test — no real third-party document is included in this repo.

## A note on limits

This is a diagnostic aid, not a verdict. [Almohaimeed et al. (2025)](https://arxiv.org/abs/2511.16690) document real false-positive problems with automated Arabic AI-text detectors on lightly-edited human writing. Treat every flag from this skill or its scanner as "worth a second look," never as proof.

## Credits

Repo structure inspired by [`blader/humanizer`](https://github.com/blader/humanizer) and its Chinese variant `humanizer-zh`. The Arabic pattern catalog itself is original, not translated.

## License

MIT
