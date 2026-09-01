"""Reuse the verified Indonesian reader implementation for the English lane."""

from pathlib import Path
import csv
import json
import re
import shutil


ROOT = Path(__file__).resolve().parents[1]
ID_ROOT = Path(r"C:\Users\Floris\Documents\interlanguage\04_mirrors\id\methods-of-algebra-volume-2-id")
ID_READER = ID_ROOT / "reader"
READER = ROOT / "reader"
TOOLS = READER / "tools"
BACKEND = ROOT / "backend"
TOOLS.mkdir(parents=True, exist_ok=True)
BACKEND.mkdir(parents=True, exist_ok=True)

# Exact reusable implementation/assets. The local MathJax license is retained.
shutil.copy2(ID_READER / "reader.css", READER / "reader.css")
shutil.copytree(ID_READER / "vendor" / "mathjax-3.2.2", READER / "vendor" / "mathjax-3.2.2", dirs_exist_ok=True)

build = (ID_READER / "tools" / "build_pandoc_reader.py").read_text(encoding="utf-8-sig")
repls = {
    'source_dir = project / "source" / "id-ID"': 'source_dir = project / "source" / "en"',
    'Al-jabr-2-id-complete-draft.tex': 'Al-jabr-2-en-complete-draft.tex',
    'figure-alt-text-id.csv': 'figure-alt-text-en.csv',
    'diagram-description-overrides-id.json': 'diagram-description-overrides-en.json',
    'alt_text_id': 'alt_text_en',
    'description_id': 'description_en',
    'pandoc tidak ditemukan': 'pandoc was not found',
    '148 unit/bridge diharapkan; ditemukan': 'Expected 148 units/bridges; found',
    '<html lang="id-ID">': '<html lang="en">',
    'Metode dalam Aljabar, Jilid 2 — edisi Bahasa Indonesia lengkap.': 'Methods of Algebra, Volume 2 — complete independent English edition.',
    'Metode dalam Aljabar, Jilid 2: Aljabar Linear — Edisi Bahasa Indonesia': 'Methods of Algebra, Volume 2: Linear Algebra — Independent English Edition',
    'Lewati ke konten utama': 'Skip to main content',
    'Metode dalam Aljabar II': 'Methods of Algebra II',
    'Edisi Bahasa Indonesia': 'Independent English Edition',
    'Metode dalam Aljabar</h1>': 'Methods of Algebra</h1>',
    'Jilid 2: Aljabar Linear': 'Volume 2: Linear Algebra',
    'Wen-Wei Li, penulis': 'Wen-Wei Li, author',
    'Tentang edisi ini': 'About this edition',
    'Edisi Bahasa Indonesia lengkap dari karya sumber 2024.': 'Complete independent English translation of the 2024 source work.',
    'CC BY 4.0. Edisi independen; penulis dan penerbit sumber tidak mendukung atau mengesahkannya.': 'CC BY 4.0. Independent edition; the source author and publisher do not endorse it.',
    'Navigasi unit': 'Unit navigation',
    'Navigasi 146 unit dan 2 jembatan': 'Navigate 146 units and 2 mastery bridges',
    'Daftar Pustaka': 'References',
    'Pembaca luring — edisi Bahasa Indonesia': 'Offline reader — independent English edition',
    'Aksesibilitas, atribusi, dan batasan': 'Accessibility, attribution, and limitations',
    'Diagram visual TeX/TikZ diganti deskripsi tekstual ledger pada fallback pembaca; PDF mempertahankan visual asli.':
        'Visual TeX/TikZ diagrams use source-traced English text descriptions in the HTML fallback; the PDF preserves the original visuals.',
}
for old, new in repls.items():
    build = build.replace(old, new)
