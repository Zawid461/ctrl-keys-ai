from core.llm import llm
from utils.logger import add_log
from utils.live_status import add_live_log
from utils.tavily_search import search_docs


def planner_agent(state):

    add_live_log("🧠 Planner Agent analyzing project...")
    add_log("🧠 Planner Agent thinking...")

    user_request = state["user_prompt"]

    # -----------------------------
    # Search latest documentation
    # -----------------------------
    try:
        docs = search_docs(user_request)

        documentation = ""

        for doc in docs:
            documentation += f"""
Title:
{doc.get('title', '')}

URL:
{doc.get('url', '')}

Content:
{doc.get('content', '')}

----------------------------------------
"""

    except Exception as e:

        documentation = f"Unable to fetch documentation.\nReason: {e}"

    # -----------------------------
    # Planner Prompt
    # -----------------------------
    prompt = f"""
You are a Senior Software Architect.

The user wants to build the following software.

USER REQUEST

{user_request}

------------------------------------------------

LATEST DOCUMENTATION

{documentation}

------------------------------------------------

Using the latest documentation and best software engineering practices,

Create a complete development plan.

Include:

1. Project Overview

2. Features

3. Tech Stack

4. Folder Structure

5. Required Files

6. API Routes

7. Database Models

8. Authentication Flow

9. Dependencies

10. Deployment Strategy

11. Future Scalability

Return ONLY the project plan.
"""

    response = llm.invoke(prompt)

    add_live_log("✅ Planner Agent completed")
    add_log("✅ Plan created")

    return {
        "plan": response.content
    }