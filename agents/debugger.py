from core.llm import llm
from utils.live_status import add_live_log


MAX_DEBUG_ATTEMPTS = 3


def debugger_agent(state):

    add_live_log("🐞 Debugger Agent debugging code...")

    attempts = state.get("debug_attempts", 0)

    print(f"\n🐞 Debug attempt: {attempts + 1}/{MAX_DEBUG_ATTEMPTS}")

    # STOP LOOP
    if attempts >= MAX_DEBUG_ATTEMPTS:

        print("\n❌ Max debug attempts reached")

        return {
            "success": False,
            "debug_attempts": attempts
        }

    execution_output = state.get(
        "execution_output",
        "No execution output"
    )

    generated_code = state.get(
        "generated_code",
        ""
    )

    prompt = f"""
You are a senior Python debugger.

Fix the project using this runtime error:

{execution_output}

IMPORTANT:
1. Return COMPLETE corrected files
2. Preserve working code
3. Do NOT explain anything
4. ONLY return FILE blocks
"""

    response = llm.invoke(prompt)

    add_live_log("✅ Errors fixed")

    return {
        "generated_code": response.content,
        "debug_attempts": attempts + 1
    }