english_env_names = '''ENV_NAMES = {
    "theorem": "Theorem", "teorema": "Theorem", "corollary": "Corollary",
    "korolari": "Corollary", "lemma": "Lemma", "lema": "Lemma",
    "proposition": "Proposition", "proposisi": "Proposition",
    "definition": "Definition", "definisi": "Definition",
    "definition-theorem": "Definition–Theorem", "definisiteorema": "Definition–Theorem",
    "definisi-proposisi": "Definition–Proposition", "definisiproposisi": "Definition–Proposition",
    "hypothesis": "Hypothesis", "hipotesis": "Hypothesis",
    "conjecture": "Conjecture", "konjektur": "Conjecture",
    "example": "Example", "contoh": "Example", "remark": "Remark",
    "catatan": "Remark", "convention": "Convention", "konvensi": "Convention",
    "proof": "Proof", "bukti": "Proof", "latihan": "Exercise",
}
'''
build = re.sub(r"ENV_NAMES = \{.*?\n\}\n", english_env_names, build, count=1, flags=re.DOTALL)
build = (build.replace(r'{persamaan}', r'{equation}')
              .replace(r'{rujukan}', r'{reference}')
              .replace(r'\\section*{Latihan}', r'\\section*{Exercises}')
              .replace(r'\\textbf{Petunjuk.}', r'\\textbf{Hint.}')
              .replace(r'\\textbf{Petunjuk Bacaan.}', r'\\textbf{Reading Guide.}')
              .replace("Override diagram tidak lengkap dalam", "Incomplete diagram override in")
              .replace("Override diagram duplikat", "Duplicate diagram override")
              .replace("Override tidak terdapat dalam ledger", "Override is absent from the ledger")
              .replace("Pandoc gagal pada", "Pandoc failed on")
              .replace("Independent English Edition lengkap dari karya sumber 2024.",
                       "Complete independent English translation of the 2024 source work."))
(TOOLS / "build_pandoc_reader.py").write_text(build, encoding="utf-8")

validate = (ID_READER / "tools" / "validate_reader.py").read_text(encoding="utf-8-sig")
validate = (validate.replace('"id-ID"', '"en"')
                    .replace('lang bukan id-ID', 'lang is not en')
                    .replace('tidak ada berkas HTML', 'no HTML files')
                    .replace('ID duplikat', 'duplicate ID')
                    .replace('gambar tanpa alt', 'image without alt text')
                    .replace('urutan unit', 'unit order')
                    .replace('tidak sama dengan 148 input master', 'does not match the 148 master inputs')
                    .replace('indeks unit tidak memuat 148 tautan', 'unit index does not contain 148 links')
                    .replace('bagian logis', 'logical sections')
                    .replace('bukan 149', 'not 149')
                    .replace('alt ledger diterapkan pada', 'alt-text ledger applied to')
                    .replace('sumber matematika semantik tidak ditemukan', 'semantic math source not found')
                    .replace('bundel MathJax lokal tidak dirujuk', 'local MathJax bundle not referenced')
                    .replace('makro matematika HTML tak didukung tersisa', 'unsupported HTML math macros remain')
                    .replace('token implementasi TeX/PGF mentah tersisa', 'raw TeX/PGF implementation tokens remain')
                    .replace('aset jaringan', 'network asset')
                    .replace('path absolut/privat', 'absolute/private path')
                    .replace('rujukan keluar dist', 'reference outside dist')
                    .replace('target lokal hilang', 'missing local target')
                    .replace('fragmen hilang', 'missing fragment'))
(TOOLS / "validate_reader.py").write_text(validate, encoding="utf-8")

# These are retained for parity/debugging, although the production generator
# already performs its own semantic post-processing.
post = (ID_READER / "tools" / "postprocess_reader.py").read_text(encoding="utf-8-sig")
for old, new in repls.items():
    post = post.replace(old, new)
post = post.replace('root.set("lang", "id-ID")', 'root.set("lang", "en")')
post = post.replace('aria-label="Navigasi unit"', 'aria-label="Unit navigation"')
post = post.replace('Navigasi langsung ke 146 unit dan 2 jembatan', 'Direct navigation to 146 units and 2 mastery bridges')
post = post.replace('frozen id-ID diagram-alt ledger', 'frozen English diagram-alt ledger')
(TOOLS / "postprocess_reader.py").write_text(post, encoding="utf-8")

