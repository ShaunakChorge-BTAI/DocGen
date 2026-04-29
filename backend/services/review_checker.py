import json
from services.llm_service import _call_ollama

_PROMPT = """You are a senior technical writer reviewing a {doc_type} document for quality issues.

Analyse the document below and identify problems in these four categories:
- completeness_gap: required sections missing or underdeveloped
- contradiction: conflicting statements between sections
- missing_requirement: vague or unspecified requirements that should be concrete
- structural: sections out of order or inappropriately placed

Return ONLY a valid JSON array. Each element must have exactly these fields:
  "section"     — heading name the issue belongs to (use "General" if not section-specific)
  "issue_type"  — one of the four categories above
  "description" — clear, actionable description of the problem (1-2 sentences)

If no issues are found, return an empty array: []

DOCUMENT ({doc_type}):
{content}

JSON:"""


def run_ai_review(doc_type: str, markdown_content: str, model: str | None = None) -> list[dict]:
    prompt = _PROMPT.format(doc_type=doc_type, content=markdown_content)
    raw = _call_ollama(prompt, model).strip()

    start = raw.find("[")
    end = raw.rfind("]") + 1
    if start == -1 or end == 0:
        return []

    try:
        items = json.loads(raw[start:end])
    except json.JSONDecodeError:
        return []

    valid_types = {"completeness_gap", "contradiction", "missing_requirement", "structural"}
    result = []
    for item in items:
        if not isinstance(item, dict):
            continue
        if not all(k in item for k in ("section", "issue_type", "description")):
            continue
        result.append({
            "section": str(item["section"]),
            "issue_type": str(item["issue_type"]) if item["issue_type"] in valid_types else "completeness_gap",
            "description": str(item["description"]),
        })
    return result
