# CONTEXT.md — news-image-20261125: "Front page of 25 November 2026"

## Task
main.py (Python 3.13 STDLIB ONLY) renders ONE PNG image (<=1024x1024, <=1 MiB) that reads as the FRONT PAGE of a world newspaper dated **25 November 2026**. It must name the day: render "25 NOVEMBER 2026" prominently in the masthead. NO other date anywhere in the image.

Honor OUT_DIR env (default /output); write the PNG to $OUT_DIR/entry.png (exact filename `entry.png`). Deterministic: two runs byte-identical (no randomness, no timestamps, no network at render time).

## Stories
The day's verified stories are in NEWS.md (gathered by a previous session from mainstream news RSS feeds, each with source). Choose the 8 strongest/most consequential for the 2x4 card grid (spread across regions and fields: war/diplomacy, courts, disasters, economy, science, sports); remaining notable headlines go in the bottom ticker. Use only facts reported in NEWS.md; no hype or speculation as fact.

## Design criteria (judge is a vision model, in priority order)
1. Names the day: contest date 25 NOVEMBER 2026 prominent; ZERO other dates in the image (no tickers/footnotes/masthead labels with other dates).
2. ~8 consequential stories across regions and fields, not one country/beat.
3. A viewer who missed the day can tell what happened from the image alone: short uppercase labels, nothing false or self-contradictory.
4. Faithful to the reported facts in NEWS.md; no speculation presented as fact.
5. Craft: one clear composition, legible at ~300 px across, no garbled text, no clipped lines, dense balanced layout with no large empty whitespace.

## Verified defect checklist (EVERY line must be swept before finishing)
- No date text other than 25 NOVEMBER 2026, anywhere.
- No text clipped at card/edge boundaries: measure each line's pixel width against its container; wrap or shorten labels.
- Digits must come from digit glyphs — 0 and O must look distinct (use a slashed zero); verify numbers like "3-2", "31", "129" render as digits.
- No stray tiny artifacts (counts, legend labels) floating near icons.
- No large empty whitespace in cards: enlarge pictograms/text so content fills each card.
- Every headline/status word fully rendered (not clipped to a prefix).

## Build recipe (verified, stdlib-only)
- Hand-rolled PNG writer (zlib + struct scanlines) + embedded 5x7 bitmap font dict + text drawing helper with scale factors 2x/3x/4x.
- Layout: masthead band ("WORLD NEWS" + "25 NOVEMBER 2026" on a highlight band), 2x4 grid of story cards (region/color header bar, flat pictogram from rectangles/polygons, 1-2 line label, small sub-line), bottom ticker strip of extra headlines (ticker may carry scores/keywords but NO dates).
- Constraints: <=1 MiB, <=1024x1024, valid whole PNG, byte-identical across two runs (compute sha256 twice), no network, no randomness/timestamps.
- Verify locally with `OUT_DIR=out python3 main.py`, then inspect the render at full size; fix defects via FIXES.md (one defect per line) and iterate until the sweep is clean.
- README.md must carry the competition's three live make.fun badge links for slug news-image-20261125 with owner/repo alexbot233/news-image-20261125 (already present — do not change README.md).

## Process rules
- Create and modify files ONLY with your write/edit tools — never shell heredocs or `cat >`.
- Do not read git history. Do not commit.
