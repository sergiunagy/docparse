# Context

Glossary for `docparse` — a personal/family assistant that ingests official documents
(German or Romanian), understands them, and helps the user act on them. This file is a
glossary only: no implementation details, no decisions (those live in `docs/adr/`).

## Glossary

### Document
A single official/administrative item a user ingests — e.g. a Finanzamt notification.
In the MVP a Document originates from a **text-based PDF**. Understanding is scoped to
the text of one Document at a time; reasoning across multiple Documents is out of scope.

### Source
Where a Document comes from. The MVP models Source as a pluggable abstraction; the first
concrete Source is a folder of files (e.g. a Google Drive folder), and ingestion must be
triggerable from a mobile device.

### Client
The family member a Document concerns ("Mom's residence permit", "my tax letter").
Extracted information and Obligations attach to a Client. A Client is *who a Document is
about*, distinct from the authenticated account holder who operates the app.

### Extraction
Turning a Document's pages into structured, layout-aware content. Because value lives in
tables (e.g. Finanzamt figures), Extraction must preserve table/layout fidelity rather
than flattening to loose prose.

### Confidence
A per-Extraction judgement of reliability. When an Extraction fails a plausibility check,
the user is *notified* and offered an optional manual **fill-in** for the affected region
(e.g. "type in table XX, OCR could not read it"). This is a notification + input option,
not a general correction workflow.

### Key Information
The salient fields lifted from a Document during Extraction: sender, document type,
dates/deadlines, amounts.

### Obligation
An action the Document *itself explicitly requests* ("pay €X by 15 March", "submit form
Y"). Obligations are extracted from the text alone. Deciding what a user should *do*
across their wider situation (an action *plan*) is out of scope.

### Understanding
The MVP's per-Document deliverable: the English translation, Key Information, any
Obligations, its association to a Client, a plain-English summary, and Q&A over that one
Document.

### Translation
Rendering a Document's content from German or Romanian into the output language. The MVP
output language is **English**; a Romanian toggle is a later iteration.

### AI Provider
The external or local model service that performs language tasks. It sits behind a
provider-agnostic adapter so the MVP can use a cloud provider while remaining swappable
to a self-hosted/local provider without rework (see `docs/adr/`).
