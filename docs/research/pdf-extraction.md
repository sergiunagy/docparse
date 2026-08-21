# Research: table/layout-faithful PDF extraction without licensed tooling

Ticket: `sergiunagy/docparse#3`. Question: for Finanzamt-style documents where the
value lives in tables (numbers, deadlines), what extraction approach best preserves
tabular/layout structure without licensed PDF tooling, while staying offline-capable
(to honour the hard local-swap requirement in `docs/adr/0001-ai-provider-adapter.md`)
and emitting a per-extraction **Confidence** signal so low-confidence regions can drive
the notify + manual fill-in loop defined in `CONTEXT.md`?

This note investigates three families against primary sources: (a) direct text+layout
libraries, (b) rasterise-then-OCR (the approach the user has used before to sidestep
formatting/licensing issues), and (c) cloud document-AI. Each is scored on table
fidelity, licensing, cost, offline/local feasibility, and Confidence emission.

## What "Confidence" must be here

`CONTEXT.md` defines Confidence as a per-Extraction judgement of reliability: when an
Extraction fails a plausibility check the user is notified and offered an optional manual
fill-in for the affected region ("type in table XX, OCR could not read it"). So the
signal must be:

- **Regional**, not just a single document-level number. The fill-in is offered per
  affected region (a table, a row, or a Key Information field), so Confidence has to be
  attributable to a region.
- **Normalisable to a threshold**. A number we can compare against a cutoff to decide
  notify-or-not.
- **Available offline**, because the whole pipeline must be swappable to local per the
  ADR, and a Confidence signal that only exists in a cloud response would break when the
  local adapter is installed.

Two independent ingredients feed it: an **intrinsic** signal the extractor itself emits
(per-word / per-cell probability), and an **extrinsic plausibility** signal we compute
(does the amount parse, does the row have the expected number of cells, do line items
sum to a total, does a date match a German/Romanian date format). The families differ
mostly in whether they hand us the intrinsic half for free.

## (a) Direct text + layout libraries

### pdfplumber

- **License: MIT** (permissive, commercial-safe), built on `pdfminer.six` (also MIT).
  Source: <https://github.com/jsvine/pdfplumber> ("License: MIT License").
- **Table fidelity**: strong for *digitally born, ruled* tables. `page.extract_tables(table_settings)`
  returns `table -> row -> cell`; `find_tables()` exposes `.cells`, `.rows`, `.columns`,
  `.bbox`. Default strategy uses the page's vector lines/rectangle edges as cell
  separators (`vertical_strategy="lines"`, `horizontal_strategy="lines"`), with a
  `"text"` strategy and `explicit_vertical_lines`/`explicit_horizontal_lines` for tables
  without full grids. Source: <https://github.com/jsvine/pdfplumber> (Extracting tables,
  table-extraction settings). This is exactly the MVP case: `CONTEXT.md` says a Document
  originates from a text-based PDF.
- **Limitation**: no OCR. It reads the PDF's own text layer, so a scanned/image-only PDF
  yields nothing. Table detection quality degrades on borderless tables and depends on
  hand-tuned `table_settings`.
- **Confidence**: **none intrinsic.** pdfplumber has no probability output; a character is
  either in the text layer or it is not. Confidence for this path must be built entirely
  from extrinsic plausibility checks (cell-count rectangularity, numeric/date parse
  success, totals reconciliation).

### PyMuPDF (fitz / `pymupdf`)

- **License: AGPL-3.0** (or a paid commercial license from Artifex). Source:
  <https://github.com/pymupdf/PyMuPDF/> ("License: GNU Affero General Public License v3.0").
  This matters: `docs/adr/0001` names possible commercialisation as a driver, and AGPL's
  network-copyleft is a real constraint for a hosted app. pdfplumber (MIT) avoids that.
- **Table fidelity**: `page.find_tables()` (added in v1.23.0) returns `Table` objects with
  header, rows, columns, per-cell bbox and text, and `to_markdown()` / `to_pandas()`
  exporters; it works across PDF/XPS/EPUB. Sources:
  <https://github.com/pymupdf/PyMuPDF/> (Extract tables),
  <https://github.com/pymupdf/PyMuPDF/discussions/2600>,
  <https://artifex.com/blog/table-recognition-extraction-from-pdfs-pymupdf-python>.
  Artifex flags it as still somewhat experimental with possible minor API changes.
- **Bonus**: PyMuPDF also renders pages to a high-resolution `Pixmap` and has built-in
  Tesseract OCR integration (full-page or partial). Source: <https://github.com/pymupdf/PyMuPDF/>
  (feature table: Rendering, OCR). So it can straddle families (a) and (b): use it as the
  rasteriser feeding the OCR path.
- **Confidence**: `find_tables()` gives no probability either; same story as pdfplumber.
  Its value here is rich geometry (per-cell bbox) that *feeds* plausibility checks and the
  rasterise step, not an intrinsic score.

