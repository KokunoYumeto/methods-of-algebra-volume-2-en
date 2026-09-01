# English mirror production log

## 2026-08-31 — authority and production start

- Full 146-unit English mirror plus two independent mastery bridges authorized and set as the active pursuit goal.
- Frozen Chinese authority: Wen-Wei Li, *Methods of Algebra, Volume 2: Linear Algebra*, official commit `9a5803ff77dd3257484cb177f851a73770a59dd3`, tree `23bd05c2fb8434278df4fdfb636559a6a2b0d2ff`, CC BY 4.0.
- Bounded official-source reuse check: the author’s Books page and pinned repository describe the Chinese book and expose no suitable complete English edition in the inspected official sources. This is not a universal nonexistence claim.
- `SOURCE_UNIT_MAP.json` freezes 146 exact source slices and two bridge stems. Initial cursor: sequence 1; admitted 0; build not yet started.
- Production provenance: OpenAI Codex gpt-5.6-sol, Ultra, acting on instructions of the user. Source authorship and human credits remain primary; this derivative is not endorsed by the author or publisher.
- Parallel production rule: workers receive disjoint contiguous unit ranges and may write only corresponding `source/en/*.tex` targets plus one range receipt in `controls/ranges/`. Shared controls, master document, backend, builds, admission, QA, and publication remain root-owned.
- Next executable action: translate all allocated ranges from Chinese primary text with the completed Indonesian edition as a structural/correction witness; then admit in exact sequence after deterministic source-structure checks.

## 2026-08-31 — parallel allocation and shared reader/build layer

- Allocated all 146 units into 15 disjoint contiguous ranges balanced by mapped source-line weight (1,497--1,759 source lines per range). A sixteenth disjoint worker owns only the two mastery bridges. Shared files remain root-owned.
- Frozen editable closure recorded in `controls/SOURCE_FREEZE.json`: 27 exact upstream files, 2,335,097 bytes, receipt SHA-256 `468b07a489f4bfef79a799b19fbe2b948f8fc3503e48aee16e7f669f8778974f`.
- Created the 148-input English XeLaTeX master plus English cover/font/title layers and translated the inactive historical draft-note source separately. The master preserves the 146-unit order and appends the two bridges with independent attribution.
- Reused the verified local MathJax/reflow implementation and assets. Created an initial 829-row English diagram ledger, 13 source-derived reader-only description overrides, English accessibility/license pages, and fixed-pass PDF/HTML/backend/admission tooling. No Indonesian public or canonical file was changed.
- Deterministic admission requires a PASS range receipt, exact frozen source/witness hashes, stable unit/segment IDs, labels, environment sequence, citation keys, math bodies apart from translated `\\text{...}`, nonidentity with Indonesian prose, substantive length, and bounded residue. QA runs after translation boundaries; translation remains dominant.

## 2026-08-31 — explicit storage-cleanup boundary

- Production workers were interrupted before cleanup; all live/provisional translations, source witnesses, controls, reader assets, build/publication tools, and receipts were retained because they remain necessary.
- Exact task-local disposable targets were only `tools/__pycache__` and `release/__pycache__`: 8 files, 88,494 loose bytes. No PDF build tree, reader build/dist tree, or release staging tree existed.
- Archived and fully byte/hash verified before deletion at `C:/Users/Floris/Documents/interlanguage/old stuff/o014-english-cache-cleanup-01a02164-3741-72b2-a48d-bab561ef5cd9-20260831-001.zip`: 49,895 bytes; SHA-256 `8301632d18ebc4e9a00ed448397a462de5b87c87f9ed24d02f5ed642374ad8ec`.
- Deleted only those two exact cache directories after verifying all 8 ZIP entries. No canonical, shared, evidentiary, credential-bearing, or potentially reusable file was deleted. The English lane is clean and production may resume from its preserved range files.

## 2026-08-31 — second bounded cache cleanup after resumed checks

