from core.llm import llm
from utils.live_status import add_live_log
from utils.logger import add_log

def architect_agent(state):

    add_log("🏗 Architect designing system...")
    add_live_log("🏗 Architect designing system...")

    prompt = f"""
    You are a senior software architect.

    Based on this project plan:

    {state['plan']}

    Create:

    1. Folder structure
    2. File names
    3. Responsibility of each file
    4. Tech architecture
    5. Backend/frontend separation if needed

    Return clean structured output.
    """

    response = llm.invoke(prompt)
    
    add_log("✅ Architecture designed")
    add_live_log("✅ Architect completed")

    return {
        "architecture": response.content
    }