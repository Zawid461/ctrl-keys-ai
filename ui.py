import os
import streamlit as st
import time
import threading
import re
from collections import Counter
import utils.agent_runner as agent_runner
import asyncio
import sys
import pandas as pd
import streamlit.components.v1 as components

if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(
        asyncio.WindowsSelectorEventLoopPolicy()
    )
from core.graph import graph
from core.llm import llm
from utils.logger import get_logs, clear_logs
from utils.history_manager import add_project, load_history
from utils.live_status import add_live_log, get_live_logs, clear_live_logs
from utils.executor import run_project
from utils.file_writer import save_generated_project
from utils.project_reader import get_project_files, read_project_file

st.set_page_config(
    page_title="CTRL KEYS · Multi-Agent Dev",
    page_icon="⌨",
    layout="wide",
    initial_sidebar_state="expanded"
)

if "last_result" not in st.session_state:
    st.session_state["last_result"] = None

if "history_view_active" not in st.session_state:
    st.session_state["history_view_active"] = False


def history_entry_to_result(entry):
    return {
        "generated_code": entry.get("generated_code", ""),
        "execution_output": entry.get("execution_output", ""),
        "execution_error": entry.get("execution_error", ""),
        "project_path": entry.get("project_path", ""),
        "zip_path": entry.get("zip_path", ""),
        "selected_file": entry.get("selected_file", ""),
        "execution_time": entry.get("execution_time", 0),
        "debug_attempts": entry.get("debug_attempts", 0),
        "framework": entry.get("framework", ""),
        "language": entry.get("language", ""),
        "dependencies": entry.get("dependencies", []),
    }


