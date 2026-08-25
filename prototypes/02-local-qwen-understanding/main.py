"""Prototype 02b — Local Qwen understanding spike.

A deliberate near-copy of ../02-openai-understanding/main.py. It renders each
page of one PDF to an image, sends them in ONE Chat Completions call — but
against a LOCAL Ollama endpoint (base_url=http://localhost:11434/v1) with a
locally hosted Qwen2.5-VL model — and reports schema-adherent JSON plus a
per-document LOCAL-PERFORMANCE breakdown (VRAM, load/eval time, tok/s, latency).
There is NO $ cost: local inference is free. See PLAN.md for the full rationale.

The schema, prompt, glossary and drift probe are copied VERBATIM from proto 02
so the only variables are endpoint, model and runtime. The measured diff vs
proto 02's main.py is itself an output (the "config change, not a rewrite" test).

Deliberately one file, no abstraction — this is a spike, not the seam.
"""

from __future__ import annotations

import base64
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import pymupdf as fitz  # PyMuPDF
import tiktoken
from dotenv import load_dotenv
from openai import OpenAI
from typing import Literal

from pydantic import BaseModel, Field, ValidationError

HERE = Path(__file__).parent
OUT = HERE / "out"

# ---- prompt / glossary / schema / drift probe (diverged from proto 02: two-pass +
# stronger translation, number-format and anti-hallucination rules; see NOTES.md) ----

GLOSSARY = (
    "DE→EN glossary: Finanzamt=tax office; Finanzkasse=tax collection office; "
    "Bescheid=official notice/assessment; Vorauszahlungsbescheid=advance-payment notice; "
    "Mahnung=payment reminder/dunning; Vorauszahlung=advance payment; "
    "Aufforderung=formal request/demand; Frist=deadline; Nachzahlung=back payment due; "
    "Guthaben=credit/overpayment balance; Erstattung=refund; "
    "Säumniszuschlag=late-payment surcharge; Zwangsgeld=coercive fine; "
    "Einkommensteuer=income tax; Solidaritätszuschlag=solidarity surcharge; "
    "zu versteuerndes Einkommen=taxable income; Gesamtbetrag der Einkünfte=total income; "
    "festgesetzt=assessed/set; Rechtsbehelfsbelehrung=instructions on legal remedies; "
    "Einspruch=formal objection/appeal; Steuernummer=tax number."
)

# Pass 1 — a focused OCR-only transcription prompt (one call per page image).
OCR_SYSTEM = (
    "You are an OCR engine for scanned German documents. Transcribe the page image to text "
    "VERBATIM. Preserve every number, amount, date, IBAN and statute reference (e.g. § 165 AO) "
    "EXACTLY as printed. Keep each table row on its own line with its values in order. Do NOT "
    "translate, summarise or comment — output ONLY the raw German transcription."
)

