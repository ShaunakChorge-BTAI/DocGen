"""
GDPR Compliance Rule Pack
=========================
Rules detect patterns that may violate GDPR data-privacy requirements:
PII column naming, SELECT * on PII tables, unmasked personal data exposure,
logging of personal data, and missing retention controls.

Rule IDs: GDPR001 – GDPR006
"""

from __future__ import annotations

import re
from typing import List

from dbanalyser.engine.rules.base import BaseRule, RuleFinding, SQLObject

# Common PII column-name patterns
_PII_COLUMN_PATTERNS = re.compile(
    r'\b(email|e_mail|phone|mobile|cell_?phone|telephone|'
    r'ssn|social_?security|national_?id|nric|pan_?no|aadhar|aadhaar|'
    r'passport|passport_?no|passport_?number|'
    r'dob|date_?of_?birth|birth_?date|birthdate|'
    r'first_?name|last_?name|full_?name|given_?name|surname|'
    r'address|street|postcode|zip_?code|'
    r'credit_?card|card_?number|cvv|'
    r'ip_?address|user_?ip|'
    r'gender|ethnicity|religion|biometric)\b',
    re.IGNORECASE,
)

# Column-name patterns for masking / encryption
_MASKING_PATTERNS = re.compile(
    r'\b(masked|mask|encrypt|hashed|hash|anonymi[sz]e|'
    r'HASHBYTES|ENCRYPTBYKEY|DECRYPTBYKEY|CONVERT.*VARBINARY)\b',
    re.IGNORECASE,
)


def _has_pii_reference(source: str) -> bool:
    return bool(_PII_COLUMN_PATTERNS.search(source))


class GdprPiiColumnInSelectStarRule(BaseRule):
    """GDPR001 — SELECT * on a table that appears to contain PII columns."""
    rule_id  = "GDPR001"
    category = "Compliance-GDPR"

    def analyse(self, obj: SQLObject) -> List[RuleFinding]:
        if not _has_pii_reference(obj.source):
            return []
        findings = []
        src = self._safe_source(obj)
        for m in re.finditer(r'\bSELECT\s+\*', src, re.IGNORECASE):
            ln = self.line_of(m, src)
            findings.append(RuleFinding(
                rule_id=self.rule_id, category=self.category,
                severity="High",
                issue="SELECT * on an object that references PII columns — exposes all personal data",
                recommendation=(
                    "Under GDPR's data-minimisation principle, only retrieve columns that are "
                    "strictly necessary. Replace SELECT * with an explicit column list, "
                    "and exclude PII columns unless the consumer has a lawful basis."
                ),
                line_number=ln,
                snippet=self.snippet_at(obj.source_lines, ln),
            ))
        return findings


class GdprPiiInPrintOrRaiserrorRule(BaseRule):
    """GDPR002 — Personal data column referenced in PRINT or RAISERROR — logs PII."""
    rule_id  = "GDPR002"
    category = "Compliance-GDPR"

    _LOG_RE = re.compile(r'\b(PRINT|RAISERROR|THROW)\b', re.IGNORECASE)

    def analyse(self, obj: SQLObject) -> List[RuleFinding]:
        findings = []
        src = self._safe_source(obj)
        for m in self._LOG_RE.finditer(src):
            # Grab the rest of the statement line
            line_end = src.find("\n", m.start())
            if line_end == -1:
                line_end = len(src)
            stmt = src[m.start(): line_end]
            if _PII_COLUMN_PATTERNS.search(stmt):
                ln = self.line_of(m, src)
                findings.append(RuleFinding(
                    rule_id=self.rule_id, category=self.category,
                    severity="High",
                    issue="PII column reference inside PRINT/RAISERROR — personal data may be logged",
                    recommendation=(
                        "Never log personal data in error messages or diagnostic output. "
                        "Use anonymised identifiers (e.g. record ID) in log statements."
                    ),
                    line_number=ln,
                    snippet=self.snippet_at(obj.source_lines, ln),
                ))
        return findings


class GdprUnmaskedPiiReturnRule(BaseRule):
    """GDPR003 — View or procedure returns PII columns without any masking."""
    rule_id  = "GDPR003"
    category = "Compliance-GDPR"

    def analyse(self, obj: SQLObject) -> List[RuleFinding]:
        if obj.obj_type not in ("View", "Stored Procedure", "Function"):
            return []
        if not _has_pii_reference(obj.source):
            return []
        src = obj.source
        has_masking = bool(_MASKING_PATTERNS.search(src))
        if not has_masking:
            return [RuleFinding(
                rule_id=self.rule_id, category=self.category,
                severity="High",
                issue=(
                    f"Object '{obj.name}' returns PII columns without masking or encryption"
                ),
                recommendation=(
                    "Apply dynamic data masking (DDM), column-level encryption, or "
                    "explicit string masking (e.g. STUFF(email,2,LEN(email)-5,'***')) "
                    "before returning personal data to callers."
                ),
                line_number=1,
            )]
        return []


