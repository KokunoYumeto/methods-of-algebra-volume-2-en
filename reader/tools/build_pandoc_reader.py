#!/usr/bin/env python3
"""Build the complete reflowed reader directly from the admitted LaTeX units.

This is the deterministic fallback for a reproducible TeX4ht failure in the
book's list/array and multi-column math surfaces. Pandoc preserves prose,
lists, headings and raw TeX math; local MathJax renders the mathematics.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import csv
import hashlib
import html as html_std
import json
import re
import shutil
import subprocess
from collections import defaultdict
from pathlib import Path

from lxml import etree, html


UNIT_RE = re.compile(
    r"\\input\{((?:prelude-unit-\d{3}|chapter\d+-unit-\d{3}|"
    r"appendix\d+-unit-\d{3}|mastery-bridge-[^}]+))\}"
)
EXPECTED_UNITS_AND_BRIDGES = 148
EXPECTED_LOGICAL_SECTIONS = 149
EXPECTED_DIAGRAMS = 907
MATHJAX_COMPATIBILITY_MACROS = {
    "ensuremath": ["#1", 1],
    "bm": [r"\boldsymbol{#1}", 1],
    "EuScript": [r"\mathcal{#1}", 1],
    "mapsfrom": r"\mathrel{↤}",
    "longmapsfrom": r"\mathrel{⟻}",
    "llbracket": r"\mathopen{⟦}",
    "rrbracket": r"\mathclose{⟧}",
    "multicolumn": ["#3", 3],
    "index": ["", 1],
    "par": "",
}
LEDGER_FIELDS = {
    "diagram_id", "unit_filename", "local_order", "alt_text_en", "provenance"
}
DIAGRAM_RE = re.compile(
    r"\\begin\{(tikzcd|tikzpicture)\}(.*?)\\end\{\1\}", re.DOTALL
)
RAW_HYPERTARGET_RE = re.compile(r"\\hypertarget\{([^{}]+)\}\{\}")
ENV_NAMES = {
    "theorem": "Theorem", "teorema": "Theorem", "corollary": "Corollary",
    "korolari": "Corollary", "lemma": "Lemma", "lema": "Lemma",
    "proposition": "Proposition", "proposisi": "Proposition",
    "definition": "Definition", "definisi": "Definition",
    "definition-theorem": "Definition–Theorem", "definisiteorema": "Definition–Theorem",
    "definition-proposition": "Definition–Proposition",
    "definisi-proposisi": "Definition–Proposition", "definisiproposisi": "Definition–Proposition",
    "hypothesis": "Hypothesis", "hipotesis": "Hypothesis",
    "conjecture": "Conjecture", "konjektur": "Conjecture",
    "example": "Example", "contoh": "Example", "remark": "Remark",
    "catatan": "Remark", "convention": "Convention", "konvensi": "Convention",
    "proof": "Proof", "bukti": "Proof", "latihan": "Exercise",
    "exercise": "Exercise",
}

DIAGRAM_TEXT_SYMBOLS = {
    r"\twoheadrightarrow": "↠", r"\hookrightarrow": "↪",
    r"\longrightarrow": "→", r"\longleftarrow": "←",
    r"\rightarrow": "→", r"\leftarrow": "←", r"\mapsto": "↦",
    r"\rightiso": "≅", r"\simeq": "≃", r"\sim": "∼",
    r"\otimes": "⊗", r"\dotimes": "⊗", r"\otimesL": "⊗ᴸ",
    r"\oplus": "⊕", r"\bigoplus": "⊕", r"\times": "×",
    r"\dtimes": "×", r"\prod": "∏", r"\coprod": "∐",
    r"\sqcup": "⊔", r"\dsqcup": "⊔", r"\sum": "∑",
    r"\cup": "∪", r"\cap": "∩", r"\wedge": "∧", r"\vee": "∨",
    r"\cdot": "·", r"\bullet": "•", r"\star": "★",
    r"\Box": "□", r"\boxplus": "⊞", r"\flat": "♭",
    r"\circ": "∘", r"\subset": "⊂", r"\backslash": "∖",
    r"\cdots": "…", r"\ldots": "…", r"\vdots": "⋮",
    r"\infty": "∞", r"\exists": "∃", r"\forall": "∀",
    r"\geq": "≥", r"\leq": "≤", r"\in": "∈", r"\notin": "∉",
    r"\varinjlim": "colim", r"\varprojlim": "lim",
    r"\identity": "id", r"\munit": "1", r"\partial": "∂",
    r"\Hom": "Hom", r"\coHom": "coHom", r"\End": "End",
    r"\Ker": "ker", r"\Coker": "coker", r"\Image": "im",
    r"\Coim": "coim", r"\Cone": "Cone", r"\Ext": "Ext",
    r"\Obj": "Ob", r"\Hm": "H", r"\TaHm": "H-hat",
    r"\IndC": "Ind", r"\Ind": "Ind", r"\coEnd": "coend",
    r"\alpha": "α", r"\beta": "β", r"\Gamma": "Γ",
    r"\delta": "δ", r"\epsilon": "ε", r"\varepsilon": "ε",
    r"\eta": "η", r"\theta": "θ", r"\iota": "ι",
    r"\lambda": "λ", r"\mu": "μ", r"\nu": "ν",
    r"\xi": "ξ", r"\Pi": "Π", r"\rho": "ρ",
    r"\Sigma": "Σ", r"\tau": "τ", r"\phi": "φ",
    r"\varphi": "φ", r"\psi": "ψ", r"\Omega": "Ω",
    r"\Bbbk": "k", r"\Z": "ℤ", r"\N": "ℕ", r"\Q": "ℚ",
    r"\R": "ℝ", r"\to": "→",
    r"\left": "", r"\right": "", r"\displaystyle": "",
    r"\tikztostart": "", r"\tikztonodes": "",
    r"\phori": "d_h", r"\dhori": "d_h",
    r"\pvert": "d_v", r"\dvert": "d_v",
}


def plain_diagram_description(value: str) -> str:
    """Make source-traced TeX summaries readable as visible/assistive text."""
    wrappers = (
        "mathcal", "mathsf", "mathrm", "mathbf", "mathfrak", "text",
        "textrm", "textsf", "textbf", "textit", "operatorname", "ensuremath",
        "cate",
    )
    for _ in range(8):
        previous = value
        for command in wrappers:
            value = re.sub(
                r"\\" + command + r"\{([^{}]*)\}", r"\1", value
            )
        for command, label in {
            "overline": "overline", "underline": "underline",
            "tilde": "tilde", "check": "check", "widehat": "hat",
            "bar": "bar",
        }.items():
            value = re.sub(
                r"\\" + command + r"\{([^{}]*)\}",
                lambda match, name=label: f"{name}({match.group(1)})",
                value,
            )
        if value == previous:
            break
    for command, replacement in sorted(
        DIAGRAM_TEXT_SYMBOLS.items(), key=lambda item: len(item[0]), reverse=True
    ):
        value = value.replace(command, replacement)
    value = value.replace(r"\\", "; ").replace(r"\;", " ").replace(r"\&", "; ")
    value = value.replace(r"\{", "{").replace(r"\}", "}")
    # Unknown semantic macros are still more legible as words than as exposed
    # backslash commands. Braces group TeX arguments and carry no prose value.
    value = re.sub(r"\\([A-Za-z]+)", r"\1", value)
    value = value.replace("\\", "")
    value = value.replace("{", "").replace("}", "")
    for source, target in {
        "kelasnya": "its class", "citranya": "its image",
        "pemetaan": "maps", "homotopi": "homotopy",
        "di three column": "in the third column",
        "beginarrayr|l": "", "endarray": "",
    }.items():
        value = re.sub(r"\b" + re.escape(source) + r"\b", target, value, flags=re.I)
    value = re.sub(r"\s+", " ", value).strip()
    return value


def macro_preamble(source_dir: Path) -> str:
    """Collect balanced command declarations Pandoc can expand in math."""
    declarations: list[str] = []
    starters = re.compile(
        r"^\s*\\(?:newcommand|renewcommand|providecommand|DeclareMathOperator\*?|"
        r"DeclarePairedDelimiterX?|DeclareRobustCommand|newrobustcmd)"
    )
    # Do not feed myarrows.sty to Pandoc.  Its print implementation deliberately
    # redefines semantic x-arrow commands with PGF/TikZ box measurements.  Pandoc
    # expands those definitions into raw \setbox/\pgfmath/\tikz code, which a
    # browser MathJax input processor cannot execute.  Leaving the semantic
    # commands unexpanded lets MathJax's AMS/extpfeil packages render them.
    for name in ("mycommand.sty",):
        lines = (source_dir / name).read_text(encoding="utf-8").splitlines()
        collecting: list[str] = []
        balance = 0
        for line in lines:
            if not collecting and starters.match(line):
                collecting = [line]
                balance = line.count("{") - line.count("}")
                if balance <= 0:
                    declarations.append("\n".join(collecting))
                    collecting = []
            elif collecting:
                collecting.append(line)
                balance += line.count("{") - line.count("}")
                if balance <= 0:
                    declarations.append("\n".join(collecting))
                    collecting = []
    return normalize_math_for_html("\n".join(declarations) + "\n")


def normalize_math_for_html(text: str) -> str:
    """Replace print-only text glyph commands with their Unicode semantics."""
    return (
        text.replace(r"\textquotedblleft", "“")
        .replace(r"\textquotedblright", "”")
    )


def strip_tex_comments(text: str) -> str:
    """Remove unescaped TeX comments after durable comment markers are lifted."""
    output: list[str] = []
    for line in text.splitlines(keepends=True):
        cut = len(line)
        for index, char in enumerate(line):
            if char != "%":
                continue
            slashes = 0
            cursor = index - 1
            while cursor >= 0 and line[cursor] == "\\":
                slashes += 1
                cursor -= 1
            if slashes % 2 == 0:
                cut = index
                break
        newline = "\n" if line.endswith("\n") else ""
        output.append(line[:cut].rstrip("\r\n") + newline)
    return "".join(output)


def strip_index_commands(text: str) -> tuple[str, int]:
    """Remove active makeindex metadata without exposing it as reader prose."""
    output: list[str] = []
    cursor = 0
    removed = 0
    command = re.compile(r"\\index(?![A-Za-z])")

    def consume_group(start: int, opener: str, closer: str) -> int:
        if start >= len(text) or text[start] != opener:
            raise ValueError(f"Malformed \\index command near byte {start}")
        depth = 0
        position = start
        while position < len(text):
            char = text[position]
            escaped = position > 0 and text[position - 1] == "\\"
            if not escaped and char == opener:
                depth += 1
            elif not escaped and char == closer:
                depth -= 1
                if depth == 0:
                    return position + 1
            position += 1
        raise ValueError(f"Unclosed \\index argument near byte {start}")

    while True:
        match = command.search(text, cursor)
        if match is None:
            output.append(text[cursor:])
            break
        output.append(text[cursor:match.start()])
        position = match.end()
        while position < len(text) and text[position].isspace():
            position += 1
        if position < len(text) and text[position] == "[":
            position = consume_group(position, "[", "]")
            while position < len(text) and text[position].isspace():
                position += 1
        position = consume_group(position, "{", "}")
        cursor = position
        removed += 1
    return "".join(output), removed


def load_diagram_overrides(path: Path, ledger_rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    """Load audited reader-only descriptions for malformed ledger summaries."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = payload.get("overrides", [])
    overrides: dict[str, dict[str, str]] = {}
    for row in rows:
        diagram_id = str(row.get("diagram_id", "")).strip()
        description = str(row.get("description_en", "")).strip()
        source_ref = str(row.get("source_ref", "")).strip()
        if not diagram_id or not description or not source_ref:
            raise ValueError(f"Incomplete diagram override in {path}")
        if diagram_id in overrides:
            raise ValueError(f"Duplicate diagram override: {diagram_id}")
        overrides[diagram_id] = {
            "description_en": description,
            "source_ref": source_ref,
        }
    ledger_ids = {row["diagram_id"] for row in ledger_rows}
    unknown = sorted(set(overrides) - ledger_ids)
    if unknown:
        raise ValueError(f"Override is absent from the ledger: {unknown}")
    return overrides


