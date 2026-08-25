# Prototype 02b — findings (local Qwen understanding spike)

**Question (PLAN.md §1):** does the ADR-0001 "swap cloud → local is a `base_url` + model-name
change" claim survive contact with a locally hosted Qwen2.5-VL on an RTX 3080 Ti, and does
Structured Outputs survive the swap?

**Run:** 2026-08-24, WSL2 / RTX 3080 Ti (12 GB), Ollama 0.32.15, `qwen2.5vl:7b` (Q4_K_M),
`OLLAMA_CONTEXT_LENGTH=32768 OLLAMA_KV_CACHE_TYPE=q8_0`, all four redacted Finanzamt PDFs
(same samples as proto 02). Artefacts in `out/` (git-ignored).

## Verdict against PLAN.md §4 success criteria

- **Swap verdict — mostly a config change.** The `openai` SDK drove the whole pass against
  `http://localhost:11434/v1` with a dummy key. The diff vs proto 02's `main.py` is ~249
  changed lines, but almost all of it is the *counter swap* ($-cost → local-perf: VRAM/tok/s
  helpers) and the structured-mode strategy block — **not** the call itself. The actual
  request (messages, image parts, `.parse(response_format=...)`) is unchanged. Genuine seam
  costs recorded: (1) the reasoning-model branch was dropped (Qwen isn't GPT-5); (2) image
  parts drop the `detail` field (Ollama ignores it); (3) **context length is a server-side
  Ollama-ism** (`OLLAMA_CONTEXT_LENGTH` on `ollama serve`), invisible to the `/v1` request —
  the adapter must model "max context" as a provider-profile property, not a per-call param.

- **Structured-output result → outcome (a): native `json_schema` parity.**
  `client.beta.chat.completions.parse(response_format=Understanding)` worked **unmodified**
  against Ollama `/v1`, schema-adherent on all 4 docs across repeated runs. No fallback was
  needed. The `OLLAMA_STRUCTURED_MODE=ollama_format` native path (`extra_body={"format": …}`)
  was tested and is **markedly worse**: it returned JSON (a) inside a ```json fence,
  (b) wrapped in a single-element array, (c) with unescaped control characters, and worst of
  all (d) **dropped required fields** (`rationale`) — i.e. the native `format` field is *not*
  strictly schema-enforcing here. **Design input for ADR-0001's JSON-mode fallback:** the
  `.parse` json_schema path is the good path on Ollama; the native fallback needs fence
  stripping + list unwrap + lenient parse + a *re-ask/repair* loop, because it can silently
  omit fields.

- **Local performance on the 3080 Ti (matches the research prediction).** 100% GPU on every
  run, ~10.4–10.5 GB VRAM resident during inference (fits comfortably under 12 GB), context
  correctly 32768 (no truncation — `prompt_tokens` 8k–16k stayed well under budget). Warm
  wall-clock latency 5.6–19.9 s/doc; tok/s (wall-clock derived) 21–85 depending on prompt
  size. NB: Ollama's `load_duration`/`eval_duration` are **not surfaced via `/v1`**, so tok/s
  here is wall-clock-derived, not `eval_duration`-derived.

- **Drift finding.** 2 of 8 total `action_plan` steps came back `grounded_in_document:false`
  (aufford 0/1, bescheid 1/2, mahnung 1/2, vorauszahlung 0/3) — comparable in shape to the
  cloud spike's behaviour; the drift steps were plausible "review your statements"-type
  suggestions beyond the text, honestly self-labelled.

- **Quality read vs proto 02 — done (2026-08-25): local ≈ cloud.** The deferred head-to-head
  was run with the current Qwen build, **`qwen3-vl:8b-instruct`** (Q4_K_M), against
  `gpt-5-mini` on the same four PDFs. Verdict: **quality parity on this task.** The local
  model produces coherent German-legal English summaries and sane Key-Information / Obligation
  extraction on par with the cloud model, with comparable drift behaviour (see below). The
  trade is cost/latency, not fidelity: `gpt-5-mini` ≈ \$0.004/doc at ~14 s; `qwen3-vl:8b-instruct`
  is **\$0 and fully on-box** at ~3× latency (~32–58 s/doc, ~11 GB VRAM resident, 100 % GPU,
  60–78 tok/s). This resolves the last open success criterion for the local arm of #2.

  Two operational findings from the comparison runs:
  - **Use the Instruct (non-thinking) build.** The thinking `qwen3-vl:8b` inflated completions
    to 12k–17k tokens and 100–260 s/doc for the same inputs; `-instruct` brought that back to
    ~2.3k–3.6k completion tokens and ~32–58 s/doc with no quality loss on this task.
  - **`OLLAMA_CONTEXT_LENGTH=32768` is mandatory.** The 4096 default hard-fails these
    2–4-page image prompts with `exceed_context_size_error` (~4.1k prompt tokens/page); it must
    be raised server-side (a provider-profile property, per the swap verdict above).

  Exact server-side config used for the recorded runs (set on `ollama serve`, not per-request):

  ```bash
  export OLLAMA_CONTEXT_LENGTH=32768   # raise from the 4096 default
  export OLLAMA_FLASH_ATTENTION=1      # required for the quantised KV cache
  export OLLAMA_KV_CACHE_TYPE=q8_0     # fit the 12 GB RTX 3080 Ti
  ```

## Prompt divergence from proto 02 (obligation translation)

Qwen-7B exposed an ambiguity in proto 02's verbatim prompt: rule 3 only said `source_quote`
is "the German text you read it from" and never said `obligations[].text` must be English, so
Qwen **copied the German source_quote into `text`** (both fields identical German).
`gpt-5-mini` had papered over this by inferring English from context. Fixed by making rule 3
explicit — `text` = English translation, `source_quote` = original German, and the two MUST
differ. This is a **deliberate divergence from the "verbatim prompt" isolation**, and itself a
finding: a smaller local model needs more prescriptive prompting than the cloud model did for
the same task.

## One-paragraph verdict (for issue #2 / ADR-0001)

The local swap is essentially the config change ADR-0001 promised: the same `openai` SDK call,
including strict Structured Outputs via `.parse`, ran unmodified against local Ollama and
returned schema-adherent JSON on a 7B Q4 model that fits the 12 GB card at 100% GPU. The real
seam costs are small and now concrete: drop the reasoning-model knobs, treat max-context as a
server-side provider-profile property (not a per-call arg), and — critically — the adapter's
documented JSON-mode fallback must assume the *native* Ollama `format` path is non-strict
(fenced/array-wrapped/field-dropping) and repair around it, whereas the OpenAI-compat
json_schema path is the reliable one to prefer.
