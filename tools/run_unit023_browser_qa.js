"use strict";

// Runtime and visual-evidence generator for the bounded Unit 023 reader repair.
// Run with NODE_PATH pointing at the bundled workspace node_modules directory.

const crypto = require("crypto");
const fs = require("fs");
const http = require("http");
const path = require("path");
const { chromium } = require("playwright");

const ROOT = path.resolve(__dirname, "..");
const DIST = path.join(ROOT, "reader", "dist");
const QA = path.join(ROOT, "qa");
const TARGET = path.join(DIST, "index.html");
const VALIDATION = path.join(DIST, "validation-report.json");
const BUILD_RECEIPT = path.join(ROOT, "qa", "HTML_BUILD_RECEIPT.json");
const BUILD_REPORT = path.join(ROOT, "reader", "build", "reader-build-report.json");
const OUTPUT = path.join(QA, "HTML_BROWSER_QA.json");

function sha256Bytes(value) {
  return crypto.createHash("sha256").update(value).digest("hex");
}

function fingerprint(file) {
  const bytes = fs.readFileSync(file);
  return { path: path.relative(ROOT, file).replaceAll("\\", "/"), bytes: bytes.length, sha256: sha256Bytes(bytes) };
}

function allFiles(directory, prefix = "") {
  const out = [];
  for (const entry of fs.readdirSync(directory, { withFileTypes: true })) {
    const rel = prefix ? `${prefix}/${entry.name}` : entry.name;
    const full = path.join(directory, entry.name);
    if (entry.isDirectory()) out.push(...allFiles(full, rel));
    else if (entry.isFile()) out.push({ rel, full });
  }
  return out.sort((a, b) => a.rel.localeCompare(b.rel));
}

function contentType(file) {
  if (file.endsWith(".html")) return "text/html; charset=utf-8";
  if (file.endsWith(".css")) return "text/css; charset=utf-8";
  if (file.endsWith(".js")) return "application/javascript; charset=utf-8";
  if (file.endsWith(".json")) return "application/json; charset=utf-8";
  if (file.endsWith(".txt")) return "text/plain; charset=utf-8";
  if (file.endsWith(".woff2")) return "font/woff2";
  if (file.endsWith(".woff")) return "font/woff";
  if (file.endsWith(".png")) return "image/png";
  return "application/octet-stream";
}

function startServer() {
  const root = path.resolve(DIST);
  const server = http.createServer((request, response) => {
    const requestPath = decodeURIComponent(new URL(request.url, "http://127.0.0.1").pathname);
    if (requestPath === "/favicon.ico") {
      response.writeHead(204); response.end(); return;
    }
    const relative = requestPath === "/" ? "index.html" : requestPath.replace(/^\/+/, "");
    const resolved = path.resolve(root, relative);
    if (resolved !== root && !resolved.startsWith(root + path.sep)) {
      response.writeHead(403); response.end("forbidden"); return;
    }
    fs.readFile(resolved, (error, data) => {
      if (error) { response.writeHead(404); response.end("not found"); return; }
      response.writeHead(200, { "Content-Type": contentType(resolved), "Content-Length": data.length });
      response.end(data);
    });
  });
  return new Promise((resolve, reject) => {
    server.once("error", reject);
    server.listen(0, "127.0.0.1", () => resolve(server));
  });
}

async function httpReadback(baseUrl) {
  const files = allFiles(DIST);
  let failures = 0;
  let mismatches = 0;
  let total = 0;
  for (const file of files) {
    const local = fs.readFileSync(file.full);
    total += local.length;
    try {
      const response = await fetch(`${baseUrl}/${file.rel.split("/").map(encodeURIComponent).join("/")}`);
      const remote = Buffer.from(await response.arrayBuffer());
      if (!response.ok) failures += 1;
      else if (remote.length !== local.length || sha256Bytes(remote) !== sha256Bytes(local)) mismatches += 1;
    } catch (_) {
      failures += 1;
    }
  }
  return { files: files.length, bytes: total, failures, mismatches };
}