def validate_ledger(
    rows: list[dict[str, str]], expected_files: set[str]
) -> None:
    """Fail closed unless the diagram ledger is an exact, ordered closure."""
    if len(rows) != EXPECTED_DIAGRAMS:
        raise ValueError(
            f"Expected {EXPECTED_DIAGRAMS} diagram descriptions; found {len(rows)}"
        )
    missing_fields = LEDGER_FIELDS - set(rows[0] if rows else ())
    if missing_fields:
        raise ValueError(f"Diagram ledger is missing columns: {sorted(missing_fields)}")
    diagram_ids: set[str] = set()
    orders: dict[str, list[int]] = defaultdict(list)
    for row_number, row in enumerate(rows, start=2):
        diagram_id = row["diagram_id"].strip()
        unit_filename = row["unit_filename"].strip()
        description = row["alt_text_en"].strip()
        provenance = row["provenance"].strip()
        if not diagram_id or not description or not provenance:
            raise ValueError(
                f"Blank diagram identity, description, or provenance at ledger row {row_number}"
            )
        if diagram_id in diagram_ids:
            raise ValueError(f"Duplicate diagram ID in ledger: {diagram_id}")
        diagram_ids.add(diagram_id)
        if unit_filename not in expected_files:
            raise ValueError(
                f"Ledger row {row_number} names an unplanned unit: {unit_filename}"
            )
        try:
            local_order = int(row["local_order"])
        except ValueError as exc:
            raise ValueError(f"Invalid local_order at ledger row {row_number}") from exc
        if local_order < 1:
            raise ValueError(f"Non-positive local_order at ledger row {row_number}")
        orders[unit_filename].append(local_order)
    for unit_filename, values in orders.items():
        expected_orders = list(range(1, len(values) + 1))
        if sorted(values) != expected_orders:
            raise ValueError(
                f"Non-contiguous diagram order for {unit_filename}: {sorted(values)}"
            )


