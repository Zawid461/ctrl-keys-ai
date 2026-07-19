from core.llm import llm
import json

def file_task_agent(state):

    prompt = f"""
Generate ONLY a JSON list of required files.

Example:
[
  "main.py",
  "requirements.txt",
  "routes/auth.py"
]

Architecture:
{state['architecture']}
"""

    response = llm.invoke(prompt)

    try:
        files = json.loads(response.content)
    except:
        files = []

    return {
        "file_tasks": files
    }