# Pass 2 — understanding over the transcribed text (no images).
SYSTEM_PROMPT = (
    "You are a careful assistant that understands official German documents and returns "
    "structured JSON. You are given the OCR'd German text of the document, one section per "
    "page. Base everything ONLY on that provided text.\n"
    "LANGUAGE RULE: english_summary and every field ending in _en, plus sender, doc_type, "
    "period, text, step and rationale, MUST be written in ENGLISH — translate any German. "
    "German is allowed ONLY in 'source_quote' and 'raw'. Never place a German word or sentence "
    "in an English field. Keep verbatim only proper nouns (person names, 'Finanzamt "
    "Regensburg'), IBANs and statute references (e.g. § 165 AO). Never emit snake_case labels "
    "or field-name prefixes inside a value.\n"
    "NUMBER RULE: German uses '.' for thousands and ',' for decimals (1.234,56 = 1234.56). "
    "Amounts printed in a table column as integers with no decimal comma are in CENTS "
    "(25000 = 250,00; 250 = 2,50). Every row in the same column uses the same unit — apply the "
    "cents interpretation consistently to the WHOLE column. Put the normalized euro value in "
    "'value_eur' and the exact printed text in 'raw'. Do NOT perform or show arithmetic and do "
    "NOT invent a total that is not printed.\n"
    "GROUNDING RULE: include only dates, amounts and quotes that literally appear in the text. "
    "Never compute or infer a date/deadline; if a value is absent, omit it. 'source_quote' must "
    "be copied VERBATIM; if you cannot find it, leave it EMPTY — never fabricate it.\n"
    "Fields:\n"
    "1. english_summary: a faithful English summary. If a payment is due, state the net amount "
    "and its due date; if nothing is due for a period, say so explicitly.\n"
    "2. key_information: sender, doc_type, period, dates, deadlines, amounts, net_due. "
    "'period' is the timeframe the document is ABOUT (e.g. 'tax year 2021', '1st quarter "
    "2026'); 'dates' are dates printed on the document (issue/print date); each 'deadlines' "
    "entry is a date the recipient must act by; 'net_due' lists, per period, the net amount the "
    "recipient must PAY ('0,00' when nothing is due).\n"
    "3. obligations: actions the document ITSELF requests. Set 'direction': 'recipient_pays' "
    "when the recipient must pay money, 'recipient_receives' when money is paid TO them (a "
    "Guthaben / Erstattung / refund is ALWAYS 'recipient_receives', NEVER a payment "
    "obligation), 'informational' otherwise. 'text' English, 'source_quote' verbatim German "
    "(empty if not found). Include a deadline if stated.\n"
    "4. action_plan: broader suggested steps for the recipient. If a payment obligation exists, "
    "the FIRST step MUST be to pay it (state amount + due date). For EACH step set "
    "grounded_in_document=true only if the document itself asks for it, false if it is your own "
    "suggestion beyond the text. Be honest — this measures drift.\n"
    f"{GLOSSARY}"
)


class Amount(BaseModel):
    label_en: str      # English label, e.g. "principal income tax due"
    value_eur: str     # normalized euros, e.g. "250,00"; "" if not a money value
    raw: str           # exactly as printed, e.g. "25000"


class Deadline(BaseModel):
    description_en: str  # English description of what must be done by this date
    date: str            # only if literally printed; else ""
    source_quote: str    # verbatim German; "" if not found


class NetDue(BaseModel):
    period: str          # e.g. "2026", "1st quarter 2026"
    amount_eur: str      # net the recipient must PAY; "0,00" when nothing is due
    description_en: str  # English note, e.g. "no advance payment due for 2026"


class KeyInformation(BaseModel):
    sender: str
    doc_type: str
    period: str
    dates: list[str]
    deadlines: list[Deadline]
    amounts: list[Amount]
    net_due: list[NetDue]


class Obligation(BaseModel):
    text: str
    direction: Literal["recipient_pays", "recipient_receives", "informational"]
    source_quote: str
    deadline: str


class ActionStep(BaseModel):
    step: str
    rationale: str
    grounded_in_document: bool


class Understanding(BaseModel):
    english_summary: str
    key_information: KeyInformation
    obligations: list[Obligation]
    action_plan: list[ActionStep] = Field(default_factory=list)


def render_pages(pdf_path: Path, dpi: int) -> list[tuple[bytes, int, int]]:
    """Return (png_bytes, width_px, height_px) per page."""
    doc = fitz.open(pdf_path)
    pages = []
    for page in doc:
        pix = page.get_pixmap(dpi=dpi)
        pages.append((pix.tobytes("png"), pix.width, pix.height))
    doc.close()
    return pages


def ocr_pages(client: OpenAI, model: str, pages: list) -> tuple[list[str], list]:
    """Pass 1: transcribe each page image to verbatim German text (one call per page,
    so no single call carries all images — keeps us clear of the context limit even at
    higher DPI). Returns (per-page text, per-page usage)."""
    texts, usages = [], []
    for i, (png, _w, _h) in enumerate(pages, 1):
        b64 = base64.b64encode(png).decode()
        completion = client.chat.completions.create(
            # Use the Instruct (non-thinking) qwen3-vl build so the reasoning trace
            # doesn't eat this budget; 4000 is ample for a page transcription. The
            # finish_reason guard below still flags truncation if a model thinks.
            model=model, max_tokens=4000, temperature=0,
            messages=[
                {"role": "system", "content": OCR_SYSTEM},
                {"role": "user", "content": [
                    {"type": "text", "text": f"Transcribe page {i} of {len(pages)}."},
                    {"type": "image_url",
                     "image_url": {"url": f"data:image/png;base64,{b64}"}},
                ]},
            ],
        )
        if completion.choices[0].finish_reason == "length":
            # qwen3-vl thinking can't be disabled on this Ollama build and shares the
            # max_tokens budget; a truncated page transcription would otherwise be silent.
            print(f"  WARNING: page {i} OCR hit max_tokens (finish_reason=length) — "
                  "transcription may be truncated; consider raising max_tokens.")
        texts.append((completion.choices[0].message.content or "").strip())
        usages.append(completion.usage)
    return texts, usages