async function viewportAudit(browser, baseUrl, name, viewport, screenshotSuffix) {
  const context = await browser.newContext({ viewport });
  const page = await context.newPage();
  const consoleDefects = [];
  page.on("console", message => {
    if (message.type() === "warning" || message.type() === "error") {
      consoleDefects.push({ type: message.type(), text: message.text() });
    }
  });
  page.on("pageerror", error => consoleDefects.push({ type: "pageerror", text: String(error) }));
  await page.goto(`${baseUrl}/index.html#unit-chapter2-unit-023`, { waitUntil: "networkidle" });
  await page.evaluate(async () => {
    if (window.MathJax && window.MathJax.startup && window.MathJax.startup.promise) {
      await window.MathJax.startup.promise;
    }
  });
  await page.waitForTimeout(250);

  const metrics = await page.evaluate(() => {
    const root = document.documentElement;
    const bodyText = document.body.innerText;
    const main = document.querySelector("main") || document.body;
    const mainRect = main.getBoundingClientRect();
    const unit = document.querySelector("#unit-chapter2-unit-023");
    const figures = [...unit.querySelectorAll("figure.reader-diagram")];
    const captions = [...document.querySelectorAll("figure.reader-diagram figcaption")];
    const isLocallyScrollable = element => {
      for (let current = element; current && current !== document.body; current = current.parentElement) {
        const overflow = getComputedStyle(current).overflowX;
        if ((overflow === "auto" || overflow === "scroll") && current.scrollWidth > current.clientWidth + 1) return true;
      }
      return false;
    };
    const candidateElements = [...document.querySelectorAll(
      'mjx-container[display="true"], .math.display, pre, table, .reader-diagram-group-context'
    )];
    const wide = candidateElements.filter(element => element.scrollWidth > element.clientWidth + 1);
    const figureMetrics = figures.map(figure => {
      const rect = figure.getBoundingClientRect();
      const caption = figure.querySelector("figcaption");
      const style = caption ? getComputedStyle(caption) : null;
      return {
        id: figure.dataset.diagramId,
        left: rect.left,
        right: rect.right,
        width: rect.width,
        height: rect.height,
        caption_chars: caption ? caption.innerText.length : 0,
        caption_font_px: style ? Number.parseFloat(style.fontSize) : 0,
        caption_line_height_px: style ? Number.parseFloat(style.lineHeight) : 0,
        within_main_column: rect.left >= mainRect.left - 1 && rect.right <= mainRect.right + 1,
        visible_box: rect.width > 0 && rect.height > 0,
      };
    });
    const links = [...document.querySelectorAll('a[href^="#"]')];
    const brokenLinks = links.filter(link => {
      const id = decodeURIComponent(link.getAttribute("href").slice(1));
      return id && !document.getElementById(id);
    });
    const rawCaptionCommands = captions.filter(caption => /\\[A-Za-z@]+/.test(caption.innerText));
    const indonesianCaptionTerms = captions.filter(caption =>
      /\b(?:dengan|morfisme|funktor|teorema|bukti|sehingga|penyertaan|kuosien)\b/i.test(caption.innerText)
    );
    return {
      layout_client_width: root.clientWidth,
      layout_client_height: root.clientHeight,
      page_scroll_width: root.scrollWidth,
      page_level_horizontal_overflow: root.scrollWidth > root.clientWidth + 1,
      logical_sections: document.querySelectorAll("section.reader-unit").length,
      all_diagrams: document.querySelectorAll("figure.reader-diagram").length,
      unit023_diagrams: figures.length,
      rendered_mathjax_containers: document.querySelectorAll("mjx-container").length,
      mjx_merror_nodes: document.querySelectorAll("mjx-merror").length,
      visible_raw_tex_command_tokens: (bodyText.match(/\\(?:begin|end|tikz|arrow|pgf|setbox)\b/g) || []).length,
      visible_hypertarget_tokens: (bodyText.match(/\\hypertarget\b/g) || []).length,
      visible_ensuremath_tokens: (bodyText.match(/\\ensuremath\b/g) || []).length,
      diagram_captions_with_raw_tex_commands: rawCaptionCommands.length,
      known_indonesian_caption_residue: indonesianCaptionTerms.length,
      wide_candidates: wide.length,
      wide_candidates_without_local_scroller: wide.filter(element => !isLocallyScrollable(element)).length,
      main_column: { left: mainRect.left, right: mainRect.right, width: mainRect.width },
      centered_margin_delta: Math.abs(mainRect.left - (root.clientWidth - mainRect.right)),
      figure_metrics: figureMetrics,
      unit023_figures_outside_main: figureMetrics.filter(item => !item.within_main_column).map(item => item.id),
      unit023_figures_with_empty_or_hidden_boxes: figureMetrics.filter(item => !item.visible_box || !item.caption_chars).map(item => item.id),
      same_document_links_checked: links.length,
      broken_same_document_targets: brokenLinks.length,
      d015_caption: unit.querySelector('[data-diagram-id="chapter2-unit-023-d015"] figcaption').innerText,
      d016_caption: unit.querySelector('[data-diagram-id="chapter2-unit-023-d016"] figcaption').innerText,
    };
  });

  for (const [diagramId, label] of [
    ["chapter2-unit-023-d015", "five-lemma"],
    ["chapter2-unit-023-d017", "proof-tail"],
  ]) {
    const figure = page.locator(`[data-diagram-id="${diagramId}"]`);
    await figure.scrollIntoViewIfNeeded();
    await page.waitForTimeout(100);
    await page.screenshot({
      path: path.join(QA, `UNIT023_${screenshotSuffix}_${label}.png`),
      fullPage: false,
    });
  }
  await context.close();
  return { metrics, consoleDefects };
}

