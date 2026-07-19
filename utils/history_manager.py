import json
import os
from datetime import datetime

HISTORY_FILE = "project_history.json"


def load_history():
    if not os.path.exists(HISTORY_FILE):
        return []

    with open(HISTORY_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_history(history):
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=4)


def add_project(
    prompt,
    result,
    selected_file=None,
    logs=None,
    live_logs=None,
    execution_time=None,
):
    history = load_history()

    history.insert(0, {
        "prompt": prompt,
        "generated_code": result.get("generated_code", ""),
        "execution_output": result.get("execution_output", ""),
        "execution_error": result.get("execution_error", ""),
        "project_path": result.get("project_path", ""),
        "zip_path": result.get("zip_path", ""),
        "selected_file": selected_file or "",
        "execution_time": execution_time if execution_time is not None else result.get("execution_time", 0),
        "debug_attempts": result.get("debug_attempts", 0),
        "framework": result.get("framework", ""),
        "language": result.get("language", ""),
        "dependencies": result.get("dependencies", []),
        "logs": logs or [],
        "live_logs": live_logs or [],
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })

    save_history(history)