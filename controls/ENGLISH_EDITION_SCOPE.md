# Methods of Algebra, Volume 2: Linear Algebra - English edition

## Authorized additive scope

Produce an independent English-access edition of the complete Wen-Wei Li
Chinese corpus selected for O014/D80, plus English versions of the two
Indonesian-original mastery bridges and their answers. The completed Indonesian
edition stays complete, public, and read-only. This is not a replacement task,
donor substitution, retranslation of an English donor, or a claim of an
official English edition.

English write root:
`C:/Users/Floris/Documents/interlanguage/04_mirrors/en/methods-of-algebra-volume-2-en`.
Read-only Indonesian source/ID reference:
`C:/Users/Floris/Documents/interlanguage/04_mirrors/id/methods-of-algebra-volume-2-id`.
Frozen official Chinese tree:
`C:/Users/Floris/Documents/interlanguage/04_mirrors/id/methods-of-algebra-volume-2-id/authority/upstream/AlJabr-2-9a5803ff77dd3257484cb177f851a73770a59dd3`.

## Authority and reuse decision

Author: Wen-Wei Li. Original title: 代数学方法, 卷二, 线性代数.
2024 Higher Education Press edition; ISBN 978-7-04-062754-1.
Official repository: https://github.com/wenweili/AlJabr-2
Commit: `9a5803ff77dd3257484cb177f851a73770a59dd3`.
Tree: `23bd05c2fb8434278df4fdfb636559a6a2b0d2ff`.
License: CC BY 4.0, including the editable codebase. Preserve exact component
licenses and author/source attribution; this independent derivative is not
endorsed by Wen-Wei Li or Higher Education Press.

A bounded official-source check on 2026-08-31 inspected the author's Books page
(https://wwli.asia/docs/books/) and the pinned repository README/inventory.
Both identify the work as Chinese; no suitable complete English edition was
found in those inspected sources. This does not assert that none exists
anywhere. Existing English mathematical terminology in the bilingual glossary
is reusable, but is not an existing English book.

## Complete finite workflow

1. Freeze the 146 source-unit records, source slices, macro/assets closure,
   existing Indonesian corrections, and two independent mastery bridges.
   `controls/SOURCE_UNIT_MAP.json` is the unit allocation and source map.
2. Produce natural English in exact source order. Preserve unit/segment IDs,
   labels, formulas, hypotheses, proofs, exercises, hints, figures, and code.
   Use Chinese as primary textual authority and Indonesian as a structure/
   correction witness. Mark every carried editorial correction as such.
   Preserve existing English donor material, if any, instead of translating it.
3. Translators write disjoint `source/en/*-unit-*.tex` ranges only. No file is
   admitted as English merely by copying Indonesian. Production state is
   recorded in per-range receipts and `controls/CURRENT_STATE.json`.
4. Translate English paratext, glossary and diagram alternatives; carry the
   two original mastery bridges with independent attribution. Reuse mathematical
   macros/assets, never Indonesian labels as English output. Keep bibliography
   source titles/authors intact.
5. Build a reproducible XeLaTeX/Biber/index PDF and accessible offline HTML
   with the repaired MathJax approach. Preserve original TikZ visuals in PDF,
   semantic math and source-traced diagram fallbacks in HTML. Validate source
   closure, stable IDs, formulas, local links, assets, and 149 logical sections
   when the full course is present. Require zero rendered MathJax errors and
   responsive desktop/mobile reflow. Partial builds must advertise exact scope.
6. Populate the English backend using the same locale-neutral unit IDs with
   explicit English locale and source/reader paths. Never overwrite the
   Indonesian backend or inherit its completion flags into untranslated units.
7. Publish completed verified English boundaries through appropriate English
   repository/archive lineage, clearly distinguish English links for central
   integration, preserve all Indonesian public access, and anonymously verify
   released inventory/bytes/SHA-256. Never create duplicate versions merely for
   retrying an observation. No upstream contact.
8. Record exact build, visual QA, artifacts, hashes, public links, coverage,
   and next source cursor at every substantial checkpoint. Completion means
   all 146 units plus equivalent-course bridges and public reader/source/
   backend closure, not a plan, audit, or first unit.

## Durable state

- `controls/SOURCE_UNIT_MAP.json`: all source ranges and target filenames.
- `controls/CURRENT_STATE.json`: actual admitted coverage and next source cursor.
- `controls/PRODUCTION_LOG.md`: decisions, build and publication history.
- `controls/ranges/`: translator receipts for disjoint source ranges.
- `qa/`: deterministic checks and visual evidence.
- `release/`: manifests, public-byte receipts and language-labelled links.

Production provenance: OpenAI Codex gpt-5.6-sol, Ultra, on instructions of the
user. Source author and other human credits are retained; the mastery bridges
are independent additions, not attributed to the source author.
