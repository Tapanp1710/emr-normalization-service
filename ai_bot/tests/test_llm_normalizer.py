import json
from ai_bot.services.emr_filter import build_llm_payload


# ============================================================
# MAIN INTEGRATION TEST
# ============================================================

def test_llm_payload():
    """
    Integration-style test for the EMR → LLM normalization pipeline.

    Verifies:
    - Structural integrity of the payload
    - Correct prioritization (high / medium / low)
    - Correct clinical risk derivation
    """

    history_data = {
        "templates": [
            {
                "sections": [
                    {
                        "section_name": "Past Medical History",
                        "forms": [
                            {
                                "data": {
                                    "conditions": [
                                        "Type 2 Diabetes Mellitus",
                                        "Hypertension"
                                    ],
                                    "comments": ""
                                }
                            }
                        ]
                    }
                ]
            }
        ]
    }

    examination_data = {
        "templetes": [
            {
                "sections": [
                    {
                        "sectionname": "Right Eye (R/OD)",
                        "forms": [
                            {
                                "data": {
                                    "appearance_symptoms": [
                                        "Phthisis Bulbi"
                                    ]
                                }
                            }
                        ]
                    },
                    {
                        "sectionname": "Left Eye (L/OS)",
                        "forms": [
                            {
                                "data": {
                                    "posterior_segment": "Mild NPDR changes"
                                }
                            }
                        ]
                    }
                ]
            }
        ]
    }

    investigation_data = [
        {
            "name": "HbA1c",
            "value": "8.2",
            "unit": "%",
            "reference": "4.0–5.6"
        }
    ]

    payload = build_llm_payload({
        "history": history_data,
        "examination": examination_data,
        "investigation": investigation_data,
    })

    # --- Structural assertions ---
    assert isinstance(payload, dict)
    assert "clinical_context" in payload
    assert "meta" in payload
    assert payload["meta"].get("version") == "1.0.0"

    ctx = payload["clinical_context"]
    assert set(ctx.keys()) == {"high_priority", "medium_priority", "low_priority"}

    high = ctx["high_priority"]
    medium = ctx["medium_priority"]
    low = ctx["low_priority"]

    # --- Content assertions ---
    assert any("phthisis" in s.lower() for s in high), f"phthisis missing: {high}"
    assert any("npdr" in s.lower() for s in high), f"npdr missing: {high}"
    assert any("hba1c" in s.lower() for s in medium), f"hba1c missing: {medium}"
    assert any("diabetes" in s.lower() for s in low), f"diabetes missing: {low}"

    # --- Risk flags ---
    risks = payload["meta"].get("risk_flags", [])
    for expected in (
        "long-standing diabetes",
        "single seeing eye",
        "poor glycemic control",
    ):
        assert expected in risks, f"missing risk: {expected}"


# ============================================================
# EDGE CASES + LATERALITY TEST
# ============================================================

def test_edge_cases_and_laterality():
    """
    Ensures:
    - 'normal' values are ignored
    - empty fields are ignored
    - laterality labels do not duplicate
    """

    sample = {
        "history": {
            "templates": [
                {
                    "sections": [
                        {
                            "section_name": "Past Medical History",
                            "forms": [
                                {
                                    "data": {
                                        "conditions": ["Type 2 Diabetes Mellitus"],
                                        "comments": ""
                                    }
                                },
                                {
                                    "data": {
                                        "notes": "normal",
                                        "other": ""
                                    }
                                }
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
                        {
                            "sectionname": "Left Eye (L/OS)",
                            "forms": [
                                {
                                    "data": {
                                        "posterior_segment": "Mild NPDR changes"
                                    }
                                }
                            ]
                        },
                        {
                            "sectionname": "Right Eye (R/OD)",
                            "forms": [
                                {
                                    "data": {
                                        "appearance_symptoms": ["Phthisis Bulbi"]
                                    }
                                }
                            ]
                        }
                    ]
                }
            ]
        },
        "investigation": [
            {"name": "HbA1c", "value": "7.0", "unit": "%"},
            {"name": "HbA1c", "value": "8.5", "unit": "%"},
            {"name": "Random Glucose", "value": "normal", "unit": "mg/dL"},
            {"name": "BadLab"},
            "not_a_dict"
        ]
    }

    payload = build_llm_payload(sample)
    ctx = payload["clinical_context"]

    combined = " ".join(ctx["high_priority"]).lower()
    assert "left left" not in combined
    assert "right right" not in combined

    all_text = " ".join(
        ctx["high_priority"] +
        ctx["medium_priority"] +
        ctx["low_priority"]
    ).lower()

    assert "normal" not in all_text
    assert "()" not in all_text


# ============================================================
# AUDIT + SANITIZATION TEST
# ============================================================

def test_no_empty_parentheses_or_duplication_in_audit():
    """
    Ensures audit metadata is clean and consistent.
    """

    sample = {
        "history": {
            "templates": [
                {
                    "sections": [
                        {
                            "section_name": "Past Medical History",
                            "forms": [
                                {
                                    "data": {
                                        "conditions": ["Type 2 Diabetes Mellitus"],
                                        "comments": ""
                                    }
                                }
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
                        {
                            "sectionname": "Right Eye (R/OD)",
                            "forms": [
                                {
                                    "data": {
                                        "appearance_symptoms": ["Phthisis Bulbi"],
                                        "comments": ""
                                    }
                                }
                            ]
                        },
                        {
                            "sectionname": "Left Eye (L/OS)",
                            "forms": [
                                {
                                    "data": {
                                        "posterior_segment": "Mild NPDR changes",
                                        "misc": "normal"
                                    }
                                }
                            ]
                        }
                    ]
                }
            ]
        },
        "investigation": [
            {"name": "HbA1c", "value": "8.5", "unit": "%"}
        ]
    }

    payload = build_llm_payload(sample)

    ctx_text = " ".join(
        sum(payload["clinical_context"].values(), [])
    )
    assert "()" not in ctx_text

    audit = payload.get("meta", {}).get("audit", {})
    audit_text = " ".join(
        audit.get("discarded", []) +
        audit.get("warnings", [])
    )
    assert "()" not in audit_text

    medium = payload["clinical_context"]["medium_priority"]
    assert any("hba1c" in s.lower() for s in medium)

    assert any(
        "normal" in d.lower()
        for d in audit.get("discarded", [])
    )

    risks = payload["meta"].get("risk_flags", [])
    assert "poor glycemic control" in risks
    assert "long-standing diabetes" in risks


# ============================================================
# FORBIDDEN TERMS SAFETY TEST
# ============================================================

def test_forbidden_terms_detection():
    """
    Ensures prescriptive free-text is detected and flagged.
    """

    sample = {
        "history": {
            "templates": [
                {
                    "sections": [
                        {
                            "section_name": "Past Medical History",
                            "forms": [
                                {
                                    "data": {
                                        "notes": "Please start insulin now"
                                    }
                                }
                            ]
                        }
                    ]
                }
            ]
        },
        "examination": {},
        "investigation": []
    }

    payload = build_llm_payload(sample)

    safety = payload["meta"].get("safety", {})
    assert "forbidden_terms" in safety
    assert any(
        "start insulin" in term.lower()
        for term in safety.get("forbidden_terms", [])
    )
