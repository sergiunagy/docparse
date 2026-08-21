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