def preprocess(text: str, rows: list[dict[str, str]]) -> tuple[str, list[str], int]:
    # One source-primary correction keeps an inherited literal ``qquad`` token
    # byte-for-byte by making ``q`` active locally for print TeX. Pandoc cannot
    # parse that active-character shim. Replace only that exact scoped construct
    # with its semantic browser form; the canonical source remains untouched.
    text = re.sub(
        r"\\begingroup\s*"
        r"\\mathcode`q=\"8000\s*"
        r"\\begingroup\\lccode`~=`q\\lowercase\{\\endgroup\\def~~uad\{\\qquad\}\}\s*"
        r"(\\\[.*?\\\])\s*"
        r"\\endgroup",
        lambda match: re.sub(r"(?<!\\)\bqquad\b", r"\\qquad", match.group(1)),
        text,
        flags=re.DOTALL,
    )
    text = normalize_math_for_html(text)
    # Preserve every durable segment and LaTeX label as an HTML anchor.
    text = re.sub(r"(?m)^\s*%\s*segment-id:\s*([^\s]+)\s*$", r"\\hypertarget{\1}{}", text)
    text = strip_tex_comments(text)
    text, index_commands_removed = strip_index_commands(text)
    text = re.sub(r"\\label\{([^}]+)\}", r"\\hypertarget{\1}{}", text)
    text = re.sub(
        r"\\sourcecrossref\{([^}]+)\}\{([^}]*)\}",
        r"\\href{#\1}{\2}", text,
    )
    text = re.sub(r"\\eqref\{([^}]+)\}", r"\\href{#\1}{equation}", text)
    text = re.sub(r"\\ref\{([^}]+)\}", r"\\href{#\1}{reference}", text)
    text = re.sub(
        r"\\cite(?:\[[^]]*\])?\{([^}]+)\}",
        lambda m: "\\href{#ref-" + m.group(1).split(",")[0].strip() + "}{[" + m.group(1) + "]}",
        text,
    )

    # ``compactitem``/``compactenum`` are formatting-only aliases supplied by
    # the print preamble. Pandoc does not know those environments and can drop
    # their item bodies, including diagram placeholders. Normalize them to the
    # semantically identical core LaTeX list environments before conversion.
    for compact, standard in {
        "compactitem": "itemize",
        "compactenum": "enumerate",
        "compactdesc": "description",
    }.items():
        text = text.replace(r"\begin{" + compact + "}", r"\begin{" + standard + "}")
        text = text.replace(r"\end{" + compact + "}", r"\end{" + standard + "}")

    # Pandoc's LaTeX reader silently discards some display-math bodies inside
    # ``description`` items (observed in the Yoneda operations list), which in
    # turn drops their diagram placeholders.  Retain the list semantics while
    # expressing each term as a bold item lead in an ordinary itemize list.
    # Restrict the item rewrite to complete description environments so
    # optional labels belonging to other list types are never changed.
    def description_as_itemize(match: re.Match[str]) -> str:
        body = re.sub(
            r"\\item\[([^]]+)\]",
            lambda item: r"\item \textbf{" + item.group(1) + r".}\quad ",
            match.group(1),
        )
        return r"\begin{itemize}" + body + r"\end{itemize}"

    text = re.sub(
        r"\\begin\{description\}(.*?)\\end\{description\}",
        description_as_itemize,
        text,
        flags=re.DOTALL,
    )

    for env, label in ENV_NAMES.items():
        pattern = re.compile(r"\\begin\{" + re.escape(env) + r"\}(?:\[([^]]*)\])?")
        text = pattern.sub(lambda m: "\\par\\noindent\\textbf{" + label + (" (" + m.group(1) + ")" if m.group(1) else "") + ".}\\quad ", text)
        text = re.sub(r"\\end\{" + re.escape(env) + r"\}", r"\\par", text)
    text = re.sub(r"\\begin\{Exercises\}", r"\\section*{Exercises}", text)
    text = re.sub(r"\\end\{Exercises\}", "", text)
    text = re.sub(r"\\begin\{hint\}", r"\\textbf{Hint.}\\quad ", text)
    text = re.sub(r"\\end\{hint\}", "", text)
    text = re.sub(r"\\begin\{petunjukbacaan\}", r"\\par\\noindent\\textbf{Reading Guide.}\\quad ", text)
    text = re.sub(r"\\end\{petunjukbacaan\}", r"\\par", text)

    tokens: list[str] = []
    index = 0
    def diagram_sub(match: re.Match[str]) -> str:
        nonlocal index
        token = f"READERDIAGRAM{index:04d}"
        tokens.append(token)
        kind = match.group(1)
        index += 1
        # A small number of durable segment markers occur inside TikZ source.
        # Keep their generated anchors adjacent to the diagram placeholder;
        # replacing the whole environment must not delete those targets.
        internal_anchors = "".join(
            rf"\hypertarget{{{anchor_id}}}{{}}"
            for anchor_id in RAW_HYPERTARGET_RE.findall(match.group(0))
        )
        # The placeholder is temporary and later replaced by an accessible
        # figure.  TikZ pictures need a prose-safe wrapper when they occur
        # outside math, but neither wrapper needs the print-only ``\par`` that
        # previously leaked into MathJax source.
        placeholder = (
            r"\text{" + token + "}"
            if kind == "tikzcd"
            else r"\textbf{" + token + "}"
        )
        return internal_anchors + placeholder
    text = DIAGRAM_RE.sub(diagram_sub, text)
    return text, tokens, index_commands_removed