- Rechecked only the exact known disposable/build paths owned by this English lane. `reader/build`, `reader/dist`, `output/pdf/build`, `release/staging`, `release/__pycache__`, and `reader/tools/__pycache__` were absent. One regenerated file existed: `tools/__pycache__/admit_translated_units.cpython-313.pyc` (11,646 bytes).
- Archived that exact file, without overwrite, to `C:/Users/Floris/Documents/interlanguage/old stuff/o014-english-cache-cleanup-01a02164-3741-72b2-a48d-bab561ef5cd9-20260831-002.zip`: 6,735 bytes; SHA-256 `f7b9086996c575d7414f92bd6bf83777810f46a2e272882a92d7612655506fb2`.
- The ZIP opens with exactly one entry, `admit_translated_units.cpython-313.pyc`, 11,646 bytes, entry SHA-256 `5d5fe4ec86e5d92ee85a3e43362714b5579347e40218ce361d2473b813db7bac`. The archive transaction verified the entry against the loose source before deleting it; an independent post-delete read verified the same entry inventory and hash.
- Deleted only that exact `.pyc` and its now-empty `tools/__pycache__` directory. All translations, source witnesses, controls, receipts, reader assets, tools, and publication material were retained. No cleanup file was uploaded to any cloud destination.

## 2026-08-31 — complete diagram-accessibility closure corrected

- A source-local validation found that the inherited provisional English ledger had 829 rows but the exact active source closure has 899 diagram environments across the 146 mapped units, plus 8 in the two mastery bridges: 907 total. The missing 78 are chiefly inline `tikzcd` diagrams without separate segment markers. Limiting the reader to 829 descriptions would leave raw placeholder tokens, so 829 is not accepted as complete English-reader closure.
- The same check found 118 malformed provisional descriptions with unbalanced TeX braces; two also retain Indonesian wording. No reader build was attempted. Evidence is persisted in `qa/DIAGRAM_LEDGER_VALIDATION.json`; the validator and backend gate now require 907 unique, source-aligned descriptions across all 148 source/bridge files.
- Resolution: rebuild the ledger against active diagram order, preserve and repair the 829 usable source-traced descriptions, add meaningful descriptions for the 70 missing source diagrams and 8 bridge diagrams, then require exact per-file counts and zero description defects before HTML generation. This accessibility repair is shared-layer work and does not pause unit translation.

## 2026-09-01 — first admitted English source boundary

- Five disjoint source ranges now carry verified PASS receipts: sequences 025–032, 033–040, 041–046, 047–055, and 056–064. This is 40 admitted units; 145/146 targets presently exist, with sequence 089 still absent. `qa/UNIT_ADMISSION.json` and `controls/CURRENT_STATE.json` record the exact boundary and cursor.
- Corrected the root admission aggregator after its first run exposed that it redundantly used a shallow regex comparison against the Indonesian witness. That check falsely rejected translated nested math text, source-primary forward cross-references, English index-entry splits, and English environment names. Admission now requires the range's PASS record, matching per-unit bytes/SHA-256, at least four recorded structural QA claims, frozen Chinese/Indonesian hashes, exact durable segment/label/target identities, exact citation keys, substantive nonidentical English, and bounded residue. Formula/environment/reference/index review remains required in—and evidenced by—the disjoint range receipt rather than being weakened or silently discarded.
- The complete source-order diagram inventory is frozen at `qa/DIAGRAM_SOURCE_INVENTORY.jsonl`: 907 active diagrams, all 829 inherited descriptions aligned without collision and 78 previously omitted inline/bridge diagrams identified. Inventory receipt result PASS; inventory SHA-256 `36f8d539bce4ce0a8990d5fe2e404195f963f8e2eae1afb82e9f7789677e6a03`. Description authoring/repair remains open and blocks HTML completion, but not source translation.

## 2026-09-01 — third bounded task-local cache cleanup

- A storage-safety override paused all production workers. The only disposable
  material in the exact known English-lane cache/build/staging paths was two
  regenerated Python bytecode files under `tools/__pycache__`; all reader,
  PDF, release-staging, temporary, and secondary cache paths checked were
  absent.
- Archived and byte/hash verified both files before deletion at
  `C:/Users/Floris/Documents/interlanguage/old stuff/o014-english-cache-cleanup-01a02164-3741-72b2-a48d-bab561ef5cd9-20260901-003.zip`:
  19,021 bytes; SHA-256
  `309192c18b44d0c8408241230653ff207516b8f0de0662c1ac0607962258d4cd`.
  The two verified entries total 34,915 loose bytes:
  `admit_translated_units.cpython-313.pyc` (17,931 bytes, SHA-256
  `aa11d1dccbbd93f8c3608ccfb819bb24bc3df9a5e02606ea221fe01ec8d23572`)
  and `audit_english_range.cpython-313.pyc` (16,984 bytes, SHA-256
  `31f51c0465604110b27928a090c30f31ae9c79d282845674e2c325c22756f1bc`).
- Deleted only those exact loose files and their now-empty cache directory.
  Canonical English translations, frozen witnesses, controls, receipts,
  source assets, build tools, QA evidence, credentials, and release material
  were retained. No cleanup artifact was uploaded to a cloud destination.

