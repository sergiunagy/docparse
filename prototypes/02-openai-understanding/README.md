# Prototype 02 — OpenAI understanding spike

Runnable spike for issue [#2](https://github.com/sergiunagy/docparse/issues/2). Renders a
PDF's pages to images, sends them in **one** Chat Completions call with a strict
`json_schema` response, and reports the structured Understanding plus a per-document
token / cost / latency breakdown. Full rationale in [`PLAN.md`](./PLAN.md).

## Setup (pyenv + venv, Python 3.13)

```bash
cd prototypes/02-openai-understanding
~/.pyenv/versions/3.13.2/bin/python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Configure secrets/config (never commit real values):

```bash
cp .env.example .env   # then edit
```

`.env` keys: `OPENAI_API_KEY`, `OPENAI_MODEL` (default `gpt-5-mini`),
`OPENAI_REASONING_EFFORT` (`minimal`), `OPENAI_IMAGE_DETAIL` (`high`),
`PDF_RENDER_DPI` (`150`), optional `OPENAI_BASE_URL`.

## Run

Put a (redacted) German PDF in `data/` (git-ignored) and point the script at it:

```bash
python main.py data/fa_bescheid_2021.pdf
```

Outputs go to `out/` (git-ignored):

- `out/<pdf>.json` — the schema-adherent Understanding
- `out/<pdf>.md` — human-readable summary + run stats
- `out/run-log.jsonl` — one line per call: token breakdown (image / text-prompt /
  reasoning / visible), computed input/output `$`, and wall-clock latency

The console also prints the **drift probe**: how many `action_plan` steps came back
`grounded_in_document: false`.

## Benchmarking alternatives

Model and image detail are env vars, so re-run against alternatives without code changes:

```bash
OPENAI_MODEL=gpt-5-nano  python main.py data/fa_mahnung_30_03.pdf
OPENAI_MODEL=gpt-4o-mini python main.py data/fa_mahnung_30_03.pdf   # legacy tile-tax point
OPENAI_IMAGE_DETAIL=low  python main.py data/fa_mahnung_30_03.pdf
```

Each run appends to `out/run-log.jsonl`, so the token/cost numbers accumulate for comparison.

## Notes / caveats

- **Not production code.** One file, no ports, disposable (see `../README.md`).
- **Prices** in `main.py` (`PRICES`) are hard-coded per model; update if rates move.
- **Image tokens** are computed analytically (the `usage` object doesn't split image from
  text); the `tiktoken` text estimate is logged alongside as a cross-check.
- With image input the model OCRs the pages itself, so `source_quote` may be paraphrased
  rather than an exact substring — treat quote-exactness as an observation, not a guarantee.
- Never commit `data/`, `out/`, `.env`, or `.venv/` (all git-ignored).
