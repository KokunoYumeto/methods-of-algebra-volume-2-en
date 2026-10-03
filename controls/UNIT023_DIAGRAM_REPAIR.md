# Unit 023 diagram correspondence and accessibility repair

## Scope and authority

This bounded repair covers all 23 diagrams in `source/en/chapter2-unit-023.tex`, “Some Diagram Lemmas.” The mathematical authority remains Wen-Wei Li’s frozen *Methods of Algebra, Volume 2* source at commit `9a5803ff77dd3257484cb177f851a73770a59dd3`, tree `23bd05c2fb8434278df4fdfb636559a6a2b0d2ff`, `chapter2.tex` lines 293–518. The English unit is unchanged; this repair corrects only the diagram-to-description correspondence used by the reflowable reader.

The initiating report is `SHDC-CPLX-F03-20261003.json`, SHA-256 `783700cb6803a6f651a09f08fe2d9dce3f32ec8dcccead5a9f0a57dba47e7bf5`. It correctly identified a one-position caption shift at the Five Lemma: `chapter2-unit-023-d015` was given the preceding Snake Lemma caption, and `chapter2-unit-023-d016` was given the five-column caption. Earlier shifted descriptions and later generic path captions showed that the complete 23-diagram unit, rather than only those two rows, needed one bounded source comparison.

## Decision

Every figure remains at its original source location and keeps its stable ID. Each figure now receives a complete equivalent English description checked against its exact TikZ or tikzcd body and nearby prose. The descriptions name every object and arrow, distinguish epimorphisms, monomorphisms, dashed or zero maps, state commutativity and exactness where asserted, and explain the diagram’s local proof role. This semantic-text approach is reflowable and screen-reader accessible. Deterministic SVG would be a compatible later enhancement, but it is not required for semantic completeness and would add a larger independent rendering surface.

The machine-readable choice ledger is `controls/UNIT023_DIAGRAM_DESCRIPTIONS.json`. Its evidence is retrospective: it records the source comparison actually performed for this correction and does not claim that these descriptions were consulted during the original English production.

## Per-diagram closure

| Order | Stable ID | Source segment | Actual use |
|---:|---|---|---|
| 1 | `chapter2-unit-023-d001` | `g001` | Exactness-criterion square |
| 2 | `chapter2-unit-023-d002` | `g002` | Dashed alpha factorization |
| 3 | `chapter2-unit-023-d003` | `g003` | Main Snake Lemma diagram |
| 4 | `chapter2-unit-023-d004` | `g004` | Pullback-pushout construction of delta |
| 5 | `chapter2-unit-023-d005` | `g005` | Naturality comparison of Snake data |
| 6 | `chapter2-unit-023-d006` | `g006` | Naturality square for delta |
| 7 | `chapter2-unit-023-diagram-007` | `g007` | Target lift for exactness at Ker |
| 8 | `chapter2-unit-023-d007` | `g008` | Auxiliary lift through X' to X to X'' |
| 9 | `chapter2-unit-023-d008` | `g009` | Desired S_0-to-Ker lift |
| 10 | `chapter2-unit-023-d009` | `g010` | Lift through the fiber product |
| 11 | `chapter2-unit-023-d010` | `g011` | Comparison of delta psi and delta_0 |
| 12 | `chapter2-unit-023-d011` | `g012` | Lift through X' to Y' to Coker' |
| 13 | `chapter2-unit-023-d012` | `g013` | Compatibility defining lambda |
| 14 | `chapter2-unit-023-d013` | `g014` | Factorization of lambda minus f k |
| 15 | `chapter2-unit-023-d014` | `g015` | Known outer-frame comparison |
| 16 | `chapter2-unit-023-d015` | `g016` | Five Lemma statement: five columns, two exact rows |
| 17 | `chapter2-unit-023-d016` | `g017` | First lifting square in the Five Lemma proof |
| 18 | `chapter2-unit-023-diagram-018` | `g018` | Two-stage epimorphic construction |
| 19 | `chapter2-unit-023-d017` | `g019` | Composite diagram with one square to prove |
| 20 | `chapter2-unit-023-d018` | `g020` | Right-then-down route in that square |
| 21 | `chapter2-unit-023-d019` | `g021` | Down-then-right route in that square |
| 22 | `chapter2-unit-023-d020` | `g022` | Known X_1-X_2-Y_1-Y_2 square |
| 23 | `chapter2-unit-023-d021` | `g023` | Known S'''-S'-Y_1-Y_2 square |

## Acceptance rule

The repair passes only if a deterministic replay preserves all 23 IDs and source ordinals, uses all 23 audited descriptions at their exact locations, contains no truncated-arrow phrases, assigns the complete Five Lemma diagram to `d015` and the four-object lifting square to `d016`, preserves all 149 reader sections and 907 figures, introduces no broken links or unsupported mathematics, and passes focused desktop and mobile inspection. Human review remains welcome but is not a gate.

Accessible-description correction produced by OpenAI Codex — GPT-5.6 Sol, Ultra effort.
