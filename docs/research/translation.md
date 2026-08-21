# Research: translating DE/RO official text into English for the MVP

Issue: sergiunagy/docparse#4. Branch: `research/translation`.

Question: how should the MVP translate German OR Romanian official/administrative
text into English at a quality adequate for legal/financial content? Compare
LLM-based translation (routed through the AI Provider adapter, see
`docs/adr/0001-ai-provider-adapter.md`) against dedicated machine translation
(for example DeepL). The evaluation axes are: quality on the bureaucratic/legal
register for both DE and RO source languages, handling of extracted table cells
and Key Information fields, terminology consistency, cost, and local/self-hosted
feasibility (a hard local-swap requirement exists per ADR 0001).

This note captures findings against primary sources. Each claim points at the
source that owns it.

## Constraints that frame the decision

- ADR 0001 makes self-hosting locally a **hard long-term requirement** (data
  sensitivity of official/financial documents, plus possible commercialisation),
  and mandates that all AI Provider access go through one provider-agnostic
  port/adapter, with the cloud-to-local swap being a configuration + adapter
  change, not a rewrite. `docs/adr/0001-ai-provider-adapter.md`.
- `CONTEXT.md` lists Translation as one of the language tasks the AI Provider
  performs, alongside extraction assistance, summarisation, and Q&A, and scopes
  MVP output to English.
- Value lives in tables (for example Finanzamt figures), so Extraction must
  preserve table/layout fidelity, and translation runs over those extracted
  cells and Key Information fields (`CONTEXT.md`: Extraction, Key Information).

## Quality on the legal/bureaucratic register (DE and RO into English)

- WMT24 General MT shared task, titled "The LLM Era Is Here but MT Is Not Solved
  Yet", collected 8 LLMs and 4 online providers and evaluated with professional
  human annotators. The best system overall was Claude 3.5 Sonnet (won 9 language
  pairs); the best participating system was the open-weight Unbabel Tower 70B (won
  8). LLMs now sit at the top of general MT for high-resource pairs.
  https://aclanthology.org/2024.wmt-1.1/ and the findings PDF
  https://aclanthology.org/anthology-files/pdf/wmt/2024.wmt-1.1.pdf
- Unbabel's Tower-V2 submission reports that an LLM adapted for translation
  "outperform[s] closed commercial systems like GPT-4O, CLAUDE-SONNET-3.5, and
  DEEPL even at a smaller 7B scale", and that open NMT models like NLLB-200 can be
  outperformed by adapting an LLM to translation.
  https://aclanthology.org/2024.wmt-1.12.pdf
- DeepL is a strong, purpose-built baseline for both our source languages. The
  DeepL API supports Romanian (`RO`) and German with full text translation.
  https://developers.deepl.com/docs/getting-started/supported-languages
- Caveat for the local case: an academic study of **local** instruction-tuned
  LLMs (llama3.2:3b, mistral, qwen2.5:14b) against OPUS-MT and NLLB-200 on FLORES
  for nine EU languages (including Romanian and German) finds that "dedicated MT
  systems remain strongest overall, especially for Germanic languages", while
  few-shot prompting narrows the gap for the stronger local LLMs.
  https://arxiv.org/html/2607.26286v1

Reading: for a cloud MVP, a frontier LLM matches or beats DeepL on general
high-resource DE/RO -> EN quality. Once we drop to a **small self-hosted** model,
a dedicated MT engine can still beat a small local LLM, which is relevant to the
mandated local-swap path.

## Table cells and Key Information fields

- DeepL offers document translation and `tag_handling` (XML/HTML) so structure is
  preserved and only content is translated, plus a document endpoint.
  https://developers.deepl.com/api-reference/translate