accessibility = '''<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Accessibility, attribution, and limitations — Methods of Algebra II</title>
<link rel="stylesheet" href="reader.css"></head><body>
<a class="skip-link" href="#main-content">Skip to main content</a>
<header class="reader-header"><a class="reader-home" href="index.html">Methods of Algebra II</a>
<span class="reader-edition">Independent English Edition</span></header>
<main id="main-content" class="reader-main" tabindex="-1">
<h1>Accessibility, attribution, and limitations</h1>
<h2>What this reader provides</h2>
<p>This reader uses HTML headings, a linked unit index, stable per-unit anchors,
a skip link, visible keyboard focus, responsive reflow, and mathematics retained
as TeX and rendered locally by MathJax into CHTML with an assistive semantic
layer. Source diagrams matched to the ledger have stable identities and
source-traced English text descriptions. Stylesheets and reader assets are
local; no network fonts or CDN assets load. The only JavaScript is the local
MathJax 3.2.2 bundle (Apache License 2.0).</p>
<h2>Explicit limitations</h2>
<p>MathJax semantics improve access to mathematics, but pronunciation still
depends on the browser, operating system, and assistive technology. Complex
mathematical diagrams are summarized in text; a summary does not replace the
entire visual relation. No WCAG conformance level or tagged-PDF claim is made.</p>
<h2>Source, license, and non-endorsement</h2>
<p>Source: Wen-Wei Li, <cite>Methods of Algebra, Volume 2: Linear Algebra</cite>,
2024 edition, source commit <code>9a5803ff77dd3257484cb177f851a73770a59dd3</code>,
tree <code>23bd05c2fb8434278df4fdfb636559a6a2b0d2ff</code>. The source and this
derivative are available under <a href="https://creativecommons.org/licenses/by/4.0/">
Creative Commons Attribution 4.0 International (CC BY 4.0)</a>. Translation,
reader configuration, terminology reconciliation, and metadata were produced
with OpenAI Codex gpt-5.6-sol, Ultra, acting on instructions of the user. This
edition is independent; Wen-Wei Li and the source publisher do not endorse it.</p>
</main><footer class="reader-footer"><span>Offline reader — independent English edition</span>
<a href="index.html">Return to the book</a></footer></body></html>'''
(READER / "accessibility.html").write_text(accessibility + "\n", encoding="utf-8")

license_text = '''Methods of Algebra, Volume 2: Linear Algebra — Independent English Edition

Source work: Wen-Wei Li, Methods of Algebra, Volume 2: Linear Algebra,
2024 edition.

The source and this derivative edition are licensed under Creative Commons
Attribution 4.0 International (CC BY 4.0):
https://creativecommons.org/licenses/by/4.0/

Changes include English translation, terminology reconciliation, metadata,
the modular backend, HTML-reader configuration, and separately identified
source corrections. Production used OpenAI Codex gpt-5.6-sol, Ultra, acting on
instructions of the user.

This edition is independent. Wen-Wei Li and the source publisher do not
endorse this translation or reader.

The reader includes MathJax 3.2.2, Copyright (c) 2009-2021 The MathJax
Consortium, under the Apache License 2.0. A copy of the component license is in
vendor/mathjax-3.2.2/LICENSE-MathJax.txt.'''
(READER / "LICENSE.txt").write_text(license_text + "\n", encoding="utf-8")

