# Methods of Algebra, Volume 2: Linear Algebra - Independent English Edition

This repository contains a complete independent English-access derivative of
Wen-Wei Li's Chinese textbook *Methods of Algebra*, Volume 2. It preserves the
146-unit source structure and adds two separately attributed mastery bridges
with exercises and full solutions.

Public release status: complete PDF and HTML readers, editable source,
modular backend, and published Zenodo archive.

Reader links:

- Reflowable HTML: <https://kokunoyumeto.github.io/methods-of-algebra-volume-2-en/>
- Repository: <https://github.com/KokunoYumeto/methods-of-algebra-volume-2-en>
- Archival DOI: <https://doi.org/10.5281/zenodo.22233942>

## Source authority

- Author: Wen-Wei Li
- Original title: 代数学方法, 卷二, 线性代数
- Edition: Higher Education Press, 2024
- ISBN: 978-7-04-062754-1
- Official source: <https://github.com/wenweili/AlJabr-2>
- Frozen commit: `9a5803ff77dd3257484cb177f851a73770a59dd3`
- Frozen tree: `23bd05c2fb8434278df4fdfb636559a6a2b0d2ff`

The official repository describes the work as *Methods of Algebra*. A bounded
check of the author's Books page and the pinned repository did not find a
suitable complete English edition in those official sources. That is not a
claim that no English version exists anywhere.

## Contents

- `source/en/`: complete editable XeLaTeX edition and source assets
- `backend/`: locale-linked units, segments, terminology, bridge, and diagram
  accessibility data keyed by stable course identifiers
- `reader/`: accessible offline HTML reader and deterministic build tools
- `output/pdf/`: the built PDF reader
- `controls/`, `qa/`, and `release/`: source freeze, production cursor,
  validation evidence, manifests, and public-byte receipts

The PDF preserves the source's TikZ diagrams. The HTML reader provides local
MathJax rendering, responsive reflow, stable anchors, and source-traced English
text fallbacks for complex diagrams. No network connection is required after
the offline-reader package has been extracted.

## Reproducible builds

The PDF build must use the workspace-wide TeX mutex. From this directory run:

```powershell
python tools/build_english_pdf.py
```

After all 146 unit admissions and the backend validation pass, build the HTML
reader with:

```powershell
python tools/build_english_reader.py
```

Exact source identities, commands, byte counts, SHA-256 hashes, limitations,
and validation results are written to machine-readable receipts in `qa/`.

## License, attribution, and status

The complete official codebase is licensed under Creative Commons Attribution
4.0 International (CC BY 4.0), and this derivative is distributed under the
same license. See `source/en/LICENSE`.

English translation, terminology reconciliation, reader configuration,
metadata, and the modular backend were produced with **OpenAI Codex
gpt-5.6-sol, Ultra**, acting on instructions of the user. This disclosure does
not displace Wen-Wei Li's authorship or any other human or component credit.
The two mastery bridges are independent course additions and are not attributed
to the source author.

This edition is independent. Wen-Wei Li and Higher Education Press do not
endorse it.
