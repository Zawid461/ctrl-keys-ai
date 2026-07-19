from core.llm import llm
from utils.logger import add_log
from utils.live_status import add_live_log

def reviewer_agent(state):

    add_log("🔍 Reviewer Agent reviewing code...")
    add_live_log("🔍 Reviewer Agent reviewing code...")

    prompt = f"""
You are a senior code reviewer.

ONLY return project files.

Rules:
- No explanations
- No analysis
- No markdown headings
- Use this exact format:

FILE: main.py

CODE:
print("hello")

FILE: requirements.txt

CODE:
fastapi
uvicorn

Project Code:
{state['generated_code']}
"""

    response = llm.invoke(prompt)

    add_log("✅ reviewed completely")
    add_live_log("✅ Reviewer Agent completed")

    return {
        "reviewed_code": response.content
    }