import os
import json

# Ensure Django settings are configured when running tests directly
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
import django
django.setup()

from django.test import RequestFactory
from ai_bot.views import analyze


def test_analyze_endpoint_with_emr_payload():
    rf = RequestFactory()

    sample_emr = {
        "history": {
            "templates": [
                {
                    "sections": [
                        {
                            "section_name": "Past Medical History",
                            "forms": [
                                {"data": {"conditions": ["Type 2 Diabetes Mellitus"], "comments": ""}}
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
                        {"sectionname": "Right Eye (R/OD)", "forms": [{"data": {"appearance_symptoms": ["Phthisis Bulbi"]}}]}
                    ]
                }
            ]
        },
        "investigation": [
            {"name": "HbA1c", "value": "9.1", "unit": "%"}
        ]
    }

    body = {"case_id": "case-1", "patient_id": "pat-1", "emr": sample_emr}
    req = rf.post("/ai_bot/analyze/", data=json.dumps(body), content_type="application/json")

    resp = analyze(req)
    assert resp.status_code == 200

    payload = json.loads(resp.content)
    assert payload.get("status") == "success"
    assert payload.get("case_id") == "case-1"
    assert payload.get("patient_id") == "pat-1"

    ai_out = payload.get("ai_output", {})
    assert "summary" in ai_out
    assert isinstance(ai_out.get("key_insights"), list)

    meta = payload.get("meta", {})
    assert "audit" in meta and "safety" in meta


def test_analyze_endpoint_forbidden_term_warning():
    rf = RequestFactory()

    sample_emr = {
        "history": {
            "templates": [
                {
                    "sections": [
                        {
                            "section_name": "Past Medical History",
                            "forms": [
                                {"data": {"notes": "Please start insulin now"}}
                            ]
                        }
                    ]
                }
            ]
        }
    }

    body = {"case_id": "c2", "patient_id": "p2", "emr": sample_emr}
    req = rf.post("/ai_bot/analyze/", data=json.dumps(body), content_type="application/json")

    resp = analyze(req)
    assert resp.status_code == 200

    payload = json.loads(resp.content)
    ai_out = payload.get("ai_output", {})
    assert "safety_warnings" in ai_out
    assert any("start insulin" in s.lower() for s in ai_out.get("safety_warnings", []))
