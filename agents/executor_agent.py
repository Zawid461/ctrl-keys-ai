from utils.executor import run_project
from utils.live_status import add_live_log


def executor_agent(state):

    add_live_log("🏃 Executor Agent running project...")
    project_path = state.get("project_path")

    result = run_project(project_path)

    success = result.get("success", False)

    add_live_log("✅ Executor Agent completed")
    return {
        "execution_output": result.get("output", ""),
        "success": success
    }