## 2026-09-01 — 123-unit English admission boundary

- All 146 mapped English unit targets now exist. Deterministic admission has
  accepted 123/146 units: sequences 001–109 and 133–146. The two independent
  mastery bridges retain their separate PASS receipt.
- The only 23 units not yet admitted are sequences 110–132, whose two range
  reviews remain in progress. Their files are preserved as translated working
  targets; this boundary does not classify them as missing or failed.
- Exact receipt: `qa/UNIT_ADMISSION.json`, 167,214 bytes, SHA-256
  `45cb83ac69cac334a60451074b46c5d604940e8dd9bd5e438bef9dbbb89c094c`.
  `controls/CURRENT_STATE.json` records translated 146, admitted 123, next
  sequence 110, and build not yet started.
- Next executable action: finish and admit ranges 110–121 and 122–132, then
  run one full 146-unit admission replay before starting the PDF/backend/HTML
  builds. Shared paratext, diagram-description, terminology/backend, reader,
  and release-tool preflights continue independently without changing units.

## 2026-09-01 — complete 146-unit English source admission

- Range reviews for sequences 110–121 and 122–132 closed with PASS receipts,
  completing all fifteen contiguous ranges. The final admission replay accepts
  146/146 units with no failed existing target; both mastery bridges remain
  separately admitted.
- Final unit admission receipt: `qa/UNIT_ADMISSION.json`, 184,802 bytes,
  SHA-256 `86026f52a35b0293dc55ad108cf879ed9f08ba185b1669771e4c3a65413cb552`.
  `controls/CURRENT_STATE.json` now records 146 translated, 146 admitted, no
  next sequence, and `unit_translation_complete`.
- The master/shared-source validator independently confirms exactly 148 inputs
  (146 units plus two bridges), zero missing inputs, and zero active shared
  language residue. Receipt: `qa/SHARED_SOURCE_VALIDATION.json`, 2,032 bytes,
  SHA-256 `c104e6205d1b4c6d51a6e88a6c3f4f0e536faf656e078c627045b046bc23372d`.
- Shared paratext preflight also passed attribution, source identity,
  CC BY 4.0, non-endorsement, bridge status, model provenance, dependency
  closure, and static TeX balance. Receipt:
  `qa/SHARED_PARATEXT_PREFLIGHT.json`, 4,202 bytes, SHA-256
  `358714a94de2f8335309cfd9cac819b4a0d95913ecc9aa27898b7ca9a1d3d536`.
- Next executable action: close the 907-description and 511-term backend
  layers, then run the mutex-serialized PDF build and accessible HTML build.

## 2026-09-01 — PDF attempt 1 failed closed at the TeX mutex

- The first PDF command waited the full bounded 600,000 ms for
  `Global\\InterlanguageTeXSlotV1` while an already-running foreign
  point-set-topology PDF build held the machine slot. It timed out exactly as
  designed: no TeX child was launched, no PDF was created, and the local build
  directory remained empty.
- Failure receipt: `qa/PDF_BUILD_ATTEMPT_001.json`. The foreign process ended
  immediately after this timeout, so the next action is one bounded retry of
  the same admitted source—not a rebuild loop or a competing worker.

## 2026-09-01 — complete offline HTML reader and browser closure

- The reader now builds 149 logical sections from all 146 units, both mastery
  bridges, and the bibliography. Its 31 local files total 6,199,898 bytes;
  `reader/dist/index.html` is 4,498,445 bytes with SHA-256
  `a1b432e4036a92d3264581e68ee6a14d00fafcc170c97967115d96258a92ac9c`.
- Deterministic validation passes 3,609 local references, 907/907 accessible
  source-traced diagram fallbacks, 28,445 math source elements, fully local
  MathJax assets, zero unsupported TeX/PGF/TikZ residue, and zero errors.
- Browser QA at 1440x900 and 390x844 rendered 28,454 MathJax containers with
  zero `mjx-merror`, zero visible `\\ensuremath`, zero page-level horizontal
  overflow, and zero wide equations/tables outside a local scroller. The reader
  column is centered on desktop and reflows to a 359 px content column on the
  mobile viewport.
- Browser inspection exposed and then closed three conversion defects that the
  static gate alone could not see: Pandoc dropping diagrams inside description
  lists, an active-character print shim that Pandoc could not parse, and
  unresolved `\\ensuremath` rendered as red literal text. Diagram captions are
  now visible/assistive plain mathematical text with no raw TeX commands and no
  known Indonesian caption residue.