def diagram_figure(row: dict[str, str]) -> etree._Element:
    """Create one accessible, source-traced fallback for a TeX diagram."""
    caption_id = f"diagram-{row['diagram_id']}-caption"
    figure = etree.Element(
        "figure", {"class": "reader-diagram tex2jax_ignore", "role": "img",
                   "data-diagram-id": row["diagram_id"],
                   "data-description-source": row["reader_description_source"],
                   "aria-labelledby": caption_id}
    )
    caption = etree.SubElement(figure, "figcaption", id=caption_id)
    strong = etree.SubElement(caption, "strong")
    strong.text = f"Diagram {row['diagram_id']}. "
    strong.tail = plain_diagram_description(row["alt_text_en"])
    return figure


def replace_placeholder_text(
    element: etree._Element, replacements: dict[str, str]
) -> None:
    """Replace placeholder text without disturbing the element's markup."""
    for node in element.iter():
        if node.text:
            for token, replacement in replacements.items():
                node.text = node.text.replace(token, replacement)
        # The root tail is outside ``element`` and must remain untouched.
        if node is not element and node.tail:
            for token, replacement in replacements.items():
                node.tail = node.tail.replace(token, replacement)


def placeholder_host(wrapper: etree._Element, token: str) -> etree._Element | None:
    """Return Pandoc's deepest replaceable DOM host for one placeholder."""
    hits = wrapper.xpath(f"//*[contains(string(.), '{token}')]")
    if not hits:
        return None
    target = hits[-1]
    while (
        target.getparent() is not None
        and target.getparent() is not wrapper
        and target.tag not in {"p", "span", "div"}
    ):
        target = target.getparent()
    # A flow-level diagram group cannot validly replace a span inside a
    # paragraph. Promote to that paragraph and retain all of its prose/math as
    # the context child of the group.
    ancestor = target.getparent()
    while ancestor is not None and ancestor is not wrapper:
        if ancestor.tag == "p":
            target = ancestor
            break
        ancestor = ancestor.getparent()
    return target


