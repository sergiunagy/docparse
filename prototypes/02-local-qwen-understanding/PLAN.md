# Prototype 02b — Local Qwen understanding spike

**Status:** planned (not yet built).
**Validates:** issue [#2](https://github.com/sergiunagy/docparse/issues/2) — specifically the
**local-swap arm** of [`docs/research/ai-orchestration.md`](../../docs/research/ai-orchestration.md)
(§"Update: routed AI service, local hardware target, and model choice") and the swap
promise in [ADR-0001](../../docs/adr/0001-ai-provider-adapter.md).

**Companion to [`../02-openai-understanding/`](../02-openai-understanding/PLAN.md).** That
spike proved the *cloud* arm (OpenAI, `gpt-5-mini`, page images → strict `json_schema`
Understanding). This one runs **the same scenario against a locally hosted Qwen model** on
the developer's own GPU, to test whether the "swap to local is a `base_url` + model-name
change" claim survives contact with reality.

## 1. Design question

ADR-0001 and the #2 research assert that because the port is the **OpenAI Chat Completions
wire contract**, moving from cloud OpenAI to a self-hosted model is *configuration, not a
rewrite* — and that a **Qwen2.5-class model on the RTX 3080 Ti (12 GB)** is the free +
fully-private end state. Both are desk conclusions. This spike answers, with something
runnable and measured on the actual hardware:

1. **Is the local swap really a config change?** Point the *same* `openai` client at a local
   Ollama endpoint (`base_url=http://localhost:11434/v1`, dummy key), change only the model
   name, and see how much of `../02-openai-understanding/main.py` runs **unmodified**. Every
   line we're forced to change is a crack in the ADR-0001 seam and must be recorded.
2. **Does Structured Outputs survive the swap?** proto 02 relies on
   `client.beta.chat.completions.parse(response_format=Understanding)` (strict `json_schema`).
   Ollama's *native* structured-output path is the `format` field (a JSON schema), and its
   OpenAI-compat `response_format: json_schema` handling has been historically weak
   ([ollama#10001](https://github.com/ollama/ollama/issues/10001)) — though `.parse(...)`
   against `/v1` has been reported working. **This is the empirical test of the "degrade to a
   documented JSON-mode fallback" path the #2 research says the adapter must own.** We find
   out whether we get: (a) native `json_schema` parity, (b) a working `.parse` that quietly
   uses Ollama's grammar sampler, or (c) a forced fallback to Ollama's `format` field.
3. **Can a local vision model actually read a German Finanzamt scan?** Qwen2.5-VL-7B OCRs the
   page images itself (same as `gpt-5-mini` did). Does its transcription + Understanding hold
   up on dense German legal/financial text, or does it miss fine print / mistranslate
   register? Quality is compared **head-to-head against proto 02's output on the same PDFs**.
4. **Does it fit and is it fast enough on a 3080 Ti?** Measure **VRAM used, model load time,
   tokens/sec, and wall-clock latency per document**. The research predicts a 7B Q4 model at
   ~5–6 GB / ~70–77 tok/s (comfortable) and a 14B Q4_K_M at ~13.6 GB (tight). Confirm on the
   real card, in WSL2.
5. **Faithfulness / drift, local edition.** Reuse proto 02's `grounded_in_document` drift
   probe: does a smaller *local* model drift *more* in its action plan, and does its
   summary/obligations stay faithful? Feeds the same "action plan vs Obligations" scope
   question, now with the model we'd actually ship for privacy.

### Deliberately OUT of scope for this spike (owned by other tickets)

- **Table/layout-faithful extraction and the Confidence signal** → issue #3. As in proto 02,
  we hand the model **raw page images** and make no structured-table or layout claims.
- **Translation-quality scoring and the OPUS-MT comparison** → issue #4. The English summary
  incidentally exercises translation; we do a qualitative German-legal-register read only, we
  do not score it or wire up the dedicated `Helsinki-NLP/opus-mt-de-en` translation slot.
- **The Model Router / capability-method AI Service** (ADR-0002, #2 §"routed AI service").
  This spike is a single hard-wired local model, not the `(capability, HW-profile) → model`
  registry. It only produces evidence the router will later consume.
- **vLLM as the runtime.** We use **Ollama** for this spike (§7 explains why for 12 GB). vLLM
  stays a documented alternative, not a second implementation here.
- **Fine-tuning / QLoRA.** Inference only, per the #2 research ("no training in the MVP").
- **$ cost.** Local inference is **$0 at inference** (only hardware/electricity already
  owned). The cost counter from proto 02 is replaced by a **local-performance** counter (§4a).

## 2. What it does (end to end)

Identical pipeline to proto 02 — *that's the point*. Only the endpoint and model change.

```
one PDF on disk (born-digital OR scanned — same samples as proto 02)
        │  render each page to a PNG (PyMuPDF at a fixed DPI)
        ▼
   N page images  (+ the same short text prompt / DE→EN glossary stub)
        │  ONE openai Chat Completions call, but against a LOCAL endpoint:
        │    base_url = http://localhost:11434/v1 , api_key = "ollama" (ignored)
        │    model    = qwen2.5vl:7b
        │  page images as image_url parts; strict json_schema response_format
        │  (with a documented fallback to Ollama's native `format` field — see §1.2)
        ▼
   {
     english_summary,
     key_information: {sender, doc_type, dates[], amounts[]},
     obligations: [ {text, source_quote, deadline} ],       # in-scope per CONTEXT.md
     action_plan: [ {step, rationale, grounded_in_document: bool} ]  # drift probe
   }
        │
        ▼
   pretty-print to console + write out/<pdf>.json, out/<pdf>.md, out/run-log.jsonl
   (run-log records model, prompt/completion tokens, VRAM, load time, tok/s, latency —
    NO $ cost, because local inference is free; see §4a)
```

The **schema, prompt, glossary, and drift probe are copied verbatim from proto 02** so the
only variables are *endpoint*, *model*, and *runtime*. That isolation is what makes the
cloud↔local comparison meaningful and what tests the ADR-0001 swap claim honestly.

### Why still Chat Completions (not Ollama's native `/api/chat`)

The whole #2 portability argument rests on the `/v1/chat/completions` wire format. Talking to
Ollama through the **stock `openai` SDK at `/v1`** — not its bespoke `/api/chat` — is the
honest test of the seam. Where a call *cannot* be made to work through `/v1`, that is a finding
(§1.2), and Ollama's native `format` field is the recorded fallback, not the default path.

## 3. Files to create (at build time)

```
prototypes/02-local-qwen-understanding/
├── PLAN.md            # this file
├── README.md          # run instructions (write at build time)
├── requirements.txt   # openai, pymupdf, tiktoken, python-dotenv, pydantic (same as proto 02)
├── .env.example       # OPENAI_BASE_URL=http://localhost:11434/v1 , OPENAI_API_KEY=ollama ,
│                      #   OPENAI_MODEL=qwen2.5vl:7b , PDF_RENDER_DPI=150 ,
│                      #   OLLAMA_STRUCTURED_MODE=auto  (auto|json_schema|ollama_format)
├── .gitignore         # .venv/  .env  data/  out/
├── main.py            # adapted copy of ../02-openai-understanding/main.py (see below)
├── data/              # SAME redacted German PDFs used in proto 02 (git-ignored)
└── out/               # JSON/markdown/perf artefacts (git-ignored)
```

`main.py` is a **deliberate near-copy** of proto 02's, to keep the diff (= the cost of the
swap) small and visible. Expected changes, all config-driven where possible:

- Construct `OpenAI(base_url=OPENAI_BASE_URL, api_key=OPENAI_API_KEY)` — proto 02 already
  reads `OPENAI_BASE_URL`, so ideally this is **zero code change**, only `.env`.
- **Drop the reasoning-model branch** (`reasoning_effort`, patch-based image-token math): Qwen
  via Ollama is not a GPT-5 reasoning model. Guard those with the existing `model.startswith`
  checks so they simply don't fire — again minimising the diff.
- **Structured-output strategy** driven by `OLLAMA_STRUCTURED_MODE`: `json_schema` (try the
  proto 02 `.parse` path as-is), `ollama_format` (fall back to passing
  `Understanding.model_json_schema()` via `extra_body={"format": ...}`), or `auto` (try the
  first, fall back on schema-nonadherence). Whichever path works is logged per run (§4a).
- **Replace the `$`-cost block** with the local-performance block (§4a): VRAM, load time,
  tok/s. Token counts still come from the `usage` object Ollama returns.

Keep it a single file, no abstraction — this is a spike, not the seam. The measured size of
the diff vs proto 02's `main.py` is itself an output (evidence for the "config change, not a
rewrite" claim).

## 4. Success criteria / evidence to capture

The spike is "done" when we can put the following in a comment on issue #2:

- [ ] **Swap verdict:** ran end-to-end against local Qwen with the `openai` SDK, and a stated
      **count of lines changed vs proto 02's `main.py`** (ideally near-zero + `.env`). Explicit
      call-out of anything that was *not* a pure config change → the real cost of the seam.
- [ ] **Structured-output result:** which of §1.2's outcomes (a/b/c) we got, whether repeated
      runs stayed schema-adherent, and — if a fallback was needed — exactly what it was. This
      is the concrete input to the adapter's "JSON-mode fallback" design.
- [ ] **Local performance on the 3080 Ti:** VRAM used, model load (cold-start) time, tok/s,
      and wall-clock latency per document — see §4a. Confirms/refutes the ~5–6 GB / ~70 tok/s
      research prediction for 7B Q4.
- [ ] **Quality read vs proto 02:** side-by-side of the local Qwen Understanding against the
      `gpt-5-mini` output **on the same PDFs** — OCR fidelity, translation register, key-info
      accuracy. A blunt "is the free/private local path good enough to ship, or only a
      fallback?" judgement.
- [ ] **Drift finding:** how many `action_plan` steps came back `grounded_in_document:false`
      locally, compared to proto 02's numbers on the same documents.
- [ ] A one-paragraph verdict feeding the ADR-0001 swap claim and the eventual Model Router.

## 4a. Local-performance counter (design)

**Goal:** replace proto 02's `$`-cost accounting with what actually matters for a local model:
does it fit, how long to load, how fast does it generate. Tokens still come from Ollama's
`usage` object; there is no reasoning-token split (not a reasoning model) and no analytic
image-token math (Ollama reports its own totals).

Capture per run:

- **Token counts** from `usage`: `prompt_tokens`, `completion_tokens`, `total_tokens`. Keep
  the `tiktoken` text-prompt cross-check from proto 02 (approximate for Qwen's tokenizer, but
  a useful sanity signal — log it as an estimate, flag it as not-Qwen-exact).
- **`load_duration` / `prompt_eval_duration` / `eval_duration`** if surfaced (Ollama reports
  these on `/api/*`; via `/v1` they may live under `extra`/be absent — capture what's there,
  else time it ourselves).
- **`tokens_per_second`** = `completion_tokens / eval_duration_s` (or wall-clock derived).
- **`vram_mb`**: sampled from `nvidia-smi --query-gpu=memory.used --format=csv` (and/or
  `ollama ps`, which reports model size + GPU/CPU split) around the call. Record the GPU/CPU
  offload split so a "tight fit that spilled to CPU" is visible, not hidden as slowness.
- **`model_load_s`**: cold-start latency (first call after `ollama stop`) vs warm latency —
  report both, since load time dominates a one-shot doc but not a batch.
- **`latency_s`**: wall-clock for the pass (kept from proto 02).

**`run-log.jsonl` — one JSON line per call:** `ts`, `pdf`, `runtime` (`ollama`), `model`,
`quant`, `structured_mode` (which of §1.2 fired), `context_length` (active
`OLLAMA_CONTEXT_LENGTH`), `kv_cache_type`, `flash_attention`, `render_dpi`, `n_pages`, `prompt_tokens`,
`completion_tokens`, `total_tokens`, `text_tokens_tiktoken` (estimate), `tokens_per_second`,
`load_duration_s`, `eval_duration_s`, `vram_mb`, `gpu_cpu_split`, `latency_s`. **No cost
fields** — free at inference is the whole point. Also assert `prompt_tokens < context_length`
per run and warn loudly if not — that's the silent-truncation tripwire from §6.5.

## 5. Build & run steps (for the later build turn)

1. Complete the **from-scratch local stack setup** in §6 first (GPU visible in WSL → Ollama →
   model pulled → smoke-tested). Nothing below works until `nvidia-smi` and `ollama run`
   succeed inside WSL.
2. `cd prototypes/02-local-qwen-understanding`
3. `~/.pyenv/versions/3.13.2/bin/python -m venv .venv && source .venv/bin/activate`
   (mirror proto 02; a fresh `docparse`-style pyenv venv is equally fine).
4. `pip install -r requirements.txt` (`openai`, `pymupdf`, `tiktoken`, `python-dotenv`,
   `pydantic` — identical set to proto 02).
5. `cp .env.example .env` — the defaults already point at local Ollama; edit only if the
   endpoint/model differ.
6. Copy (or symlink) the **same redacted German PDFs** used in proto 02 into `data/`.
7. `python main.py data/<file>.pdf`
8. Inspect `out/` and `out/run-log.jsonl`; diff the JSON against
   `../02-openai-understanding/out/<file>.json`; record findings on issue #2.

## 6. From-scratch local stack setup (WSL2 · Ubuntu 22.04 · RTX 3080 Ti)

Unlike proto 02 (which prepped a *cloud account*), this prototype must stand up a **local GPU
inference stack from nothing**. Order matters: get the GPU visible to WSL *before* touching
Ollama.

### 6.1 GPU passthrough into WSL2 (Windows-side, one-time)

The GPU is exposed to WSL by the **NVIDIA Windows driver only** — via GPU-paravirtualisation.
([CUDA on WSL User Guide](https://docs.nvidia.com/cuda/wsl-user-guide/))

1. On **Windows** (host), install/refresh a recent NVIDIA driver for the 3080 Ti (Game Ready
   or Studio, R495+ includes WSL CUDA support). Download from
   <https://www.nvidia.com/Download/index.aspx>. A clean install is recommended.
2. **Do NOT install any Linux/NVIDIA GPU driver inside WSL.** `libcuda.so` is stubbed into
   WSL automatically by the Windows driver; a Linux GPU driver in WSL breaks the path.
   ([CUDA on WSL User Guide](https://docs.nvidia.com/cuda/wsl-user-guide/))
3. Ensure WSL itself is current: from PowerShell, `wsl --update` and `wsl --version`
   (GPU compute needs a recent WSL kernel + Windows build).
4. **Verify inside WSL:** `nvidia-smi` should list the RTX 3080 Ti with 12 GB. If it doesn't,
   stop here — it's a Windows-driver/WSL-version problem, and nothing downstream will work.
   (NVIDIA-SMI shows a limited feature set under WSL — that's expected.)

> Note: no CUDA Toolkit install is required for this spike — Ollama ships its own bundled
> CUDA runtime. A toolkit is only needed to *compile* CUDA code, which we don't.

### 6.2 Install Ollama (inside WSL)

1. `curl -fsSL https://ollama.com/install.sh | sh` (installs the Linux Ollama; it will use
   the WSL-exposed GPU automatically). Note: the installer tries to create a **systemd
   service, which won't start under WSL unless systemd is enabled** (`/etc/wsl.conf` →
   `[boot]\nsystemd=true`, then `wsl --shutdown`). Without systemd, run `ollama serve`
   manually (foreground) — fine for a spike.
2. Start the server **with the context/KV-cache tuning from §6.5** (this is not optional for
   multi-page vision docs — see §6.5 for why):

   ```bash
   # 32768 measured to fit 100% on GPU (~6.5 GB) on this 12 GB card — see §6.5
   export OLLAMA_CONTEXT_LENGTH=32768
   export OLLAMA_FLASH_ATTENTION=1
   export OLLAMA_KV_CACHE_TYPE=q8_0
   ollama serve
   ```

   It listens on `http://127.0.0.1:11434` and exposes the OpenAI-compat surface at
   `http://127.0.0.1:11434/v1`.
3. **Confirm GPU detection:** the `ollama serve` log should show a CUDA line, e.g.
   `library=CUDA compute=8.6 ... name="NVIDIA GeForce RTX 3080 Ti" ... total="12.0 GiB"
   available="10.8 GiB"` (≈1.2 GiB is already held by the Windows desktop — expected). If it
   says CPU-only, revisit §6.1. Cross-check with `ollama ps` → `PROCESSOR` should read
   `100% GPU`.

### 6.3 Pull and smoke-test the model

1. `ollama pull qwen2.5vl:7b` (Q4_K_M, ~6 GB download, 125K context, **text + image** input —
   [ollama.com/library/qwen2.5vl](https://ollama.com/library/qwen2.5vl/tags)).
2. Quick text sanity check: `ollama run qwen2.5vl:7b "sag hallo auf Englisch"`.
3. Vision sanity check via `/v1` with the stock `openai` client (a ~10-line throwaway) — send
   one page image and confirm it OCRs German text. This proves the *exact* call path proto
   02's `main.py` uses before running the full spike.
4. `ollama ps` → note VRAM used and the GPU/CPU split (feeds §4a; a 7B Q4 should sit fully on
   the GPU well under 12 GB).

### 6.4 Python environment

As proto 02 (§5 steps 3–4): fresh venv, `pip install -r requirements.txt`. **No API key or
billing** — the "key" is the ignored dummy string `ollama`.

### 6.5 Context length & VRAM tuning (do NOT skip — silent truncation risk)

On a 12 GB card Ollama's `OLLAMA_CONTEXT_LENGTH=0` sentinel resolves to a **default context of
only 4096 tokens** (the runtime picks 4K below 23 GiB VRAM, 32K at 23 GiB+). That is dangerous
for *this* scenario: a Qwen2.5-VL page image expands to hundreds–thousands of context tokens,
and proto 02 measured ~2 700 text-prompt tokens + ~1 100 output on a 2-page doc — so a
2-page scan **overruns 4096 and Ollama silently truncates the input**, quietly degrading OCR
and Understanding with no error. This would poison the quality comparison in §4.

Critically, **the OpenAI `/v1` endpoint ignores `num_ctx`** (it's not an OpenAI parameter), so
this *cannot* be fixed from `main.py`'s request — it must be set **server-side** on
`ollama serve`:

- `OLLAMA_KV_CACHE_TYPE=q8_0` — the KV cache grows linearly with context and would otherwise
  blow the VRAM headroom (7B Q4 weights are ~5.5 GB of the ~10.8 GB available); `q8_0` roughly
  halves the KV cache for negligible quality loss.
- `OLLAMA_FLASH_ATTENTION=1` — **set explicitly.** A quantised KV cache requires flash
  attention; do not rely on it being auto-enabled (it was not reliably on for the recorded
  runs, so it is exported alongside the other two rather than assumed).
- `OLLAMA_CONTEXT_LENGTH=32768` — **empirically fits 100% on GPU on this 12 GB card.**
  Measured: `qwen2.5vl:7b` with `OLLAMA_KV_CACHE_TYPE=q8_0` at 32768 context reports
  `ollama ps` → `100% GPU`, **6.5 GB** resident (vs 5.5 GB at the 4096 default — the +1 GB is
  the q8_0 KV cache), well under the ~10.8 GiB available. So context is *not* the binding
  constraint here and 32768 can stand (it comfortably exceeds any 2–3 page doc's prompt
  tokens, killing the truncation risk).

  Validate whenever the model/quant/context changes, and don't trust a cold measurement:
  1. `ollama ps` → `PROCESSOR` must read **`100% GPU`** (anything else = CPU offload → step the
     context down until it's fully on GPU).
  2. Measure tok/s **warm, on a real ~1000-token generation** (`ollama run ... --verbose`
     prints `eval rate`). A 10-token `/api/generate` warmup right after load is *not* valid —
     it includes one-time CUDA-graph build and is far too short (this bit us once: a warmup
     read 2.45 tok/s while the warm on-GPU rate is tens of tok/s).
  3. Keep the §4a `prompt_tokens < context_length` tripwire as the real truncation guard.

  Only if a bigger model/context ever *does* spill: step context down, or lower
  `PDF_RENDER_DPI` to shrink image tokens — that context/DPI/on-GPU-speed trade-off is a
  finding worth recording for §4.

**Seam wrinkle to record for ADR-0001 (analogous to proto 02's `reasoning_effort` note):**
context length is an Ollama-ism configured on the *server*, not via the OpenAI request — the
cloud path had no such knob. The adapter must treat "max context" as a deployment/config
property of a provider profile, not a per-call parameter. Log the active `OLLAMA_CONTEXT_LENGTH`,
`OLLAMA_FLASH_ATTENTION`, and `OLLAMA_KV_CACHE_TYPE` in `run-log.jsonl` so every run's context
budget is attributable.

## 7. Model & runtime choice

**Model: `qwen2.5vl:7b`** (Qwen2.5-VL-7B-Instruct, Q4_K_M via Ollama). Rationale:

- **Vision is mandatory here.** proto 02's scenario feeds *page images*; a text-only
  Qwen2.5-7B (the model the #2 research pinned for the general slot) cannot do this scenario.
  Qwen2.5-**VL**-7B is the vision-capable sibling and the smallest Qwen that reads the pages
  itself. This is a deliberate, recorded deviation from the research's text-model pin —
  because extraction-from-images (proto 02's design) demands it.
- **Fits the 12 GB card comfortably.** Q4_K_M is ~6 GB on disk (~5–6 GB resident + vision
  encoder/context), leaving headroom — matching the research's "7-8B Q4 ≈ 5-6 GB, comfortable,
  ~70-77 tok/s" prediction. ([qwen2.5vl tags](https://ollama.com/library/qwen2.5vl/tags))
- **Apache-2.0 lineage** (Qwen2.5 7B/14B), the licensing the research prefers for eventual
  commercialisation.
- **125K context** — ample for multi-page scans (many image parts + text).

**Benchmark alternatives beside the default** (model is an env var, as in proto 02):

- `qwen2.5vl:7b-q8_0` (~9.4 GB) — quality-vs-VRAM probe; still fits 12 GB, tests whether Q4
  quantisation is what's hurting German-legal fidelity.
- `qwen2.5vl:32b` (21 GB) — **won't fit**; note as the "needs a bigger card" data point, do
  not run (heavy CPU offload → impractical, per the research).
- Cross-reference every run against **proto 02's `gpt-5-mini` output on the same PDF** — that
  cloud result is the quality yardstick this local spike is measured against.

**Runtime: Ollama, not vLLM** (for this spike). GGUF Q4 via Ollama/llama.cpp fits the 12 GB
card, whereas vanilla vLLM FP16 will not fit a 7B in 12 GB (it needs an AWQ/GPTQ quant and is
fussier to stand up on WSL). Ollama is drop-in OpenAI-compatible, bundles its own CUDA
runtime (minimal WSL setup), and its vision support covers Qwen2.5-VL. vLLM remains the
documented production/alternative runtime (better batched throughput) but is out of scope
here per §1.

**Structured-output caveat (the headline risk).** Ollama's *native* structured output is the
`format` field taking a JSON schema
([Ollama structured outputs](https://docs.ollama.com/capabilities/structured-outputs)); its
OpenAI-compat `response_format: json_schema` handling has been reported as ignored on some
models ([ollama#10001](https://github.com/ollama/ollama/issues/10001)), though
`client.beta.chat.completions.parse(response_format=Model)` against `/v1` has been reported
working. §1.2 / §3 make this a *tested* path with an explicit fallback, not an assumption —
and whatever we learn here is the concrete design input for the adapter's documented
JSON-mode fallback in ADR-0001.