- Exact runtime receipt: `qa/HTML_BROWSER_QA.json`. Next action remains the
  mutex-safe PDF build, followed by packaging and public publication/readback.

## 2026-09-01 — refreshed reader closure and first executable PDF correction

- After the accessible-diagram ledger was corrected and made deterministically
  replayable, the backend replay again passed all 146 units, 6,347 segments,
  511 explicit English terms, 907 figures, and both mastery bridges. The ledger
  is 337,312 bytes with SHA-256
  `aa15c68e8e0f19ee58dc9329199c4ff84db1deb1df9bf58dd5a11105ff293937`.
- The refreshed 31-file offline reader totals 6,200,748 bytes;
  `reader/dist/index.html` is 4,499,295 bytes with SHA-256
  `894749f6fc9e19d37ff981a0e5a2681539d2dc04b33952967ac989b3d70abff3`.
  Fresh desktop/mobile runtime inspection again passes 149 sections, 907
  diagram captions, 28,454 rendered MathJax containers, zero `mjx-merror`,
  zero unsupported/raw residue, zero page overflow, and zero uncontained wide
  equations. Exact receipt: `qa/HTML_BROWSER_QA.json`.
- The first XeLaTeX pass after the global mutex became available stopped at
  Chapter 1 because `xstring` could not safely parse titlesec's protected
  expansion of `\thechapter` inside `\AJchapterttl`. The edition-local title
  helper in `source/en/titles-setup-en.tex` now uses an expandable appendix
  marker test for A/B instead of `\IfSubStr`; the mathematical/source unit
  text is unchanged. The exact mutex-safe PDF command is being replayed once
  from this corrected source.

## 2026-09-01 — complete HTML reader published and anonymously read back

- The complete 149-section English HTML reader, editable English source,
  backend, controls, and QA evidence were published as an explicitly labelled
  HTML-first checkpoint in the permanent public repository. PDF and Zenodo
  remain truthfully marked pending while the machine-wide TeX slot is occupied.
- Repository: `https://github.com/KokunoYumeto/methods-of-algebra-volume-2-en`.
  Content commit: `5e76c3454625afd6227e1762d9d65ba2c6c4b906`.
  Pages commit: `ffe5fd72a87a4de894a7fa09861d415406544278`.
  Reader: `https://kokunoyumeto.github.io/methods-of-algebra-volume-2-en/`.
- The first anonymous byte comparison detected Git EOL normalization in five
  text artifacts. `.gitattributes` now marks `reader/dist/** -text`; a narrow
  `git add --renormalize -- reader/dist` republished their exact verified bytes.
  Final anonymous readback passes all 31 files and 6,200,748 bytes with exact
  SHA-256 identity. Receipt: `release/GITHUB_PUBLIC_READBACK.json`, SHA-256
  `e7658a6e688cda2d1cd0e10ef3c4d20845c54fd05b0ff0acfa9df301b8d1e618`.
- Next executable action: when `Global\\InterlanguageTeXSlotV1` is observed
  free, run the corrected PDF build once, inspect representative pages, package
  the nine-file Zenodo release, publish/read it back, then update the same
  GitHub lineage from checkpoint to the complete PDF+HTML release.

## 2026-09-01 — refreshed reader runtime QA after deterministic ledger replay

- Fresh localhost browser QA closed against `reader/dist/index.html`, 4,499,295
  bytes, SHA-256
  `894749f6fc9e19d37ff981a0e5a2681539d2dc04b33952967ac989b3d70abff3`.
  Both 1440x900 and 390x844 rendered all 149 logical sections, 907 diagram
  fallbacks/captions, and 28,454 MathJax containers with zero `mjx-merror`,
  visible `\\ensuremath`, unsupported TeX/PGF/TikZ/print residue, raw-TeX
  captions, known Indonesian caption residue, or page-level overflow.
- Desktop/mobile respectively had 49/1,368 wide mathematical containers and
  zero without a local scroller. The desktop main column was centered to
  0.111 px; mobile reflow produced a 359.111 px main column. All 3,636
  same-origin links had valid same-document targets, and all 31 packaged files
  (6,200,748 bytes) were HTTP-read back with exact byte and SHA-256 identity;
  the browser console had zero warnings or errors.
- Receipt: `qa/HTML_BROWSER_QA.json`, 3,306 bytes, SHA-256
  `e4baa7d5d0a1d92c0749790160f50618df59929bf74aff1b34c02f87ca9283f9`.