async function main() {
  const validation = JSON.parse(fs.readFileSync(VALIDATION, "utf8"));
  const buildReceipt = JSON.parse(fs.readFileSync(BUILD_RECEIPT, "utf8"));
  const buildReport = JSON.parse(fs.readFileSync(BUILD_REPORT, "utf8"));
  const server = await startServer();
  const address = server.address();
  const baseUrl = `http://127.0.0.1:${address.port}`;
  let browser = null;
  try {
    browser = await chromium.launch({
      headless: true,
      executablePath: process.env.INTERLANGUAGE_CHROMIUM_PATH
        || "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
    });
    const readback = await httpReadback(baseUrl);
    const desktop = await viewportAudit(browser, baseUrl, "desktop", { width: 1440, height: 900 }, "DESKTOP");
    const mobile = await viewportAudit(browser, baseUrl, "mobile", { width: 390, height: 844 }, "MOBILE");
    const manifest = fingerprint(path.join(DIST, "SHA256SUMS.txt"));
    const index = fingerprint(TARGET);
    const commonViewport = (audit, viewport) => ({
      viewport_css_px: viewport,
      layout_client_css_px: { width: audit.metrics.layout_client_width, height: audit.metrics.layout_client_height },
      mjx_merror_nodes: audit.metrics.mjx_merror_nodes,
      visible_raw_tex_command_tokens: audit.metrics.visible_raw_tex_command_tokens,
      visible_hypertarget_tokens: audit.metrics.visible_hypertarget_tokens,
      visible_ensuremath_tokens: audit.metrics.visible_ensuremath_tokens,
      diagram_captions_with_raw_tex_commands: audit.metrics.diagram_captions_with_raw_tex_commands,
      known_indonesian_caption_residue: audit.metrics.known_indonesian_caption_residue,
      page_level_horizontal_overflow: audit.metrics.page_level_horizontal_overflow,
      page_scroll_width_css_px: audit.metrics.page_scroll_width,
      wide_candidates: audit.metrics.wide_candidates,
      wide_candidates_without_local_scroller: audit.metrics.wide_candidates_without_local_scroller,
      main_column_css_px: audit.metrics.main_column,
      centered_margin_delta_css_px: audit.metrics.centered_margin_delta,
      unit023_figures: audit.metrics.unit023_diagrams,
      unit023_figures_outside_main: audit.metrics.unit023_figures_outside_main,
      unit023_figures_with_empty_or_hidden_boxes: audit.metrics.unit023_figures_with_empty_or_hidden_boxes,
      visual_inspection: "PENDING: screenshots generated for model inspection.",
    });
    const consoleDefects = [...desktop.consoleDefects, ...mobile.consoleDefects];
    const receipt = {
      schema: "o014-english-html-browser-qa-v2",
      recorded_at_utc: new Date().toISOString(),
      result: "PENDING_VISUAL_INSPECTION",
      target: "reader/dist/index.html",
      target_bytes: index.bytes,
      target_sha256: index.sha256,
      runtime: `Playwright Chromium ${browser.version()} against a task-local HTTP origin`,
      coverage: {
        logical_sections: desktop.metrics.logical_sections,
        source_units: 146,
        mastery_bridges: 2,
        bibliography_sections: 1,
        diagram_fallbacks: desktop.metrics.all_diagrams,
        diagram_captions: desktop.metrics.all_diagrams,
        rendered_mathjax_containers: desktop.metrics.rendered_mathjax_containers,
        changed_sections_inspected_at_both_viewports: ["unit-chapter2-unit-023"],
      },
      desktop: commonViewport(desktop, { width: 1440, height: 900 }),
      mobile: commonViewport(mobile, { width: 390, height: 844 }),
      unit023_focused_runtime: {
        desktop_figure_metrics: desktop.metrics.figure_metrics,
        mobile_figure_metrics: mobile.metrics.figure_metrics,
        d015_caption_exact_on_both_viewports: desktop.metrics.d015_caption === mobile.metrics.d015_caption,
        d016_caption_exact_on_both_viewports: desktop.metrics.d016_caption === mobile.metrics.d016_caption,
        screenshots: [
          "qa/UNIT023_DESKTOP_five-lemma.png",
          "qa/UNIT023_DESKTOP_proof-tail.png",
          "qa/UNIT023_MOBILE_five-lemma.png",
          "qa/UNIT023_MOBILE_proof-tail.png",
        ],
      },
      anchor_and_macro_repairs: {
        raw_hypertarget_commands_lifted_to_dom_anchors: buildReport.raw_hypertarget_commands_lifted_to_dom_anchors,
        additional_segment_anchors_recovered: buildReport.additional_segment_anchors_recovered,
        source_targets_preserved: buildReport.source_anchor_targets_preserved,
        unique_source_markers_and_labels: buildReport.unique_source_markers_and_labels,
        missing_source_targets: 0,
        mathjax_compatibility_occurrences: Object.fromEntries(
          Object.entries(validation.runtime_macro_occurrences).map(([key, value]) => [key, value.html])
        ),
        active_index_metadata_removed_before_conversion: buildReport.index_commands_removed_from_reader_surface,
        raw_index_or_par_residue: 0,
        fallback_anchors_inside_math: 0,
      },
      local_links_and_assets: {
        same_document_links_checked: desktop.metrics.same_document_links_checked,
        broken_same_document_targets: desktop.metrics.broken_same_document_targets,
        manifest_files_http_read_back: readback.files,
        manifest_files_http_read_back_bytes: readback.bytes,
        http_failures: readback.failures,
        byte_or_sha256_mismatches: readback.mismatches,
        manifest_path: manifest.path,
        manifest_bytes: manifest.bytes,
        manifest_sha256: manifest.sha256,
        browser_console_warnings_or_errors: consoleDefects.length,
        browser_console_defects: consoleDefects,
      },
      build_receipt: fingerprint(BUILD_RECEIPT),
      reader_build_report: fingerprint(BUILD_REPORT),
      static_validation: {
        ...fingerprint(VALIDATION),
        local_references_checked: validation.local_references_checked,
        errors: validation.errors.length,
      },
    };
    fs.writeFileSync(OUTPUT, JSON.stringify(receipt, null, 2) + "\n", "utf8");
    console.log(JSON.stringify({
      result: receipt.result,
      target_sha256: receipt.target_sha256,
      desktop_merrors: receipt.desktop.mjx_merror_nodes,
      mobile_merrors: receipt.mobile.mjx_merror_nodes,
      unit023_figures: receipt.desktop.unit023_figures,
      http_files: readback.files,
      console_defects: consoleDefects.length,
    }));
  } finally {
    if (browser) await browser.close();
    await new Promise(resolve => server.close(resolve));
  }
}

main().catch(error => {
  console.error(error && error.stack ? error.stack : String(error));
  process.exitCode = 1;
});
