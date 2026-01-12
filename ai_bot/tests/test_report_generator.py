import sys
import json
from pathlib import Path
sys.path.insert(0, "config")

from ai_bot.services.emr_filter import build_llm_payload
from ai_bot.services.report_generator import generate_report


def sample_emr():
    return {
        "history": {
            "templates": [
                {
                    "sections": [
                        {
                            "section_name": "Past Medical History",
                            "forms": [
                                {"data": {"conditions": ["Type 2 Diabetes Mellitus", "Hypertension"], "comments": ""}},
                            ]
                        }
                    ]
                }
            ]
        },
        "examination": {
            "templetes": [
                {
                    "sections": [
                        {"sectionname": "Right Eye (R/OD)", "forms": [{"data": {"appearance_symptoms": ["Phthisis Bulbi"]}}]},
                        {"sectionname": "Left Eye (L/OS)", "forms": [{"data": {"posterior_segment": "Mild NPDR changes"}}]},
                    ]
                }
            ]
        },
        "investigation": [
            {"name": "HbA1c", "value": "9.1", "unit": "%"},
        ]
    }


def test_generate_report_basic():
    payload = build_llm_payload(sample_emr())
    report = generate_report(payload)

    assert report.get("status") == "success"
    ai_out = report.get("ai_output", {})
    assert "summary" in ai_out and isinstance(ai_out["summary"], str)
    assert isinstance(ai_out["key_insights"], list)
    assert ai_out["clinical_risks"] == payload["meta"]["risk_flags"]

    # Suggested steps should include diabetes-related actions
    steps = ai_out["suggested_next_steps"]
    assert any("retinal" in s.lower() or "glucose" in s.lower() for s in steps)

    # Confidence should be medium because risks exist
    assert ai_out["confidence_level"] == "medium"


def test_safety_warnings_present_in_report():
    # Create a payload that will trigger a forbidden term
    sample = {
        "history": {"templates": [{"sections": [{"section_name": "Past Medical History", "forms": [
            {"data": {"notes": "Please start insulin now"}}
        ]}]}]},
        "examination": {},
        "investigation": [],
    }

    payload = build_llm_payload(sample)
    report = generate_report(payload)

    ai_out = report.get("ai_output", {})
    assert "safety_warnings" in ai_out
    assert any("start insulin" in s.lower() for s in ai_out.get("safety_warnings", []))

    # Audit should be present in the top-level result
    assert "audit" in report and "discarded" in report["audit"]


def test_generate_report_no_risks():
    # A payload with no risks should return low confidence and a fallback step
    p = build_llm_payload({"history": {}, "examination": {}, "investigation": []})
    r = generate_report(p)
    assert r["ai_output"]["confidence_level"] == "low"
    assert r["ai_output"]["suggested_next_steps"] == ["Clinical review"]
