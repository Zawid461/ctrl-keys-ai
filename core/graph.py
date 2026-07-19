from langgraph.graph import StateGraph, END

from core.state import AgentState

from agents.planner import planner_agent
from agents.architect import architect_agent
from agents.coder import coder_agent
from agents.reviewer import reviewer_agent
from agents.file_writer_agent import file_writer_agent
from agents.executor_agent import executor_agent
from agents.debugger import debugger_agent


# -----------------------------------
# DEBUG CONTROLLER
# -----------------------------------

def should_debug(state):

    # SUCCESS = STOP
    if state.get("success") is True:

        print("\n✅ Project executed successfully")

        return END

    # LIMIT DEBUG ATTEMPTS
    attempts = state.get("debug_attempts", 0)

    if attempts >= 3:

        print("\n🛑 Debug limit reached")

        return END

    print("\n🐞 Sending project to debugger...")

    return "debugger"


# -----------------------------------
# BUILD GRAPH
# -----------------------------------

builder = StateGraph(AgentState)

builder.add_node("planner", planner_agent)

builder.add_node("architect", architect_agent)

builder.add_node("coder", coder_agent)

builder.add_node("reviewer", reviewer_agent)

builder.add_node("file_writer", file_writer_agent)

builder.add_node("executor", executor_agent)

builder.add_node("debugger", debugger_agent)


# -----------------------------------
# FLOW
# -----------------------------------

builder.set_entry_point("planner")

builder.add_edge("planner", "architect")

builder.add_edge("architect", "coder")

builder.add_edge("coder", "reviewer")

builder.add_edge("reviewer", "file_writer")

builder.add_edge("file_writer", "executor")


# CONDITIONAL DEBUG LOOP
builder.add_conditional_edges(
    "executor",
    should_debug
)

builder.add_edge("debugger", "file_writer")


# -----------------------------------
# COMPILE GRAPH
# -----------------------------------

graph = builder.compile()