def tiktoken_text_estimate(text: str) -> int:
    """Approximate token count of the text prompt. NOT Qwen-exact — see PLAN.md §4a;
    logged as a sanity signal only (tiktoken doesn't know Qwen's tokenizer)."""
    enc = tiktoken.get_encoding("o200k_base")
    return len(enc.encode(text))


# ---- local-performance helpers (replaces proto 02's $-cost block; PLAN.md §4a) ----

def quant_from_model(model: str) -> str:
    """Best-effort quant label from the Ollama tag (e.g. ':7b' -> Q4_K_M default)."""
    tag = model.split(":", 1)[1] if ":" in model else ""
    for q in ("q8_0", "q4_k_m", "q4_0", "q6_k", "q5_k_m", "fp16"):
        if q in tag.lower():
            return q.upper()
    return "Q4_K_M"  # Ollama's default quant for qwen2.5vl:7b


def nvidia_vram_used_mb() -> int | None:
    try:
        out = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=10,
        )
        return int(out.stdout.strip().splitlines()[0])
    except Exception:
        return None


def ollama_ps(model: str) -> tuple[str | None, int | None]:
    """Return (gpu_cpu_split, context_length) for `model` from `ollama ps`."""
    try:
        out = subprocess.run(["ollama", "ps"], capture_output=True, text=True, timeout=10)
    except Exception:
        return None, None
    for line in out.stdout.splitlines():
        if line.startswith(model.split(":")[0]) and model in line:
            split = None
            for tok in ("100% GPU", "100% CPU"):
                if tok in line:
                    split = tok
            if split is None and "%" in line:
                # e.g. "58%/42% CPU/GPU"
                for part in line.split():
                    if "%" in part:
                        split = part
                        break
            # The CONTEXT column is a large int (e.g. 32768); the UNTIL column also
            # contains small ints ("4 minutes from now"), so take the largest.
            ints = [int(p) for p in line.split() if p.isdigit()]
            ctx = max(ints) if ints else None
            return split, ctx
    return None, None


