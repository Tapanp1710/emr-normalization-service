from openai import OpenAI

client = OpenAI(api_key="OPENAI_API_KEY")

def generate_summary(context: dict) -> str:
    prompt = f"""
You are a clinical assistant.

Generate:
1. Clinical Summary
2. Key Findings
3. Suggestions (non-diagnostic)

Patient Data:
{context}
"""

    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
    )

    return response.choices[0].message.content