def remove_raw_hypertargets(
    wrapper: etree._Element, known_ids: set[str]
) -> int:
    """Lift Pandoc-preserved TeX anchors out of math and into the DOM.

    Pandoc correctly emits ``\\hypertarget`` as an HTML anchor in ordinary
    prose, but preserves the literal command when it occurs inside display
    math.  MathJax then sees an unsupported command and can expose it as a red
    error.  Remove only the empty anchor commands introduced by ``preprocess``
    and insert equivalent HTML anchors immediately before their math host (or
    at the corresponding prose position).  The canonical source is untouched.
    """
    occurrences: list[tuple[str, etree._Element, str]] = []
    for node in wrapper.iter():
        for field in ("text", "tail"):
            value = getattr(node, field)
            if not value:
                continue
            matches = list(RAW_HYPERTARGET_RE.finditer(value))
            if not matches:
                continue
            for match in matches:
                anchor_id = match.group(1)
                if anchor_id not in known_ids:
                    raise ValueError(
                        f"Pandoc preserved an unregistered hypertarget: {anchor_id}"
                    )
                occurrences.append((anchor_id, node, field))
            setattr(node, field, RAW_HYPERTARGET_RE.sub("", value))

    present_ids = set(wrapper.xpath(".//*[@id]/@id"))
    for anchor_id, node, field in occurrences:
        if anchor_id in present_ids:
            continue
        anchor = etree.Element(
            "span", {"id": anchor_id, "class": "reader-anchor-fallback"}
        )

        # A raw command in MathJax source must become a sibling before the
        # complete math host, never a child of the math source element.
        math_host = None
        cursor = node
        while cursor is not None and cursor is not wrapper:
            classes = set((cursor.get("class") or "").split())
            if "math" in classes or "mathjax-inline" in classes or "mathjax-display" in classes:
                math_host = cursor
                break
            cursor = cursor.getparent()

        if math_host is not None and math_host.getparent() is not None:
            parent = math_host.getparent()
            parent.insert(parent.index(math_host), anchor)
        elif field == "tail" and node.getparent() is not None:
            parent = node.getparent()
            parent.insert(parent.index(node) + 1, anchor)
        elif node is not wrapper and node.getparent() is not None:
            parent = node.getparent()
            parent.insert(parent.index(node), anchor)
        else:
            wrapper.insert(0, anchor)
        present_ids.add(anchor_id)

    rendered = html.tostring(wrapper, encoding="unicode")
    if RAW_HYPERTARGET_RE.search(rendered) or r"\hypertarget" in rendered:
        raise ValueError("Raw hypertarget command remains after DOM anchor lifting")
    return len(occurrences)