def main() -> None:
    load_dotenv(HERE / ".env")
    if len(sys.argv) != 2:
        sys.exit("usage: python main.py <path-to-pdf>")
    pdf_path = Path(sys.argv[1]).expanduser()
    if not pdf_path.exists():
        sys.exit(f"no such file: {pdf_path}")

    model = os.getenv("OPENAI_MODEL", "qwen3-vl:8b-instruct")
    structured_mode = os.getenv("OLLAMA_STRUCTURED_MODE", "auto")
    dpi = int(os.getenv("PDF_RENDER_DPI", "200"))
    kv_cache_type = os.getenv("OLLAMA_KV_CACHE_TYPE")  # server-side; log only
    flash_attention = os.getenv("OLLAMA_FLASH_ATTENTION")  # server-side; log only
    env_ctx = os.getenv("OLLAMA_CONTEXT_LENGTH")

    client = OpenAI(
        base_url=os.getenv("OPENAI_BASE_URL") or "http://localhost:11434/v1",
        api_key=os.getenv("OPENAI_API_KEY") or "ollama",
    )

    print(f"Rendering {pdf_path.name} at {dpi} DPI ...")
    pages = render_pages(pdf_path, dpi)
    print(f"  {len(pages)} page(s); model={model} structured_mode={structured_mode}")

    # ---- two-pass pipeline: (1) per-page OCR, (2) understanding over the text ----
    vram_before = nvidia_vram_used_mb()
    t0 = time.perf_counter()

    print(f"Pass 1: OCR-ing {len(pages)} page(s) ...")
    ocr_texts, ocr_usages = ocr_pages(client, model, pages)
    transcription = "\n\n".join(
        f"=== PAGE {i} ===\n{t}" for i, t in enumerate(ocr_texts, 1))

    text_prompt = (
        "Below is the OCR'd German text of the document, one section per page. Understand it "
        "and return the structured JSON described by the schema. Base everything ONLY on this "
        "text.\n\n" + transcription
    )
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": text_prompt},
    ]

    print("Pass 2: understanding (structured output) ...")
    result, completion, used_mode = call_structured(client, model, messages, structured_mode)
    latency_s = round(time.perf_counter() - t0, 2)
    vram_after = nvidia_vram_used_mb()

    # Aggregate usage across the OCR calls + the understanding call. Track the largest
    # SINGLE-call prompt separately for the truncation tripwire (per-call, not summed).
    def _tok(u, attr: str) -> int:
        return getattr(u, attr, 0) or 0

    usage = completion.usage
    all_usages = ocr_usages + [usage]
    prompt_tokens = sum(_tok(u, "prompt_tokens") for u in all_usages)
    completion_tokens = sum(_tok(u, "completion_tokens") for u in all_usages)
    total_tokens = sum(_tok(u, "total_tokens") for u in all_usages)
    max_call_prompt_tokens = max(_tok(u, "prompt_tokens") for u in all_usages)

    # Ollama's ns timings, if surfaced via /v1 (may be absent — PLAN.md §4a).
    extra = getattr(completion, "model_extra", None) or {}
    load_ns = extra.get("load_duration")
    eval_ns = extra.get("eval_duration")
    load_duration_s = round(load_ns / 1e9, 3) if load_ns else None
    eval_duration_s = round(eval_ns / 1e9, 3) if eval_ns else None
    if eval_duration_s:
        tokens_per_second = round(completion_tokens / eval_duration_s, 1)
    elif latency_s:
        tokens_per_second = round(completion_tokens / latency_s, 1)  # wall-clock derived
    else:
        tokens_per_second = None

    text_tokens_tiktoken = tiktoken_text_estimate(SYSTEM_PROMPT + "\n" + text_prompt)
    gpu_cpu_split, ps_ctx = ollama_ps(model)
    context_length = ps_ctx or (int(env_ctx) if env_ctx and env_ctx.isdigit() else None)

    # Silent-truncation tripwire (PLAN.md §4a / §6.5).
    truncation_warning = None
    if context_length and max_call_prompt_tokens >= context_length:
        truncation_warning = (
            f"a single-call prompt ({max_call_prompt_tokens}) >= context_length "
            f"({context_length}) — Ollama may have SILENTLY TRUNCATED the input; "
            "quality is suspect."
        )

    log = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "pdf": pdf_path.name,
        "runtime": "ollama",
        "model": model,
        "quant": quant_from_model(model),
        "structured_mode": used_mode,
        "passes": 2,
        "ocr_calls": len(pages),
        "max_call_prompt_tokens": max_call_prompt_tokens,
        "context_length": context_length,
        "kv_cache_type": kv_cache_type,
        "flash_attention": flash_attention,
        "render_dpi": dpi,
        "n_pages": len(pages),
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
        "text_tokens_tiktoken": text_tokens_tiktoken,  # estimate, NOT Qwen-exact
        "tokens_per_second": tokens_per_second,
        "load_duration_s": load_duration_s,
        "eval_duration_s": eval_duration_s,
        "vram_mb": vram_after or vram_before,
        "vram_mb_before": vram_before,
        "gpu_cpu_split": gpu_cpu_split,
        "latency_s": latency_s,
    }

    # ---- persist ----
    OUT.mkdir(exist_ok=True)
    stem = pdf_path.stem
    (OUT / f"{stem}.json").write_text(result.model_dump_json(indent=2))
    (OUT / f"{stem}.md").write_text(to_markdown(result, log))
    with (OUT / "run-log.jsonl").open("a") as f:
        f.write(json.dumps(log) + "\n")

    # ---- console ----
    print("\n=== UNDERSTANDING ===")
    print(result.model_dump_json(indent=2))
    grounded = [s for s in result.action_plan if not s.grounded_in_document]
    print("\n=== TOKENS / LOCAL PERF / LATENCY ===")
    print(json.dumps(log, indent=2))
    if truncation_warning:
        print(f"\n!!! TRUNCATION WARNING: {truncation_warning}")
    print(f"\nStructured-output path used: {used_mode}")
    print(f"Drift probe: {len(grounded)}/{len(result.action_plan)} action-plan steps "
          f"were NOT grounded in the document.")
    print(f"Artefacts in {OUT}/  (json, md, run-log.jsonl)")


