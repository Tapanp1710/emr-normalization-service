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

    # -------- MOCKED DATA (CURRENT DEV MODE) --------
    history = {
        "chief_complaint": "Blurred vision",
        "past_history": ["Diabetes Mellitus"]
    }

    examination = {
        "right_eye": "Reduced visual acuity",
        "left_eye": "Normal"
    }

    investigation = {
        "HbA1c": "8.2%",
        "FBS": "160 mg/dL"
    }

    # -------- REAL EMR API (TO BE ENABLED LATER) --------
    """
    import requests

    history = requests.get(
        f"{EMR_BASE_URL}/emr/history/",
        params={"case_id": case_id, "patient_id": patient_id},
        headers={"Authorization": f"Bearer {TOKEN}"}
    ).json()

    examination = requests.get(
        f"{EMR_BASE_URL}/emr/examination/",
        params={"case_id": case_id},
        headers={"Authorization": f"Bearer {TOKEN}"}
    ).json()

    investigation = requests.get(
        f"{EMR_BASE_URL}/emr/investigation/",
        params={"case_id": case_id},
        headers={"Authorization": f"Bearer {TOKEN}"}
    ).json()
    """

    # =========================
    # STEP 3: FILTER & COMPRESS
    # =========================
    llm_payload = build_llm_payload({
        "history": history,
        "examination": examination,
        "investigation": investigation
    })

    # =========================
    # STEP 4: LLM CALL
    # =========================

    # -------- MOCKED LLM RESPONSE (CURRENT) --------
    ai_output = {
        "summary": "Patient presents with blurred vision and a history of diabetes.",
        "key_insights": [
            "Chronic diabetes with poor glycemic control",
            "Visual symptoms may be diabetes-related"
        ],
        "clinical_risks": [
            "Risk of diabetic retinopathy"
        ],
        "suggested_next_steps": [
            "Detailed retinal examination",
            "Optimize blood glucose control"
        ],
        "confidence_level": "medium"
    }

    # -------- REAL LLM CALL (TO BE ENABLED LATER) --------
    """
    ai_output = generate_summary(llm_payload)
    """

    # =========================
    # STEP 5: RESPONSE
    # =========================
    return JsonResponse({
        "status": "success",
        "case_id": case_id,
        "patient_id": patient_id,
        "ai_output": ai_output
    })