**Verdict for (a):** great fidelity and near-zero cost on born-digital ruled tables, fully
offline, but it gives us **no intrinsic Confidence** and collapses on any scanned page.
Prefer **pdfplumber (MIT)** as the default text-layer reader over PyMuPDF (AGPL) unless we
specifically want PyMuPDF's rendering/OCR bridge.

## (b) Rasterise each page to an image, then OCR / layout model

This is the path the user has used before to sidestep formatting/licensing issues, and it
is the one that hands us an intrinsic Confidence signal for free.

### Tesseract (via pytesseract)

- **License: Apache-2.0** for both the engine (<https://github.com/tesseract-ocr/tesseract>)
  and the language data (<https://github.com/tesseract-ocr/tessdata>, "All data ... licensed
  under the Apache-2.0 License"). German (`deu`) is a first-class language, including
  Fraktur variants (`deu_latf`); Source:
  <https://tesseract-ocr.github.io/tessdoc/Data-Files-in-different-versions.html>. Fully
  offline; no per-page cost.
- **Confidence (the key win)**: `pytesseract.image_to_data(..., output_type=Output.DICT)`
  returns a `conf` column, a per-word confidence from 0 (none) to 100 (max), with `-1`
  meaning "no text here", alongside `left/top/width/height` bounding boxes and
  `block/par/line/word` structure. Sources: <https://github.com/madmaze/pytesseract>
  (image_to_data), <https://tomrochette.com/tesseract-tsv-format/> (TSV column spec),
  Tesseract mailing-list column description. This is exactly the intrinsic, regional,
  thresholdable signal we need: aggregate word `conf` to per-cell and per-table
  min/mean and you have a Confidence per region, offline.
- **Table fidelity**: Tesseract alone does *not* recover table structure; it gives words
  with coordinates. Structure must be reconstructed either from bounding-box geometry (our
  own row/column clustering, aided by the source PDF's ruling lines via pdfplumber/PyMuPDF)
  or by pairing Tesseract with a dedicated table-structure model below.

### Layout / table-structure models (offline)

- **PaddleOCR PP-Structure**: **Apache-2.0 code** (<https://github.com/PaddlePaddle/PaddleOCR>).
  Provides table recognition (SLANet / TableRec-RARE) with English and Chinese models, runs
  locally on CPU or GPU, and outputs the recognised table as HTML/Excel with cell
  coordinates. Model sizes are small (SLANet ~7-9 MB). Sources:
  <https://github.com/PaddlePaddle/PaddleOCR/blob/main/ppstructure/table/README.md>,
  <https://paddlepaddle.github.io/PaddleX/latest/en/pipeline_usage/tutorials/ocr_pipelines/table_recognition.html>.
  Gives structure Tesseract lacks, and recognition scores usable as an intrinsic signal.
- **Surya**: **code Apache-2.0**, but **model weights are a modified AI Pubs Open-RAIL-M
  license** ("free for research, personal use, and startups under $5M funding/revenue";
  broader commercial use needs a paid license). Strong multilingual OCR + layout + table
  recognition, but Surya 2 now needs a `vllm` (NVIDIA GPU) or `llama.cpp` (CPU/Apple
  Silicon) backend, i.e. heavier to self-host. Sources: <https://github.com/datalab-to/surya>,
  <https://github.com/datalab-to/surya/releases/tag/v0.20.0>. The weight license is a
  commercialisation flag, like PyMuPDF's AGPL.

**Verdict for (b):** fully offline, permissive if we stay on Tesseract (+ PaddleOCR),
robust to scanned/image PDFs, and uniquely it emits an **intrinsic per-word Confidence**.
Cost is compute/latency (rasterise at ~300 DPI, run OCR, optional table model) and lower
raw fidelity than a clean text layer on born-digital ruled tables. Confidence is its
strongest argument for our notify/fill-in loop.

## (c) Cloud document-AI

All three majors detect tables well and, crucially, return per-element confidence:

- **AWS Textract** `AnalyzeDocument` with `FeatureTypes=[TABLES]` returns `TABLE` and `CELL`
  `Block` objects, each carrying a `Confidence` float from 0 to 100, plus geometry. AWS's
  own best-practices doc tells you to enforce a minimum confidence threshold and route
  below-threshold results to human review (their words). Sources:
  <https://docs.aws.amazon.com/textract/latest/dg/how-it-works-tables.html>,
  <https://docs.aws.amazon.com/textract/latest/dg/API_Block.html>,
  <https://docs.aws.amazon.com/textract/latest/dg/textract-best-practices.html>.
- **Azure Document Intelligence** returns confidence (0-1) for words, key-value pairs,
  selection marks, etc. Note the caveat: **table / row / cell confidence is only available
  from the `2024-11-30` (GA) API and only for custom models**, not the prebuilt-layout
  model (prebuilt-layout gives word confidence but no table-object confidence). Sources:
  <https://learn.microsoft.com/en-us/azure/ai-services/document-intelligence/concept/accuracy-confidence?view=doc-intel-4.0.0>,
  <https://learn.microsoft.com/en-us/azure/ai-services/document-intelligence/train/custom-neural?view=doc-intel-4.0.0>,
  Microsoft Q&A on table-cell confidence.
- **Google Document AI** similarly returns table structure with confidence scores.

**Verdict for (c):** best out-of-the-box fidelity and a native, well-documented confidence
score, but it is a metered per-page cloud service and, decisively, it **violates the hard
local-swap requirement** if used as the only path: a Confidence signal that lives only in
a Textract/Azure response disappears the day the local adapter is installed. Cloud
document-AI is acceptable only *behind the same swappable seam* as the AI Provider (ADR
0001), never as the sole extractor.

## Scorecard

| Approach | Table fidelity | License | Cost | Offline / local-swap | Intrinsic Confidence |
|---|---|---|---|---|---|
| pdfplumber | High on born-digital ruled tables; weak borderless; none on scans | MIT (clean) | ~0 | Yes | None (heuristics only) |
| PyMuPDF | High, `find_tables()`, rich geometry, can also rasterise+OCR | AGPL-3.0 / paid | ~0 | Yes | None (heuristics only) |
| Tesseract (+ geometry) | Words + boxes; structure needs reconstruction | Apache-2.0 | compute | Yes | **Per-word `conf` 0-100** |
| PaddleOCR PP-Structure | Good table structure (SLANet), HTML/Excel out | Apache-2.0 | compute | Yes | Recognition scores |
| Surya | Strong multilingual OCR + table rec | Code Apache-2.0; **weights RAIL-M (commercial limits)** | compute (GPU-ish) | Yes | Model scores |
| Cloud (Textract/Azure/GCP) | Best OOTB | Proprietary/metered | per-page $ | **No (breaks local-swap)** | Native per-cell confidence |

## Recommendation: a two-track extractor behind an Extraction port, offline-first

Mirror the AI Provider decision (`docs/adr/0001`): put extraction behind a single
provider-agnostic **Extraction port**, and make the *default* adapter fully offline so the
hard local-swap requirement holds from day one. Cloud document-AI, if ever used, is just
another adapter behind that port, not the baseline.

Pipeline shape:

1. **Classify the page.** Ask the PDF whether it has a usable text layer (pdfplumber /
   pdfminer.six). Born-digital vs image-only decides the track.
2. **Track A, text+layout (fast path).** For text-based pages (the MVP norm), extract
   tables with **pdfplumber** (MIT), using its line and text strategies plus the source
   PDF's ruling geometry. Cheap, offline, high fidelity on ruled tables.
3. **Track B, rasterise + OCR (fidelity/fallback path).** Render the page (or just a
   suspect table region) to ~300 DPI and run **Tesseract** (`image_to_data`, Apache-2.0),
   optionally adding **PaddleOCR PP-Structure/SLANet** (Apache-2.0) for table-structure
   recovery. This is the user's known rasterise-to-OCR approach, and it is the track that
   yields an intrinsic Confidence. Always available; used automatically for scanned pages
   and as a cross-check on low-plausibility Track A tables.
4. **Normalise** both tracks into one internal structure: regions (tables, rows, Key
   Information fields) with text, bbox, and a Confidence in `[0, 1]`.

## How Confidence is emitted for the notify / fill-in loop

Every extracted region carries a Confidence computed as the minimum of two sub-scores, so
either a shaky read *or* an implausible value drags the region below threshold:

- **Intrinsic (Track B):** aggregate Tesseract per-word `conf` (0-100, `-1` dropped) to the
  cell, then take the per-cell minimum (or a low percentile) as the table/row score, scaled
  to `[0, 1]`. Track A has no intrinsic score, so its intrinsic term defaults to a neutral
  prior and it leans on the extrinsic term (and on a Track B re-OCR cross-check when the
  extrinsic term is low).
- **Extrinsic plausibility (both tracks):** rule checks tuned to Finanzamt-style content,
  every amount parses as a German-format number, dates match expected `dd.mm.yyyy`
  patterns, each row has the expected cell count (rectangularity), and line items
  reconcile to any stated total. Each check contributes to the extrinsic sub-score.

The port returns, per region: the extracted value, its bbox, the Confidence, and the
failing check(s). A region whose Confidence is below the configured threshold raises the
**notify** event, and the failing region's bbox is exactly what the **fill-in** UI shows
the user ("type in table XX, OCR could not read it"), matching the `Confidence` definition
in `CONTEXT.md`. Because both the extraction and its Confidence are produced offline, the
notify/fill-in loop behaves identically whether the app runs on a cloud or a self-hosted
adapter, satisfying `docs/adr/0001`.

### Concrete default stack (Python + FastAPI)

- Text layer + Track A tables: **pdfplumber** (MIT).
- Rasterise: pdfplumber/`pdf2image` or PyMuPDF `Pixmap` (keep PyMuPDF optional given AGPL).
- Track B OCR + intrinsic Confidence: **Tesseract** via `pytesseract` (Apache-2.0), German
  `deu` traineddata; add **PaddleOCR PP-Structure** (Apache-2.0) for table structure.
- Extraction port with adapters so a cloud document-AI (Textract/Azure) can be slotted in
  later without touching application code, exactly as ADR 0001 mandates for the AI Provider.
