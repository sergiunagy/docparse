# Context

Glossary for `docparse` — a personal/family assistant that ingests official German
documents, understands them, and helps the user act on them. This file is a
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
Rendering a Document's content into the output language. The MVP translates **German ->
English**; Romanian source support and a Romanian output toggle are later iterations
(currently fog).

### AI Provider
The external or local model service that performs a single language task. It sits behind
the AI Service's provider-agnostic contract so the MVP can use a cloud provider while
remaining swappable to a self-hosted/local provider without rework (see `docs/adr/`).

### AI Service
The application service that owns all language work, exposed as capability methods
(translate, extract-assist, summarise, answer) rather than raw model calls. It is one
service among several (see Service, and `docs/adr/` for the service-oriented decision),
and it hides which AI Provider and model actually served a request.

### Model Router
The component inside the AI Service that chooses which AI Provider and model serves a
given request, keyed by the capability needed and the available deployment/hardware
profile (e.g. a small local model on a 12 GB GPU, a dedicated translation model for
`translate`, or a cloud model). Selection is configuration, not application logic.

### Service
An independently deployable component of the application. `docparse` is service-oriented:
distinct services (e.g. client/UI, gateway, ingestion, extraction, AI Service, document
store, Auth Service) own their own responsibilities and can be placed, swapped, or
developed independently.

### Auth Service
The separate Service responsible for authenticating the account holder. It is deliberately
its own service so the underlying identity provider can be outsourced to a third party
rather than hand-built. Distinct from Client (who a Document is *about*).
