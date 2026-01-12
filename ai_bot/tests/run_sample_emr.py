import sys, json
sys.path.insert(0, "config")
from ai_bot.services.emr_filter import build_llm_payload

sample_emr = {
    "history": {
        "templates": [
            {
                "sections": [
                    {
                        "section_name": "Past Medical History",
                        "forms": [
                            {"data": {"conditions": ["Type 2 Diabetes Mellitus", "Hypertension"], "comments": ""}},
                            {"data": {"allergies": ["Peanuts"], "notes": "normal"}}
                        ]
                    },
                    {
                        "section_name": "Social History",
                        "forms": [
                            {"data": {"smoking_status": "Former smoker"}}
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
                    {"sectionname": "Right Eye (R/OD)", "forms": [{"data": {"appearance_symptoms": ["Phthisis Bulbi"], "comments": ""}}]},
                    {"sectionname": "Left Eye (L/OS)", "forms": [{"data": {"posterior_segment": "Mild NPDR changes", "misc": "normal"}}]},
                    {"sectionname": "General", "forms": [{"data": {"blood_pressure": "120/80"}}]}
                ]
            }
        ]
    },
    "investigation": [
        {"name": "HbA1c", "value": "9.1", "unit": "%", "reference": "4.0-5.6"},
        {"name": "Random Glucose", "value": "normal", "unit": "mg/dL"},
        {"name": "Cholesterol", "value": "", "unit": "mg/dL"},
        "not_a_dict",
        {"name": "Creatinine", "value": "1.0", "unit": "mg/dL"}
    ]
}

payload = build_llm_payload(sample_emr)
print(json.dumps(payload, indent=2))
