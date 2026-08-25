"""Prototype 02 — OpenAI understanding spike.

Renders each page of one PDF to an image, sends them in ONE Chat Completions
call with a strict json_schema response, and reports schema-adherent JSON plus a
per-document token/cost/latency breakdown. See PLAN.md for the full rationale.

Deliberately one file, no abstraction — this is a spike, not the seam.
"""

from __future__ import annotations

import base64
import json
import math
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

import pymupdf as fitz  # PyMuPDF
import tiktoken
from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel, Field

HERE = Path(__file__).parent
OUT = HERE / "out"

# Hard-coded per-model rates, USD per 1M tokens (input, output). Adjust as prices move.
PRICES = {
    "gpt-5":       (1.25, 10.00),
    "gpt-5-mini":  (0.25,  2.00),
    "gpt-5-nano":  (0.05,  0.40),
    "gpt-4o-mini": (0.15,  0.60),
}

GLOSSARY = (
    "DE→EN glossary stub: Finanzamt=tax office; Bescheid=official notice/assessment; "
    "Mahnung=payment reminder/dunning; Vorauszahlung=advance payment; "
    "Aufforderung=formal request; Frist=deadline; Nachzahlung=back payment due; "
    "Einspruch=formal objection/appeal; Steuernummer=tax number."
)

