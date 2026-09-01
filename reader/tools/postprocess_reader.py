#!/usr/bin/env python3
"""Apply reader semantics and the frozen English diagram-alt ledger."""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import defaultdict
from pathlib import Path

from lxml import etree, html


UNIT_RE = re.compile(
    r"\\input\{((?:prelude-unit-\d{3}|chapter\d+-unit-\d{3}|"
    r"appendix\d+-unit-\d{3}|mastery-bridge-[^}]+))\}"
)


def text_label(section: etree._Element, filename: str) -> str:
    heading = section.xpath(".//h1 | .//h2 | .//h3 | .//h4 | .//h5 | .//h6")
    if heading:
        value = " ".join(heading[0].itertext()).strip()
        if value:
            return value
    return filename.removesuffix(".tex").replace("-", " ")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--html", required=True, type=Path)
    parser.add_argument("--master", required=True, type=Path)
    parser.add_argument("--ledger", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args()

    expected = [f"{stem}.tex" for stem in UNIT_RE.findall(args.master.read_text(encoding="utf-8"))]
    with args.ledger.open(encoding="utf-8-sig", newline="") as stream:
        ledger_rows = list(csv.DictReader(stream))
    ledger: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in ledger_rows:
        ledger[row["unit_filename"]].append(row)
    for rows in ledger.values():
        rows.sort(key=lambda row: int(row["local_order"]))

    document = html.parse(str(args.html), parser=html.HTMLParser(encoding="utf-8"))
    root = document.getroot()
    root.set("lang", "en")
    title = root.find(".//title")
    if title is None:
        head = root.find("head")
        title = etree.SubElement(head, "title")
    title.text = "Methods of Algebra, Volume 2: Linear Algebra — Independent English Edition"

    sections = root.xpath("//section[@data-unit-file]")
    by_file = {section.get("data-unit-file"): section for section in sections}
    applied: list[str] = []
    mismatches: list[dict[str, object]] = []
    for filename in expected:
        section = by_file.get(filename)
        if section is None:
            mismatches.append({"unit": filename, "reason": "unit-section-missing"})
            continue
        label = text_label(section, filename)
        section.set("aria-label", label)
        images = section.xpath(".//img")
        rows = ledger.get(filename, [])
        if len(images) != len(rows):
            mismatches.append(
                {"unit": filename, "reason": "diagram-count", "html": len(images), "ledger": len(rows)}
            )
            continue
        for image, row in zip(images, rows, strict=True):
            image.set("alt", row["alt_text_en"].strip())
            image.set("data-diagram-id", row["diagram_id"])
            image.set("loading", "lazy")
            image.set("decoding", "async")
            classes = set((image.get("class") or "").split())
            classes.add("reader-diagram-image")
            image.set("class", " ".join(sorted(classes)))
            applied.append(row["diagram_id"])

    main_node = root.xpath("//main[@id='main-content']")
    if main_node:
        old_nav = root.xpath("//nav[@class='reader-unit-index']")
        for node in old_nav:
            node.getparent().remove(node)
        nav = html.fragment_fromstring(
            '<nav class="reader-unit-index" aria-label="Unit navigation">'
            '<details><summary>Direct navigation to 146 units and 2 mastery bridges</summary><ol></ol></details></nav>'
        )
        ordered = nav.xpath(".//ol")[0]
        for filename in expected:
            section = by_file.get(filename)
            if section is None:
                continue
            item = etree.SubElement(ordered, "li")
            link = etree.SubElement(item, "a", href=f"#{section.get('id')}")
            link.text = text_label(section, filename)
        cover = main_node[0].xpath("./section[contains(concat(' ', normalize-space(@class), ' '), ' reader-cover ')]")
        if cover:
            cover[0].addnext(nav)
        else:
            main_node[0].insert(0, nav)

    args.html.write_bytes(
        html.tostring(root, encoding="utf-8", method="html", doctype="<!DOCTYPE html>")
    )
    report = {
        "expected_units_and_bridges": len(expected),
        "unit_sections_found": len(sections),
        "ledger_diagrams": len(ledger_rows),
        "diagram_alt_text_applied": len(applied),
        "mismatches": mismatches,
    }
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
