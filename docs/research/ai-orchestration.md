# What sits behind the AI Provider adapter for the MVP

Research for [sergiunagy/docparse#2](https://github.com/sergiunagy/docparse/issues/2).
Companion to [`docs/adr/0001-ai-provider-adapter.md`](../adr/0001-ai-provider-adapter.md).

This is the first note under `docs/research/`; there was no prior convention, so this
directory is the sensible home for reading notes that back a decision (decisions
themselves live in `docs/adr/`).

## Question and constraints

ADR 0001 fixes the *seam*: all AI Provider access goes through one provider-agnostic
port, and swapping a cloud provider for a self-hosted/local model must be a
configuration + adapter change, not a rewrite. This note answers the deferred question:
**what technology sits behind that seam for the MVP** - raw provider SDKs, a routing layer
(LiteLLM), or an agent/orchestration framework (LangChain, LlamaIndex)?

Evaluation axes (from the ticket): portability to local models (Ollama / vLLM-class),
streaming, structured output, cost/latency, and how much of the
translate + extract + summarise + Q&A flow each option *owns* versus leaves to our own
code. Stack is Python + FastAPI.

**Added requirement (post-initial-research):** the model should be **free of charge**
wherever it is hosted, and the paid path needs a concrete **per-document cost** estimate.
Both are addressed in [Cost per document, and the free-of-charge preference](#cost-per-document-and-the-free-of-charge-preference) below; they sharpen but do not change the port recommendation.

## The fact that decides most of it: the OpenAI Chat Completions wire format is the portability substrate

The local-swap requirement is not really a question about a Python library - it is a
question about a *wire protocol*. The local runtimes we would realistically target both
expose the OpenAI Chat Completions HTTP surface:

- **Ollama** ships partial OpenAI compatibility at `/v1/chat/completions`, and its own
  docs list the supported features as chat completions, **streaming**, **JSON mode**,
  reproducible outputs, vision, and tools. You point the stock `openai` client at
  `http://localhost:11434/v1/` with a dummy key.
  ([ollama/ollama `docs/api/openai-compatibility.mdx`](https://github.com/ollama/ollama/blob/main/docs/api/openai-compatibility.mdx))
- **vLLM** runs an OpenAI-compatible server (`/v1/chat/completions`, `/v1/completions`)
  and supports **structured outputs by default** - via the portable
  `response_format: {type: "json_schema", ...}` field, plus vLLM-specific
  `structured_outputs` constraints (json / choice / regex / grammar) passed through
  `extra_body`.
  ([vLLM OpenAI-Compatible Server](https://docs.vllm.ai/en/latest/serving/online_serving/openai_compatible_server/),
  [vLLM Structured Outputs](https://docs.vllm.ai/en/latest/features/structured_outputs/))

Consequence: **if our adapter is defined in terms of the OpenAI Chat Completions
contract (messages in, streamed deltas out, `response_format` json_schema for structured
output), the "swap to local" path is a base-URL + model-name change.** Every option
below is judged first on how cleanly it preserves that contract, because that contract is
what makes the swap cheap.

## Option A - Raw provider SDKs (e.g. `openai`, `anthropic`)

**Portability.** Excellent *if* we standardise on the `openai` SDK, because Ollama and
vLLM are drop-in for it (change `base_url`, keep the code). The catch is that "raw SDKs"
plural means one SDK per vendor; if the cloud MVP uses Anthropic's SDK, its message
shape, streaming events, and tool/JSON semantics differ from OpenAI's, and *we* absorb
that divergence in the adapter. Using the `openai` SDK as the single client (cloud
OpenAI-compatible endpoint now, local OpenAI-compatible endpoint later) is the leanest
portable choice.

**Streaming / structured output.** First-class and native: `stream=True` yields Chat
Completion chunks; `response_format` json_schema is the provider feature, so we are not
depending on a library to emulate it.

**Cost / latency.** Lowest overhead - no extra process, no translation layer, minimal
dependency surface. Easiest to reason about for latency and to keep small for a personal
app.

**How much of the flow it owns.** *None.* translate / extract / summarise / Q&A are all
our own prompt + orchestration code. That is more code for us, but it is exactly the code
that encodes docparse's domain (layout-faithful extraction, Confidence checks, Obligation
extraction) - logic we would not want a framework to own anyway.

## Option B - Routing layer: LiteLLM

LiteLLM gives "a single, unified interface to call 100+ LLMs ... using the OpenAI format",
with a consistent output shape across providers and built-in retry/fallback via its
Router. ([LiteLLM Getting Started](https://docs.litellm.ai/docs/))

**Portability.** Strong and explicitly two-shaped:

- *SDK mode:* `litellm.completion(model="ollama_chat/llama3.2", api_base="http://...:11434")`
  talks to a local Ollama model with the same call you use for `openai/gpt-4o`.
  ([LiteLLM Ollama provider](https://docs.litellm.ai/docs/providers/ollama))
- *Proxy mode:* a self-hosted OpenAI-compatible gateway; you map an alias like
  `llama3.2 -> ollama_chat/llama3.2` in `config.yaml`, and any OpenAI client (including
  the stock `openai` SDK) points at it. This makes the local swap a *server-config* change
  with **zero application code change**. ([LiteLLM Getting Started](https://docs.litellm.ai/docs/),
  [routing local Ollama through the proxy](https://github.com/BerriAI/litellm/discussions/12151))

**Streaming / structured output.** `stream=True` yields `ModelResponseStream` chunks in
OpenAI shape; structured output via json_schema is supported and normalised across
providers. ([LiteLLM Getting Started](https://docs.litellm.ai/docs/))

**Caveat worth recording.** LiteLLM's local-model support has sharp edges: it consults an
internal model registry (`model_prices_and_context_window.json`) and can mis-detect
capabilities for *unmapped* local models - e.g. `supports_function_calling()` defaulting
to `False`, and provider routing overriding an explicit `api_base` in some cases.
([litellm#23054](https://github.com/BerriAI/litellm/issues/23054),
[litellm#9602](https://github.com/BerriAI/litellm/issues/9602)). Usable, but validate the
exact local model before trusting capability flags.

**Cost / latency.** SDK mode adds a thin in-process normalisation layer. Proxy mode adds
a network hop and a service to operate - real value at scale (virtual keys, budgets, cost
tracking, central logging) but arguably more than a single-family MVP needs on day one.

**How much of the flow it owns.** *None of the domain flow.* LiteLLM owns
provider-normalisation, routing, fallback, and (optionally) cost tracking. translate /
extract / summarise / Q&A stay ours. This is the appealing property: it deepens the
*adapter boundary* without colonising our application logic.

## Option C - Agent / orchestration framework: LangChain or LlamaIndex

**LangChain.** Offers a genuinely provider-agnostic model layer: `init_chat_model("openai:...")`
returns a `BaseChatModel`, every provider implements the same interface, and the docs
advertise swapping providers without rewriting application logic, plus uniform streaming
(`model.stream(...)`) and `with_structured_output` / `create_agent` structured output.
([LangChain providers-and-models](https://docs.langchain.com/oss/python/concepts/providers-and-models),
[init_chat_model source](https://github.com/langchain-ai/langchain/blob/master/libs/langchain_v1/langchain/chat_models/base.py),
[structured output](https://docs.langchain.com/oss/python/langchain/structured-output))
For a *local* model you either use a local provider package or point `ChatOpenAI` at an
OpenAI-compatible base URL. Structured output quality is provider-dependent: LangChain
picks `ProviderStrategy` (native json_schema) for providers that support it and falls back
to `ToolStrategy` (tool-call emulation) otherwise - so a weaker local model degrades to the
emulated path.

**LlamaIndex.** Its `OpenAILike` LLM is "a thin wrapper around the OpenAI model that makes
it compatible with 3rd party tools that provide an openai-compatible api" - set
`api_base`, `api_key`, `is_chat_model`, `is_function_calling_model` and it drives Ollama,
vLLM, or LocalAI. LlamaIndex's real value is *above* the model: `VectorStoreIndex`,
`as_query_engine()`, retrievers - i.e. it wants to own RAG / Q&A.
([LlamaIndex OpenAILike](https://developers.llamaindex.ai/python/framework-api-reference/llms/openai_like/),
[LocalAI integration](https://developers.llamaindex.ai/python/framework/integrations/llm/localai/),
[vLLM + LlamaIndex RAG example](https://github.com/vllm-project/vllm/blob/main/examples/applications/rag/retrieval_augmented_generation_with_llamaindex.py))

**Portability.** Good in principle (both abstract providers; both reach local via
OpenAI-compatible endpoints). But the abstraction is a *framework object model*, not the
OpenAI wire contract - so portability now depends on the framework's per-provider
integration keeping parity, which is a bigger moving target than "does this endpoint speak
`/v1/chat/completions`".

**Streaming / structured output.** Both support streaming and structured output, with the
same caveat as LangChain: on capability-limited local models, structured output may fall
back to prompt/tool emulation rather than native constrained decoding.

**How much of the flow it owns.** *A lot* - and that is the problem for docparse. These
frameworks want to own chunking, retrieval, agent loops, prompt templates, and Q&A. For a
one-Document-at-a-time understanding flow with bespoke domain rules (Confidence /
plausibility checks, layout-faithful Extraction, Obligation extraction from text alone per
`CONTEXT.md`), most of that machinery is either unused or something we would have to fight.
Adopting a framework here means adopting its abstractions, upgrade cadence, and breaking
changes across the whole flow - the opposite of a thin swappable seam. It also pulls the
provider dependency *upward* into application code unless we very carefully wrap it, which
partly defeats ADR 0001.

## Evaluation summary

| Axis | Raw `openai` SDK | LiteLLM (SDK / proxy) | LangChain / LlamaIndex |
| --- | --- | --- | --- |
| Local swap (Ollama/vLLM) | base-URL + model change | best: alias in `config.yaml`, no app change (proxy) | via provider pkg or OpenAI-compat base URL |
| Portability *mechanism* | the OpenAI wire contract itself | OpenAI contract + normalisation across 100+ providers | framework object model (per-provider parity) |
| Streaming | native | native (OpenAI-shaped chunks) | supported |
| Structured output | native json_schema | normalised json_schema | supported; may degrade to tool/prompt emulation locally |
| Cost / latency | lowest overhead | thin (SDK) / +1 hop & a service (proxy) | heaviest; framework in hot path |
| Owns domain flow | nothing (we own it) | nothing (we own it) | wants to own RAG/agents/Q&A |
| Main risk | multi-vendor divergence if not OpenAI-only | local capability mis-detection (registry) | framework lock-in, churn, dependency creep |

## Recommendation

**Behind the seam, define the adapter in terms of the OpenAI Chat Completions contract,
and back it with the `openai` SDK for the MVP - with LiteLLM as the pre-designed drop-in
when we need multi-provider routing or a self-hosted gateway. Do *not* adopt an
agent/orchestration framework as the AI Provider layer.**

Rationale: the local-swap requirement is satisfied by a *wire protocol* (OpenAI-compatible
`/v1/chat/completions`), which both Ollama and vLLM already speak, so the cheapest durable
boundary is that contract - not a framework's object model. Raw `openai` SDK gives native
streaming and native `response_format` json_schema with the least overhead and leaves 100%
of the domain flow (translate / extract / summarise / Q&A) in our own code, which is where
docparse's real value (layout-faithful Extraction, Confidence checks, Obligation
extraction) lives anyway. LangChain/LlamaIndex would try to own that flow and pull the
provider dependency back up into application code, working against ADR 0001.

### Adapter interface shape (the port)

Keep it small, provider-shaped-but-not-provider-specific, and streaming-first. Sketch:

```python
class ChatMessage(TypedDict):
    role: Literal["system", "user", "assistant"]
    content: str

class AIProvider(Protocol):
    async def complete(
        self,
        messages: list[ChatMessage],
        *,
        response_schema: dict | None = None,   # JSON Schema -> response_format json_schema
        temperature: float = 0.0,
        max_tokens: int | None = None,
    ) -> AIResult: ...                           # text + parsed (if schema) + usage/cost/latency

    def stream(
        self,
        messages: list[ChatMessage],
        *,
        temperature: float = 0.0,
        max_tokens: int | None = None,
    ) -> AsyncIterator[AITextDelta]: ...          # for translation/summary/Q&A UX
```

Design notes that protect the swap:

- **Messages in, deltas out.** Mirror Chat Completions so a local endpoint is a config
  change, not a reshape.
- **Structured output is `response_schema` (JSON Schema), never a vendor-specific object.**
  Maps to `response_format={"type": "json_schema", ...}` on OpenAI *and* vLLM; degrade to
  a documented JSON-mode fallback for a weaker local model (this is the one place local
  parity may need a code path, so make it explicit in the adapter, not scattered).
- **No LangChain/LlamaIndex/provider types cross this boundary.** Application code depends
  only on `AIProvider`, `ChatMessage`, `AIResult` - satisfying ADR 0001 literally.
- Prompt construction and the translate/extract/summarise/Q&A orchestration live *above*
  the port, in docparse's own service code.

### Concrete config, and the local-swap path spelled out

Construct the OpenAI client from config only:

```python
# cloud MVP
client = OpenAI(base_url="https://api.openai.com/v1", api_key=SETTINGS.api_key)
# or any OpenAI-compatible cloud provider via its base_url
```

Swap to local - **no application code change**, only env/config:

- **Ollama:** `base_url="http://localhost:11434/v1"`, `api_key="ollama"` (ignored),
  `model="<local-model>"`. Streaming and JSON mode are supported.
  ([Ollama OpenAI compatibility](https://github.com/ollama/ollama/blob/main/docs/api/openai-compatibility.mdx))
- **vLLM:** `base_url="http://<host>:8000/v1"`, `model="<served-model>"`; structured output
  via the same `response_format` json_schema field.
  ([vLLM OpenAI-Compatible Server](https://docs.vllm.ai/en/latest/serving/online_serving/openai_compatible_server/))

If/when we need multi-provider routing, fallback, or a hardened self-hosted gateway,
**introduce LiteLLM without touching application code**: either swap the adapter's internals
to `litellm.completion(...)`, or (cleaner operationally) run the **LiteLLM proxy** and just
repoint `base_url` at it, mapping model aliases to `ollama_chat/...` or `openai/...` in
`config.yaml`. Because the adapter already speaks the OpenAI contract, LiteLLM slots in
underneath it. ([LiteLLM Getting Started](https://docs.litellm.ai/docs/),
[LiteLLM Ollama](https://docs.litellm.ai/docs/providers/ollama))
When routing to unmapped local models through LiteLLM, verify capability flags
(function calling, context window) rather than trusting registry defaults.
([litellm#23054](https://github.com/BerriAI/litellm/issues/23054))

**One-line summary:** make the OpenAI Chat Completions contract the port, back it with the
`openai` SDK now, keep LiteLLM as the sanctioned drop-in for later, and keep the
translate/extract/summarise/Q&A orchestration in our own code - never behind a framework.

## Cost per document, and the free-of-charge preference

This section answers two questions the initial research left open: (1) how the
free-of-charge preference reconciles with the recommendation, and (2) what one average
document actually costs on the paid OpenAI path.

### Free of charge, reconciled with the seam

- The adapter's whole point (ADR 0001) is that the same application code runs against a
  local OpenAI-compatible endpoint. A **self-hosted Ollama / vLLM model is free of charge
  at inference** (you pay only for hardware and electricity you already own), so the
  free-of-charge preference is fully satisfied by the *local* path the adapter already
  targets. This is the recommended end state for cost and for the ADR 0001 privacy driver
  at once.
- **Free cloud tiers exist but carry a disqualifying caveat for this app.** Google's
  Gemini free tier is `$0`, but its own pricing table marks "Used to improve our products:
  **Yes**" for the free tier, i.e. your prompts and responses feed Google's training, and
  it is hard rate-limited. Sending official financial/legal documents into a training
  pipeline conflicts directly with the data-sensitivity driver behind ADR 0001. Groq and
  OpenRouter free models vary similarly in data handling. So a *free cloud* model is not a
  safe default for real documents.
- **Net:** for free *and* private, the answer is **local (Ollama/vLLM)**, reached through
  the same adapter. The paid cloud path below is an optional low-cost bridge while
  standing up the MVP, not the destination.

### What one average document costs on the paid OpenAI path

Assumptions for an average Finanzamt item (a notification, a tax-return request, or an
assessment confirmation): about 2 pages, roughly 1,500 words of German, which tokenises to
about 3,000 source tokens (German runs higher tokens-per-word than English). The one-time
"understanding" pass is translation + key-info/obligation extraction + summary; interactive
Q&A is billed separately and is cheap.

| Pipeline call | Input tokens | Output tokens |
| --- | --- | --- |
| Translation (DE -> EN, with glossary) | ~3,800 | ~2,500 |
| Key info + obligations (structured JSON) | ~3,500 | ~500 |
| Plain-English summary | ~3,200 | ~400 |
| **Total per document** | **~10,500** | **~3,400** |

Applying current OpenAI list prices (per 1M tokens; fetched 2026-08-21 from
<https://openai.com/api/pricing/>):

| Model | Input | Output | Approx cost / document |
| --- | --- | --- | --- |
| gpt-4o-mini | $0.15 | $0.60 | **~$0.004** (under half a cent) |
| gpt-4.1-mini | $0.40 | $1.60 | **~$0.01** (about one cent) |
| gpt-4o | $2.50 | $10.00 | **~$0.06** |

So a family processing ~30 documents/month costs roughly **$0.12/month on gpt-4o-mini** or
**~$1.80/month on gpt-4o**. Each follow-up Q&A question adds about **$0.0006** on gpt-4o-mini
(document context in, short answer out) and drops further with prompt/context caching, where
cached input is ~10x cheaper than fresh input. Cost is therefore *not* a constraint on the
paid path; model *quality* on German legal register is the real lever (see the translation
research: small/mini and small local models are weaker on Germanic legal text, so budget
for occasional escalation to a stronger model or a dedicated MT fallback).

### Recommendation update (unchanged port, sharpened model choice)

Keep the OpenAI Chat Completions contract as the port. For the model behind it, prefer, in
order:

1. A **free self-hosted** OpenAI-compatible model (Ollama/vLLM) as the target that
   satisfies free-of-charge *and* privacy at once.
2. If a cloud model is used to bootstrap the MVP, **gpt-4o-mini** at about half a cent per
   document is the pragmatic paid bridge, escalating to gpt-4o only for documents the mini
   model handles poorly.
3. **Avoid free cloud tiers** (Gemini/Groq/OpenRouter free) for real documents, because
   their terms may use your data for training.

Because the port is the OpenAI wire contract, all three are the same swap: a base-URL,
model-name, and key change, no application rewrite.

## Update: routed AI service, local hardware target, and model choice

Later constraints reshape *how* this seam is packaged and *which* models sit behind it.
None of them change the port (still the OpenAI Chat Completions contract); they promote
the routing from "later" to "now" and pin the local model.

### The AI Provider becomes a routed AI Service (not a single model)

Per the service-oriented decision (ADR 0002) and the requirement to pick the best model
*per function and per available hardware*, the port is exposed as an **AI Service** with
capability methods - `translate`, `extract_assist`, `summarise`, `answer` - rather than a
single generic `complete`. Behind those methods sits a **Model Router**: a registry that
maps `(capability, deployment/HW profile) -> (provider, model, params)`. Examples:

- `translate` + local -> OPUS-MT `de-en`; `translate` + cloud -> an LLM
- `extract_assist` / `summarise` / `answer` + local-12GB -> Qwen2.5-7B; + local-24GB -> 14B;
  + cloud -> gpt-4o-mini
- HW detection (a VRAM probe at startup) selects the fitting local variant, or falls back
  to cloud / CPU

This is exactly what LiteLLM's Router provides, so the earlier "LiteLLM as a later drop-in"
is promoted to "the routing layer is part of the AI Service now". A lightweight custom
registry over `openai`-compatible clients is an equally valid implementation; either way
the router lives *inside* the AI Service and application code only sees the capability
methods. The set and shape of those methods is an interface-design question deferred to
the service-architecture ticket, not fixed here.

### No training or fine-tuning in the MVP

Every task (translation, extraction, summary, Q&A) is an **inference** task achievable with
off-the-shelf instruction-tuned models steered by prompting: system prompts, an injected
DE->EN glossary, JSON schemas for structured output, and a few worked examples for tricky
Finanzamt layouts. The escalation ladder is prompt engineering -> few-shot -> glossary/RAG
injection -> (last resort) LoRA fine-tuning. Fine-tuning is a future lever if prompting
provably fails on the German legal register, not MVP work. A 12 GB card could do **QLoRA on
a 7B** if it ever came to that, but not full fine-tuning; we do not need either.

### Local hardware target: RTX 3080 Ti (12 GB)

The GPU is relevant for **inference**, not training - a common conflation. Local LLM
inference is memory-bandwidth bound, and the 3080 Ti (12 GB GDDR6X, 912 GB/s, 3090-class
bandwidth) is fast; its **12 GB is the binding constraint**. Fit, via Ollama / llama.cpp
GGUF (vanilla vLLM FP16 will not fit a 7B in 12 GB):

| Model class | Quant | VRAM | Fit on 3080 Ti | Speed |
| --- | --- | --- | --- | --- |
| 7-8B (Qwen2.5-7B, Llama-3.1-8B) | Q4-Q5 | ~5-6 GB | Comfortable, long context | ~70-77 tok/s |
| 14B (Qwen2.5-14B) | Q4_K_M | ~13.6 GB | Tight; cap context (~7-16k) or slight offload | ~46 tok/s |
| 32B+ | Q4 | 20 GB+ | Does not fit (heavy offload, ~4 tok/s) | impractical |

Because inference-only local hosting still costs `$0` at inference, the 3080 Ti is the
**accelerator that makes the free + fully-private local path fast enough to use**. It is
*not* an MVP requirement: the adapter lets the MVP run on cloud first and flip to local
later, so the GPU only matters once you choose the local path for privacy/cost.

### Model choice for the German-only MVP

Romanian moved to the fog, so the deciding factor that had favoured Qwen (Romanian support,
which Llama 3.1 does not officially list) no longer applies. For German -> English:

- **General-LLM slot (extract/summarise/answer):** both work; **Qwen2.5-7B/14B (Apache-2.0)**
  stays a *soft* preference over **Llama-3.1-8B (Llama Community License)** on cleaner
  licensing for eventual commercialisation. (Avoid Qwen2.5-3B / 72B - non-Apache licenses;
  the 7B/14B that fit the GPU are Apache-2.0 anyway.)
- **Translation slot:** route to a **dedicated MT model, `Helsinki-NLP/opus-mt-de-en`** -
  tiny (<1 GB), fast, strong on German, permissive - alongside the general LLM.

**"Chinese model -> data leak?" No, not when run locally.** Open-weights are inert numbers
doing matrix math; a GGUF file has no network path and cannot exfiltrate anything, whoever
trained it. The trust points are the same for any model: the (open-source, auditable)
runtime and the download source (pull official weights, verify checksums). Qwen's
China-origin alignment/censorship concerns are about politically-sensitive Chinese topics,
irrelevant to German bureaucratic/financial documents. Country of origin affects *what the
model says*, not *whether your data escapes*; local hosting keeps everything on-box.

### Cloud data-usage guarantee (OpenAI), for the paid bridge

If the paid bridge is used, OpenAI's API terms are materially stronger than Gemini's free
tier: since 2023-03-01, API data is **not used to train or improve models** unless you
explicitly opt in; inputs/outputs may sit in **abuse-monitoring logs for up to 30 days**
then are deleted (visible to limited OpenAI personnel/classifiers, never to other customers
or the public); **Zero Data Retention** removes even that for approved organisations. This
is a strong *contractual* guarantee, but not a *technical* one - the documents still transit
and briefly reside on OpenAI servers - which is exactly why local remains the privacy
destination for sensitive documents. It is, however, far safer than any free cloud tier.

## Empirical validation (prototype 02) — desk research confirmed

The recommendation above was run, not just argued, in the two arms of prototype 02
(`prototypes/02-openai-understanding/` and `prototypes/02-local-qwen-understanding/`). Both
render a real (redacted) Finanzamt PDF to page images and make **one** Structured-Outputs
(`json_schema`) Chat Completions call for the full Understanding. The findings back the desk
research:

- **The OpenAI wire format is the portability substrate — confirmed in code.** The exact same
  `openai` SDK call, including strict Structured Outputs via `client.beta.chat.completions.parse`,
  ran **unmodified** against local Ollama's `/v1` surface with a dummy key. Swapping cloud →
  local was, as ADR-0001 claimed, essentially a `base_url` + model-name change. The real seam
  costs are small and now concrete: drop the reasoning-model knobs (Qwen isn't GPT-5), image
  parts drop the `detail` field (Ollama ignores it), and **max context is a server-side
  provider-profile property** (`OLLAMA_CONTEXT_LENGTH`), invisible to the per-call request — the
  adapter must model it as a profile property, not a per-call arg. The exact server-side config
  used for the recorded local runs (set on `ollama serve`, not per-request):

  ```bash
  export OLLAMA_CONTEXT_LENGTH=32768   # 4096 default hard-fails with exceed_context_size
  export OLLAMA_FLASH_ATTENTION=1      # required for the quantised KV cache
  export OLLAMA_KV_CACHE_TYPE=q8_0     # fit the 12 GB RTX 3080 Ti
  ```

- **Structured Outputs survive the swap.** The `.parse(response_format=…)` json_schema path was
  schema-adherent on all sample docs across repeated runs, on both cloud and a local 8B Q4 model.
  The *native* Ollama `format` path is markedly worse (fenced/array-wrapped output, dropped
  required fields) — so the adapter's JSON-mode fallback should prefer the OpenAI-compat
  json_schema path and treat the native path as non-strict, repairing around it.

- **Quality parity, local ≈ cloud, on this task.** A head-to-head on the same PDFs found
  `qwen3-vl:8b-instruct` (local, RTX 3080 Ti, Q4_K_M) produces coherent German-legal English
  summaries and sane Key-Information / Obligation extraction **on par with `gpt-5-mini`** (cloud).
  Drift (ungrounded `action_plan` steps) was comparable in shape on both. Cost/latency trade:
  gpt-5-mini ≈ \$0.004/doc at ~14 s; the local model is **\$0 and fully on-box** at ~3× latency
  (~32–58 s/doc, ~11 GB VRAM, 100 % GPU). Two operational findings: the **Instruct
  (non-thinking) build is essential** — the thinking `qwen3-vl:8b` inflated completions to
  12k–17k tokens and 100–260 s/doc — and a small local model needs **more prescriptive
  prompting** than the cloud model (Qwen copied German into an English field until the prompt
  was made explicit).

**Verdict:** issue #2 is validated — the raw `openai` SDK behind the adapter is sufficient for
the MVP, no router/framework was pulled in, and the local-swap requirement holds in practice.
Full run notes live in `prototypes/02-local-qwen-understanding/NOTES.md`.

## Sources

- Ollama OpenAI compatibility (features: streaming, JSON mode, tools): <https://github.com/ollama/ollama/blob/main/docs/api/openai-compatibility.mdx>
- vLLM OpenAI-Compatible Server: <https://docs.vllm.ai/en/latest/serving/online_serving/openai_compatible_server/>
- vLLM Structured Outputs (json_schema / structured_outputs): <https://docs.vllm.ai/en/latest/features/structured_outputs/>
- LiteLLM Getting Started (unified OpenAI-format interface, streaming, proxy): <https://docs.litellm.ai/docs/>
- LiteLLM Ollama provider: <https://docs.litellm.ai/docs/providers/ollama>
- LiteLLM local-model routing discussion: <https://github.com/BerriAI/litellm/discussions/12151>
- LiteLLM local-model capability-detection issues: <https://github.com/BerriAI/litellm/issues/23054>, <https://github.com/BerriAI/litellm/issues/9602>
- LangChain providers & models (provider-agnostic, swap without rewrite): <https://docs.langchain.com/oss/python/concepts/providers-and-models>
- LangChain `init_chat_model` source: <https://github.com/langchain-ai/langchain/blob/master/libs/langchain_v1/langchain/chat_models/base.py>
- LangChain structured output (Provider vs Tool strategy): <https://docs.langchain.com/oss/python/langchain/structured-output>
- LlamaIndex `OpenAILike`: <https://developers.llamaindex.ai/python/framework-api-reference/llms/openai_like/>
- LlamaIndex LocalAI integration: <https://developers.llamaindex.ai/python/framework/integrations/llm/localai/>
- vLLM + LlamaIndex RAG example: <https://github.com/vllm-project/vllm/blob/main/examples/applications/rag/retrieval_augmented_generation_with_llamaindex.py>
- OpenAI API pricing (gpt-4o, gpt-4o-mini, gpt-4.1-mini; fetched 2026-08-21): <https://openai.com/api/pricing/>
- Gemini API pricing, free tier and "used to improve our products" flag: <https://ai.google.dev/gemini-api/docs/pricing>
- OpenAI API data controls (no training by default, 30-day abuse logs, Zero Data Retention): <https://developers.openai.com/api/docs/guides/your-data>
- OpenAI business data privacy (no training on your data by default): <https://openai.com/business-data/>
- Qwen2.5 licenses per size (Apache-2.0 except 3B/72B): <https://qwenlm.github.io/blog/qwen2.5-llm/>
- Llama 3.1 supported languages (8, Romanian not listed): <https://github.com/meta-llama/llama-models/blob/main/models/llama3_1/MODEL_CARD.md>
- RTX 3080 Ti local-model fit (12 GB, Qwen2.5-14B tight): <https://willitrunai.com/can-run/qwen-2.5-14b-on-rtx-3080-ti-12gb>, <https://canirunthismodel.sefarai.com/gpu/nvidia-rtx-3080-ti>
