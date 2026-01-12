import json
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt

from ai_bot.services.emr_filter import build_llm_payload
# from ai_bot.services.llm_openai import generate_summary   # real LLM later


@csrf_exempt
@require_POST
def analyze(request):
    """
    AI Bot main endpoint.
    Accepts EMR-derived payload.
    Can work with mocked data or real EMR APIs.
    """

    # =========================
    # STEP 1: Get input payload
    # =========================
    try:
        body = json.loads(request.body)
    except Exception:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    case_id = body.get("case_id")
    patient_id = body.get("patient_id")

    # =========================
    # STEP 2: DATA SOURCE
    # =========================

    # Prefer the 'emr' object in POST body; otherwise accept explicit keys; else fallback to mocked data
    emr = body.get("emr")

    if emr and isinstance(emr, dict):
        history = emr.get("history", {})
        examination = emr.get("examination", {})
        investigation = emr.get("investigation", [])
    else:
        history = body.get("history", {})
        examination = body.get("examination", {})
        investigation = body.get("investigation", [])

    # If nothing provided, keep a small mocked fallback for development convenience
    if not any((history, examination, investigation)):
        history = {
            "chief_complaint": "Blurred vision",
            "past_history": ["Diabetes Mellitus"]
        }
        examination = {
            "right_eye": "Reduced visual acuity",
            "left_eye": "Normal"
        }
        investigation = [
            {"name": "HbA1c", "value": "8.2", "unit": "%"},
        ]

    # =========================
    # STEP 3: FILTER & COMPRESS
    # =========================
    llm_payload = build_llm_payload({
        "history": history,
        "examination": examination,
        "investigation": investigation
    })

    # =========================
    # STEP 4: DETERMINISTIC REPORT GENERATOR
    # =========================
    from ai_bot.services.report_generator import generate_report

    report = generate_report(llm_payload)

    # =========================
    # STEP 5: RESPONSE
    # =========================
    response = {
        "status": "success",
        "case_id": case_id,
        "patient_id": patient_id,
        "ai_output": report.get("ai_output"),
        "meta": {
            "audit": report.get("audit") or llm_payload.get("meta", {}).get("audit"),
            "safety": llm_payload.get("meta", {}).get("safety"),
            "risk_flags": llm_payload.get("meta", {}).get("risk_flags"),
        }
    }

    return JsonResponse(response)
