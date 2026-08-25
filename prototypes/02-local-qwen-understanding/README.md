# Prototype 02b — Local Qwen understanding spike

Runnable spike for issue [#2](https://github.com/sergiunagy/docparse/issues/2), local-swap
arm. Same scenario as [`../02-openai-understanding/`](../02-openai-understanding/README.md),
but pointed at a **locally hosted Qwen3-VL** (`qwen3-vl:8b-instruct`) via Ollama's OpenAI-compatible `/v1` surface —
to test the ADR-0001 claim that swapping cloud → local is a `base_url` + model-name change.
Renders a PDF's pages to images, sends them in **one** Chat Completions call, and reports the
structured Understanding plus a per-document **local-performance** breakdown (VRAM, load/eval
time, tok/s, latency — **no `$` cost**, local inference is free). Full rationale in
[`PLAN.md`](./PLAN.md).

## Prerequisites — local GPU stack (PLAN.md §6)

You must have the local stack up **before** running this:

1. RTX 3080 Ti visible in WSL: `nvidia-smi` lists the card with 12 GB.
2. Ollama running with the **server-side runtime tuning** (not optional — PLAN.md §6.5).
   These are the exact env vars used for the recorded runs:
   ```bash
   export OLLAMA_CONTEXT_LENGTH=32768   # 4096 default hard-fails multi-page image prompts
   export OLLAMA_FLASH_ATTENTION=1      # required for the quantised KV cache
   export OLLAMA_KV_CACHE_TYPE=q8_0     # fit the 12 GB card
   ollama serve
   ```
3. Model pulled: `ollama pull qwen3-vl:8b-instruct` (prefer the **Instruct**/non-thinking
   build — the plain `qwen3-vl:8b` is the Thinking build whose reasoning trace can't be
   disabled here and roughly doubles latency).
4. `ollama ps` → `PROCESSOR` reads **`100% GPU`** and `CONTEXT` is `32768`.

## Setup (pyenv + venv, Python 3.13)

```bash
cd prototypes/02-local-qwen-understanding
~/.pyenv/versions/3.13.2/bin/python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Config (no secrets — the API key is the ignored dummy string `ollama`):

```bash
cp .env.example .env   # defaults already point at local Ollama; edit only if endpoint differs
```

`.env` keys: `OPENAI_BASE_URL` (`http://localhost:11434/v1`), `OPENAI_API_KEY` (`ollama`),
`OPENAI_MODEL` (`qwen3-vl:8b-instruct`), `OLLAMA_STRUCTURED_MODE` (`auto`|`json_schema`|`ollama_format`),
`PDF_RENDER_DPI` (`150`), plus `OLLAMA_CONTEXT_LENGTH` / `OLLAMA_FLASH_ATTENTION` /
`OLLAMA_KV_CACHE_TYPE` (logged for attribution; these are set server-side on `ollama serve`,
not per-request — PLAN.md §6.5).

## Run

Put the (redacted) German PDFs in `data/` (git-ignored — the same samples as proto 02) and
point the script at one:

```bash
python main.py data/fa_bescheid_2021.pdf
```

Outputs go to `out/` (git-ignored):

- `out/<pdf>.json` — the schema-adherent Understanding
- `out/<pdf>.md` — human-readable summary + run stats
- `out/run-log.jsonl` — one line per call: token counts, tok/s, load/eval time, VRAM,
  GPU/CPU split, latency, and which structured-output path fired (**no `$` — free at inference**)

The console also prints the **drift probe** (`action_plan` steps with
`grounded_in_document: false`), the structured-output path used, and a loud **truncation
warning** if `prompt_tokens >= context_length` (the silent-truncation tripwire from §6.5).

## Benchmarking alternatives

Model and structured mode are env vars, so re-run without code changes:

```bash
OPENAI_MODEL=qwen3-vl:8b          python main.py data/fa_mahnung_30_03.pdf  # Thinking build (slower)
OLLAMA_STRUCTURED_MODE=ollama_format python main.py data/fa_mahnung_30_03.pdf
OLLAMA_STRUCTURED_MODE=json_schema   python main.py data/fa_mahnung_30_03.pdf
```

Each run appends to `out/run-log.jsonl`, so numbers accumulate for the cloud↔local comparison.

## Notes / caveats

- **Not production code.** One file, no ports, disposable (see `../README.md`). It is a
  deliberate near-copy of proto 02's `main.py`; the size of that diff is itself a finding.
- **No `$` cost.** Local inference is free; the cost counter is replaced by a local-perf one.
- **tiktoken text estimate is NOT Qwen-exact** — logged as a sanity signal only.
- With image input the model OCRs the pages itself, so `source_quote` may be paraphrased
  rather than an exact substring — treat quote-exactness as an observation, not a guarantee.
- Never commit `data/`, `out/`, `.env`, or `.venv/` (all git-ignored).
