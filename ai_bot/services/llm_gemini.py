import google.generativeai as genai
from django.conf import settings

genai.configure(api_key='GEMINI_API_KEY')

model = genai.GenerativeModel("gemini-pro")

def generate_summary(context: dict) -> str:
    prompt = f"""
You are a clinical decision support assistant.

Based on the patient data below, generate:
1. Clinical Summary
2. Key Findings
3. Suggestions (supportive only, non-diagnostic)

Patient Data:
{context}
"""
    response = model.generate_content(prompt)
    return response.text
