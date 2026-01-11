"""
EMR → LLM Normalization Layer

SINGLE source of truth for:
- History filtering
- Examination filtering
- Investigation (labs) placeholder
- Final LLM payload builder

DO NOT parse EMR anywhere else.
DO NOT rewrite logic during integration.
"""


# -------------------------------------------------
# HISTORY FILTERING
# -------------------------------------------------

def extract_history_findings(history: dict) -> list:
    """
    Extracts meaningful history from EMR history templates.
    Works with:
    - templates → sections → forms → data
    - templates → forms → data
    - templates → data
    """
    findings = []

    if not isinstance(history, dict):
        return findings

    templates = history.get("templates", [])
    for template in templates:

        if not isinstance(template, dict):
            continue

        # Case 1: templates → sections → forms → data
        if "sections" in template:
            for section in template.get("sections", []):
                label = section.get("section_name", "History")

                for form in section.get("forms", []):
                    data = form.get("data")
                    _extract_data(findings, data, label)

        # Case 2: templates → forms → data
        elif "forms" in template:
            for form in template.get("forms", []):
                data = form.get("data")
                _extract_data(findings, data, "History")

        # Case 3: templates → data
        elif "data" in template:
            _extract_data(findings, template.get("data"), "History")

    return findings


# -------------------------------------------------
# EXAMINATION FILTERING
# -------------------------------------------------

def extract_examination_findings(examination: dict):
    """
    Extracts examination findings from EMR templates.
    Works with:
    - templates → sections → forms → data
    - templates → forms → data
    - templates → data
    """
    findings = []

    if not isinstance(examination, dict):
        return findings

    templates = examination.get("templetes", [])
    for template in templates:

        if not isinstance(template, dict):
            continue

        # Case 1: templates → sections → forms → data
        if "sections" in template:
            for section in template.get("sections", []):
                section_label = normalize_section_label(
                    section.get("sectionname", "")
                )

                for form in section.get("forms", []):
                    data = form.get("data")
                    _extract_data(findings, data, section_label)

        # Case 2: templates → forms → data
        elif "forms" in template:
            for form in template.get("forms", []):
                data = form.get("data")
                _extract_data(findings, data, "General")

        # Case 3: templates → data
        elif "data" in template:
            _extract_data(findings, template.get("data"), "General")

    return findings


# -------------------------------------------------
# INVESTIGATION / LAB FILTERING (STUB)
# -------------------------------------------------

def extract_investigation_findings(investigation) -> list:
    """
    TEMPORARY placeholder.
    Real EMR lab payloads will be wired later.
    """
    findings = []

    # Mock / normalized labs
    if isinstance(investigation, list):
        for lab in investigation:
            if not isinstance(lab, dict):
                continue

            name = lab.get("name")
            value = lab.get("value")
            unit = lab.get("unit", "")
            ref = lab.get("reference")

            if not name or value is None:
                continue

            if ref:
                findings.append(f"{name}: {value} {unit} (ref {ref})")
            else:
                findings.append(f"{name}: {value} {unit}".strip())

    elif investigation:
        findings.append("Lab data available (details pending)")

    return findings


# -------------------------------------------------
# SHARED DATA EXTRACTION
# -------------------------------------------------

def _extract_data(findings: list, data, label: str):
    """
    Extracts meaningful values from a data dictionary.
    Skips empty, normal, and comment fields.
    """
    if not isinstance(data, dict):
        return

    for key, value in data.items():

        if key == "comments":
            continue

        # List values (symptoms, conditions)
        if isinstance(value, list):
            for item in value:
                if item:
                    findings.append(f"{label}: {item}")

        # Scalar values
        elif isinstance(value, (str, int, float)):
            value_str = str(value).strip()
            if value_str and value_str.lower() != "normal":
                findings.append(
                    f"{label} {key.replace('_', ' ')}: {value_str}"
                )


# -------------------------------------------------
# SECTION LABEL NORMALIZATION
# -------------------------------------------------

def normalize_section_label(section_name: str) -> str:
    """
    Normalizes section labels in a department-agnostic way.
    Handles laterality safely without duplication.
    """
    if not section_name or not isinstance(section_name, str):
        return "General"

    original = section_name.strip()
    s = original.lower()

    # Right side
    if any(k in s for k in ["right", "r/od", "r/", "r-"]):
        cleaned = original.replace("Right", "").replace("right", "").strip(" -/")
        return f"Right {cleaned}".strip()

    # Left side
    if any(k in s for k in ["left", "l/os", "l/", "l-"]):
        cleaned = original.replace("Left", "").replace("left", "").strip(" -/")
        return f"Left {cleaned}".strip()

    return original


# -------------------------------------------------
# FINAL PAYLOAD BUILDER (ENTRY POINT)
# -------------------------------------------------

def build_llm_payload(context: dict) -> dict:
    """
    FINAL entry point used by views.py
    """

    history = context.get("history", {})
    examination = context.get("examination", {})
    investigation = context.get("investigation", [])

    return {
        "clinical_context": {
            "history": extract_history_findings(history),
            "examination": extract_examination_findings(examination),
            "investigations": extract_investigation_findings(investigation)
        }
    }