def format_duration(seconds):
    try:
        total_seconds = float(seconds)
    except (TypeError, ValueError):
        return "--"

    if total_seconds <= 0:
        return "--"

    if total_seconds < 60:
        return f"{total_seconds:.1f}s"

    minutes = int(total_seconds // 60)
    remaining_seconds = total_seconds % 60
    return f"{minutes}m {remaining_seconds:.0f}s"


def detect_framework(result):
    generated_code = result.get("generated_code", "").lower()
    dependencies = [item.lower() for item in result.get("dependencies", [])]
    project_path = result.get("project_path", "")

    if "streamlit" in generated_code or "streamlit" in dependencies:
        return "Streamlit"
    if "fastapi" in generated_code or "fastapi" in dependencies:
        return "FastAPI"
    if "flask" in generated_code or "flask" in dependencies:
        return "Flask"
    if project_path and os.path.exists(os.path.join(project_path, "package.json")):
        return "Node / React"
    if "django" in generated_code or "django" in dependencies:
        return "Django"
    return "Python App"


def detect_language(result):
    project_path = result.get("project_path", "")
    if project_path and os.path.exists(project_path):
        files = get_project_files(project_path)
        counts = Counter()
        for file_path in files:
            extension = file_path.rsplit(".", 1)[-1].lower() if "." in file_path else ""
            if extension:
                counts[extension] += 1

        if counts:
            dominant_extension = counts.most_common(1)[0][0]
            return {
                "py": "Python",
                "js": "JavaScript",
                "jsx": "JavaScript",
                "ts": "TypeScript",
                "tsx": "TypeScript",
                "html": "HTML",
                "css": "CSS",
                "sh": "Shell",
                "json": "JSON",
            }.get(dominant_extension, dominant_extension.upper())

    generated_code = result.get("generated_code", "").lower()
    if "from fastapi" in generated_code or "import fastapi" in generated_code:
        return "Python"
    if "import react" in generated_code or "from react" in generated_code:
        return "JavaScript"
    return "Python"


def detect_dependencies(result):
    dependencies = list(result.get("dependencies", []))
    project_path = result.get("project_path", "")

    if project_path and os.path.exists(project_path):
        for root, _, files in os.walk(project_path):
            if "requirements.txt" not in files:
                continue

            requirements_path = os.path.join(root, "requirements.txt")
            try:
                with open(requirements_path, "r", encoding="utf-8") as handle:
                    for line in handle:
                        package = line.strip()
                        if package and not package.startswith("#"):
                            dependencies.append(package)
            except Exception:
                continue

    unique_dependencies = []
    seen = set()
    for dependency in dependencies:
        normalized = dependency.strip()
        if not normalized:
            continue
        if normalized.lower() in seen:
            continue
        seen.add(normalized.lower())
        unique_dependencies.append(normalized)

    return unique_dependencies


def infer_project_dashboard(result, project_logs=None):
    project_logs = project_logs or []

    project_path = result.get("project_path", "")
    file_paths = get_project_files(project_path) if project_path and os.path.exists(project_path) else []
    folder_names = {
        os.path.dirname(path).replace("\\", "/")
        for path in file_paths
        if os.path.dirname(path)
    }

    debug_attempts = result.get("debug_attempts")
    if debug_attempts is None:
        debug_attempts = sum(1 for log in project_logs if "Debugger Agent debugging code" in log)

    execution_time = result.get("execution_time") or st.session_state.get("last_execution_time", 0)
    dependencies = detect_dependencies(result)
    framework = result.get("framework") or detect_framework({**result, "dependencies": dependencies})
    language = result.get("language") or detect_language(result)

    execution_status = "Success" if result.get("success") is True else "Failed"
    if result.get("execution_error"):
        execution_status = "Failed"
    elif result.get("execution_output") and result.get("success") is not False:
        execution_status = "Success"

    file_count = len(file_paths)
    if not file_count:
        file_count = len([
            line for line in result.get("generated_code", "").splitlines()
            if line.strip().lower().startswith("file:")
        ])

    return {
        "files_generated": file_count,
        "folders": len(folder_names),
        "execution_time": format_duration(execution_time),
        "framework": framework,
        "language": language,
        "dependencies": dependencies,
        "dependencies_label": f"{len(dependencies)} packages" if dependencies else "None",
        "debug_attempts": int(debug_attempts or 0),
        "execution_status": execution_status,
    }


def render_dashboard_card(label, value, subtext="", accent="blue"):
    st.markdown(
        f"""
        <div class="dashboard-card dashboard-card--{accent}">
            <div class="dashboard-card__label">{label}</div>
            <div class="dashboard-card__value">{value}</div>
            <div class="dashboard-card__subtext">{subtext}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_project_dashboard(result, project_logs=None):
    dashboard = infer_project_dashboard(result, project_logs)
    dependencies_preview = ", ".join(dashboard["dependencies"][:3]) if dashboard["dependencies"] else "No dependencies detected"
    if len(dashboard["dependencies"]) > 3:
        dependencies_preview += f" +{len(dashboard['dependencies']) - 3} more"

    st.markdown("""<div class="section-lbl"><span style="color:#38bdf8">▣</span> PROJECT DASHBOARD</div>""", unsafe_allow_html=True)
    st.markdown("<div class='project-dashboard-grid'>", unsafe_allow_html=True)

    columns = st.columns(4)
    with columns[0]:
        render_dashboard_card("Files Generated", str(dashboard["files_generated"]), "Generated file count", "blue")
    with columns[1]:
        render_dashboard_card("Folders", str(dashboard["folders"]), "Project folder count", "cyan")
    with columns[2]:
        render_dashboard_card("Execution Time", dashboard["execution_time"], "End-to-end run time", "blue")
    with columns[3]:
        render_dashboard_card("Framework", dashboard["framework"], "Detected project stack", "cyan")

    columns = st.columns(4)
    with columns[0]:
        render_dashboard_card("Language", dashboard["language"], "Primary code language", "blue")
    with columns[1]:
        render_dashboard_card("Dependencies", dashboard["dependencies_label"], dependencies_preview, "cyan")
    with columns[2]:
        render_dashboard_card("Debug Attempts", str(dashboard["debug_attempts"]), "Debugger pass count", "blue")
    with columns[3]:
        status_accent = "success" if dashboard["execution_status"] == "Success" else "warning"
        render_dashboard_card("Execution Status", dashboard["execution_status"], "Runtime result", status_accent)

    st.markdown("</div>", unsafe_allow_html=True)


def parse_history_timestamp(timestamp_value):
    try:
        return pd.to_datetime(timestamp_value)
    except Exception:
        return pd.NaT


def build_history_dataframe(history):
    records = []

    for index, item in enumerate(history):
        project_path = item.get("project_path", "")
        file_count = 0
        if project_path and os.path.exists(project_path):
            file_count = len(get_project_files(project_path))
        elif item.get("generated_code"):
            file_count = sum(
                1
                for line in item.get("generated_code", "").splitlines()
                if line.strip().lower().startswith("file:")
            )

        records.append({
            "index": index,
            "timestamp": parse_history_timestamp(item.get("timestamp", "")),
            "label": item.get("timestamp", f"Project {index + 1}"),
            "project_count": index + 1,
            "files_generated": file_count,
            "execution_time": float(item.get("execution_time", 0) or 0),
            "debug_attempts": int(item.get("debug_attempts", 0) or 0),
        })

    if not records:
        return pd.DataFrame()

    frame = pd.DataFrame(records)
    if frame["timestamp"].notna().any():
        frame = frame.sort_values(by=["timestamp", "index"], ascending=True)
    else:
        frame = frame.sort_values(by="index", ascending=True)

    frame["cumulative_projects"] = range(1, len(frame) + 1)
    return frame


def render_project_analytics(history=None):
    history = history if history is not None else load_history()
    frame = build_history_dataframe(history)

    st.markdown("""<div class="section-lbl"><span style="color:#38bdf8">◈</span> ANALYTICS</div>""", unsafe_allow_html=True)

    if frame.empty:
        st.markdown(
            """
            <div style="font-family:'JetBrains Mono',monospace;font-size:11px;color:#9fb2ca;padding:10px 0;font-style:italic">
            No history available yet for analytics.
            </div>
            """,
            unsafe_allow_html=True,
        )
        return

    chart_source = frame.set_index("label")

    top_row = st.columns(2)
    with top_row[0]:
        st.markdown("""<div class="analytics-card-title">Project Count</div>""", unsafe_allow_html=True)
        st.line_chart(chart_source[["cumulative_projects"]], height=240)
    with top_row[1]:
        st.markdown("""<div class="analytics-card-title">Files Generated</div>""", unsafe_allow_html=True)
        st.bar_chart(chart_source[["files_generated"]], height=240)

    bottom_row = st.columns(2)
    with bottom_row[0]:
        st.markdown("""<div class="analytics-card-title">Execution Time</div>""", unsafe_allow_html=True)
        st.bar_chart(chart_source[["execution_time"]], height=240)
    with bottom_row[1]:
        st.markdown("""<div class="analytics-card-title">Debug Attempts</div>""", unsafe_allow_html=True)
        st.bar_chart(chart_source[["debug_attempts"]], height=240)


def get_project_chat_context_files(project_path, request_text, selected_file=None):
    files = get_project_files(project_path)
    lower_request = request_text.lower()

    keywords = []
    if any(term in lower_request for term in ("jwt", "login", "auth")):
        keywords.extend(["auth", "login", "main.py", "config.py", "database", "requirements.txt", "routes", "models", "schemas"])
    if any(term in lower_request for term in ("mysql", "sqlite", "database")):
        keywords.extend(["database", "db", "main.py", "config.py", "requirements.txt", "routes", "models", "schemas"])

    prioritized_files = []
    if selected_file and selected_file in files:
        prioritized_files.append(selected_file)

    for file_path in files:
        lowered_path = file_path.lower()
        if file_path in prioritized_files:
            continue
        if any(keyword in lowered_path for keyword in keywords):
            prioritized_files.append(file_path)

    for fallback_file in files:
        if fallback_file in prioritized_files:
            continue
        if fallback_file.endswith("main.py") or fallback_file.endswith("database.py") or fallback_file.endswith("config.py"):
            prioritized_files.append(fallback_file)

    return files, prioritized_files[:8]


def build_project_chat_prompt(project_path, request_text, selected_file=None):
    files, context_files = get_project_chat_context_files(project_path, request_text, selected_file)
    tree_text = "\n".join(f"- {file_path}" for file_path in files) if files else "- (no files found)"

    context_sections = []
    for file_path in context_files:
        try:
            file_content = read_project_file(project_path, file_path)
        except Exception as exc:
            file_content = str(exc)

        context_sections.append(f"FILE: {file_path}\n<CODE>\n{file_content}\n</CODE>")

    context_text = "\n\n".join(context_sections) if context_sections else "No file content available."

    return f"""
You are editing an existing project in place.

User request:
{request_text}

Rules:
1. Do NOT regenerate the whole project.
2. Only return FILE blocks for files you changed.
3. Preserve unrelated code and files.
4. Make the smallest possible targeted edit.
5. If the request is Add JWT or Add Login, update only the needed auth, routes, config, and dependency files.
6. If the request is Convert SQLite to MySQL, update only the database, config, model, and dependency files needed for the conversion.
7. Do not include explanations, markdown, or analysis.

Current file tree:
{tree_text}

Relevant file contents:
{context_text}

Return only modified FILE blocks.
""".strip()


def parse_modified_files(response_text):
    return [match.strip() for match in re.findall(r"^FILE:\s*(.+)$", response_text, flags=re.MULTILINE)]


def apply_project_chat_update(project_path, request_text, selected_file=None):
    prompt_text = build_project_chat_prompt(project_path, request_text, selected_file)
    response = llm.invoke(prompt_text)
    response_text = getattr(response, "content", str(response))

    if "FILE:" not in response_text:
        return {
            "success": False,
            "message": "No file changes were returned.",
            "modified_files": [],
            "response_text": response_text,
        }

    save_generated_project(response_text, project_path)

    return {
        "success": True,
        "message": "Project updated in place.",
        "modified_files": parse_modified_files(response_text),
        "response_text": response_text,
    }


def render_project_chat(result):
    project_path = result.get("project_path", "")
    if not project_path or not os.path.exists(project_path):
        return

    if st.session_state.get("project_chat_project_path") != project_path:
        st.session_state["project_chat_project_path"] = project_path
        st.session_state["project_chat_messages"] = []

    if "project_chat_messages" not in st.session_state:
        st.session_state["project_chat_messages"] = []

    st.markdown("""<div class="section-lbl"><span style="color:#38bdf8">✦</span> CHAT WITH PROJECT</div>""", unsafe_allow_html=True)

    quick_left, quick_middle, quick_right = st.columns(3)
    if quick_left.button("Add JWT", use_container_width=True):
        st.session_state["project_chat_pending"] = "Add JWT"
    if quick_middle.button("Add Login", use_container_width=True):
        st.session_state["project_chat_pending"] = "Add Login"
    if quick_right.button("Convert SQLite to MySQL", use_container_width=True):
        st.session_state["project_chat_pending"] = "Convert SQLite to MySQL"

    for message in st.session_state["project_chat_messages"]:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    custom_request = st.chat_input("Ask the project to change itself without rebuilding it...")
    request_text = st.session_state.pop("project_chat_pending", None) or custom_request

    if request_text:
        selected_file = st.session_state.get("explorer_selected_file") or result.get("selected_file")
        st.session_state["project_chat_messages"].append({"role": "user", "content": request_text})

        with st.spinner("Applying a targeted project update..."):
            update_result = apply_project_chat_update(project_path, request_text, selected_file)

        if update_result["success"]:
            updated_files = get_project_files(project_path)
            if selected_file not in updated_files:
                st.session_state["explorer_selected_file"] = updated_files[0] if updated_files else ""

            result["generated_code"] = update_result["response_text"]
            st.session_state["last_result"] = result
            st.session_state["project_chat_messages"].append({
                "role": "assistant",
                "content": f"Updated {len(update_result['modified_files'])} file(s): {', '.join(update_result['modified_files']) if update_result['modified_files'] else 'project files'}",
            })
            st.rerun()
        else:
            st.session_state["project_chat_messages"].append({"role": "assistant", "content": update_result["message"]})


def write_project_file(project_path, file_path, content):
    full_path = os.path.join(project_path, file_path)
    os.makedirs(os.path.dirname(full_path), exist_ok=True)
    with open(full_path, "w", encoding="utf-8") as handle:
        handle.write(content)


def get_project_editor_state_keys(project_path):
    safe_key = project_path.replace("\\", "/")
    return {
        "selected": f"code_editor_selected::{safe_key}",
        "content": f"code_editor_content::{safe_key}",
        "loaded": f"code_editor_loaded::{safe_key}",
    }


def load_project_editor_file(project_path, file_path):
    state_keys = get_project_editor_state_keys(project_path)
    st.session_state[state_keys["selected"]] = file_path
    st.session_state[state_keys["loaded"]] = file_path
    st.session_state[state_keys["content"]] = read_project_file(project_path, file_path)


def run_existing_project(result):
    project_path = result.get("project_path", "")
    if not project_path or not os.path.exists(project_path):
        return {
            "success": False,
            "message": "Project path is not available.",
        }

    start_time = time.perf_counter()
    run_result = run_project(project_path)
    elapsed = time.perf_counter() - start_time

    updated_result = dict(result)
    updated_result["success"] = run_result.get("success", False)
    updated_result["execution_output"] = run_result.get("stdout", "")
    updated_result["execution_error"] = run_result.get("stderr", "")
    updated_result["execution_time"] = elapsed

    st.session_state["last_result"] = updated_result
    st.session_state["last_execution_time"] = elapsed
    st.session_state["history_view_active"] = True

    return {
        "success": True,
        "result": updated_result,
        "execution_time": elapsed,
    }


def render_project_code_editor(result):
    project_path = result.get("project_path", "")
    if not project_path or not os.path.exists(project_path):
        return

    files = get_project_files(project_path)
    if not files:
        return

    state_keys = get_project_editor_state_keys(project_path)
    default_file = st.session_state.get("explorer_selected_file") or result.get("selected_file") or files[0]
    if state_keys["selected"] not in st.session_state or st.session_state[state_keys["selected"]] not in files:
        st.session_state[state_keys["selected"]] = default_file if default_file in files else files[0]

    if state_keys["loaded"] not in st.session_state or st.session_state[state_keys["loaded"]] not in files:
        load_project_editor_file(project_path, st.session_state[state_keys["selected"]])

    st.markdown("""<div class="section-lbl"><span style="color:#38bdf8">▤</span> CODE EDITOR</div>""", unsafe_allow_html=True)
    st.markdown("""<div class="code-editor-card">""", unsafe_allow_html=True)

    top_left, top_mid, top_right = st.columns([2.2, 1, 1])
    with top_left:
        selected_file = st.selectbox(
            "Open file",
            files,
            key=state_keys["selected"],
            label_visibility="collapsed",
        )
    with top_mid:
        if st.button("Open file", use_container_width=True):
            load_project_editor_file(project_path, selected_file)
            st.rerun()
    with top_right:
        if st.button("Run again", use_container_width=True):
            with st.spinner("Running the existing project..."):
                run_result = run_existing_project(result)

            if run_result["success"]:
                st.success("Project rerun completed.")
                st.rerun()
            else:
                st.error(run_result["message"])

    loaded_file = st.session_state.get(state_keys["loaded"], selected_file)
    st.markdown(
        f"""
        <div style="font-family:'JetBrains Mono',monospace;font-size:10px;color:#9fb2ca;margin:4px 0 8px">
        Editing: {loaded_file}
        </div>
        """,
        unsafe_allow_html=True,
    )

    editor_content_key = state_keys["content"]
    if editor_content_key not in st.session_state:
        st.session_state[editor_content_key] = read_project_file(project_path, loaded_file)

    edited_content = st.text_area(
        "Project file editor",
        key=editor_content_key,
        height=420,
        label_visibility="collapsed",
    )

    save_left, save_right = st.columns([1, 2])
    with save_left:
        if st.button("Save file", use_container_width=True):
            try:
                write_project_file(project_path, loaded_file, edited_content)
                st.success(f"Saved {loaded_file}")
                st.session_state["explorer_selected_file"] = loaded_file
                st.session_state[state_keys["loaded"]] = loaded_file
                st.session_state["history_view_active"] = True
                st.rerun()
            except Exception as exc:
                st.error(f"Unable to save file: {exc}")
    with save_right:
        st.markdown(
            """
            <div style="font-family:'JetBrains Mono',monospace;font-size:10px;color:#6c7e96;padding-top:10px">
            Save writes directly to the existing generated project. Run again re-executes the same project folder.
            </div>
            """,
            unsafe_allow_html=True,
        )
    st.markdown("""</div>""", unsafe_allow_html=True)


def classify_console_line(line):
    lowered = line.lower()

    if any(token in lowered for token in ("error", "traceback", "exception", "failed", "✗", "❌")):
        return "red"
    if any(token in lowered for token in ("warning", "warn", "deprecated", "caution", "⚠")):
        return "yellow"
    if any(token in lowered for token in ("success", "completed", "installed", "created", "running", "done", "✅", "✓")):
        return "green"
    return "blue"


def render_vscode_console(text, title="CONSOLE", language_label="TEXT", height=300):
    lines = (text or "").splitlines()
    if not lines:
        lines = ["// no output"]

    styled_lines = []
    for index, line in enumerate(lines, start=1):
        line_class = classify_console_line(line)
        styled_lines.append(
            f"<div class='vscode-console__line vscode-console__line--{line_class}'><span class='vscode-console__line-no'>{index:>4}</span><span class='vscode-console__line-text'>{line}</span></div>"
        )

    console_html = f"""
    <div class="vscode-console" id="vscode-console">
        <div class="vscode-console__header">
            <div class="vscode-console__title">{title}</div>
            <div class="vscode-console__meta">{language_label}</div>
        </div>
        <div class="vscode-console__body" id="vscode-console-body">
            {''.join(styled_lines)}
        </div>
    </div>
    <script>
        const body = document.getElementById('vscode-console-body');
        if (body) {{
            body.scrollTop = body.scrollHeight;
        }}
    </script>
    """

    components.html(console_html, height=height, scrolling=False)


def render_project_artifacts(result, project_logs=None, live_logs=None):
    project_logs = project_logs or []
    live_logs = live_logs or []

    # Agent activity log
    st.markdown("""<div class="section-lbl"><span style="color:#60a5fa">◈</span> AGENT LOG</div>""", unsafe_allow_html=True)
    if project_logs:
        for log in project_logs:
            st.markdown(f"""
            <div style="font-family:'JetBrains Mono',monospace;font-size:12px;color:#9fb2ca;padding:3px 0;border-bottom:1px solid rgba(96,165,250,0.08)">
            › {log}
            </div>
            """, unsafe_allow_html=True)
    else:
        st.markdown("""
        <div style="font-family:'JetBrains Mono',monospace;font-size:12px;color:#6c7e96;padding:3px 0;font-style:italic">
        // no agent logs captured
        </div>
        """, unsafe_allow_html=True)

    # Live stream
    st.markdown("""<div class="section-lbl"><span style="color:#38bdf8">◉</span> LIVE STREAM</div>""", unsafe_allow_html=True)
    render_vscode_console(
        "\n".join(live_logs) if live_logs else "// no live logs captured",
        title="TERMINAL",
        language_label="LIVE",
        height=380,
    )

    # Download
    if result.get("zip_path"):
        st.markdown("""<div class="section-lbl"><span style="color:#60a5fa">↓</span> DOWNLOAD</div>""", unsafe_allow_html=True)
        with open(result["zip_path"], "rb") as f:
            st.download_button(
                "⬇  Download project.zip",
                data=f,
                file_name="generated_project.zip",
                mime="application/zip",
                use_container_width=True
            )

    # Output tabs
    st.markdown("""<div class="section-lbl"><span style="color:#dbeafe">◧</span> OUTPUT</div>""", unsafe_allow_html=True)

    tab1, tab2, tab3 = st.tabs(["[1]  CODE", "[2]  EXECUTION", "[!]  ERRORS"])

    with tab1:
        st.code(result.get("generated_code", "// no code generated"), language="python")

    with tab2:
        out = result.get("execution_output", "")
        if out:
            render_vscode_console(
                out,
                title="TERMINAL",
                language_label="OUTPUT",
                height=380,
            )
        else:
            st.markdown("""<div style="font-family:'JetBrains Mono',monospace;font-size:12px;color:#6c7e96;font-style:italic">// no execution output</div>""", unsafe_allow_html=True)

    with tab3:
        err = result.get("execution_error", "")
        if err:
            render_vscode_console(
                err,
                title="TERMINAL",
                language_label="ERROR",
                height=300,
            )
        else:
            st.success("✓  No errors detected.")

    # File explorer
    project_path = result.get("project_path")
    if project_path and os.path.exists(project_path):
        st.markdown("""<div class="section-lbl"><span style="color:#38bdf8">◫</span> FILE EXPLORER</div>""", unsafe_allow_html=True)
        files = get_project_files(project_path)
        explorer_state_key = "explorer_selected_file"

        def file_icon(file_name):
            extension = file_name.rsplit(".", 1)[-1].lower() if "." in file_name else ""
            icon_map = {
                "py": "🐍",
                "js": "🟨",
                "jsx": "⚛",
                "ts": "🔷",
                "tsx": "⚛",
                "html": "🌐",
                "css": "🎨",
                "json": "🧩",
                "yaml": "⚙",
                "yml": "⚙",
                "md": "📝",
                "sh": "⌘",
                "txt": "📄",
                "sql": "🗄",
                "toml": "⚙",
                "ini": "⚙",
                "env": "🔐",
                "png": "🖼",
                "jpg": "🖼",
                "jpeg": "🖼",
                "gif": "🖼",
                "svg": "🖼",
                "zip": "🗜",
                "pdf": "📕",
            }
            return icon_map.get(extension, "📄")

        def build_file_tree(file_paths):
            tree = {"__files__": []}
            for file_path in file_paths:
                normalized_path = file_path.replace("\\", "/")
                parts = [part for part in normalized_path.split("/") if part]
                if not parts:
                    continue

                node = tree
                for folder in parts[:-1]:
                    node = node.setdefault(folder, {"__files__": []})
                node["__files__"].append((parts[-1], normalized_path))
            return tree

        def render_file_tree(node, parent_path=""):
            folder_names = sorted(
                key for key in node.keys() if key != "__files__"
            )
            selected_path = st.session_state.get(explorer_state_key)

            for folder_name in folder_names:
                child_node = node[folder_name]
                folder_path = f"{parent_path}/{folder_name}" if parent_path else folder_name
                nested_file_count = len(child_node.get("__files__", []))
                nested_folder_count = len([key for key in child_node.keys() if key != "__files__"])
                folder_label = f"📁 {folder_name} · {nested_folder_count + nested_file_count} items"
                expanded = bool(selected_path and (selected_path == folder_path or selected_path.startswith(f"{folder_path}/")))

                with st.expander(folder_label, expanded=expanded):
                    render_file_tree(child_node, folder_path)

            file_entries = sorted(
                node.get("__files__", []),
                key=lambda item: item[0].lower()
            )

            for file_name, relative_path in file_entries:
                icon = file_icon(file_name)
                button_label = f"{icon} {file_name}"

                if st.button(
                    button_label,
                    key=f"explorer_file::{relative_path}",
                    use_container_width=True,
                ):
                    st.session_state[explorer_state_key] = relative_path
                    selected_path = relative_path

                if selected_path == relative_path:
                    st.markdown(
                        f"""
                        <div class="explorer-selected-file">
                            <div class="path">Selected: {relative_path}</div>
                            <div class="meta">{icon} {file_name}</div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

        if files:
            if explorer_state_key not in st.session_state or st.session_state.get(explorer_state_key) not in files:
                st.session_state[explorer_state_key] = result.get("selected_file") or files[0]

            render_file_tree(build_file_tree(files))

            selected = st.session_state.get(explorer_state_key)
            if selected:
                content = read_project_file(project_path, selected)
                ext = selected.rsplit(".", 1)[-1].lower() if "." in selected else "text"
                lang = {"py":"python","js":"javascript","jsx":"javascript","ts":"typescript","tsx":"typescript","html":"html",
                        "css":"css","json":"json","yaml":"yaml","yml":"yaml",
                        "md":"markdown","sh":"bash","toml":"toml","sql":"sql"}.get(ext, "text")
                st.code(content, language=lang)

            render_project_code_editor(result)
        else:
            st.markdown(
                """
                <div style="font-family:'JetBrains Mono',monospace;font-size:11px;color:#9fb2ca;padding:10px 0;font-style:italic">
                No files found in the saved project.
                </div>
                """,
                unsafe_allow_html=True,
            )

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600;700&display=swap');

:root {
    --bg-0: #05070d;
    --bg-1: #0a1020;
    --bg-2: #0f1729;
    --panel: rgba(10, 16, 32, 0.82);
    --panel-strong: rgba(5, 7, 13, 0.96);
    --border: rgba(148, 163, 184, 0.16);
    --border-strong: rgba(96, 165, 250, 0.36);
    --text: #f8fbff;
    --muted: #9fb2ca;
    --muted-2: #6c7e96;
    --blue: #60a5fa;
    --blue-strong: #2563eb;
    --cyan: #38bdf8;
    --glow: rgba(56, 189, 248, 0.22);
}

html, body, [class*="css"] {
    font-family: 'Space Grotesk', sans-serif !important;
}

body {
    background:
        radial-gradient(circle at top left, rgba(37, 99, 235, 0.22), transparent 30%),
        radial-gradient(circle at top right, rgba(56, 189, 248, 0.14), transparent 26%),
        radial-gradient(circle at bottom center, rgba(96, 165, 250, 0.10), transparent 28%),
        linear-gradient(180deg, #05070d 0%, #07101d 48%, #05070d 100%);
}

.stApp {
    color: var(--text);
    background:
        radial-gradient(circle at 20% 12%, rgba(59, 130, 246, 0.14), transparent 22%),
        radial-gradient(circle at 80% 8%, rgba(14, 165, 233, 0.10), transparent 20%),
        linear-gradient(180deg, #04060b 0%, #070d18 100%);
}

.stApp::before {
    content: '';
    position: fixed;
    inset: 0;
    pointer-events: none;
    background-image:
        linear-gradient(rgba(148, 163, 184, 0.04) 1px, transparent 1px),
        linear-gradient(90deg, rgba(148, 163, 184, 0.04) 1px, transparent 1px);
    background-size: 42px 42px;
    mask-image: linear-gradient(180deg, rgba(0,0,0,0.56), rgba(0,0,0,0.12));
    z-index: 0;
}

.main .block-container {
    position: relative;
    z-index: 1;
    padding-top: 1.4rem;
    padding-bottom: 2rem;
}

section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, rgba(7, 11, 20, 0.98), rgba(10, 16, 32, 0.96));
    border-right: 1px solid var(--border);
    box-shadow: inset -1px 0 0 rgba(96, 165, 250, 0.10);
}

section[data-testid="stSidebar"] > div {
    background: transparent;
}

.stApp h1, .stApp h2, .stApp h3, .stApp h4, .stApp h5, .stApp h6 {
    color: var(--text);
    letter-spacing: -0.02em;
}

/* TOP BAR */
.topbar {
    background: linear-gradient(180deg, rgba(10, 16, 32, 0.92), rgba(5, 7, 13, 0.96));
    border: 1px solid var(--border);
    box-shadow: 0 18px 50px rgba(2, 6, 23, 0.45), inset 0 1px 0 rgba(255,255,255,0.03);
    border-radius: 18px;
    padding: 18px 24px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 10px;
    backdrop-filter: blur(18px);
}
.topbar-logo { display: flex; align-items: center; gap: 14px; }
.topbar-keys { display: flex; gap: 4px; }
.topbar-key {
    width: 26px; height: 24px;
    background: linear-gradient(180deg, rgba(15, 23, 42, 0.98), rgba(30, 41, 59, 0.98));
    border: 1px solid rgba(96, 165, 250, 0.35);
    border-bottom-width: 4px;
    border-radius: 5px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-family: 'JetBrains Mono', monospace;
    font-size: 10px;
    font-weight: 700;
    color: #dbeafe;
    box-shadow: 0 0 0 1px rgba(8, 15, 30, 0.5), 0 0 24px rgba(56, 189, 248, 0.08);
}
.topbar-key.accent { background: linear-gradient(180deg, rgba(37, 99, 235, 0.95), rgba(30, 64, 175, 0.9)); border-color: rgba(96, 165, 250, 0.9); color: #ffffff; }
.brand-name {
    font-size: 18px;
    font-weight: 700;
    letter-spacing: 3px;
    color: #f8fbff;
}
.brand-name span { color: var(--cyan); }
.topbar-tag {
    font-family: 'JetBrains Mono', monospace;
    font-size: 10px;
    color: var(--muted-2);
    letter-spacing: 1.5px;
    margin-top: 3px;
}
.status-pill {
    display: flex;
    align-items: center;
    gap: 8px;
    font-family: 'JetBrains Mono', monospace;
    font-size: 10px;
    color: #dbeafe;
    letter-spacing: 1px;
    padding: 8px 12px;
    border-radius: 999px;
    background: rgba(8, 15, 30, 0.72);
    border: 1px solid rgba(96, 165, 250, 0.22);
}
.pulse-dot {
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background: var(--cyan);
    box-shadow: 0 0 0 6px rgba(56, 189, 248, 0.12);
}

/* HERO CARD */
.hero-card {
    background: linear-gradient(180deg, rgba(10, 16, 32, 0.94), rgba(5, 7, 13, 0.98));
    border: 1px solid rgba(96, 165, 250, 0.18);
    border-radius: 18px;
    padding: 28px 28px 26px;
    margin-bottom: 10px;
    box-shadow: 0 22px 60px rgba(2, 6, 23, 0.35), inset 0 1px 0 rgba(255,255,255,0.03);
    position: relative;
    overflow: hidden;
}
.hero-card::after {
    content: '';
    position: absolute;
    inset: 0;
    background: linear-gradient(135deg, rgba(56, 189, 248, 0.10), transparent 35%, rgba(37, 99, 235, 0.08));
    pointer-events: none;
}
.hero-tag {
    font-family: 'JetBrains Mono', monospace;
    font-size: 10px;
    color: var(--cyan);
    letter-spacing: 2px;
    margin-bottom: 8px;
}
.hero-title {
    font-size: clamp(24px, 4vw, 34px);
    font-weight: 700;
    color: #ffffff;
    line-height: 1.25;
    position: relative;
    z-index: 1;
}
.hero-title span { color: var(--cyan); }
.hero-sub {
    font-size: 13px;
    color: var(--muted);
    margin-top: 8px;
    position: relative;
    z-index: 1;
}

/* AGENT CARDS */
.agent-grid { display: grid; grid-template-columns: repeat(4,1fr); gap: 10px; margin: 10px 0 8px; }
.agent-card {
    background: linear-gradient(180deg, rgba(10, 16, 32, 0.92), rgba(5, 7, 13, 0.98));
    border: 1px solid rgba(96, 165, 250, 0.14);
    border-radius: 14px;
    padding: 16px 14px;
    position: relative;
    overflow: hidden;
    box-shadow: 0 18px 44px rgba(2, 6, 23, 0.26);
}
.agent-card::after {
    content: '';
    position: absolute;
    inset: auto 0 0 0;
    height: 1px;
    background: linear-gradient(90deg, transparent, rgba(56, 189, 248, 0.55), transparent);
}
.agent-bar { height: 3px; position: absolute; top: 0; left: 0; right: 0; border-radius: 3px 3px 0 0; }
.agent-key-icon {
    width: 36px; height: 33px; border-radius: 8px;
    border: 1.5px solid var(--ak); border-bottom-width: 5px;
    display: flex; align-items: center; justify-content: center;
    font-family: 'JetBrains Mono', monospace; font-size: 13px;
    font-weight: 700; color: var(--ak); background: rgba(8, 15, 30, 0.98);
    margin-bottom: 10px;
    box-shadow: 0 0 0 1px rgba(255,255,255,0.02), 0 0 18px rgba(96, 165, 250, 0.06);
}
.agent-name { font-size: 11px; font-weight: 700; letter-spacing: 1.5px; color: #eff6ff; }
.agent-desc { font-size: 10px; color: var(--muted-2); margin-top: 3px; line-height: 1.5; }
.agent-badge {
    position: absolute; top: 14px; right: 12px;
    font-family: 'JetBrains Mono', monospace; font-size: 9px;
    padding: 2px 8px; border-radius: 20px; background: rgba(8, 15, 30, 0.92);
    color: #dbeafe; border: 1px solid rgba(96, 165, 250, 0.18); letter-spacing: .5px;
}

/* SECTION LABEL */
.section-lbl {
    font-family: 'JetBrains Mono', monospace;
    font-size: 10px;
    color: #cbd5e1;
    letter-spacing: 2px;
    padding: 14px 0 8px;
    border-bottom: 1px solid rgba(96, 165, 250, 0.14);
    margin-bottom: 10px;
    display: flex;
    align-items: center;
    gap: 8px;
}
.section-lbl span {
    color: var(--cyan) !important;
}

/* INPUT */
.stTextArea > label { display: none !important; }
textarea {
    background: linear-gradient(180deg, rgba(10, 16, 32, 0.98), rgba(5, 7, 13, 0.98)) !important;
    color: #e5eefc !important;
    border-radius: 14px !important;
    border: 1px solid rgba(96, 165, 250, 0.18) !important;
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 13px !important;
    line-height: 1.7 !important;
    caret-color: var(--cyan) !important;
    box-shadow: inset 0 1px 0 rgba(255,255,255,0.03);
}
textarea:focus {
    border-color: rgba(56, 189, 248, 0.72) !important;
    box-shadow: 0 0 0 3px rgba(56, 189, 248, .12) !important;
}
textarea::placeholder { color: rgba(148, 163, 184, 0.45) !important; }

/* BUTTONS */
.stButton > button {
    background: linear-gradient(180deg, rgba(37, 99, 235, 0.98), rgba(29, 78, 216, 0.96));
    color: #ffffff;
    border: 1px solid rgba(96, 165, 250, 0.55);
    border-bottom-width: 3px;
    border-radius: 12px;
    font-family: 'Space Grotesk', sans-serif;
    font-weight: 700;
    font-size: 13px;
    letter-spacing: 1px;
    width: 100%;
    padding: 11px 20px;
    transition: transform .16s ease, box-shadow .16s ease, background .16s ease;
    box-shadow: 0 14px 28px rgba(37, 99, 235, 0.18);
}
.stButton > button:hover {
    background: linear-gradient(180deg, rgba(59, 130, 246, 1), rgba(37, 99, 235, 0.98));
    box-shadow: 0 18px 30px rgba(37, 99, 235, 0.26);
}
.stButton > button:active { transform: translateY(1px); border-bottom-width: 1px; }

/* TABS */
.stTabs [data-baseweb="tab-list"] {
    background: rgba(5, 7, 13, 0.92);
    border-radius: 14px 14px 0 0;
    border: 1px solid rgba(96, 165, 250, 0.12);
    border-bottom: none;
    gap: 0;
}
.stTabs [data-baseweb="tab"] {
    color: var(--muted-2);
    font-family: 'JetBrains Mono', monospace;
    font-size: 11px;
    letter-spacing: 1px;
    padding: 10px 18px;
    background: transparent;
    border-bottom: 2px solid transparent;
}
.stTabs [aria-selected="true"] { color: #eff6ff !important; border-bottom: 2px solid var(--cyan) !important; }
.stTabs [data-baseweb="tab-panel"] {
    background: linear-gradient(180deg, rgba(10, 16, 32, 0.96), rgba(5, 7, 13, 0.98));
    border: 1px solid rgba(96, 165, 250, 0.12);
    border-radius: 0 0 14px 14px;
    padding: 16px;
}

/* CODE */
.stCodeBlock, pre, code {
    background: rgba(5, 7, 13, 0.98) !important;
    border: 1px solid rgba(96, 165, 250, 0.14) !important;
    border-radius: 12px !important;
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 12px !important;
    color: #dbeafe !important;
}

/* SELECT */
.stSelectbox > label {
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 10px !important;
    color: var(--muted-2) !important;
    letter-spacing: 2px !important;
}
.stSelectbox div[data-baseweb="select"] {
    background: linear-gradient(180deg, rgba(10, 16, 32, 0.98), rgba(5, 7, 13, 0.98)) !important;
    border: 1px solid rgba(96, 165, 250, 0.16) !important;
    border-radius: 10px !important;
    color: #e5eefc !important;
    font-family: 'JetBrains Mono', monospace !important;
}

.explorer-selected-file {
    background: rgba(8, 15, 30, 0.96);
    border: 1px solid rgba(96, 165, 250, 0.18);
    border-radius: 12px;
    padding: 10px 12px;
    margin: 8px 0 10px;
    font-family: 'JetBrains Mono', monospace;
    font-size: 10px;
    letter-spacing: 0.4px;
}

.explorer-selected-file .path {
    color: #dbeafe;
}

.explorer-selected-file .meta {
    color: #9fb2ca;
    margin-top: 4px;
}

.project-dashboard-grid {
    margin-bottom: 8px;
}

.dashboard-card {
    background: linear-gradient(180deg, rgba(10, 16, 32, 0.96), rgba(5, 7, 13, 0.98));
    border: 1px solid rgba(96, 165, 250, 0.14);
    border-radius: 16px;
    padding: 14px 14px 13px;
    min-height: 112px;
    box-shadow: 0 18px 40px rgba(2, 6, 23, 0.24);
}

.dashboard-card--blue {
    box-shadow: 0 18px 40px rgba(37, 99, 235, 0.10);
}

.dashboard-card--cyan {
    box-shadow: 0 18px 40px rgba(56, 189, 248, 0.10);
}

.dashboard-card--success {
    border-color: rgba(56, 189, 248, 0.34);
}

.dashboard-card--warning {
    border-color: rgba(245, 158, 11, 0.30);
}

.dashboard-card__label {
    font-family: 'JetBrains Mono', monospace;
    font-size: 10px;
    letter-spacing: 1.8px;
    color: #9fb2ca;
    text-transform: uppercase;
}

.dashboard-card__value {
    margin-top: 12px;
    font-family: 'Space Grotesk', sans-serif;
    font-size: 24px;
    line-height: 1.05;
    font-weight: 700;
    color: #f8fbff;
    word-break: break-word;
}

.dashboard-card__subtext {
    margin-top: 8px;
    font-family: 'JetBrains Mono', monospace;
    font-size: 10px;
    color: #6c7e96;
    line-height: 1.4;
    min-height: 28px;
}

.analytics-card-title {
    margin: 10px 0 8px;
    font-family: 'JetBrains Mono', monospace;
    font-size: 10px;
    letter-spacing: 1.8px;
    color: #9fb2ca;
    text-transform: uppercase;
}

.project-chat-message {
    background: rgba(8, 15, 30, 0.72);
    border: 1px solid rgba(96, 165, 250, 0.14);
    border-radius: 14px;
    padding: 12px 14px;
    margin: 8px 0;
    font-family: 'JetBrains Mono', monospace;
    font-size: 12px;
    color: #dbeafe;
}

.project-chat-message--assistant {
    background: rgba(10, 16, 32, 0.92);
    border-color: rgba(56, 189, 248, 0.24);
}

.project-chat-message__role {
    font-size: 9px;
    letter-spacing: 1.8px;
    text-transform: uppercase;
    color: #9fb2ca;
    margin-bottom: 6px;
}

div[data-testid="stChatInput"] {
    background: rgba(10, 16, 32, 0.96);
    border-top: 1px solid rgba(96, 165, 250, 0.12);
}

.code-editor-card {
    margin-top: 10px;
    padding: 14px;
    border: 1px solid rgba(96, 165, 250, 0.14);
    border-radius: 16px;
    background: linear-gradient(180deg, rgba(10, 16, 32, 0.94), rgba(5, 7, 13, 0.98));
}

.vscode-console {
    background: #1e1e1e;
    border: 1px solid #313131;
    border-radius: 10px;
    overflow: hidden;
    box-shadow: inset 0 1px 0 rgba(255,255,255,0.03);
}

.vscode-console__header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 10px 12px;
    background: linear-gradient(180deg, #252526, #1f1f1f);
    border-bottom: 1px solid #2d2d2d;
    font-family: 'JetBrains Mono', monospace;
}

.vscode-console__title {
    color: #d4d4d4;
    font-size: 11px;
    letter-spacing: 1.4px;
}

.vscode-console__meta {
    color: #9fb2ca;
    font-size: 10px;
    letter-spacing: 1px;
}

.vscode-console__body {
    max-height: 360px;
    overflow-y: auto;
    background: #1e1e1e;
    scrollbar-color: rgba(66, 153, 225, 0.75) #1e1e1e;
    scrollbar-width: thin;
}

.vscode-console__line {
    display: flex;
    gap: 12px;
    padding: 3px 12px;
    font-family: 'JetBrains Mono', monospace;
    font-size: 12px;
    line-height: 1.55;
    white-space: pre-wrap;
    word-break: break-word;
}

.vscode-console__line-no {
    min-width: 34px;
    text-align: right;
    color: #858585;
    user-select: none;
}

.vscode-console__line-text {
    flex: 1;
}

.vscode-console__line--green .vscode-console__line-text { color: #6A9955; }
.vscode-console__line--red .vscode-console__line-text { color: #F44747; }
.vscode-console__line--yellow .vscode-console__line-text { color: #D7BA7D; }
.vscode-console__line--blue .vscode-console__line-text { color: #569CD6; }

.vscode-console__body::-webkit-scrollbar { width: 8px; }
.vscode-console__body::-webkit-scrollbar-track { background: #1e1e1e; }
.vscode-console__body::-webkit-scrollbar-thumb { background: #3c3c3c; border-radius: 8px; }
.vscode-console__body::-webkit-scrollbar-thumb:hover { background: #4d4d4d; }

/* ALERTS */
.stAlert {
    background: rgba(10, 16, 32, 0.92) !important;
    border-radius: 12px !important;
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 12px !important;
    border: 1px solid rgba(96, 165, 250, 0.14) !important;
}
.element-container .stSuccess {
    background: rgba(8, 20, 34, 0.96) !important;
    border: 1px solid rgba(56, 189, 248, 0.28) !important;
    color: #dbeafe !important;
}
.element-container .stInfo {
    background: rgba(10, 16, 32, 0.96) !important;
    border: 1px solid rgba(96, 165, 250, 0.24) !important;
    color: #dbeafe !important;
}
.element-container .stWarning {
    background: rgba(31, 21, 11, 0.96) !important;
    border: 1px solid rgba(245, 158, 11, 0.28) !important;
    color: #fde68a !important;
}

/* DOWNLOAD */
.stDownloadButton > button {
    background: linear-gradient(180deg, rgba(8, 15, 30, 0.98), rgba(7, 11, 20, 0.98));
    color: #dbeafe;
    border: 1px solid rgba(96, 165, 250, 0.22);
    border-bottom-width: 2px;
    border-radius: 12px;
    font-family: 'JetBrains Mono', monospace;
    font-weight: 600;
    font-size: 12px;
    letter-spacing: 1px;
    width: 100%;
    padding: 10px;
}
.stDownloadButton > button:hover {
    background: linear-gradient(180deg, rgba(15, 23, 42, 0.98), rgba(8, 15, 30, 0.98));
    border-color: rgba(56, 189, 248, 0.42);
}

/* EXPANDERS */
.streamlit-expanderHeader {
    background: rgba(10, 16, 32, 0.96) !important;
    border: 1px solid rgba(96, 165, 250, 0.14) !important;
    border-radius: 10px !important;
    color: #dbeafe !important;
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 11px !important;
}

/* SCROLLBAR */
::-webkit-scrollbar { width: 6px; }
::-webkit-scrollbar-track { background: #05070d; }
::-webkit-scrollbar-thumb { background: rgba(96, 165, 250, 0.26); border-radius: 6px; }
::-webkit-scrollbar-thumb:hover { background: rgba(56, 189, 248, 0.5); }

/* PROGRESS */
.stProgress > div > div { background: linear-gradient(90deg, var(--cyan), var(--blue)) !important; border-radius: 999px !important; }
.stProgress > div { background: rgba(96, 165, 250, 0.12) !important; border-radius: 999px !important; }

/* WIDE IMAGE-LIKE PANELS */
.stMarkdown, .stText, .element-container {
    color: var(--text);
}

@media (max-width: 1100px) {
    .agent-grid { grid-template-columns: repeat(2, 1fr); }
}

@media (max-width: 700px) {
    .topbar, .hero-card { padding: 18px; }
    .agent-grid { grid-template-columns: 1fr; }
    .topbar { flex-direction: column; align-items: flex-start; gap: 14px; }
}
</style>
""", unsafe_allow_html=True)


# ── TOP BAR ────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="topbar">
  <div class="topbar-logo">
    <div class="topbar-keys">
      <div class="topbar-key accent">C</div>
      <div class="topbar-key">T</div>
      <div class="topbar-key">R</div>
      <div class="topbar-key accent">L</div>
    </div>
    <div>
      <div class="brand-name"><span>CTRL</span> KEYS</div>
      <div class="topbar-tag">// AUTONOMOUS MULTI-AGENT DEVELOPMENT SYSTEM</div>
    </div>
  </div>
  <div class="status-pill">
    <div class="pulse-dot"></div>
        SYSTEMS OPTIMIZED
  </div>
</div>
""", unsafe_allow_html=True)


# ── HERO ───────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="hero-card">
  <div class="hero-tag">// PRESS ANY KEY TO BEGIN</div>
  <div class="hero-title">Build production software<br>with <span>four AI agents</span> — automatically.</div>
    <div class="hero-sub">Describe your idea. Planner, Architect, Coder, and Executor collaborate inside a focused blue-black command interface.</div>
</div>
""", unsafe_allow_html=True)


# ── AGENT STATUS CARDS ─────────────────────────────────────────────────────────
st.markdown("""
<div class="agent-grid">
    <div class="agent-card" style="--ak:#60a5fa">
        <div class="agent-bar" style="background:linear-gradient(90deg,#2563eb,#38bdf8)"></div>
    <div class="agent-key-icon">P</div>
    <div class="agent-name">PLANNER</div>
    <div class="agent-desc">Breaks ideas into structured task trees</div>
    <div class="agent-badge">IDLE</div>
  </div>
    <div class="agent-card" style="--ak:#38bdf8">
        <div class="agent-bar" style="background:linear-gradient(90deg,#0ea5e9,#38bdf8)"></div>
    <div class="agent-key-icon">A</div>
    <div class="agent-name">ARCHITECT</div>
    <div class="agent-desc">Designs system structure and file schema</div>
    <div class="agent-badge">IDLE</div>
  </div>
    <div class="agent-card" style="--ak:#dbeafe">
        <div class="agent-bar" style="background:linear-gradient(90deg,#94a3b8,#dbeafe)"></div>
    <div class="agent-key-icon">C</div>
    <div class="agent-name">CODER</div>
    <div class="agent-desc">Writes clean production-ready code files</div>
    <div class="agent-badge">IDLE</div>
  </div>
    <div class="agent-card" style="--ak:#93c5fd">
        <div class="agent-bar" style="background:linear-gradient(90deg,#2563eb,#93c5fd)"></div>
    <div class="agent-key-icon">X</div>
    <div class="agent-name">EXECUTOR</div>
    <div class="agent-desc">Runs, tests and validates all output</div>
    <div class="agent-badge">IDLE</div>
  </div>
</div>
""", unsafe_allow_html=True)


# ── SIDEBAR ────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("""
    <div style="padding:20px 16px 16px;border-bottom:1px solid #1a1a28;margin-bottom:10px">
      <div style="display:flex;align-items:center;gap:10px">
        <div style="display:flex;gap:3px">
                    <div style="width:20px;height:18px;background:#0b1220;border:1.5px solid #2563eb;border-bottom-width:3px;border-radius:4px;display:flex;align-items:center;justify-content:center;font-family:'JetBrains Mono',monospace;font-size:9px;font-weight:700;color:#dbeafe">C</div>
                    <div style="width:20px;height:18px;background:#0b1220;border:1.5px solid #1d4ed8;border-bottom-width:3px;border-radius:4px;display:flex;align-items:center;justify-content:center;font-family:'JetBrains Mono',monospace;font-size:9px;font-weight:700;color:#dbeafe">T</div>
                    <div style="width:20px;height:18px;background:#0b1220;border:1.5px solid #1d4ed8;border-bottom-width:3px;border-radius:4px;display:flex;align-items:center;justify-content:center;font-family:'JetBrains Mono',monospace;font-size:9px;font-weight:700;color:#dbeafe">R</div>
                    <div style="width:20px;height:18px;background:#0f172a;border:1.5px solid #38bdf8;border-bottom-width:3px;border-radius:4px;display:flex;align-items:center;justify-content:center;font-family:'JetBrains Mono',monospace;font-size:9px;font-weight:700;color:#ffffff">L</div>
        </div>
                <span style="font-family:'Space Grotesk',sans-serif;font-weight:700;font-size:15px;letter-spacing:2px;color:#f8fbff"><span style="color:#38bdf8">CTRL</span> KEYS</span>
      </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div style="font-family:'JetBrains Mono',monospace;font-size:9px;color:#6c7e96;letter-spacing:2px;padding:0 14px 8px">
    RECENT PROJECTS
    </div>
    """, unsafe_allow_html=True)

    history = load_history()
    if not history:
        st.markdown("""
        <div style="font-family:'JetBrains Mono',monospace;font-size:11px;color:#6c7e96;padding:10px 14px;font-style:italic">
        No projects yet.
        </div>
        """, unsafe_allow_html=True)
    else:
        for index, item in enumerate(history[:10]):
            with st.expander(f"› {item['prompt'][:32]}..."):
                st.markdown(f"""
                <div style="font-family:'JetBrains Mono',monospace;font-size:9px;color:#9fb2ca;margin-bottom:6px">
                {item['timestamp']}
                </div>
                """, unsafe_allow_html=True)
                st.code(item["prompt"], language="text")
                history_result = history_entry_to_result(item)
                if st.button("↩ Reload", key=f"reload_{index}_{item['timestamp']}"):
                    st.session_state["prompt"] = item["prompt"]
                    st.session_state["last_result"] = history_result
                    st.session_state["history_view_active"] = True
                    st.session_state["explorer_selected_file"] = item.get("selected_file", "")
                    st.session_state["history_logs"] = item.get("logs", [])
                    st.session_state["history_live_logs"] = item.get("live_logs", [])
                    st.rerun()


# ── PROMPT INPUT ───────────────────────────────────────────────────────────────
st.markdown("""
<div class="section-lbl">
    <span style="background:#0f172a;border:1px solid #38bdf8;border-radius:4px;padding:2px 8px;font-size:9px;color:#dbeafe">_</span>
  DESCRIBE YOUR IDEA
</div>
""", unsafe_allow_html=True)

prompt = st.text_area(
    "idea",
    value=st.session_state.get("prompt", ""),
    height=160,
    placeholder="// e.g. Build a REST API with JWT auth, SQLite database, and Swagger docs...\n// e.g. Create a React dashboard with WebSocket real-time data and Chart.js...",
    label_visibility="collapsed"
)

col_left, col_right = st.columns([4, 1.2])
with col_left:
    st.markdown(f"""
    <div style="font-family:'JetBrains Mono',monospace;font-size:10px;color:#6c7e96;padding-top:10px">
    {len(prompt)} chars · describe in plain english or pseudo-code
    </div>
    """, unsafe_allow_html=True)
with col_right:
    generate = st.button("⌨  GENERATE PROJECT", use_container_width=True)

if st.session_state.get("history_view_active") and st.session_state.get("last_result") and not generate:
    st.markdown("""
    <div class="section-lbl" style="margin-top:16px">
                <span style="color:#38bdf8">⟲</span> HISTORY SNAPSHOT
    </div>
    """, unsafe_allow_html=True)
    render_project_dashboard(
        st.session_state["last_result"],
        st.session_state.get("history_logs", []),
    )
    render_project_analytics(load_history())
    render_project_chat(st.session_state["last_result"])
    render_project_artifacts(
        st.session_state["last_result"],
        st.session_state.get("history_logs", []),
        st.session_state.get("history_live_logs", [])
    )


# ── GENERATION ─────────────────────────────────────────────────────────────────
if generate:
    if not prompt.strip():
        st.warning("⚠  Enter a project idea first.")
    else:
        st.session_state["history_view_active"] = False
        st.markdown("""
        <div class="section-lbl" style="margin-top:16px">
            <span style="color:#38bdf8">▶</span> AGENT PIPELINE
        </div>
        """, unsafe_allow_html=True)

        status_panel = st.empty()
        bar = st.progress(0)

        stages = [
            {"key": "planner", "label": "Planner", "emoji": "🧠", "keywords": ("planner",)},
            {"key": "architect", "label": "Architect", "emoji": "🏗", "keywords": ("architect",)},
            {"key": "coder", "label": "Coder", "emoji": "💻", "keywords": ("coder",)},
            {"key": "reviewer", "label": "Reviewer", "emoji": "🔍", "keywords": ("reviewer",)},
            {"key": "writer", "label": "Writer", "emoji": "📂", "keywords": ("file writer", "writer", "saving files")},
            {"key": "executor", "label": "Executor", "emoji": "🏃", "keywords": ("executor", "running project")},
            {"key": "debugger", "label": "Debugger", "emoji": "🐞", "keywords": ("debugger", "debug")},
        ]

        def detect_stage_index(message):
            lowered = message.lower()
            for index, stage in enumerate(stages):
                if any(keyword in lowered for keyword in stage["keywords"]):
                    return index
            return None

        def is_completion_message(message):
            lowered = message.lower()
            return any(token in lowered for token in ("completed", "successfully", "fixed", "written"))

        def render_status_panel(logs_snapshot):
            latest_message = logs_snapshot[-1] if logs_snapshot else "Starting generation..."
            stage_states = ["pending"] * len(stages)
            active_index = None

            for log_message in logs_snapshot:
                stage_index = detect_stage_index(log_message)
                if stage_index is None:
                    continue

                if is_completion_message(log_message):
                    stage_states[stage_index] = "done"
                    active_index = stage_index
                else:
                    for prior_index in range(stage_index):
                        if stage_states[prior_index] == "pending":
                            stage_states[prior_index] = "done"
                    stage_states[stage_index] = "active"
                    active_index = stage_index

            completed_count = sum(1 for state in stage_states if state == "done")
            active_count = sum(1 for state in stage_states if state == "active")
            progress_value = min((completed_count + (active_count * 0.35)) / len(stages), 0.98)
            current_label = stages[active_index]["label"] if active_index is not None else "Planner"
            current_state = "running" if active_index is not None else "queued"

            chip_html = []
            for index, stage in enumerate(stages):
                state = stage_states[index]
                if state == "done":
                    background = "rgba(8, 15, 30, 0.96)"
                    border = "rgba(56, 189, 248, 0.42)"
                    color = "#dbeafe"
                    box_shadow = "none"
                    badge = "DONE"
                    fill_width = "100%"
                elif state == "active":
                    background = "rgba(37, 99, 235, 0.16)"
                    border = "rgba(56, 189, 248, 0.76)"
                    color = "#f8fbff"
                    box_shadow = "0 0 0 1px rgba(56, 189, 248, 0.10), 0 0 24px rgba(56, 189, 248, 0.12)"
                    badge = "LIVE"
                    fill_width = "100%"
                else:
                    background = "rgba(8, 15, 30, 0.72)"
                    border = "rgba(148, 163, 184, 0.16)"
                    color = "#9fb2ca"
                    box_shadow = "none"
                    badge = "WAIT"
                    fill_width = "0%"

                chip_html.append(f"""
                    <div style="background:{background};border:1px solid {border};border-radius:12px;padding:10px 10px 9px;box-shadow:{box_shadow};min-height:76px;">
                        <div style="font-family:'JetBrains Mono',monospace;font-size:10px;letter-spacing:1px;color:{color};display:flex;justify-content:space-between;align-items:center;gap:8px;">
                            <span>{stage['emoji']} {stage['label']}</span>
                            <span style="opacity:.8">{badge}</span>
                        </div>
                        <div style="margin-top:8px;height:5px;border-radius:999px;background:rgba(148,163,184,0.12);overflow:hidden;">
                            <div style="height:100%;width:{fill_width};background:linear-gradient(90deg,#2563eb,#38bdf8);border-radius:999px;"></div>
                        </div>
                    </div>
                """)

            status_panel.markdown(f"""
                <div style="background:linear-gradient(180deg, rgba(10, 16, 32, 0.96), rgba(5, 7, 13, 0.98));border:1px solid rgba(96, 165, 250, 0.18);border-radius:16px;padding:14px 14px 12px;box-shadow:0 18px 44px rgba(2, 6, 23, 0.32);">
                    <div style="display:flex;justify-content:space-between;align-items:center;gap:12px;">
                        <div>
                            <div style="font-family:'JetBrains Mono',monospace;font-size:10px;letter-spacing:2px;color:#38bdf8;">REAL-TIME STATUS</div>
                            <div style="margin-top:4px;font-family:'Space Grotesk',sans-serif;font-size:16px;font-weight:700;color:#f8fbff;">{current_label}</div>
                        </div>
                        <div style="text-align:right;">
                            <div style="font-family:'JetBrains Mono',monospace;font-size:10px;letter-spacing:2px;color:#9fb2ca;">PHASE</div>
                            <div style="margin-top:4px;font-family:'JetBrains Mono',monospace;font-size:14px;font-weight:700;color:#dbeafe;">{current_state.upper()}</div>
                        </div>
                    </div>
                    <div style="margin-top:10px;height:8px;background:rgba(148,163,184,0.10);border-radius:999px;overflow:hidden;">
                        <div style="height:100%;width:{max(4, int(progress_value * 100))}%;background:linear-gradient(90deg,#2563eb,#38bdf8);border-radius:999px;transition:width .18s ease;"></div>
                    </div>
                    <div style="margin-top:8px;font-family:'JetBrains Mono',monospace;font-size:10px;color:#9fb2ca;letter-spacing:1px;display:flex;justify-content:space-between;gap:10px;flex-wrap:wrap;">
                        <span>LIVE LOG: {latest_message}</span>
                        <span>{int(progress_value * 100)}%</span>
                    </div>
                    <div style="margin-top:12px;display:grid;grid-template-columns:repeat(7,minmax(0,1fr));gap:8px;">
                        {''.join(chip_html)}
                    </div>
                </div>
            """, unsafe_allow_html=True)
            bar.progress(progress_value)

        clear_logs()
        clear_live_logs()

        start_time = time.perf_counter()

        thread = threading.Thread(
            target=agent_runner.run_graph,
            args=(
                graph,
                {
                    "user_prompt": prompt,
                    "retry_count": 0,
                },
            ),
        )

        thread.start()

        while agent_runner.generation_running:
            render_status_panel(get_live_logs())
            time.sleep(0.2)

        result = agent_runner.generation_result

        if result:
            execution_time = time.perf_counter() - start_time
            st.session_state["last_result"] = result
            st.session_state["history_logs"] = get_logs()
            st.session_state["history_live_logs"] = get_live_logs()
            st.session_state["last_execution_time"] = execution_time
            result["execution_time"] = execution_time
            add_project(
                prompt,
                result,
                selected_file=st.session_state.get("explorer_selected_file"),
                logs=st.session_state.get("history_logs", []),
                live_logs=st.session_state.get("history_live_logs", []),
                execution_time=execution_time,
            )
        else:
            st.error("❌ Project generation failed")
            st.stop()

        render_status_panel(get_live_logs())
        bar.progress(1.0)
        status_panel.success("✓  Project generated successfully.")

        render_project_dashboard(
            result,
            st.session_state.get("history_logs", []),
        )
        render_project_analytics(load_history())
        render_project_chat(result)

        render_project_artifacts(
            result,
            st.session_state.get("history_logs", []),
            st.session_state.get("history_live_logs", []),
        )