overrides = {
  "schema": "o014-reader-diagram-description-overrides-en-v1",
  "purpose": "Reader-only source-derived English replacements for malformed or truncated ledger descriptions.",
  "overrides": [
    ["chapter1-unit-015-d003", "source/en/chapter1-unit-015.tex:52-59", "Left Kan-extension 2-cell diagram. Functors K: C → D and F: C → E; the two functors D → E are Lan_K F and L. Natural transformations η: F ⇒ (Lan_K F)K and χ: Lan_K F ⇒ L express ξ = (χK)η."],
    ["chapter1-unit-015-d005", "source/en/chapter1-unit-015.tex:76-83", "Right Kan-extension 2-cell diagram. Functors K: C → D and F: C → E; the two functors D → E are Ran_K F and R. Natural transformations ε: (Ran_K F)K ⇒ F and θ: R ⇒ Ran_K F express δ = ε(θK)."],
    ["chapter1-unit-017-d004", "source/en/chapter1-unit-017.tex:208-215", "Commutative diagram for condition S4. Morphisms t: Z ⇢ X and s: Y → W belong to S, and there are two morphisms f, g: X → Y. The equality sf = sg implies ft = gt."],
    ["chapter3-unit-037-d002", "source/en/chapter3-unit-037.tex:143-162", "Long exact sequence: … → H^(n−1)(Y) → H^(n−1)(Z) → H^n(X) → H^n(Y) → H^n(Z) → H^(n+1)(X) → …. Successive arrows are labeled H^(n−1)(g), δ^(n−1), H^n(f), H^n(g), and δ^n."],
    ["chapter3-unit-038-d005", "source/en/chapter3-unit-038.tex:160-177", "Long exact sequence: … → H^(n−1)(Y) → H^(n−1)(Z) → H^n(X) → H^n(Y) → H^n(Z) → H^(n+1)(X) → H^(n+1)(Y) → …."],
    ["chapter3-unit-043-d008", "source/en/chapter3-unit-043.tex:153-176", "Long exact sequence for a cohomological delta functor: 0 → F^0(X) → F^0(Y) → F^0(Z) → F^1(X) → F^1(Y) → F^1(Z) → F^2(X) → F^2(Y) → …. The connecting arrow F^n(Z) → F^(n+1)(X) is labeled δ^n."],
    ["chapter3-unit-043-d010", "source/en/chapter3-unit-043.tex:187-207", "Long exact sequence for a homological delta functor: … → F_2(Y) → F_2(Z) → F_1(X) → F_1(Y) → F_1(Z) → F_0(X) → F_0(Y) → F_0(Z) → 0. The connecting arrow F_n(Z) → F_(n−1)(X) is labeled ∂_n."],
    ["chapter3-unit-046-d010", "source/en/chapter3-unit-046.tex:453-461", "Commutative square. The top row is I → Cone(Δ_I)[−1], as in equation K-injective-diagonal; the bottom row is A → Cone(Δ_(τA))[−1]. The left vertical arrow is f: A → I, and the right vertical arrow is induced by all f_k."],
    ["chapter4-unit-056-d008", "source/en/chapter4-unit-056.tex:221-232", "Composition-comparison 2-cell diagram. Functors F'F: D → D'', Q: D → D/N, and Q'': D'' → D''/N''. The two functors D/N → D''/N'', namely R^(N''_N)(F'F) and R'R, are connected by the canonical natural transformation R^(N''_N)(F'F) ⇒ R'R."],
    ["chapter4-unit-062-d004", "source/en/chapter4-unit-062.tex:412-465", "Composition of 2-cells along the edges of a cube. A starting path containing a dashed edge is changed through a sequence of 2-cells into the final path; the resulting composite morphism is named beth."],
    ["chapter6-unit-086-d001", "source/en/chapter6-unit-086.tex:318-328", "Exact sequence of pointed sets: 1 → H^0(G,A) → H^0(G,B) → H^0(G,C) → H^1(G,A) → H^1(G,B). Successive arrows are labeled H^0(u), H^0(v), δ^0, and H^1(u)."],
    ["chapter6-unit-086-d002", "source/en/chapter6-unit-086.tex:330-342", "Exact sequence of pointed sets: 1 → H^0(G,A) → H^0(G,B) → H^0(G,C) → H^1(G,A) → H^1(G,B) → H^1(G,C). The connecting arrow H^0(G,C) → H^1(G,A) is labeled δ^0."],
    ["chapter6-unit-086-d003", "source/en/chapter6-unit-086.tex:344-360", "Exact sequence: 1 → H^0(G,A) → H^0(G,B) → H^0(G,C) → H^1(G,A) → H^1(G,B) → H^1(G,C) → H^2(G,A). Connecting arrows are labeled δ^0 and δ^1; the other arrows are induced by u and v."],
  ]
}
overrides["overrides"] = [{"diagram_id": a, "source_ref": b, "description_en": c} for a,b,c in overrides["overrides"]]
(READER / "diagram-description-overrides-en.json").write_text(json.dumps(overrides, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

# Initial deterministic English ledger. Formula strings and node labels remain
# exact; recurring Indonesian narrative frames are translated here and later
# checked for residue and mathematical traceability.
rows = list(csv.DictReader((ID_ROOT / "backend" / "figure-alt-text-id.csv").open(encoding="utf-8-sig", newline="")))
phrase_map = [
    ("satu persegi diberi tanda", "one square is marked"),
    ("panah penghubung", "connecting arrow"),
    ("panah lain", "other arrows"),
    ("simpul di kiri-atas", "node at upper left"),
    ("simpul di kiri-bawah", "node at lower left"),
    ("simpul di kanan-atas", "node at upper right"),
    ("simpul di kanan-bawah", "node at lower right"),
    ("simpul di kiri", "node on the left"),
    ("simpul di kanan", "node on the right"),
    ("persegi kiri atas", "upper-left square"),
    ("Komposisikan kedua lintasan", "Compose the two paths"),
    ("komposisi di sepanjang", "composition along"),
    ("transformasi alami", "natural transformation"),
    ("homomorfisme modul", "module homomorphism"),
    ("himpunan bertitik", "pointed sets"),
    ("adjoin kiri", "left adjoint"),
    ("adjoin kanan", "right adjoint"),
    ("Diagram kategori dengan persegi bertanda", "Category diagram with a square marked"),
    ("Diagram kategori", "Category diagram"),
    ("Diagram komutatif", "Commutative diagram"),
    ("Diagram eksak", "Exact diagram"),
    ("Diagram tali dengan label atau simpul", "String diagram with labels or nodes"),
    ("Diagram tali", "String diagram"),
    ("Diagram TikZ dengan label atau simpul", "TikZ diagram with labels or nodes"),
    ("untai, sisi, atau panah digambar menurut komposisi", "strands, edges, or arrows drawn according to the composition"),
    ("label lain", "other labels"),
    ("serta", "and"),
    ("kasus khusus", "special case"),
    ("Konteks", "Context"),
]
word_map = {
    "panah": "arrow", "simpul": "node", "morfisme": "morphism",
    "funktor": "functor", "kanonik": "canonical", "inklusi": "inclusion",
    "proyeksi": "projection", "objek": "object", "identitas": "identity",
    "isomorfisme": "isomorphism", "homomorfisme": "homomorphism",
    "ekuivalensi": "equivalence", "proposisi": "Proposition",
    "bukti": "proof", "kolom": "column", "baris": "row",
    "menyatakan": "indicates", "diinduksi": "induced", "penghubung": "connecting",
    "komposisi": "composition", "persegi": "square", "diberi": "given",
    "tanda": "mark", "lintasan": "path", "diagonal": "diagonal",
    "bagian": "part", "himpunan": "set", "modul": "module",
    "satu": "one", "dua": "two", "tiga": "three", "empat": "four",
    "lima": "five", "enam": "six", "lain": "other", "lainnya": "others",
    "kiri": "left", "kanan": "right", "atas": "upper", "bawah": "lower",
    "awal": "initial", "akhir": "final", "semua": "all", "kedua": "both",
    "terdapat": "there are", "seperti": "as", "persamaan": "equation",
    "diubah": "changed", "melalui": "through", "serangkaian": "a sequence of",
    "dinamai": "named", "mengakibatkan": "implies", "kesamaan": "the equality",
    "berada": "belong", "berbentuk": "in the form of", "berlabel": "labeled",
    "berturut-turut": "successively", "menurut": "according to",
    "dengan": "with", "dalam": "in", "dari": "from", "untuk": "for",
    "pada": "on", "oleh": "by", "sepanjang": "along", "dan": "and",
    "atau": "or", "ke": "to", "kasus": "case", "khusus": "special",
    "alami": "natural", "sisi": "edge",
}
for row in rows:
    text = row.pop("alt_text_id")
    for old, new in phrase_map:
        text = text.replace(old, new)
    for old, new in word_map.items():
        text = re.sub(rf"\b{re.escape(old)}\b", new, text, flags=re.IGNORECASE)
    row["alt_text_en"] = text
    row["provenance"] = row["provenance"].replace("id-ID/", "source/en/")
with (BACKEND / "figure-alt-text-en.csv").open("w", encoding="utf-8", newline="") as stream:
    writer = csv.DictWriter(stream, fieldnames=["diagram_id","unit_filename","local_order","alt_text_en","provenance"])
    writer.writeheader(); writer.writerows(rows)

print({"ledger_rows": len(rows), "overrides": len(overrides["overrides"])})