def call_structured(client: OpenAI, model: str, messages: list, mode: str):
    """Return (Understanding, completion, mode_used). Implements PLAN.md §1.2:
    json_schema (proto 02's .parse path), ollama_format (native `format` field),
    or auto (try the first, fall back to the second on failure)."""

    def via_json_schema():
        completion = client.beta.chat.completions.parse(
            model=model, messages=messages, temperature=0,
            response_format=Understanding, max_tokens=8000,
        )
        if completion.choices[0].finish_reason == "length":
            raise ValueError("json_schema path hit max_tokens (finish_reason=length); "
                             "thinking likely starved the JSON — raise max_tokens")
        parsed = completion.choices[0].message.parsed
        if parsed is None:
            raise ValueError("json_schema path returned no parsed object")
        return parsed, completion

    def via_ollama_format():
        completion = client.chat.completions.create(
            model=model, messages=messages, max_tokens=8000, temperature=0,
            extra_body={"format": Understanding.model_json_schema()},
        )
        if completion.choices[0].finish_reason == "length":
            raise ValueError("ollama_format path hit max_tokens (finish_reason=length); "
                             "thinking likely starved the JSON — raise max_tokens")
        raw = completion.choices[0].message.content.strip()
        # Findings on this path: JSON sometimes comes back (a) inside a ```json fence
        # and (b) wrapped in a single-element array. Both must be unwrapped.
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1] if "\n" in raw else raw
            raw = raw.rsplit("```", 1)[0].strip()
        obj = json.loads(raw, strict=False)  # (c) tolerate unescaped control chars
        if isinstance(obj, list) and len(obj) == 1:
            obj = obj[0]
        parsed = Understanding.model_validate(obj)
        return parsed, completion

    if mode == "json_schema":
        parsed, completion = via_json_schema()
        return parsed, completion, "json_schema"
    if mode == "ollama_format":
        parsed, completion = via_ollama_format()
        return parsed, completion, "ollama_format"
    # auto
    try:
        parsed, completion = via_json_schema()
        return parsed, completion, "json_schema"
    except (Exception, ValidationError) as e:  # noqa: BLE001 — spike; record & fall back
        print(f"  json_schema path failed ({type(e).__name__}: {e}); "
              "falling back to ollama_format ...")
        parsed, completion = via_ollama_format()
        return parsed, completion, "ollama_format(fallback)"


def to_markdown(r: Understanding, log: dict) -> str:
    ki = r.key_information
    lines = [f"# Understanding — {log['pdf']}", "",
             "## English summary", r.english_summary, "",
             "## Key information",
             f"- **Sender:** {ki.sender}",
             f"- **Type:** {ki.doc_type}",
             f"- **Period:** {ki.period or '—'}",
             f"- **Dates:** {', '.join(ki.dates) or '—'}", "",
             "### Deadlines"]
    lines += [f"- {d.description_en}: {d.date or '—'}\n  > {d.source_quote or '—'}"
              for d in ki.deadlines] or ["- (none)"]
    lines += ["", "### Amounts"]
    lines += [f"- {a.label_en}: {a.value_eur or '—'} € (raw: {a.raw})"
              for a in ki.amounts] or ["- (none)"]
    lines += ["", "### Net due"]
    lines += [f"- {n.period}: {n.amount_eur} € — {n.description_en}"
              for n in ki.net_due] or ["- (none)"]
    lines += ["", "## Obligations"]
    lines += [f"- [{o.direction}] {o.text} (deadline: {o.deadline or '—'})\n  > "
              f"{o.source_quote or '—'}" for o in r.obligations] or ["- (none)"]
    lines += ["", "## Action plan"]
    lines += [f"- [{'grounded' if s.grounded_in_document else 'DRIFT'}] {s.step} — "
              f"{s.rationale}" for s in r.action_plan] or ["- (none)"]
    lines += ["", "## Run", "```json", json.dumps(log, indent=2), "```"]
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    main()
