"""Build the complete English diagram-accessibility ledger from its inventory.

The inventory is the ordering and source-body authority.  Descriptions that
already pass the English ledger validator are copied byte-for-byte.  Missing
or invalid descriptions are rebuilt as concise graph summaries from the
corresponding TikZ body.  This deliberately describes objects and morphisms;
it never copies a raw TikZ program into alt text.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
import re

from validate_english_diagram_ledger import (
    HAN,
    INDONESIAN,
    PLACEHOLDER,
    ROOT,
    braces_balanced,
)


INVENTORY = ROOT / "qa" / "DIAGRAM_SOURCE_INVENTORY.jsonl"
LEDGER = ROOT / "backend" / "figure-alt-text-en.csv"


# The eight omitted tikzpicture environments are small geometric glyphs rather
# than object-and-arrow grids, so a direct visual account is clearer than the
# graph summarizer used for tikzcd.
PICTURE_DESCRIPTIONS = {
    "chapter4-unit-060-diagram-003": (
        "Small path icon: an arrow rises diagonally from the lower left to a "
        "central corner, then continues horizontally to the right."
    ),
    "chapter4-unit-060-diagram-004": (
        "Small path icon: a V-shaped arrow descends diagonally from the upper "
        "left to a lower corner and then rises diagonally to the upper right."
    ),
    "chapter8-unit-106-diagram-001": "Geometric realization of a zero-simplex, drawn as one black point.",
    "chapter8-unit-106-diagram-002": "Geometric realization of a one-simplex, drawn as a single diagonal line segment.",
    "chapter8-unit-106-diagram-003": (
        "Geometric realization of a two-simplex, drawn as a lightly shaded "
        "filled triangle with a dark boundary."
    ),
    "chapter8-unit-106-diagram-004": (
        "Geometric realization of a three-simplex, shown as a projected "
        "tetrahedron with four triangular faces, a dashed hidden edge, and "
        "contrasting shading on the front faces."
    ),
    "chapter9-unit-121-diagram-006": (
        "Small right-angle path icon: an arrow descends vertically to a corner "
        "and then continues horizontally to the right."
    ),
    "chapter9-unit-121-diagram-007": (
        "Small bent path icon: an arrow runs right, bends diagonally downward, "
        "and then continues vertically downward."
    ),
}


# These diagrams need context that is not recoverable from relative arrow
# coordinates alone (for example, named 2-cells, coequalizer roles, or repeated
# primed rows).  Each account is tied to the inventory ID and was authored from
# that row's TeX body together with its immediately surrounding English prose.
SEMANTIC_OVERRIDES = {
    "prelude-unit-007-diagram-006": (
        "Triangle-identity diagram for the functors G:C' to C and F:C to C'. "
        "It compares the composite FG with id_C' by the counit epsilon and "
        "compares id_C with GF by the unit eta along the chain G, F, G."
    ),
    "prelude-unit-007-diagram-007": (
        "Natural-transformation diagram with two parallel copies of G:C' to C "
        "and the identity 2-cell id_G between them."
    ),
    "prelude-unit-007-diagram-008": (
        "Triangle-identity diagram for the functors F:C to C' and G:C' to C. "
        "It compares id_C with GF by the unit eta and compares FG with id_C' "
        "by the counit epsilon along the chain F, G, F."
    ),
    "prelude-unit-007-diagram-009": (
        "Natural-transformation diagram with two parallel copies of F:C to C' "
        "and the identity 2-cell id_F between them."
    ),
    "prelude-unit-007-diagram-011": (
        "Universal-property bijection for the equalizer: Hom(T, Ker(f,g)) is "
        "identified with maps phi:T to X satisfying f phi = g phi; a map psi "
        "is sent to iota composed with psi."
    ),
    "prelude-unit-007-diagram-012": (
        "Universal-property bijection for the coequalizer: Hom(Coker(f,g), T) "
        "is identified with maps phi:Y to T satisfying phi f = phi g; a map "
        "psi is sent to psi composed with the quotient p."
    ),
    "prelude-unit-007-diagram-013": (
        "Product universal-property bijection from Hom(T, product over i of "
        "X_i) to the product over i of Hom(T,X_i), sending psi to the family "
        "of components p_i composed with psi."
    ),
    "prelude-unit-007-diagram-014": (
        "Coproduct universal-property bijection from Hom(coproduct over i of "
        "X_i,T) to the product over i of Hom(X_i,T), sending psi to the family "
        "psi composed with the coproduct inclusions iota_i."
    ),
    "chapter1-unit-011-diagram-001": "Paired functors F:C to C' and G:C' to C, shown by opposing arrows.",
    "chapter1-unit-015-diagram-013": "Paired functors F:C to C' and G:C' to C, shown by opposing arrows.",
    "chapter3-unit-038-d004": (
        "Mapping-cone comparison triangle: Phi maps Cone(f) to Cone(g), Phi' "
        "maps X[1] to Cone(g), beta(f) maps Cone(f) to X[1], and alpha(g) maps "
        "Z to Cone(g). The displayed matrices express alpha(g) Phi plus Phi' "
        "beta(f) as the diagonal map with entries f[1] and g."
    ),
    "chapter3-unit-036-d002": (
        "Bicomplex grid centered at X^(p,q). Horizontal differentials connect "
        "the terms in row p, vertical differentials connect the terms in "
        "column q, and the boundary terms display the corresponding pieces of "
        "the two filtrations F_I X and F_II X."
    ),
    "chapter3-unit-038-d007": (
        "Comparison of long exact cohomology sequences. The upper row is "
        "H^n(Y) to H^n(Cone(f)) to H^n(X[1]) to H^(n+1)(Y); the lower row is "
        "H^n(Y) to H^n(Z) to H^(n+1)(X) to H^(n+1)(Y). Vertical maps are the "
        "identity maps, H^n(Phi), eta^n, and xi^n."
    ),
    "chapter3-unit-038-d008": (
        "Comparison of long exact cohomology sequences. The upper row is "
        "H^n(Z) to H^n(Cone(g)) to H^n(Y[1]) to H^(n+1)(Z); the lower row is "
        "H^n(Z) to H^n(X[1]) to H^(n+1)(Y) to H^(n+1)(Z). Vertical maps are "
        "the identity maps, (eta')^n, H^n(Phi'), and (xi')^n."
    ),
    "chapter3-unit-040-d002": (
        "Two-row morphism of truncated complexes. The top row runs from the "
        "preceding terms through X^(n-2), X^(n-1), Ker(d_X^n), and 0; the "
        "bottom row has the corresponding Y terms. Vertical maps are "
        "h^(n-2), h^(n-1), the induced map on kernels, and zero."
    ),
    "chapter4-unit-059-d001": (
        "Equality characterizing the global dimension of A: the supremum of "
        "injective dimensions, the least n for which Ext in every degree at "
        "least n+1 vanishes, the supremum of projective dimensions, and the "
        "largest degree n with some nonzero Ext^n(X,Y) are all equal. The "
        "infimum of the empty set is taken to be infinity."
    ),
    "chapter4-unit-059-diagram-002": "Paired functors F:A to A' and G:A' to A, shown by opposing arrows.",
    "chapter4-unit-061-diagram-001": "Paired functors F:A to A' and G:A' to A, shown by opposing arrows.",
    "chapter4-unit-062-diagram-002": (
        "Layered cube comparing tensor over R on homotopy categories with its "
        "derived tensor functor on derived categories. Diagonal arrows forget "
        "bimodule structure, vertical arrows are localization functors, and "
        "the rear faces land in K(Ab) and D(Ab)."
    ),
    "chapter5-unit-066-diagram-011": (
        "Oriented triangular cycle on three vertices: the top edge is labeled "
        "minus 1, the descending edge is labeled plus r, and the returning "
        "edge is unlabeled, recording the sign and degree convention."
    ),
    "chapter6-unit-079-d002": (
        "Canonical isomorphism from compact induction c-Ind_H^G(N) to the "
        "H-equivariant functions f:G to N having finite support modulo H. It "
        "sends g_i tensor y to the function supported on H g_i^(-1) with value "
        "h y at h g_i^(-1), and sends f back to the sum of g_i tensor "
        "f(g_i^(-1))."
    ),
    "chapter6-unit-080-d003": (
        "Commutative square of H-invariants. A G-module maps to a G/H-module "
        "by H-invariants and to an H-module by restriction; forgetting the "
        "G/H-action on the upper-right object agrees with taking H-invariants "
        "after restriction along the lower path."
    ),
    "chapter7-unit-091-d001": (
        "Composition in the tensor product dg-category C_1 tensor C_2. The "
        "Koszul braiding first regroups the C_1 and C_2 Hom complexes; "
        "composition in each category then yields Hom_C1(X,Z) tensor "
        "Hom_C2(X',Z')."
    ),
    "chapter7-unit-095-diagram-003": "Paired functors F:C to D and G:D to C, shown by opposing arrows.",
    "chapter7-unit-100-diagram-001": "Paired functors F:C to D and G:D to C, shown by opposing arrows.",
    "chapter7-unit-104-diagram-002": (
        "Free-forgetful adjunction between R-modules and R-algebras: T sends an "
        "R-module to its free R-algebra, and U is the forgetful functor in the "
        "reverse direction."
    ),
    "chapter8-unit-110-diagram-006": (
        "Dold-Kan equivalence between nonnegative chain complexes of abelian "
        "groups and simplicial abelian groups, with Gamma forward and the "
        "normalization functor N backward."
    ),
    "chapter8-unit-111-diagram-001": (
        "Dold-Kan equivalence for an abelian category A: Gamma maps "
        "nonnegative chain complexes in A to simplicial objects in A, and "
        "normalization N maps back."
    ),
    "chapter8-unit-112-diagram-001": (
        "Free-forgetful adjunction between simplicial sets and simplicial "
        "abelian groups: Z(-) is the free abelian-group functor and the reverse "
        "arrow is the forgetful functor."
    ),
    "chapter8-unit-113-d002": (
        "Extension-forgetful adjunction along A to B: tensoring with B over A "
        "maps A-modules to B-modules, and the opposing arrow forgets the "
        "B-module structure back to an A-module."
    ),
    "chapter8-unit-113-d004": (
        "Visible part of the augmented bar diagram for a T-algebra (M,a): "
        "T^3(M) has the three face maps mu_T(M), T mu_M, and T^2(a) to T^2(M); "
        "T^2(M) has face maps mu_M and T(a) to T(M); and T(M) maps to M by a."
    ),
    "chapter8-unit-114-diagram-004": "Paired functors F:A to B and G:B to A, shown by opposing arrows.",
    "chapter8-unit-114-d004": (
        "Scalar-extension adjunction from k-modules to R-modules: R tensor "
        "(-) is the forward functor and restriction of scalars is the "
        "forgetful functor in the reverse direction."
    ),
    "chapter8-unit-119-d002": (
        "Coequalizer presentation of the simplicial horn Lambda^n_k. Two face "
        "maps run from the disjoint union of Delta^(n-2) over pairs i'<j' "
        "excluding k to the disjoint union of Delta^(n-1) over indices "
        "excluding k; their coequalizer maps to Lambda^n_k. The upper and "
        "lower triangles commute by the coface maps d^i and d^j."
    ),
    "chapter8-unit-120-diagram-002": "Paired functors F:C to D and G:D to C, shown by opposing arrows.",
    "chapter8-unit-120-diagram-004": "Paired functors F:C to D and G:D to C, shown by opposing arrows.",
    "chapter8-unit-120-d002": (
        "Adjoint triple for a ring map S to R. Extension of scalars "
        "R tensor_S (-) is left adjoint to restriction from R-modules to "
        "S-modules, and restriction is left adjoint to Hom_S(R,-)."
    ),
    "chapter8-unit-120-d003": (
        "Extension-restriction adjunction for a ring map S to R: tensoring "
        "with R over S maps S-modules to R-modules, and restriction of scalars "
        "maps back."
    ),
    "chapter9-unit-127-d003": (
        "Compatibility diagram for the product on coHom. Canonical coaction "
        "maps send omega''_2(X tensor X') down to the tensor of omega_2(X) "
        "and omega'_2(X'), then to the tensor of the two coHom factors. The "
        "bottom product map and theta_1 tensor identity agree with the direct "
        "canonical map to omega''_1(X tensor X') tensor coHom_B(omega''_1,omega''_2)."
    ),
    "mastery-bridge-001-diagram-chasing-diagram-004": (
        "Commutative three-by-three diagram with exact rows and columns. The "
        "rows are 0 to A' to B' to C' to 0, 0 to A to B to C to 0, and 0 to "
        "A'' to B'' to C'' to 0; vertical maps are alpha, beta, gamma and their "
        "barred counterparts, with zeros closing the outer columns."
    ),
    "mastery-bridge-001-diagram-chasing-diagram-006": (
        "Naturality square for connecting morphisms: delta maps Ker(alpha'') "
        "to Coker(alpha'), the vertical maps pass to Ker(tilde alpha'') and "
        "Coker(tilde alpha'), and tilde delta closes the lower edge."
    ),
    "mastery-bridge-001-diagram-chasing-diagram-007": (
        "Morphism between two short exact sequences 0 to Z to Z to Z/6Z to 0. "
        "Both horizontal middle maps are multiplication by 6 followed by the "
        "quotient pi, and all three vertical maps are multiplication by 4."
    ),
}


WORD_TRANSLATIONS = {
    "dengan konvensi": "with the convention",
    "adjoin kanan": "right adjoint",
    "adjoin kiri": "left adjoint",
    "diidentifikasi dengan": "identified with",
    "diidentifikasi": "identified",
    "diinduksi oleh semua": "induced by all",
    "diinduksi oleh": "induced by",
    "funktor inklusi": "inclusion functor",
    "funktor penyertaan": "inclusion functor",
    "morfisme natural": "natural morphism",
    "morfisme alami": "natural morphism",
    "morfisme diagonal": "diagonal morphism",
    "morfisme kuosien": "quotient morphism",
    "homomorfisme penghubung": "connecting homomorphism",
    "hasil bagi bagian degenerat": "quotient by the degenerate part",
    "hasil bagi part degenerat": "quotient by the degenerate part",
    "pada derajat nol": "in degree zero",
    "di upper": "at the top",
    "di lower": "at the bottom",
    "yang dicari": "sought",
    "seperti di atas, tetapi": "as above, but",
    "seperti": "as",
    "as di upper, tetapi": "as above, but",
    "ekuivalensi": "equivalence",
    "ekuivalens": "equivalence",
    "penyertaan": "inclusion",
    "inklusi": "inclusion",
    "pelupa": "forgetful functor",
    "kuosien": "quotient",
    "langsung": "direct",
    "monoton": "monotone",
    "kanonik": "canonical",
    "dahulu": "first",
    "hingga": "finite",
    "koset": "coset",
    "bernilai": "having value",
    "melalui": "through",
    "proyeksi": "projection",
    "pertukaran": "interchange",
    "semua": "all",
    "alami": "natural",
    "keluarkan": "move",
    "kolom ke": "column",
    "morfisme": "morphism",
    "funktor": "functor",
    "suku": "summand",
    "bebas": "free",
    "jelas": "evident",
    "lupa": "forgetful",
    "lalu": "then",
    "yang": "that",
    "dengan": "with",
    "adalah": "is",
    "untuk": "for",
    "dari": "from",
    "dalam": "in",
    "pada": "at",
    "sebagai": "as",
    "maka": "then",
    "karena": "because",
    "jika": "if",
    "dan": "and",
    "atau": "or",
    "suatu": "a",
    "dapat": "can",
    "akan": "will",
    "kita": "we",
    "ini": "this",
    "tersebut": "that",
    "bukti": "proof",
    "latihan": "exercise",
    "petunjuk": "hint",
    "teorema": "theorem",
    "definisi": "definition",
    "contoh": "example",
    "catatan": "remark",
    "misalkan": "let",
    "sehingga": "so that",
}

# These narrowly missed phrases were present in otherwise structurally valid
# inherited descriptions. Apply them after the preserve/rebuild decision so a
# deterministic replay reproduces the corrected English ledger byte-for-byte
# without changing which of the other 896 descriptions are preserved.
ACCESSIBILITY_PHRASE_FIXES = {
    "pemetaan kontinu": "continuous maps",
    "di three column to right": "three columns to the right",
    "kelasnya": "its class",
    "citranya": "its image",
    "pemetaan": "maps",
    "homotopi": "homotopy",
}


COMMAND_WORDS = {
    "alpha": "alpha",
    "beta": "beta",
    "gamma": "gamma",
    "delta": "delta",
    "epsilon": "epsilon",
    "varepsilon": "epsilon",
    "zeta": "zeta",
    "eta": "eta",
    "theta": "theta",
    "vartheta": "theta",
    "iota": "iota",
    "kappa": "kappa",
    "lambda": "lambda",
    "mu": "mu",
    "nu": "nu",
    "xi": "xi",
    "pi": "pi",
    "rho": "rho",
    "sigma": "sigma",
    "tau": "tau",
    "upsilon": "upsilon",
    "phi": "phi",
    "varphi": "phi",
    "chi": "chi",
    "psi": "psi",
    "omega": "omega",
    "Gamma": "Gamma",
    "Delta": "Delta",
    "Phi": "Phi",
    "Psi": "Psi",
    "Theta": "Theta",
    "Omega": "Omega",
    "identity": "id",
    "sim": "isomorphism",
    "simeq": "equivalence",
    "cong": "isomorphism",
    "to": "to",
    "mapsto": "maps to",
    "leftarrow": "from",
    "rightarrow": "to",
    "rightarrowtail": "inclusion into",
    "twoheadrightarrow": "surjection onto",
    "oplus": " direct sum ",
    "otimes": " tensor ",
    "dotimes": " tensor ",
    "times": " times ",
    "cdot": " dot ",
    "circ": " composed with ",
    "in": " in ",
    "ni": " contains ",
    "geq": " greater than or equal to ",
    "leq": " less than or equal to ",
    "neq": " not equal to ",
    "infty": "infinity",
    "ldots": "...",
    "cdots": "...",
    "dots": "...",
    "bullet": "point",
    "Box": "marked square",
    "opp": "op",
    "Z": "Z",
    "Bbbk": "k",
    "munit": "unit object",
    "Hom": "Hom",
    "End": "End",
    "Ext": "Ext",
    "Ker": "Ker",
    "Coker": "Coker",
    "Image": "Image",
    "Coim": "Coimage",
    "Cone": "Cone",
    "Cyl": "Cylinder",
    "Hm": "H",
    "coHom": "coHom",
    "Res": "Res",
    "Ind": "Ind",
    "iInd": "compact Ind",
    "tot": "Tot",
    "prod": "product",
    "coprod": "coproduct",
    "bigoplus": "direct sum",
    "varinjlim": "direct limit",
    "varprojlim": "inverse limit",
    "bigsqcup": "disjoint union",
    "partial": "boundary",
    "overline": "bar ",
    "widetilde": "tilde ",
    "widehat": "hat ",
    "hat": "hat ",
    "tilde": "tilde ",
    "dtimes": "fiber product over ",
}


TRANSPARENT_COMMANDS = {
    "Bbb",
    "mathbf",
    "mathbb",
    "mathcal",
    "mathbf",
    "mathrm",
    "mathsf",
    "mathfrak",
    "mathtt",
    "operatorname",
    "text",
    "textrm",
    "textsf",
    "cate",
    "dcate",
    "cated",
    "underline",
    "underbracket",
    "left",
    "right",
    "displaystyle",
    "scriptstyle",
    "footnotesize",
    "bigl",
    "bigr",
    "Bigl",
    "Bigr",
}


def translate_words(value: str) -> str:
    """Remove Indonesian residue, including words embedded in math subscripts."""
    for source, target in sorted(WORD_TRANSLATIONS.items(), key=lambda item: -len(item[0])):
        value = re.sub(
            rf"(?i)(?<![A-Za-z]){re.escape(source)}(?![A-Za-z])",
            target,
            value,
        )
    return value


def has_known_indonesian(value: str) -> bool:
    return any(
        re.search(
            rf"(?i)(?<![A-Za-z]){re.escape(term)}(?![A-Za-z])",
            value,
        )
        for term in WORD_TRANSLATIONS
    )


def plain_math(value: str) -> str:
    """Turn a short TeX label into readable, brace-free inline notation."""
    value = value.strip().strip(".,;")
    while len(value) >= 2 and value[0] == "{" and value[-1] == "}":
        value = value[1:-1].strip()
    value = value.replace("\\,", " ").replace("\\;", " ").replace("\\!", "")
    value = value.replace("\\ ", " ").replace("~", " ").replace("$", "")
    value = re.sub(r"\\begin\{(?:array|smallmatrix|matrix|gathered|aligned)\}(?:\[[^]]*\])?", "", value)
    value = re.sub(r"\\end\{(?:array|smallmatrix|matrix|gathered|aligned)\}", "", value)
    value = value.replace("\\\\", "; ").replace("\\&", " and ").replace("&", " and ")
    value = re.sub(r"\\dfrac\s*\{([^{}]*)\}\s*\{([^{}]*)\}", r"(\1)/(\2)", value)
    value = re.sub(r"\\frac\s*\{([^{}]*)\}\s*\{([^{}]*)\}", r"(\1)/(\2)", value)
    for command in TRANSPARENT_COMMANDS:
        value = re.sub(rf"\\{command}\b", "", value)
    for command, word in COMMAND_WORDS.items():
        value = re.sub(rf"\\{re.escape(command)}(?![A-Za-z])", word, value)
    # Unknown control words are still more legible as names than as raw TeX.
    value = re.sub(r"\\([A-Za-z]+)\*?", lambda match: match.group(1), value)
    value = value.replace("\\{", "{").replace("\\}", "}")
    value = value.replace("{", "").replace("}", "")
    value = value.replace("^", "^").replace("_", "_")
    value = value.replace("\\", "")
    value = translate_words(value)
    value = re.sub(r"\s+", " ", value)
    value = re.sub(r"\s+([,.;:)])", r"\1", value)
    value = re.sub(r"([(])\s+", r"\1", value)
    # A trailing apostrophe commonly distinguishes a primed object (C' from C).
    value = value.strip(" \t\r\n.,;:\"")
    return value


def strip_leading_options(body: str) -> str:
    body = body.lstrip()
    if not body.startswith("["):
        return body
    depth = 0
    for index, char in enumerate(body):
        if char == "[":
            depth += 1
        elif char == "]":
            depth -= 1
            if depth == 0:
                return body[index + 1 :].lstrip()
    return body


def split_grid(body: str) -> list[list[str]]:
    """Split a tikzcd body at top-level row and column separators."""
    body = strip_leading_options(body)
    rows: list[list[str]] = [[]]
    cell: list[str] = []
    brace_depth = 0
    environments: list[str] = []
    index = 0
    while index < len(body):
        begin = re.match(r"\\begin\{([^{}]+)\}", body[index:])
        end = re.match(r"\\end\{([^{}]+)\}", body[index:])
        if begin:
            token = begin.group(0)
            environments.append(begin.group(1))
            cell.append(token)
            index += len(token)
            continue
        if end:
            token = end.group(0)
            if environments and environments[-1] == end.group(1):
                environments.pop()
            cell.append(token)
            index += len(token)
            continue
        char = body[index]
        escaped = index > 0 and body[index - 1] == "\\"
        if char == "{" and not escaped:
            brace_depth += 1
        elif char == "}" and not escaped and brace_depth:
            brace_depth -= 1
        if not environments and brace_depth == 0 and body[index : index + 2] == "\\\\":
            rows[-1].append("".join(cell))
            rows.append([])
            cell = []
            index += 2
            continue
        if not environments and brace_depth == 0 and char == "&" and not escaped:
            rows[-1].append("".join(cell))
            cell = []
            index += 1
            continue
        cell.append(char)
        index += 1
    rows[-1].append("".join(cell))
    return rows


def bracket_content(value: str, start: int) -> tuple[str, int]:
    depth = 0
    quote = False
    escaped = False
    for index in range(start, len(value)):
        char = value[index]
        if escaped:
            escaped = False
            continue
        if char == "\\":
            escaped = True
            continue
        if char == '"':
            quote = not quote
        elif not quote and char == "[":
            depth += 1
        elif not quote and char == "]":
            depth -= 1
            if depth == 0:
                return value[start + 1 : index], index + 1
    return value[start + 1 :], len(value)


def arrow_commands(cell: str) -> tuple[str, list[str]]:
    matches = list(re.finditer(r"\\arrow\b", cell))
    if not matches:
        return cell, []
    node = cell[: matches[0].start()]
    options = []
    for match in matches:
        cursor = match.end()
        while cursor < len(cell) and cell[cursor].isspace():
            cursor += 1
        if cursor < len(cell) and cell[cursor] == "[":
            option, _ = bracket_content(cell, cursor)
            options.append(option)
        else:
            options.append("r")
    return node, options


def quoted_labels(options: str) -> list[str]:
    labels = []
    index = 0
    while index < len(options):
        if options[index] != '"':
            index += 1
            continue
        cursor = index + 1
        token = []
        while cursor < len(options):
            if options[cursor] == '"' and options[cursor - 1] != "\\":
                break
            token.append(options[cursor])
            cursor += 1
        label = plain_math("".join(token))
        if label:
            labels.append(label)
        index = cursor + 1
    return labels


def shorten(value: str, limit: int = 110) -> str:
    value = re.sub(r"\s+", " ", value).strip()
    if len(value) <= limit:
        return value
    for separator in (";", ",", ")", " "):
        cut = value.rfind(separator, 0, limit)
        if cut >= max(28, limit // 2):
            return value[: cut + (1 if separator == ")" else 0)].rstrip() + " and related terms"
    return value[:limit].rstrip() + " and related terms"


def direction(options: str) -> str | None:
    # Direction tokens occur as comma-separated bare u/d/l/r strings.
    for token in (part.strip() for part in options.split(",")):
        if re.fullmatch(r"[udlr]+", token):
            return token
    return None


def named_endpoint(options: str, name: str) -> str | None:
    match = re.search(rf"(?:^|,)\s*{name}\s*=\s*([^,\]]+)", options)
    return plain_math(match.group(1)) if match else None


def target_position(row: int, column: int, route: str) -> tuple[int, int]:
    return (
        row + route.count("d") - route.count("u"),
        column + route.count("r") - route.count("l"),
    )


def object_at(objects: dict[tuple[int, int], str], position: tuple[int, int]) -> str:
    value = objects.get(position, "")
    if value:
        return value
    return f"the position at row {position[0] + 1}, column {position[1] + 1}"


def relation_text(source: str, target: str, label: str, options: str) -> str:
    if "Rightarrow" in options:
        relation = f"a 2-cell from {source} to {target}"
    elif "rightarrowtail" in options or "hookrightarrow" in options:
        relation = f"{source} includes into {target}"
    elif "twoheadrightarrow" in options:
        relation = f"{source} surjects onto {target}"
    elif "leftarrow" in options:
        relation = f"{target} maps to {source}"
    elif "mapsto" in options:
        relation = f"{source} maps to {target}"
    else:
        relation = f"{source} maps to {target}"
    if label:
        relation += f", labeled {label}"
    if "dashed" in options:
        relation = "a dashed " + relation
    return relation


def describe_tikzcd(body: str) -> str:
    grid = split_grid(body)
    objects: dict[tuple[int, int], str] = {}
    commands: dict[tuple[int, int], list[str]] = {}
    for row_index, row in enumerate(grid):
        for column_index, cell in enumerate(row):
            node, arrows = arrow_commands(cell)
            name = shorten(plain_math(node))
            if name:
                objects[(row_index, column_index)] = name
            commands[(row_index, column_index)] = arrows

    relations = []
    for position, arrows in commands.items():
        source = object_at(objects, position)
        for options in arrows:
            labels = quoted_labels(options)
            label = labels[0] if labels else ""
            route = direction(options)
            source_name = named_endpoint(options, "from")
            target_name = named_endpoint(options, "to")
            if source_name or target_name:
                left = source_name or source
                right = target_name or source
                relation = relation_text(left, right, label, options)
            elif route:
                target = object_at(objects, target_position(*position, route))
                relation = relation_text(source, target, label, options)
            else:
                relation = f"an arrow at {source}"
                if label:
                    relation += f", labeled {label}"
            relations.append(shorten(relation, 180))

    # Preserve source order while avoiding repetitions from parallel unlabeled arrows.
    object_names = list(dict.fromkeys(objects.values()))
    relation_names = list(dict.fromkeys(relations))
    if "Rightarrow" in body:
        kind = "Natural-transformation diagram"
    elif re.search(r"(?:^|[&\\])\s*0\s*\\arrow", body):
        kind = "Exact-sequence diagram"
    else:
        kind = "Commutative diagram"

    parts = []
    if object_names:
        shown = object_names[:12]
        objects_clause = ", ".join(shown)
        if len(object_names) > len(shown):
            objects_clause += f", and {len(object_names) - len(shown)} further displayed objects"
        parts.append(f"{kind} with objects {objects_clause}.")
    else:
        parts.append(f"{kind} describing the displayed morphisms.")
    if relation_names:
        shown_relations = relation_names[:14]
        relations_clause = "; ".join(shown_relations)
        if len(relation_names) > len(shown_relations):
            relations_clause += (
                f"; {len(relation_names) - len(shown_relations)} additional arrows complete the grid"
            )
        parts.append("Arrows: " + relations_clause + ".")
    else:
        parts.append("The displayed positions encode the indicated comparison.")
    description = translate_words(" ".join(parts))
    description = HAN.sub("the indicated symbol", description)
    description = re.sub(r"\s+", " ", description).strip()
    return description


def valid_description(value: str) -> bool:
    value = value.strip()
    return (
        len(value) >= 15
        and braces_balanced(value)
        and not HAN.search(value)
        and not INDONESIAN.search(value)
        and not has_known_indonesian(value)
        and not PLACEHOLDER.search(value)
    )


def main() -> None:
    inventory = [
        json.loads(line)
        for line in INVENTORY.read_text(encoding="utf-8-sig").splitlines()
        if line.strip()
    ]
    if len(inventory) != 907:
        raise SystemExit(f"inventory row count is {len(inventory)}, expected 907")

    rows = []
    preserved = 0
    rebuilt = 0
    authored = 0
    for inventory_line, record in enumerate(inventory, 1):
        inherited = record["description_en"].strip()
        if inherited and valid_description(inherited):
            description = inherited
            preserved += 1
        elif record["diagram_id"] in SEMANTIC_OVERRIDES:
            description = SEMANTIC_OVERRIDES[record["diagram_id"]]
            if inherited:
                rebuilt += 1
            else:
                authored += 1
        elif record["diagram_id"] in PICTURE_DESCRIPTIONS:
            description = PICTURE_DESCRIPTIONS[record["diagram_id"]]
            authored += 1
        else:
            description = describe_tikzcd(record["tex_body"])
            if inherited:
                rebuilt += 1
            else:
                authored += 1
        for source, target in sorted(
            ACCESSIBILITY_PHRASE_FIXES.items(), key=lambda item: -len(item[0])
        ):
            description = re.sub(
                rf"(?i)(?<![A-Za-z]){re.escape(source)}(?![A-Za-z])",
                target,
                description,
            )
        if not valid_description(description):
            raise SystemExit(
                f"generated invalid description for {record['diagram_id']}: {description!r}"
            )
        provenance = (
            f"qa/DIAGRAM_SOURCE_INVENTORY.jsonl:{inventory_line}; "
            f"source/en/{record['unit_filename']}:diagram {record['actual_order']}; "
            f"{record['environment']}; {record['source_relationship']}"
        )
        rows.append({
            "diagram_id": record["diagram_id"],
            "unit_filename": record["unit_filename"],
            "local_order": str(record["actual_order"]),
            "alt_text_en": description,
            "provenance": provenance,
        })

    ids = [row["diagram_id"] for row in rows]
    unit_orders = [(row["unit_filename"], row["local_order"]) for row in rows]
    if len(ids) != len(set(ids)):
        raise SystemExit("duplicate diagram IDs")
    if len(unit_orders) != len(set(unit_orders)):
        raise SystemExit("duplicate unit/local-order pairs")

    with LEDGER.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=["diagram_id", "unit_filename", "local_order", "alt_text_en", "provenance"],
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)
    print(json.dumps({
        "rows": len(rows),
        "valid_inherited_preserved": preserved,
        "invalid_inherited_rebuilt": rebuilt,
        "missing_authored": authored,
    }))


if __name__ == "__main__":
    main()
