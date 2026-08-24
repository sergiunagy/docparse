# Prototype 02 — OpenAI understanding spike

**Status:** planned (not yet built).
**Validates:** issue [#2](https://github.com/sergiunagy/docparse/issues/2) —
[`docs/research/ai-orchestration.md`](../../docs/research/ai-orchestration.md).

## 1. Design question

The #2 research recommends putting the **OpenAI Chat Completions contract** behind the AI
seam, backed by the raw `openai` SDK, and keeping the translate/extract/summarise/Q&A
orchestration in *our own* code (no LangChain/LlamaIndex). That is a desk conclusion. This
spike answers, with something runnable and measured:

1. **Is the raw `openai` SDK genuinely enough** to drive an end-to-end "understand this
   document" pass, or do we feel a real pull toward a framework? (validates Option A over C)
2. **Does Structured Outputs** (`response_format` = `json_schema`, `strict: true`) reliably
   return schema-adherent extraction on a real German document?
3. **Faithfulness / drift:** how far does a broad **"action plan"** wander beyond what the
   document literally says, versus strict **Obligations** ("actions the Document *itself
   explicitly requests*", per `CONTEXT.md`)? This is the empirical test of whether an
   "action plan" can live inside the MVP's scope or needs guardrails.
4. **Real cost & latency per document**, from measured token usage. Because this spike sends
   **page images** (§2) and defaults to a **reasoning** model (`gpt-5-mini`, see §7), the old
   ~$0.004 desk estimate on `gpt-4o-mini` no longer applies. Two variables dominate instead:
   patch-based image tokens (cheap on GPT-5, unlike 4o-mini's tile tax) and **reasoning
   tokens billed as output** — the counter exists to measure both, not confirm a guess.
5. **Token workload profile.** How many tokens does one document actually consume, **grouped
   by type** (text-prompt vs image-input vs completion) **and by step** (per API call)? This
   is the input to any capacity/cost planning and the reason for the token counter (§4a).

### Deliberately OUT of scope for this spike (owned by other tickets)

- **Table/layout-faithful extraction and the Confidence signal** → issue #3. Here we hand the
  model **raw page images** and let it read them; we make **no** structured-table or layout
  claims. (We send images rather than `pdfplumber` text on purpose: real inputs are often
  scans with no usable text layer, and the default model is vision-capable, so a text-only
  extractor would silently fail on exactly the documents we care about.)
- **Translation-quality evaluation and the OPUS-MT comparison** → issue #4. The English
  summary incidentally exercises translation, but we do not score legal register here.
- **Local swap (Ollama/vLLM).** Cloud OpenAI only. (But see §4 — we stay on the wire format
  that makes the swap a config change, so this spike doesn't paint us into a corner.)

## 2. What it does (end to end)

```
one PDF on disk (born-digital OR scanned — we don't care which)
        │  render each page to a PNG (PyMuPDF at a fixed DPI; #3 owns real extraction)
        ▼
   N page images  (+ a short text prompt / glossary stub)
        │  ONE openai Chat Completions call: messages carry the text prompt plus
        │  one image_url part per page, response_format=json_schema (strict),
        │  detail = OPENAI_IMAGE_DETAIL (low|high — the main cost lever, see §7)
        ▼
   {
     english_summary,                      # plain-English summary
     key_information: {sender, doc_type, dates[], amounts[]},
     obligations: [                        # in-scope per CONTEXT.md
        {text, source_quote, deadline}
     ],
     action_plan: [                        # the "compare" arm
        {step, rationale, grounded_in_document: bool}
     ]
   }
        │
        ▼
   pretty-print to console + write out/<pdf>.json, out/<pdf>.md, out/run-log.jsonl
   (run-log records model, prompt/completion tokens, computed $ cost, wall-clock latency)
```

The `grounded_in_document` boolean on each action-plan step is the drift probe: it lets us
count how many suggested steps the model itself cannot tie back to the text, i.e. how much
the "action plan" framing invites content the document never asked for.

**Vision caveat on `source_quote`:** with image input the model *reconstructs* the text via
OCR rather than being handed it verbatim, so `source_quote` may be paraphrased or slightly
mis-transcribed rather than an exact substring. We keep the field (it still anchors
grounding) but treat quote-exactness as something to observe, not assume — an extra data
point for the faithfulness read in §4.

### Why Chat Completions specifically (not the Responses API)

The entire #2 portability argument rests on the `/v1/chat/completions` wire format, because
that is what Ollama and vLLM speak. Using **Chat Completions** here keeps the spike honest
to the seam decision and to the local-swap path; the exact same call flips to a local
endpoint later with only a `base_url` + model-name change.

## 3. Files to create (at build time)

```
prototypes/02-openai-understanding/
├── PLAN.md            # this file
├── README.md          # run instructions (write at build time)
├── requirements.txt   # openai, pymupdf, tiktoken, python-dotenv, pydantic
├── .env.example       # OPENAI_API_KEY= , OPENAI_MODEL=gpt-5-mini ,
│                      #   OPENAI_REASONING_EFFORT=minimal ,
│                      #   OPENAI_IMAGE_DETAIL=high , PDF_RENDER_DPI=150
├── .gitignore         # .venv/  .env  samples/  out/
├── main.py            # the spike
├── samples/           # drop a redacted German PDF here (git-ignored)
└── out/               # JSON/markdown/cost artefacts (git-ignored)
```

`main.py` responsibilities (kept in one file on purpose):

- Load `.env`, construct `OpenAI(base_url=..., api_key=...)` from config **only** (so the
  local-swap path is visible even though we don't exercise it).
- `PyMuPDF` → render each PDF page to a PNG at `PDF_RENDER_DPI`, base64-encode it.
- Build messages: a system prompt that (a) asks for an English summary, (b) extracts
  Obligations strictly grounded in the document with a `source_quote`, (c) proposes an action
  plan and self-labels each step `grounded_in_document`. Inject a tiny DE→EN
  legal/financial glossary stub inline (this also previews the #4 glossary idea). Attach one
  `image_url` content part per page at `detail=OPENAI_IMAGE_DETAIL`.
- One Chat Completions call with a strict `json_schema` response format (Pydantic model →
  schema). Since the default model is a **reasoning** model (§7): pass
  `reasoning_effort=OPENAI_REASONING_EFFORT` (default `minimal`), use `max_completion_tokens`
  (not `max_tokens`), and **do not** send `temperature`/`top_p` (reasoning models reject
  them). Parse, print, and persist outputs + the **token accounting** described in §4a.

Keep it under ~180 lines. No abstraction, no ports — this is a spike, not the seam.

## 4. Success criteria / evidence to capture

The spike is "done" when we can put the following in a comment on issue #2:

- [ ] Runs end-to-end on **≥1 real (redacted) German PDF (ideally a scan)** and produces
      valid, schema-adherent JSON on repeated runs (evidence for the Structured Outputs claim).
- [ ] **Measured token breakdown per document, grouped by type** (image-input, text-prompt,
      completion) **and by step** (per API call), plus computed $/document split into
      input/output cost — see §4a. Explicitly replaces the dead ~$0.004 desk estimate.
- [ ] Measured wall-clock latency for the pass.
- [ ] **Drift finding:** how many `action_plan` steps came back `grounded_in_document:false`,
      and a qualitative read of whether the summary/obligations stayed faithful. This
      directly informs the "action plan vs Obligations" scope question.
- [ ] A one-paragraph verdict: did the raw `openai` SDK feel sufficient, or did we hit
      anything that argues for a routing layer / framework?

## 4a. Token counter (design)

**Goal:** for one document, report tokens grouped **by type** (image-input / text-prompt /
visible-completion / reasoning) and **by step** (per API call — currently one; the log is
per-call so a future multi-step flow extends without rework).

**Why it isn't just reading `usage`:** the `usage` object gives authoritative totals —
`prompt_tokens` (all input), `completion_tokens` (visible **plus** reasoning),
`total_tokens` — but it doesn't split image-from-text within `prompt_tokens`, and on a
reasoning model the reasoning tokens are folded into `completion_tokens`. So we split both:

1. Take `prompt_tokens`, `completion_tokens`, `total_tokens` from `usage` (this is what you
   are billed). Read `completion_tokens_details.reasoning_tokens` to separate **reasoning**
   from **visible** output (`visible = completion_tokens − reasoning_tokens`).
2. Compute `image_tokens` **analytically** per page. The default (`gpt-5-mini`/`gpt-5-nano`)
   uses **patch-based** tokenization, *not* 4o-mini's tile tax:
   `patches = ceil(w/32) × ceil(h/32)`, capped at a **1 536-patch budget** (image is shrunk
   to fit if larger), then `image_tokens = ceil(patches × multiplier)` with `multiplier ≈
   1.5` (nano) / `≈ 1.62` (mini). Sanity-check: a large A4 scan lands ~**2 300–2 500** image
   tokens on GPT-5 — versus ~**25 500** on `gpt-4o-mini` (tile). Keep a tile branch
   (`detail:low`=85 / `high`≈765 on `gpt-4o`; ×33.33 on `gpt-4o-mini`) only for the legacy
   comparison runs.
3. Derive `text_prompt_tokens = prompt_tokens − image_tokens`. Independently compute a
   `tiktoken` estimate of the text messages and log **both**, so a large gap flags a bug in
   the image formula rather than hiding it.

**`run-log.jsonl` — one JSON line per call:** `model`, `reasoning_effort`, `image_detail`,
`render_dpi`, `n_pages`, `image_tokens`, `text_prompt_tokens`, `text_tokens_tiktoken`
(cross-check), `prompt_tokens` (reported), `reasoning_tokens`, `visible_completion_tokens`,
`completion_tokens` (reported), `total_tokens`, `input_cost_usd`, `output_cost_usd`
(reasoning billed here), `total_cost_usd`, `latency_s`. Prices come from a small hard-coded
per-model rate table in `main.py` (input/output $/1M tokens).

## 5. Build & run steps (for the later build turn)

1. `cd prototypes/02-openai-understanding`
2. `python3 -m venv .venv && source .venv/bin/activate`
3. `pip install -r requirements.txt` (`openai`, `pymupdf`, `tiktoken`, `python-dotenv`, `pydantic`)
4. Complete the **OpenAI account setup** in §6, then `cp .env.example .env` and paste the key.
5. Put a redacted German PDF in `samples/`.
6. `python main.py samples/<file>.pdf`
7. Inspect `out/` and `out/run-log.jsonl`; record findings on issue #2.

## 6. OpenAI account setup (from nothing → funded API key)

You have no account yet, so start here. **The API platform is separate from ChatGPT —
API access is *not* included in a ChatGPT Plus/Pro subscription, and the two have separate
billing.** (Sources: OpenAI Help Center — "Billing settings in ChatGPT vs Platform"; API
pricing FAQ.)

1. **Create an API platform account** at <https://platform.openai.com>. Sign up / log in;
   verify email and phone.
2. **Create a dedicated Project (recommended).** A **Default project** is created for you,
   but usage, spend, rate limits, and keys are all tracked *per project*. Create a dedicated
   one so this spike is isolated and disposable: sidebar project switcher (top-left, reads
   "Default project") → **Create project** → name it e.g. `docparse-prototypes`. **Switch
   into that project now**, *before* creating the key in step 5 — a key inherits the project
   that is active when you create it. Deleting the project later revokes every key in it at
   once, which keeps the blast radius small if a key leaks.
3. **Set up prepaid billing.** New accounts are on **prepaid billing**: add a payment method
   and purchase credits. Minimum purchase **$5**, default **$10** — plenty for a spike, though
   at the image-based cost this now implies (cents-to-tens-of-cents/run, see §7) that's dozens
   to a few hundred runs, not thousands. Notes:
   - **Auto-recharge is ON by default** during setup. If you want a hard spend cap for a
     throwaway spike, **turn auto-recharge off** before confirming.
   - Purchased credits **expire after 1 year** and are **non-refundable**.
   (Source: OpenAI Help Center — "How can I set up prepaid billing?" / "What is prepaid
   billing?".)
4. **(Recommended) Set a usage limit + alert.** In the billing/limits settings, set a low
   monthly budget and an email alert threshold, so a runaway loop can't burn credits.
5. **Create an API key.** With the `docparse-prototypes` project active (step 2), create a
   **project-scoped** API key. When asked who owns it, choose **owned by you** (a personal
   user key) — a service account is only worth it for keys that must outlive a person (CI,
   shared servers), which a local one-person spike is not. Name it e.g.
   `docparse-prototype-02`. **Copy it immediately — it is shown only once.** If lost, revoke
   and create a new one.
6. **(Optional) Confirm data controls.** By default, API inputs/outputs are **not used to
   train** OpenAI models; inputs/outputs may sit in abuse-monitoring logs for up to ~30
   days. This is the "paid bridge" caveat already recorded in the #2 research — fine for a
   redacted sample, and the reason local remains the privacy destination.
7. **Store the key locally.** `cp .env.example .env`, then set
   `OPENAI_API_KEY=sk-...`. The repo `.gitignore` ignores `.env` (any directory), so it
   won't be committed. **Never** paste the key into code, a commit, or an issue.

### Cost expectation for this spike

**The old ~$0.004/document estimate assumed text input on `gpt-4o-mini` and no longer holds.**
The default is now `gpt-5-mini` (§7), which on **patch-based** vision costs only ~2 300–2 500
image tokens per A4 scan (≈$0.0006/page input) — an order of magnitude below `gpt-4o-mini`'s
tile tax. The new cost variable is **reasoning tokens** (billed as output at $2.00/1M on mini);
`reasoning_effort=minimal` keeps them small. Ballpark: a single-page doc is ~$0.003–0.004 on
`gpt-5-mini` and ~$0.0007 on `gpt-5-nano`. A $5 credit covers hundreds–thousands of runs, but
**the point of the token counter is to produce the real number** (§4/§4a). Keep the usage
limit (step 4) low.

## 7. Model choice

**Default `OPENAI_MODEL=gpt-5-mini`** — chosen as the *quality anchor* against which we
reference cheaper and stronger alternatives. Rationale (verified 2026-08):

- **Quality reference.** Nano is the family floor ("limited in reasoning depth"), which is
  exactly the wrong bet for nuanced **German legal/financial translation and register
  fidelity** — a stated selection criterion. `gpt-5-mini` is the cheapest model we'd trust as
  the yardstick.
- **Cheap vision.** GPT-5 uses **patch-based** image tokens (budget-capped ~1 536 patches ×
  ~1.62), so an A4 scan is ~2 500 image tokens — ~10× fewer than `gpt-4o-mini`'s tile tax
  (~25 500). The vision-cost objection that applied to 4o-mini does **not** apply here.
- **400K context** (vs 128K on `gpt-4o-mini`) — real headroom for multi-page scans (many
  image parts + text) plus a large output budget.
- Supports strict Structured Outputs and Chat Completions, so the #2 portability seam holds.

**Reasoning-model caveats (new).** `gpt-5-mini`/`gpt-5-nano` are reasoning models: they emit
**reasoning tokens billed as output**, run slower, and **reject `temperature`/`top_p`**. Use
`reasoning_effort=minimal` for this extraction/summary task and log reasoning tokens
separately (§4a). Portability note for ADR 0001: `reasoning_effort` is an OpenAI-ism a local
Ollama/vLLM model won't reproduce identically — a small seam wrinkle, not a blocker.

Because model is an env var, **benchmark alternatives beside the default**: `gpt-5-nano`
(the cost floor — ~5× cheaper, near-free vision; likely the *production* default *if* its
German-legal quality holds), `gpt-5` (upgrade probe — does more quality justify the cost?),
and `gpt-4o-mini` (legacy point for continuity with the #2 desk research). Let the §4a
counter decide on measured $/document *and* quality — don't assume the default wins.

`OPENAI_IMAGE_DETAIL` (`low` | `high`) is the other lever. On the patch models `high` is
already cheap, and `low` risks missing fine print in a dense legal scan, so default `high`
for correctness and record it per run so cost is always attributable to the detail setting.
