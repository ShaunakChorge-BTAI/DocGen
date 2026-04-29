import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent

DOC_TYPE_MAP = {
    "BRD": "BRD.md",
    "FSD": "FSD.md",
    "SRS": "SRS.md",
    "User Manual": "User-Manual.md",
    "Product Brochure": "Product-Brochure.md",
}


def load_template(doc_type: str) -> str:
    filename = DOC_TYPE_MAP.get(doc_type)
    if not filename:
        raise ValueError(f"Unknown document type: {doc_type}")
    path = BASE_DIR / "doc-templates" / filename
    return path.read_text(encoding="utf-8")


def load_brand_guide() -> str:
    path = BASE_DIR / "config" / "brand-guide.md"
    return path.read_text(encoding="utf-8")


def load_system_prompt() -> str:
    path = BASE_DIR / "prompts" / "system-prompt.md"
    return path.read_text(encoding="utf-8")


def load_brand_config() -> dict:
    """Parse structured config values from brand-guide.md."""
    content = load_brand_guide()
    config: dict = {}
    field_map = {
        "- Company Name:": "company_name",
        "- Product Name:": "product_name",
        "- Industry:": "industry",
        "- Default Author:": "default_author",
        "- Default Author Role:": "default_author_role",
        "- Default Reviewer:": "default_reviewer",
        "- Default Approver:": "default_approver",
    }
    for line in content.splitlines():
        line = line.strip()
        for prefix, key in field_map.items():
            if line.startswith(prefix):
                config[key] = line.split(":", 1)[1].strip()
    return config
