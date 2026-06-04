"""
DBAnalyser — Rule Engine Base Classes
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class RuleFinding:
    """A single issue produced by a rule."""
    category:       str
    issue:          str
    severity:       str            # Critical | High | Medium | Low
    recommendation: str
    line_number:    Optional[int]  = None
    snippet:        Optional[str]  = None
    rule_id:        Optional[str]  = None


@dataclass
class SQLObject:
    """A SQL object passed to each rule for analysis."""
    name:       str
    obj_type:   str               # Stored Procedure | View | Table | Function | Trigger
    schema:     str               = "dbo"
    source:     str               = ""   # raw SQL text
    file_path:  Optional[str]     = None
    lines:      int               = 0
    size_kb:    float             = 0.0

    # pre-computed helpers (set by analyser before passing to rules)
    source_upper: str             = field(default="", repr=False)
    source_lines: List[str]       = field(default_factory=list, repr=False)

    def __post_init__(self):
        if not self.source_upper:
            self.source_upper = self.source.upper()
        if not self.source_lines:
            self.source_lines = self.source.splitlines()
        if not self.lines:
            self.lines = len(self.source_lines)


class BaseRule(ABC):
    """Abstract base for all analysis rules."""

    rule_id:  str = ""
    category: str = ""
    enabled:  bool = True

    @abstractmethod
    def analyse(self, obj: SQLObject) -> List[RuleFinding]:
        ...

    # ── shared helpers ────────────────────────────────────────────────────────
    @staticmethod
    def find_pattern(pattern: str, text: str,
                     flags: int = re.IGNORECASE) -> List[re.Match]:
        return list(re.finditer(pattern, text, flags))

    @staticmethod
    def line_of(match: re.Match, source: str) -> int:
        return source[: match.start()].count("\n") + 1

    @staticmethod
    def snippet_at(lines: List[str], lineno: int, context: int = 2) -> str:
        lo = max(0, lineno - context - 1)
        hi = min(len(lines), lineno + context)
        return "\n".join(lines[lo:hi])

    @staticmethod
    def strip_comments(sql: str) -> str:
        """Remove /* */ and -- comments (approximate)."""
        sql = re.sub(r"/\*.*?\*/", " ", sql, flags=re.DOTALL)
        sql = re.sub(r"--[^\n]*", " ", sql)
        return sql

    @staticmethod
    def strip_strings(sql: str) -> str:
        """Replace quoted string literals with empty quotes."""
        return re.sub(r"'[^']*'", "''", sql)

    def _safe_source(self, obj: SQLObject) -> str:
        return self.strip_strings(self.strip_comments(obj.source))
