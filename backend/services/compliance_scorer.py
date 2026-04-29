import json
from pathlib import Path
from services.llm_service import _call_ollama

RUBRICS_DIR = (Path(__file__).resolve().parent.parent.parent / "config" / "rubrics").resolve()

_PROMPT = """You are a document quality auditor. Score the following {doc_type} document against the compliance rubric.

RUBRIC:
{rubric}

DOCUMENT ({doc_type}):
{content}

For each numbered criterion in the rubric, assess whether the document meets it.
Return ONLY a valid JSON object with this exact structure:
{{
  "score": <integer 0-100, weighted average of pass/fail criteria>,
  "criteria": [
    {{"criterion": "<name>", "status": "pass", "note": "<one sentence reason>"}},
    {{"criterion": "<name>", "status": "fail", "note": "<one sentence reason>"}}
  ]
}}

JSON:"""


def list_rubrics() -> list[str]:
    if not RUBRICS_DIR.exists():
        return []
    return sorted(f.stem for f in RUBRICS_DIR.glob("*.md"))


def _load_rubric(name: str) -> str:
    safe = Path(name).name
    path = (RUBRICS_DIR / f"{safe}.md").resolve()
    if not str(path).startswith(str(RUBRICS_DIR)):
        raise ValueError("Invalid rubric name")
    if not path.exists():
        raise FileNotFoundError(f"Rubric '{name}' not found")
    return path.read_text(encoding="utf-8")


def score_document(doc_type: str, markdown_content: str, rubric_name: str, model: str | None = None) -> dict:
    rubric = _load_rubric(rubric_name)
    prompt = _PROMPT.format(doc_type=doc_type, rubric=rubric, content=markdown_content)
    raw = _call_ollama(prompt, model).strip()

    start = raw.find("{")
    end = raw.rfind("}") + 1
    if start == -1 or end == 0:
        return {"score": 0, "criteria": []}

    try:
        parsed = json.loads(raw[start:end])
    except json.JSONDecodeError:
        return {"score": 0, "criteria": []}

    criteria = []
    for c in parsed.get("criteria", []):
        if not isinstance(c, dict):
            continue
        criteria.append({
            "criterion": str(c.get("criterion", "")),
            "status": "pass" if str(c.get("status", "")).lower() == "pass" else "fail",
            "note": str(c.get("note", "")),
        })

    try:
        score = max(0, min(100, int(parsed.get("score", 0))))
    except (ValueError, TypeError):
        passed = sum(1 for c in criteria if c["status"] == "pass")
        score = round(passed / len(criteria) * 100) if criteria else 0

    return {"score": score, "criteria": criteria}
