# FROZEN: Report generation logic validated.
# Changes require test updates and explicit review. Do not modify without adding tests.

from typing import Dict, Any, List
import re

# Deterministic report generator
# Converts normalized payload from `build_llm_payload` into a safe, auditable `ai_output` structure.

RISK_TO_ACTIONS = {
    "single seeing eye": ["Urgent ophthalmology review", "Warn about vision preservation"],
    "long-standing diabetes": ["Detailed retinal examination", "Optimize blood glucose control"],
    "poor glycemic control": ["Optimize blood glucose control", "Consider HbA1c recheck & diabetes clinic referral"],
}


def _shorten(text: str, max_len: int = 140) -> str:
    text = (text or "").strip()
    if len(text) <= max_len:
        return text
    return text[: max_len - 1].rstrip() + "…"


def _normalize_text(s: str) -> str:
    """Clean stray characters and normalize spacing"""
    s = (s or "").strip()
    # remove stray empty parentheses
    s = s.replace("()", "")
    # collapse multiple spaces
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def _humanize_finding(finding: str) -> str:
    """Convert raw finding strings to clinician-friendly bullets."""
    if not finding or not isinstance(finding, str):
        return ""

    finding = _normalize_text(finding)

    # Split at first ': '
    if ": " in finding:
        left, right = finding.split(": ", 1)
        left = left.strip()
        right = right.strip()
    else:
        left = finding.strip()
        right = ""

    # Short circuit for common patterns
    # Eye-related: "Left Eye posterior segment: Mild NPDR changes" -> "Left eye: Mild NPDR changes"
    m = re.match(r"(?i)\b(left|right)\b.*eye", left)
    if m:
        # Extract laterality and the rest
        lat = m.group(1).capitalize()
        # Use right side as main message
        if right:
            return f"{lat} eye: {right}"
        return f"{lat} eye: {left}"

    # Lab-like: left is lab name
    if left.lower().startswith("hba1c") or left.lower().startswith("hb") or left.lower().startswith("creatinine") or left.lower().startswith("cholesterol") or left.lower().startswith("fasting glucose"):
        # Normalize spacing around percent signs
        r = right.replace(" %", "%")
        r = r.replace(" % (", "% (")
        return f"{left}: {r}"

    # General: If left contains 'general' drop it and present key
    if left.lower().startswith("general"):
        # e.g., 'General blood pressure: 120/80' -> 'Blood pressure: 120/80'
        content = left[len("General"):].strip()
        if content:
            if right:
                return f"{content.capitalize()}: {right}"
            return f"{content.capitalize()}: {right}"

    # Fallback: title-case the left label
    if right:
        return f"{left}: {right}"

    return left


def _normalize_key_for_dedup(s: str) -> str:
    """Create a normalized key for deduplication by removing numbers and punctuation."""
    s = (s or "").lower()
    # remove digits and punctuation
    s = re.sub(r"[^a-z\s]", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def generate_report(payload: Dict[str, Any]) -> Dict[str, Any]:
    ctx = payload.get("clinical_context", {})
    risks: List[str] = payload.get("meta", {}).get("risk_flags", []) or []

    high = ctx.get("high_priority", []) or []
    medium = ctx.get("medium_priority", []) or []
    low = ctx.get("low_priority", []) or []

    # Build ordered list of raw findings (priority preserved)
    ordered_findings = high + medium + low

    # Humanize & deduplicate findings, preserving order
    insights: List[str] = []
    seen_keys = set()
    for raw in ordered_findings:
        h = _humanize_finding(str(raw))
        key = _normalize_key_for_dedup(h)
        if not h or key in seen_keys:
            continue
        insights.append(_shorten(h))
        seen_keys.add(key)
        if len(insights) >= 6:
            break

    # Add humanized risk messages after insights, avoid duplicates
    for r in risks:
        if r == "poor glycemic control":
            msg = "Poor glycemic control noted; consider tighter glucose control."
        elif r == "long-standing diabetes":
            msg = "Long-standing diabetes noted; check for chronic complications."
        elif r == "single seeing eye":
            msg = "Single-seeing eye detected; prioritize protecting vision."
        else:
            msg = r
        key = _normalize_key_for_dedup(msg)
        if key not in seen_keys:
            insights.append(msg)
            seen_keys.add(key)

    # Summary: prefer explicit HbA1c numeric mention if available
    parsed = payload.get("meta", {}).get("parsed_labs", []) or []
    hba1c = None
    for lab in parsed:
        if (lab.get("name") or "").lower().startswith("hba1c"):
            hba1c = lab.get("numeric_value") or lab.get("raw_value")
            break

    if insights:
        top = insights[0]
        if risks:
            risk_text = ", ".join(risks)
            if hba1c is not None:
                summary = _shorten(f"{top}. Key risks include {risk_text}; HbA1c {hba1c} %.")
            else:
                summary = _shorten(f"{top}. Key risks include {risk_text}.")
        else:
            summary = _shorten(top)
    else:
        summary = _shorten(f"Key risks: {', '.join(risks)}") if risks else ""

    # Clinical risks (pass-through)
    clinical_risks = risks

    # Suggested next steps: aggregate action items for all risks
    suggested: List[str] = []
    for r in risks:
        suggested.extend(RISK_TO_ACTIONS.get(r, ["Clinical review"]))

    # Deduplicate preserving order
    seen = set()
    suggested_unique = []
    for s in suggested:
        if s not in seen:
            suggested_unique.append(s)
            seen.add(s)

    # Confidence: simple heuristic — medium if any risks, low otherwise
    confidence = "medium" if risks else "low"

    ai_output = {
        "summary": summary,
        "key_insights": insights,
        "clinical_risks": clinical_risks,
        "suggested_next_steps": suggested_unique or ["Clinical review"],
        "confidence_level": confidence,
    }

    # Include safety warnings if present
    safety = payload.get("meta", {}).get("safety", {}) or {}
    if safety.get("forbidden_terms"):
        ai_output["safety_warnings"] = [f"Forbidden term detected: {t}" for t in safety.get("forbidden_terms")]

    # Include audit if present (for transparency)
    audit = payload.get("meta", {}).get("audit")

    result = {
        "status": "success",
        "case_id": None,
        "patient_id": None,
        "ai_output": ai_output,
    }

    if audit is not None:
        result["audit"] = audit

    return result
