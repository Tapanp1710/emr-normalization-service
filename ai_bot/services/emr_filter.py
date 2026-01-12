"""
EMR → LLM Normalization Layer

SINGLE source of truth for:
- History filtering
- Examination filtering
- Investigation filtering
- Risk flag derivation
- Priority scoring
- Final LLM payload builder

Design goals:
- Deterministic output
- Clinically meaningful
- Auditable
- LLM-safe
"""

# FROZEN: Clinical logic validated.
# Changes require test updates and explicit review. Do not modify without adding tests.


from typing import Any, Dict, List, Set
from datetime import datetime
import re


# =================================================
# ENTRY POINT
# =================================================

def build_llm_payload(context: Dict[str, Any]) -> Dict[str, Any]:
    """
    FINAL entry point used by AI service layer.

    Adds audit and safety metadata to the result for explainability.
    """

    history = context.get("history", {})
    examination = context.get("examination", {})
    investigation = context.get("investigation", [])

    # audit structure collects discarded fields and parsing warnings
    audit = {"discarded": [], "warnings": []}

    # simple safety scan
    safety = check_forbidden_terms(context)

    history_findings = extract_history_findings(history, audit=audit)
    exam_findings = extract_examination_findings(examination, audit=audit)
    lab_findings = extract_investigation_findings(investigation, audit=audit)

    # parsed labs for numeric interpretation
    parsed_labs = parse_investigations(investigation, audit=audit)

    risk_flags = derive_clinical_risks(
        history_findings,
        exam_findings,
        parsed_labs,
    )

    prioritized_context = prioritize_context(
        history_findings,
        exam_findings,
        lab_findings,
        risk_flags,
    )

    return {
        "clinical_context": prioritized_context,
        "meta": {
            "generated_at": datetime.utcnow().isoformat(),
            "version": "1.0.0",
            "risk_flags": risk_flags,
            "audit": audit,
            "safety": safety,
            "parsed_labs": parsed_labs,
        },
    }


# =================================================
# HISTORY FILTERING
# =================================================

def extract_history_findings(history: Dict[str, Any], audit: Dict[str, Any] = None) -> List[str]:
    findings: Set[str] = set()

    templates = history.get("templates", [])
    _process_templates(
        findings,
        templates,
        default_label="History",
        audit=audit,
    )

    return sorted(findings)


# =================================================
# EXAMINATION FILTERING
# =================================================

def extract_examination_findings(examination: Dict[str, Any], audit: Dict[str, Any] = None) -> List[str]:
    findings: Set[str] = set()

    templates = (
        examination.get("templates")
        or examination.get("templetes")
        or []
    )

    _process_templates(
        findings,
        templates,
        default_label="Examination",
        section_label_resolver=normalize_section_label,
        audit=audit,
    )

    return sorted(findings)


# =================================================
# INVESTIGATION FILTERING
# =================================================

def extract_investigation_findings(investigation: Any, audit: Dict[str, Any] = None) -> List[str]:
    findings: List[str] = []

    if audit is None:
        audit = {"discarded": [], "warnings": []}

    if not isinstance(investigation, list):
        audit["discarded"].append("investigation: not a list")
        return findings

    for lab in investigation:
        if not isinstance(lab, dict):
            audit["discarded"].append(f"investigation: skipped non-dict entry {repr(lab)}")
            continue

        name = lab.get("name")
        value = lab.get("value")

        if not name:
            audit["discarded"].append(f"investigation: skipped lab with missing name {lab}")
            continue

        if value in ("", None):
            audit["discarded"].append(f"investigation: skipped {name} with empty value")
            continue

        # Ignore textual 'normal' results
        if isinstance(value, str) and value.strip().lower() == "normal":
            audit["discarded"].append(f"investigation: skipped {name}=='normal'")
            continue

        unit = lab.get("unit", "")
        ref = lab.get("reference") or lab.get("reference_range")

        entry = f"{name}: {value}"
        if unit:
            entry += f" {unit}"
        if ref:
            entry += f" (ref {ref})"

        findings.append(entry)

    return findings


def parse_investigations(investigation: Any, audit: Dict[str, Any] = None) -> List[Dict[str, Any]]:
    """Return parsed lab entries with numeric values when possible."""
    parsed: List[Dict[str, Any]] = []

    if audit is None:
        audit = {"discarded": [], "warnings": []}

    if not isinstance(investigation, list):
        audit["warnings"].append("parse_investigations: investigation is not a list")
        return parsed

    for lab in investigation:
        if not isinstance(lab, dict):
            audit["discarded"].append(f"parse_investigations: skipped non-dict {repr(lab)}")
            continue

        name = lab.get("name")
        value = lab.get("value")
        unit = lab.get("unit")
        ref = lab.get("reference") or lab.get("reference_range")

        if not name or value in ("", None):
            audit["discarded"].append(f"parse_investigations: skipped {lab}")
            continue

        # attempt numeric parse
        numeric = None
        raw = str(value).strip()
        try:
            # Some values can be like '8.5' or '8.2 %' — extract leading number
            m = re.search(r"[-+]?[0-9]*\.?[0-9]+", raw)
            if m:
                numeric = float(m.group(0))
        except Exception:
            audit["warnings"].append(f"parse_investigations: could not parse numeric for {name} value={raw}")

        parsed.append({
            "name": name,
            "raw_value": raw,
            "numeric_value": numeric,
            "unit": unit,
            "reference": ref,
        })

    return parsed