class GdprHardcodedPersonalDataRule(BaseRule):
    """GDPR004 — Hardcoded string that looks like personal data (email, phone number)."""
    rule_id  = "GDPR004"
    category = "Compliance-GDPR"

    _EMAIL_RE  = re.compile(r"'[^']*@[^']+\.[a-zA-Z]{2,}'")
    _PHONE_RE  = re.compile(r"'\+?[0-9][0-9\s\-]{8,20}'")

    def analyse(self, obj: SQLObject) -> List[RuleFinding]:
        findings = []
        for pattern, label in [
            (self._EMAIL_RE, "email address"),
            (self._PHONE_RE, "phone number"),
        ]:
            for m in pattern.finditer(obj.source):
                ln = self.line_of(m, obj.source)
                findings.append(RuleFinding(
                    rule_id=self.rule_id, category=self.category,
                    severity="Medium",
                    issue=f"Hardcoded {label} literal detected — personal data should not be embedded in code",
                    recommendation=(
                        "Remove hardcoded personal data from SQL objects. "
                        "Use parameterised queries or reference tables instead."
                    ),
                    line_number=ln,
                    snippet=self.snippet_at(obj.source_lines, ln),
                ))
        return findings


class GdprMissingRetentionHintRule(BaseRule):
    """GDPR005 — Table with PII columns has no retention / deletion logic nearby."""
    rule_id  = "GDPR005"
    category = "Compliance-GDPR"

    _RETENTION_RE = re.compile(
        r'\b(retention|purge|archive|delete_?after|expir|gdpr|data_?lifecycle)\b',
        re.IGNORECASE,
    )

    def analyse(self, obj: SQLObject) -> List[RuleFinding]:
        # Only relevant for CREATE TABLE statements
        if obj.obj_type != "Table":
            return []
        if not _has_pii_reference(obj.source):
            return []
        has_retention = bool(self._RETENTION_RE.search(obj.source))
        if not has_retention:
            return [RuleFinding(
                rule_id=self.rule_id, category=self.category,
                severity="Medium",
                issue=(
                    f"Table '{obj.name}' stores PII but has no retention or expiry hint in its definition"
                ),
                recommendation=(
                    "Add a comment or companion procedure that documents the data-retention policy "
                    "for this table (e.g. '-- GDPR: retain 6 years, purge via sp_PurgePersonalData'). "
                    "GDPR Article 5(1)(e) requires data not to be kept longer than necessary."
                ),
                line_number=1,
            )]
        return []


class GdprNoConsentCheckRule(BaseRule):
    """GDPR006 — Procedure inserts personal data without any consent-check reference."""
    rule_id  = "GDPR006"
    category = "Compliance-GDPR"

    _CONSENT_RE = re.compile(
        r'\b(consent|opt_?in|opt_?out|privacy|gdpr_?flag|marketing_?flag|is_?consented)\b',
        re.IGNORECASE,
    )

    def analyse(self, obj: SQLObject) -> List[RuleFinding]:
        if obj.obj_type != "Stored Procedure":
            return []
        src = self._safe_source(obj)
        has_insert_pii = (
            bool(re.search(r'\bINSERT\s+INTO\b', src, re.IGNORECASE))
            and _has_pii_reference(src)
        )
        if not has_insert_pii:
            return []
        has_consent = bool(self._CONSENT_RE.search(src))
        if not has_consent:
            return [RuleFinding(
                rule_id=self.rule_id, category=self.category,
                severity="Medium",
                issue=(
                    f"Procedure '{obj.name}' inserts personal data without referencing consent status"
                ),
                recommendation=(
                    "Before inserting personal data, verify that the data subject has given "
                    "valid consent (GDPR Article 6). Reference a consent flag or consent-check "
                    "function in the procedure."
                ),
                line_number=1,
            )]
        return []


GDPR_RULES: List[BaseRule] = [
    GdprPiiColumnInSelectStarRule(),
    GdprPiiInPrintOrRaiserrorRule(),
    GdprUnmaskedPiiReturnRule(),
    GdprHardcodedPersonalDataRule(),
    GdprMissingRetentionHintRule(),
    GdprNoConsentCheckRule(),
]