- Trade-off for extracted cells: individual table cells and lifted fields
  (sender, dates, amounts) are short and context-poor. A dedicated MT call on an
  isolated fragment loses the surrounding document context. An LLM can be given
  the whole extracted table plus instructions ("translate cell text, leave
  numbers, dates, currency, and IDs verbatim, keep the row/column structure"),
  which fits the layout-fidelity goal in `CONTEXT.md` and the fact that the same
  provider already does Extraction assistance and summarisation.

## Terminology consistency

- DeepL has first-class, deterministic terminology control: glossaries and
  translation memory are both available for Romanian and for German (per-language
  feature flags `glossaries: true`, `translationMemory: true` on `RO`; German is
  a core supported language).
  https://developers.deepl.com/docs/getting-started/supported-languages
- An LLM has no built-in glossary; consistency comes from injecting a curated
  term list into the prompt (and optionally post-checking). This works and is
  flexible, but is less deterministic than DeepL's enforced glossary. For
  legal/financial terms this is the axis where dedicated MT has a genuine edge,
  and it argues for us maintaining a DE/RO -> EN glossary regardless of engine.

## Cost

- For a personal/family, low-volume app, both options are inexpensive. DeepL bills
  per character with a free developer tier; a DeepL account (including Free) is
  enough to start. https://www.deepl.com/en/pro-api and
  https://developers.deepl.com/docs/getting-started/deepl-mcp-server
- LLM translation bills per token on the same provider we already use for
  Extraction assist, summary, and Q&A, so translation adds no new billing
  relationship. Self-hosting moves cost from per-request fees to GPU/compute.
- Cost is not the deciding axis here; local feasibility and the single-seam
  requirement are.

## Local / self-hosted feasibility (the hard requirement)

- DeepL does not offer a general self-hosted/on-premises deployment. Its own
  description is a **hybrid cloud**: DeepL-administered data centres in Europe
  plus AWS as a sub-processor, with DeepL's proprietary models running in a
  DeepL-controlled environment. Customers do not run the model.
  https://support.deepl.com/hc/en-us/articles/26380849099932-DeepL-infrastructure-and-data-protection
- The DeepL "local MCP server" is only a local **client** wrapper: it "runs on
  your machine, uses your API key" and calls the DeepL cloud API. It is not local
  inference. https://www.deepl.com/en/ai-agents and
  https://github.com/DeepL/deepl-mcp-server
- Therefore DeepL structurally **cannot satisfy** ADR 0001's hard local-swap
  requirement. Adopting DeepL as the MVP engine would either break that
  requirement or force a full engine replacement later (exactly the rewrite ADR
  0001 exists to prevent).
- Open, self-hostable engines do exist for our pairs:
  - Dedicated MT: OPUS-MT / MarianMT (Helsinki-NLP), permissively licensed
    (Apache-2.0 / CC-BY-4.0), commercial-safe, and competitive with NLLB on
    European pairs.
    https://github.com/Lawrenzho-bit/LayoutTranslateBench/pull/19
  - NLLB-200 covers 200 languages and self-hosts, but its **weights are CC-BY-NC
    4.0 (non-commercial)**; Meta confirms even fine-tuned adaptations are not
    authorised for commercial use. Given ADR 0001 flags possible
    commercialisation, NLLB weights are a licensing risk.
    https://github.com/facebookresearch/fairseq/issues/5633 and
    https://github.com/facebookresearch/fairseq/tree/nllb
  - Self-hosted instruction-tuned LLMs (Qwen, Mistral, Llama) can do the
    translation task locally and, per the local study above, are competitive with
    few-shot prompting though still behind dedicated MT for Germanic at small
    sizes. https://arxiv.org/html/2607.26286v1

## Recommendation

1. **MVP engine: LLM-based translation via the AI Provider, not DeepL.** A
   frontier cloud LLM already matches or beats DeepL on DE/RO -> EN general
   quality (WMT24, Tower-V2), and the same provider already performs Extraction
   assist, summarisation, and Q&A, so translation reuses one integration and can
   see full-document context when translating table cells and fields. Decisively,
   DeepL fails ADR 0001's hard local-swap requirement, so choosing it now would
   create the rewrite the ADR forbids.
2. **Carry a curated DE/RO -> EN glossary of legal/financial terms** and inject it
   into the translation prompt (with an optional post-translation term check).
   This is the one axis where dedicated MT is inherently stronger, so we close the
   gap deliberately rather than depend on the engine.
3. **Prompt for structure-preserving translation** of extracted tables: translate
   cell/field text, keep numbers, dates, currency, and identifiers verbatim,
   preserve row/column structure. This aligns with the Extraction layout-fidelity
   goal.
4. **Local-swap path:** when self-hosting, prefer a self-hosted instruction-tuned
   LLM to keep one provider surface, and keep a permissively licensed dedicated MT
   engine (OPUS-MT/MarianMT, Apache-2.0 / CC-BY-4.0) as a fallback for higher DE/RO
   quality at small model sizes. Avoid NLLB-200 weights if commercialisation stays
   on the table (CC-BY-NC 4.0).

## AI Provider adapter, or a separate adapter?

**Route translation through the AI Provider adapter (ADR 0001), not a separate
parallel adapter.** Reasons:

- ADR 0001 explicitly names translation as an AI Provider language task and
  requires that **all** AI Provider access go through the single provider-agnostic
  seam. A separate top-level translation adapter that reached a vendor directly
  would violate that ADR and reintroduce the spread-out SDK calls it prevents.
- In the MVP the same model does translation, extraction assist, summarisation,
  and Q&A. One provider integration, one swap.

Refinement, so this is not read as "just make it another chat call": expose
translation as its **own capability (its own port method / interface)** inside the
adapter boundary, distinct from generic chat/completion. The adapter stays the one
swap seam, but Translation being its own capability means a future
**dedicated-MT backend** (self-hosted OPUS-MT, or DeepL cloud if the hard local
requirement were ever relaxed) can implement just that capability without touching
the chat-style calls, and without a second seam.

Net: **its own capability/port, but behind the shared AI Provider adapter, backed
by the LLM provider for the MVP.** Not a separate standalone adapter.

## Sources

- ADR 0001, `docs/adr/0001-ai-provider-adapter.md`; `CONTEXT.md` (this repo).
- WMT24 General MT findings: https://aclanthology.org/2024.wmt-1.1/ ,
  https://aclanthology.org/anthology-files/pdf/wmt/2024.wmt-1.1.pdf
- Tower-V2 WMT24 submission: https://aclanthology.org/2024.wmt-1.12.pdf
- Local LLM vs OPUS-MT/NLLB study (incl. RO, DE): https://arxiv.org/html/2607.26286v1
- DeepL supported languages: https://developers.deepl.com/docs/getting-started/supported-languages
- DeepL translate API (tag handling, glossaries): https://developers.deepl.com/api-reference/translate
- DeepL infrastructure/data protection: https://support.deepl.com/hc/en-us/articles/26380849099932-DeepL-infrastructure-and-data-protection
- DeepL AI agents / local MCP server: https://www.deepl.com/en/ai-agents ,
  https://github.com/DeepL/deepl-mcp-server
- NLLB-200 license (CC-BY-NC 4.0): https://github.com/facebookresearch/fairseq/issues/5633 ,
  https://github.com/facebookresearch/fairseq/tree/nllb
- OPUS-MT commercial-safe licensing note: https://github.com/Lawrenzho-bit/LayoutTranslateBench/pull/19