SYSTEM_PROMPT = (
    "You are a careful assistant that reads official German documents from page images "
    "and returns structured JSON. You OCR the pages yourself.\n"
    "LANGUAGE RULE: english_summary and every field ending in _en, plus sender, doc_type, "
    "period, text, step and rationale, MUST be written in ENGLISH — translate any German. "
    "German is allowed ONLY in 'source_quote' and 'raw'. Keep verbatim only proper nouns "
    "(person names, 'Finanzamt Regensburg'), IBANs and statute references (e.g. § 165 AO).\n"
    "NUMBER RULE: German uses '.' for thousands and ',' for decimals (1.234,56 = 1234.56). "
    "Amounts printed in a table column as integers with no decimal comma are in CENTS "
    "(25000 = 250,00; 250 = 2,50). Every row in the same column uses the same unit — apply the "
    "cents interpretation consistently to the WHOLE column. Put the normalized euro value in "
    "'value_eur' and the exact printed text in 'raw'. Do NOT invent a total that is not "
    "printed.\n"
    "GROUNDING RULE: include only dates, amounts and quotes that literally appear. Never "
    "compute or infer a date/deadline. 'source_quote' should be verbatim German; if you cannot "
    "read it, leave it EMPTY rather than inventing it.\n"
    "Fields:\n"
    "1. english_summary: a faithful English summary. If a payment is due, state the net amount "
    "and its due date; if nothing is due for a period, say so explicitly.\n"
    "2. key_information: sender, doc_type, period, dates, deadlines, amounts, net_due. "
    "'period' is the timeframe the document is ABOUT (e.g. 'tax year 2021'); 'dates' are dates "
    "printed on the document; each 'deadlines' entry is a date the recipient must act by; "
    "'net_due' lists, per period, the net amount the recipient must PAY ('0,00' when nothing is "
    "due).\n"
    "3. obligations: actions the document ITSELF requests. Set 'direction': 'recipient_pays' "
    "when the recipient must pay, 'recipient_receives' when money is paid TO them (a Guthaben / "
    "Erstattung / refund is ALWAYS 'recipient_receives', NEVER a payment obligation), "
    "'informational' otherwise. 'text' English, 'source_quote' German. Include a deadline if "
    "stated.\n"
    "4. action_plan: broader suggested steps for the recipient. If a payment obligation exists, "
    "the FIRST step MUST be to pay it (amount + due date). For EACH step set "
    "grounded_in_document=true only if the document itself asks for it, false if it is your "
    "own suggestion beyond the text. Be honest — this measures drift.\n"
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


def image_tokens_for(model: str, w: int, h: int, detail: str) -> int:
    """Analytic image-token estimate (usage doesn't split image from text)."""
    if model.startswith("gpt-5"):  # patch-based, budget-capped
        raw = math.ceil(w / 32) * math.ceil(h / 32)
        if raw > 1536:
            scale = math.sqrt(1536 / raw)
            w, h = w * scale, h * scale
        patches = min(math.ceil(w / 32) * math.ceil(h / 32), 1536)
        mult = 1.5 if "nano" in model else 1.62
        return math.ceil(patches * mult)
    # legacy tile tax (gpt-4o family)
    if detail == "low":
        base = 85
    else:
        tiles = math.ceil(w / 512) * math.ceil(h / 512)
        base = 85 + 170 * tiles
    return round(base * 33.33) if "mini" in model else base


def tiktoken_text_estimate(model: str, text: str) -> int:
    try:
        enc = tiktoken.encoding_for_model(model)
    except KeyError:
        enc = tiktoken.get_encoding("o200k_base")
    return len(enc.encode(text))


def main() -> None:
    load_dotenv(HERE / ".env")
    if len(sys.argv) != 2:
        sys.exit("usage: python main.py <path-to-pdf>")
    pdf_path = Path(sys.argv[1]).expanduser()
    if not pdf_path.exists():
        sys.exit(f"no such file: {pdf_path}")

    model = os.getenv("OPENAI_MODEL", "gpt-5-mini")
    reasoning_effort = os.getenv("OPENAI_REASONING_EFFORT", "minimal")
    detail = os.getenv("OPENAI_IMAGE_DETAIL", "high")
    dpi = int(os.getenv("PDF_RENDER_DPI", "150"))
    is_reasoning = model.startswith("gpt-5")

    client = OpenAI(
        api_key=os.environ["OPENAI_API_KEY"],
        base_url=os.getenv("OPENAI_BASE_URL") or None,
    )

    print(f"Rendering {pdf_path.name} at {dpi} DPI ...")
    pages = render_pages(pdf_path, dpi)
    print(f"  {len(pages)} page(s); model={model} detail={detail} reasoning={reasoning_effort}")

    text_prompt = (
        "Understand the attached German document (one image per page, in order) and return "
        "the structured JSON described by the schema. Extract only what the pages show."
    )
    content: list[dict] = [{"type": "text", "text": text_prompt}]
    for png, _w, _h in pages:
        b64 = base64.b64encode(png).decode()
        content.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/png;base64,{b64}", "detail": detail},
        })
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": content},
    ]

    kwargs: dict = {"model": model, "messages": messages,
                    "response_format": Understanding, "max_completion_tokens": 8000}
    if is_reasoning:
        kwargs["reasoning_effort"] = reasoning_effort

    print("Calling OpenAI Chat Completions (structured output) ...")
    t0 = time.perf_counter()
    completion = client.beta.chat.completions.parse(**kwargs)
    latency_s = round(time.perf_counter() - t0, 2)

    result: Understanding = completion.choices[0].message.parsed
    usage = completion.usage

    # ---- token accounting (PLAN.md §4a) ----
    image_tokens = sum(image_tokens_for(model, w, h, detail) for _b, w, h in pages)
    text_tokens_tiktoken = tiktoken_text_estimate(
        model, SYSTEM_PROMPT + "\n" + text_prompt)
    prompt_tokens = usage.prompt_tokens
    completion_tokens = usage.completion_tokens
    total_tokens = usage.total_tokens
    reasoning_tokens = getattr(
        getattr(usage, "completion_tokens_details", None), "reasoning_tokens", 0) or 0
    visible_completion = completion_tokens - reasoning_tokens
    text_prompt_tokens = prompt_tokens - image_tokens

    in_rate, out_rate = PRICES.get(model, (0.0, 0.0))
    input_cost = prompt_tokens / 1_000_000 * in_rate
    output_cost = completion_tokens / 1_000_000 * out_rate  # reasoning billed here
    total_cost = input_cost + output_cost

    log = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "pdf": pdf_path.name,
        "model": model,
        "reasoning_effort": reasoning_effort if is_reasoning else None,
        "image_detail": detail,
        "render_dpi": dpi,
        "n_pages": len(pages),
        "image_tokens": image_tokens,
        "text_prompt_tokens": text_prompt_tokens,
        "text_tokens_tiktoken": text_tokens_tiktoken,
        "prompt_tokens": prompt_tokens,
        "reasoning_tokens": reasoning_tokens,
        "visible_completion_tokens": visible_completion,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
        "input_cost_usd": round(input_cost, 6),
        "output_cost_usd": round(output_cost, 6),
        "total_cost_usd": round(total_cost, 6),
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
    print("\n=== TOKENS / COST / LATENCY ===")
    print(json.dumps(log, indent=2))
    print(f"\nDrift probe: {len(grounded)}/{len(result.action_plan)} action-plan steps "
          f"were NOT grounded in the document.")
    print(f"Artefacts in {OUT}/  (json, md, run-log.jsonl)")


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
