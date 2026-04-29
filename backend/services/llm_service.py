import os
import re
import json
import httpx
from dotenv import load_dotenv
from .template_loader import load_template, load_brand_guide, load_system_prompt

load_dotenv()

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL    = os.getenv("OLLAMA_MODEL", "llama3")

AVAILABLE_MODELS = ["llama3", "llama3.1", "mistral", "gemma2", "codellama", "phi3", "qwen2.5-coder:14b"]


def _waf_safe(text: str) -> str:
    """Convert markdown tables to WAF-safe bullet format (pipes trigger corporate WAF 403)."""
    lines = text.splitlines()
    result = []
    headers: list[str] = []

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("|") and stripped.endswith("|"):
            cells = [c.strip() for c in stripped.strip("|").split("|")]
            # separator row like |---|---|  — skip it, capture headers from prior row
            if all(re.match(r"^[-:]+$", c) for c in cells if c):
                continue
            # header row or data row
            if not headers:
                headers = cells
                result.append("Fields: " + ", ".join(headers))
            else:
                pairs = [f"{h}={v}" for h, v in zip(headers, cells) if h]
                result.append("  - " + " | ".join(pairs) if not all(v in ("", " ") for _, v in zip(headers, cells)) else "  - (row)")
        else:
            if stripped == "" and headers:
                headers = []  # reset on blank line after table
            result.append(line)

    return "\n".join(result)


def build_prompt(doc_type: str, instructions: str, previous_content: str | None) -> str:
    system_prompt = load_system_prompt()
    brand_guide   = load_brand_guide()
    template      = load_template(doc_type)

    parts = [
        f"SYSTEM INSTRUCTIONS:\n{_waf_safe(system_prompt)}",
        f"\nBRAND GUIDE:\n{_waf_safe(brand_guide)}",
        f"\nTEMPLATE TO FOLLOW:\n{_waf_safe(template)}",
        f"\nUSER INSTRUCTIONS:\n{instructions}",
    ]

    if previous_content:
        parts.append(
            f"""\nPREVIOUS VERSION:
{previous_content}

DIFF INSTRUCTIONS:
- Identify which sections are affected by the USER INSTRUCTIONS above.
- On the VERY FIRST LINE of your output, write exactly:
  CHANGED_SECTIONS: Section Name One, Section Name Two
  (comma-separated list of heading names you will modify — nothing else on that line)
- Preserve all unaffected sections EXACTLY as they appear in the previous version.
- Only rewrite sections directly relevant to the change instructions."""
        )
    else:
        parts.append("\nCHANGED_SECTIONS: All Sections")

    parts.append("\nGenerate the complete document now:")
    return "\n".join(parts)


def build_section_prompt(
    section_name: str, current_content: str, new_instructions: str, doc_type: str
) -> str:
    brand_guide = load_brand_guide()
    return f"""You are a professional technical writer. Rewrite only the section below according to the new instructions.

BRAND GUIDE:
{_waf_safe(brand_guide)}

DOCUMENT TYPE: {doc_type}
SECTION TO REWRITE: {section_name}

CURRENT SECTION CONTENT:
{_waf_safe(current_content)}

NEW INSTRUCTIONS FOR THIS SECTION:
{new_instructions}

Output ONLY the rewritten section content in markdown. Do not include other sections. No preamble."""


def _call_ollama(prompt: str, model: str | None = None) -> str:
    """Stream from Ollama and return the full response string."""
    active_model = model or OLLAMA_MODEL
    payload = {"model": active_model, "prompt": prompt, "stream": True}
    full_response: list[str] = []

    headers = {
        "Content-Type": "application/json",
        "Origin": "http://localhost",
    }
    with httpx.Client(timeout=300.0) as client:
        with client.stream(
            "POST", f"{OLLAMA_BASE_URL}/api/generate", json=payload, headers=headers
        ) as response:
            response.raise_for_status()
            for line in response.iter_lines():
                if line:
                    chunk = json.loads(line)
                    full_response.append(chunk.get("response", ""))
                    if chunk.get("done"):
                        break

    return "".join(full_response)


def _parse_changed_sections(raw: str) -> tuple[str, list[str]]:
    lines = raw.split("\n")
    if lines and lines[0].strip().startswith("CHANGED_SECTIONS:"):
        sections_str = lines[0].split(":", 1)[1].strip()
        sections = [s.strip() for s in sections_str.split(",") if s.strip()]
        return "\n".join(lines[1:]).strip(), sections
    return raw, []


def generate_document(
    doc_type: str,
    instructions: str,
    previous_content: str | None = None,
    model: str | None = None,
) -> tuple[str, list[str]]:
    prompt = build_prompt(doc_type, instructions, previous_content)
    raw = _call_ollama(prompt, model)
    return _parse_changed_sections(raw)


def generate_section(
    section_name: str,
    current_content: str,
    new_instructions: str,
    doc_type: str,
    model: str | None = None,
) -> str:
    prompt = build_section_prompt(section_name, current_content, new_instructions, doc_type)
    return _call_ollama(prompt, model)
