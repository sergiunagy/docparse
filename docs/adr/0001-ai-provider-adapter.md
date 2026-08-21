# AI provider sits behind a provider-agnostic adapter

The app performs language tasks (translation, extraction assistance, summarisation, Q&A)
via an **AI Provider**. Self-hosting locally is a hard long-term requirement (data
sensitivity of official/financial documents, plus possible commercialisation), but for
MVP speed we will use a cloud provider first.

**Decision:** all AI Provider access goes through a single provider-agnostic port/adapter
boundary. No application code calls a vendor SDK directly. Swapping the cloud provider for
a self-hosted/local model must be a configuration + adapter change, not a rewrite.

**Why it's recorded:** it's hard to reverse (retrofitting the seam after direct SDK calls
have spread is expensive), surprising without context (a reader might ask why we don't
just call the provider directly), and a real trade-off (cloud speed now vs. mandatory
local-swap later). The concrete orchestration technology behind this seam (raw SDK vs. a
router like LiteLLM vs. an agent framework) is deferred to a research ticket.
