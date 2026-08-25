# Prototypes

Throwaway spikes that produce **empirical evidence** to back (or overturn) the desk
research under [`docs/research/`](../docs/research/) before those research tickets are
closed. Each prototype exists to answer a specific design question with something
*runnable and measured*, not more prose.

These are **not** production code. They are deliberately minimal, single-purpose, and
disposable. Nothing here is imported by the real application; the real MVP is built
separately once the decisions are settled.

## Why this folder exists

The research notes (issues #2/#3/#4) already recommend a stack, but the recommendations
rest on documentation and reasoning, not on having *run* the thing. This folder is where
we exercise the recommended option **and its strongest alternative** on a real
Finanzamt-style document, capture numbers (cost, latency, quality, confidence), and feed
the findings back into the ticket before deciding.

## Layout convention

One directory per prototype, prefixed with the research issue number it validates:

| Directory | Validates | Research note |
| --- | --- | --- |
| `02-openai-understanding/` | AI orchestration seam (#2), cloud arm | [`ai-orchestration.md`](../docs/research/ai-orchestration.md) |
| `02-local-qwen-understanding/` | AI orchestration seam (#2), local-swap arm — same scenario on a self-hosted Qwen3-VL (`qwen3-vl:8b-instruct`, Ollama, RTX 3080 Ti) | [`ai-orchestration.md`](../docs/research/ai-orchestration.md) |
| `03-pdf-extraction/` (planned) | table/layout extraction + Confidence (#3) | [`pdf-extraction.md`](../docs/research/pdf-extraction.md) |
| `04-translation/` (planned) | DE→EN legal-register translation (#4) | [`translation.md`](../docs/research/translation.md) |

Each prototype directory should contain:

- `PLAN.md` — the design question, what evidence it must produce, and how to build/run it.
- `README.md` — short run instructions (added when the prototype is built).
- `main.py` (or equivalent), `requirements.txt`, `.env.example`.
- `samples/` — input documents. **Real official documents are sensitive** (the privacy
  driver behind [ADR-0001](../docs/adr/0001-ai-provider-adapter.md)); this directory is
  git-ignored. Prefer a redacted or synthetic sample.
- `out/` — run artefacts (JSON output, token/cost logs). Git-ignored.

## Conventions

- **Python 3.11+**, one isolated virtualenv per prototype (`.venv/`, git-ignored).
- Secrets live in a per-prototype `.env` (git-ignored via the repo `.gitignore`); commit
  only `.env.example`.
- Never commit `samples/`, `out/`, `.env`, or `.venv/`.
- When a prototype yields a conclusion, record it as a comment on the matching issue and,
  if it changes a recommendation, update the relevant `docs/research/*.md`.
