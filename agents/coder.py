from core.llm import llm
from utils.logger import add_log
from utils.live_status import add_live_log
from utils.tavily_search import search_docs


def coder_agent(state):

    add_live_log("💻 Coder Agent generating code...")
    add_log("💻 Coder Agent generating code...")

    architecture = state["architecture"]

    # ------------------------------------
    # Search latest documentation
    # ------------------------------------

    try:

        docs = search_docs(architecture)

        documentation = ""

        for doc in docs:

            documentation += f"""
Title:
{doc.get("title","")}

URL:
{doc.get("url","")}

Content:
{doc.get("content","")}

----------------------------------------
"""

    except Exception as e:

        documentation = f"Unable to retrieve latest documentation.\n{e}"

    # ------------------------------------
    # Prompt
    # ------------------------------------

    prompt = f"""
You are CTRL KEYS — an elite autonomous software engineer.

Your task is to generate a COMPLETE production-ready software project.

================================================

PROJECT ARCHITECTURE

{architecture}

================================================

LATEST DOCUMENTATION

{documentation}

================================================

STRICT OUTPUT RULES

ONLY output project files.

Never explain.

Never summarize.

Never use markdown headings.

Never output anything except project files.

Every file MUST follow EXACTLY:

FILE: path/to/file.ext

<CODE>
...
</CODE>

================================================

ENGINEERING RULES

- No duplicate imports
- No duplicate functions
- No duplicate classes
- No placeholder code
- No TODO comments
- No fake implementations
- No incomplete files
- No recursive helper names
- No "(continued)" files
- No duplicate FILE blocks

================================================

ALWAYS GENERATE

requirements.txt

README.md

main entry point

.env.example

.gitignore

__init__.py

================================================

FASTAPI RULES

Use

from sqlalchemy.orm import declarative_base

Never use deprecated SQLAlchemy imports.

Use

from pydantic_settings import BaseSettings

Never use old BaseSettings.

Always generate proper requirements.

Use latest package versions.

================================================

Return ONLY project files.
"""

    response = llm.invoke(prompt)

    add_live_log("✅ Code generated completely")
    add_log("✅ Code generated completely")

    return {
        "generated_code": response.content
    }