# =================================================
# TEMPLATE PROCESSOR
# =================================================

def _process_templates(
    findings: Set[str],
    templates: Any,
    default_label: str,
    section_label_resolver=None,
    audit: Dict[str, Any] = None,
):
    if not isinstance(templates, list):
        return

    for template in templates:
        if not isinstance(template, dict):
            continue

        if "sections" in template:
            for section in template.get("sections", []):
                label = (
                    section.get("section_name")
                    or section.get("sectionname")
                    or default_label
                )

                if section_label_resolver:
                    label = section_label_resolver(label)

                for form in section.get("forms", []):
                    _extract_data(findings, form.get("data"), label, audit=audit)

        elif "forms" in template:
            for form in template.get("forms", []):
                _extract_data(findings, form.get("data"), default_label, audit=audit)

        elif "data" in template:
            _extract_data(findings, template.get("data"), default_label, audit=audit)


# =================================================
# DATA EXTRACTION
# =================================================

def _extract_data(findings: Set[str], data: Any, label: str, audit: Dict[str, Any] = None):
    if audit is None:
        audit = {"discarded": [], "warnings": []}

    if not isinstance(data, dict):
        audit["discarded"].append(f"{label}: data not a dict")
        return

    for key, value in data.items():

        if key.lower() == "comments":
            audit["discarded"].append(f"{label}.{key}: ignored (comments)")
            continue

        if isinstance(value, list):
            for item in value:
                if _valid_value(item):
                    findings.add(f"{label}: {item}")
                else:
                    audit["discarded"].append(f"{label}.{key}: ignored list item {repr(item)}")

        elif _valid_value(value):
            key_label = key.replace("_", " ").strip()
            findings.add(f"{label} {key_label}: {value}")
        else:
            audit["discarded"].append(f"{label}.{key}: ignored value {repr(value)}")


def _valid_value(value: Any) -> bool:
    if value in ("", None):
        return False

    if isinstance(value, str) and value.strip().lower() == "normal":
        return False

    return True


# =================================================
# SECTION NORMALIZATION
# =================================================

def normalize_section_label(section_name: str) -> str:
    if not isinstance(section_name, str):
        return "General"

    s = section_name.lower()

    if any(k in s for k in ("right", "r/od", "r/", "r-")):
        return f"Right {strip_laterality(section_name)}".strip()

    if any(k in s for k in ("left", "l/os", "l/", "l-")):
        return f"Left {strip_laterality(section_name)}".strip()

    return section_name.strip()


def strip_laterality(text: str) -> str:
    """Remove laterality tokens in a case-insensitive way and clean up separators."""
    if not isinstance(text, str):
        return ""

    # Remove common laterality tokens (case-insensitive)
    cleaned = re.sub(r"(?i)\b(right|left)\b", "", text)

    # Remove common abbreviations and separators
    cleaned = re.sub(r"(?i)(r/od|l/os|r/|l/|r-|l-)", "", cleaned)

    # Collapse multiple spaces and remove stray punctuation
    cleaned = re.sub(r"[\s\-_/]+", " ", cleaned)

    # Remove empty parentheses left after stripping laterality tokens
    cleaned = re.sub(r"\(\s*\)", "", cleaned)

    # Final cleanup: collapse spaces and strip
    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    return cleaned


# =================================================
# SAFETY + RISK DERIVATION
# =================================================

# Simple forbidden terms list — keep conservative and expand as needed
FORBIDDEN_TERMS = [
    "prescribe",
    "diagnose",
    "start insulin",
    "start metformin",
    "you should",
    "do surgery",
    "operate",
]

def check_forbidden_terms(context: Any) -> Dict[str, Any]:
    """Scan input context for forbidden phrases and return a summary."""
    found = set()

    def _scan(obj: Any):
        if isinstance(obj, dict):
            for v in obj.values():
                _scan(v)
        elif isinstance(obj, list):
            for item in obj:
                _scan(item)
        elif isinstance(obj, str):
            s = obj.lower()
            for term in FORBIDDEN_TERMS:
                if term in s:
                    found.add(term)

    _scan(context)
    return {"forbidden_terms": sorted(found)}


# =================================================
# RISK DERIVATION
# =================================================

def derive_clinical_risks(
    history: List[str],
    exam: List[str],
    parsed_labs: List[Dict[str, Any]],
) -> List[str]:
    risks: Set[str] = set()

    if any("diabetes" in h.lower() for h in history):
        risks.add("long-standing diabetes")

    if any("phthisis" in e.lower() for e in exam):
        risks.add("single seeing eye")

    # Numeric HbA1c interpretation
    for lab in parsed_labs:
        name = (lab.get("name") or "").lower()
        num = lab.get("numeric_value")
        if "hba1c" in name:
            if num is not None and num >= 8.0:
                risks.add("poor glycemic control")
            else:
                # fallback: if textual value contains '8' or '9'
                raw = (lab.get("raw_value") or "").lower()
                if any(d in raw for d in ("8", "9")):
                    risks.add("poor glycemic control")

    return sorted(risks)


# =================================================
# PRIORITIZATION
# =================================================

def prioritize_context(
    history: List[str],
    exam: List[str],
    labs: List[str],
    risks: List[str],
) -> Dict[str, List[str]]:
    """
    Ensures LLM sees critical info first.
    """

    return {
        "high_priority": exam + risks,
        "medium_priority": labs,
        "low_priority": history,
    }