def convert_one(args: tuple[int, str, Path, str, list[dict[str, str]], Path]) -> dict[str, object]:
    order, stem, source_path, macros, rows, pandoc = args
    source_bytes = source_path.read_bytes()
    source, tokens, index_commands_removed = preprocess(
        source_bytes.decode("utf-8"), rows
    )
    if len(tokens) != len(rows):
        raise ValueError(
            f"Diagram ledger closure failed for {source_path.name}: "
            f"{len(tokens)} active environments but {len(rows)} descriptions"
        )
    completed = subprocess.run(
        [str(pandoc), "-f", "latex+raw_tex", "-t", "html5", "--mathjax", "--wrap=none"],
        input=macros + source, text=True, encoding="utf-8", capture_output=True,
        check=False,
    )
    if completed.returncode:
        raise RuntimeError(f"Pandoc failed on {source_path.name}: {completed.stderr}")
    wrapper = html.fragment_fromstring("<div></div>")
    for fragment in html.fragments_fromstring(completed.stdout):
        if isinstance(fragment, str):
            if fragment.strip():
                paragraph = etree.SubElement(wrapper, "p")
                paragraph.text = fragment
        else:
            wrapper.append(fragment)

    known_ids = set(re.findall(r"\\hypertarget\{([^}]+)\}", source))
    raw_hypertargets_removed = remove_raw_hypertargets(wrapper, known_ids)
    renamed: dict[str, str] = {}
    for node in wrapper.xpath(".//*[@id]"):
        old = node.get("id")
        if old and old not in known_ids:
            new = f"{stem}--{old}"
            node.set("id", new)
            renamed[old] = new
    for link in wrapper.xpath(".//a[starts-with(@href, '#')]"):
        old = link.get("href")[1:]
        if old in renamed:
            link.set("href", "#" + renamed[old])

    # Pandoc cannot emit a DOM anchor when \label occurred inside display math.
    # Retain those stable targets at the owning unit boundary so every xref is
    # keyboard-navigable even when the exact equation-level placement is lost.
    present_ids = set(wrapper.xpath(".//*[@id]/@id"))
    for missing_id in sorted(known_ids - present_ids):
        wrapper.insert(0, etree.Element("span", {"id": missing_id, "class": "reader-anchor-fallback"}))

    token_rows = list(zip(tokens, rows, strict=True))
    for token, _row in token_rows:
        if wrapper.text_content().count(token) != 1:
            raise ValueError(
                f"Pandoc did not preserve exactly one {token} placeholder in {source_path.name}"
            )

    applied = 0
    pending = {token for token, _row in token_rows}
    for token, row in token_rows:
        if token not in pending:
            continue
        target = placeholder_host(wrapper, token)
        if target is None or target.getparent() is None:
            raise ValueError(f"Could not place diagram {row['diagram_id']} in {source_path.name}")
        target_text = target.text_content()
        hosted = [
            (hosted_token, hosted_row)
            for hosted_token, hosted_row in token_rows
            if hosted_token in pending and hosted_token in target_text
        ]
        if not hosted:
            raise ValueError(f"Could not group diagram {row['diagram_id']} in {source_path.name}")

        # Pandoc can place several adjacent diagram placeholders in one math
        # span. Replace that host once, preserve its equation/connective text as
        # references to the exact diagram IDs, then append every fallback in
        # source/ledger order. Replacing the host once avoids deleting sibling
        # placeholders while retaining the surrounding mathematical semantics.
        group = etree.Element(
            "div", {"class": "reader-diagram-group", "role": "group",
                    "aria-label": "Source diagram context and text alternatives"}
        )
        replacements = {
            hosted_token: f"Diagram {hosted_row['diagram_id']}"
            for hosted_token, hosted_row in hosted
        }
        replace_placeholder_text(target, replacements)
        target_class = (target.get("class") or "").split()
        if "reader-diagram-group-context" not in target_class:
            target.set("class", " ".join(target_class + ["reader-diagram-group-context"]))
        parent = target.getparent()
        parent.replace(target, group)
        group.append(target)
        for hosted_token, hosted_row in hosted:
            group.append(diagram_figure(hosted_row))
            pending.remove(hosted_token)
            applied += 1
    if pending:
        raise ValueError(
            f"Unplaced diagram placeholders in {source_path.name}: {sorted(pending)}"
        )
    final_ids = set(wrapper.xpath(".//*[@id]/@id"))
    missing_anchor_targets = sorted(known_ids - final_ids)
    if missing_anchor_targets:
        raise ValueError(
            f"Reader lost {len(missing_anchor_targets)} durable anchor targets in "
            f"{source_path.name}: {missing_anchor_targets[:10]}"
        )
    rendered = html.tostring(wrapper, encoding="unicode")
    if "READERDIAGRAM" in rendered:
        raise ValueError(f"Unresolved diagram placeholder remains in {source_path.name}")
    headings = wrapper.xpath(".//h1 | .//h2 | .//h3 | .//h4 | .//h5 | .//h6")
    label = " ".join(headings[0].itertext()).strip() if headings else ""
    if not label:
        label = stem.replace("-", " ")
    return {"order": order, "stem": stem, "label": label, "html": rendered,
            "stderr": completed.stderr, "diagrams": applied,
            "raw_hypertargets_removed": raw_hypertargets_removed,
            "source_anchor_targets": len(known_ids),
            "index_commands_removed": index_commands_removed,
            "source_sha256": hashlib.sha256(source_bytes).hexdigest()}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True, type=Path)
    parser.add_argument("--reader", required=True, type=Path)
    args = parser.parse_args()
    project = args.project.resolve()
    reader = args.reader.resolve()
    script_reader = Path(__file__).resolve().parents[1]
    script_project = script_reader.parent
    if project != script_project or reader != script_reader or reader != project / "reader":
        raise SystemExit(
            "Reader build paths must resolve to this script's project and reader directories"
        )
    source_dir = project / "source" / "en"
    master = source_dir / "Al-jabr-2-en-complete-draft.tex"
    dist = reader / "dist"
    build = reader / "build"
    dist.mkdir(parents=True, exist_ok=True)
    build.mkdir(parents=True, exist_ok=True)
    pandoc = Path(shutil.which("pandoc") or "")
    if not pandoc:
        raise SystemExit("pandoc was not found")

    master_bytes = master.read_bytes()
    stems = UNIT_RE.findall(master_bytes.decode("utf-8"))
    if len(stems) != EXPECTED_UNITS_AND_BRIDGES or len(set(stems)) != len(stems):
        raise SystemExit(
            f"Expected {EXPECTED_UNITS_AND_BRIDGES} distinct units/bridges; "
            f"found {len(stems)} inputs and {len(set(stems))} distinct inputs"
        )
    expected_files = {f"{stem}.tex" for stem in stems}
    missing_sources = sorted(
        filename for filename in expected_files if not (source_dir / filename).is_file()
    )
    if missing_sources:
        raise SystemExit(f"Missing planned reader sources: {missing_sources}")
    with (project / "backend" / "figure-alt-text-en.csv").open(encoding="utf-8-sig", newline="") as stream:
        ledger_rows = list(csv.DictReader(stream))
    validate_ledger(ledger_rows, expected_files)
    override_path = reader / "diagram-description-overrides-en.json"
    diagram_overrides = load_diagram_overrides(override_path, ledger_rows)
    for row in ledger_rows:
        override = diagram_overrides.get(row["diagram_id"])
        row["reader_description_source"] = row["provenance"].strip()
        if override:
            row["alt_text_en"] = override["description_en"]
            row["reader_description_source"] = override["source_ref"]
    ledger: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in ledger_rows:
        ledger[row["unit_filename"]].append(row)
    for rows in ledger.values():
        rows.sort(key=lambda row: int(row["local_order"]))
    macros = macro_preamble(source_dir)
    css_version = hashlib.sha256((reader / "reader.css").read_bytes()).hexdigest()[:16]
    mathjax_macros_json = json.dumps(
        MATHJAX_COMPATIBILITY_MACROS,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    jobs = [
        (i, stem, source_dir / f"{stem}.tex", macros, ledger.get(f"{stem}.tex", []), pandoc)
        for i, stem in enumerate(stems)
    ]
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        results = list(executor.map(convert_one, jobs))
    results.sort(key=lambda row: row["order"])

    bib = subprocess.run(
        [str(pandoc), "-f", "latex", "-t", "html5", "--citeproc",
         "--bibliography", str(source_dir / "Al-jabr.bib"), "--wrap=none"],
        input=r"\nocite{*}", text=True, encoding="utf-8", capture_output=True, check=True,
    ).stdout
    nav_items = "\n".join(
        f'<li><a href="#unit-{r["stem"]}">{html_std.escape(str(r["label"]))}</a></li>'
        for r in results
    )
    sections = "\n".join(
        f'<section id="unit-{r["stem"]}" class="reader-unit" data-unit-file="{r["stem"]}.tex" '
        f'role="doc-chapter" aria-label="{html_std.escape(str(r["label"]), quote=True)}">'
        f'{r["html"]}</section>' for r in results
    )
    document = f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="author" content="Wen-Wei Li">
<meta name="description" content="Methods of Algebra, Volume 2 — complete independent English edition.">
<title>Methods of Algebra, Volume 2: Linear Algebra — Independent English Edition</title>
<link rel="stylesheet" href="reader.css?v={css_version}">
<script>window.MathJax={{tex:{{tags:"ams",macros:{mathjax_macros_json}}},options:{{enableAssistiveMml:true,ignoreHtmlClass:"tex2jax_ignore"}},chtml:{{fontURL:"vendor/mathjax-3.2.2/output/chtml/fonts/woff-v2"}}}};</script>
<script defer src="vendor/mathjax-3.2.2/tex-chtml-full.js"></script></head><body>
<a class="skip-link" href="#main-content">Skip to main content</a>
<header class="reader-header"><a class="reader-home" href="index.html">Methods of Algebra II</a><span class="reader-edition">Independent English Edition</span></header>
<main id="main-content" class="reader-main" tabindex="-1">
<section class="reader-cover" aria-labelledby="book-title"><h1 id="book-title">Methods of Algebra</h1><p class="reader-cover-volume">Volume 2: Linear Algebra</p><p class="reader-cover-author">Wen-Wei Li, author</p><hr><h2>About this edition</h2><p>Complete independent English translation of the 2024 source work.</p><p class="reader-cover-license">CC BY 4.0. Independent edition; the source author and publisher do not endorse it.</p></section>
<nav class="reader-unit-index" aria-label="Unit navigation"><details open><summary>Navigate 146 units and 2 mastery bridges</summary><ol>{nav_items}</ol></details></nav>
{sections}
<section id="bibliography" class="reader-unit" aria-labelledby="bibliography-heading"><h1 id="bibliography-heading">References</h1>{bib}</section>
</main><footer class="reader-footer"><span>Offline reader — independent English edition</span><a href="accessibility.html">Accessibility, attribution, and limitations</a></footer></body></html>'''
    (dist / "index.html").write_text(document, encoding="utf-8")
    shutil.copy2(reader / "reader.css", dist / "reader.css")
    shutil.copy2(reader / "accessibility.html", dist / "accessibility.html")
    shutil.copy2(reader / "LICENSE.txt", dist / "LICENSE.txt")
    shutil.copytree(reader / "vendor" / "mathjax-3.2.2", dist / "vendor" / "mathjax-3.2.2", dirs_exist_ok=True)
    report = {
        "backend": "Pandoc LaTeX reader + local MathJax 3.2.2",
        "units_and_bridges": len(results),
        "logical_sections": EXPECTED_LOGICAL_SECTIONS,
        "ledger_diagrams": len(ledger_rows),
        "diagram_descriptions_embedded": sum(int(r["diagrams"]) for r in results),
        "raw_hypertarget_commands_lifted_to_dom_anchors": sum(
            int(r["raw_hypertargets_removed"]) for r in results
        ),
        "source_anchor_targets_preserved": sum(
            int(r["source_anchor_targets"]) for r in results
        ),
        "index_commands_removed_from_reader_surface": sum(
            int(r["index_commands_removed"]) for r in results
        ),
        "mathjax_compatibility_macros": MATHJAX_COMPATIBILITY_MACROS,
        "diagram_description_overrides": len(diagram_overrides),
        "diagram_description_override_file": override_path.name,
        "reader_css_version": css_version,
        "source_inputs": {
            "master": {"path": master.relative_to(project).as_posix(),
                       "sha256": hashlib.sha256(master_bytes).hexdigest()},
            "bibliography": {"path": "source/en/Al-jabr.bib",
                             "sha256": hashlib.sha256((source_dir / "Al-jabr.bib").read_bytes()).hexdigest()},
            "macro_file": {"path": "source/en/mycommand.sty",
                           "sha256": hashlib.sha256((source_dir / "mycommand.sty").read_bytes()).hexdigest()},
            "diagram_ledger": {"path": "backend/figure-alt-text-en.csv",
                               "sha256": hashlib.sha256((project / "backend" / "figure-alt-text-en.csv").read_bytes()).hexdigest()},
            "units": [
                {"path": f"source/en/{r['stem']}.tex", "sha256": r["source_sha256"]}
                for r in results
            ],
        },
        "reader_inputs": {
            "stylesheet": {"path": "reader/reader.css",
                           "sha256": hashlib.sha256((reader / "reader.css").read_bytes()).hexdigest()},
            "accessibility_page": {"path": "reader/accessibility.html",
                                   "sha256": hashlib.sha256((reader / "accessibility.html").read_bytes()).hexdigest()},
            "diagram_overrides": {"path": f"reader/{override_path.name}",
                                  "sha256": hashlib.sha256(override_path.read_bytes()).hexdigest()},
            "mathjax_files": [
                {"path": path.relative_to(project).as_posix(),
                 "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
                for path in sorted((reader / "vendor" / "mathjax-3.2.2").rglob("*"))
                if path.is_file()
            ],
        },
        "pandoc_warnings": [r["stderr"] for r in results if str(r["stderr"]).strip()],
        "explicit_limitation": "Visual TeX/TikZ diagrams use source-traced English text descriptions in the HTML fallback; the PDF preserves the original visuals.",
    }
    (build / "reader-build-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
