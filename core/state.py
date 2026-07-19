from typing import TypedDict


class AgentState(TypedDict, total=False):

    # User input
    user_prompt: str

    # Planner output
    plan: str

    # Architect output
    architecture: str

    # Coder output
    generated_code: str

    # Reviewer output
    reviewed_code: str

    # File writer output
    project_path: str

    # zip file
    zip_path: str

    # Executor output
    execution_output: str
    execution_error: str

    # Debugger
    retry_count: int
    debug_attempts: int
    last_error: str

    # Generic
    success: bool
    error: str